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

# Scan and repair CommonMark before plugins translate it to service dialects.

from bisect import bisect_left, bisect_right
from functools import lru_cache
import re
import unicodedata

# Keep related constants together and define dependent patterns afterward.

# CommonMark ASCII punctuation; Unicode categories cover other characters.
_CM_ASCII_PUNCTUATION = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"

# CommonMark expands tabs to the next four-column stop in block indentation.
_TAB_SIZE = 4

# Preserve list and blockquote markers from Apprise's HTML converter.
# Quote spacing applies only when followed by ">".
_QUOTE_UNIT = r"(?: {0,3}>[ \t]?)"

# Match a list marker and its leading indentation; padding is measured later.
_LIST_MARKER_CHAR_RE = re.compile(r"^ {0,3}(?:[-*+]|[0-9]{1,9}[.)])")

# Match a fence of at least three backticks or tildes and its info string.
# Backtick fence info cannot contain another backtick.
_FENCE_SHAPE_RE = re.compile(r"^(?:(`{3,})[^\n`]*|(~{3,})[^\n]*)$")

# Match a heading with up to three leading spaces and one to six "#".
# A heading marker must be followed by whitespace or the end of the line.
_ATX_HEADING_START_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")

# Match a blockquote using the shared quote-prefix pattern.
_QUOTE_START_RE = re.compile(r"^" + _QUOTE_UNIT)

# A thematic break: three or more of the same character among -, _, *,
# optionally separated by spaces or tabs, with 0-3 leading spaces.
_THEMATIC_BREAK_RE = re.compile(
    r"^ {0,3}(?:-[ \t]*){3,}$"
    r"|^ {0,3}(?:_[ \t]*){3,}$"
    r"|^ {0,3}(?:\*[ \t]*){3,}$"
)

# A setext underline turns the open paragraph above it into a heading.
_SETEXT_UNDERLINE_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")

# These HTML block tags interrupt a CommonMark paragraph.
_HTML_BLOCK_TAGS = (
    "address|article|aside|base|basefont|blockquote|body|caption|"
    "center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|"
    "figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|"
    "hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|"
    "ol|optgroup|option|p|param|pre|script|section|source|style|"
    "summary|table|tbody|td|textarea|tfoot|th|thead|title|tr|track|ul"
)

# Raw HTML blocks close at a matching raw-tag end rather than a blank line.
_HTML_RAW_TAGS = frozenset(("script", "pre", "style", "textarea"))

# Any complete raw-tag closer ends the block, even if its name differs from
# the opener. Partial closing tags do not count.
_HTML_RAW_TAG_CLOSE_RE = re.compile(
    r"</(?:" + "|".join(_HTML_RAW_TAGS) + r")>", re.IGNORECASE
)

# Named groups identify each HTML block's closing rule.
_HTML_BLOCK_START_RE = re.compile(
    r"^ {0,3}(?:"
    r"(?P<comment><!--)"
    r"|(?P<pi><\?)"
    r"|(?P<decl><![A-Za-z])"
    r"|(?P<cdata><!\[CDATA\[)"
    r"|</?(?P<tag>" + _HTML_BLOCK_TAGS + r")(?:[ \t>]|/>|$)"
    r")",
    re.IGNORECASE,
)

# Match a named HTML attribute with an optional value.
# Requiring a name after whitespace keeps malformed input quick to reject.
_HTML_ATTR = (
    r"[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?"
)

# Match other complete HTML tags that appear alone on a line.
# These tags cannot interrupt an open paragraph.
_HTML_CUSTOM_TAG_RE = re.compile(
    r"^ {0,3}(?:"
    r"<[A-Za-z][A-Za-z0-9-]*(?:" + _HTML_ATTR + r")*[ \t]*/?"
    r"|</[A-Za-z][A-Za-z0-9-]*[ \t]*"
    r")>[ \t]*$"
)


def _match_html_block_start(line):
    """Match the start of a CommonMark HTML block (types 1-6) at ``line``.

    Tag names are case-insensitive, while CDATA requires the exact
    ``"<![CDATA["`` opener.
    """
    m = _HTML_BLOCK_START_RE.match(line)
    if m and m.group("cdata") and m.group("cdata") != "<![CDATA[":
        return None
    return m


# Match a heading after its list or quote prefix has been removed.
# Optional closing hashes are handled separately.
_ATX_HEADING_SHAPE_RE = re.compile(r"#{1,6}(?:[ \t]+(?P<content>.*))?[ \t]*$")

# Match closing hashes preceded by whitespace at the end of a heading.
_ATX_CLOSING_SEQUENCE_RE = re.compile(r"[ \t]+#+[ \t]*$")

# Allow several full-body destination scans while keeping total work linear.
SCAN_BUDGET_MULTIPLIER = 4

# After the shared scan budget is spent, allow a short probe for nearby URL
# endings without permitting an unbounded search.
MIN_SCAN_ALLOWANCE = 256

# A CommonMark autolink scheme: a letter followed by 1-31 more letters,
# digits, "+", "-", or "." -- 2 to 32 characters before the ":".
_AUTOLINK_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]{1,31}:")

# Escape these CommonMark characters when they must remain literal.
_COMMONMARK_LITERAL_CHARS = "\\`*_[]()<>"


def commonmark_index_backtick_runs(text):
    """Index unescaped backtick positions by run length in one pass.

    For example, ``"a`b``c"`` produces ``{1: [1], 2: [3]}``.
    """

    # Group positions by delimiter width.
    index = {}

    # Scan each character once.
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        # Skip escaped characters so escaped backticks remain literal.
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "`":
            # Measure and record the complete backtick run.
            j = i
            while j < n and text[j] == "`":
                j += 1
            index.setdefault(j - i, []).append(i)
            i = j
            continue

        i += 1

    return index


def commonmark_find_backtick_run(index, start, run):
    """Find the next code fence of ``run`` backticks at or after ``start``.

    For example, ``commonmark_find_backtick_run({1: [0, 4]}, 1, 1)`` returns 4.
    """

    # Return early when no run has the requested width.
    positions = index.get(run)
    if not positions:
        return None
    # Find the first run at or after the requested position.
    pos = bisect_left(positions, start)
    return positions[pos] if pos < len(positions) else None


def _commonmark_code_spans(text):
    """Find complete backtick spans so other rewrites can skip code.

    Runs pair only within one paragraph because CommonMark resolves block
    boundaries before inline code. This prevents runs on opposite sides of a
    heading or blank line from hiding that block.
    """
    spans = []
    pos = 0
    n = len(text)
    while pos < n:
        line, line_end = _next_line(text, pos, n)
        if not line.strip() or _looks_like_new_block(line):
            pos = line_end + 1
            continue

        # Continue through the current paragraph only.
        para_end = line_end
        scan_pos = line_end + 1
        while scan_pos < n:
            next_line, next_line_end = _next_line(text, scan_pos, n)
            if not next_line.strip() or _looks_like_new_block(next_line):
                break
            para_end = next_line_end
            scan_pos = next_line_end + 1

        spans.extend(_commonmark_code_spans_in_range(text, pos, para_end))
        pos = scan_pos

    return spans


def _commonmark_code_spans_in_range(text, start, end):
    """Find backtick spans within ``text[start:end]``, offset to ``text``."""
    spans = []
    scoped = text[start:end]
    backtick_runs = commonmark_index_backtick_runs(scoped)
    i = 0
    m = len(scoped)
    while i < m:
        if scoped[i] == "\\" and i + 1 < m:
            i += 2
            continue
        if scoped[i] == "`":
            j = i
            while j < m and scoped[j] == "`":
                j += 1
            run = j - i
            close = commonmark_find_backtick_run(backtick_runs, j, run)
            if close is not None:
                spans.append((start + i, start + close + run))
                i = close + run
                continue
            i = j
            continue
        i += 1
    return spans


def _leading_width(line, start_col=0):
    """Measure leading spaces and tabs in rendered columns."""
    col = start_col
    for ch in line:
        if ch == " ":
            col += 1
        elif ch == "\t":
            col += _TAB_SIZE - (col % _TAB_SIZE)
        else:
            break
    return col - start_col


def _text_width(text, start_col=0):
    """Measure all of ``text`` in rendered columns, expanding tabs.

    This general helper is used wherever character and rendered widths differ.
    """
    col = start_col
    for ch in text:
        if ch == "\t":
            col += _TAB_SIZE - (col % _TAB_SIZE)
        else:
            col += 1
    return col - start_col


def _chars_for_width(line, width, start_col=0):
    """Return the leading character count needed to reach ``width`` columns.

    Character and column counts differ when indentation contains tabs.
    """
    col = start_col
    for i, ch in enumerate(line):
        if col - start_col >= width:
            return i
        if ch == " ":
            col += 1
        elif ch == "\t":
            col += _TAB_SIZE - (col % _TAB_SIZE)
        else:
            # Callers already validate the requested indentation width, so
            # reaching ordinary text is only a defensive fallback.
            return i
    return len(line)


def _strip_cr(line):
    """Remove the carriage return left when splitting CRLF input."""
    return line[:-1] if line.endswith("\r") else line


def _next_line(text, pos, end):
    """Return ``(line, line_end)`` for the line starting at ``pos``.

    A trailing carriage return is removed so CRLF and LF input behave alike.
    """
    line_end = text.find("\n", pos, end)
    line_end = line_end if line_end != -1 else end
    return _strip_cr(text[pos:line_end]), line_end


