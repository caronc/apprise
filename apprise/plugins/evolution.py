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
import re

import requests

from ..common import NotifyFormat, NotifyType
from ..conversion import (
    commonmark_emphasis_run,
    commonmark_find_backtick_run,
    commonmark_index_backtick_runs,
    commonmark_new_scan_budget,
    commonmark_pick_emphasis_sentinel,
    commonmark_render_emphasis_markers,
    commonmark_scan_angle_dest,
    commonmark_scan_autolink_dest,
    commonmark_scan_paren_dest,
)
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
    @classmethod
    def _commonmark_code_spans(cls, body):
        """Return complete CommonMark code-span ranges as ``(start, end)``."""
        spans = []
        backtick_runs = commonmark_index_backtick_runs(body)
        i = 0
        n = len(body)
        while i < n:
            if body[i] == "\\" and i + 1 < n:
                i += 2
                continue
            if body[i] == "`":
                j = i
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                close = commonmark_find_backtick_run(backtick_runs, j, run)
                if close is not None:
                    spans.append((i, close + run))
                    i = close + run
                    continue
                i = j
                continue
            i += 1
        return spans

    @staticmethod
    def _append_whatsapp_link(out, open_index, raw_url):
        """Replace a buffered link with WhatsApp's ``label (url)`` form.

        CommonMark escapes are decoded and closing parentheses are protected.
        """
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

        # Recover the buffered label and remove its opening ``[``.
        text = "".join(out[open_index + 1 :])
        del out[open_index:]

        # Protect wrapper parentheses from URL content.
        safe_url = url.replace(")", "%29")

        # Omit the label when only a bare URL is available.
        out.append(f"{text} ({safe_url})" if text else safe_url)

    def dialect_convert(self, body, body_format=None, *args, **kwargs):
        """Translate repaired CommonMark to WhatsApp formatting."""
        if body_format != NotifyFormat.MARKDOWN:
            return body
        return self._commonmark_to_whatsapp(body)

    @classmethod
    def _commonmark_to_whatsapp(cls, body):
        """Translate CommonMark to WhatsApp formatting.

        CommonMark          WhatsApp
        ------------------  ---------------------------
        # heading           *heading* (WhatsApp has no heading syntax)
        **bold**            *bold*
        *italic*            _italic_
        `code`              ```code``` (triple backticks)
        [label](<url>)      label (url)
        \\*                 *

        WhatsApp auto-links bare URLs but has no custom-label link syntax.
        Backslash escapes are removed because WhatsApp does not use them.
        """
        # Convert headings to bold without changing literal code.
        code_spans = cls._commonmark_code_spans(body)

        # Both inputs are ordered, so one forward cursor avoids rescanning.
        span_idx = 0

        def _heading_to_bold(match):
            nonlocal span_idx
            start = match.start()
            # Advance past any spans that end at or before this heading.
            while (
                span_idx < len(code_spans) and code_spans[span_idx][1] <= start
            ):
                span_idx += 1
            if span_idx < len(code_spans) and code_spans[span_idx][0] <= start:
                # Inside a code span: leave the line untouched.
                return match.group(0)
            heading = match.group(1).rstrip()
            return f"**{heading}**" if heading else ""

        body = re.sub(r"(?m)^#{1,6}[ \t]+(.*)$", _heading_to_bold, body)

        # Accumulate translated characters one item at a time.
        out = []
        # Record ``*`` and ``_`` markup in order, then match it after the scan.
        delimiters = []
        # Track possible link-label openings in LIFO order.
        link_stack = []

        # Initialize the single-pass scanner.
        i = 0
        n = len(body)

        # Record backtick positions so matching code spans is quick.
        backtick_runs = commonmark_index_backtick_runs(body)
        # Pick a temporary marker that does not occur in the message.
        sentinel = commonmark_pick_emphasis_sentinel(body)
        # Share one budget across link scans to preserve long valid links while
        # bounding the total work spent on malformed destinations.
        scan_budget = commonmark_new_scan_budget(body)

        while i < n:
            ch = body[i]

            # Drop CommonMark escapes because WhatsApp does not use them.
            if ch == "\\" and i + 1 < n:
                out.append(body[i + 1])
                i += 2
                continue

            # Normalize matched CommonMark code spans to triple backticks.
            if ch == "`":
                j = i
                # Measure the run length by counting consecutive backticks.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Search the pre-built index for the next matching close run.
                close = commonmark_find_backtick_run(backtick_runs, j, run)

                if close is not None:
                    # WhatsApp uses triple backticks for monospace text.
                    # Collapse runs of three or more backticks to two so
                    # embedded content cannot close the WhatsApp span early.
                    content = re.sub(r"`{3,}", "``", body[j:close])
                    out.append("```" + content + "```")
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

            # Convert a complete CommonMark link to ``label (url)``.
            if body.startswith("](<", i) and link_stack:
                # Scan forward with escape awareness for the ">)" terminator.
                close = commonmark_scan_angle_dest(
                    body, i, n, budget=scan_budget
                )

                if close is not None:
                    raw_url = body[i + 3 : close]
                    open_index = link_stack.pop()
                    cls._append_whatsapp_link(out, open_index, raw_url)
                    # Skip past the closing ">)" of the destination.
                    i = close + 2
                    continue

                # Retire the unmatched label so later text cannot reuse it.
                link_stack.pop()

            # Convert bare destinations without scanning their URL as emphasis.
            if body.startswith("](", i) and link_stack:
                close = commonmark_scan_paren_dest(
                    body, i + 1, n, budget=scan_budget
                )

                if close is not None:
                    raw_url = body[i + 2 : close]
                    open_index = link_stack.pop()
                    cls._append_whatsapp_link(out, open_index, raw_url)
                    # Skip past the closing ")" of the destination.
                    i = close + 1
                    continue

                # Same reasoning as the angle-dest case above.
                link_stack.pop()

            # Drop autolink brackets; WhatsApp recognizes the remaining URL.
            if ch == "<":
                close, still_valid = commonmark_scan_autolink_dest(body, i, n)
                if close is not None:
                    out.append(body[i + 1 : close])
                    i = close + 1
                    continue
                if not still_valid:
                    # Not an autolink -- fall through as a literal "<".
                    out.append(ch)
                    i += 1
                    continue
                # Ignore markup characters inside an unfinished autolink.
                out.append(body[i:])
                i = n
                continue

            # Map CommonMark emphasis to WhatsApp's ``*``/``_`` syntax.
            if ch == "*":
                i = commonmark_emphasis_run(
                    body, i, n, delimiters, out, sentinel
                )
                continue

            # Preserve ordinary characters.
            out.append(ch)
            i += 1

        # Replace temporary markers with WhatsApp bold and italic markup.
        return commonmark_render_emphasis_markers(
            "".join(out), delimiters, ("*", "*"), ("_", "_"), sentinel
        )

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        body_format=None,
        body_passthrough=None,
        **kwargs,
    ):
        """Perform Evolution API Notification."""

        # The framework has already converted and resized the final body.

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
