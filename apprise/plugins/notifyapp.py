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


# Notify! (by Pingie) sends push notifications to iPhone, iPad, Mac and web
# browsers.
#
# To get your Device ID and Token:
#  1. Install the Notify! app (iOS/macOS) or open the web app in a browser.
#  2. Your Device ID and Token are shown in the app.
#  3. A Device Group has its own ID (it starts with GRP) and Token; find them
#     under Devices -> Device Groups -> (your group).
#
# Your Apprise URL should be assembled as:
#     notifyapp://{device_id}/{token}
#
# Resources:
# - https://getnotifyapp.com/apidocs/

from __future__ import annotations

from json import dumps, loads
import re
from typing import Any, Optional

import requests

from ..common import NotifyImageSize, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on: https://getnotifyapp.com/apidocs/
NOTIFYAPP_HTTP_ERROR_MAP = {
    400: "Bad Request - The notification could not be delivered.",
    403: "Forbidden - Invalid Token.",
    404: "Not Found - The Device or Group ID does not exist.",
    415: "Unsupported Media Type.",
    429: "Too many requests were made.",
}


class NotifyNotifyApp(NotifyBase):
    """A wrapper for Notify! Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Notify!"

    # The services URL
    service_url = "https://getnotifyapp.com/"

    # The default secure protocol
    secure_protocol = "notifyapp"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/notifyapp/"

    # Notify! JSON API URL; the Device or Group ID is appended to it
    notify_url = "https://push.getnotifyapp.com/notify-json/"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 16384

    # The maximum allowable characters allowed in the title per message
    title_maxlen = 2048

    # Define object templates
    templates = ("{schema}://{device}/{token}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "device": {
                "name": _("Device ID"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9_-]+$", "i"),
            },
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
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
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
            "thread": {
                "name": _("Thread ID"),
                "type": "string",
            },
            "urgent": {
                "name": _("Time Sensitive"),
                "type": "bool",
                "default": False,
            },
        },
    )

    def __init__(
        self,
        device: str,
        token: str,
        include_image: bool = True,
        thread: Optional[str] = None,
        urgent: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Notify! Object."""
        super().__init__(**kwargs)

        # The Device (or Device Group) ID we notify
        self.device = validate_regex(
            device, *self.template_tokens["device"]["regex"]
        )
        if not self.device:
            msg = f"An invalid Notify! Device ID ({device}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The Token that goes with our Device (or Device Group) ID
        self.token = validate_regex(token)
        if not self.token:
            msg = f"An invalid Notify! Token ({token}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Send our Apprise icon along as the sender avatar
        self.include_image = include_image

        # Notifications sharing a thread are grouped together on the device
        self.thread = thread.strip() if thread else None

        # Time sensitive notifications can break through Focus modes
        self.urgent = (
            self.template_args["urgent"]["default"]
            if urgent is None
            else bool(urgent)
        )

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Notify! Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Prepare our payload
        payload: dict[str, Any] = {
            "text": body,
        }

        # A title is only included when one was provided
        if title:
            payload["title"] = title

        # Acquire our image url if configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )
        if image_url:
            payload["iconUrl"] = image_url

        # Group our notification into a thread if one was specified
        if self.thread:
            payload["groupType"] = self.thread

        # Only flag the notification when it was requested
        if self.urgent:
            payload["timeSensitive"] = True

        # Prepare our URL
        url = self.notify_url + NotifyNotifyApp.quote(self.device, safe="")

        self.logger.debug(
            "Notify! POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Notify! Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                params={"token": self.token},
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            self.logger.trace("Notify! Response: %s", r.content)

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyNotifyApp.http_response_code_lookup(
                    r.status_code, NOTIFYAPP_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Notify! notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Mark our failure
                return False

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # An unreadable response still means it was accepted
                content = {}

            # A Device Group reports devices it could not reach
            if not isinstance(content, dict):
                content = {}

            failures = content.get("failureCount")
            if failures:
                self.logger.warning(
                    "Notify! could not reach %s device(s) in group %s.",
                    failures,
                    self.device,
                )

                # Retrying is only safe when no device received it
                if not content.get("successCount"):
                    return False

            self.logger.info("Sent Notify! notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Notify! notification."
            )
            self.logger.debug("Socket Exception: %s", str(e))

            # Mark our failure
            return False

        return True

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The Device ID and its Token identify the connection
        return (self.secure_protocol, self.device, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params: dict[str, Any] = {
            "image": "yes" if self.include_image else "no",
            "urgent": "yes" if self.urgent else "no",
        }

        # Only include our thread if one was set
        if self.thread:
            params["thread"] = self.thread

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{device}/{token}/?{params}".format(
            schema=self.secure_protocol,
            device=self.pprint(self.device, privacy, safe=""),
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyNotifyApp.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early
            return results

        # Our Device ID is the host
        results["device"] = NotifyNotifyApp.unquote(results["host"])

        # Our Token is the first entry on our path
        entries = NotifyNotifyApp.split_path(results["fullpath"])
        results["token"] = entries[0] if entries else None

        # The 'token' makes it easier to use yaml configuration
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyNotifyApp.unquote(results["qsd"]["token"])

        # Include images with our message
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        # Our thread identifier
        if "thread" in results["qsd"] and results["qsd"]["thread"]:
            results["thread"] = NotifyNotifyApp.unquote(
                results["qsd"]["thread"]
            )

        # Time sensitive delivery
        if "urgent" in results["qsd"] and results["qsd"]["urgent"]:
            results["urgent"] = parse_bool(results["qsd"]["urgent"])

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """
        Support:
           https://push.getnotifyapp.com/notify/{device}?token={token}
           https://push.getnotifyapp.com/notify-json/{device}?token={token}
           https://push.getnotifyapp.com/notify-group/{group}?token={token}
        """

        result = re.match(
            r"^https?://push\.getnotifyapp\.com/"
            r"notify(-json|-group)?/(?P<device>[A-Z0-9_-]+)/?"
            r"(?P<params>\?[^#]+)?(#.*)?$",
            url,
            re.I,
        )

        if result:
            return NotifyNotifyApp.parse_url(
                "{schema}://{device}/{params}".format(
                    schema=NotifyNotifyApp.secure_protocol,
                    device=result.group("device"),
                    params=result.group("params") or "",
                )
            )

        return None