def _match_quote_prefix(line, quote_depth, pos=0, col=0):
    """Consume exactly ``quote_depth`` blockquote markers from ``line``.

    Return the ending character and column offsets, or ``None`` when markers
    are missing. A tab after ``>`` uses one marker-padding column; its
    remaining width belongs to nested content.
    """
    n = len(line)
    for _ in range(quote_depth):
        leading = 0
        while pos < n and leading < 3 and line[pos] == " ":
            pos += 1
            col += 1
            leading += 1
        if pos >= n or line[pos] != ">":
            return None
        pos += 1
        col += 1
        if pos < n and line[pos] in " \t":
            pos += 1
            col += 1
    return pos, col


def _scan_quote_depth(line, pos=0, col=0):
    """Greedily count leading blockquote markers at ``line[pos:]``.

    This direct scan has no nesting limit, and its work grows only with the
    markers present. It returns ``(depth, ending position, ending column)``.
    """
    depth = 0
    n = len(line)
    while True:
        p, c = pos, col
        leading = 0
        while p < n and leading < 3 and line[p] == " ":
            p += 1
            c += 1
            leading += 1
        if p >= n or line[p] != ">":
            break
        p += 1
        c += 1
        if p < n and line[p] in " \t":
            p += 1
            c += 1
        pos, col = p, c
        depth += 1
    return depth, pos, col


def _match_list_marker(line, pos=0, col=0):
    """Match a list marker at ``line[pos:]``, up to 3 leading columns.

    The marker must end the line or precede whitespace; ``"-x"`` is plain
    text. One to four padding columns belong to the marker, while extra
    indentation belongs to its content. Returns the content position/column.
    """
    m = _LIST_MARKER_CHAR_RE.match(line[pos:])
    if not m:
        return None
    marker_end = pos + m.end()
    marker_col = col + _text_width(m.group(0), col)

    rest = line[marker_end:]
    if not rest:
        # End of line right after the marker: a valid, blank list item.
        return marker_end, marker_col + 1
    if rest[0] not in " \t":
        # Not followed by whitespace or the end of the line -- this is
        # not a marker at all (e.g. "-x" is ordinary text).
        return None

    pad_width = _leading_width(rest, marker_col)
    after_pad = rest[_chars_for_width(rest, pad_width, marker_col) :]
    if not after_pad or pad_width > 4:
        # Count one marker-padding column, but leave the full whitespace
        # available as content indentation. Tabs cannot be partly consumed.
        return marker_end, marker_col + 1
    content_pos = marker_end + _chars_for_width(rest, pad_width, marker_col)
    return content_pos, marker_col + pad_width


def _scan_opening_prefix(line):
    """Deterministically parse one line's leading list/quote containers.

    The direct scan avoids regex backtracking and supports any quote depth.
    List-then-quote is checked before quote-then-list. The result contains the
    quote depth, quote column, list width, and ending position and column.
    """
    list_m = _match_list_marker(line)
    if list_m:
        content_pos, content_col = list_m
        marker_width = content_col
        quote_depth, end_pos, end_col = _scan_quote_depth(
            line, content_pos, content_col
        )
        return quote_depth, end_col, marker_width, end_pos, end_col

    quote_depth, q_end_pos, q_end_col = _scan_quote_depth(line)
    list_m = _match_list_marker(line, q_end_pos, q_end_col)
    if list_m:
        content_pos, content_col = list_m
        marker_width = content_col - q_end_col
        return quote_depth, q_end_col, marker_width, content_pos, content_col
    return quote_depth, q_end_col, 0, q_end_pos, q_end_col


def _match_container(line, quote_depth, list_width):
    """Match a line against its expected quote depth and list indentation.

    Both list-then-quote and quote-then-list forms are accepted. The return
    value is the consumed character count, or ``None`` when the line exits.
    """
    if not quote_depth:
        if _leading_width(line) >= list_width:
            return _chars_for_width(line, list_width)
        return None

    # List-then-quote.
    if _leading_width(line) >= list_width:
        rest_start = _chars_for_width(line, list_width)
        result = _match_quote_prefix(line, quote_depth, rest_start, list_width)
        if result is not None:
            return result[0]

    # Quote-then-list.
    result = _match_quote_prefix(line, quote_depth)
    if result is not None:
        end_pos, end_col = result
        rest = line[end_pos:]
        if _leading_width(rest, end_col) >= list_width:
            return end_pos + _chars_for_width(rest, list_width, end_col)

    return None


def _find_fence_end(
    text, search_from, quote_depth, list_width, fence_char, fence_len
):
    """Find where a fence closes, in a single forward pass.

    A valid closer stays in the same quote/list and adds no more than three
    columns. Otherwise, an unfinished nested fence ends with its container.
    """
    n = len(text)
    has_container = bool(quote_depth or list_width)
    pos = search_from
    while pos < n:
        line, line_end = _next_line(text, pos, n)

        if not line.strip():
            # Blank lines may remain in loose lists. A blockquote continues
            # only when the blank line carries every required ``>`` marker.
            if quote_depth and _match_quote_prefix(line, quote_depth) is None:
                return pos
            pos = line_end + 1
            continue

        consumed = (
            0
            if not has_container
            else _match_container(line, quote_depth, list_width)
        )
        if has_container and consumed is None:
            # The container ended before a closer, so stop the fence here.
            return pos

        # ``consumed`` is now an offset because a failed match returned above.
        rest = line[consumed:]
        extra = _leading_width(rest, consumed)
        if extra <= 3:
            candidate = rest[_chars_for_width(rest, extra, consumed) :]
            stripped = candidate.rstrip(" \t")
            if (
                len(stripped) >= fence_len
                and stripped[:fence_len] == fence_char * fence_len
                and set(stripped) == {fence_char}
            ):
                # line_end == n (no trailing newline) would
                # otherwise push this one past the end of the text.
                return min(line_end + 1, n)

        pos = line_end + 1

    return n


def _match_fence_open(rest, start_col=0):
    """Check whether ``rest`` opens a valid fence.

    Return the fence character and length when indentation and its info string
    are valid. Over-indented text and backticks in a backtick info string are
    not fence openers.
    """
    slack = _leading_width(rest, start_col)
    if slack > 3:
        return None
    candidate = rest[_chars_for_width(rest, slack, start_col) :]
    m = _FENCE_SHAPE_RE.match(candidate)
    if not m:
        return None
    fence_run = m.group(1) or m.group(2)
    return fence_run[0], len(fence_run)


def _looks_like_new_block(line, require_nonempty_list_item=False):
    """Return whether a line starts a block instead of paragraph text.

    Set ``require_nonempty_list_item`` when an empty list marker must remain
    part of the open paragraph instead of interrupting it.
    """
    list_m = _match_list_marker(line)
    has_list_marker = bool(list_m) and (
        not require_nonempty_list_item or line[list_m[0] :].strip()
    )
    return bool(
        has_list_marker
        or _match_fence_open(line)
        or _ATX_HEADING_START_RE.match(line)
        or _QUOTE_START_RE.match(line)
        or _THEMATIC_BREAK_RE.match(line)
        or _match_html_block_start(line)
    )


class _ContainerScanner:
    """Track nested list widths while scanning each message line once.

    Paragraph state preserves valid lazy continuations, and fenced code is
    skipped with the same closer rules used by the main span scanner.
    """

    def __init__(self, text):
        self._text = text
        self._pos = 0
        self._stack = []
        self._paragraph_open = False

    def width_at(self, offset):
        """Return the active list width at a non-decreasing line offset.

        Each call resumes the previous scan, keeping total work linear.
        """
        text = self._text
        pos = self._pos
        stack = self._stack
        paragraph_open = self._paragraph_open
        n = len(text)

        while pos < offset:
            line, line_end = _next_line(text, pos, n)

            if not line.strip():
                # Blank lines end lazy continuation but may remain in a list.
                paragraph_open = False
                pos = line_end + 1
                continue

            leading = _leading_width(line)
            # Keep the list levels supported by this line's indentation.
            satisfied = bisect_right(stack, leading)

            if (
                satisfied < len(stack)
                and paragraph_open
                and not _looks_like_new_block(
                    line, require_nonempty_list_item=True
                )
            ):
                # Under-indented text lazily continues the list paragraph
                # unless it starts another block.
                pos = line_end + 1
                continue

            if satisfied < len(stack):
                del stack[satisfied:]

            matched_width = stack[-1] if stack else 0
            rest = line[_chars_for_width(line, matched_width) :]

            marker_m = _match_list_marker(rest, 0, matched_width)
            if marker_m:
                # Record the indentation needed by this list's content.
                content_pos, content_col = marker_m
                stack.append(content_col)
                # A marker can open a heading or another non-paragraph
                # block; an empty item (nothing after the marker) opens
                # no paragraph at all.
                item_content = rest[content_pos:]
                paragraph_open = bool(
                    item_content
                ) and not _looks_like_new_block(item_content)
                pos = line_end + 1
                continue

            fence_open = _match_fence_open(rest, matched_width)
            if fence_open:
                # Skip fenced content using the main scanner's boundary rule.
                fence_char, fence_len = fence_open
                pos = _find_fence_end(
                    text, line_end + 1, 0, matched_width, fence_char, fence_len
                )
                paragraph_open = False
                continue

            if paragraph_open and _SETEXT_UNDERLINE_RE.match(rest):
                # The underline turns the open paragraph into a heading.
                paragraph_open = False
            elif paragraph_open:
                # Empty list markers remain part of the open paragraph.
                paragraph_open = not _looks_like_new_block(
                    rest, require_nonempty_list_item=True
                )
            else:
                # Only ordinary, non-empty text opens a paragraph here.
                paragraph_open = bool(rest) and not _looks_like_new_block(rest)
            pos = line_end + 1

        # The queried fence may close list levels that its indentation cannot
        # continue. Commit that state for the next lookup.
        line, _ = _next_line(text, offset, n)
        leading = _leading_width(line)
        satisfied = bisect_right(stack, leading)
        if satisfied < len(stack):
            del stack[satisfied:]

        self._pos = pos
        self._stack = stack
        self._paragraph_open = paragraph_open
        return stack[-1] if stack else 0


