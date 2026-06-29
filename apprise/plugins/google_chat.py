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

# For this to work correctly you need to create a webhook. You'll also
# need a GSuite account (there are free trials if you don't have one)
#
#  - Open Google Chat in your browser:
#     Link: https://chat.google.com/
#  - Go to the room to which you want to add a bot.
#  - From the room menu at the top of the page, select Manage webhooks.
#  - Provide it a name and optional avatar and click SAVE
#  - Copy the URL listed next to your new webhook in the Webhook URL column.
#  - Click outside the dialog box to close.
#
# When you've completed, you'll get a URL that looks a little like this:
#  https://chat.googleapis.com/v1/spaces/AAAAk6lGXyM/\
#       messages?key=AIzaSyDdI0hCZtE6vySjMm-WEfRq3CPzqKqqsHI&\
#       token=O7b1nyri_waOpLMSzbFILAGRzgtQofPW71fEEXKcyFk%3D
#
# Simplified, it looks like this:
#     https://chat.googleapis.com/v1/spaces/WORKSPACE/messages?\
#       key=WEBHOOK_KEY&token=WEBHOOK_TOKEN
#
# This plugin will simply work using the url of:
#     gchat://WORKSPACE/WEBHOOK_KEY/WEBHOOK_TOKEN
#
# API Documentation on Webhooks:
#    - https://developers.google.com/hangouts/chat/quickstart/\
#         incoming-bot-python
#    - https://developers.google.com/hangouts/chat/reference/rest
#
from json import dumps
import re

import requests

from ..common import NotifyFormat, NotifyType
from ..conversion import (
    build_backtick_run_index,
    commonmark_emphasis_run,
    commonmark_escape_link_url,
    commonmark_force_close_spans,
    commonmark_prepend_title,
    commonmark_scan_angle_dest,
    find_unescaped_run,
)
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase


