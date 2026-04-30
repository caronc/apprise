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

# Create an account https://gateway.threema.ch/en/ if you don't already have
# one.
#
# Two messaging modes are supported:
#
#  Basic Mode (default):
#    Messages are encrypted server-side by Threema. Requires a "Basic"
#    Gateway ID. Supports Threema ID, phone number, and email targets.
#    Read more: https://gateway.threema.ch/en/developer/api
#
#  End-to-End (E2E) Mode (?mode=e2e):
#    Messages are encrypted on your machine before transmission using
#    NaCl (Curve25519 + XSalsa20-Poly1305). Requires an "E2E" Gateway
#    ID and your Curve25519 private key. Only Threema ID targets are
#    supported in this mode. Requires: pip install PyNaCl
#    Read more: https://gateway.threema.ch/en/developer/api
#
# Syntax:
#   Basic:  threema://{gateway_id}@{secret}/{targets}
#   E2E:    threema://{gateway_id}@{secret}/{targets}?mode=e2e
#             &privkey={your_private_key}
#
# Where:
#   gateway_id   - Your 8-character Gateway ID (e.g., *MYGWYID)
#   secret       - The API secret associated with your Gateway ID
#   targets      - Threema ID, phone number(s), or email address(es)
#   privkey      - Your Curve25519 private key (E2E mode only).
#                  Accepts either the raw 64-character hex string shown
#                  in the Threema Gateway portal, OR the full SDK format
#                  with the "private:" prefix (both work):
#                    ?privkey=aabbcc...  (raw hex, 64 chars)
#                    ?privkey=private:aabbcc...  (SDK format)

from itertools import chain
import os

import requests

try:
    from nacl.public import (
        Box as _NaclBox,
        PrivateKey as _NaclPrivateKey,
        PublicKey as _NaclPublicKey,
    )
    from nacl.utils import random as _nacl_random

    _NACL_NONCE_SIZE = _NaclBox.NONCE_SIZE
    NACL_SUPPORT = True

except ImportError:
    _NaclBox = None
    _NaclPrivateKey = None
    _NaclPublicKey = None
    _nacl_random = None
    _NACL_NONCE_SIZE = 24
    NACL_SUPPORT = False

from ..common import NotifyType, PersistentStoreMode
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_email, is_phone_no, parse_list, validate_regex
from .base import NotifyBase


class ThreemaMode:
    """Tracks the mode of operation for the Threema plugin."""

    # Basic mode: server-side encryption, no private key required
    BASIC = "basic"

    # End-to-end mode: client-side NaCl encryption, private key required
    E2E = "e2e"


THREEMA_MODES = (
    ThreemaMode.BASIC,
    ThreemaMode.E2E,
)

# E2E encrypted-message endpoint
THREEMA_E2E_URL = "https://msgapi.threema.ch/send_e2e"

# Public key lookup endpoint; format with the recipient Threema ID
THREEMA_PUBKEY_URL = "https://msgapi.threema.ch/pubkeys/{}"

# Threema-specific HTTP status messages
THREEMA_HTTP_ERROR_MAP = {
    402: "Insufficient credits.",
    404: "Recipient not found.",
    413: "Message too large.",
    429: "Rate limited; try again later.",
}


class ThreemaRecipientTypes:
    """The supported recipient specifiers."""

    THREEMA_ID = "to"
    PHONE = "phone"
    EMAIL = "email"


