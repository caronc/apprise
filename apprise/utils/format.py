# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

# Support Markdown constructs (e.g., links, formatting)
# Longer lookback for links [text](url)
MARKDOWN_CONSTRUCT_LOOKBACK = 32


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
    """
    Adjust the split point to avoid splitting inside simple Markdown
    link / image constructs like [Text](URL) or ![Alt](URL).

    This is a best-effort heuristic and does not attempt full Markdown
    parsing. If the boundary falls between '['/'!' and the closing ')'
    of a nearby link/image, move the split back to that start.
    """
    if split_at <= window_start or split_at > len(text):
        return split_at

    search_start = max(window_start, split_at - MARKDOWN_CONSTRUCT_LOOKBACK)

    # Prefer '[' as the starting marker for links/images.
    link_start_idx = text.rfind("[", search_start, split_at)
    if link_start_idx == -1:
        # As a fallback, consider '!' as a possible start, e.g. '![Alt](...)'.
        link_start_idx = text.rfind("!", search_start, split_at)

    if link_start_idx == -1:
        return split_at

    # Look ahead for a closing ')' to bound the construct.
    forward_end = min(len(text), split_at + MARKDOWN_CONSTRUCT_LOOKBACK)
    link_end_idx = text.find(")", link_start_idx, forward_end)

    if link_end_idx != -1 and link_start_idx < split_at < link_end_idx:
        return link_start_idx

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

    while start < length:   # pragma: no branch
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
