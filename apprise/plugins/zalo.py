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

# Zalo posts messages through a Zalo Bot:
#  1. In the Zalo app, search for the "Zalo Bot Manager" account.
#  2. Choose "Create bot" from its menu and give your bot a name
#     (it must start with "Bot", like "Bot Apprise").
#  3. Zalo sends you a message with your Bot Token; it looks like:
#     123456789:abcdefghijKLMNOPqrst
#
#  Every person or group you want to notify must first message your bot.
#  Their Chat ID is the result.message.chat.id value shown by:
#     https://bot-api.zaloplatforms.com/bot{bot_token}/getUpdates
#
#  Your Apprise URL should be assembled as:
#     zalo://{bot_token}/{chat_id}
#
#  The Zalo Bot API only accepts photos that are already hosted online
#  (it is given a link, not a file), so attachments are not supported.
#
# Resources:
# - https://bot.zapps.me/docs/
# - https://bot.zapps.me/docs/apis/sendMessage/

from __future__ import annotations

from json import dumps, loads
import re
from typing import Any, Optional

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on: https://bot.zapps.me/docs/error-code/
ZALO_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the Chat ID.",
    401: "Unauthorized - Invalid or expired Bot Token.",
    404: "The request could not be found.",
    408: "The request timed out.",
    429: "The API usage limit was exceeded.",
}

# Used to validate our Chat IDs
IS_CHAT_ID = re.compile(r"^(?P<id>[A-Z0-9._-]+)$", re.I)


class NotifyZalo(NotifyBase):
    """A wrapper for Zalo Bot Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Zalo"

    # The services URL
    service_url = "https://zalo.me/"

    # The default secure protocol
    secure_protocol = "zalo"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/zalo/"

    # Our message URL; the Bot Token follows the word "bot"
    notify_url = "https://bot-api.zaloplatforms.com/bot{token}/sendMessage"

    # Zalo renders Markdown or plain text.  Its HTML mode has no line
    # break tag, so HTML is converted to Markdown instead.
    notify_format = (NotifyFormat.MARKDOWN, NotifyFormat.TEXT)

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 2000

    # Zalo has no title field, so the title is placed in the body
    title_maxlen = 0

    # Define object URL templates
    templates = ("{schema}://{token}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Bot Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[0-9]+:[A-Z0-9_-]+$", "i"),
            },
            "target_chat_id": {
                "name": _("Target Chat ID"),
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
            "to": {
                "alias_of": "targets",
            },
            "token": {
                "alias_of": "token",
            },
        },
    )

    def __init__(
        self,
        token: str,
        targets: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Zalo Object."""
        super().__init__(**kwargs)

        # Our Bot Token
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid Zalo Bot Token ({token}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The Chat IDs we will notify
        self.targets = []

        # Anything we could not make sense of; kept for url()
        self.invalid_targets = []

        for target in parse_list(targets):
            result = IS_CHAT_ID.match(target)
            if result:
                self.targets.append(result.group("id"))
                continue

            self.logger.warning(
                "Dropped invalid Zalo Chat ID (%s) specified.", target
            )
            self.invalid_targets.append(target)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        body_format: Optional[str] = None,
        **kwargs: Any,
    ) -> bool:
        """Perform Zalo Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no Zalo Chat IDs to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json; charset=utf-8",
        }

        # Prepare our URL
        url = self.notify_url.format(token=self.token)

        # Prepare our payload
        payload = {"text": body}

        # Ask Zalo to style the text when it is Markdown
        if body_format == NotifyFormat.MARKDOWN:
            payload["parse_mode"] = "markdown"

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so a retry
            # does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Address this copy of our message
            payload["chat_id"] = target

            self.logger.debug(
                "Zalo POST URL: %s (cert_verify=%r)",
                self.notify_url.format(token="****"),
                self.verify_certificate,
            )
            self.logger.debug("Zalo Payload: %s", payload)

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

                try:
                    content = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # The response was not JSON; rely on the status code
                    content = {}

                # Zalo reports a refused message with "ok" set to false
                if r.status_code != requests.codes.ok or (
                    isinstance(content, dict) and content.get("ok") is False
                ):
                    # We had a problem
                    status_str = NotifyZalo.http_response_code_lookup(
                        r.status_code, ZALO_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Zalo notification to %s: "
                        "%s%serror=%s.",
                        target,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                self.logger.info("Sent Zalo notification to %s.", target)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Zalo "
                    "notification to %s.",
                    target,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The Bot Token alone identifies our bot
        return (self.secure_protocol, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{token}/{targets}?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=":"),
            targets="/".join(
                NotifyZalo.quote(x, safe="")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyZalo.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        # The colon inside the Bot Token looks like a port to a URL parser.
        # Swap it for a slash so the token is split across host and path.
        if isinstance(url, str):
            url = re.sub(
                r"^(?P<schema>[a-z0-9]+://)(?P<id>[0-9]+)(:|%3A)",
                r"\g<schema>\g<id>/",
                url,
                count=1,
                flags=re.I,
            )

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our Chat IDs are in the path
        entries = NotifyZalo.split_path(results["fullpath"])

        if results["qsd"].get("token"):
            # The whole Bot Token was given as ?token=, so the host and
            # path are all Chat IDs
            results["token"] = NotifyZalo.unquote(results["qsd"]["token"])
            if results["host"]:
                entries.insert(0, NotifyZalo.unquote(results["host"]))

        else:
            # Rebuild the Bot Token from the host and first path entry
            results["token"] = "{}:{}".format(
                NotifyZalo.unquote(results["host"]),
                entries.pop(0) if entries else "",
            )

        results["targets"] = entries

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyZalo.parse_list(results["qsd"]["to"])

        return results
