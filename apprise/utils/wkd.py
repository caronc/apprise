# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Web Key Directory (WKD) support for automatic OpenPGP key discovery.
#
# WKD allows an email client to automatically fetch a recipient's public
# PGP key by querying a well-known HTTPS endpoint on the recipient's mail
# domain.  No manual key exchange is required: if the recipient's provider
# publishes their key via WKD, Apprise can encrypt outbound email without
# any user-visible configuration.
#
# Two URL forms are tried, in order (RFC 9080 / draft-koch-openpgp-webkey-
# service):
#
#   Subdomain method (preferred):
#     https://openpgpkey.{domain}/.well-known/openpgpkey/{domain}/hu/{hash}
#         ?l={localpart}
#
#   Direct method (fallback):
#     https://{domain}/.well-known/openpgpkey/hu/{hash}?l={localpart}
#
# The {hash} is a z-base32-encoded SHA-1 digest of the lower-cased local
# part of the email address.
#
# References:
#   https://wiki.gnupg.org/WKD
#   https://datatracker.ietf.org/doc/html/rfc9080

from datetime import datetime, timedelta, timezone
import hashlib
from urllib.parse import quote

import requests

from ..asset import AppriseAsset
from ..exception import ApprisePluginException
from ..logger import logger
from .parse import is_hostname


class AppriseWKDException(ApprisePluginException):
    """Raised when a WKD operation fails in an unrecoverable way."""

    def __init__(self, message, error_code=610):
        super().__init__(message, error_code=error_code)