def _container_drop_pos(text, search_from, quote_depth, list_width):
    """Return where a required quote/list container first stops holding.

    Blockquotes require their markers on blank lines; lists tolerate blank
    lines. Other lines must retain the full container. ``None`` means the
    container reaches the end or no container applies.
    """
    if not (quote_depth or list_width):
        return None
    n = len(text)
    pos = search_from
    while pos < n:
        line, line_end = _next_line(text, pos, n)
        if not line.strip():
            if quote_depth and _match_quote_prefix(line, quote_depth) is None:
                return pos
            pos = line_end + 1
            continue
        if _match_container(line, quote_depth, list_width) is None:
            return pos
        pos = line_end + 1
    return None


def _blank_line_end(text, search_from, quote_depth, list_width):
    """Return where a "closes at the next blank line" HTML block ends.

    Types 6 and 7 stop at the next blank line, including a line containing
    only its quote/list prefix. They also stop when their container ends.
    """
    n = len(text)
    has_container = bool(quote_depth or list_width)
    pos = search_from
    while pos < n:
        line, line_end = _next_line(text, pos, n)

        if not line.strip():
            # A genuinely blank line always ends the block outright.
            return pos

        if not has_container:
            pos = line_end + 1
            continue

        consumed = _match_container(line, quote_depth, list_width)
        if consumed is None:
            return pos
        if not line[consumed:].strip():
            # Blank once the required container prefix is removed.
            return pos
        pos = line_end + 1

    return n


def _commonmark_html_block_end(
    text, abs_rest_start, line_end, m, quote_depth, list_width
):
    """Return an HTML block's end offset given its opening match.

    ``abs_rest_start`` locates the opener after any container prefix.
    Fixed terminators are searched only inside that container. Type 6 ends at
    the next blank line, and every type ends when its container ends.
    """
    n = len(text)
    search_from = abs_rest_start + m.end()
    has_raw_tag = m.group("tag") and m.group("tag").lower() in _HTML_RAW_TAGS

    if not (
        m.group("comment")
        or m.group("pi")
        or m.group("decl")
        or m.group("cdata")
        or has_raw_tag
    ):
        # Type 6: no fixed terminator -- ends at the next blank line. No
        # need to compute the container boundary separately here, since
        # that check is already folded into _blank_line_end() itself.
        return _blank_line_end(text, line_end + 1, quote_depth, list_width)

    # Every other type has its own fixed terminator, searched only up to
    # where an enclosing quote or list container (if any) stops holding.
    container_end = _container_drop_pos(
        text, line_end + 1, quote_depth, list_width
    )
    limit = container_end if container_end is not None else n

    if m.group("comment"):
        terminator = text.find("-->", search_from, limit)
    elif m.group("pi"):
        terminator = text.find("?>", search_from, limit)
    elif m.group("decl"):
        terminator = text.find(">", search_from, limit)
    elif m.group("cdata"):
        terminator = text.find("]]>", search_from, limit)
    else:
        # Per spec, any of the four raw tags' exact closing form ends
        # the block -- not only the one that opened it -- while a
        # partial form such as "</script nope" still does not.
        close_m = _HTML_RAW_TAG_CLOSE_RE.search(text, search_from, limit)
        terminator = close_m.start() if close_m else -1

    if terminator == -1:
        # The terminator never appears -- the block runs to the container
        # boundary (or the end of the text, when there is no container).
        return limit
    # Extend through the end of the line containing the terminator.
    _, term_line_end = _next_line(text, terminator, n)
    return min(term_line_end + 1, limit) if term_line_end < n else limit


def _resolve_prefix_widths(
    text,
    start,
    quote_depth,
    quote_end_col,
    marker_width,
    slack_width,
    container_scanner,
):
    """Resolve one line's combined quote/list/slack column widths.

    Marker-less lines consult the shared scanner for active list indentation.
    ``extra`` is indentation beyond recognized containers and must not exceed
    three columns for headings or fences. The scanner is returned for reuse.
    """
    if marker_width:
        list_width = marker_width
        extra = slack_width
    elif quote_depth or not slack_width:
        list_width = 0
        extra = slack_width
    else:
        if container_scanner is None:
            container_scanner = _ContainerScanner(text)
        active_width = container_scanner.width_at(start)
        # A fence or heading may sit up to three columns past the
        # list's own required column without leaving the list.
        if active_width <= slack_width <= active_width + 3:
            list_width = active_width
            extra = slack_width - active_width
        else:
            list_width = 0
            extra = slack_width

    return quote_depth, list_width, extra, container_scanner


def _commonmark_leaf_block_spans(text):
    """Find fenced code and HTML block ranges in a single forward pass.

    The first leaf block found owns its contents, so fence-like HTML text and
    HTML-like fenced text remain literal. Type-7 HTML starts only outside an
    active paragraph. Results are ``(start, end, "fence"|"html")`` tuples.
    """
    spans = []
    pos = 0
    n = len(text)
    # Create the scanner only when the first ambiguous line needs it.
    container_scanner = None
    paragraph_open = False

    while pos < n:
        line, line_end = _next_line(text, pos, n)

        if not line.strip():
            paragraph_open = False
            pos = line_end + 1
            continue

        (
            quote_depth,
            quote_end_col,
            marker_width,
            prefix_end_pos,
            prefix_end_col,
        ) = _scan_opening_prefix(line)
        slack_width = _leading_width(line[prefix_end_pos:], prefix_end_col)

        (
            quote_depth,
            list_width,
            extra_slack,
            container_scanner,
        ) = _resolve_prefix_widths(
            text,
            pos,
            quote_depth,
            quote_end_col,
            marker_width,
            slack_width,
            container_scanner,
        )

        # More than three remaining columns are indented code. If a paragraph
        # is already open, the same line lazily continues that paragraph.
        if extra_slack > 3:
            pos = line_end + 1
            continue

        slack_end_pos = prefix_end_pos + _chars_for_width(
            line[prefix_end_pos:], slack_width, prefix_end_col
        )
        rest = line[slack_end_pos:]
        rest_col = prefix_end_col + slack_width

        fence_open = _match_fence_open(rest, rest_col)
        if fence_open:
            fence_char, fence_len = fence_open
            start = pos
            # Find the closer or the boundary of an unfinished nested fence.
            end = _find_fence_end(
                text,
                line_end + 1,
                quote_depth,
                list_width,
                fence_char,
                fence_len,
            )
            spans.append((start, end, "fence"))
            paragraph_open = False
            pos = end
            continue

        html_m = _match_html_block_start(rest)
        if html_m:
            start = pos
            end = _commonmark_html_block_end(
                text,
                pos + slack_end_pos,
                line_end,
                html_m,
                quote_depth,
                list_width,
            )
            spans.append((start, end, "html"))
            paragraph_open = False
            pos = end
            continue

        if not paragraph_open and _HTML_CUSTOM_TAG_RE.match(rest):
            # Type 7 closes at the next blank line, the same as type 6 --
            # and cannot outlive its own quote/list container either.
            start = pos
            end = _blank_line_end(text, line_end + 1, quote_depth, list_width)
            spans.append((start, end, "html"))
            paragraph_open = False
            pos = end
            continue

        if paragraph_open and _SETEXT_UNDERLINE_RE.match(rest):
            # The underline turns the open paragraph into a heading.
            paragraph_open = False
        elif paragraph_open:
            # The list marker was removed from ``rest``; a non-empty marker
            # or another block start interrupts the open paragraph.
            has_nonempty_marker = bool(marker_width) and bool(rest.strip())
            paragraph_open = not (
                has_nonempty_marker or _looks_like_new_block(rest)
            )
        else:
            # Ordinary non-empty text starts a paragraph. A bare list or
            # quote marker does not.
            paragraph_open = bool(rest) and not _looks_like_new_block(rest)
        pos = line_end + 1

    return spans


def _commonmark_fenced_code_spans(text):
    """Find backtick and tilde fenced code blocks as ``(start, end)`` offsets.

    A thin filter over ``_commonmark_leaf_block_spans()`` -- see that
    function for why fences and HTML blocks must be resolved together in
    one pass rather than independently.
    """
    return [
        (start, end)
        for start, end, kind in _commonmark_leaf_block_spans(text)
        if kind == "fence"
    ]


def _commonmark_html_block_spans(text):
    """Find CommonMark HTML block ranges as ``(start, end)`` offsets.

    This filters types 1-7 from the shared fence and HTML scan.
    """
    return [
        (start, end)
        for start, end, kind in _commonmark_leaf_block_spans(text)
        if kind == "html"
    ]


