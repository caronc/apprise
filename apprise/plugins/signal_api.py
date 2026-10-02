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

from __future__ import annotations

from json import dumps
import logging
import re
from string import punctuation
from typing import Any, Optional

import requests

from .. import exception
from ..common import NotifyType
from ..conversion import (
    commonmark_can_close_emphasis,
    commonmark_can_open_emphasis,
    commonmark_decode_backslash_escapes,
    commonmark_emphasis_run,
    commonmark_find_backtick_run,
    commonmark_headings_to_bold,
    commonmark_index_backtick_runs,
    commonmark_match_emphasis,
    commonmark_new_scan_budget,
    commonmark_pick_emphasis_sentinel,
    commonmark_scan_angle_dest,
    commonmark_scan_autolink_dest,
    commonmark_scan_paren_dest,
)
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_phone_no, parse_bool, parse_phone_no
from ..utils.sanitize import sanitize_payload
from .base import NotifyBase, NotifyFormat

GROUP_REGEX = re.compile(
    r"^\s*((\@|\%40)?(group\.)|\@|\%40)(?P<group>[a-z0-9_=-]+)", re.I
)

# Signal markup characters that require escaping when used literally:
#   https://github.com/bbernhard/signal-cli-rest-api/blob/master/\
#       src/utils/textstyleparser.go
SIGNAL_STYLE_CHARS = "*`~|"

# A zero-width space separates literal escapes from adjacent markup.
SIGNAL_ZWSP = "\u200b"


