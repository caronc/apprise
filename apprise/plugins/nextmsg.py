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


# NextMsg is a one-way push notification app for iPhone and Android.
#
# To get your key:
#  1. Install the NextMsg app; no account is needed.
#  2. Open Settings -> Send keys. Copy your starter key, or tap
#     Add send key -> Copy a key to give Apprise its own revocable key.
#     Every key starts with nextmsg_live_.
#
# Your Apprise URL should be assembled as:
#     nextmsg://{key}
#     nextmsg://{key}/{channel}
#
# Each channel gets its own tab in the app.
#
# Resources:
# - https://nextmsg.app/docs
# - https://api.nextmsg.app/openapi.json

from __future__ import annotations

from json import dumps
import re
from typing import Any, Optional

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# NextMsg formats **bold**, *italic*, ~~strikethrough~~ and `code`, and
# reads a backslash in front of *, ~, ` or \ as "show this literally". Plain
# text converted to Markdown escapes more than that (CommonMark escapes all
# ASCII punctuation), and those other backslashes would show on the phone.
# Escaped pairs are matched as a whole, so an escaped backslash is never
# mistaken for the start of another escape.
NEXTMSG_ESCAPE_RE = re.compile(r"\\([!-/:-@\[-`{-~])")

# The escapes NextMsg itself understands
NEXTMSG_ESCAPES = "*~`\\"


def nextmsg_unescape(content: str) -> str:
    """Remove the Markdown escapes NextMsg would show as backslashes."""
    return NEXTMSG_ESCAPE_RE.sub(
        lambda m: m.group(0) if m.group(1) in NEXTMSG_ESCAPES else m.group(1),
        content,
    )


# Extend HTTP Error Messages
# Based on: https://api.nextmsg.app/openapi.json
NEXTMSG_HTTP_ERROR_MAP = {
    400: "Bad Request - The message or channel is not valid.",
    401: "Unauthorized - The key is invalid, rotated or revoked.",
    402: "Payment Required - The free monthly limit was reached.",
    413: "Payload Too Large - The request body is over 16 KiB.",
    429: "Too many requests were made.",
}


class NotifyNextMsg(NotifyBase):
    """A wrapper for NextMsg Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "NextMsg"

    # The services URL
    service_url = "https://nextmsg.app/"

    # The default secure protocol
    secure_protocol = "nextmsg"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/nextmsg/"

    # NextMsg send URL; the key goes in the Authorization header
    notify_url = "https://api.nextmsg.app/v1/send"

    # NextMsg shows **bold**, *italic*, ~~strikethrough~~ and `code`
    notify_format = NotifyFormat.MARKDOWN

    # Messages are at most 640 characters, title included
    body_maxlen = 640

    # The title is sent in bold on the first line of the message
    title_maxlen = 120

    # The title counts towards the body_maxlen
    overflow_amalgamate_title = True

    # Leave room for the bold markers and the line break around the title
    overflow_buffer = 5

    # Define object templates
    templates = (
        "{schema}://{apikey}",
        "{schema}://{apikey}/{channel}",
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
                "regex": (r"^nextmsg_live_[0-9a-f]{48}$", "i"),
            },
            "channel": {
                "name": _("Channel"),
                "type": "string",
                "regex": (r"^[a-z0-9_-]{1,32}$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "key": {
                "alias_of": "apikey",
            },
            "channel": {
                "alias_of": "channel",
            },
        },
    )

    def __init__(
        self,
        apikey: str,
        channel: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize NextMsg Object."""
        super().__init__(**kwargs)

        # The send key
        self.apikey = validate_regex(
            apikey.strip() if isinstance(apikey, str) else apikey,
            *self.template_tokens["apikey"]["regex"],
        )
        if not self.apikey:
            msg = f"An invalid NextMsg key ({apikey}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Keys are lowercase hex; the prefix is case sensitive on the server
        self.apikey = self.apikey.lower()

        # The channel (tab in the app); NextMsg uses "general" when unset
        self.channel = None
        if channel:
            self.channel = validate_regex(
                channel.strip().lower(),
                *self.template_tokens["channel"]["regex"],
            )
            if not self.channel:
                msg = (
                    f"An invalid NextMsg channel ({channel}) was specified; "
                    "use 1-32 characters: a-z, 0-9, - and _."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform NextMsg Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.apikey}",
        }

        # Escapes NextMsg doesn't know would show as backslashes
        body = nextmsg_unescape(body)

        # The title, when there is one, is shown in bold on the first line;
        # its own markers are escaped so they can't end the bold early
        if title:
            title = re.sub(r"([*~`\\])", r"\\\1", title)
            message = f"**{title}**\n{body}"

        else:
            message = body

        # Prepare our payload
        payload: dict[str, Any] = {
            "message": message,
        }

        if self.channel:
            payload["channel"] = self.channel

        self.logger.debug(
            "NextMsg POST URL: %s (cert_verify=%r)",
            self.notify_url,
            self.verify_certificate,
        )
        self.logger.debug("NextMsg Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            self.logger.trace("NextMsg Response: %s", r.content)

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyNextMsg.http_response_code_lookup(
                    r.status_code, NEXTMSG_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send NextMsg notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Mark our failure
                return False

            self.logger.info("Sent NextMsg notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending NextMsg notification."
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
        return (self.secure_protocol, self.apikey)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{apikey}/{channel}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            channel=(
                NotifyNextMsg.quote(self.channel, safe="")
                if self.channel
                else ""
            ),
            params=NotifyNextMsg.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early
            return results

        # Our key is the host
        results["apikey"] = NotifyNextMsg.unquote(results["host"])

        # Our channel is the first entry on our path
        entries = NotifyNextMsg.split_path(results["fullpath"])
        results["channel"] = entries[0] if entries else None

        # The 'key' makes it easier to use yaml configuration
        if "key" in results["qsd"] and results["qsd"]["key"]:
            results["apikey"] = NotifyNextMsg.unquote(results["qsd"]["key"])

        if "channel" in results["qsd"] and results["qsd"]["channel"]:
            results["channel"] = NotifyNextMsg.unquote(
                results["qsd"]["channel"]
            )

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """
        Support:
           https://api.nextmsg.app/p/{key}
           https://api.nextmsg.app/p/{key}?channel={channel}
        """

        result = re.match(
            r"^https?://api\.nextmsg\.app/p/"
            r"(?P<key>nextmsg_live_[0-9a-f]{48})/?"
            r"(?P<params>\?[^#]+)?(#.*)?$",
            url,
            re.I,
        )

        if result:
            return NotifyNextMsg.parse_url(
                "{schema}://{key}/{params}".format(
                    schema=NotifyNextMsg.secure_protocol,
                    key=result.group("key"),
                    params=result.group("params") or "",
                )
            )

        return None
