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

from html.entities import html5
import re
from typing import Optional

from apprise.common import NotifyFormat

# Characters we can apply a new line to if found
PUNCTUATION_CHARS = ".!?:;"
PUNCT_SPLIT_PATTERN = re.compile(
    f"[{re.escape(PUNCTUATION_CHARS)}][ \t\r\n\x0b\x0c]+"
)

# The longest an HTML entity can be, "&" and ";" included.  The longest
# named one is &CounterClockwiseContourIntegral;
HTML_ENTITY_MAXLEN = 1 + max(len(name) for name in html5)

# Characters that end a tag or open a quoted attribute value
HTML_TAG_STOP_RE = re.compile("[>\"']")


def html_tag_end(text: str, start: int, end: Optional[int] = None) -> int:
    """Return where the tag opened at ``start`` ends, or -1 if unclosed.

    A ``>`` inside a quoted attribute value does not end the tag.
    """
    # Scan no further than the requested end
    end = len(text) if end is None else end
    idx = start + 1
    while True:
        # Jump to the next closing ">" or opening quote
        match = HTML_TAG_STOP_RE.search(text, idx, end)
        if not match:
            return -1

        idx = match.start()
        if text[idx] == ">":
            # The tag ends here
            return idx

        # Skip past the matching quote so a ">" inside it is ignored
        idx = text.find(text[idx], idx + 1, end)
        if idx == -1:
            # The quoted value never closes, so neither does the tag
            return -1

        idx += 1


def html_adjust(
    text: str,
    window_start: int,
    split_at: int,
) -> int:
    """Move a split before any HTML entity it would divide.

    For example, a split inside ``&nbsp;`` moves back to ``&`` so the next
    chunk receives the complete entity.
    """
    if split_at <= window_start or split_at > len(text):
        return split_at

    search_start = max(window_start, split_at - HTML_ENTITY_MAXLEN)
    search_end = split_at

    amp_index = text.rfind("&", search_start, search_end)
    if amp_index == -1:
        return split_at

    forward_end = min(len(text), split_at + HTML_ENTITY_MAXLEN)
    semi_index = text.find(";", amp_index, forward_end)

    if (
        semi_index != -1
        and amp_index > window_start
        and amp_index < split_at <= semi_index
    ):
        return amp_index

    return split_at


def html_tag_adjust(
    text: str,
    window_start: int,
    split_at: int,
    window_end: Optional[int] = None,
) -> int:
    """Move a split out of an HTML tag.

    A tag may contain spaces, so a soft split can land inside it:
      - Move before ``<`` so the tag goes to the next chunk.
      - If the tag opens the chunk, move after ``>`` when it still fits.

    Returns the adjusted split, or the original one when neither fits.
    """
    if split_at <= window_start or split_at > len(text):
        return split_at

    # Walk the tags before the split to find one the split lands inside.
    # Scanning forward keeps a "<" or ">" inside quotes from misleading us.
    lt_index = text.find("<", window_start, split_at)
    while lt_index != -1:
        # Find where this tag ends, honouring quoted attribute values
        gt_index = html_tag_end(text, lt_index, window_end)
        if gt_index == -1 or gt_index >= split_at:
            # The split is inside this tag
            break

        # This tag ended before the split; check the next one
        lt_index = text.find("<", gt_index + 1, split_at)

    if lt_index == -1:
        # No tag opener; nothing to protect
        return split_at

    if lt_index > window_start:
        # The split is inside the tag; keep the tag whole
        return lt_index

    # The tag opens the chunk, so try to end the chunk right after it
    return gt_index + 1 if gt_index != -1 else split_at


def markdown_adjust(
    text: str,
    window_start: int,
    split_at: int,
) -> int:
    """Move a split left when it cuts a Markdown or Chat link.

    Protected forms are ``[label](url)``, ``![alt](url)``, and
    ``<url|label>``. The scan looks backward for an opener and at most one
    window forward for its closer, keeping adjustment work linear.

    Returns the original split or the construct's opening position.
    """
    if split_at <= window_start or split_at > len(text):
        return split_at

    # Search the entire current chunk for a construct opener.
    search_start = window_start

    # Cap the forward scan to one window to avoid quadratic work.
    forward_end = min(
        len(text),
        split_at + (split_at - window_start) + 1,
    )

    # Find a possible CommonMark link or image opener.
    link_start_idx = text.rfind("[", search_start, split_at)
    if link_start_idx == -1:
        # Accept ``!`` only when it begins an image label.
        bang = text.rfind("!", search_start, split_at)
        if bang != -1 and bang + 1 < len(text) and text[bang + 1] == "[":
            link_start_idx = bang

    if link_start_idx != -1:
        # Confirm that the split lands before the closing parenthesis.
        link_end_idx = text.find(")", link_start_idx, forward_end)
        if link_end_idx != -1 and link_start_idx < split_at < link_end_idx:
            # Move the split back to before the opening "[" or "!".
            return link_start_idx

    # Find a possible Slack or Chat ``<URL|label>`` opener.
    angle_start_idx = text.rfind("<", search_start, split_at)
    if angle_start_idx != -1:
        # Locate the separator even when the split falls inside the URL.
        pipe_idx = text.find("|", angle_start_idx + 1, forward_end)
        if pipe_idx != -1:
            # Move splits inside the complete construct before ``<``.
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
    """Split text within ``limit``, preferring natural boundaries.

    Priority             Boundary
    -------------------  ---------------------------------------
    1                    Newline
    2                    Space or tab
    3                    Punctuation followed by whitespace
    4                    Hard character limit

    HTML avoids splitting entities. Markdown additionally protects common
    link constructs when they can fit within a chunk.
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

            # Never cut a tag such as <a href="..."> in two
            split_at = html_tag_adjust(text, start, split_at, window_end)

        elif body_format is NotifyFormat.MARKDOWN:
            # Markdown may also contain HTML entities.
            split_at = html_adjust(text, start, split_at)
            split_at = markdown_adjust(text, start, split_at)

            # Never separate an escaping backslash from the character it
            # escapes. An odd run of backslashes right before the split
            # means the last one still needs its partner, so keep them
            # together in the next chunk.
            chunk = text[start:split_at]
            if (len(chunk) - len(chunk.rstrip("\\"))) % 2:
                split_at -= 1

        if split_at <= start:
            split_at = orig_split

        result.append(text[start:split_at])
        start = split_at

    return result
