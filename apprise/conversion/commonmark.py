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

# CommonMark ASCII punctuation; Unicode categories cover other characters.
_CM_ASCII_PUNCTUATION = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"


def commonmark_index_backtick_runs(text):
    """Index unescaped backtick positions by run length in one pass.

    For example, ``"a`b``c"`` produces ``{1: [1], 2: [3]}``.
    """

    # Maps run-length -> [start, ...] in ascending position order.
    index = {}

    # Track the current scanner position and input length.
    i = 0
    n = len(text)

    # Visit each character at most once.
    while i < n:
        ch = text[i]
        # Consume escape pairs so a backslash-escaped backtick is not
        # mistaken for the start or end of a code span.
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "`":
            # Measure the run by advancing until the first non-backtick.
            j = i
            while j < n and text[j] == "`":
                j += 1
            # Store this run's starting position under its length key.
            # setdefault ensures the list exists before appending.
            index.setdefault(j - i, []).append(i)
            # Jump past the entire run to avoid double-counting.
            i = j
            continue

        # Advance past ordinary text.
        i += 1

    # Return positions grouped by delimiter width.
    return index


def commonmark_find_backtick_run(index, start, run):
    """Find the next code fence of ``run`` backticks at or after ``start``.

    For example, ``commonmark_find_backtick_run({1: [0, 4]}, 1, 1)`` returns 4.
    """

    # Nothing to search if no run of this exact length was indexed.
    positions = index.get(run)
    if not positions:
        return None
    # Binary-search for the first position that is >= start.
    pos = bisect_left(positions, start)
    # Return the found position, or None if we went past the end of the list.
    return positions[pos] if pos < len(positions) else None


def commonmark_escape_link_url(url):
    """Prepare a CommonMark URL for a service's ``<url|label>`` syntax.

    For example, ``r"a\\|b&c"`` becomes ``"a%7Cb&amp;c"``.
    """

    # Step 1: strip CommonMark backslash escapes so we recover the raw URL
    # characters before re-applying any encoding the target dialect needs.
    out = []

    # Scan the URL without allocating intermediate match objects.
    i = 0
    n = len(url)
    while i < n:
        ch = url[i]
        if ch == "\\" and i + 1 < n:
            # Discard the backslash and keep only the escaped character.
            out.append(url[i + 1])
            i += 2
            continue
        out.append(ch)
        i += 1

    # Reassemble the decoded CommonMark destination.
    url = "".join(out)

    # Step 2: re-encode the characters that the <url|label> delimiter syntax
    # would mis-parse if left bare in the URL string.
    # "&" must come first to avoid double-encoding the entities below.
    url = url.replace("&", "&amp;").replace("<", "&lt;")
    url = url.replace(">", "&gt;")
    # "|" is the separator between the URL and label inside <url|label>;
    # percent-encode it so it cannot be mistaken for the delimiter.
    return url.replace("|", "%7C")


# Allow several full-body destination scans while keeping total work linear.
SCAN_BUDGET_MULTIPLIER = 4

# After the shared budget is spent, allow a small fixed probe so nearby
# destinations can still close without restoring unbounded scanning.
# The 256-character fallback covers common URLs while keeping work bounded.
MIN_SCAN_ALLOWANCE = 256


def commonmark_new_scan_budget(body):
    """Create one link-scanning allowance shared across a conversion.

    Pass it to every URL scanner. Once spent, each later URL receives a fixed
    256-character scan so malformed links cannot repeatedly scan the message.
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


# A CommonMark autolink scheme: a letter followed by 1-31 more letters,
# digits, "+", "-", or "." -- 2 to 32 characters before the ":".
_AUTOLINK_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]{1,31}:")


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


# Escape these CommonMark characters when they must remain literal.
_COMMONMARK_LITERAL_CHARS = "\\`*_[]()<>"


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
    """Make one split CommonMark chunk independently renderable.

    Pass the returned state into the next call. Calling this for ``"**hello"``
    with ``next_chunk=" world**"`` returns ``"**hello**"`` and state
    ``{"**": 1}``, allowing the next chunk to consume the real closer.

    When supplied, ``record_atoms`` collects reusable parsed sections as
    ``(start, end, kind, payload)``. This lets callers repair many shorter
    prefixes without scanning the same text again. Section kinds are:

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
            # Save the opening position until this chunk completes the link.
            link_stack.append(len(out))
            out.append(ch)
            i += 1
            continue

        if text.startswith("](<", i):
            # We are at the "](<" that may close a pending link label.
            close = commonmark_scan_angle_dest(text, i, n)
            if close is not None and link_stack:
                # Preserve a complete link contained in this chunk.
                link_stack.pop()
                out.append(text[i : close + 2])
                i = close + 2
                continue

            # Render any boundary-cut link as escaped literal text.
            if link_stack:
                link_stack.pop()

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
                # Preserve a complete link contained in this chunk.
                link_stack.pop()
                out.append(text[i : close + 1])
                i = close + 1
                continue

            if link_stack:
                link_stack.pop()

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

    # Escape link labels that do not complete within this chunk.
    for idx in link_stack:
        out[idx] = "\\" + out[idx]

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
    """Index possible closing ``*`` and ``_`` runs for repeated range checks.

    Scanning stops at escapes, code, or links because a later range may start
    inside them and interpret the following text differently. Callers directly
    scan any range beyond that safe stopping point.

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
    """Scan text once into recorded sections for reuse by prefix repairs.

    Use the same ``pending`` and ``lookahead_span`` as later materialization
    calls. Include enough text after the largest planned cut to fill lookahead.

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
    """Repair one prefix by reusing a region scanned earlier.

    Equivalent to calling::

        commonmark_repair_chunk(
            body[offset : offset + cut],
            pending,
            next_chunk=body[offset + cut : offset + cut + lookahead_span],
            next_chunk_boundary_ch=body[offset + cut + lookahead_span]
            if that position exists else None,
        )

    ``scan_atoms``, ``covered_end``, and ``sentinel`` come from
    ``commonmark_scan_repair_region()`` using the same ``pending`` value.
    Optional closer data avoids another lookahead scan; omitting it is slower
    but produces the same result.
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