class NotifyThreema(NotifyBase):
    """A wrapper for Threema Gateway Notifications."""

    requirements = {
        # PyNaCl is only needed for E2E encrypted mode; basic mode
        # works without it.
        "packages_recommended": "PyNaCl",
    }

    # Enable persistent storage so that fetched public keys survive
    # across plugin instances and process restarts
    storage_mode = PersistentStoreMode.AUTO

    # Cache fetched public keys for 30 days; Threema keys are stable
    # but may be rotated, so an expiry prevents stale key use.
    pubkey_cache_expiry_sec = 60 * 60 * 24 * 30

    # The default descriptive name associated with the Notification
    service_name = "Threema Gateway"

    # The services URL
    service_url = "https://gateway.threema.ch/"

    # The default protocol
    secure_protocol = "threema"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/threema/"

    # Basic (send_simple) endpoint
    notify_url = "https://msgapi.threema.ch/send_simple"

    # The maximum length of the body
    body_maxlen = 3500

    # No title support
    title_maxlen = 0

    # Define object templates
    templates = ("{schema}://{gateway_id}@{secret}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "gateway_id": {
                "name": _("Gateway ID"),
                "type": "string",
                "private": True,
                "required": True,
                "map_to": "user",
            },
            "secret": {
                "name": _("API Secret"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "target_email": {
                "name": _("Target Email"),
                "type": "string",
                "map_to": "targets",
            },
            "target_threema_id": {
                "name": _("Target Threema ID"),
                "type": "string",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "from": {
                "alias_of": "gateway_id",
            },
            "gwid": {
                "alias_of": "gateway_id",
            },
            "secret": {
                "alias_of": "secret",
            },
            "to": {
                "alias_of": "targets",
            },
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": THREEMA_MODES,
            },
            "privkey": {
                "name": _("Private Key"),
                "type": "string",
                "private": True,
            },
        },
    )

    def __init__(
        self,
        secret=None,
        targets=None,
        mode=None,
        privkey=None,
        **kwargs,
    ):
        """Initialize Threema Gateway Object."""
        super().__init__(**kwargs)

        # Validate our params here.

        if not self.user:
            msg = "Threema Gateway ID must be specified"
            self.logger.warning(msg)
            raise TypeError(msg)

        # Verify our Gateway ID
        if len(self.user) != 8:
            msg = "Threema Gateway ID must be 8 characters in length"
            self.logger.warning(msg)
            raise TypeError(msg)

        # Verify our secret
        self.secret = validate_regex(secret)
        if not self.secret:
            msg = f"An invalid Threema API Secret ({secret}) was specified"
            self.logger.warning(msg)
            raise TypeError(msg)

        # Resolve operating mode
        if mode:
            self.mode = next(
                (m for m in THREEMA_MODES if m.startswith(mode.lower())),
                None,
            )
            if self.mode not in THREEMA_MODES:
                msg = f"The Threema mode specified ({mode}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)

        elif privkey:
            # Auto-detect E2E when a private key is supplied
            self.mode = ThreemaMode.E2E

        else:
            self.mode = ThreemaMode.BASIC

        # E2E-specific validation
        self._privkey = None
        if self.mode == ThreemaMode.E2E:
            self._privkey = self._parse_privkey(privkey)
            if not self._privkey:
                msg = (
                    "Threema E2E mode requires a valid"
                    " 32-byte Curve25519 private key"
                    f" ({privkey!r})"
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        # Parse our targets
        self.targets = []

        # Used for URL generation afterwards only
        self.invalid_targets = []

        for target in parse_list(targets, allow_whitespace=False):
            if len(target) == 8:
                # Store our user
                self.targets.append((ThreemaRecipientTypes.THREEMA_ID, target))
                continue

            # Check if an email was defined
            result = is_email(target)
            if result:
                # Store our user
                self.targets.append(
                    (
                        ThreemaRecipientTypes.EMAIL,
                        result["full_email"],
                    )
                )
                continue

            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if result:
                # store valid phone number
                self.targets.append(
                    (ThreemaRecipientTypes.PHONE, result["full"])
                )
                continue

            self.logger.warning(
                f"Dropped invalid user/email/phone ({target}) specified",
            )
            self.invalid_targets.append(target)

        return

    @staticmethod
    def _parse_privkey(key):
        """Parse and validate a Curve25519 private key string.

        Accepts 'private:64hexchars' (Threema SDK format) or a raw
        64-character hex string. Returns the hex string (lower-cased)
        on success, or None on failure.
        """
        if not isinstance(key, str):
            return None
        if key.startswith("private:"):
            key = key[8:]
        if len(key) != 64:
            return None
        try:
            bytes.fromhex(key)
        except ValueError:
            return None
        return key.lower()

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Threema Gateway Notification."""
        if self.mode == ThreemaMode.E2E:
            return self._send_e2e(body)
        return self._send_basic(body)

    def _send_basic(self, body):
        """Send via the basic (send_simple) endpoint."""
        if not self.targets:
            # There were no services to notify
            self.logger.warning(
                "There were no Threema Gateway targets to notify"
            )
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": (
                "application/x-www-form-urlencoded; charset=utf-8"
            ),
            "Accept": "*/*",
        }

        # Prepare our payload
        payload_ = {
            "secret": self.secret,
            "from": self.user,
            "text": body.encode("utf-8"),
        }

        # Create a copy of the targets list
        targets = list(self.targets)

        while targets:
            # Get our target to notify
            key, target = targets.pop(0)

            # Prepare a payload object
            payload = payload_.copy()

            # Set Target
            payload[key] = target

            # Some Debug Logging
            self.logger.debug(
                "Threema Gateway POST URL:"
                f" {self.notify_url}"
                f" (cert_verify={self.verify_certificate})"
            )
            self.logger.debug(f"Threema Gateway Payload: {payload}")

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    params=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyThreema.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send Threema Gateway notification to {}: "
                        "{}{}error={}".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                # We were successful
                self.logger.info(
                    f"Sent Threema Gateway notification to {target}"
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Threema"
                    f" Gateway:{target} notification"
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def _send_e2e(self, body):
        """Send end-to-end encrypted messages via /send_e2e.

        Only Threema ID targets are supported in E2E mode.
        Phone and email targets are skipped with a warning.
        """
        if not NACL_SUPPORT:
            self.logger.warning(
                "Threema E2E mode requires PyNaCl;"
                " install with: pip install PyNaCl"
            )
            return False

        e2e_targets = [
            (k, v)
            for k, v in self.targets
            if k == ThreemaRecipientTypes.THREEMA_ID
        ]

        skipped = len(self.targets) - len(e2e_targets)
        if skipped:
            self.logger.warning(
                "Threema E2E mode only supports Threema ID"
                " targets; skipping %d phone/email target(s)",
                skipped,
            )

        if not e2e_targets:
            self.logger.warning("No Threema ID targets for E2E mode; aborting")
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": (
                "application/x-www-form-urlencoded; charset=utf-8"
            ),
            "Accept": "*/*",
        }

        private_key = _NaclPrivateKey(bytes.fromhex(self._privkey))

        for _rtype, threema_id in e2e_targets:
            pubkey_bytes = self._fetch_pubkey(threema_id, headers)
            if pubkey_bytes is None:
                has_error = True
                continue

            try:
                nonce, ciphertext = self._encrypt_message(
                    body, private_key, pubkey_bytes
                )
            except Exception as exc:
                self.logger.warning(
                    f"Failed to encrypt Threema E2E message for {threema_id}"
                )
                self.logger.debug(f"Encryption error: {exc!s}")
                has_error = True
                continue

            payload = {
                "secret": self.secret,
                "from": self.user,
                "to": threema_id,
                "nonce": nonce.hex(),
                "box": ciphertext.hex(),
            }

            self.logger.debug(
                "Threema E2E POST URL:"
                f" {THREEMA_E2E_URL}"
                f" (cert_verify={self.verify_certificate})"
            )
            self.logger.debug(
                "Threema E2E from=%s to=%s nonce=%s",
                payload["from"],
                threema_id,
                payload["nonce"],
            )

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    THREEMA_E2E_URL,
                    params=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyThreema.http_response_code_lookup(
                        r.status_code,
                        THREEMA_HTTP_ERROR_MAP,
                    )

                    self.logger.warning(
                        "Failed to send Threema E2E notification"
                        " to {}: {}{}error={}".format(
                            threema_id,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )

                    # Mark our failure
                    has_error = True
                    continue

                # We were successful
                self.logger.info(
                    f"Sent Threema E2E notification to {threema_id}"
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending"
                    f" Threema E2E:{threema_id} notification"
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def _fetch_pubkey(self, threema_id, headers):
        """Fetch and cache the public key for a Threema ID.

        Returns the raw 32-byte public key on success, or None on
        failure. Keys are cached in persistent storage to avoid
        repeated API calls across sends and restarts.
        """
        store_key = f"pubkey_{threema_id}"
        cached = self.store.get(store_key)
        if cached is not None:
            return cached

        url = THREEMA_PUBKEY_URL.format(threema_id)
        params = {"secret": self.secret, "from": self.user}

        self.logger.debug("Fetching Threema public key for %s", threema_id)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.get(
                url,
                params=params,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

        except requests.RequestException as exc:
            self.logger.warning(
                "Connection error fetching public key for Threema ID %s",
                threema_id,
            )
            self.logger.debug(f"Socket Exception: {exc!s}")
            return None

        if r.status_code != requests.codes.ok:
            self.logger.warning(
                "Failed to fetch public key for Threema ID %s: error=%d",
                threema_id,
                r.status_code,
            )
            return None

        pubkey_hex = r.text.strip()
        if len(pubkey_hex) != 64:
            self.logger.warning(
                "Invalid public key length for Threema"
                " ID %s (got %d hex chars, expected 64)",
                threema_id,
                len(pubkey_hex),
            )
            return None

        try:
            pubkey_bytes = bytes.fromhex(pubkey_hex)
        except ValueError:
            self.logger.warning(
                "Non-hex public key received for Threema ID %s",
                threema_id,
            )
            return None

        self.store.set(
            store_key,
            pubkey_bytes,
            expires=self.pubkey_cache_expiry_sec,
        )
        return pubkey_bytes

    def _encrypt_message(self, text, private_key, pubkey_bytes):
        """Encrypt a text message using a NaCl Box.

        Builds the Threema message container (type byte 0x01 + UTF-8
        text + PKCS#7 padding) then encrypts it using Curve25519 +
        XSalsa20-Poly1305 (NaCl crypto_box).

        Returns (nonce_bytes, ciphertext_bytes).
        """
        public_key = _NaclPublicKey(pubkey_bytes)
        box = _NaclBox(private_key, public_key)

        # Message container: type byte (0x01 = text message) + UTF-8 body
        plaintext = b"\x01" + text.encode("utf-8")

        # PKCS#7 padding: minimum 1 byte, minimum total 32 bytes
        min_pad = max(1, 32 - len(plaintext))
        max_extra = 255 - min_pad
        extra = int.from_bytes(os.urandom(1), "big") % (max_extra + 1)
        pad_len = min_pad + extra
        plaintext += bytes([pad_len] * pad_len)

        nonce = _nacl_random(_NACL_NONCE_SIZE)
        encrypted = box.encrypt(plaintext, nonce)

        return encrypted.nonce, encrypted.ciphertext

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.user, self.secret)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.mode == ThreemaMode.E2E:
            params["mode"] = ThreemaMode.E2E
            params["privkey"] = (
                self.pprint(
                    self._privkey,
                    privacy=privacy,
                    # Parmameters are quoted anyway; avoid double quote
                    quote=False,
                    safe="*",
                )
                if privacy
                else f"private:{self._privkey}"
            )

        schemaStr = "{schema}://{gatewayid}@{secret}/{targets}?{params}"
        return schemaStr.format(
            schema=self.secure_protocol,
            gatewayid=NotifyThreema.quote(self.user),
            secret=self.pprint(
                self.secret, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            targets="/".join(
                chain(
                    [
                        NotifyThreema.quote(x[1], safe="@+")
                        for x in self.targets
                    ],
                    [
                        NotifyThreema.quote(x, safe="@+")
                        for x in self.invalid_targets
                    ],
                )
            ),
            params=NotifyThreema.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        targets = len(self.targets)
        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        results["targets"] = []

        if "secret" in results["qsd"] and len(results["qsd"]["secret"]):
            results["secret"] = NotifyThreema.unquote(results["qsd"]["secret"])

        else:
            results["secret"] = NotifyThreema.unquote(results["host"])

        results["targets"] += NotifyThreema.split_path(results["fullpath"])

        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["user"] = NotifyThreema.unquote(results["qsd"]["from"])

        elif "gwid" in results["qsd"] and len(results["qsd"]["gwid"]):
            results["user"] = NotifyThreema.unquote(results["qsd"]["gwid"])

        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyThreema.parse_list(
                results["qsd"]["to"], allow_whitespace=False
            )

        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyThreema.unquote(results["qsd"]["mode"])

        if "privkey" in results["qsd"] and results["qsd"]["privkey"]:
            results["privkey"] = NotifyThreema.unquote(
                results["qsd"]["privkey"]
            )

        return results

    @staticmethod
    def runtime_deps():
        """Return a tuple of top-level Python package names that this
        plugin imported as optional runtime dependencies.
        """
        return ("nacl",)
