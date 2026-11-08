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

# PushWard (https://pushward.app) is a hosted push notification service.
#
# To use this plugin you need an integration key from the PushWard app. The
# key always begins with the prefix "hlk_".
#
# Your Apprise URL would be assembled as:
#   pushward://{integration_key}
#
# For example:
#   pushward://hlk_xxxxxxxxxxxx
#
# The level may be set explicitly, otherwise it is derived from the Apprise
# notification type:
#   pushward://hlk_xxxxxxxxxxxx?level=critical&volume=0.8
#
# The title, subtitle, body and url can be end-to-end encrypted with a key of
# 64 hexadecimal characters that the PushWard app holds as well. This needs
# the cryptography package:
#   pushward://hlk_xxxxxxxxxxxx?key=0123456789abcdef...
#
# References:
# - https://pushward.app/docs/api

from __future__ import annotations

from json import dumps
from os import urandom
import re
from typing import Any, Optional, Union

import requests

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF

    PUSHWARD_E2EE_SUPPORT = True

except ImportError:
    PUSHWARD_E2EE_SUPPORT = False

from ..common import NotifyImageSize, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.base64 import base64_urlencode
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
PUSHWARD_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Integration Key.",
    403: "Forbidden - The Integration Key lacks permission.",
    422: "Unprocessable - The notification payload was rejected.",
    429: "Too many requests; rate-limit exceeded.",
}

# The PushWard notification levels (interruption levels)
PUSHWARD_LEVELS = (
    "passive",
    "active",
    "time-sensitive",
    "critical",
)

# The default PushWard level mapped to each Apprise notification type. Each is
# overridable from the URL (e.g. ?info=passive&failure=critical) so the mapping
# can match a user's own PushWard setup. "critical" is never a default; it must
# be opted into as it bypasses the device's silent mode / Focus.
PUSHWARD_DEFAULT_LEVELS = {
    NotifyType.INFO: "active",
    NotifyType.SUCCESS: "active",
    NotifyType.WARNING: "time-sensitive",
    NotifyType.FAILURE: "time-sensitive",
}

# An encryption key is 32 bytes written as 64 hexadecimal characters
VALIDATE_ENCRYPTION_KEY = re.compile(r"^[0-9a-f]{64}$")

# The longest pw1 envelope the server accepts
PUSHWARD_ENVELOPE_MAXLEN = 3072

# The most plaintext one envelope can hold: the "pw1.<kid>." prefix takes 13
# characters, and the nonce and tag 28 of the bytes that are base64 encoded
PUSHWARD_PLAINTEXT_MAXLEN = (PUSHWARD_ENVELOPE_MAXLEN - 13) * 3 // 4 - 28


def pushward_level(value):
    """Resolve a full or short-form level (e.g. 'crit', 'c') to a canonical
    PushWard level, or None if it does not match one."""
    value = str(value).strip().lower()
    if not value:
        return None
    return next(
        (level for level in PUSHWARD_LEVELS if level.startswith(value)),
        None,
    )


def pushward_hkdf(key: bytes, info: bytes, length: int) -> bytes:
    """Derive pw1 key material with HKDF-SHA256 and an empty salt."""
    return HKDF(
        algorithm=hashes.SHA256(), length=length, salt=None, info=info
    ).derive(key)