def commonmark_headings_to_bold(body):
    """Convert ATX headings to bold while leaving code regions unchanged.

    For example, ``"# Alert"`` becomes ``"**Alert**"``. Code and HTML remain
    unchanged, while list and quote prefixes are preserved.
    """
    # Find fenced code and HTML blocks together to avoid a duplicate scan.
    protected = sorted(
        _commonmark_code_spans(body)
        + [
            (start, end)
            for start, end, _ in _commonmark_leaf_block_spans(body)
        ]
    )
    # Both inputs are ordered, so one forward cursor avoids rescanning.
    span_idx = 0
    # Create the scanner only when the first ambiguous heading needs it.
    container_scanner = None

    out = []
    pos = 0
    n = len(body)
    while pos < n:
        line_end = body.find("\n", pos)
        line_end = line_end if line_end != -1 else n
        raw_line = body[pos:line_end]
        line = _strip_cr(raw_line)

        # Skip past any protected region that ends at or before this line.
        while span_idx < len(protected) and protected[span_idx][1] <= pos:
            span_idx += 1
        in_protected = (
            span_idx < len(protected) and protected[span_idx][0] <= pos
        )

        replacement = None
        if not in_protected:
            (
                quote_depth,
                quote_end_col,
                marker_width,
                prefix_end_pos,
                prefix_end_col,
            ) = _scan_opening_prefix(line)
            slack_width = _leading_width(line[prefix_end_pos:], prefix_end_col)
            (
                _,
                _,
                extra_slack,
                container_scanner,
            ) = _resolve_prefix_widths(
                body,
                pos,
                quote_depth,
                quote_end_col,
                marker_width,
                slack_width,
                container_scanner,
            )
            # More than three columns after a list or quote is indented
            # code, not a heading.
            if extra_slack <= 3:
                slack_end_pos = prefix_end_pos + _chars_for_width(
                    line[prefix_end_pos:], slack_width, prefix_end_col
                )
                heading_m = _ATX_HEADING_SHAPE_RE.match(line[slack_end_pos:])
                if heading_m:
                    heading = heading_m.group("content") or ""
                    # Strip a trailing closing sequence like " ##" before
                    # trimming ordinary whitespace, so "## Alert ##"
                    # becomes "Alert", not "Alert ##".
                    heading = _ATX_CLOSING_SEQUENCE_RE.sub("", heading).strip()
                    prefix = line[:slack_end_pos]
                    replacement = (
                        f"{prefix}**{heading}**" if heading else prefix
                    )

        # A trailing "\r" (if any) is not restored on a converted heading,
        # matching CommonMark's own line-ending-agnostic ATX heading rule.
        out.append(replacement if replacement is not None else raw_line)
        if line_end < n:
            out.append("\n")
        pos = line_end + 1

    return "".join(out)


def commonmark_decode_backslash_escapes(text):
    """Remove backslashes from escaped characters before dialect encoding.

    For example, ``r"a\\_b"`` becomes ``"a_b"`` for a URL or link label.
    Only CommonMark punctuation is unescaped, preserving paths such as
    ``r"C:\\Users"``.
    """
    out = []

    # Scan the text without allocating intermediate match objects.
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n and text[i + 1] in _CM_ASCII_PUNCTUATION:
            # Discard the backslash and keep only the escaped character.
            out.append(text[i + 1])
            i += 2
            continue
        out.append(ch)
        i += 1

    return "".join(out)


def commonmark_escape_link_url(url):
    """Prepare a CommonMark URL for a service's ``<url|label>`` syntax.

    For example, ``r"a\\|b&c"`` becomes ``"a%7Cb&amp;c"``.
    """

    # Step 1: strip CommonMark backslash escapes so we recover the raw URL
    # characters before re-applying any encoding the target dialect needs.
    url = commonmark_decode_backslash_escapes(url)

    # Step 2: re-encode the characters that the <url|label> delimiter syntax
    # would mis-parse if left bare in the URL string.
    # "&" must come first to avoid double-encoding the entities below.
    url = url.replace("&", "&amp;").replace("<", "&lt;")
    url = url.replace(">", "&gt;")
    # "|" is the separator between the URL and label inside <url|label>;
    # percent-encode it so it cannot be mistaken for the delimiter.
    return url.replace("|", "%7C")


def commonmark_new_scan_budget(body):
    """Create a shared allowance for labeled-link destination scans.

    Once spent, each later destination receives a short fixed scan.
    """
    return [len(body) * SCAN_BUDGET_MULTIPLIER]


def commonmark_scan_angle_dest(body, i, n, budget=None):
    """Locate the closing ``>`` of ``](<url>)``, ignoring escaped pairs.

    For ``"[x](<https://a>)"``, index 2 returns 14. ``budget`` limits the
    combined work across a message while still allowing nearby closing text.
    """
    # Start immediately after the opening ``](<`` sequence.
    start = i + 3
    k = start

    # After the shared budget is spent, allow a small local scan. Include room
    # for ``>)`` so a URL at the fallback length can still close.
    limit = (
        n
        if budget is None or budget[0] > 0
        else min(n, start + MIN_SCAN_ALLOWANCE + 2)
    )

    # Scan until a complete two-character terminator can no longer fit.
    while k < limit - 1:
        if body[k] == "\\" and k + 1 < n:
            # Skip escape sequences -- they cannot be the terminator.
            k += 2
            continue
        if body[k] == ">" and body[k + 1] == ")":
            if budget is not None:
                budget[0] -= k - start
            return k
        k += 1

    if budget is not None:
        budget[0] -= k - start
    return None


def commonmark_scan_paren_dest(text, i, n, budget=None):
    """Locate the closing ``)`` of a bare ``](dest)`` link destination.

    For ``"[x](a_(b))"``, index 3 returns 9. Invalid input returns ``None``.
    ``budget`` limits combined work while still allowing nearby closing text.
    """
    depth = 1
    start = i + 1
    k = start

    # After the budget is spent, leave room for a nearby closing ``)``.
    limit = (
        n
        if budget is None or budget[0] > 0
        else min(n, start + MIN_SCAN_ALLOWANCE + 1)
    )

    while k < limit:
        ch = text[k]
        if ch == "\\" and k + 1 < n:
            k += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                if budget is not None:
                    budget[0] -= k - start
                return k
        else:
            is_control = ord(ch) < 0x20 or ord(ch) == 0x7F
            if ch == "<" or is_control or _cm_is_whitespace(ch):
                if budget is not None:
                    budget[0] -= k - start
                return None
        k += 1

    if budget is not None:
        budget[0] -= k - start
    return None


def commonmark_scan_autolink_dest(text, i, n):
    """Classify a possible ``<scheme:destination>`` autolink at ``i``.

    ``"<https://a*b>"`` returns ``(12, True)``. An incomplete destination
    remains viable until a disallowed character makes the second value false.
    """
    match = _AUTOLINK_SCHEME_RE.match(text, i + 1)
    if not match:
        return None, False

    k = match.end()
    while k < n:
        ch = text[k]
        if ch == ">":
            return k, True
        # A nested "<", a control character, or whitespace rules out a
        # genuine autolink -- CommonMark allows none of these in its
        # destination.
        is_control = ord(ch) < 0x20 or ord(ch) == 0x7F
        if ch == "<" or is_control or _cm_is_whitespace(ch):
            return None, False
        k += 1

    # Ran out of text before finding a terminator or a disqualifier.
    return None, True


def commonmark_pick_emphasis_sentinel(body):
    """Return a deterministic Private Use placeholder absent from ``body``.

    For example, a body containing ``chr(0xE000)`` receives that character
    twice, keeping internal markers distinct from user text.
    """
    width = 1
    while True:
        # Use an uncommon Private Use character as the placeholder and grow
        # its width until it cannot collide with the message.
        candidate = chr(0xE000) * width
        if candidate not in body:
            return candidate
        width *= 2


def _commonmark_emphasis_marker_pattern(sentinel):
    """Match sentinel-wrapped indexes in the accompanying delimiter list."""
    escaped = re.escape(sentinel)
    return re.compile(escaped + r"(\d+)" + escaped)


def commonmark_emphasis_run(body, i, n, delimiters, out, sentinel):
    """Record the ``*`` or ``_`` run at ``i`` for later emphasis matching.

    Scanning ``"**bold**"`` at index 0 records a bold opener, appends its
    placeholder to ``out``, and returns index 2.
    """
    ch = body[i]

    # Measure the full delimiter run starting at i.
    j = i
    while j < n and body[j] == ch:
        j += 1

    prev_ch = body[i - 1] if i > 0 else None
    next_ch = body[j] if j < n else None

    delimiters.append(
        {
            "char": ch,
            "numdelims": j - i,
            "origdelims": j - i,
            "can_open": commonmark_can_open_emphasis(ch, prev_ch, next_ch),
            "can_close": commonmark_can_close_emphasis(ch, prev_ch, next_ch),
            "events": [],
        }
    )

    index = len(delimiters) - 1
    out.append(f"{sentinel}{index}{sentinel}")

    # Return the position right after the full delimiter run.
    return j


def commonmark_render_emphasis_events(events, strong_markers, regular_markers):
    """Translate one delimiter run's events into close/open target markers.

    A strong open with markers ``("<b>", "</b>")`` returns ``("", "<b>")``.
    """
    close_part = "".join(
        (strong_markers[1] if is_strong else regular_markers[1])
        for kind, is_strong in events
        if kind == "close"
    )
    # Open markers nest around content collected after them, so the
    # outermost open (the first one recorded) must render last.
    open_part = "".join(
        (strong_markers[0] if is_strong else regular_markers[0])
        for kind, is_strong in reversed(events)
        if kind == "open"
    )
    return close_part, open_part


