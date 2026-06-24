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
    commonmark_escape_link_url,
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

    # Expose shared delimiter helpers for classmethods, tests, and subclasses.
    build_backtick_run_index = staticmethod(build_backtick_run_index)
    find_unescaped_run = staticmethod(find_unescaped_run)

    @classmethod
    def _commonmark_to_google_chat(cls, body):
        """Adapt html_to_markdown()'s CommonMark output to Google Chat's
        own text formatting dialect."""

        # Accumulate translated characters one item at a time.
        out = []
        # Each entry is (delimiter, index-in-out) for an open emphasis span,
        # innermost last, so we can close spans in LIFO order.
        stack = []
        # Each entry is the out-index of the opening "[" for a pending link,
        # innermost last; used to splice the label text out when we find "]".
        link_stack = []
        i = 0
        n = len(body)
        # Pre-scan all unescaped backtick run positions indexed by run length
        # so code-span open/close matching is O(log n) rather than O(n^2).
        backtick_runs = build_backtick_run_index(body)

        while i < n:
            ch = body[i]

            # CommonMark backslash escapes: translate into Chat-safe forms.
            if ch == "\\" and i + 1 < n:
                nxt = body[i + 1]
                if nxt == "<":
                    # "<" must be entity-escaped so Chat does not treat it as
                    # the start of a <url|label> anchor.
                    out.append("&lt;")
                elif nxt == ">":
                    # Symmetric: ">" closes Chat anchors and must be escaped.
                    out.append("&gt;")
                else:
                    # All other escapes: emit just the escaped character so
                    # the backslash is not passed through to the Chat renderer.
                    out.append(nxt)
                i += 2
                continue

            # Chat requires literal ampersands to be entity-escaped so they
            # are not confused with HTML entity sequences in the payload.
            if ch == "&":
                out.append("&amp;")
                i += 1
                continue

            # Code spans: locate the matching closing run of the same length
            # and entity-escape HTML controls inside the span content.
            if ch == "`":
                j = i
                # Measure the run length by counting consecutive backticks.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Search the pre-built index for the next run of the same
                # length after the opening run ends.
                close = find_unescaped_run(backtick_runs, j, run)

                if close is not None:
                    # Matched code span: entity-escape its content so Chat
                    # does not interpret HTML inside monospace runs.
                    content = body[j:close]
                    content = (
                        content.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    # Preserve the original delimiter width (1, 2, or 3+).
                    delim = body[i:j]
                    out.append(delim + content + delim)
                    # Advance past the closing run.
                    i = close + run
                    continue

                # No matching close -- not a real code span; emit the
                # backticks as literal text.
                out.append(body[i:j])
                i = j
                continue

            # CommonMark inline links look like [label](<url>).
            # Push the current out-index so we can retrieve the label text
            # once we encounter the matching "](<".
            if ch == "[":
                link_stack.append(len(out))
                out.append("[")
                i += 1
                continue

            if body.startswith("](<", i) and link_stack:
                # We are at the "](<" that closes a pending link label.
                # Scan forward with escape awareness to find ">)" which marks
                # the end of the angle-bracketed destination.
                close = None
                k = i + 3
                while k < n - 1:
                    if body[k] == "\\" and k + 1 < n:
                        # Skip escaped characters inside the destination so a
                        # literal ">)" in the URL does not falsely terminate.
                        k += 2
                        continue
                    if body[k] == ">" and body[k + 1] == ")":
                        close = k
                        break
                    k += 1

                if close is not None:
                    # Decode CommonMark escapes in the URL and re-encode
                    # characters that would break the <url|label> syntax.
                    url = commonmark_escape_link_url(body[i + 3 : close])
                    # Retrieve the label text that was buffered after "[".
                    open_index = link_stack.pop()
                    text = "".join(out[open_index + 1 :])
                    # Splice out everything from "[" onward and replace with
                    # the Chat-native anchor format.
                    del out[open_index:]
                    out.append(f"<{url}|{text}>")
                    # Skip past the closing ">)".
                    i = close + 2
                    continue

            # Emphasis: CommonMark uses * for bold (**) and italic (*).
            # Convert to Chat Markdown while preserving LIFO nesting order.
            if ch == "*":
                j = i
                # Measure how many consecutive "*" characters are here.
                while j < n and body[j] == "*":
                    j += 1
                run = j - i

                # Consume the run one span at a time.  "**" maps to Chat bold
                # (*) and "*" maps to Chat italic (_).  LIFO: close the most
                # recently opened span if this run width can satisfy it.
                while run > 0:
                    if stack and (
                        (stack[-1][0] == "*" and run >= 2)
                        or (stack[-1][0] == "_" and run >= 1)
                    ):
                        # Close the innermost open span.
                        delim, open_index = stack.pop()
                        if open_index == len(out) - 1:
                            # The span opened but collected no content --
                            # drop the empty opening delimiter too.
                            out.pop()
                        else:
                            # Emit the matching close delimiter.
                            out.append(delim)
                        # Bold consumes 2 asterisks; italic consumes 1.
                        run -= 2 if delim == "*" else 1
                    elif run >= 2:
                        # Open a new bold (*) span.
                        out.append("*")
                        stack.append(("*", len(out) - 1))
                        run -= 2
                    else:
                        # Open a new italic (_) span.
                        out.append("_")
                        stack.append(("_", len(out) - 1))
                        run -= 1

                # Advance past the entire asterisk run.
                i = j
                continue

            # All other characters pass through unchanged.
            out.append(ch)
            i += 1

        # Force-close any spans still open so each chunk of output is
        # independently valid Chat Markdown even if the input was malformed.
        while stack:
            delim, open_index = stack.pop()
            if open_index == len(out) - 1:
                # Opened but empty -- drop the dangling delimiter.
                out.pop()
            else:
                out.append(delim)

        text = "".join(out)

        # Google Chat requires four spaces per nested-list level, versus two
        # in the generated CommonMark, so double leading indentation.
        lines = text.split("\n")
        result = []
        for line in lines:
            stripped = line.lstrip(" ")
            # Count how many leading spaces the CommonMark version had.
            spaces = len(line) - len(stripped)
            # Each original space expands to two spaces (1 level -> 4 spaces).
            result.append("  " * spaces + stripped)
        return "\n".join(result)

    def _build_send_calls(
        self, body=None, title=None, body_format=None, **kwargs
    ):
        """Convert CommonMark to Chat Markdown before splitting into chunks."""

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
            # Strip leading whitespace and Markdown heading / list chars that
            # would otherwise produce a malformed "# # Title" heading.
            title_text = title.lstrip("\r\n \t\v\f#-")
            if title_text:
                # Prepend the title as a level-1 heading above the body.
                body = f"# {title_text}\n{body}" if body else f"# {title_text}"
            # Clear the title so the base class does not try to send it
            # separately as a second field.
            title = ""

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