class NotifySignalAPI(NotifyBase):
    """A wrapper for SignalAPI Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Signal API"

    # The services URL
    service_url = "https://bbernhard.github.io/signal-cli-rest-api/"

    # The default protocol
    protocol = "signal"

    # The default protocol
    secure_protocol = "signals"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/signal/"

    # Support attachments
    attachment_support = True

    # The maximum targets to include when doing batch transfers
    default_batch_size = 10

    # We don't support titles for Signal notifications
    title_maxlen = 0

    # Define object templates
    templates = (
        "{schema}://{host}/{from_phone}",
        "{schema}://{host}:{port}/{from_phone}",
        "{schema}://{user}@{host}/{from_phone}",
        "{schema}://{user}@{host}:{port}/{from_phone}",
        "{schema}://{user}:{password}@{host}/{from_phone}",
        "{schema}://{user}:{password}@{host}:{port}/{from_phone}",
        "{schema}://{host}/{from_phone}/{targets}",
        "{schema}://{host}:{port}/{from_phone}/{targets}",
        "{schema}://{user}@{host}/{from_phone}/{targets}",
        "{schema}://{user}@{host}:{port}/{from_phone}/{targets}",
        "{schema}://{user}:{password}@{host}/{from_phone}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{from_phone}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
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
            "user": {
                "name": _("Username"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "from_phone": {
                "name": _("From Phone No"),
                "type": "string",
                "required": True,
                "regex": (r"^\+?[0-9\s)(+-]+$", "i"),
                "map_to": "source",
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "target_channel": {
                "name": _("Target Group ID"),
                "type": "string",
                "prefix": "@",
                "regex": (r"^[a-z0-9_=-]+$", "i"),
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
            "from": {
                "alias_of": "from_phone",
            },
            "status": {
                "name": _("Show Status"),
                "type": "bool",
                "default": False,
            },
            "to": {
                "alias_of": "targets",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
        },
    )

    def __init__(
        self, source=None, targets=None, batch=False, status=False, **kwargs
    ):
        """Initialize SignalAPI Object."""
        super().__init__(**kwargs)

        # Prepare Batch Mode Flag
        self.batch = batch

        # Set Status type
        self.status = status

        # Parse our targets
        self.targets = []

        # Used for URL generation afterwards only
        self.invalid_targets = []

        # Manage our Source Phone
        result = is_phone_no(source)
        if not result:
            msg = (
                "An invalid Signal API Source Phone No "
                f"({source}) was provided."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        self.source = "+{}".format(result["full"])

        if targets:
            # Validate our targerts
            for target in parse_phone_no(targets):
                # Validate targets and drop bad ones:
                result = is_phone_no(target)
                if result:
                    # store valid phone number
                    self.targets.append("+{}".format(result["full"]))
                    continue

                result = GROUP_REGEX.match(target)
                if result:
                    # Just store group information
                    self.targets.append(
                        "group.{}".format(result.group("group"))
                    )
                    continue

                self.logger.warning(
                    f"Dropped invalid phone/group ({target}) specified.",
                )
                self.invalid_targets.append(target)
                continue

        else:
            # Send a message to ourselves
            self.targets.append(self.source)

        return

    def dialect_convert(
        self,
        body: str,
        body_format: Optional[NotifyFormat] = None,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        """Translate repaired CommonMark to Signal styled text."""
        if body_format != NotifyFormat.MARKDOWN:
            return body
        return self._commonmark_to_signal(body)

    @classmethod
    def _commonmark_to_signal(cls, body: str) -> str:
        """Translate CommonMark to signal-cli-rest-api styled text.

        CommonMark          Signal
        ------------------  ---------------------------
        # heading           **heading** (Signal has no headings)
        **bold**            **bold**
        *italic*            *italic*
        ~~strike~~          ~strike~
        `code`              `code`
        [label](<url>)      label (url)
        \\_                 _

        Unescaped ``||spoiler||`` is Signal's own syntax and is kept. Other
        backslash escapes are dropped unless Signal needs them to keep a
        ``*``, backtick, ``~`` or ``|`` literal.
        """
        # Signal represents headings as bold while preserving code.
        body = commonmark_headings_to_bold(body)

        # Build translated output while recording markup for later matching.
        out = []
        delimiters = []
        # Tilde runs use (length, can_open, can_close).
        tildes: list[tuple[int, bool, bool]] = []
        # Link labels are nested in stack order.
        link_stack = []

        # Scan once from left to right.
        i = 0
        n = len(body)

        # Index backticks for quick code-span matching.
        backtick_runs = commonmark_index_backtick_runs(body)
        # Use a temporary marker absent from the message.
        sentinel = commonmark_pick_emphasis_sentinel(body)
        # Mark literal backslashes with the sentinel plus a backslash.
        # Numbered delimiter placeholders need a digit after the sentinel, so
        # adjacent digits stay literal text and the marker stays small.
        backslash = f"{sentinel}\\"
        # Escape Signal markup and temporarily mark literal backslashes.
        escape = str.maketrans(
            {"\\": backslash, **{c: "\\" + c for c in SIGNAL_STYLE_CHARS}}
        )
        # Bound the total work spent scanning labeled-link destinations.
        scan_budget = commonmark_new_scan_budget(body)

        while i < n:
            ch = body[i]

            # Decode CommonMark escapes, keeping Signal's own where needed.
            if ch == "\\" and i + 1 < n and body[i + 1] in punctuation:
                out.append(body[i + 1].translate(escape))
                i += 2
                continue

            # A backslash before a line break is a CommonMark hard break.
            if ch == "\\" and i + 1 < n and body[i + 1] == "\n":
                i += 1
                continue

            # Keep any other backslash as literal text.
            if ch == "\\":
                out.append(backslash)
                i += 1
                continue

            # Signal uses a single backtick for monospace text.
            if ch == "`":
                j = i
                # Measure this backtick run.
                while j < n and body[j] == "`":
                    j += 1
                run = j - i
                # Find the next closing run of the same size.
                close = commonmark_find_backtick_run(backtick_runs, j, run)

                if close is not None:
                    content = body[j:close]
                    if run >= 3 and "\n" in content:
                        # Drop the language line of a fenced code block.
                        content = content.split("\n", 1)[1].rstrip("\n")

                    out.append("`" + content.translate(escape) + "`")
                    # Continue after the closing run.
                    i = close + run
                    continue

                # Preserve unmatched backticks as literal text.
                out.append(body[i:j].translate(escape))
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
                    cls._append_signal_link(
                        out, link_stack.pop(), body[i + 3 : close], escape
                    )
                    # Skip past the closing ">)" of the destination.
                    i = close + 2
                    continue

                # Fall through to the bare-link check.

            # Convert bare destinations without scanning their URL as markup.
            if body.startswith("](", i) and link_stack:
                close = commonmark_scan_paren_dest(
                    body, i + 1, n, budget=scan_budget
                )

                if close is not None:
                    cls._append_signal_link(
                        out, link_stack.pop(), body[i + 2 : close], escape
                    )
                    # Skip past the closing ")" of the destination.
                    i = close + 1
                    continue

                # Prevent this label from matching an unrelated link.
                link_stack.pop()

            # Retire labels that do not form a link.
            if ch == "]" and link_stack and not body.startswith("](", i):
                link_stack.pop()

            # Drop autolink brackets; Signal recognizes the remaining URL.
            if ch == "<":
                close, still_valid = commonmark_scan_autolink_dest(body, i, n)
                if close is not None:
                    out.append(body[i + 1 : close].translate(escape))
                    i = close + 1
                    continue

                if not still_valid:
                    # Keep a non-autolink "<" literal.
                    out.append(ch)
                    i += 1
                    continue

                # Keep an unfinished autolink as literal text.
                out.append(body[i:].translate(escape))
                i = n
                continue

            # Record CommonMark emphasis for Signal's ``**``/``*`` syntax.
            if ch in "*_":
                i = commonmark_emphasis_run(
                    body, i, n, delimiters, out, sentinel
                )
                continue

            # Record a possible strikethrough opener or closer.
            if ch == "~":
                j = i
                while j < n and body[j] == "~":
                    j += 1

                prev_ch = body[i - 1] if i > 0 else None
                next_ch = body[j] if j < n else None
                tildes.append(
                    (
                        j - i,
                        commonmark_can_open_emphasis(ch, prev_ch, next_ch),
                        commonmark_can_close_emphasis(ch, prev_ch, next_ch),
                    )
                )
                out.append(f"{sentinel}~{len(tildes) - 1}{sentinel}")
                i = j
                continue

            # Preserve ordinary characters (including a raw ``||``).
            out.append(ch)
            i += 1

        # Pair tilde runs with the nearest opener of the same size.
        openers: dict[int, list[int]] = {1: [], 2: []}
        # Indices of the ``~`` runs that were paired.
        matched: set[int] = set()
        for index, (length, can_open, can_close) in enumerate(tildes):
            if length > 2:
                continue

            if can_close and openers[length]:
                # Pair with the nearest opener of the same size
                opener = openers[length].pop()
                matched.update((opener, index))

                # Discard crossed openers of the other size.
                other = openers[3 - length]
                while other and other[-1] > opener:
                    other.pop()

            if index not in matched and can_open:
                openers[length].append(index)

        # Pair ``*`` and ``_`` runs using CommonMark's emphasis rules.
        commonmark_match_emphasis(delimiters)

        def _render(match: re.Match) -> str:
            # Strikethrough uses a single ``~`` on either side in Signal.
            if match.group(1):
                index = int(match.group(2))
                return "~" if index in matched else "\\~" * tildes[index][0]

            # Render closers, unmatched text, then openers in nesting order.
            descriptor = delimiters[int(match.group(2))]
            events = descriptor["events"]
            pieces = [
                "**" if is_strong else "*"
                for kind, is_strong in events
                if kind == "close"
            ]
            # Unmatched stars are literal and must be escaped for Signal.
            pieces.append(
                (descriptor["char"] * descriptor["numdelims"]).translate(
                    escape
                )
            )
            pieces.extend(
                "**" if is_strong else "*"
                for kind, is_strong in reversed(events)
                if kind == "open"
            )

            # Separate adjacent star tokens so Signal does not merge them.
            after_star = match.string.endswith("\\*", 0, match.start())
            result = []
            for piece in pieces:
                if piece and piece[0] == "*" and after_star:
                    result.append(SIGNAL_ZWSP)

                if piece:
                    result.append(piece)
                    after_star = piece[-1] == "*"

            return "".join(result)

        escaped = re.escape(sentinel)
        body = re.sub(escaped + r"(~?)(\d+)" + escaped, _render, "".join(out))

        # Separate a literal backslash from following markup.
        before_markup = re.compile(
            re.escape(backslash)
            + "(?=["
            + re.escape(SIGNAL_STYLE_CHARS)
            + "])"
        )
        return before_markup.sub(lambda _: "\\" + SIGNAL_ZWSP, body).replace(
            backslash, "\\"
        )

    @staticmethod
    def _append_signal_link(
        out: list[str], open_index: int, raw_url: str, escape: dict[int, str]
    ) -> None:
        """Replace a buffered link with Signal's ``label (url)`` form."""
        url = commonmark_decode_backslash_escapes(raw_url).translate(escape)

        # Recover the buffered label and remove its opening ``[``.
        text = "".join(out[open_index + 1 :])
        del out[open_index:]

        # Omit the label when only a bare URL is available.
        out.append(f"{text} ({url})" if text else url)

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Signal API Notification."""

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning("There were no Signal API targets to notify.")
            return False

        # error tracking (used for function return)
        has_error = False

        attachments = []
        if attach and self.attachment_support:
            for attachment in attach:
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Signal API attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                try:
                    attachments.append(attachment.base64())

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access Signal API attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                self.logger.debug(
                    "Appending Signal API attachment"
                    f" {attachment.url(privacy=True)}"
                )

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Support Styled (Markdown formatting)
        text_mode = (
            "styled"
            if self.notify_format == NotifyFormat.MARKDOWN
            else "normal"
        )

        # Format defined here:
        #   https://bbernhard.github.io/signal-cli-rest-api\
        #       /#/Messages/post_v2_send
        # Example:
        # {
        #   "base64_attachments": [
        #     "string"
        #   ],
        #   "message": "string",
        #   "number": "string",
        #   "recipients": [
        #     "string"
        #   ]
        # }
        # Prepare our payload
        payload = {
            "message": (
                "{}{}".format(
                    (
                        ""
                        if not self.status
                        else f"{self.asset.ascii(notify_type)} "
                    ),
                    body,
                ).rstrip()
            ),
            "number": self.source,
            "text_mode": text_mode,
            "recipients": [],
        }

        if attachments:
            # Store our attachments
            payload["base64_attachments"] = attachments

        # Determine Authentication
        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = "https" if self.secure else "http"

        # Construct our URL
        notify_url = f"{schema}://{self.host}"
        if isinstance(self.port, int):
            notify_url += f":{self.port}"
        notify_url += "/v2/send"

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        for index in range(0, len(self.targets), batch_size):
            # Skip a batch that already went out so a retry does
            # not deliver it to those recipients twice.
            if self.is_delivered(index):
                continue

            # Prepare our recipients
            payload["recipients"] = self.targets[index : index + batch_size]

            # Some Debug Logging
            if self.logger.isEnabledFor(logging.DEBUG):
                # Due to attachments; output can be quite heavy and io
                # intensive.
                # To accommodate this, we only show our debug payload
                # information if required.
                self.logger.debug(
                    "Signal API POST URL:"
                    f" {notify_url} (cert_verify={self.verify_certificate!r})"
                )
                log_payload = dict(payload)
                log_payload.pop("recipients", None)
                self.logger.debug(
                    "Signal API Payload: %s", sanitize_payload(log_payload)
                )
                self.logger.debug(
                    "Signal API Recipients: %s",
                    payload.get("recipients", []),
                )

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    notify_url,
                    auth=auth,
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
                    # We had a problem
                    status_str = NotifySignalAPI.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send {} Signal API notification{}: "
                        "{}{}error={}.".format(
                            len(self.targets[index : index + batch_size]),
                            (
                                f" to {self.targets[index]}"
                                if batch_size == 1
                                else "(s)"
                            ),
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        "Sent {} Signal API notification{}.".format(
                            len(self.targets[index : index + batch_size]),
                            (
                                f" to {self.targets[index]}"
                                if batch_size == 1
                                else "(s)"
                            ),
                        )
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occured sending"
                    f" {len(self.targets[index : index + batch_size])} Signal"
                    " API notification(s)."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this batch.
            self.mark_delivered(index)

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user,
            self.password,
            self.host,
            self.port,
            self.source,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "batch": "yes" if self.batch else "no",
            "status": "yes" if self.status else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ""
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=NotifySignalAPI.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )
        elif self.user:
            auth = "{user}@".format(
                user=NotifySignalAPI.quote(self.user, safe=""),
            )

        default_port = 443 if self.secure else 80

        # So we can strip out our own phone (if present); create a copy of our
        # targets
        if len(self.targets) == 1 and self.source in self.targets:
            targets = []

        elif len(self.targets) == 0:
            # invalid phone-no were specified
            targets = self.invalid_targets

        else:
            # append @ to non-phone number entries as they are groups
            # Remove group. prefix as well
            targets = [f"@{x[6:]}" if x[0] != "+" else x for x in self.targets]

        return "{schema}://{auth}{hostname}{port}/{src}/{dst}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            ),
            src=self.source,
            dst="/".join(
                [NotifySignalAPI.quote(x, safe="@+") for x in targets]
            ),
            params=NotifySignalAPI.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + (
                1 if targets % batch_size else 0
            )

        return targets

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results["targets"] = NotifySignalAPI.split_path(results["fullpath"])

        # The hostname is our authentication key
        results["apikey"] = NotifySignalAPI.unquote(results["host"])

        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifySignalAPI.unquote(results["qsd"]["from"])

        elif results["targets"]:
            # The from phone no is the first entry in the list otherwise
            results["source"] = results["targets"].pop(0)

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifySignalAPI.parse_phone_no(
                results["qsd"]["to"]
            )

        # Get Batch Mode Flag
        results["batch"] = parse_bool(results["qsd"].get("batch", False))

        # Get status switch
        results["status"] = parse_bool(results["qsd"].get("status", False))

        return results
