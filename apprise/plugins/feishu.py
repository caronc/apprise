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

# Feishu
#   1. Visit https://open.feishu.cn

# Custom Bot Setup
#    https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
#

from json import dumps, loads

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase


class NotifyFeishu(NotifyBase):
    """A wrapper for Feishu Notifications."""

    # The default descriptive name associated with the Notification
    service_name = _("Feishu")

    # The services URL
    service_url = "https://open.feishu.cn/"

    # The default secure protocol
    secure_protocol = "feishu"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/feishu/"

    # Notification URL
    notify_url = "https://open.feishu.cn/open-apis/bot/v2/hook/{token}/"

    # Define object templates
    templates = ("{schema}://{token}",)

    # The title is not used
    title_maxlen = 0

    # Limit is documented to be 20K message sizes.  This number safely
    # allows padding around that size.
    body_maxlen = 19985

    # Feishu caps a webhook request body at 20 KB, measured in bytes while
    # our body_maxlen above counts characters; a CJK body runs into the
    # byte cap long before it runs into the character one.  Both message
    # types are trimmed against this budget.
    max_payload_bytes = 19000

    # A plain text message has no formatting at all, so Markdown is only
    # honoured once we send an interactive card instead.
    notify_format = (NotifyFormat.TEXT, NotifyFormat.MARKDOWN)

    # The title area of a card comfortably fits this much
    card_title_maxlen = 100

    # Card header colours, keyed by the notification type
    card_colors = {
        NotifyType.INFO: "blue",
        NotifyType.SUCCESS: "green",
        NotifyType.WARNING: "orange",
        NotifyType.FAILURE: "red",
    }

    # Define our tokens; these are the minimum tokens required required to
    # be passed into this function (as arguments). The syntax appends any
    # previously defined in the base package and builds onto them
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9_-]+$", "i"),
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
        },
    )

    def __init__(self, token, **kwargs):
        """Initialize Feishu Object."""
        super().__init__(**kwargs)

        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"The Feishu token specified ({token}) is invalid."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # A card carries its own title area, so let a title through when the
        # caller asked for Markdown.  Plain text keeps amalgamating the title
        # into the body (title_maxlen = 0) exactly as it always has.
        if self.resolve_format() == NotifyFormat.MARKDOWN:
            self.title_maxlen = self.card_title_maxlen

        return

    @staticmethod
    def _serialize(payload):
        """Serialize a payload exactly as it is sent on the wire.

        ``ensure_ascii`` stays off so the byte budget measured here matches
        the bytes Feishu receives; escaping every CJK character to ``\\uXXXX``
        would roughly double the request size for nothing.
        """
        return dumps(payload, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def _slice_bytes(text, budget):
        """Truncate text to at most budget UTF-8 bytes."""
        if budget <= 0:
            return ""

        return text.encode("utf-8")[:budget].decode("utf-8", "ignore")

    def card_payload(self, body, title, notify_type):
        """Build the interactive card used to render a Markdown body.

        Feishu only renders Markdown inside a card (the lark_md element); a
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
                "content": {
                    "text": body,
                },
            }
        )

    def _payload(self, body, title, notify_type, card):
        """Compose a payload that stays within Feishu's byte budget."""
        payload = self._compose(body, title, notify_type, card)

        # Feishu rejects a request body larger than 20 KB with code 9499.
        # Trim by bytes instead of characters: a CJK body reaches the byte
        # cap long before it reaches body_maxlen.
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

        # prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Our Message
        payload = self._payload(
            body, title, notify_type, body_format == NotifyFormat.MARKDOWN
        )

        self.logger.debug(
            "Feishu GET URL:"
            f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Feishu Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url.format(token=self.token),
                data=self._serialize(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            #
            # Sample Responses
            #
            # Valid:
            # {
            #   "code": 0,
            #   "data": {},
            #   "msg": "success"
            # }

            # Invalid (HTTP 200, but the payload was refused):
            # {
            #   "code": 9499,
            #   "msg": "Bad Request",
            #   "data": {}
            # }
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyFeishu.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Feishu notification: {}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            else:
                # Feishu answers a refused payload with HTTP 200 and a
                # non-zero code, so the response body needs inspecting too.
                try:
                    response = loads(r.content)

                except (TypeError, ValueError):
                    response = None

                if isinstance(response, dict) and response.get("code", 0):
                    self.logger.warning(
                        "Feishu rejected our notification: code=%s msg=%s",
                        response.get("code"),
                        response.get("msg"),
                    )
                    return False

                self.logger.info("Sent Feishu notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Feishu notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Return; we're done
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Prepare our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyFeishu.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        # parse_url already handles getting the `user` and `password` fields
        # populated.
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Allow over-ride
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["token"] = NotifyFeishu.unquote(results["qsd"]["token"])

        else:
            results["token"] = NotifyFeishu.unquote(results["host"])

        return results
