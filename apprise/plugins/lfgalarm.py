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

# LFG Alarm is a social alarm clock for iPhone and Android.  An Anything
# alarm has a private link; a POST to it rings the alarm on every phone
# that joined it.
#
# To set one up:
#  1. Create an Anything alarm in the LFG Alarm app.
#  2. Copy its private link.  It looks like:
#     https://api.lfg.gm/horn/{token}
#
#  The token at the end of the link is all Apprise needs.  Your Apprise URL
#  should be assembled as:
#     lfg://{token}
#
#  You can also paste the link itself as your Apprise URL.
#
# The title and body of your notification are never shown.  LFG Alarm
# ignores the request body and shows the alarm's own name when it rings.
#
# Anything alarms need a paid plan; see https://lfg.gm.
#
# Resources:
# - https://lfg.gm/developers

from __future__ import annotations

from json import loads
import re
from typing import Any, Optional

import requests

from ..common import NotifyType, OverflowMode
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
LFG_ALARM_HTTP_ERROR_MAP = {
    404: "No alarm was found at this link.",
    409: "The alarm is switched off; nothing rang.",
    429: "The alarm rang moments ago and is cooling down; nothing rang.",
}


class NotifyLFGAlarm(NotifyBase):
    """A wrapper for LFG Alarm Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "LFG Alarm"

    # The services URL
    service_url = "https://lfg.gm/"

    # The default secure protocol
    secure_protocol = "lfg"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/lfgalarm/"

    # The link every Anything alarm is rung through
    notify_url = "https://api.lfg.gm/horn/{token}"

    # Define object URL templates
    templates = ("{schema}://{token}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9]{32}$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "token": {
                "alias_of": "token",
            },
        },
    )

    def __init__(self, token: str, **kwargs: Any) -> None:
        """Initialize LFG Alarm Object."""
        super().__init__(**kwargs)

        # The body is never sent, so splitting it would only ring the alarm
        # again during its cooldown and report a failure.
        self.overflow_mode = OverflowMode.UPSTREAM

        # The token identifies the alarm we ring
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = "An invalid LFG Alarm token ({}) was specified.".format(
                token
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform LFG Alarm Notification."""

        # LFG Alarm never reads the request body, so none is sent; the
        # alarm shows its own name when it rings
        headers = {
            "User-Agent": self.app_id,
        }

        # Prepare our URL
        url = self.notify_url.format(token=self.token)

        self.logger.debug(
            "LFG Alarm POST URL: %s (cert_verify=%s)",
            self.notify_url.format(
                token=self.pprint(self.token, privacy=True, safe="")
            ),
            self.verify_certificate,
        )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            # Read the reply; it tells us how many phones rang, or how
            # long to wait before the alarm can ring again
            try:
                response = loads(r.content)
                if not isinstance(response, dict):
                    response = {}

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                response = {}

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyLFGAlarm.http_response_code_lookup(
                    r.status_code, LFG_ALARM_HTTP_ERROR_MAP
                )

                retry_after = response.get("retryAfterSeconds")
                if (
                    r.status_code == requests.codes.too_many_requests
                    and isinstance(retry_after, int)
                ):
                    status_str = "{} It can ring again in {}s.".format(
                        status_str, retry_after
                    )

                self.logger.warning(
                    "Failed to ring LFG Alarm: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug("Response Details:\r\n%r", r.content)

                # Return; we're done
                return False

            # A 200 reply only counts when it confirms the alarm rang
            fired = response.get("fired")
            if fired is not True:
                self.logger.warning("LFG Alarm did not ring: fired=%r.", fired)
                self.logger.debug("Response Details:\r\n%r", r.content)

                # Return; we're done
                return False

            devices = response.get("devices")
            if isinstance(devices, int):
                self.logger.info(
                    "Rang LFG Alarm on %d phone%s.",
                    devices,
                    "" if devices == 1 else "s",
                )

            else:
                self.logger.info("Rang LFG Alarm.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred ringing LFG Alarm."
            )
            self.logger.debug("Socket Exception: %s", str(e))

            # Return; we're done
            return False

        return True

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyLFGAlarm.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our token is kept in the host
        results["token"] = NotifyLFGAlarm.unquote(results["host"])

        # Support ?token= for an easier yaml configuration
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyLFGAlarm.unquote(results["qsd"]["token"])

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """Support https://api.lfg.gm/horn/TOKEN."""
        result = re.match(
            r"^https?://api\.lfg\.gm/horn/"
            r"(?P<token>[a-z0-9]{32})/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyLFGAlarm.parse_url(
                "{schema}://{token}/{params}".format(
                    schema=NotifyLFGAlarm.secure_protocol,
                    token=result.group("token"),
                    params=result.group("params") or "",
                )
            )

        return None
