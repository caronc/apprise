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

# Gorush is a self-hosted push notification server. It forwards messages
# to Apple (APNs), Android (FCM) and Huawei (HMS) devices for you.
#
# Steps:
#  1. Install and start Gorush, see https://github.com/appleboy/gorush.
#     It listens on port 8088 by default.
#  2. Configure the platforms you plan to use (ios, android and/or huawei)
#     in the Gorush configuration file.
#  3. Collect the device tokens your mobile app registered for push.
#
# URL syntax (HTTP):
#   gorush://host:port/device_token
#   gorush://host:port/device_token1/device_token2?platform=ios
#
# URL syntax (HTTPS, or behind a reverse proxy with basic auth):
#   gorushs://user:password@host/device_token
#
# Gorush only accepts an image as a web URL, so file attachments are not
# supported.
#
# Resources:
# - https://github.com/appleboy/gorush#run-gorush-web-server

from __future__ import annotations

from json import dumps, loads
from typing import Any, Optional

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_list
from .base import NotifyBase


class GorushPlatform:
    """The device platforms Gorush can deliver to."""

    # Apple Push Notification service
    IOS = "ios"

    # Firebase Cloud Messaging
    ANDROID = "android"

    # Huawei Mobile Services
    HUAWEI = "huawei"


# The platform number Gorush expects for each platform
GORUSH_PLATFORMS = {
    GorushPlatform.IOS: 1,
    GorushPlatform.ANDROID: 2,
    GorushPlatform.HUAWEI: 3,
}

# Accept the platform names, their service names and Gorush's own numbers
GORUSH_PLATFORM_MAP = {
    "ios": GorushPlatform.IOS,
    "apns": GorushPlatform.IOS,
    "1": GorushPlatform.IOS,
    "android": GorushPlatform.ANDROID,
    "fcm": GorushPlatform.ANDROID,
    "2": GorushPlatform.ANDROID,
    "huawei": GorushPlatform.HUAWEI,
    "hms": GorushPlatform.HUAWEI,
    "3": GorushPlatform.HUAWEI,
}

# The priorities Gorush accepts
GORUSH_PRIORITIES = ("normal", "high")

# Gorush errors documented at:
# https://github.com/appleboy/gorush/blob/master/router/server.go
GORUSH_HTTP_ERROR_MAP = {
    400: "Bad request, or too many notifications.",
}

# Gorush reports each device it could not reach with this log type
GORUSH_FAILED_PUSH = "failed-push"


