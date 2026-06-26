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

import re

from apprise.common import NotifyFormat

# Characters we can apply a new line to if found
PUNCTUATION_CHARS = ".!?:;"
PUNCT_SPLIT_PATTERN = re.compile(
    f"[{re.escape(PUNCTUATION_CHARS)}][ \t\r\n\x0b\x0c]+"
)

# Support HTML entities (&...;)
HTML_ENTITY_LOOKBACK = 16
HTML_ENTITY_LOOKAHEAD = 16


def html_adjust(
    text: str,
    window_start: int,
    split_at: int,
) -> int:
    """
    Adjust the split point to avoid splitting inside short HTML entities
    such as '&nbsp;'.

    If the split falls inside '&...;' within a small window around the
    boundary, move the split back to '&' so the entire entity is kept
    in the next chunk.
    """
    if split_at <= window_start or split_at > len(text):
        return split_at

    search_start = max(window_start, split_at - HTML_ENTITY_LOOKBACK)
    search_end = split_at

    amp_index = text.rfind("&", search_start, search_end)
    if amp_index == -1:
        return split_at

    forward_end = min(len(text), split_at + HTML_ENTITY_LOOKAHEAD)
    semi_index = text.find(";", amp_index, forward_end)

    if (
        semi_index != -1
        and amp_index > window_start
        and amp_index < split_at <= semi_index
    ):
        return amp_index

    return split_at


def markdown_adjust(
    text: str,
    window_start: int,
    split_at: int,
) -> int:
    """Adjust split_at to avoid cutting inside a Markdown link construct.

    Protects two construct shapes:
      - CommonMark links/images: [Text](URL) and ![Alt](URL)
      - Angle-bracket links:     <URL|label>  (Slack mrkdwn, Google Chat)

    Backward scan: from window_start to split_at, so that a long URL
    whose opening "[" or "<" sits anywhere in the current chunk window
    is still detected correctly.

    Forward scan: capped at split_at + (split_at - window_start) + 1.
    The cap is symmetric with the backward scan distance and keeps the
    total work per call O(window_size) rather than O(body_length).
    Without the cap, an adversarial body of many unterminated "[" openers
    would cause O(n^2) work as each split point scans to len(text) finding
    no ")".  Any construct whose closing delimiter lies beyond the cap is
    also so long that moving the split back to its opener would land at or
    before window_start, which smart_split() would reset anyway.

    Returns the (possibly moved-left) split position.
    """
    if split_at <= window_start or split_at > len(text):
        return split_at

    # Scan backward through the entire current chunk window so that any
    # construct opener within the window is detected regardless of distance.
    search_start = window_start

    # Cap the forward scan symmetrically with the backward window size.
    # This bounds the per-call cost to O(window_size) and still covers
    # every construct whose closing delimiter fits within one chunk-length
    # past the split point (the only ones where moving the split is useful).
    forward_end = min(
        len(text),
        split_at + (split_at - window_start) + 1,
    )

    # Protect [Text](URL) and ![Alt](URL) CommonMark link/image constructs.
    # rfind searches backward from split_at; if the split falls inside a
    # link the "[" (or "!" for images) will be found somewhere to the left.
    link_start_idx = text.rfind("[", search_start, split_at)
    if link_start_idx == -1:
        # Fallback: check for an image opener "!" immediately before "[".
        link_start_idx = text.rfind("!", search_start, split_at)

    if link_start_idx != -1:
        # The construct is only active when split_at lands inside the
        # URL / destination parentheses; verify a closing ")" lies ahead.
        link_end_idx = text.find(")", link_start_idx, forward_end)
        if link_end_idx != -1 and link_start_idx < split_at < link_end_idx:
            # Move the split back to before the opening "[" or "!".
            return link_start_idx

    # Protect <URL|label> angle-bracket constructs (Slack mrkdwn, Chat).
    # The "|" requirement distinguishes these from bare HTML tags like <br>.
    angle_start_idx = text.rfind("<", search_start, split_at)
    if angle_start_idx != -1:
        # Search for the "|" separator across the full forward scan range,
        # not just up to split_at.  This is necessary because the split
        # can land INSIDE the URL portion (between "<" and "|"), in which
        # case the pipe is ahead of split_at.  Both cases -- split in the
        # URL part and split in the label part -- reduce to the same check:
        # angle_start_idx < split_at <= angle_end_idx.
        pipe_idx = text.find("|", angle_start_idx + 1, forward_end)
        if pipe_idx != -1:
            # The construct closes at ">" after the pipe; if split_at
            # lands anywhere inside "<URL|label>" move it to before "<".
            angle_end_idx = text.find(">", pipe_idx, forward_end)
            if (
                angle_end_idx != -1
                and angle_start_idx < split_at <= angle_end_idx
            ):
                return angle_start_idx

    return split_at


def smart_split(
    text: str,
    limit: int,
    body_format: NotifyFormat,
) -> list[str]:
    """
    Split `text` into chunks of at most `limit` characters.

    Soft split priority:
      1. Last newline before `limit` (\\n or \\r)
      2. Last space or tab before `limit`
      3. Last punctuation+whitespace (.,!?:; followed by space/tab/newline)
      4. Hard split at `limit`

    `body_format` controls additional safety rules:
      - NotifyFormat.TEXT: generic splitting only
      - NotifyFormat.HTML: avoid splitting inside '&...;' entities
      - NotifyFormat.MARKDOWN: same as HTML, plus a best-effort check to
        avoid splitting inside [Text](URL) / ![Alt](URL) patterns.
    """

    if not text or limit <= 0:
        return [""]

    result: list[str] = []
    start = 0
    length = len(text)

    while start < length:  # pragma: no branch
        remaining = length - start
        if remaining <= limit:
            result.append(text[start:])
            break

        window_end = min(start + limit, length)
        #
        # Priority 1: Search for newline
        #
        last_nl_idx = max(
            text.rfind("\n", start, window_end),
            text.rfind("\r", start, window_end),
        )
        split_nl = last_nl_idx + 1 if last_nl_idx != -1 else -1

        #
        # Priority 2: Search for ending Space and/or Tab
        #
        last_space_tab_idx = max(
            text.rfind(" ", start, window_end),
            text.rfind("\t", start, window_end),
        )
        split_space_tab = (
            last_space_tab_idx + 1 if last_space_tab_idx != -1 else -1
        )

        #
        # Priority 3: Last punctuation + whitespace
        #
        split_punct = -1
        for match in PUNCT_SPLIT_PATTERN.finditer(text, start, window_end):
            split_punct = match.end()

        # Determine the best soft split point
        if split_nl != -1:
            split_at = split_nl

        elif split_space_tab != -1:
            split_at = split_space_tab

        elif split_punct != -1:
            split_at = split_punct

        else:
            #
            # Priority 4: Hard split (old way of doing things)
            #
            split_at = window_end

        #
        # Conditional Content-specific adjustments
        #
        orig_split = split_at
        if body_format is NotifyFormat.HTML:
            split_at = html_adjust(text, start, split_at)

        elif body_format is NotifyFormat.MARKDOWN:
            # Markdown may also contain HTML entities.
            split_at = html_adjust(text, start, split_at)
            split_at = markdown_adjust(text, start, split_at)

        if split_at <= start:
            split_at = orig_split

        result.append(text[start:split_at])
        start = split_at

    return result
