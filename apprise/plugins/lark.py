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

# Details at:
# https://open.larksuite.com/document/client-docs/bot-v3/add-bot

import json
import re

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
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
    setup_url = "https://appriseit.com/services/lark/"

    # This is the static part of the webhook URL; only the token varies.
    notify_url = "https://open.larksuite.com/open-apis/bot/v2/hook/"

    # Limit is documented to be 20K message sizes.  This number safely
    # allows padding around that size.
    body_maxlen = 19985

    # Feishu/Lark caps a webhook request body at 20 KB, measured in bytes
    # while body_maxlen above counts characters; a CJK body runs into the
    # byte cap long before it runs into the character one.
    max_payload_bytes = 19000

    # The title area of a card comfortably fits this much
    card_title_maxlen = 100

    # A plain text message has no formatting at all, so Markdown is only
    # honoured once we send an interactive card instead.
    notify_format = (NotifyFormat.TEXT, NotifyFormat.MARKDOWN)

    # Card header colours, keyed by the notification type
    card_colors = {
        NotifyType.INFO: "blue",
        NotifyType.SUCCESS: "green",
        NotifyType.WARNING: "orange",
        NotifyType.FAILURE: "red",
    }

    # The title is joined to the body in one text field, so both share
    # the same limit.
    overflow_amalgamate_title = True

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
            raise AppriseImproperlyConfigured(msg)

        self.webhook_url = f"{self.notify_url}{self.token}"

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""
        params = self.url_parameters(privacy=privacy, *args, **kwargs)
        return (
            f"{self.secure_protocol}://"
            f"{self.pprint(self.token, privacy, mode=PrivacyMode.Secret)}/"
            f"?{NotifyLark.urlencode(params)}"
        )

    @staticmethod
    def _serialize(payload):
        """Serialize a payload exactly as it is sent on the wire.

        ``ensure_ascii`` stays off so the byte budget measured here matches
        the bytes Lark receives; escaping every CJK character to ``\\uXXXX``
        would roughly double the request size for nothing.
        """
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def _slice_bytes(text, budget):
        """Truncate text to at most budget UTF-8 bytes."""
        if budget <= 0:
            return ""

        return text.encode("utf-8")[:budget].decode("utf-8", "ignore")

    def card_payload(self, body, title, notify_type):
        """Build the interactive card used to render a Markdown body.

        Lark only renders Markdown inside a card (the lark_md element); a
        plain text message would show the raw markup instead.
        """
        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": (title or self.app_desc)[
                            : self.card_title_maxlen
                        ],
                    },
                    "template": self.card_colors.get(
                        notify_type, self.card_colors[NotifyType.INFO]
                    ),
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": body},
                    },
                ],
            },
        }

    def _compose(self, body, title, notify_type, card):
        """Compose the request payload for either message type."""
        return (
            self.card_payload(body, title, notify_type)
            if card
            else {
                "msg_type": "text",
                "content": {"text": f"{title}\n{body}" if title else body},
            }
        )

    def _payload(self, body, title, notify_type, card):
        """Compose a payload that stays within Lark's byte budget."""
        payload = self._compose(body, title, notify_type, card)

        # Lark rejects a request body larger than 20 KB.  Trim by bytes
        # instead of characters: a CJK body reaches the byte cap long
        # before it reaches body_maxlen.
        while len(self._serialize(payload)) > self.max_payload_bytes:
            overflow = len(self._serialize(payload)) - self.max_payload_bytes
            body = self._slice_bytes(
                body, len(body.encode("utf-8")) - overflow - 4
            )
            if not body:
                # Nothing left to trim; stop instead of looping forever.
                return self._compose("", title, notify_type, card)

            payload = self._compose(f"{body}\u2026", title, notify_type, card)

        return payload

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        body_format=None,
        **kwargs,
    ):
        """Send our notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        payload = self._payload(
            body, title, notify_type, body_format == NotifyFormat.MARKDOWN
        )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.webhook_url,
                headers=headers,
                data=self._serialize(payload),
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            if r.status_code != requests.codes.ok:
                self.logger.warning(
                    "Lark notification failed: %d - %s",
                    r.status_code,
                    (r.content or b"")[:2000],
                )
                return False

            # Lark answers a refused payload with HTTP 200 and a non-zero
            # code, so the response body needs inspecting too.
            try:
                response = json.loads(r.content)

            except (TypeError, ValueError):
                response = None

            if isinstance(response, dict) and response.get("code", 0):
                self.logger.warning(
                    "Lark rejected our notification: code=%s msg=%s",
                    response.get("code"),
                    response.get("msg"),
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