class NotifyGorush(NotifyBase):
    """Send push notifications through a Gorush server."""

    # The default descriptive name associated with the Notification
    service_name = "Gorush"

    # The services URL
    service_url = "https://github.com/appleboy/gorush"

    # The default protocol (plain HTTP)
    protocol = "gorush"

    # The default secure protocol (HTTPS)
    secure_protocol = "gorushs"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/gorush/"

    # Self-hosted Gorush servers do not need client-side rate limiting.
    request_rate_per_sec = 0

    # Push notifications are plain text.
    notify_format = NotifyFormat.TEXT

    # APNs, FCM and HMS each cap a push at roughly 4KB in total, so leave
    # a little room for the rest of the payload.
    body_maxlen = 4000

    # Define object URL templates
    templates = (
        "{schema}://{host}/{targets}",
        "{schema}://{host}:{port}/{targets}",
        "{schema}://{user}@{host}/{targets}",
        "{schema}://{user}@{host}:{port}/{targets}",
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
    )

    # Define our template tokens
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
            "user": {
                "name": _("Username"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "target_device": {
                "name": _("Target Device"),
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
            "platform": {
                "name": _("Platform"),
                "type": "choice:string",
                "values": tuple(GORUSH_PLATFORMS),
                "default": GorushPlatform.ANDROID,
            },
            "mode": {
                "alias_of": "platform",
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:string",
                "values": GORUSH_PRIORITIES,
            },
            "topic": {
                "name": _("Topic"),
                "type": "string",
            },
            "sound": {
                "name": _("Sound"),
                "type": "string",
            },
            "badge": {
                "name": _("Badge"),
                "type": "int",
                "min": 0,
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    # Define our data entry
    template_kwargs = {
        "data_kwargs": {
            "name": _("Data Entries"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        targets: Optional[Any] = None,
        platform: Optional[str] = None,
        priority: Optional[str] = None,
        topic: Optional[str] = None,
        sound: Optional[str] = None,
        badge: Optional[Any] = None,
        data_kwargs: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a Gorush notification."""
        super().__init__(**kwargs)

        # Every token in this URL goes to the same platform.
        self.platform = (
            self.template_args["platform"]["default"]
            if not platform
            else GORUSH_PLATFORM_MAP.get(str(platform).strip().lower())
        )
        if not self.platform:
            msg = f"The Gorush platform specified ({platform}) is invalid."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Gorush accepts "normal" or "high"; unset leaves it to Gorush.
        self.priority = None
        if priority:
            self.priority = next(
                (
                    p
                    for p in GORUSH_PRIORITIES
                    if p.startswith(str(priority).strip().lower())
                ),
                None,
            )
            if not self.priority:
                msg = f"The Gorush priority specified ({priority}) is invalid."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The badge count shown on the app icon (iOS only).
        try:
            self.badge = None if badge in (None, "") else int(badge)

        except (TypeError, ValueError):
            # A value that is not a number is rejected below.
            self.badge = -1

        if self.badge is not None and self.badge < 0:
            msg = f"The Gorush badge specified ({badge}) is invalid."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Optional topic (the app bundle ID on iOS) and sound name.
        self.topic = topic if isinstance(topic, str) and topic else None
        self.sound = sound if isinstance(sound, str) and sound else None

        # Extra key/value pairs handed to the mobile app.
        self.data_kwargs = {}
        if isinstance(data_kwargs, dict):
            self.data_kwargs.update(data_kwargs)

        # Device tokens are opaque, so any value is accepted.
        self.targets = parse_list(targets)

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Push the notification to every device token in one request."""
        if not self.targets:
            # A notification needs at least one device token.
            self.logger.warning("There are no Gorush devices to notify.")
            return False

        # Skip devices an earlier attempt already reached.  A failed
        # attempt always leaves at least one device for the retry.
        tokens = [t for t in self.targets if not self.is_delivered(t)]

        # Prepare our notification
        notification = {
            "tokens": tokens,
            "platform": GORUSH_PLATFORMS[self.platform],
            "message": body,
        }

        if title:
            notification["title"] = title

        # Only send the optional fields that were set.
        if self.priority:
            notification["priority"] = self.priority

        if self.topic:
            notification["topic"] = self.topic

        if self.sound:
            notification["sound"] = self.sound

        if self.badge is not None:
            notification["badge"] = self.badge

        if self.data_kwargs:
            notification["data"] = self.data_kwargs

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Basic auth is only needed when a reverse proxy asks for it.
        auth = (self.user, self.password) if self.user else None

        # Prepare our URL
        url = "{schema}://{host}{port}/api/push".format(
            schema="https" if self.secure else "http",
            host=self.host,
            port=f":{self.port}" if self.port else "",
        )

        self.logger.debug(
            "Gorush POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Gorush Payload: %s", notification)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps({"notifications": [notification]}),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            self.logger.trace("Gorush Response: %s", r.content)

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyGorush.http_response_code_lookup(
                    r.status_code, GORUSH_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Gorush notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Mark our failure
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Gorush notification "
                "to %s.",
                self.host,
            )
            self.logger.debug("Socket Exception: %s", str(e))

            # Mark our failure
            return False

        try:
            content = loads(r.content)

        except (AttributeError, TypeError, ValueError):
            # An empty or unreadable reply still means Gorush accepted it.
            content = {}

        # Gorush only lists failed devices, and only in its sync mode.
        logs = content.get("logs") if isinstance(content, dict) else None
        failed = [
            entry
            for entry in (logs if isinstance(logs, list) else [])
            if isinstance(entry, dict)
            and entry.get("type") == GORUSH_FAILED_PUSH
        ]

        if not failed:
            self.logger.info(
                "Sent Gorush notification to %d device(s).", len(tokens)
            )
            return True

        for entry in failed:
            self.logger.warning(
                "Gorush could not notify a device: %s",
                entry.get("error") or "unknown error",
            )

        # Gorush can hide part of each token in its reply.  Only let a
        # retry skip devices when every failure can be matched exactly.
        failed_tokens = {entry.get("token") for entry in failed}
        if failed_tokens.issubset(tokens):
            for token in tokens:
                if token not in failed_tokens:
                    # This device received it; a retry can skip it.
                    self.mark_delivered(token)

        # Mark our failure
        return False

    def __len__(self) -> int:
        """Return the number of requests this notification makes."""
        # Every device token is sent in a single request.
        return 1

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Return the settings that identify this Gorush server.

        Targets are excluded so delivery can be tracked per device.
        """
        # Include the server address, protocol, and credentials.
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user,
            self.password,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Return a Gorush URL for the current settings and targets."""
        # Define any URL parameters
        params = {"platform": self.platform}

        if self.priority:
            params["priority"] = self.priority

        if self.topic:
            params["topic"] = self.topic

        if self.sound:
            params["sound"] = self.sound

        if self.badge is not None:
            params["badge"] = str(self.badge)

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Append our data entries
        params.update({f"+{k}": v for k, v in self.data_kwargs.items()})

        # Determine Authentication
        auth = ""
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=NotifyGorush.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )

        elif self.user:
            auth = "{user}@".format(
                user=NotifyGorush.quote(self.user, safe=""),
            )

        return "{schema}://{auth}{host}{port}/{targets}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            host=self.host,
            port="" if not self.port else f":{self.port}",
            targets="/".join(
                self.pprint(t, privacy, safe="") for t in self.targets
            ),
            params=NotifyGorush.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse a Gorush URL into constructor arguments."""
        results = NotifyBase.parse_url(url, verify_host=True)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Every path entry is a device token
        results["targets"] = NotifyGorush.split_path(results["fullpath"])

        # Support the ?to= argument
        if results["qsd"].get("to"):
            results["targets"] += NotifyGorush.parse_list(results["qsd"]["to"])

        # mode= is an alias; platform= wins when both are given
        if results["qsd"].get("mode"):
            results["platform"] = NotifyGorush.unquote(results["qsd"]["mode"])

        if results["qsd"].get("platform"):
            results["platform"] = NotifyGorush.unquote(
                results["qsd"]["platform"]
            )

        # Read our remaining options
        for key in ("priority", "topic", "sound", "badge"):
            if results["qsd"].get(key):
                results[key] = NotifyGorush.unquote(results["qsd"][key])

        # Store our data entries
        results["data_kwargs"] = results["qsd+"]

        return results
