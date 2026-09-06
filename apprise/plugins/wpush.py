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
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
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

# WPUSH is a Chinese multi-channel push platform (WeChat, App, SMS, email,
# DingTalk, Feishu, WeCom, webhook, and more). Docs: https://wpush.cn/docs
#
# Obtain your API Key from https://wpush.cn/settings (starts with WPUSH).
# Bind at least one channel at https://wpush.cn/channels before sending.
#
# Apprise URL forms:
#   wpush://{apikey}
#   wpush://{apikey}?channel=wechat
#   wpush://{apikey}?channel=feishu&topic_code={code}
#   wpush://?apikey={apikey}
#
# Native API URL (also accepted):
#   https://api.wpush.cn/api/v1/send?apikey={apikey}
#
# Success is JSON code === 0 (unlike PushPlus which uses code 200).

import json
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex
from .base import NotifyBase


class WPushChannel:
    """WPUSH delivery channels."""

    WECHAT = "wechat"
    APP = "app"
    SMS = "sms"
    MAIL = "mail"
    WEBHOOK = "webhook"
    DINGTALK = "dingtalk"
    FEISHU = "feishu"
    WECHAT_WORK = "wechat_work"
    CLAWBOT = "clawbot"
    QQBOT = "qqbot"


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

WPUSH_CHANNEL_DEFAULT = WPushChannel.WECHAT


class NotifyWPush(NotifyBase):
    """A wrapper for WPUSH Notifications."""

    service_name = "WPUSH"

    service_url = "https://wpush.cn/"

    secure_protocol = "wpush"

    setup_url = "https://wpush.cn/docs"

    notify_url = "https://api.wpush.cn/api/v1/send"

    # Practical caps aligned with WPUSH open API docs
    body_maxlen = 10000
    title_maxlen = 255

    templates = ("{schema}://{apikey}",)

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
                # Keys start with WPUSH followed by alphanumeric characters
                "regex": (r"^WPUSH[a-z0-9]+$", "i"),
            },
        },
    )

    template_args = dict(
        NotifyBase.template_args,
        **{
            "apikey": {
                "alias_of": "apikey",
            },
            "channel": {
                "name": _("Channel"),
                "type": "choice:string",
                "values": WPUSH_CHANNELS,
                "default": WPUSH_CHANNEL_DEFAULT,
            },
            "topic_code": {
                "name": _("Topic Code"),
                "type": "string",
            },
            # Convenience alias used elsewhere in Apprise
            "to": {
                "alias_of": "topic_code",
            },
        },
    )

    def __init__(self, apikey, channel=None, topic_code=None, **kwargs):
        """Initialize WPUSH Object."""
        super().__init__(**kwargs)

        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = "The WPUSH API Key ({}) is invalid.".format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        if channel:
            self.channel = next(
                (c for c in WPUSH_CHANNELS if c == channel.lower()),
                None,
            )
            if not self.channel:
                msg = "The WPUSH channel ({}) is not valid.".format(channel)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.channel = WPUSH_CHANNEL_DEFAULT

        self.topic_code = (
            topic_code
            if isinstance(topic_code, str) and topic_code.strip()
            else None
        )

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform WPUSH Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        payload = {
            "apikey": self.apikey,
            # title is required by WPUSH; fall back to body when empty
            "title": title if title else body,
            "content": body,
            "channel": self.channel,
        }
        if self.topic_code:
            payload["topic_code"] = self.topic_code

        self.logger.debug(
            "WPUSH POST URL: %s (cert_verify=%r)",
            self.notify_url,
            self.verify_certificate,
        )
        self.logger.debug("WPUSH Payload: %r", payload)

        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                headers=headers,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
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
                return False

            try:
                content = json.loads(r.content)
            except (AttributeError, TypeError, ValueError):
                content = {}
                self.logger.debug(
                    "Failed to parse WPUSH JSON response; body: %r",
                    (r.content or b"")[:2000],
                )

            # WPUSH success is code === 0 (not PushPlus's 200)
            api_code = content.get("code") if content else None
            if api_code != 0:
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
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending WPUSH notification."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        self.logger.info("Sent WPUSH notification.")
        return True

    @property
    def url_identifier(self):
        """Returns identifiers that make this URL unique."""
        return (self.secure_protocol, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""
        params = {}
        if self.channel != WPUSH_CHANNEL_DEFAULT:
            params["channel"] = self.channel
        if self.topic_code:
            params["topic_code"] = self.topic_code
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(
                self.apikey, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            params=NotifyWPush.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments to re-instantiate."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        if "apikey" in results["qsd"] and results["qsd"]["apikey"]:
            results["apikey"] = NotifyWPush.unquote(results["qsd"]["apikey"])
        else:
            results["apikey"] = NotifyWPush.unquote(results["host"])

        if "channel" in results["qsd"] and results["qsd"]["channel"]:
            results["channel"] = NotifyWPush.unquote(results["qsd"]["channel"])

        if "topic_code" in results["qsd"] and results["qsd"]["topic_code"]:
            results["topic_code"] = NotifyWPush.unquote(
                results["qsd"]["topic_code"]
            )
        elif "to" in results["qsd"] and results["qsd"]["to"]:
            results["topic_code"] = NotifyWPush.unquote(results["qsd"]["to"])

        return results

    @staticmethod
    def parse_native_url(url):
        """Support native WPUSH API URLs:
        https://api.wpush.cn/api/v1/send?apikey=KEY[&channel=…]
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