def commonmark_render_emphasis_markers(
    text, delimiters, strong_markers, regular_markers, sentinel
):
    """Replace recorded CommonMark runs with a service's emphasis markers.

    Adapters can pass ``("<b>", "</b>")`` and ``("<i>", "</i>")`` to
    render matched strong and regular emphasis as HTML-style tags.
    """
    commonmark_match_emphasis(delimiters)

    def _substitute(match):
        descriptor = delimiters[int(match.group(1))]
        leftover = descriptor["char"] * descriptor["numdelims"]
        close_part, open_part = commonmark_render_emphasis_events(
            descriptor["events"], strong_markers, regular_markers
        )
        return close_part + leftover + open_part

    marker_re = _commonmark_emphasis_marker_pattern(sentinel)
    return marker_re.sub(_substitute, text)


def _commonmark_escape_literal(text):
    """Escape syntax characters in fragments known to be literal text."""
    return "".join(
        f"\\{ch}" if ch in _COMMONMARK_LITERAL_CHARS else ch for ch in text
    )


def _scan_angle_terminator(text, start, n):
    """Find ``>)`` or report a trailing ``>`` split from the next chunk."""
    k = start
    while k < n:
        if text[k] == "\\" and k + 1 < n:
            # Skip escape sequences -- they cannot be the terminator.
            k += 2
            continue
        if text[k] == ">":
            if k + 1 < n and text[k + 1] == ")":
                return k, False
            if k + 1 == n:
                # Unescaped ">" is the last character of this chunk.
                return None, True
        k += 1
    return None, False


# These checks depend only on their arguments, so their results are safe to
# cache. Repeated characters can then reuse earlier Unicode lookups.


@lru_cache(maxsize=8192)
def _cm_is_whitespace(ch):
    """Return whether ``ch`` is CommonMark whitespace or a boundary."""
    if ch is None:
        return True
    if ch in " \t\n\r\f\v":
        return True
    return unicodedata.category(ch) == "Zs"


@lru_cache(maxsize=8192)
def _cm_is_punctuation(ch):
    """Return whether ``ch`` is CommonMark punctuation or a symbol."""
    if ch is None:
        # Callers classify a missing boundary as whitespace first, so this
        # fallback is defensive only.
        return False
    if ch in _CM_ASCII_PUNCTUATION:
        return True
    return unicodedata.category(ch)[0] in ("P", "S")


@lru_cache(maxsize=8192)
def _cm_flanking(prev_ch, next_ch):
    """Return a delimiter run's left- and right-flanking flags."""
    left_flanking = not _cm_is_whitespace(next_ch) and (
        not _cm_is_punctuation(next_ch)
        or _cm_is_whitespace(prev_ch)
        or _cm_is_punctuation(prev_ch)
    )
    right_flanking = not _cm_is_whitespace(prev_ch) and (
        not _cm_is_punctuation(prev_ch)
        or _cm_is_whitespace(next_ch)
        or _cm_is_punctuation(next_ch)
    )
    return left_flanking, right_flanking


@lru_cache(maxsize=8192)
def commonmark_can_open_emphasis(delim_char, prev_ch, next_ch):
    """Return whether ``*`` or ``_`` can open emphasis between two characters.

    For example, ``commonmark_can_open_emphasis("*", " ", "x")`` is true.
    """
    left_flanking, right_flanking = _cm_flanking(prev_ch, next_ch)
    if not left_flanking:
        return False

    if delim_char != "_":
        return True

    # Prevent right-flanking intraword underscores from opening emphasis.
    return not right_flanking or _cm_is_punctuation(prev_ch)


@lru_cache(maxsize=8192)
def commonmark_can_close_emphasis(delim_char, prev_ch, next_ch):
    """Return whether ``*`` or ``_`` can close emphasis between two characters.

    For example, ``commonmark_can_close_emphasis("*", "x", " ")`` is true.
    """
    left_flanking, right_flanking = _cm_flanking(prev_ch, next_ch)
    if not right_flanking:
        return False

    if delim_char != "_":
        return True

    # Prevent left-flanking intraword underscores from closing emphasis.
    return not left_flanking or _cm_is_punctuation(next_ch)


def commonmark_scan_delimiter_run(
    text, i, boundary_prev_ch=None, boundary_next_ch=None
):
    """Return a ``*``/``_`` run's end and the characters surrounding it.

    ``commonmark_scan_delimiter_run("**word", 0)`` returns ``(2, None, "w")``;
    boundary arguments supply neighbors outside the provided slice.
    """
    ch = text[i]
    n = len(text)
    j = i
    while j < n and text[j] == ch:
        j += 1
    prev_ch = text[i - 1] if i > 0 else boundary_prev_ch
    next_ch = text[j] if j < n else boundary_next_ch
    return j, prev_ch, next_ch


def commonmark_lookahead_closer_widths(
    next_chunk, boundary_prev_ch=None, boundary_next_ch=None
):
    """Find usable emphasis closers in the next bounded message slice.

    ``commonmark_lookahead_closer_widths("tail** end")`` returns ``{"*": 2}``.
    Markers inside code or links are ignored because they are literal text.
    """
    if not next_chunk:
        return {}

    # Scan once for all pending openers.
    widths = {}
    i = 0
    n = len(next_chunk)
    # Index backticks so ``*`` and ``_`` inside code are not treated as markup.
    backtick_runs = commonmark_index_backtick_runs(next_chunk)
    while i < n:
        ch = next_chunk[i]
        # Skip escape pairs -- an escaped delimiter can never close a span.
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "`":
            j = i
            while j < n and next_chunk[j] == ch:
                j += 1
            run = j - i
            close = commonmark_find_backtick_run(backtick_runs, j, run)
            if close is not None:
                # Complete code span -- its contents are not delimiters.
                i = close + run
                continue
            # Ignore the rest because it is still part of the unfinished code.
            break
        # Both destination forms below start with "]", so check that
        # cheap single-character condition first instead of paying for
        # a startswith() call at every position regardless of ch.
        if ch == "]" and next_chunk.startswith("](<", i):
            close = commonmark_scan_angle_dest(next_chunk, i, n)
            if close is not None:
                # Skip this URL so markup characters inside it stay text.
                i = close + 2
                continue
            # Ignore the rest because it is still part of the unfinished URL.
            break
        if ch == "]" and next_chunk.startswith("](", i):
            close = commonmark_scan_paren_dest(next_chunk, i + 1, n)
            if close is not None:
                # Skip this URL so markup characters inside it stay text.
                i = close + 1
                continue
            # Same reasoning as an unterminated code span above.
            break
        if ch == "<":
            close, still_valid = commonmark_scan_autolink_dest(
                next_chunk, i, n
            )
            if close is not None:
                # Skip this autolink; its markup-like characters are text.
                i = close + 1
                continue
            if still_valid:
                # Same reasoning as an unterminated code span above.
                break
            # Not an autolink -- fall through and scan it as ordinary text.
        if ch in "*_":
            j, prev_ch, next_ch = commonmark_scan_delimiter_run(
                next_chunk,
                i,
                boundary_prev_ch=boundary_prev_ch,
                boundary_next_ch=boundary_next_ch,
            )
            run = j - i
            if commonmark_can_close_emphasis(ch, prev_ch, next_ch):
                width = min(run, 3)
                if width > widths.get(ch, 0):
                    widths[ch] = width
            i = j
            continue
        i += 1

    return widths


def commonmark_match_emphasis(delimiters):
    """Pair recorded opener/closer runs using CommonMark emphasis rules.

    For runs from ``"*text*"``, this records an open on the first run and a
    close on the second for later rendering.
    """
    total = len(delimiters)

    # Link surviving markup positions in both directions. Matching can then
    # skip removed entries instead of repeatedly walking over them.
    prev_active = list(range(-1, total - 1))
    next_active = list(range(1, total + 1))
    # Use a mutable cell because removing the first entry changes the head.
    head = [0 if total else total]

    def _unlink(index):
        # Remove one entry by linking its neighbors directly together.
        before = prev_active[index]
        after = next_active[index]
        if before == -1:
            head[0] = after
        else:
            next_active[before] = after
        if after != total:
            prev_active[after] = before

    # Remember failed searches so later closers skip known-impossible ranges.
    search_bound = {}

    closer_index = head[0]
    while closer_index < total:
        closer = delimiters[closer_index]
        if not closer["can_close"]:
            closer_index = next_active[closer_index]
            continue

        bucket = (closer["char"], closer["can_open"], closer["origdelims"] % 3)
        bound = search_bound.get(bucket, -1)

        opener_index = prev_active[closer_index]
        found = -1
        while opener_index > bound:
            opener = delimiters[opener_index]
            if opener["char"] == closer["char"] and opener["can_open"]:
                # Apply the multiple-of-three ambiguity rule.
                ambiguous = (
                    (closer["can_open"] or opener["can_close"])
                    and closer["origdelims"] % 3 != 0
                    and (opener["origdelims"] + closer["origdelims"]) % 3 == 0
                )
                if not ambiguous:
                    found = opener_index
                    break
            opener_index = prev_active[opener_index]

        if found == -1:
            # Cache the failed range for later closers in this bucket.
            search_bound[bucket] = closer_index - 1
            if not closer["can_open"]:
                # This run cannot participate in a later match.
                next_pos = next_active[closer_index]
                _unlink(closer_index)
                closer_index = next_pos
            else:
                closer_index = next_active[closer_index]
            continue

        opener = delimiters[found]
        # Strong emphasis (2 delimiters) is preferred whenever both
        # sides have enough width left for it.
        use_delims = (
            2 if closer["numdelims"] >= 2 and opener["numdelims"] >= 2 else 1
        )

        opener["numdelims"] -= use_delims
        closer["numdelims"] -= use_delims
        opener["events"].append(("open", use_delims == 2))
        closer["events"].append(("close", use_delims == 2))

        # Markup inside this match cannot pair with text outside it. Link the
        # opener and closer directly so the enclosed entries are skipped.
        if found + 1 != closer_index:
            next_active[found] = closer_index
            prev_active[closer_index] = found

        if opener["numdelims"] == 0:
            _unlink(found)
        if closer["numdelims"] == 0:
            next_pos = next_active[closer_index]
            _unlink(closer_index)
            closer_index = next_pos
        # Retry a partially consumed closer on the next pass.

    # Anything still reachable was not fully consumed by a match.
    still_active = [False] * total
    pos = head[0]
    while pos < total:
        still_active[pos] = True
        pos = next_active[pos]
    for index, descriptor in enumerate(delimiters):
        descriptor["extendable"] = still_active[index]

    return delimiters


