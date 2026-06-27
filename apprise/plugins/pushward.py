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
# References:
# - https://pushward.app/docs/api

from json import dumps

import requests

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
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


class NotifyPushWard(NotifyBase):
    """A wrapper for PushWard Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "PushWard"

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
        },
    )

    def __init__(
        self,
        apikey,
        level=None,
        info=None,
        success=None,
        warning=None,
        failure=None,
        volume=None,
        **kwargs,
    ):
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
            raise TypeError(msg)

        # An explicit level forces every notification to that level
        self.level = None
        if level:
            self.level = pushward_level(level)
            if self.level is None:
                msg = f"An invalid PushWard level ({level}) was specified."
                self.logger.warning(msg)
                raise TypeError(msg)

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
                raise TypeError(msg)
            self.level_map[ntype] = resolved

        # Acquire our volume (only applied to critical notifications)
        if volume is not None:
            try:
                self.volume = float(volume)

            except (ValueError, TypeError):
                msg = f"An invalid PushWard volume ({volume}) was specified."
                self.logger.warning(msg)
                raise TypeError(msg) from None

            if self.volume < 0.0 or self.volume > 1.0:
                msg = f"An invalid PushWard volume ({volume}) was specified."
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.volume = None

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
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
        }

        # Reference an icon if one is available
        image_url = self.image_url(notify_type)
        if image_url:
            payload["icon_url"] = image_url

        # Volume is only applied to critical notifications
        if level == "critical" and self.volume is not None:
            payload["volume"] = self.volume

        self.logger.debug(
            "PushWard POST URL: %s (cert_verify=%s)",
            self.notify_url,
            self.verify_certificate,
        )
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
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

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

    def url(self, privacy=False, *args, **kwargs):
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

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            params=NotifyPushWard.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
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

        return results
