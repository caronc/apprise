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

# Evolution API is a self-hosted WhatsApp integration layer.
# Project:  https://github.com/EvolutionAPI/evolution-api
# API Docs: https://doc.evolution-api.com/

# Steps:
#  1. Deploy Evolution API on your server (Docker recommended).
#  2. Create an instance via the Evolution API dashboard or API.
#  3. Connect the instance by scanning the QR code via WhatsApp.
#  4. Use the API key shown in your instance settings.

# URL syntax (HTTP):
#   evolution://apikey@host/instance/5511999999999
#   evolution://apikey@host:port/instance/5511999999999
#   evolution://apikey@host/instance/number1/number2/...
#
# URL syntax (HTTPS):
#   evolutions://apikey@host/instance/5511999999999
#   evolutions://apikey@host:port/instance/5511999999999
#
# Phone numbers must be in international format without the leading '+',
# e.g. 5511999999999 for a Brazilian mobile number.

from json import dumps

import requests

from ..common import NotifyFormat, NotifyType
from ..conversion import build_backtick_run_index, find_unescaped_run
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_phone_no,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase


class NotifyEvolution(NotifyBase):
    """A wrapper for Evolution API (WhatsApp) Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Evolution API"

    # The services URL
    service_url = "https://github.com/EvolutionAPI/evolution-api"

    # The default protocol (plain HTTP)
    protocol = "evolution"

    # The default secure protocol (HTTPS)
    secure_protocol = "evolutions"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/evolution/"

    # Disable throttle rate
    request_rate_per_sec = 0

    # Evolution API / WhatsApp uses Markdown-like formatting;
    # setting this causes Apprise to convert HTML bodies to Markdown
    # before calling send().
    notify_format = NotifyFormat.MARKDOWN

    # Evolution API has no separate title field; Apprise will merge the
    # title into the body before calling send().
    title_maxlen = 0

    # Define object URL templates
    templates = (
        "{schema}://{apikey}@{host}/{instance}/{targets}",
        "{schema}://{apikey}@{host}:{port}/{instance}/{targets}",
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
            },
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "instance": {
                "name": _("Instance Name"),
                "type": "string",
                "required": True,
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
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
        },
    )

    def __init__(self, apikey, instance, targets=None, **kwargs):
        """Initialize Evolution API Object."""
        super().__init__(**kwargs)

        # API Key
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Evolution API key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Instance name
        self.instance = validate_regex(instance)
        if not self.instance:
            msg = (
                "An invalid Evolution API instance name "
                f"({instance}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse and validate recipient phone numbers
        self.phone = []
        self.invalid_targets = []

        for target in parse_phone_no(targets):
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    "Dropped invalid Evolution API phone # "
                    f"({target}) specified."
                )
                self.invalid_targets.append(target)
                continue
            # Store digits only — Evolution API expects no leading '+'
            self.phone.append(result["full"])

        if not self.phone:
            msg = "No valid Evolution API phone numbers were specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    # Adapt HTML-derived CommonMark to WhatsApp formatting.
    # Direct WhatsApp Markdown is left unchanged.
    # Syntax: https://faq.whatsapp.com/539178204879377/

    # Expose shared delimiter helpers for classmethods, tests, and subclasses.
    build_backtick_run_index = staticmethod(build_backtick_run_index)
    find_unescaped_run = staticmethod(find_unescaped_run)

    @classmethod
    def _commonmark_to_whatsapp(cls, body):
        """Adapt html_to_markdown()'s CommonMark output to WhatsApp's own
        text formatting dialect.

        Overview
        --------
        html_to_markdown() produces CommonMark.  WhatsApp uses a different
        dialect with these key differences:

          CommonMark            WhatsApp
          ----------            --------
          **bold**              *bold*
          *italic*              _italic_
          `code`                ```code```  (always triple backtick)
          [label](<url>)        label (url)  (no hyperlink syntax; WhatsApp
                                             auto-links bare URLs)
          \\*                   *  (backslash escapes dropped; WhatsApp
                                   does not support them)

        Links are rendered as "label (url)" because WhatsApp has no rich
        anchor syntax -- it auto-links URLs that appear inline.  When the
        label and the URL are the same, the label is omitted and only the
        bare URL is emitted.

        Data structures
        ---------------
        out        -- list of str fragments accumulated during the scan;
                      joined once at the end to form the result string.
                      Using a list avoids O(n^2) string concatenation.
        stack      -- list of (delimiter, open_index) pairs, innermost
                      frame last (LIFO order).  "delimiter" is "*" (bold)
                      or "_" (italic).  "open_index" is the index in `out`
                      where the opening delimiter was placed; used to drop
                      empty spans at the force-close step.
        link_stack -- list of out-indices for unmatched "[" characters that
                      may start a CommonMark link label.  When we reach the
                      matching "](<url>)", we splice in the "label (url)"
                      form and discard the buffered "[".  Stray "[" chars
                      that never match stay as plain text.
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
            # WhatsApp does not recognise backslash escaping.  We discard
            # the backslash and emit just the following literal character
            # so it appears in the output without any escape prefix.
            if ch == "\\" and i + 1 < n:
                out.append(body[i + 1])
                i += 2
                continue

            # ----------------------------------------------------------------
            # Code spans  (` ... ` or ``` ... ```)
            # ----------------------------------------------------------------
            # Locate the matching close run of the same backtick width.
            # WhatsApp only renders triple-backtick code spans, so we
            # normalise all matched code spans to "```content```" form.
            if ch == "`":
                j = i
                # Measure the run length by counting consecutive backticks.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Search the pre-built index for the next matching close run.
                close = find_unescaped_run(backtick_runs, j, run)

                if close is not None:
                    # Matched code span: emit as triple backtick regardless
                    # of the original delimiter width (single, double, etc.).
                    out.append("```" + body[j:close] + "```")
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
            # Link destination  ](<url>)  -->  label (url)
            # ----------------------------------------------------------------
            # When we see "](<" and there is an open "[" on link_stack,
            # we have a complete CommonMark link.  Convert it to WhatsApp's
            # plain "label (url)" form by scanning for the ">)" terminator,
            # decoding the URL, and splicing the result back into `out`.
            if body.startswith("](<", i) and link_stack:
                # Scan forward with escape awareness so a literal ">)" inside
                # the URL (e.g. a ">" in a query string) does not terminate
                # the scan prematurely.
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
                    # Decode CommonMark backslash escapes in the raw URL
                    # fragment (body[i+3 : close]) to get the actual URL.
                    raw_url = body[i + 3 : close]
                    url = []
                    j2 = 0
                    while j2 < len(raw_url):
                        c2 = raw_url[j2]
                        if c2 == "\\" and j2 + 1 < len(raw_url):
                            # Discard the backslash; keep only the next char.
                            url.append(raw_url[j2 + 1])
                            j2 += 2
                            continue
                        # Plain character: pass through unchanged.
                        url.append(c2)
                        j2 += 1
                    url = "".join(url)

                    # Retrieve the index of the matching "[" in out.
                    open_index = link_stack.pop()
                    # Collect the label text buffered between "[" and "]".
                    text = "".join(out[open_index + 1 :])
                    # Remove everything from "[" onward -- we will replace
                    # it with the WhatsApp-native "label (url)" form.
                    del out[open_index:]
                    # Percent-encode ")" inside the URL so WhatsApp's
                    # auto-link parser does not mistake a paren in the URL
                    # for the end of the "label (url)" wrapper parentheses.
                    safe_url = url.replace(")", "%29")
                    # Emit "label (url)" when a label exists;
                    # bare URL when no label text was present.
                    out.append(f"{text} ({safe_url})" if text else safe_url)
                    # Skip past the closing ">)" of the destination.
                    i = close + 2
                    continue

            # ----------------------------------------------------------------
            # Emphasis runs  (* or **)
            # ----------------------------------------------------------------
            # CommonMark uses "*" (italic) and "**" (bold).  WhatsApp uses
            # "_" (italic) and "*" (bold) -- the same mapping as Google Chat
            # and Telegram.  Process the run one span at a time using the
            # LIFO stack to always close the most recently opened span first.
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
                        # The top-of-stack span can be closed.  Pop it and
                        # emit the close delimiter (or drop it if empty).
                        delim, open_index = stack.pop()
                        if open_index == len(out) - 1:
                            # Span collected no content -- drop the orphan.
                            out.pop()
                        else:
                            # Emit the close delimiter for this span.
                            out.append(delim)
                        # Bold ("*") consumes 2 asterisks; italic ("_") 1.
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
                # Emit the close delimiter to produce valid WhatsApp markup.
                out.append(delim)

        return "".join(out)

    def _build_send_calls(
        self, body=None, title=None, body_format=None, **kwargs
    ):
        """Convert CommonMark to WhatsApp before splitting it into chunks."""

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

        # Merge the title before conversion; WhatsApp has no title field.
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

        # Apply the WhatsApp dialect adapter to convert CommonMark constructs
        # (backslash escapes, links, emphasis, code spans) to WhatsApp syntax.
        body = self._commonmark_to_whatsapp(body)

        # Tell the base splitter that the body is now WhatsApp Markdown so
        # that split heuristics protect link and code-span constructs.
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
        """Perform Evolution API Notification."""

        # Build the base URL
        schema = "https" if self.secure else "http"
        default_port = 443 if self.secure else 80

        base_url = "{}://{}{}".format(
            schema,
            self.host,
            (
                ""
                if not self.port or self.port == default_port
                else f":{self.port}"
            ),
        )

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "apikey": self.apikey,
        }

        has_error = False
        for number in self.phone:
            url = f"{base_url}/message/sendText/{self.instance}"
            payload = {
                "number": number,
                "text": body,
            }

            self.logger.debug(
                "Evolution API POST URL: {} (cert_verify={!r})".format(
                    url, self.verify_certificate
                )
            )
            self.logger.debug(f"Evolution API Payload: {payload!s}")

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

                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.created,
                ):
                    status_str = NotifyEvolution.http_response_code_lookup(
                        r.status_code
                    )
                    self.logger.warning(
                        "Failed to send Evolution API notification to "
                        "{}: {}{}error={}.".format(
                            number,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        f"Sent Evolution API notification to {number}."
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Evolution API "
                    f"notification to {number}."
                )
                self.logger.debug(f"Socket Exception: {e!s}")
                has_error = True
                continue

        return not has_error

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return max(1, len(self.phone))

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.apikey,
            self.host,
            self.port,
            self.instance,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        default_port = 443 if self.secure else 80

        targets = self.phone if self.phone else self.invalid_targets

        return (
            "{schema}://{apikey}@{host}{port}/{instance}/{targets}?{params}"
        ).format(
            schema=self.secure_protocol if self.secure else self.protocol,
            apikey=(
                self.pprint(self.apikey, "key", safe="")
                if privacy
                else NotifyEvolution.quote(self.apikey, safe="")
            ),
            host=self.host,
            port=(
                ""
                if not self.port or self.port == default_port
                else f":{self.port}"
            ),
            instance=NotifyEvolution.quote(self.instance, safe=""),
            targets="/".join(
                [NotifyEvolution.quote(t, safe="+") for t in targets]
            ),
            params=NotifyEvolution.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=True)
        if not results:
            return results

        # The API key is placed in the user field of the URL
        if results.get("user"):
            results["apikey"] = NotifyEvolution.unquote(results["user"])
        else:
            results["apikey"] = None

        # Path tokens: first is instance name, rest are phone numbers
        entries = NotifyEvolution.split_path(results["fullpath"])

        try:
            results["instance"] = NotifyEvolution.unquote(entries.pop(0))
        except IndexError:
            results["instance"] = None

        results["targets"] = entries

        # Also accept ?to= query param for additional targets
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyEvolution.parse_phone_no(
                results["qsd"]["to"]
            )

        return results