def commonmark_repair_chunk(
    text,
    pending,
    next_chunk=None,
    next_chunk_boundary_ch=None,
    record_atoms=None,
):
    """Make one split CommonMark chunk safe to render on its own.

    Pass the returned state to the next chunk. For example, ``"**hello"`` with
    ``next_chunk=" world**"`` returns ``"**hello**"`` and ``{"**": 1}``.

    When supplied, ``record_atoms`` collects reusable parsed sections as
    ``(start, end, kind, payload)``. Available section kinds are:

    - ``"plain"`` contains ordinary text and may be safely cut shorter.
    - ``"literal"`` contains one complete escape, code span, or link.
    - ``"delimiter"`` describes a reusable ``*`` or ``_`` markup run.
    - ``"consumed"`` records markup already closed by a previous chunk.
    - ``"resume"`` contains text plus the updated cross-chunk state.
    """

    def _record(start, end, kind, payload):
        """Record one parsed section when the caller requests reusable data."""
        if record_atoms is not None:
            record_atoms.append((start, end, kind, payload))

    # Collect fragments for one final join.
    out = []
    # Collect source-ordered delimiter runs for one matching pass.
    delimiters = []
    # Preserve the caller's state dictionary.
    pending = dict(pending)

    # Track possible link-label openings in this chunk.
    link_stack = []
    # Track labels so delayed records can be restored to source order.
    had_link_label = False

    # Initialize the single-pass scanner.
    i = 0
    n = len(text)
    # Index backtick runs for efficient matching.
    backtick_runs = commonmark_index_backtick_runs(text)

    # Pick a placeholder character proven not to collide with this
    # chunk's own real content before recording any delimiter runs.
    sentinel = commonmark_pick_emphasis_sentinel(text)

    # Resume code, links, or escapes started in the previous chunk.
    # Keep these fragments together and save the resulting state so a later
    # prefix query can replay this section without rebuilding it.
    _resume_start = len(out)
    in_code_width = pending.pop("in_code", None)
    if in_code_width:
        # Search this chunk for the carried code span's closing fence.
        close = commonmark_find_backtick_run(backtick_runs, 0, in_code_width)
        if close is not None:
            # Carried content plus the leftover fence are plain text now.
            out.append(_commonmark_escape_literal(text[:close]))
            i = close + in_code_width
        else:
            # Still doesn't close in this chunk either; carry it onward.
            out.append(_commonmark_escape_literal(text))
            pending["in_code"] = in_code_width
            i = n
        _record(
            0,
            i,
            "resume",
            {"text": "".join(out[_resume_start:]), "pending": dict(pending)},
        )

    elif pending.pop("in_link_dest", False):
        # Complete a terminator split between the previous and current chunk.
        if pending.pop("dest_gt", False) and n and text[0] == ")":
            out.append("\\)")
            i = 1
        else:
            # Find the end of a destination already treated as literal text.
            close, trailing_gt = _scan_angle_terminator(text, 0, n)

            if close is not None:
                # Escape the remaining destination and its closing marker.
                out.append(_commonmark_escape_literal(text[:close]))
                out.append("\\>\\)")
                i = close + 2
            else:
                # Carry the destination and any split closing marker forward.
                out.append(_commonmark_escape_literal(text))
                pending["in_link_dest"] = True
                if trailing_gt:
                    pending["dest_gt"] = True
                i = n
        _record(
            0,
            i,
            "resume",
            {"text": "".join(out[_resume_start:]), "pending": dict(pending)},
        )

    elif pending.pop("in_autolink", False):
        # Complete a still-forming autolink split from the previous chunk.
        close = text.find(">") if text else -1
        if close != -1:
            # Escape the remaining destination and its closing marker.
            out.append(_commonmark_escape_literal(text[:close]))
            out.append("\\>")
            i = close + 1
        else:
            # Still doesn't close in this chunk either; carry it onward.
            out.append(_commonmark_escape_literal(text))
            pending["in_autolink"] = True
            i = n
        _record(
            0,
            i,
            "resume",
            {"text": "".join(out[_resume_start:]), "pending": dict(pending)},
        )

    elif pending.pop("in_escape", False):
        # The prior backslash already escapes this chunk's first character.
        if text:
            out.append(text[0])
            i = 1
            _record(
                0,
                i,
                "resume",
                {
                    "text": "".join(out[_resume_start:]),
                    "pending": dict(pending),
                },
            )
        else:
            # Still nothing to consume; keep waiting for a real chunk.
            pending["in_escape"] = True

    # Scan the remainder of this chunk.
    while i < n:
        # Remember where this parsed section begins so it can be reused later.
        start = i
        ch = text[i]

        # Preserve escapes already present in the CommonMark source.
        if ch == "\\":
            if i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                _record(start, i, "literal", out[-1])
                continue
            # Carry a trailing backslash's escape state into the next chunk.
            out.append(ch)
            pending["in_escape"] = True
            i = n
            # Save the state because this escape continues in the next chunk.
            _record(
                start, i, "resume", {"text": out[-1], "pending": dict(pending)}
            )
            continue

        # Preserve complete code spans or carry split spans forward.
        if ch == "`":
            j = i
            # Measure the opening backtick run.
            while j < n and text[j] == "`":
                j += 1
            run = j - i
            # Look for the matching close run in the pre-built index.
            close = commonmark_find_backtick_run(backtick_runs, j, run)
            if close is not None:
                # Complete span in this chunk: copy verbatim.
                out.append(text[i : close + run])
                i = close + run
                _record(start, i, "literal", out[-1])
                continue

            # Drop a split fence and carry its width. Some targets decode
            # escapes before rendering, so escaping the fence is unsafe.
            pending["in_code"] = run
            out.append(_commonmark_escape_literal(text[j:]))
            i = n
            # Save the new state because this code span continues later.
            _record(
                start, i, "resume", {"text": out[-1], "pending": dict(pending)}
            )
            continue

        # Preserve a complete standalone autolink or carry a split one
        # forward. Its interior must never be scanned for emphasis
        # delimiters -- a "*" or "_" inside a URL is literal, not markup.
        if ch == "<":
            close, still_valid = commonmark_scan_autolink_dest(text, i, n)
            if close is not None:
                # Complete autolink in this chunk: copy verbatim.
                out.append(text[i : close + 1])
                i = close + 1
                _record(start, i, "literal", out[-1])
                continue
            if still_valid:
                # Carry the still-forming autolink onward, rendered as
                # escaped literal text in the meantime.
                out.append(_commonmark_escape_literal(text[i:]))
                pending["in_autolink"] = True
                i = n
                # This sets pending too -- same reasoning as above.
                _record(
                    start,
                    i,
                    "resume",
                    {"text": out[-1], "pending": dict(pending)},
                )
                continue
            # Not an autolink -- fall through and preserve it literally.

        # Classify delimiters from source text, not unresolved placeholders.
        if ch in "*_":
            j, prev_ch, next_ch = commonmark_scan_delimiter_run(
                text,
                i,
                boundary_next_ch=(next_chunk[0] if next_chunk else None),
            )
            run = j - i

            # Consume closers already rendered in the previous chunk.
            # Save consumed markers so reused scans update state too.
            consumed_markers = []
            while run > 0:
                marker = ch * 2 if run >= 2 else ch
                if pending.get(marker, 0) > 0:
                    pending[marker] -= 1
                    run -= len(marker)
                    consumed_markers.append(marker)
                else:
                    break

            if run > 0:
                # Record remaining width for the chunk-wide matching pass.
                descriptor = {
                    "char": ch,
                    "numdelims": run,
                    "origdelims": run,
                    "can_open": commonmark_can_open_emphasis(
                        ch, prev_ch, next_ch
                    ),
                    "can_close": commonmark_can_close_emphasis(
                        ch, prev_ch, next_ch
                    ),
                    "events": [],
                }
                delimiters.append(descriptor)
                index = len(delimiters) - 1
                out.append(f"{sentinel}{index}{sentinel}")
                # Save a description before matching changes the live copy.
                # Each reused prefix must begin with the same original values.
                _record(
                    start,
                    j,
                    "delimiter",
                    {
                        "char": descriptor["char"],
                        "numdelims": descriptor["numdelims"],
                        "origdelims": descriptor["origdelims"],
                        "can_open": descriptor["can_open"],
                        "can_close": descriptor["can_close"],
                        "events": [],
                        "consumed_markers": consumed_markers,
                    },
                )
            else:
                # The previous chunk consumed this run. Record that state
                # change even though this section produces no output.
                _record(
                    start,
                    j,
                    "consumed",
                    {"consumed_markers": consumed_markers},
                )

            i = j
            continue

        # Track link labels for carry-over across chunk boundaries.
        if ch == "[":
            # Keep output and source positions until the link completes.
            link_stack.append((len(out), i))
            out.append(ch)
            i += 1
            # Add the label record after its outcome is known.
            had_link_label = True
            continue

        if text.startswith("](<", i):
            # We are at the "](<" that may close a pending link label.
            close = commonmark_scan_angle_dest(text, i, n)
            if close is not None and link_stack:
                # Record the opener separately from the completed link ending.
                open_index, open_start = link_stack.pop()
                _record(open_start, open_start + 1, "literal", out[open_index])
                out.append(text[i : close + 2])
                _record(start, close + 2, "literal", text[i : close + 2])
                i = close + 2
                continue

            # Keep an incomplete link as escaped literal text.
            if link_stack:
                open_index, open_start = link_stack.pop()
                _record(open_start, open_start + 1, "literal", out[open_index])

            # The shared scanner stops at a real ``[``, so reaching this point
            # without a label is safe to record as literal or continued text.
            _dest_start = len(out)
            if close is not None:
                out.append("\\]\\(")
                out.append(_commonmark_escape_literal(text[i + 3 : close]))
                out.append("\\>\\)")
                i = close + 2
                _record(start, i, "literal", "".join(out[_dest_start:]))

            else:
                out.append("\\]\\(")
                out.append(_commonmark_escape_literal(text[i + 3 :]))
                pending["in_link_dest"] = True
                # Record a trailing ">" that may close in the next chunk.
                _, trailing_gt = _scan_angle_terminator(text, i + 3, n)
                if trailing_gt:
                    pending["dest_gt"] = True
                i = n
                _record(
                    start,
                    i,
                    "resume",
                    {
                        "text": "".join(out[_dest_start:]),
                        "pending": dict(pending),
                    },
                )
            continue

        if text.startswith("](", i):
            # A bare "](" (the angle-bracket form above already handled
            # "](<") that may close a pending link label with an
            # unbracketed destination.
            close = commonmark_scan_paren_dest(text, i + 1, n)
            if close is not None and link_stack:
                # Record the opener separately from the completed link ending.
                open_index, open_start = link_stack.pop()
                _record(open_start, open_start + 1, "literal", out[open_index])
                out.append(text[i : close + 1])
                _record(start, close + 1, "literal", text[i : close + 1])
                i = close + 1
                continue

            # This failed label now has its final literal value.
            if link_stack:
                open_index, open_start = link_stack.pop()
                _record(open_start, open_start + 1, "literal", out[open_index])

            if close is not None:
                # Without a matching ``[``, escape this URL as literal text so
                # any ``*`` or ``_`` inside it cannot become markup.
                _dest_start = len(out)
                out.append("\\]\\(")
                out.append(_commonmark_escape_literal(text[i + 2 : close]))
                out.append("\\)")
                i = close + 1
                _record(start, i, "literal", "".join(out[_dest_start:]))
                continue

            # Leave the unfinished URL untouched and do not inspect its markup.
            # Only angle-style URLs carry state because Apprise creates them.
            out.append(text[i:])
            i = n
            # No cross-chunk state changed, so record this as literal text.
            _record(start, i, "literal", out[-1])
            continue

        # Group ordinary characters to reduce repeated append calls.
        # An unhandled markup-like character stands alone so the
        # following character is checked normally on the next pass.
        if ch in "\\`<*_[]":
            i += 1
        else:
            while i < n and text[i] not in "\\`<*_[]":
                i += 1
        out.append(text[start:i])
        # Plain text can be safely shortened when rebuilding a smaller prefix.
        _record(start, i, "plain", out[-1])

    # Escape labels that did not complete within this chunk.
    for open_index, open_start in link_stack:
        out[open_index] = "\\" + out[open_index]
        _record(open_start, open_start + 1, "literal", out[open_index])

    if record_atoms is not None and had_link_label:
        # Restore source order after adding delayed label records.
        record_atoms.sort(key=lambda atom: atom[0])

    return _commonmark_resolve_emphasis(
        out,
        delimiters,
        sentinel,
        text_len=n,
        last_char=(text[-1] if text else None),
        pending=pending,
        next_chunk=next_chunk,
        next_chunk_boundary_ch=next_chunk_boundary_ch,
    )