class NotifyGoogleChat(NotifyBase):
    """A wrapper to Google Chat Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Google Chat"

    # The services URL
    service_url = "https://chat.google.com/"

    # The default secure protocol
    secure_protocol = "gchat"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/googlechat/"

    # Google Chat Webhook
    notify_url = "https://chat.googleapis.com/v1/spaces/{workspace}/messages"

    # Default Notify Format
    notify_format = NotifyFormat.MARKDOWN

    # A title can not be used for Google Chat Messages.  Setting this to zero
    # will cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4000

    # Define object templates
    templates = (
        "{schema}://{workspace}/{webhook_key}/{webhook_token}",
        "{schema}://{workspace}/{webhook_key}/{webhook_token}/{thread_key}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "workspace": {
                "name": _("Workspace"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "webhook_key": {
                "name": _("Webhook Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "webhook_token": {
                "name": _("Webhook Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "thread_key": {
                "name": _("Thread Key"),
                "type": "string",
                "private": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "workspace": {
                "alias_of": "workspace",
            },
            "key": {
                "alias_of": "webhook_key",
            },
            "token": {
                "alias_of": "webhook_token",
            },
            "thread": {
                "alias_of": "thread_key",
            },
        },
    )

    def __init__(
        self, workspace, webhook_key, webhook_token, thread_key=None, **kwargs
    ):
        """Initialize Google Chat Object."""
        super().__init__(**kwargs)

        # Workspace (associated with project)
        self.workspace = validate_regex(workspace)
        if not self.workspace:
            msg = (
                "An invalid Google Chat Workspace "
                f"({workspace}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Key (associated with project)
        self.webhook_key = validate_regex(webhook_key)
        if not self.webhook_key:
            msg = (
                "An invalid Google Chat Webhook Key "
                f"({webhook_key}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Token (associated with project)
        self.webhook_token = validate_regex(webhook_token)
        if not self.webhook_token:
            msg = (
                "An invalid Google Chat Webhook Token "
                f"({webhook_token}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        if thread_key:
            self.thread_key = validate_regex(thread_key)
            if not self.thread_key:
                msg = (
                    "An invalid Google Chat Thread Key "
                    f"({thread_key}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.thread_key = None

        return

    # Adapt HTML-derived CommonMark to Google Chat's Markdown subset.
    # Direct Google Chat Markdown is left unchanged.
    # Syntax: https://developers.google.com/workspace/chat/format-messages

    @classmethod
    def _commonmark_to_google_chat(cls, body):
        """Translate CommonMark to Google Chat formatting.

        CommonMark          Google Chat
        ------------------  -----------------
        **bold**            *bold*
        *italic*            _italic_
        `code`              `code`
        [label](<url>)      <url|label>
        &, <, >             HTML entities

        Chat uses HTML-like anchors, so text and code escape ``&``, ``<``,
        and ``>`` before delivery.
        """

        # Accumulate translated characters one item at a time.
        out = []
        # Track open emphasis as ``(delimiter, output index)`` pairs.
        stack = []
        # Track possible link-label openings in LIFO order.
        link_stack = []

        # Initialize the single-pass scanner.
        i = 0
        n = len(body)

        # Index backtick runs for efficient closing-delimiter lookups.
        backtick_runs = build_backtick_run_index(body)

        while i < n:
            ch = body[i]

            # Decode CommonMark escapes and protect Chat anchor delimiters.
            if ch == "\\" and i + 1 < n:
                nxt = body[i + 1]
                if nxt == "<":
                    # "<" starts a Chat anchor; escape it to prevent that.
                    out.append("&lt;")
                elif nxt == ">":
                    # ">" closes a Chat anchor; escape it symmetrically.
                    out.append("&gt;")
                elif nxt in ("*", "_", "~", "`"):
                    # Preserve escapes for Chat formatting characters.
                    out.append("\\" + nxt)
                else:
                    # Other escapes become their literal character.
                    out.append(nxt)
                i += 2
                continue

            # Escape ampersands before Chat interprets them as entities.
            if ch == "&":
                out.append("&amp;")
                i += 1
                continue

            # Preserve code spans while escaping HTML-sensitive content.
            if ch == "`":
                j = i
                # Measure the run length by counting consecutive backticks.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Search the pre-built index for the matching close run.
                close = find_unescaped_run(backtick_runs, j, run)

                if close is not None:
                    # Escape HTML controls inside the matched span.
                    content = body[j:close]
                    content = (
                        content.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    # Preserve the original delimiter width (1, 2, or 3+).
                    delim = body[i:j]
                    out.append(delim + content + delim)
                    # Skip past the closing backtick run.
                    i = close + run
                    continue

                # Preserve unmatched backticks as literal text.
                out.append(body[i:j])
                i = j
                continue

            # Record a possible CommonMark link-label opening.
            if ch == "[":
                link_stack.append(len(out))
                out.append("[")
                i += 1
                continue

            # Convert a complete CommonMark link to ``<url|label>``.
            if body.startswith("](<", i) and link_stack:
                # Scan forward with escape awareness for the ">)" terminator.
                close = commonmark_scan_angle_dest(body, i, n)

                if close is not None:
                    # Re-encode characters reserved by Chat anchors.
                    url = commonmark_escape_link_url(body[i + 3 : close])

                    # Recover the buffered label and replace its opening.
                    open_index = link_stack.pop()
                    text = "".join(out[open_index + 1 :])
                    del out[open_index:]
                    out.append(f"<{url}|{text}>")
                    # Skip past the closing ">)" of the destination.
                    i = close + 2
                    continue

            # Map CommonMark emphasis to Chat's ``*``/``_`` syntax.
            if ch == "*":
                i = commonmark_emphasis_run(body, i, n, stack, out)
                continue

            # Preserve ordinary characters.
            out.append(ch)
            i += 1

        # Close spans left open by malformed or truncated input.
        commonmark_force_close_spans(out, stack)

        # Join the translated fragments once before adjusting indentation.
        text = "".join(out)

        # Google Chat requires four spaces per nested-list level, versus two
        # in the generated CommonMark, so double leading indentation.
        # Track fence boundaries so code-block indentation remains unchanged.
        lines = text.split("\n")
        result = []
        # Track the opening fence width; zero means no fence is active.
        # Shorter backtick runs inside the block remain ordinary content.
        fence_run = 0
        for line in lines:
            # Count leading backticks on the stripped line.
            stripped_line = line.lstrip(" ")
            run = len(stripped_line) - len(stripped_line.lstrip("`"))

            # Assume ordinary content until a fence boundary is recognized.
            is_boundary = False
            if fence_run == 0:
                # Outside a fence, three or more backticks open one.
                if run >= 3:
                    fence_run = run
                    is_boundary = True
            else:
                # A close needs the opening width or more and no other text.
                if run >= fence_run and stripped_line[run:].strip() == "":
                    fence_run = 0
                    is_boundary = True

            if is_boundary or fence_run != 0:
                # Fence boundary lines and lines inside a fence are kept as-is.
                result.append(line)
            else:
                # Outside a code block: double leading spaces so CommonMark
                # 2-space list indentation maps to Chat's 4-space indent.
                stripped = line.lstrip(" ")
                spaces = len(line) - len(stripped)
                result.append("  " * spaces + stripped)

        return "\n".join(result)

    def _build_send_calls(
        self, body=None, title=None, body_format=None, **kwargs
    ):
        """Convert HTML-derived CommonMark before splitting for Chat.

        Direct Markdown and other source formats pass through unchanged.
        """

        # Only adapt HTML-derived Markdown; pass other formats through.
        if not (
            self.notify_format == NotifyFormat.MARKDOWN
            and body_format == NotifyFormat.HTML
        ):
            yield from super()._build_send_calls(
                body=body,
                title=title,
                body_format=body_format,
                **kwargs,
            )
            return

        # Merge the title before conversion because Chat has no title field.
        if self.title_maxlen <= 0 and title:
            body, title = commonmark_prepend_title(body, title)

        # Apply the Chat dialect adapter to convert CommonMark constructs
        # (backslash escapes, links, emphasis) into Chat-native syntax.
        body = self._commonmark_to_google_chat(body)

        # Tell the base splitter that the body is now Chat Markdown so that
        # the split heuristics protect link and code-span constructs.
        yield from super()._build_send_calls(
            body=body,
            title=title,
            body_format=NotifyFormat.MARKDOWN,
            **kwargs,
        )

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        body_format=None,
        **kwargs,
    ):
        """Perform Google Chat Notification."""

        # Our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json; charset=utf-8",
        }

        payload = {
            # Our Message
            "text": body,
        }

        # Construct Notify URL
        notify_url = self.notify_url.format(
            workspace=self.workspace,
        )

        params = {
            # Prepare our URL Parameters
            "token": self.webhook_token,
            "key": self.webhook_key,
        }

        if self.thread_key:
            params.update(
                {
                    "messageReplyOption": (
                        "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
                    ),
                }
            )

            payload.update(
                {
                    "thread": {
                        "thread_key": self.thread_key,
                    }
                }
            )

        self.logger.debug(
            "Google Chat POST URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Google Chat Parameters: {params!s}")
        self.logger.debug(f"Google Chat Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                notify_url,
                params=params,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.no_content,
            ):
                # We had a problem
                status_str = NotifyBase.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Google Chat notification: "
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Google Chat notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred postingto Google Chat."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.workspace,
            self.webhook_key,
            self.webhook_token,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Set our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{workspace}/{key}/{token}/{thread}?{params}".format(
            schema=self.secure_protocol,
            workspace=self.pprint(self.workspace, privacy, safe=""),
            key=self.pprint(self.webhook_key, privacy, safe=""),
            token=self.pprint(self.webhook_token, privacy, safe=""),
            thread=(
                ""
                if not self.thread_key
                else self.pprint(self.thread_key, privacy, safe="")
            ),
            params=NotifyGoogleChat.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object.

        Syntax:
          gchat://workspace/webhook_key/webhook_token
          gchat://workspace/webhook_key/webhook_token/thread_key
        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store our Workspace
        results["workspace"] = NotifyGoogleChat.unquote(results["host"])

        # Acquire our tokens
        tokens = NotifyGoogleChat.split_path(results["fullpath"])

        # Store our Webhook Key
        results["webhook_key"] = tokens.pop(0) if tokens else None

        # Store our Webhook Token
        results["webhook_token"] = tokens.pop(0) if tokens else None

        # Store our Thread Key
        results["thread_key"] = tokens.pop(0) if tokens else None

        # Support arguments as overrides (if specified)
        if "workspace" in results["qsd"]:
            results["workspace"] = NotifyGoogleChat.unquote(
                results["qsd"]["workspace"]
            )

        if "key" in results["qsd"]:
            results["webhook_key"] = NotifyGoogleChat.unquote(
                results["qsd"]["key"]
            )

        if "token" in results["qsd"]:
            results["webhook_token"] = NotifyGoogleChat.unquote(
                results["qsd"]["token"]
            )

        if "thread" in results["qsd"]:
            results["thread_key"] = NotifyGoogleChat.unquote(
                results["qsd"]["thread"]
            )

        elif "threadkey" in results["qsd"]:
            # Support Google Chat's Thread Key (if set)
            # keys are always made lowercase; so check above is attually
            # testing threadKey successfully as well
            results["thread_key"] = NotifyGoogleChat.unquote(
                results["qsd"]["threadkey"]
            )

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support
           https://chat.googleapis.com/v1/spaces/{workspace}/messages
                 '?key={key}&token={token}
           https://chat.googleapis.com/v1/spaces/{workspace}/messages
                 '?key={key}&token={token}&threadKey={thread}
        """

        result = re.match(
            r"^https://chat\.googleapis\.com/v1/spaces/"
            r"(?P<workspace>[A-Z0-9_-]+)/messages/*(?P<params>.+)$",
            url,
            re.I,
        )

        if result:
            return NotifyGoogleChat.parse_url(
                "{schema}://{workspace}/{params}".format(
                    schema=NotifyGoogleChat.secure_protocol,
                    workspace=result.group("workspace"),
                    params=result.group("params"),
                )
            )

        return None
