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
        text formatting dialect."""

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

            # WhatsApp does not use backslash escaping; emit the escaped
            # character as a plain literal and discard the backslash.
            if ch == "\\" and i + 1 < n:
                out.append(body[i + 1])
                i += 2
                continue

            # WhatsApp normalises all code spans to triple backticks
            # regardless of how wide the original CommonMark delimiter was.
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
                    # Matched code span: collapse to triple-backtick form.
                    # WhatsApp does not support single or double backtick code.
                    out.append("```" + body[j:close] + "```")
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
                    # Preserve the label beside the URL using WhatsApp's plain
                    # "label (url)" convention -- WhatsApp auto-links the URL.
                    raw_url = body[i + 3 : close]
                    # Decode CommonMark backslash escapes in the URL so we
                    # work with the actual URL characters before re-encoding.
                    url = []
                    j2 = 0
                    while j2 < len(raw_url):
                        c2 = raw_url[j2]
                        if c2 == "\\" and j2 + 1 < len(raw_url):
                            # Consume the backslash; keep only the next char.
                            url.append(raw_url[j2 + 1])
                            j2 += 2
                            continue
                        url.append(c2)
                        j2 += 1
                    url = "".join(url)

                    # Retrieve the label text that was buffered after "[".
                    open_index = link_stack.pop()
                    text = "".join(out[open_index + 1 :])
                    # Splice out everything from "[" onward.
                    del out[open_index:]
                    # Percent-encode ")" so WhatsApp's auto-link parser does
                    # not mistake a closing paren in the URL for the end of
                    # the surrounding "label (url)" wrapper.
                    safe_url = url.replace(")", "%29")
                    out.append(f"{text} ({safe_url})" if text else safe_url)
                    # Skip past the closing ">)".
                    i = close + 2
                    continue

            # Emphasis: CommonMark uses * for bold (**) and italic (*).
            # Convert to WhatsApp's dialect while preserving LIFO nesting.
            if ch == "*":
                j = i
                # Measure how many consecutive "*" characters are here.
                while j < n and body[j] == "*":
                    j += 1
                run = j - i

                # Consume the run one span at a time.  "**" maps to WhatsApp
                # bold (*) and "*" maps to WhatsApp italic (_).  LIFO: close
                # the most recently opened span if this run can satisfy it.
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
        # independently valid WhatsApp markup even if the input was malformed.
        while stack:
            delim, open_index = stack.pop()
            if open_index == len(out) - 1:
                # Opened but empty -- drop the dangling delimiter.
                out.pop()
            else:
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