def _commonmark_resolve_emphasis(
    out,
    delimiters,
    sentinel,
    text_len,
    last_char,
    pending,
    next_chunk,
    next_chunk_boundary_ch,
    closer_widths=None,
):
    """Resolve ``*`` and ``_`` runs and return ``(text, new_pending)``.

    ``text_len`` and ``last_char`` describe the requested prefix.
    ``closer_widths`` may supply precomputed closing-marker widths so the
    function does not need to scan ``next_chunk`` again.
    """
    # Resolve emphasis after every run in the chunk is known.
    commonmark_match_emphasis(delimiters)

    # Force eligible unmatched openers closed for this chunk and carry their
    # state forward. Runs already ruled out by CommonMark stay literal.
    new_pending = dict(pending)

    # Treat a final single marker as literal and a final empty pair as noise.
    last_index = len(delimiters) - 1
    trailing_empty = (
        bool(delimiters)
        and bool(out)
        and out[-1] == f"{sentinel}{last_index}{sentinel}"
    )

    # Classify edge runs using the characters around the lookahead slice,
    # unless a caller already worked this out from a shared index.
    if closer_widths is None:
        lookahead_closer_widths = commonmark_lookahead_closer_widths(
            next_chunk,
            boundary_prev_ch=last_char,
            boundary_next_ch=next_chunk_boundary_ch,
        )
    else:
        lookahead_closer_widths = closer_widths

    # Track forced opens so the tail can close them in reverse order.
    forced_open_groups = []
    for index, descriptor in enumerate(delimiters):
        # Carry an opener only when lookahead contains a possible closer.
        available_width = lookahead_closer_widths.get(descriptor["char"], 0)
        if (
            not descriptor["can_open"]
            or not descriptor["extendable"]
            or descriptor["numdelims"] <= 0
            or not available_width
        ):
            continue

        # Drop empty trailing runs unless that would empty the whole chunk.
        whole_chunk_is_this_run = text_len == descriptor["origdelims"]
        if (
            trailing_empty
            and index == last_index
            and not whole_chunk_is_this_run
        ):
            # Drop leftover pairs and preserve at most one literal marker.
            descriptor["numdelims"] %= 2
            continue

        # Record at most one strong and one regular verified expectation.
        char = descriptor["char"]
        opened = []
        to_allocate = descriptor["numdelims"]
        if available_width >= 2 and to_allocate >= 2:
            opened.append(char * 2)
            to_allocate -= 2
        if available_width != 2 and to_allocate >= 1:
            opened.append(char)
            to_allocate -= 1

        # Escape unallocated width so dialect adapters keep it literal.
        excess = _commonmark_escape_literal(char * to_allocate)

        descriptor["numdelims"] = 0

        # Emit literal excess before the portion closed for this chunk.
        real_close_part, _ = commonmark_render_emphasis_events(
            descriptor["events"], (char * 2, char * 2), (char, char)
        )
        descriptor["_forced_text"] = real_close_part + excess + "".join(opened)

        for marker in opened:
            new_pending[marker] = new_pending.get(marker, 0) + 1

        forced_open_groups.append(opened)

    # Close forced-open runs from innermost to outermost.
    for opened in reversed(forced_open_groups):
        out.extend(opened)

    def _substitute(match):
        descriptor = delimiters[int(match.group(1))]
        if "_forced_text" in descriptor:
            return descriptor["_forced_text"]
        char = descriptor["char"]
        # Escape unmatched width that cannot become emphasis.
        leftover = _commonmark_escape_literal(char * descriptor["numdelims"])
        close_part, open_part = commonmark_render_emphasis_events(
            descriptor["events"], (char * 2, char * 2), (char, char)
        )
        return close_part + leftover + open_part

    marker_re = _commonmark_emphasis_marker_pattern(sentinel)
    resolved_text = marker_re.sub(_substitute, "".join(out))

    return resolved_text, new_pending


# ---------------------------------------------------------------------------
# Shared repair scans the source once, then rebuilds many shorter prefixes from
# recorded sections. Links fall back to a direct repair because their meaning
# can change at each cut. Closing ``*`` and ``_`` runs use a shared lookup too.


def _cm_build_range_max_table(values):
    """Precompute range maximums for quick repeated lookups.

    Each row covers larger power-of-two windows. ``_cm_range_max()`` combines
    two of those windows to find the largest value in any requested range.
    """
    n = len(values)
    table = [list(values)]
    width = 1
    while width * 2 <= n:
        prev_row = table[-1]
        table.append(
            [
                max(prev_row[k], prev_row[k + width])
                for k in range(n - width * 2 + 1)
            ]
        )
        width *= 2
    return table


def _cm_range_max(table, lo, hi):
    """Return ``max(values[lo:hi])`` using a table built by
    ``_cm_build_range_max_table()``. Requires ``hi > lo``.
    """
    length = hi - lo
    level = length.bit_length() - 1
    row = table[level]
    width = 1 << level
    # Cover the requested range from both ends; overlap does not affect max().
    return max(row[lo], row[hi - width])


