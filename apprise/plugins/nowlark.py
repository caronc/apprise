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


# Nowlark delivers push notifications to iPhone, iPad, Mac and Apple Watch.
#
# 1. Install the Nowlark app and sign in.
# 2. In the app: Settings > Connect an App > Create Your Key. It looks like
#    nlk_ followed by 43 characters.
#
# Then use:
#   nowlark://{key}
#   nowlark://{key}/{source}
#
# The source is the sender's name shown on each notification, for example
# "Nightly backup". It defaults to "Apprise".
#
# Images and buttons are part of Nowlark's paid Upgrade Pass, and a send
# that uses one without it is refused, so this plugin sends text only.
#
# API reference: https://nowlark.com/api

from json import dumps
import re
from typing import Any, Optional, Union

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on: https://nowlark.com/api/errors
NOWLARK_HTTP_ERROR_MAP = {
    400: "Bad Request - A field is missing or invalid.",
    401: "Unauthorized - Missing, unknown or revoked key.",
    402: "Payment Required - The send used an Upgrade Pass feature.",
    429: "Too Many Requests - The key's hourly limit was reached.",
}


class NowlarkPriority:
    """Nowlark priorities, the same -2 to 2 scale Prowl and Pushover use."""

    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


NOWLARK_PRIORITIES = {
    NowlarkPriority.LOW: "low",
    NowlarkPriority.MODERATE: "moderate",
    NowlarkPriority.NORMAL: "normal",
    NowlarkPriority.HIGH: "high",
    NowlarkPriority.EMERGENCY: "emergency",
}

NOWLARK_PRIORITY_MAP = {
    # Maps against string 'low'
    "l": NowlarkPriority.LOW,
    # Maps against string 'moderate'
    "m": NowlarkPriority.MODERATE,
    # Maps against string 'normal'
    "n": NowlarkPriority.NORMAL,
    # Maps against string 'high'
    "h": NowlarkPriority.HIGH,
    # Maps against string 'emergency'
    "e": NowlarkPriority.EMERGENCY,
    # Entries to additionally support (so more like Nowlark's API)
    "-2": NowlarkPriority.LOW,
    "-1": NowlarkPriority.MODERATE,
    "0": NowlarkPriority.NORMAL,
    "1": NowlarkPriority.HIGH,
    "2": NowlarkPriority.EMERGENCY,
}


class NotifyNowlark(NotifyBase):
    """A wrapper for Nowlark Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Nowlark"

    # The services URL
    service_url = "https://nowlark.com/"

    # Secure Protocol
    secure_protocol = "nowlark"

    # The URL refererenced for remote Notifications
    notify_url = "https://nowlark.com/v1/notify"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/nowlark/"

    # Nowlark's own limits
    title_maxlen = 1024
    body_maxlen = 10000

    # The longest source and link Nowlark accepts
    source_maxlen = 256
    url_maxlen = 512

    # Define object templates
    templates = (
        "{schema}://{apikey}",
        "{schema}://{apikey}/{source}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^nlk_[A-Za-z0-9_-]{20,}$", ""),
            },
            "source": {
                "name": _("Source"),
                "type": "string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "key": {
                "alias_of": "apikey",
            },
            "source": {
                "alias_of": "source",
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:int",
                "values": tuple(NOWLARK_PRIORITIES),
                "default": NowlarkPriority.NORMAL,
            },
            "url": {
                "name": _("URL"),
                "type": "string",
                "map_to": "click",
            },
        },
    )

    def __init__(
        self,
        apikey: str,
        source: Optional[str] = None,
        priority: Optional[Union[str, int]] = None,
        click: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Nowlark Object."""
        super().__init__(**kwargs)

        # Validate our API Key (nlk_ prefix)
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"An invalid Nowlark API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The sender's name shown on each notification
        self.source = (source or "").strip() or self.app_id
        if len(self.source) > self.source_maxlen:
            msg = (
                f"The Nowlark source ({self.source}) is longer than "
                f"{self.source_maxlen} characters."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Accept a priority by name or by Nowlark's own -2 to 2 number
        self.priority = int(
            NotifyNowlark.template_args["priority"]["default"]
            if priority is None
            else next(
                (
                    v
                    for k, v in NOWLARK_PRIORITY_MAP.items()
                    if str(priority).lower().startswith(k)
                ),
                NotifyNowlark.template_args["priority"]["default"],
            )
        )

        # The link the notification opens: http or https only
        self.click = None
        if click:
            if (
                not re.match(r"^https?://", click, re.I)
                or len(click) > self.url_maxlen
            ):
                msg = (
                    f"The Nowlark url ({click}) must be http or https and "
                    f"at most {self.url_maxlen} characters."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.click = click

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Send our Nowlark Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.apikey}",
        }

        # Prepare our payload. Nowlark needs a title or a body, and only
        # the fields that are set are sent.
        payload = {
            "source": self.source,
            "priority": self.priority,
        }
        if title:
            payload["title"] = title

        if body:
            payload["body"] = body

        if self.click:
            payload["url"] = self.click

        self.logger.debug(
            "Nowlark POST URL: %s (cert_verify=%r)",
            self.notify_url,
            self.verify_certificate,
        )
        self.logger.debug("Nowlark Payload: %s", payload)

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
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyNowlark.http_response_code_lookup(
                    r.status_code, NOWLARK_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Nowlark notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return False

            self.logger.info("Sent Nowlark notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Nowlark notification."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # One key is one connection; the source is only a display name
        return (self.secure_protocol, self.apikey)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params: dict[str, Any] = {
            "priority": str(self.priority),
        }

        # Only include the link when one was set
        if self.click:
            params["url"] = self.click

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/{source}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(
                self.apikey, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            source=NotifyNowlark.quote(self.source, safe=""),
            params=NotifyNowlark.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The key is the host, or ?key= for yaml configuration
        results["apikey"] = NotifyNowlark.unquote(
            results["qsd"]["key"]
            if "key" in results["qsd"] and len(results["qsd"]["key"])
            else results["host"]
        )

        # The source is the first path entry, or ?source=
        entries = NotifyNowlark.split_path(results["fullpath"])
        if "source" in results["qsd"] and len(results["qsd"]["source"]):
            results["source"] = NotifyNowlark.unquote(results["qsd"]["source"])
        elif entries:
            results["source"] = entries[0]

        # Set our priority
        if "priority" in results["qsd"] and len(results["qsd"]["priority"]):
            results["priority"] = NotifyNowlark.unquote(
                results["qsd"]["priority"]
            )

        # The link the notification opens
        if "url" in results["qsd"] and len(results["qsd"]["url"]):
            results["click"] = NotifyNowlark.unquote(results["qsd"]["url"])

        return results
