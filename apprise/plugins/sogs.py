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

# Session Open Group Server (SOGS) Notifications
#
# SOGS is the reference implementation of a Session Community Server.
# It hosts publicly accessible open-group rooms for the Session messaging app.
# Resources:
#  - https://getsession.org/
#  - https://github.com/session-foundation/session-pysogs
#
# Setting up a bot account
# -------------------------
# 1. Generate a 32-byte Ed25519 seed and note its 64-character hex encoding.
#    In Python:
#        import os; print(os.urandom(32).hex())
#    Keep this value secret -- it is your bot's seed.
#
# 2. Find the SOGS public_key from any Session group join link.
#    The link looks like:
#        https://open.getsession.org/discussion?public_key=a03c383c...
#    The value after "public_key=" is the 64-hex-char public_key.
#
# 3. Find the room token -- the path segment of the join link above
#    ("discussion" in the example).
#
# Apprise URL format
# -------------------
# Secure (HTTPS):
#    sessions://{public_key}:{seed}@{host}/{room}
#    sessions://{public_key}:{seed}@{host}/{room1}/{room2}
#    sessions://{public_key}:{seed}@{host}:{port}/{room}
#
# Insecure (HTTP):
#    session://{public_key}:{seed}@{host}/{room}
#
# Query-string form (useful in config files):
#    sessions://{host}/{room}?key={public_key}&seed={seed}
#    sessions://{host}/{room}?public_key={public_key}&seed={seed}
#
# References:
#  - SOGS API: https://github.com/session-foundation/session-pysogs
#  - Session protocol: https://getsession.org/
#  - Auth spec: sogs/routes/auth.py in the session-pysogs repository

from base64 import b64encode
import hashlib
from json import dumps, loads
import os
import re
import time

import requests

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    # We're good to go!
    NOTIFY_SESSIONOGS_ENABLED = True

except ImportError:
    Ed25519PrivateKey = None
    Encoding = None
    PublicFormat = None
    NOTIFY_SESSIONOGS_ENABLED = False

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list
from .base import NotifyBase

# public_key: 64 hex characters (the SOGS server's Curve25519 public key).
# This is the value shown in Session group join links as ?public_key=...
IS_PUBLIC_KEY = re.compile(r"^[0-9a-f]{64}$", re.I)

# Room token: alphanumeric, hyphens, underscores (as used by pysogs).
IS_ROOM_TOKEN = re.compile(r"^[a-z0-9_-]{1,64}$", re.I)

# seed: 64 hex characters (32-byte Ed25519 seed that identifies the bot).
IS_SEED = re.compile(r"^[0-9a-f]{64}$", re.I)

# HTTP error map for SOGS responses.
SOGS_HTTP_ERROR_MAP = {
    400: "Bad Request -- malformed message data or headers.",
    401: "Unauthorized -- invalid or missing X-SOGS-* auth headers.",
    403: "Forbidden -- the bot does not have write permission in this room.",
    404: "Not Found -- the room token does not exist on this server.",
    425: "Too Early -- timestamp out of range or nonce already used.",
    429: "Too Many Requests -- rate limit exceeded.",
}


def _encode_varint(n):
    """Encode an integer as a protobuf-style base-128 varint."""
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _ld_field(field_num, data):
    """Encode a protobuf length-delimited field (wire type 2)."""
    tag = _encode_varint((field_num << 3) | 2)
    return tag + _encode_varint(len(data)) + data


def _build_session_message(text):
    """Encode text as a Session protocol Content protobuf message.

    Builds: Content { dataMessage { body: text } }
    and appends a minimal Session padding marker byte (0x80).
    """
    # DataMessage.body is field 1, wire type 2 (length-delimited).
    body_bytes = text.encode("utf-8")
    data_message = _ld_field(1, body_bytes)

    # Content.dataMessage is field 1, wire type 2.
    content = _ld_field(1, data_message)

    # Append the Session padding marker so the server can locate message
    # boundaries correctly.
    return content + b"\x80"