class _CmCloserRunIndex:
    """Find the widest closing-marker run in a requested text range.

    ``commonmark_scan_closer_runs()`` builds one index for ``*`` and one for
    ``_`` so repeated prefix checks do not scan the same text again.
    """

    __slots__ = ("_ends", "_starts", "_table")

    def __init__(self, starts, ends, widths):
        # Runs arrive in source order, so no sorting is needed. Keep every run
        # for boundary checks; a zero width means it cannot close markup.
        self._starts = starts
        self._ends = ends
        self._table = _cm_build_range_max_table(widths)

    def widest_in_window(self, window_start, window_end):
        """Return the widest closing run visible in this range, up to 3.

        Partly visible runs are shortened to the visible width. Call
        ``straddles()`` first and use a direct scan when a boundary cuts a run.
        """
        starts = self._starts
        ends = self._ends
        n = len(starts)
        if n == 0 or window_start >= window_end:
            return 0

        # The first table row stores usable widths; zero means ignore the run.
        run_widths = self._table[0]

        # At most one non-overlapping run can cross the window's left edge.
        idx = bisect_right(starts, window_start) - 1
        best = 0
        if idx >= 0 and ends[idx] > window_start:
            visible = min(ends[idx], window_end) - window_start
            best = min(visible, run_widths[idx])
            idx += 1
        else:
            idx += 1

        stop = bisect_left(starts, window_end)
        if stop > idx:
            # These runs are inside the window, so one lookup covers them.
            best = max(best, _cm_range_max(self._table, idx, stop))

        return best

    def straddles(self, position):
        """Return whether ``position`` falls inside a recorded marker run.

        A boundary inside a run changes which neighboring characters are
        visible, so callers must directly rescan that range for a safe result.
        """
        starts = self._starts
        idx = bisect_right(starts, position) - 1
        return idx >= 0 and starts[idx] < position < self._ends[idx]


def commonmark_scan_closer_runs(text, boundary_next_ch=None):
    """Index closing ``*`` and ``_`` runs for repeated checks.

    Scanning stops where an escape, code span, or link could change how a
    later range is interpreted.

    Returns ``(index_by_char, covered_end)``:

    - ``index_by_char`` contains an index for both ``*`` and ``_``.
    - ``covered_end`` marks how far the shared result can be safely used.
    """
    starts = {"*": [], "_": []}
    ends = {"*": [], "_": []}
    widths = {"*": [], "_": []}

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in "\\`<]":
            # Stop here because ranges beginning later may interpret this
            # escape, code span, or link differently.
            break
        if ch in "*_":
            j, prev_ch, next_ch = commonmark_scan_delimiter_run(
                text, i, boundary_next_ch=boundary_next_ch
            )
            # Record every run so boundaries that split an unusable run are
            # detected too. Store zero when it cannot close markup.
            starts[ch].append(i)
            ends[ch].append(j)
            widths[ch].append(
                min(j - i, 3)
                if commonmark_can_close_emphasis(ch, prev_ch, next_ch)
                else 0
            )
            i = j
            continue
        i += 1

    index_by_char = {
        ch: _CmCloserRunIndex(starts[ch], ends[ch], widths[ch])
        for ch in ("*", "_")
    }
    return index_by_char, i


def commonmark_scan_repair_region(text, pending, lookahead_span):
    """Record reusable sections for repairing several prefixes of one text.

    Use the same ``pending`` state and ``lookahead_span`` when materializing.

    Returns ``(recorded_sections, covered_end, sentinel)``:

    - ``recorded_sections`` contains ``(start, end, kind, payload)`` entries.
    - ``covered_end`` marks the last safe reusable position.
    - ``sentinel`` is the unique placeholder used while rebuilding markup.
    """
    bracket_pos = text.find("[")
    covered_end = len(text) if bracket_pos == -1 else bracket_pos
    region = text[:covered_end]

    # Start lookahead at the reusable region's end, which may be shortened by a
    # link opening. Read it from the supplied text so it need not be predicted.
    lookahead_end = covered_end + lookahead_span
    lookahead = text[covered_end:lookahead_end]
    lookahead_boundary_ch = text[lookahead_end : lookahead_end + 1] or None

    atoms = []
    commonmark_repair_chunk(
        region,
        pending,
        next_chunk=(lookahead or None),
        next_chunk_boundary_ch=lookahead_boundary_ch,
        record_atoms=atoms,
    )

    # An unfinished ``<`` may become an autolink when more text is available.
    # Keep only the recorded sections before it, whose meaning cannot change.
    for atom_index, (atom_start, _end, kind, payload) in enumerate(atoms):
        if kind == "plain" and payload == "<":
            covered_end = atom_start
            region = text[:covered_end]
            atoms = atoms[:atom_index]
            break

    # One unique placeholder is safe for every shorter prefix of this region.
    sentinel = commonmark_pick_emphasis_sentinel(region)

    return atoms, covered_end, sentinel


def commonmark_materialize_repair(
    body,
    offset,
    cut,
    pending,
    scan_atoms,
    covered_end,
    sentinel,
    lookahead_span,
    closer_index=None,
    closer_covered_end=None,
):
    """Repair one prefix using a region scanned earlier.

    Equivalent to calling::

        commonmark_repair_chunk(
            body[offset : offset + cut],
            pending,
            next_chunk=body[offset + cut : offset + cut + lookahead_span],
            next_chunk_boundary_ch=body[offset + cut + lookahead_span]
            if that position exists else None,
        )

    Supply the values returned by ``commonmark_scan_repair_region()`` with the
    same ``pending`` state. Closer data is optional but avoids another scan.
    """

    def _fallback():
        """Repair directly when the shared scan cannot be reused."""
        abs_cut = offset + cut
        lookahead_end = abs_cut + lookahead_span
        lookahead = body[abs_cut:lookahead_end]
        boundary_next_ch = body[lookahead_end : lookahead_end + 1] or None
        return commonmark_repair_chunk(
            body[offset:abs_cut],
            pending,
            next_chunk=lookahead or None,
            next_chunk_boundary_ch=boundary_next_ch,
        )

    if cut <= 0:
        # Even empty input can update carried state, so use the normal repair.
        return _fallback()

    if cut > covered_end:
        # The shared scan stopped before this cut, usually at a link opening.
        return _fallback()

    # Recorded sections cover the reusable text in order with no gaps.
    ends = [atom[1] for atom in scan_atoms]
    split = bisect_left(ends, cut)

    tail_text = None
    if ends[split] == cut:
        # This recorded section ends at the cut, so include it in full.
        included = scan_atoms[: split + 1]
    else:
        # The cut lands inside this recorded section.
        atom_start, _atom_end, kind, payload = scan_atoms[split]
        if kind != "plain":
            # Escapes, code spans, links, and markup runs must remain whole.
            # Repair directly rather than guessing how part of one behaves.
            return _fallback()
        # A run of ordinary characters carries no escaping ambiguity, so
        # any prefix of it is trivially valid on its own.
        included = scan_atoms[:split]
        tail_text = payload[: cut - atom_start]

    # Rebuild the prefix from recorded sections. Use a private state copy so
    # each query replays carried-marker changes independently.
    out = []
    delimiters = []
    working_pending = dict(pending)
    for _start, _end, kind, payload in included:
        if kind == "resume":
            # Replace working state with the snapshot saved for this section.
            out.append(payload["text"])
            working_pending = dict(payload["pending"])
        elif kind == "delimiter":
            # Copy mutable markup data so independent queries cannot change it.
            delimiters.append(
                {
                    "char": payload["char"],
                    "numdelims": payload["numdelims"],
                    "origdelims": payload["origdelims"],
                    "can_open": payload["can_open"],
                    "can_close": payload["can_close"],
                    "events": [],
                }
            )
            out.append(f"{sentinel}{len(delimiters) - 1}{sentinel}")
            for marker in payload["consumed_markers"]:
                working_pending[marker] = working_pending.get(marker, 0) - 1
        elif kind == "consumed":
            # This run produced no text, but its state change still applies.
            for marker in payload["consumed_markers"]:
                working_pending[marker] = working_pending.get(marker, 0) - 1
        else:
            out.append(payload)

    if tail_text is not None:
        out.append(tail_text)

    abs_cut = offset + cut
    lookahead_end = abs_cut + lookahead_span
    last_char = body[abs_cut - 1] if cut else None

    # Express this prefix's lookahead range relative to the shared scan.
    rel_start = cut
    rel_end = cut + lookahead_span

    closer_widths = None
    if closer_index is not None and rel_end <= closer_covered_end:
        straddling = any(
            index.straddles(rel_start) or index.straddles(rel_end)
            for index in closer_index.values()
        )
        if not straddling:
            # A boundary inside a marker run requires the direct scan below.
            closer_widths = {}
            for ch, index in closer_index.items():
                width = index.widest_in_window(rel_start, rel_end)
                if width:
                    closer_widths[ch] = width

    if closer_widths is not None:
        return _commonmark_resolve_emphasis(
            out,
            delimiters,
            sentinel,
            text_len=cut,
            last_char=last_char,
            pending=working_pending,
            next_chunk=None,
            next_chunk_boundary_ch=None,
            closer_widths=closer_widths,
        )

    lookahead = body[abs_cut:lookahead_end]
    boundary_next_ch = body[lookahead_end : lookahead_end + 1] or None

    return _commonmark_resolve_emphasis(
        out,
        delimiters,
        sentinel,
        text_len=cut,
        last_char=last_char,
        pending=working_pending,
        next_chunk=(lookahead or None),
        next_chunk_boundary_ch=boundary_next_ch,
    )
