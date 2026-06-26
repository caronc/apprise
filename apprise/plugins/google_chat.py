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
        own text formatting dialect.

        Overview
        --------
        html_to_markdown() produces CommonMark.  Google Chat uses a
        different dialect with these key differences:

          CommonMark            Google Chat
          ----------            -----------
          **bold**              *bold*
          *italic*              _italic_
          `code`                `code`  (same delimiter, but content must
                                         be HTML-entity-escaped)
          [label](<url>)        <url|label>  (Chat anchor syntax)
          & < > in text         &amp; &lt; &gt;  (Chat renders HTML)
          \\< or \\>            &lt; / &gt;  (prevent Chat anchor parsing)

        Data structures
        ---------------
        out        -- list of str fragments accumulated during the scan;
                      joined once at the end to form the result string.
                      Using a list avoids O(n^2) string concatenation.
        stack      -- list of (delimiter, open_index) pairs, innermost
                      frame last (LIFO order).  "delimiter" is "*" (bold)
                      or "_" (italic).  "open_index" is the index in `out`
                      where the opening delimiter was placed; used to drop
                      empty spans (open_index == last item) at cleanup.
        link_stack -- list of out-indices for unmatched "[" characters that
                      may start a CommonMark link label.  When we reach the
                      matching "](<url>)", we retrieve the buffered label
                      text and rewrite the construct as <url|label>.  Stray
                      "[" characters that never find a destination are kept
                      as plain text (they were already appended to `out`).
        i          -- current position in the input string body[i].
        n          -- len(body); cached to avoid repeated attribute lookup.
        backtick_runs -- pre-built index of all unescaped backtick run
                      positions indexed by run length so code-span matching
                      is O(log n) instead of O(n^2).
        """

        # Accumulate translated characters one item at a time.
        out = []
        # Open emphasis spans in LIFO order.  Each entry is
        # (delimiter, out_index) where out_index is where the opening
        # delimiter sits in `out`.
        stack = []
        # Stack of out-indices for "[" chars that may open a link label.
        # Innermost "[" is last so we match "](<url>)" LIFO.
        link_stack = []
        i = 0
        n = len(body)
        # Pre-scan all unescaped backtick run positions indexed by run
        # length so code-span open/close matching is O(log n) not O(n^2).
        backtick_runs = build_backtick_run_index(body)

        while i < n:
            ch = body[i]

            # ----------------------------------------------------------------
            # Backslash escapes
            # ----------------------------------------------------------------
            # CommonMark escapes look like "\*" or "\[".  We strip the
            # backslash and emit just the literal character, but we must
            # also HTML-entity-escape "<" and ">" because Google Chat's
            # renderer will otherwise interpret them as anchor delimiters.
            if ch == "\\" and i + 1 < n:
                nxt = body[i + 1]
                if nxt == "<":
                    # "<" starts a Chat anchor; escape it to prevent that.
                    out.append("&lt;")
                elif nxt == ">":
                    # ">" closes a Chat anchor; escape it symmetrically.
                    out.append("&gt;")
                else:
                    # All other escapes: emit just the escaped character.
                    # The backslash itself is not sent to Chat's renderer.
                    out.append(nxt)
                i += 2
                continue

            # ----------------------------------------------------------------
            # Literal ampersands
            # ----------------------------------------------------------------
            # Chat's renderer interprets "&" as the start of an HTML entity.
            # Escape every bare "&" so it renders as a literal ampersand.
            if ch == "&":
                out.append("&amp;")
                i += 1
                continue

            # ----------------------------------------------------------------
            # Code spans  (` ... ` or ``` ... ```)
            # ----------------------------------------------------------------
            # Locate the matching closing run of the same backtick width.
            # Inside code spans, HTML control characters must be entity-escaped
            # so Chat does not interpret them as markup.
            if ch == "`":
                j = i
                # Measure the run length by counting consecutive backticks.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Search the pre-built index for the matching close run.
                close = find_unescaped_run(backtick_runs, j, run)

                if close is not None:
                    # Matched code span: entity-escape HTML controls inside
                    # so Chat does not interpret them as markup.
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

                # No matching close found -- not a real code span.
                # Emit the raw backticks as literal text.
                out.append(body[i:j])
                i = j
                continue

            # ----------------------------------------------------------------
            # Link labels  [  (start of [label](<url>) construct)
            # ----------------------------------------------------------------
            # Push the current out-index so we can retrieve the label text
            # once we encounter the matching "](<url>)" further in the body.
            # If no matching destination follows, the "[" stays as plain text.
            if ch == "[":
                link_stack.append(len(out))
                out.append("[")
                i += 1
                continue

            # ----------------------------------------------------------------
            # Link destination  ](<url>)  -->  <url|label>
            # ----------------------------------------------------------------
            # When we see "](<" and there is an open "[" on link_stack,
            # we have a complete CommonMark link.  Rewrite it as a Chat
            # anchor by: scanning forward for ">)" (the destination end),
            # decoding the URL, and splicing the label+destination back
            # into `out` as "<url|label>".
            if body.startswith("](<", i) and link_stack:
                # Scan forward with escape awareness so a literal ">)" inside
                # the URL does not falsely terminate the destination scan.
                close = None
                k = i + 3
                while k < n - 1:
                    if body[k] == "\\" and k + 1 < n:
                        # Skip escape sequences -- cannot be the terminator.
                        k += 2
                        continue
                    if body[k] == ">" and body[k + 1] == ")":
                        # Found the closing ">)" of the destination.
                        close = k
                        break
                    k += 1

                if close is not None:
                    # Decode CommonMark backslash escapes in the URL and
                    # re-encode characters that would break Chat's anchor
                    # syntax (e.g. a literal "<", ">", or "|" in the URL).
                    url = commonmark_escape_link_url(body[i + 3 : close])
                    # Retrieve the index of the matching "[" in out.
                    open_index = link_stack.pop()
                    # Collect the label text that was buffered after "[".
                    text = "".join(out[open_index + 1 :])
                    # Remove everything from "[" onward from out and replace
                    # it with the Chat-native anchor in one splice.
                    del out[open_index:]
                    out.append(f"<{url}|{text}>")
                    # Skip past the closing ">)" of the destination.
                    i = close + 2
                    continue

            # ----------------------------------------------------------------
            # Emphasis runs  (* or **)
            # ----------------------------------------------------------------
            # CommonMark uses "*" (italic) and "**" (bold).  Google Chat
            # uses "_" (italic) and "*" (bold).  We process each asterisk
            # run one span at a time using the LIFO stack to match the most
            # recently opened span first, preserving correct nesting order.
            if ch == "*":
                j = i
                # Measure the full asterisk run.
                while j < n and body[j] == "*":
                    j += 1
                run = j - i

                # Consume the run width one span at a time.
                # Each iteration either closes the top-of-stack span (if the
                # remaining run width satisfies it) or opens a new span.
                while run > 0:
                    if stack and (
                        (stack[-1][0] == "*" and run >= 2)
                        or (stack[-1][0] == "_" and run >= 1)
                    ):
                        # The top-of-stack span can be closed by the
                        # current run width.  Pop and emit the close
                        # delimiter (or drop it if the span is empty).
                        delim, open_index = stack.pop()
                        if open_index == len(out) - 1:
                            # The span opened but collected no content --
                            # remove the orphan opening delimiter entirely.
                            out.pop()
                        else:
                            # Emit the close delimiter for this span.
                            out.append(delim)
                        # Bold ("*") consumes 2 asterisks; italic ("_") 1 each.
                        run -= 2 if delim == "*" else 1
                    elif run >= 2:
                        # No closeable bold on stack; open a new bold span.
                        out.append("*")
                        stack.append(("*", len(out) - 1))
                        run -= 2
                    else:
                        # run == 1: open a new italic span.
                        out.append("_")
                        stack.append(("_", len(out) - 1))
                        run -= 1

                # Advance past the entire asterisk run.
                i = j
                continue

            # ----------------------------------------------------------------
            # All other characters pass through unchanged.
            # ----------------------------------------------------------------
            out.append(ch)
            i += 1

        # --------------------------------------------------------------------
        # Force-close spans left open by malformed or truncated source.
        # --------------------------------------------------------------------
        # Pop innermost-first (LIFO) so the emitted close delimiters are in
        # the right order.  Empty spans (open_index == last item) are dropped
        # so the output contains no empty delimiter pairs.
        while stack:
            delim, open_index = stack.pop()
            if open_index == len(out) - 1:
                # Span opened but collected no content -- remove the orphan.
                out.pop()
            else:
                # Emit the close delimiter to produce valid Chat Markdown.
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