class NotifySessionOGS(NotifyBase):
    """A wrapper for Session Open Group Server (SOGS) Notifications."""

    # The default descriptive name associated with the Notification.
    service_name = "Session Open Group Server"

    # The services URL.
    service_url = "https://getsession.org/"

    # The default insecure protocol.
    protocol = "session"

    # The default secure protocol.
    secure_protocol = ("sessions", "sogs")

    # A URL that takes you to the setup/help of the specific protocol.
    setup_url = "https://appriseit.com/services/sogs/"

    # SOGS message endpoint; actual request URL is built in _post().
    notify_url = "{schema}://{host}/room/{room}/message"

    # Titles are not a native Session concept; prepend to body if provided.
    title_maxlen = 0

    # 2000-character soft limit (Session app displays long messages fine).
    body_maxlen = 2000

    # Set our global enabled flag.
    enabled = NOTIFY_SESSIONOGS_ENABLED

    # Require the cryptography library.
    requirements = {
        "packages_required": "cryptography",
    }

    # URL templates for this plugin.
    templates = (
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
    )

    # Template tokens.
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            # URL user field carries the 64-hex public_key (Curve25519 pubkey).
            "user": {
                "name": _("Public Key"),
                "type": "string",
                "required": True,
                "map_to": "public_key",
            },
            # URL password field carries the 64-hex Ed25519 seed.
            "password": {
                "name": _("Seed"),
                "type": "string",
                "private": True,
                "required": True,
                "map_to": "seed",
            },
            "targets": {
                "name": _("Rooms"),
                "type": "list:string",
            },
        },
    )

    # Template arguments.
    template_args = dict(
        NotifyBase.template_args,
        **{
            # key= is the short query-string alias for the server's Curve25519
            # public key (URL user field).
            "key": {
                "alias_of": "user",
            },
            # public_key= matches Session's own join-link terminology
            # (?public_key=... in Session group join links).
            "public_key": {
                "alias_of": "user",
            },
            # seed= is the query-string form of the bot's Ed25519 seed
            # (URL password field).
            "seed": {
                "alias_of": "password",
            },
            # to= is the project-wide convention for additional targets.
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(self, public_key, seed, targets=None, **kwargs):
        """Initialize Session Open Group Server Object."""
        super().__init__(**kwargs)

        # Raise a clear error when the cryptography library is absent so
        # callers get an explicit message rather than a confusing
        # AttributeError from None.from_private_bytes().
        if not NOTIFY_SESSIONOGS_ENABLED:
            msg = (
                "The cryptography library is required for SOGS "
                "notifications.  Install it with: pip install cryptography"
            )
            self.logger.warning(msg)
            raise ImportError(msg)

        # Validate the public key (64-char hex Curve25519 public key).
        _pk = (public_key or "").strip().lower()
        if not IS_PUBLIC_KEY.match(_pk):
            msg = (
                "The SOGS public_key must be exactly 64 hex "
                f"characters ({_pk!r} is invalid)."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store the validated public key.
        self.public_key = _pk

        # Validate the bot seed (64-char hex Ed25519 seed).
        _seed = (seed or "").strip().lower()
        if not IS_SEED.match(_seed):
            msg = (
                "The SOGS bot seed must be exactly 64 hex "
                f"characters ({_seed!r} is invalid)."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store the validated seed hex string.
        self.seed = _seed

        # Derive the Ed25519 signing key from the seed.
        self._signing_key = Ed25519PrivateKey.from_private_bytes(
            bytes.fromhex(self.seed)
        )

        # Derive the 32-byte Ed25519 public key for auth headers.
        self._bot_pubkey_bytes = self._signing_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )

        # Parse and validate the room token list.
        self.rooms = []
        self.invalid_rooms = []
        for token in parse_list(targets):
            token = token.strip().lower()
            if IS_ROOM_TOKEN.match(token):
                self.rooms.append(token)
            else:
                self.logger.warning(
                    "SOGS ignoring invalid room token %r.", token
                )
                self.invalid_rooms.append(token)

        # At least one valid room is required to send a notification.
        if not self.rooms:
            msg = "At least one valid SOGS room token must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

    def _sogs_auth_headers(self, method, path, body_bytes=None):
        """
        Build the four X-SOGS-* authentication headers for a request.

        The signature covers:
            SERVER_KEY || NONCE || TIMESTAMP || METHOD || PATH [|| HBODY]
        where HBODY is the 64-byte blake2b hash of the request body when
        the body is non-empty.  The signing key is the bot's Ed25519 key.
        """
        # Generate a fresh 16-byte random nonce for each request.
        nonce = os.urandom(16)

        # Unix timestamp as a decimal string.
        ts_str = str(int(time.time()))

        # Concatenate the fields to sign.
        to_sign = (
            bytes.fromhex(self.public_key)
            + nonce
            + ts_str.encode()
            + method.upper().encode()
            + path.encode()
        )

        # Append the 64-byte blake2b hash of the body when a body is present.
        if body_bytes:
            to_sign += hashlib.blake2b(body_bytes, digest_size=64).digest()

        # Sign with the bot's Ed25519 key.
        sig = self._signing_key.sign(to_sign)

        # Assemble headers.  The Pubkey header is "00" (unblinded prefix)
        # followed by the 32-byte Ed25519 pubkey as hex.
        return {
            "X-SOGS-Pubkey": "00" + self._bot_pubkey_bytes.hex(),
            "X-SOGS-Nonce": b64encode(nonce).decode(),
            "X-SOGS-Timestamp": ts_str,
            "X-SOGS-Signature": b64encode(sig).decode(),
        }

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Session Open Group Server Notification."""

        # Encode as a Session protocol protobuf message with padding.
        # title_maxlen=0 ensures the framework already prepended any title.
        msg_data = _build_session_message(body)

        # Sign the padded message bytes with the bot's Ed25519 key.
        msg_sig = self._signing_key.sign(msg_data)

        # JSON payload for POST /room/{room}/message.
        payload = {
            "data": b64encode(msg_data).decode(),
            "signature": b64encode(msg_sig).decode(),
        }

        # Serialize the payload to bytes for body hashing.
        body_bytes = dumps(payload).encode()

        # Send to each configured room in turn.
        has_error = False
        for room in self.rooms:
            if not self._post(room, body_bytes):
                has_error = True

        return not has_error

    def _post(self, room, body_bytes):
        """POST a notification to a single SOGS room."""

        # Build the request path.
        path = f"/room/{room}/message"

        # Derive the base URL from the secure flag and host/port.
        # Only include the port when it differs from the protocol default.
        schema = "https" if self.secure else "http"
        default_port = 443 if self.secure else 80
        host_str = (
            f"{self.host}:{self.port}"
            if self.port and self.port != default_port
            else self.host
        )
        url = f"{schema}://{host_str}{path}"

        # Build the X-SOGS-* authentication headers.
        auth_headers = self._sogs_auth_headers("POST", path, body_bytes)

        # Merge with the content-type header.
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }
        headers.update(auth_headers)

        self.logger.debug(
            "SOGS POST URL: %s (cert_verify=%r)", url, self.verify_certificate
        )
        self.logger.debug("SOGS Room: %s", room)

        # Throttle before every network request.
        self.throttle()

        try:
            r = requests.post(
                url,
                data=body_bytes,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            # Parse response body defensively.
            try:
                content = loads(r.content)
            except (AttributeError, TypeError, ValueError):
                content = {}

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
            ):
                # Log any known status description.
                status_str = NotifySessionOGS.http_response_code_lookup(
                    r.status_code, SOGS_HTTP_ERROR_MAP
                )
                self.logger.warning(
                    "Failed to post to SOGS room %r: %s%serror=%s.",
                    room,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug("Response Details:\r\n%s", r.content)
                return False

            self.logger.info("Sent SOGS notification to room %r.", room)
            self.logger.debug("SOGS response: %s", content)

        except requests.RequestException as e:
            self.logger.warning(
                "A connection error occurred posting to SOGS room %r.",
                room,
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol[0] if self.secure else self.protocol,
            self.public_key,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Collect standard URL parameters.
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Determine the schema and default port.
        schema = self.secure_protocol[0] if self.secure else self.protocol
        default_port = 443 if self.secure else 80

        # public_key goes in the URL user field; seed in the password field
        # (masked to {first}...{last} when privacy=True).
        return "{schema}://{public_key}:{seed}@{host}{port}/{rooms}?{params}".format(
            schema=schema,
            public_key=NotifySessionOGS.quote(self.public_key, safe=""),
            seed=self.pprint(self.seed, privacy, safe=""),
            host=self.host,
            port=(
                ""
                if not self.port or self.port == default_port
                else f":{self.port}"
            ),
            rooms="/".join(
                [NotifySessionOGS.quote(r, safe="") for r in self.rooms]
                + [
                    NotifySessionOGS.quote(r, safe="")
                    for r in self.invalid_rooms
                ]
            ),
            params=NotifySessionOGS.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object.
        """
        results = NotifyBase.parse_url(url)
        if not results:
            return results

        # The URL user field carries the public_key (Curve25519 public key).
        results["public_key"] = (
            NotifySessionOGS.unquote(results["user"])
            if results.get("user")
            else None
        )

        # The URL password field carries the bot's Ed25519 seed.
        results["seed"] = (
            NotifySessionOGS.unquote(results["password"])
            if results.get("password")
            else None
        )

        # ?key= is the short query-string alias for the public_key.
        if "key" in results["qsd"] and results["qsd"]["key"]:
            results["public_key"] = NotifySessionOGS.unquote(
                results["qsd"]["key"]
            )

        # ?public_key= matches Session's own join-link terminology and
        # overrides ?key= when both are present.
        if "public_key" in results["qsd"] and results["qsd"]["public_key"]:
            results["public_key"] = NotifySessionOGS.unquote(
                results["qsd"]["public_key"]
            )

        # ?seed= query param overrides the URL password field.
        if "seed" in results["qsd"] and results["qsd"]["seed"]:
            results["seed"] = NotifySessionOGS.unquote(results["qsd"]["seed"])

        # All path segments are room tokens.
        results["targets"] = NotifySessionOGS.split_path(results["fullpath"])

        # ?to= is the project-wide alias for additional room tokens.
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifySessionOGS.parse_list(
                results["qsd"]["to"]
            )

        return results

    @staticmethod
    def runtime_deps():
        """
        Return a tuple of top-level Python package names that this
        plugin imported as optional runtime dependencies.
        """
        return ("cryptography",)
