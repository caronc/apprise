#
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

# WPUSH sends messages through WeChat, its App, SMS, Email, DingTalk, Feishu,
# WeCom, Webhooks, WeChat ClawBot, and QQ Robot. One request can use several
# channels.
#
# Steps to get your API Key:
#  1. Visit https://wpush.cn/ and sign in (or register).
#  2. Visit https://wpush.cn/apikey and copy your API Key. It always
#     starts with "WPUSH" followed by 27 more characters (32 total).
#  3. Visit https://wpush.cn/channels and bind at least one delivery
#     channel (WeChat, Email, etc.) before sending your first message.
#
# Basic Apprise URL:
#     wpush://{apikey}
#
# To notify a topic's subscribers, add extra channels, attach a
# click-through link, or target a specific QQ group:
#     wpush://{apikey}/{topic}?channel=feishu,dingtalk
#     wpush://{apikey}?url=https://example.com/
#     wpush://{apikey}?channel=qqbot&group={qq_group_code}
#     wpush://{apikey}?channel=feishu&option=ops
#
# Native API URL (also accepted):
#     https://api.wpush.cn/api/v1/send?apikey={apikey}
#
# Resources:
# - https://wpush.cn/docs
# - https://github.com/WPUSH/skills (current parameters)

import json
import re
from uuid import uuid4

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase


class WPushChannel:
    """WPUSH delivery channels."""

    # WeChat (WPUSH default)
    WECHAT = "wechat"

    # WPUSH mobile App
    APP = "app"

    # SMS
    SMS = "sms"

    # Email
    MAIL = "mail"

    # Configured Webhook
    WEBHOOK = "webhook"

    # DingTalk
    DINGTALK = "dingtalk"

    # Feishu
    FEISHU = "feishu"

    # WeCom (WeChat Work / Enterprise WeChat)
    WECHAT_WORK = "wechat_work"

    # WeChat ClawBot
    CLAWBOT = "clawbot"

    # QQ Robot with optional group targeting
    QQBOT = "qqbot"


# WPUSH accepts one or more of these channel values per request
WPUSH_CHANNELS = (
    WPushChannel.WECHAT,
    WPushChannel.APP,
    WPushChannel.SMS,
    WPushChannel.MAIL,
    WPushChannel.WEBHOOK,
    WPushChannel.DINGTALK,
    WPushChannel.FEISHU,
    WPushChannel.WECHAT_WORK,
    WPushChannel.CLAWBOT,
    WPushChannel.QQBOT,
)

# Default delivery channel
WPUSH_CHANNEL_DEFAULT = WPushChannel.WECHAT


