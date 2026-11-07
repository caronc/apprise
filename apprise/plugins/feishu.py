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
from typing import Any, Optional

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

    # Limit is documented to be 20K message sizes.  This number safely
    # allows padding around that size.
    body_maxlen = 19985

    # A text message cannot show any formatting, so Markdown is sent as an
    # interactive card instead.  Plain text stays the default.
    notify_format = (NotifyFormat.TEXT, NotifyFormat.MARKDOWN)

    # The title is joined to the body in one text field, so both share
    # the same limit.  A card shows the title in its own header instead.
    overflow_amalgamate_title = True

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

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        body_format: Optional[NotifyFormat] = None,
        **kwargs: Any,
    ) -> bool:
        """Send our notification."""

        # prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Our Message
        payload = (
            {
                # Feishu only renders Markdown inside an interactive card
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": title or self.app_desc,
                        },
                        # The header colour follows the notification type
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
            if body_format == NotifyFormat.MARKDOWN
            else {
                "msg_type": "text",
                "content": {
                    "text": f"{title}\r\n{body}" if title else body,
                },
            }
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
                # Send UTF-8 as is; \uXXXX escapes double the size of CJK
                # text, and Feishu limits the request body size.
                data=dumps(payload, ensure_ascii=False).encode("utf-8"),
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
                    content = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # Not JSON; the HTTP status is all we have to go on
                    content = {}

                if isinstance(content, dict) and content.get("code"):
                    self.logger.warning(
                        "Feishu rejected our notification: code=%s msg=%s",
                        content.get("code"),
                        content.get("msg"),
                    )

                    # Return; we're done
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
