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

# Lauther — notifications & anonymous identity
#   1. Install the Lauther app (https://lauther.app/)
#   2. In the app: Apps -> + -> New token
#   3. Your token looks like: lpt_AbCdEf...
#
# Syntax:
#   lauther://{token}
#   lauther://{token}?priority=high&sound=default
#

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase


# Priorities (Pushover-style scale)
class LautherPriority:
    LOWEST = -2
    LOW = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


LAUTHER_PRIORITIES = {
    # Note: This also acts as a reverse lookup mapping
    LautherPriority.LOWEST: "lowest",
    LautherPriority.LOW: "low",
    LautherPriority.NORMAL: "normal",
    LautherPriority.HIGH: "high",
    LautherPriority.EMERGENCY: "emergency",
}

LAUTHER_PRIORITY_MAP = {
    # short for 'lowest'
    "lowest": LautherPriority.LOWEST,
    # short for 'low'
    "low": LautherPriority.LOW,
    # short for 'normal'
    "normal": LautherPriority.NORMAL,
    # short for 'high'
    "high": LautherPriority.HIGH,
    # short for 'emergency'
    "emergency": LautherPriority.EMERGENCY,
}


class NotifyLauther(NotifyBase):
    """A wrapper for Lauther Notifications."""

    # The default descriptive name associated with the Notification
    service_name = _("Lauther")

    # The services URL
    service_url = "https://lauther.app/"

    # The default secure protocol
    secure_protocol = "lauther"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://lauther.app/docs.html"

    # Notification URL
    notify_url = "https://api.lauther.id/v1/push"

    # Define object templates
    templates = ("{schema}://{token}",)

    # Define our tokens; these are the minimum tokens required required to
    # be passed into this function (as arguments).
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^lpt_[a-z0-9]+$", "i"),
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
            "priority": {
                "name": _("Priority"),
                "type": "choice:int",
                "values": LAUTHER_PRIORITIES,
                "default": LautherPriority.NORMAL,
            },
            "sound": {
                "name": _("Sound"),
                "type": "string",
            },
            "click": {
                "name": _("Click URL"),
                "type": "string",
            },
        },
    )

    def __init__(self, token, priority=None, sound=None, click=None, **kwargs):
        """Initialize Lauther Object."""
        super().__init__(**kwargs)

        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"The Lauther token specified ({token}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # The priority of the message
        self.priority = int(
            NotifyLauther.template_args["priority"]["default"]
            if priority is None
            else next(
                (
                    v
                    # Longest key first: "lowest" and "low" share a prefix, so
                    # a shortest-first scan resolves "low" to LOWEST. Upstream
                    # Pushover avoids this with single-letter keys, which is
                    # not available here — its scale has no "lowest".
                    for k, v in sorted(
                        LAUTHER_PRIORITY_MAP.items(),
                        key=lambda kv: -len(kv[0]),
                    )
                    if str(priority).lower().startswith(k)
                ),
                (
                    int(priority)
                    if str(priority).lstrip("+-").isdigit()
                    else NotifyLauther.template_args["priority"]["default"]
                ),
            )
        )
        if self.priority not in LAUTHER_PRIORITIES:
            msg = f"The Lauther priority specified ({priority}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # An optional sound and click-through URL
        self.sound = sound
        self.click = click

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform the Lauther Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        payload = {
            "title": title,
            "message": body,
            "priority": self.priority,
        }
        if self.sound:
            payload["sound"] = self.sound
        if self.click:
            payload["url"] = self.click

        self.logger.debug(
            "Lauther POST URL:"
            f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Lauther Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                json=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyLauther.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Lauther notification: "
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Lauther notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Lauther notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "priority": LAUTHER_PRIORITIES[self.priority],
        }
        if self.sound:
            params["sound"] = self.sound
        if self.click:
            params["click"] = self.click

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyLauther.urlencode(params),
        )

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.token)

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Allow over-ride; template_args advertises `token` as an argument,
        # so a URL of the form lauther://?token=lpt_... has to work.
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["token"] = NotifyLauther.unquote(results["qsd"]["token"])

        else:
            results["token"] = NotifyLauther.unquote(results["host"])

        # Get our priority (if defined)
        if "priority" in results["qsd"] and len(results["qsd"]["priority"]):
            results["priority"] = NotifyLauther.unquote(
                results["qsd"]["priority"]
            )

        # Get our sound (if defined)
        if "sound" in results["qsd"] and len(results["qsd"]["sound"]):
            results["sound"] = NotifyLauther.unquote(results["qsd"]["sound"])

        # Get our click-through URL (if defined)
        if "click" in results["qsd"] and len(results["qsd"]["click"]):
            results["click"] = NotifyLauther.unquote(results["qsd"]["click"])

        return results