class AppriseWKDController:
    """Web Key Directory controller for automatic OpenPGP key discovery.

    Fetches binary OpenPGP public key material for a given email address
    by querying the two WKD URL forms defined in RFC 9080.  Results are
    cached in memory to avoid redundant network requests within a single
    Apprise session.

    This class is intentionally decoupled from pgpy: it returns raw bytes
    and leaves key parsing to the caller (ApprisePGPController).  That
    separation makes it reusable for any future consumer that works with
    OpenPGP key material.
    """

    # z-base32 encoding alphabet (RFC 6189, used by the WKD hash)
    _ZB32 = "ybndrfg8ejkmcpqxot1uwisza345h769"

    # Upper bound on accepted WKD response size (64 KiB)
    max_response_size = 65536

    # How long fetched keys are kept in the in-memory cache (24 hours)
    default_cache_expiry_sec = 60 * 60 * 24

    def __init__(
        self,
        asset=None,
        verify_certificate=True,
        request_timeout=(4, 4),
        allow_redirects=True,
    ):
        """Initialise the WKD controller.

        Args:
            asset: Optional AppriseAsset used for the User-Agent string.
            verify_certificate: Whether TLS certificates are verified.
            request_timeout: (connect, read) timeout tuple passed to
                requests.get().
            allow_redirects: Whether HTTP redirects are followed.  WKD
                deployments commonly redirect (e.g. shared hosting), so
                this defaults to True.  Set to False to require a direct
                response from the WKD host.
        """

        # Prepare our Asset Object
        self.asset = (
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()
        )

        # TLS verification flag
        self.verify_certificate = verify_certificate

        # (connect, read) timeouts
        self.request_timeout = request_timeout

        # Whether to follow HTTP redirects
        self.allow_redirects = allow_redirects

        # In-memory cache: lower-cased email -> {data, expires}
        self._cache = {}

    @classmethod
    def zb32_encode(cls, data):
        """Return the z-base32 encoding of *data* (bytes).

        z-base32 is a human-oriented base-32 encoding (RFC 6189) used by
        WKD to build the hash component of the lookup URL.  Each group of
        five bits maps to one character in cls._ZB32.

        For a SHA-1 digest (20 bytes = 160 bits) this always produces
        exactly 32 characters with no padding.
        """

        result = []
        acc = 0
        bits = 0

        # Accumulate bits and emit one character per 5-bit group
        for byte in data:
            acc = (acc << 8) | byte
            bits += 8
            while bits >= 5:
                bits -= 5
                result.append(cls._ZB32[(acc >> bits) & 0x1F])

        # Emit any leftover bits, left-shifted to fill a 5-bit slot
        if bits:
            result.append(cls._ZB32[(acc << (5 - bits)) & 0x1F])

        return "".join(result)

    @classmethod
    def wkd_urls(cls, email):
        """Return the (subdomain_url, direct_url) pair for *email*.

        Returns (None, None) when *email* is not a valid address.
        """

        # Validate and split the email address
        if not isinstance(email, str) or not email or "@" not in email:
            return None, None

        try:
            # Split before lowercasing so the original local-part case
            # is preserved for the ?l= query parameter (RFC 9080 requires
            # the unchanged local-part; only the hash uses lowercase)
            local_orig, domain = email.split("@", 1)
            local = local_orig.lower()
            domain = domain.lower()
        except (ValueError, AttributeError):
            return None, None

        if not local or not domain:
            return None, None

        # Reject domains that fail hostname validation.  Without this, a
        # crafted email like user@legit.com@attacker.test splits to
        # domain="legit.com@attacker.test", causing the WKD request to
        # reach attacker.test with legit.com as URL credentials.
        if not is_hostname(domain, ipv4=False, ipv6=False, underscore=False):
            return None, None

        # SHA-1 of the lower-cased local part, then z-base32 encoded
        hash_val = cls.zb32_encode(
            hashlib.sha1(local.encode("utf-8")).digest()
        )

        # URL-encode the original (unchanged) local part for ?l= per RFC 9080
        quoted_local = quote(local_orig)

        # Subdomain method (preferred per RFC 9080)
        subdomain_url = (
            "https://openpgpkey.{domain}"
            "/.well-known/openpgpkey/{domain}"
            "/hu/{h}?l={l}"
        ).format(domain=domain, h=hash_val, l=quoted_local)

        # Direct method (fallback)
        direct_url = (
            "https://{domain}/.well-known/openpgpkey/hu/{h}?l={l}"
        ).format(domain=domain, h=hash_val, l=quoted_local)

        return subdomain_url, direct_url

    def fetch(self, email):
        """Return binary OpenPGP key material for *email* via WKD.

        Tries the subdomain method first, then the direct method.
        Returns bytes on success, or None when no key is found or the
        email address is invalid.

        Results are cached in memory for default_cache_expiry_sec seconds
        so repeated calls within a session avoid unnecessary round-trips.
        """

        # Reject obviously invalid input
        if not isinstance(email, str) or not email or "@" not in email:
            return None

        # Normalise for cache lookups
        email_key = email.lower().strip()

        # Return cached entry when it has not expired
        cached = self._cache.get(email_key)
        if cached and cached["expires"] > datetime.now(timezone.utc):
            logger.debug("WKD cache hit for %s", email_key)
            return cached["data"]

        # Build the two WKD URLs; pass the stripped original (not the
        # lowercased key) so wkd_urls() can preserve the local-part case
        # in the ?l= parameter as required by RFC 9080
        subdomain_url, direct_url = self.wkd_urls(email.strip())
        if not subdomain_url:
            # wkd_urls() returned None, None -- email was malformed
            return None

        # Try subdomain method first, direct method as fallback
        for url in (subdomain_url, direct_url):
            key_data = self._get(url)
            if key_data is not None:
                # Store in cache before returning
                self._cache[email_key] = {
                    "data": key_data,
                    "expires": datetime.now(timezone.utc)
                    + timedelta(seconds=self.default_cache_expiry_sec),
                }
                logger.debug(
                    "WKD key fetched for %s (%d bytes)",
                    email_key,
                    len(key_data),
                )
                return key_data

        logger.debug("No WKD key found for %s", email_key)
        return None

    def _get(self, url):
        """Perform a single GET request and return the response body.

        Returns bytes when the server responds with HTTP 200 and a
        non-empty body within max_response_size, or None for any other
        outcome (network error, non-200 status, empty or oversized body).
        """

        logger.debug("WKD GET %s", url)

        try:
            with requests.get(
                url,
                headers={"User-Agent": self.asset.app_id},
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.allow_redirects,
                # Stream so we can abort early without buffering everything
                stream=True,
            ) as r:
                if r.status_code != requests.codes.ok:
                    logger.debug(
                        "WKD returned HTTP %d for %s", r.status_code, url
                    )
                    return None

                # Verify the final URL after any redirects is still HTTPS.
                # Following a redirect to HTTP would expose the key material
                # to interception and break the WKD trust model.
                if not r.url.lower().startswith("https://"):
                    logger.debug(
                        "WKD redirect ended on non-HTTPS URL for %s; skipping",
                        url,
                    )
                    return None

                # Reject early when the server advertises an oversized body
                # before we read a single byte
                content_length = r.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        if int(content_length) > self.max_response_size:
                            logger.warning(
                                "WKD response too large (%s bytes) for"
                                " %s; skipping",
                                content_length,
                                url,
                            )
                            return None
                    except (TypeError, ValueError):
                        # Malformed Content-Length; let the chunk
                        # accumulation guard catch any actual oversize
                        pass

                # Consume the body in 8 KiB chunks, checking cumulative
                # size after each chunk so we abort before the full body
                # is in memory
                content = bytearray()
                for chunk in r.iter_content(chunk_size=8192):
                    if not chunk:
                        continue
                    content.extend(chunk)
                    if len(content) > self.max_response_size:
                        logger.warning(
                            "WKD response too large (%d bytes) for"
                            " %s; skipping",
                            len(content),
                            url,
                        )
                        return None

                content = bytes(content)

        except Exception as exc:
            # Connection refused, DNS failure, TLS error, timeout mid-
            # stream, disk full, connection reset, IncompleteRead, etc.
            logger.debug("WKD request failed for %s: %s", url, str(exc))
            return None

        if not content:
            logger.debug("WKD returned empty body for %s", url)
            return None

        # Reject obvious non-PGP responses (e.g. an HTML error page served
        # with HTTP 200 by a CDN or parked domain at the subdomain endpoint).
        # Every OpenPGP binary packet has bit 7 set in its first byte; ASCII-
        # armoured keys start with "-----".  HTML/JSON/text does not match
        # either pattern, so we can skip the direct-method fallback slot from
        # being silently eaten by a bad subdomain response.
        if not (content[0] & 0x80 or content.startswith(b"-----")):
            logger.debug("WKD response for %s is not PGP data; skipping", url)
            return None

        return content

    def prune(self):
        """Remove expired entries from the in-memory cache."""
        now = datetime.now(timezone.utc)
        self._cache = {
            k: v for k, v in self._cache.items() if v["expires"] > now
        }
