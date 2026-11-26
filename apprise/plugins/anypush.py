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


# anypush sends push notifications to an Android phone through the anypush
# app (https://anypush.app).
#
# To get your channel address:
#  1. Install the anypush app from Google Play.
#  2. Make a channel in the app and copy its address. It looks like:
#       https://anypush.app/h/YOUR_CHANNEL_TOKEN
#
# Your Apprise URL is the token at the end of that address:
#     anypush://{token}
#
# The channel address itself is accepted as an Apprise URL too.
#
# The channel address is a secret: anyone who has it can push to the phone
# it belongs to, so the token is never written to the logs.
#
# Resources:
# - https://anypush.app/webhooks

from __future__ import annotations

from json import dumps
import re
from typing import Any, Optional, Union
from uuid import uuid4

import requests

from .. import __version__
from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_choice, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on: https://anypush.app/webhooks
ANYPUSH_HTTP_ERROR_MAP = {
    404: "No channel at this address; the token is wrong or was deleted.",
    413: "The message is too large.",
    422: "A field of the message was rejected.",
    429: "Too many messages were sent to this channel.",
    503: "anypush is briefly unavailable.",
}


class AnypushPriority:
    """anypush Priority Definitions."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


ANYPUSH_PRIORITIES = (
    AnypushPriority.LOW,
    AnypushPriority.NORMAL,
    AnypushPriority.HIGH,
)

# The priority words of other services, mapped onto the three anypush
# knows.  An abbreviation picks the first entry that starts with it, so
# the order matters: "m" is "min", "mo" is "moderate" and "ma" is "max".
ANYPUSH_PRIORITY_MAP = {
    "low": AnypushPriority.LOW,
    "min": AnypushPriority.LOW,
    "normal": AnypushPriority.NORMAL,
    "default": AnypushPriority.NORMAL,
    "moderate": AnypushPriority.NORMAL,
    "high": AnypushPriority.HIGH,
    "max": AnypushPriority.HIGH,
    "urgent": AnypushPriority.HIGH,
    "emergency": AnypushPriority.HIGH,
}


class NotifyAnypush(NotifyBase):
    """A wrapper for anypush Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "anypush"

    # The services URL
    service_url = "https://anypush.app/"

    # The default secure protocol
    secure_protocol = "anypush"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/anypush/"

    # The channel address; the token is appended to it
    notify_url = "https://anypush.app/h/"

    # anypush shows plain text
    notify_format = NotifyFormat.TEXT

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4096

    # The maximum allowable characters allowed in the title per message
    title_maxlen = 256

    # Define object templates
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
                "regex": (r"^[a-z2-7]{24,52}$", "i"),
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
                "type": "choice:string",
                "values": ANYPUSH_PRIORITIES,
                "default": AnypushPriority.NORMAL,
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
        token: str,
        priority: Optional[str] = None,
        click: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize anypush Object."""
        super().__init__(**kwargs)

        # The channel token (anypush hands it out in lowercase)
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            # The value is left out: a mistyped token is still most of the
            # secret address of a channel
            msg = "An invalid anypush channel token was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        self.token = self.token.lower()

        # The priority of the message
        self.priority = self.template_args["priority"]["default"]
        if priority:
            match = parse_choice(str(priority), ANYPUSH_PRIORITY_MAP)
            if not match:
                msg = (
                    f"An invalid anypush priority ({priority}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.priority = ANYPUSH_PRIORITY_MAP[match]

        # The address opened when the notification is tapped
        self.click = None
        if click:
            self.click = validate_regex(click, r"^https?://\S+$", "i")
            if not self.click:
                msg = f"An invalid anypush URL ({click}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform anypush Notification."""

        # A retry of this message reuses its key, so anypush shows it once
        idempotency_key = self.recall("idempotency_key")
        if idempotency_key is None:
            idempotency_key = str(uuid4())
            self.remember("idempotency_key", idempotency_key)

        # Prepare our headers
        headers = {
            "User-Agent": f"anypush-apprise/{__version__}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        # Prepare our payload
        payload: dict[str, Any] = {
            "message": body,
            "priority": self.priority,
        }

        # A title is only included when one was provided
        if title:
            payload["title"] = title

        # Open this address when the notification is tapped
        if self.click:
            payload["url"] = self.click

        # Prepare our URL
        url = self.notify_url + self.token

        self.logger.debug(
            "anypush POST URL: %s (cert_verify=%r)",
            self._redact(url),
            self.verify_certificate,
        )
        self.logger.debug("anypush Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.accepted,
            ):
                # We had a problem
                status_str = NotifyAnypush.http_response_code_lookup(
                    r.status_code, ANYPUSH_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send anypush notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r",
                    self._redact(r.content or b"")[:2000],
                )

                # Mark our failure
                return False

            # The answer is not logged: it holds the channel address
            self.logger.info("Sent anypush notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending anypush notification."
            )
            # The error names the address it could not reach
            self.logger.debug("Socket Exception: %s", self._redact(str(e)))

            # Mark our failure
            return False

        return True

    def _redact(self, content: Union[str, bytes]) -> Union[str, bytes]:
        """Returns the content with the channel token masked."""
        masked = self.pprint(self.token, privacy=True, safe="")
        if isinstance(content, bytes):
            return content.replace(
                self.token.encode("utf-8"), masked.encode("utf-8")
            )

        return content.replace(self.token, masked)

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
        params: dict[str, Any] = {
            "priority": self.priority,
        }

        # Only include our tap address if one was set
        if self.click:
            params["url"] = self.click

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyAnypush.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early
            return results

        # The 'token' makes it easier to use yaml configuration
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyAnypush.unquote(results["qsd"]["token"])

        else:
            # Our token is the host
            results["token"] = NotifyAnypush.unquote(results["host"])

        # Our priority
        if "priority" in results["qsd"] and results["qsd"]["priority"]:
            results["priority"] = NotifyAnypush.unquote(
                results["qsd"]["priority"]
            )

        # The address opened when the notification is tapped; it is already
        # unquoted, and a second pass would change any %-escapes it holds
        if "url" in results["qsd"] and results["qsd"]["url"]:
            results["click"] = results["qsd"]["url"]

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """
        Support https://anypush.app/h/{token}
        """

        result = re.match(
            r"^https?://anypush\.app/h/(?P<token>[a-z2-7]{24,52})/?"
            r"(?P<params>\?[^#]+)?(#.*)?$",
            url,
            re.I,
        )

        if result:
            return NotifyAnypush.parse_url(
                "{schema}://{token}/{params}".format(
                    schema=NotifyAnypush.secure_protocol,
                    token=result.group("token"),
                    params=result.group("params") or "",
                )
            )

        return None
