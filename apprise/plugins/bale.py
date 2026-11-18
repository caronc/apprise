# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, pooya220
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

import re

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from .base import NotifyBase


class NotifyBale(NotifyBase):
    """A wrapper for Bale Messenger notifications."""

    service_name = "Bale Messenger"
    service_url = "https://ble.ir/"
    protocol = "bale"
    setup_url = "https://docs.bale.ai/"
    notify_url = "https://tapi.bale.ai/bot"

    socket_connect_timeout = 15.0
    socket_read_timeout = 15.0

    templates = ("{schema}://{user}:{password}@{host}",)

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Target Chat ID"),
                "type": "string",
                "map_to": "chat_id",
                "required": True,
            },
            "user": {
                "name": _("Bot ID"),
                "type": "string",
                "map_to": "bot_id",
                "required": True,
            },
            "password": {
                "name": _("Bot Token"),
                "type": "string",
                "map_to": "token_secret",
                "private": True,
                "required": True,
            },
        },
    )

    def __init__(self, bot_id=None, token_secret=None, chat_id=None, **kwargs):
        """Initialize the Bale notification service."""
        super().__init__(**kwargs)

        self.bot_id = str(bot_id or "").strip()
        if not re.fullmatch(r"[0-9]+", self.bot_id):
            msg = "An invalid Bale bot ID was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        self.token_secret = str(token_secret or "")
        if not self.token_secret.strip():
            msg = "A Bale bot token secret was not specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        self.chat_id = str(chat_id or "").strip()
        if not re.fullmatch(r"-?[0-9]+", self.chat_id):
            msg = "An invalid Bale chat ID was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Send a text notification through the Bale Bot API."""
        message = f"{title}\n{body}" if title else body
        url = f"{self.notify_url}{self.bot_id}:{self.token_secret}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
        }

        self.logger.debug("Sending Bale notification.")
        self.throttle()

        try:
            response = requests.post(
                url,
                data=payload,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                # The bot token is in the URL path; do not forward it through
                # a redirect to another host.
                allow_redirects=False,
            )

            if not 200 <= response.status_code < 300:
                status = self.http_response_code_lookup(response.status_code)
                self.logger.warning(
                    "Failed to send Bale notification: %s%sHTTP %s.",
                    status,
                    ", " if status else "",
                    response.status_code,
                )
                return False

            result = response.json()
            if not isinstance(result, dict) or result.get("ok") is not True:
                self.logger.warning("Bale rejected the notification.")
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A connection error occurred sending the Bale notification."
            )
            self.logger.debug("Bale request failed (%s).", type(e).__name__)
            return False

        except ValueError:
            self.logger.warning("Bale returned an invalid response.")
            return False

        self.logger.info("Sent Bale notification.")
        return True

    @property
    def url_identifier(self):
        """Return fields that uniquely identify the notification service."""
        return (
            self.protocol,
            self.bot_id,
            self.token_secret,
            self.chat_id,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Return a URL that recreates this notification service."""
        params = self.url_parameters(privacy=privacy, *args, **kwargs)
        query = f"?{self.urlencode(params)}" if params else ""

        return "{schema}://{bot_id}:{token_secret}@{chat_id}{query}".format(
            schema=self.protocol,
            bot_id=self.quote(self.bot_id, safe=""),
            token_secret=self.pprint(
                self.token_secret,
                privacy,
                mode=PrivacyMode.Secret,
                safe="",
            ),
            chat_id=self.quote(self.chat_id, safe=""),
            query=query,
        )

    @staticmethod
    def parse_url(url):
        """Parse an Apprise URL into initialization parameters."""
        results = NotifyBase.parse_url(url)
        if not results:
            return results

        results["bot_id"] = NotifyBale.unquote(results.get("user") or "")
        results["token_secret"] = NotifyBale.unquote(
            results.get("password") or ""
        )
        results["chat_id"] = NotifyBale.unquote(results.get("host") or "")
        return results
