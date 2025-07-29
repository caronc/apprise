# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

# Details at:
# https://open.larksuite.com/document/client-docs/bot-v3/add-bot

import json
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex
from .base import NotifyBase


class NotifyLark(NotifyBase):
    """A wrapper for Lark (Feishu) Notifications via Webhook."""

    # The default descriptive name associated with the Notification
    service_name = _("Lark (Feishu)")

    service_url = "https://open.larksuite.com/"

    # The default protocol
    secure_protocol = "lark"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_lark"

    # This is the static part of the webhook URL; only the token varies.
    notify_url = "https://open.larksuite.com/open-apis/bot/v2/hook/"

    # Define object templates
    templates = ("{schema}://{token}",)

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Bot Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9-]+$", "i"),
            },
        },
    )

    def __init__(self, token, **kwargs):
        """Initialize Email Object.

        The smtp_host and secure_mode can be automatically detected depending
        on how the URL was built
        """
        super().__init__(**kwargs)

        # The token associated with the account
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"The Lark Bot Token token specified ({token}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.webhook_url = f"{self.notify_url}{self.token}"

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""
        params = self.url_parameters(privacy=privacy, *args, **kwargs)
        return (
            f"{self.secure_protocol}://"
            f"{self.pprint(self.token, privacy, mode=PrivacyMode.Secret)}/"
            f"?{NotifyLark.urlencode(params)}"
        )

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        self.throttle()

        payload = {
            "msg_type": "text",
            "content": {"text": f"{title}\n{body}" if title else body},
        }

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                self.webhook_url,
                headers=headers,
                data=json.dumps(payload),
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                self.logger.warning(
                    "Lark notification failed: %d - %s", r.status_code, r.text
                )
                return False

        except requests.RequestException as e:
            self.logger.warning(f"Lark Exception: {e}")
            return False

        self.logger.info("Lark notification sent successfully.")
        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

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

        # Set our token if found as an argument
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["token"] = NotifyLark.unquote(results["qsd"]["token"])

        else:
            # Fall back to hose (if defined here)
            results["token"] = NotifyLark.unquote(results["host"])

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://open.larksuite.com/open-apis/bot/v2/hook//WEBHOOK_TOKEN
        """
        match = re.match(
            r"^https://open\.larksuite\.com/open-apis/bot/v2/hook/([\w-]+)$",
            url,
            re.I,
        )
        if not match:
            return None

        return NotifyLark.parse_url(
            f"{NotifyLark.secure_protocol}://{match.group(1)}"
        )