class NotifyPushWard(NotifyBase):
    """A wrapper for PushWard Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "PushWard"

    # Only needed for encryption; plaintext notifications work without it
    requirements = {
        "packages_recommended": "cryptography",
    }

    # The services URL
    service_url = "https://pushward.app/"

    # The default secure protocol
    secure_protocol = "pushward"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/pushward/"

    # PushWard notification endpoint (used in send())
    notify_url = "https://api.pushward.app/notifications"

    # Allow an image to be referenced as the notification icon
    image_size = NotifyImageSize.XY_128

    # Defines the maximum allowable characters in the title
    title_maxlen = 256

    # Body limit
    body_maxlen = 3000

    # PushWard supports media attachments by URL only (not file uploads), so
    # Apprise file attachments are not wired in at this time
    attachment_support = False

    # Define object URL templates
    templates = ("{schema}://{apikey}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("Integration Key"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^hlk_[A-Za-z0-9]+$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "apikey": {
                "alias_of": "apikey",
            },
            # Force the level for every notification regardless of its type
            "level": {
                "name": _("Level"),
                "type": "choice:string",
                "values": PUSHWARD_LEVELS,
            },
            # Per-type level overrides; default to PUSHWARD_DEFAULT_LEVELS
            "info": {
                "name": _("Info Level"),
                "type": "choice:string",
                "values": PUSHWARD_LEVELS,
                "default": PUSHWARD_DEFAULT_LEVELS[NotifyType.INFO],
            },
            "success": {
                "name": _("Success Level"),
                "type": "choice:string",
                "values": PUSHWARD_LEVELS,
                "default": PUSHWARD_DEFAULT_LEVELS[NotifyType.SUCCESS],
            },
            "warning": {
                "name": _("Warning Level"),
                "type": "choice:string",
                "values": PUSHWARD_LEVELS,
                "default": PUSHWARD_DEFAULT_LEVELS[NotifyType.WARNING],
            },
            "failure": {
                "name": _("Failure Level"),
                "type": "choice:string",
                "values": PUSHWARD_LEVELS,
                "default": PUSHWARD_DEFAULT_LEVELS[NotifyType.FAILURE],
            },
            "volume": {
                "name": _("Volume"),
                "type": "float",
                "min": 0.0,
                "max": 1.0,
            },
            "ack": {
                "name": _("Acknowledge"),
                "type": "bool",
                "default": False,
            },
            # Seconds between repeats, only sent with ack
            "repeat": {
                "name": _("Repeat Interval"),
                "type": "int",
                "min": 30,
                "max": 3600,
                "default": 60,
            },
            # Seconds before repeating gives up, only sent with ack
            "expire": {
                "name": _("Expire"),
                "type": "int",
                "min": 60,
                "max": 10800,
                "default": 3600,
            },
            "url": {
                "name": _("URL"),
                "type": "string",
                "map_to": "supplemental_url",
            },
            "subtitle": {
                "name": _("Subtitle"),
                "type": "string",
            },
            "thread": {
                "name": _("Thread ID"),
                "type": "string",
                "map_to": "thread_id",
            },
            "collapse": {
                "name": _("Collapse ID"),
                "type": "string",
                "map_to": "collapse_id",
            },
            # Up to 3 snooze durations, in minutes
            "snooze": {
                "name": _("Snooze"),
                "type": "list:int",
            },
            # Seals the title, subtitle, body and url when set
            "key": {
                "name": _("Encryption Key"),
                "type": "string",
                "private": True,
                "map_to": "encryption_key",
            },
            # On whenever a key is present; no sends plaintext despite the key
            "e2ee": {
                "name": _("E2EE"),
                "type": "bool",
                "default": True,
            },
        },
    )

    def __init__(
        self,
        apikey: str,
        level: Optional[str] = None,
        info: Optional[str] = None,
        success: Optional[str] = None,
        warning: Optional[str] = None,
        failure: Optional[str] = None,
        volume: Optional[Union[float, str]] = None,
        ack: Optional[Union[bool, str]] = None,
        repeat: Optional[Union[int, str]] = None,
        expire: Optional[Union[int, str]] = None,
        supplemental_url: Optional[str] = None,
        subtitle: Optional[str] = None,
        thread_id: Optional[str] = None,
        collapse_id: Optional[str] = None,
        snooze: Optional[Union[list[int], str]] = None,
        encryption_key: Optional[str] = None,
        e2ee: Optional[Union[bool, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize PushWard Object."""
        super().__init__(**kwargs)

        # Validate the Integration Key (begins with the hlk_ prefix)
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = (
                "An invalid PushWard Integration Key "
                f"({apikey}) was specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # An explicit level forces every notification to that level
        self.level = None
        if level:
            self.level = pushward_level(level)
            if self.level is None:
                msg = f"An invalid PushWard level ({level}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Per-notification-type level mapping; each type may be overridden from
        # the URL, otherwise it falls back to the default
        self.level_map = {}
        for ntype, value in (
            (NotifyType.INFO, info),
            (NotifyType.SUCCESS, success),
            (NotifyType.WARNING, warning),
            (NotifyType.FAILURE, failure),
        ):
            if not value:
                self.level_map[ntype] = PUSHWARD_DEFAULT_LEVELS[ntype]
                continue

            resolved = pushward_level(value)
            if resolved is None:
                msg = f"An invalid PushWard level ({value}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)
            self.level_map[ntype] = resolved

        # Acquire our volume (only applied to critical notifications)
        if volume is not None:
            try:
                self.volume = float(volume)

            except (ValueError, TypeError):
                msg = f"An invalid PushWard volume ({volume}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg) from None

            if self.volume < 0.0 or self.volume > 1.0:
                msg = f"An invalid PushWard volume ({volume}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)
        else:
            self.volume = None

        # Require the notification to be acknowledged
        self.ack = (
            self.template_args["ack"]["default"]
            if ack is None
            else parse_bool(ack)
        )

        # Acquire our repeat interval.  Going through str() makes a float
        # fail instead of being silently truncated by int().
        self.repeat = self.template_args["repeat"]["default"]
        if repeat is not None:
            try:
                self.repeat = int(str(repeat))

            except (ValueError, TypeError):
                msg = f"An invalid PushWard repeat ({repeat}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg) from None

            if self.repeat < 30 or self.repeat > 3600:
                msg = f"An invalid PushWard repeat ({repeat}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Acquire our expiry
        self.expire = self.template_args["expire"]["default"]
        if expire is not None:
            try:
                self.expire = int(str(expire))

            except (ValueError, TypeError):
                msg = f"An invalid PushWard expire ({expire}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg) from None

            if self.expire < 60 or self.expire > 10800:
                msg = f"An invalid PushWard expire ({expire}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The URL opened from the notification
        self.supplemental_url = (
            str(supplemental_url) if supplemental_url else None
        )
        if self.supplemental_url and len(self.supplemental_url) > 2048:
            msg = "A PushWard url cannot exceed 2048 characters."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The line shown under the title
        self.subtitle = str(subtitle) if subtitle else None
        if self.subtitle and len(self.subtitle) > 256:
            msg = "A PushWard subtitle cannot exceed 256 characters."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Notifications sharing a thread are grouped together
        self.thread_id = str(thread_id) if thread_id else None
        if self.thread_id and len(self.thread_id) > 128:
            msg = "A PushWard thread cannot exceed 128 characters."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # A later notification with the same collapse id replaces this one
        self.collapse_id = str(collapse_id) if collapse_id else None
        if self.collapse_id and len(self.collapse_id) > 64:
            msg = "A PushWard collapse cannot exceed 64 characters."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Acquire our snooze durations.  Order is kept and duplicates are
        # refused.
        self.snooze = None
        if snooze is not None:
            values = (
                snooze
                if isinstance(snooze, (list, tuple))
                else parse_list(str(snooze), sort=False)
            )
            try:
                self.snooze = [int(str(value)) for value in values]

            except (ValueError, TypeError):
                msg = f"An invalid PushWard snooze ({snooze}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg) from None

            if (
                not 1 <= len(self.snooze) <= 3
                or len(set(self.snooze)) != len(self.snooze)
                or not all(1 <= value <= 1440 for value in self.snooze)
            ):
                msg = f"An invalid PushWard snooze ({snooze}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The server refuses snooze together with acknowledge
        if self.ack and self.snooze:
            msg = "A PushWard notification cannot combine ack with snooze."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Acquire our encryption key; whitespace and case do not matter. A
        # blank key is refused, as reading it as no key would send plaintext
        self.encryption_key = None
        if encryption_key is not None:
            key = "".join(str(encryption_key).split()).lower()
            if not VALIDATE_ENCRYPTION_KEY.match(key):
                msg = "An invalid PushWard encryption key was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.encryption_key = key

        # A value parse_bool() cannot read leaves encryption on
        default = self.template_args["e2ee"]["default"]
        self.e2ee = default if e2ee is None else parse_bool(e2ee, default)

        # An explicit request for encryption must not send plaintext
        if e2ee is not None and self.e2ee and not self.encryption_key:
            msg = "PushWard e2ee requires an encryption key."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Fail closed; never fall back to sending plaintext when the
        # caller asked for encryption but the library isn't available
        if self.encryption_key and self.e2ee and not PUSHWARD_E2EE_SUPPORT:
            msg = (
                "PushWard encryption requires the 'cryptography' package. "
                "Install Apprise with the 'all-plugins' extra."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform PushWard Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.apikey}",
        }

        # Resolve the level: an explicit override wins, otherwise the
        # per-notification-type mapping applies
        level = self.level if self.level else self.level_map[notify_type]

        # PushWard requires a non-empty title; the body is guaranteed by the
        # framework, but the title can be empty so we fall back to our
        # application descriptor
        title = title if title else self.app_desc
        if not title:
            title = self.app_id

        # Prepare our payload
        payload = {
            "title": title,
            "body": body,
            "level": level,
            "source": "apprise",
            "source_display_name": self.app_id,
        }

        # Reference an icon if one is available
        image_url = self.image_url(notify_type)
        if image_url:
            payload["icon_url"] = image_url

        # Volume is only applied to critical notifications
        if level == "critical" and self.volume is not None:
            payload["volume"] = self.volume

        # The server refuses acknowledge at the passive level
        if self.ack and level != "passive":
            payload["acknowledge"] = {
                "repeat_seconds": self.repeat,
                "expire_seconds": self.expire,
            }

        # Include our optional fields when they were set
        if self.supplemental_url:
            payload["url"] = self.supplemental_url

        if self.subtitle:
            payload["subtitle"] = self.subtitle

        if self.thread_id:
            payload["thread_id"] = self.thread_id

        if self.collapse_id:
            payload["collapse_id"] = self.collapse_id

        if self.snooze:
            payload["snooze"] = self.snooze

        # Everything else stays readable; the server needs it to deliver
        encrypt = bool(self.encryption_key and self.e2ee)
        if encrypt:
            try:
                envelope = self._encrypt_payload(payload)

            except Exception as e:
                # Fail closed; never fall back to sending plaintext
                self.logger.warning("Failed to encrypt PushWard notification.")
                self.logger.debug(
                    "PushWard encryption failed with %s.", type(e).__name__
                )
                return False

            # The server cannot shorten what it cannot read
            if len(envelope) > PUSHWARD_ENVELOPE_MAXLEN:
                self.logger.warning(
                    "The PushWard notification is too long to encrypt."
                )
                return False

            payload["encrypted"] = envelope

        self.logger.debug(
            "PushWard POST URL: %s (cert_verify=%s)",
            self.notify_url,
            self.verify_certificate,
        )
        if not encrypt:
            self.logger.debug("PushWard Payload: %s", str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
            ):
                # We had a problem
                status_str = NotifyPushWard.http_response_code_lookup(
                    r.status_code, PUSHWARD_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send PushWard notification: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                if not encrypt:
                    # The response may echo fragments of the request
                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                # Return; we're done
                return False

            else:
                self.logger.info("Sent PushWard notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred posting to PushWard."
            )
            if not encrypt:
                # The exception text may echo fragments of the request
                self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

    def _encrypt_payload(self, payload: dict[str, Any]) -> str:
        """Move the notification text out of payload into a pw1 envelope."""

        # The server refuses any of these beside an envelope; the app reads
        # them from the JSON in this order
        fields = {
            field: payload.pop(field)
            for field in ("title", "subtitle", "body", "url")
            if field in payload
        }

        # The app refuses to open these and the server can no longer tell
        if not (fields["title"] and fields["body"]):
            raise ValueError("A title and a body are required")

        plaintext = dumps(
            fields,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        # Padding to a multiple of 64 bytes hides the exact length, unless
        # that alone would push the envelope over its limit
        padded = plaintext + b" " * (-len(plaintext) % 64)
        if len(padded) <= PUSHWARD_PLAINTEXT_MAXLEN:
            plaintext = padded

        key = bytes.fromhex(self.encryption_key)
        kid = pushward_hkdf(key, b"pushward/e2e/v1/kid", 4).hex()
        cipher = AESGCM(pushward_hkdf(key, b"pushward/e2e/v1/enc", 32))

        # A fresh nonce for every send; the tag also covers the key id
        nonce = urandom(12)
        sealed = cipher.encrypt(nonce, plaintext, f"pw1.{kid}".encode("ascii"))

        return f"pw1.{kid}.{base64_urlencode(nonce + sealed)}"

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.apikey,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}
        if self.level:
            params["level"] = self.level

        # Include any per-type level that differs from the default
        for ntype, key in (
            (NotifyType.INFO, "info"),
            (NotifyType.SUCCESS, "success"),
            (NotifyType.WARNING, "warning"),
            (NotifyType.FAILURE, "failure"),
        ):
            if self.level_map[ntype] != PUSHWARD_DEFAULT_LEVELS[ntype]:
                params[key] = self.level_map[ntype]

        if self.volume is not None:
            params["volume"] = str(self.volume)

        # Only include acknowledge settings that differ from the default
        if self.ack:
            params["ack"] = "yes"

        if self.repeat != self.template_args["repeat"]["default"]:
            params["repeat"] = str(self.repeat)

        if self.expire != self.template_args["expire"]["default"]:
            params["expire"] = str(self.expire)

        # What is sealed from the server stays out of the logs as well
        masked = privacy and self.encryption_key and self.e2ee

        # Include our optional fields when they were set
        if self.supplemental_url:
            params["url"] = self.pprint(
                self.supplemental_url,
                masked,
                mode=PrivacyMode.Secret,
                quote=False,
            )

        if self.subtitle:
            params["subtitle"] = self.pprint(
                self.subtitle, masked, mode=PrivacyMode.Secret, quote=False
            )

        if self.thread_id:
            params["thread"] = self.thread_id

        if self.collapse_id:
            params["collapse"] = self.collapse_id

        if self.snooze:
            params["snooze"] = ",".join(str(value) for value in self.snooze)

        if self.encryption_key:
            params["key"] = self.pprint(
                self.encryption_key,
                privacy,
                mode=PrivacyMode.Secret,
                safe="",
            )

        if not self.e2ee:
            params["e2ee"] = "no"

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            params=NotifyPushWard.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The Integration Key is in the host position (case is preserved
        # because verify_host=False skips hostname normalization)
        results["apikey"] = NotifyPushWard.unquote(results["host"])

        # Allow ?apikey= to override the host-supplied key
        if "apikey" in results["qsd"] and results["qsd"]["apikey"]:
            results["apikey"] = NotifyPushWard.unquote(
                results["qsd"]["apikey"]
            )

        # Allow the level to be set (forces every notification type)
        if "level" in results["qsd"] and results["qsd"]["level"]:
            results["level"] = NotifyPushWard.unquote(results["qsd"]["level"])

        # Allow per-notification-type level overrides
        for key in ("info", "success", "warning", "failure"):
            if key in results["qsd"] and results["qsd"][key]:
                results[key] = NotifyPushWard.unquote(results["qsd"][key])

        # Allow the volume to be set
        if "volume" in results["qsd"] and results["qsd"]["volume"]:
            results["volume"] = NotifyPushWard.unquote(
                results["qsd"]["volume"]
            )

        # Allow an acknowledgement to be required
        if "ack" in results["qsd"] and results["qsd"]["ack"]:
            results["ack"] = parse_bool(results["qsd"]["ack"])

        # Seconds between repeats of an acknowledge notification
        if "repeat" in results["qsd"] and results["qsd"]["repeat"]:
            results["repeat"] = NotifyPushWard.unquote(
                results["qsd"]["repeat"]
            )

        # Seconds before an acknowledge notification stops repeating
        if "expire" in results["qsd"] and results["qsd"]["expire"]:
            results["expire"] = NotifyPushWard.unquote(
                results["qsd"]["expire"]
            )

        # Stored as supplemental_url because results["url"] already holds
        # the Apprise URL.  The value is already decoded, so it is not
        # unquoted again, which would corrupt any escapes in the link.
        if "url" in results["qsd"] and results["qsd"]["url"]:
            results["supplemental_url"] = results["qsd"]["url"]

        # The line shown under the title
        if "subtitle" in results["qsd"] and results["qsd"]["subtitle"]:
            results["subtitle"] = NotifyPushWard.unquote(
                results["qsd"]["subtitle"]
            )

        # Group notifications together
        if "thread" in results["qsd"] and results["qsd"]["thread"]:
            results["thread_id"] = NotifyPushWard.unquote(
                results["qsd"]["thread"]
            )

        # Replace an earlier notification with the same collapse id
        if "collapse" in results["qsd"] and results["qsd"]["collapse"]:
            results["collapse_id"] = NotifyPushWard.unquote(
                results["qsd"]["collapse"]
            )

        # Snooze durations in minutes, as a comma separated list
        if "snooze" in results["qsd"] and results["qsd"]["snooze"]:
            results["snooze"] = NotifyPushWard.unquote(
                results["qsd"]["snooze"]
            )

        # A blank key= is passed on so that it is refused, not ignored
        if "key" in results["qsd"]:
            results["encryption_key"] = NotifyPushWard.unquote(
                results["qsd"]["key"]
            )

        if "e2ee" in results["qsd"] and results["qsd"]["e2ee"]:
            results["e2ee"] = NotifyPushWard.unquote(results["qsd"]["e2ee"])

        return results

    @staticmethod
    def runtime_deps():
        """Return optional runtime dependency package names."""
        return ("cryptography",)