class NotifyWPush(NotifyBase):
    """A wrapper for WPUSH Notifications."""

    # Service name shown to users
    service_name = "WPUSH"

    # WPUSH website
    service_url = "https://wpush.cn/"

    # Apprise URL scheme
    secure_protocol = "wpush"

    # Plugin setup guide
    setup_url = "https://appriseit.com/services/wpush/"

    # Notification endpoint
    notify_url = "https://api.wpush.cn/api/v1/send"

    # WPUSH limits messages to 10,000 characters and titles to 255
    body_maxlen = 10000
    title_maxlen = 255

    # Define object URL templates
    templates = (
        # No topic: broadcast a personal notification
        "{schema}://{apikey}",
        # Topics in path: one API call per topic
        "{schema}://{apikey}/{targets}",
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
                # WPUSH followed by exactly 27 more characters (32 total)
                "regex": (r"^WPUSH[a-z0-9]{27}$", "i"),
            },
            # Topic codes go directly in the URL path with no prefix
            "targets": {
                "name": _("Topics"),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            # Allow the API Key to be supplied as a query parameter
            "apikey": {
                "alias_of": "apikey",
            },
            # One or more comma-separated channels; WeChat is the default
            "channel": {
                "name": _("Channel"),
                "type": "list:string",
            },
            # ?to= is the standard Apprise alias for targets (topics)
            "to": {
                "alias_of": "targets",
            },
            # Keep WPUSH's ?topic_code= name as another target alias.
            "topic_code": {
                "alias_of": "targets",
            },
            # ?topic= is another alias for topic targets
            "topic": {
                "alias_of": "targets",
            },
            # QQ group code or multi-instance option code (API `option`)
            "group": {
                "name": _("Group / Option Code"),
                "type": "string",
                "map_to": "group",
            },
            # ?option= mirrors WPUSH's own API field name for the above
            "option": {
                "alias_of": "group",
            },
            # Optional click-through link included with the notification
            "url": {
                "name": _("Click URL"),
                "type": "string",
                "map_to": "click_url",
            },
        },
    )

    def __init__(
        self,
        apikey,
        targets=None,
        channel=None,
        group=None,
        click_url=None,
        **kwargs,
    ):
        """Initialize WPUSH Object."""
        super().__init__(**kwargs)

        # Validate the required API Key
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = "The WPUSH API Key ({}) is invalid.".format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Resolve one or more delivery channels (comma-separated)
        if channel:
            self.channels = []
            for entry in parse_list(channel):
                resolved = next(
                    (c for c in WPUSH_CHANNELS if c == entry.lower()),
                    None,
                )
                if not resolved:
                    msg = "The WPUSH channel ({}) is not valid.".format(entry)
                    self.logger.warning(msg)
                    raise TypeError(msg)
                self.channels.append(resolved)

        else:
            # Default to WeChat
            self.channels = [WPUSH_CHANNEL_DEFAULT]

        # Send one request for each resolved topic code
        self.topics = parse_list(targets)

        # Sub-target passed as API `option` (QQ group code or instance code)
        self.group = (
            group if isinstance(group, str) and group.strip() else None
        )

        # WPUSH rejects requests that combine option and topic targets
        if self.group and self.topics:
            msg = (
                "The WPUSH option/group cannot be combined with topic targets."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Optional click-through link delivered alongside the notification
        self.click_url = (
            click_url
            if isinstance(click_url, str) and click_url.strip()
            else None
        )

    def __len__(self):
        """Return the topic count, or one for a direct send."""
        # Keep direct sends countable by the framework
        return len(self.topics) if self.topics else 1

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform WPUSH Notification."""

        # Authenticate in both supported locations; WPUSH prefers the header
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "X-API-Key": self.apikey,
        }

        # A single call can target more than one channel at once
        channel_str = ",".join(self.channels)

        # Use None to send once without a topic.
        topics_to_notify = self.topics if self.topics else [None]

        # Track whether any individual send failed
        has_error = False

        for topic in topics_to_notify:
            # Build this topic's payload
            payload = {
                "apikey": self.apikey,
                # title is required by WPUSH; fall back to body when empty
                "title": title if title else body,
                "content": body,
                "channel": channel_str,
            }

            # Add an optional click-through link
            if self.click_url:
                payload["url"] = self.click_url

            if topic:
                # Add the topic code when broadcasting to a specific topic
                payload["topic_code"] = topic

            elif self.group:
                # API `option`: qqbot group code, or multi-instance code for
                # webhook / dingtalk / feishu / wechat_work
                payload["option"] = self.group

            self.logger.debug(
                "WPUSH POST URL: %s (cert_verify=%r)",
                self.notify_url,
                self.verify_certificate,
            )
            self.logger.debug("WPUSH Payload: %r", payload)

            # Give each request a unique key to prevent duplicate delivery
            headers["X-Idempotency-Key"] = str(uuid4())

            # Throttle each request
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    headers=headers,
                    # Preserve non-ASCII text, including Chinese characters
                    data=json.dumps(payload, ensure_ascii=False).encode(
                        "utf-8"
                    ),
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code != requests.codes.ok:
                    # Log the HTTP failure, then try the next topic
                    status_str = NotifyWPush.http_response_code_lookup(
                        r.status_code
                    )
                    self.logger.warning(
                        "Failed to send WPUSH notification: "
                        "{}{}error={}.".format(
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )
                    # Mark our failure and continue with the next topic
                    has_error = True
                    continue

                # WPUSH reports success as code 0 in its JSON response
                try:
                    content = json.loads(r.content)
                except (AttributeError, TypeError, ValueError):
                    # Handle malformed, missing, or unavailable response data
                    content = {}
                    self.logger.debug(
                        "Failed to parse WPUSH JSON response; body: %r",
                        (r.content or b"")[:2000],
                    )

                # Check WPUSH's result code (reject bool; False == 0 in Python)
                api_code = content.get("code") if content else None
                if isinstance(api_code, bool) or api_code != 0:
                    # WPUSH rejected the request
                    error_str = (
                        content.get("message", "Unknown error")
                        if content
                        else "Unknown error"
                    )
                    self.logger.warning(
                        "Failed to send WPUSH notification: "
                        "code={}: {}.".format(api_code, error_str)
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        content if content else (r.content or b"")[:2000],
                    )
                    # Mark our failure and continue with the next topic
                    has_error = True
                    continue

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending WPUSH notification."
                )
                self.logger.debug("Socket Exception: %s", str(e))
                # Mark our failure and continue with the next topic
                has_error = True
                continue

            # Notification delivered for this topic
            self.logger.info(
                "Sent WPUSH notification%s.",
                " to topic {}".format(topic) if topic else "",
            )

        return not has_error

    @property
    def url_identifier(self):
        """Return the fields that uniquely identify this WPUSH account.

        Topics are targets, so they are excluded.
        """
        # The API Key alone identifies the WPUSH account
        return (self.secure_protocol, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """Build a WPUSH URL from this configuration."""

        # Collect optional URL parameters
        params = {}

        # Include ?channel= when it differs from the default
        if self.channels != [WPUSH_CHANNEL_DEFAULT]:
            params["channel"] = ",".join(self.channels)

        # Include the QQ group code when set
        if self.group:
            params["group"] = self.group

        # Include the click-through link when set
        if self.click_url:
            params["url"] = self.click_url

        # Add standard Apprise options such as verify and format
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Mask the API Key when privacy mode is active
        apikey_str = self.pprint(
            self.apikey, privacy, mode=PrivacyMode.Secret, safe=""
        )

        if self.topics:
            # One or more topics: include them in the URL path
            return "{schema}://{apikey}/{targets}/?{params}".format(
                schema=self.secure_protocol,
                apikey=apikey_str,
                targets="/".join(
                    NotifyWPush.quote(t, safe="") for t in self.topics
                ),
                params=NotifyWPush.urlencode(params),
            )

        # No topics produce a simple personal notification URL
        return "{schema}://{apikey}/?{params}".format(
            schema=self.secure_protocol,
            apikey=apikey_str,
            params=NotifyWPush.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parse a WPUSH URL into constructor arguments."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # Stop when the base URL could not be parsed
            return results

        # Prefer ?apikey= query parameter over the URL host field
        if "apikey" in results["qsd"] and results["qsd"]["apikey"]:
            results["apikey"] = NotifyWPush.unquote(results["qsd"]["apikey"])
        else:
            results["apikey"] = NotifyWPush.unquote(results["host"])

        # Collect topic codes from the URL path
        results["targets"] = NotifyWPush.split_path(results["fullpath"])

        # ?to= adds comma- or space-separated topics
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyWPush.parse_list(results["qsd"]["to"])

        # ?topic_code= mirrors WPUSH's own API field name
        if "topic_code" in results["qsd"] and results["qsd"]["topic_code"]:
            results["targets"] += NotifyWPush.parse_list(
                results["qsd"]["topic_code"]
            )

        # ?topic= is another alias for topic targets
        if "topic" in results["qsd"] and results["qsd"]["topic"]:
            results["targets"] += NotifyWPush.parse_list(
                results["qsd"]["topic"]
            )

        # Pass channels to __init__ for splitting and validation
        if "channel" in results["qsd"] and results["qsd"]["channel"]:
            results["channel"] = NotifyWPush.unquote(results["qsd"]["channel"])

        # Accept ?option=, but prefer ?group= when both are set
        if "option" in results["qsd"] and results["qsd"]["option"]:
            results["group"] = NotifyWPush.unquote(results["qsd"]["option"])
        if "group" in results["qsd"] and results["qsd"]["group"]:
            results["group"] = NotifyWPush.unquote(results["qsd"]["group"])

        # Extract the optional click-through link from ?url=
        if "url" in results["qsd"] and results["qsd"]["url"]:
            results["click_url"] = NotifyWPush.unquote(results["qsd"]["url"])

        return results

    @staticmethod
    def parse_native_url(url):
        """Parse a native WPUSH API URL such as:
        https://api.wpush.cn/api/v1/send?apikey=KEY[&channel=...]
        """
        result = re.match(
            r"^https?://api\.wpush\.cn/api/v1/send"
            r"(?:\?(?P<params>[^#]+))?$",
            url,
            re.I,
        )
        if result:
            params = result.group("params") or ""
            key = re.search(
                r"(?:(?:^|&))apikey=(?P<apikey>[^&]+)",
                params,
                re.I,
            )
            if key:
                return NotifyWPush.parse_url(
                    "{schema}://{apikey}/?{params}".format(
                        schema=NotifyWPush.secure_protocol,
                        apikey=NotifyWPush.unquote(key.group("apikey")),
                        params=params,
                    )
                )
        return None
