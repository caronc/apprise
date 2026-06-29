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

from bisect import bisect_left
import contextlib
from html.parser import HTMLParser
import re

from markdown import markdown

from .common import NotifyFormat
from .url import URLBase

# Cap list indentation so deeply nested input stays linear.
LIST_DEPTH_MAX = 4

# Apply the same depth cap to blockquote prefixes.
BLOCKQUOTE_DEPTH_MAX = 4

# Bound the context-stack depth so adversarially nested HTML cannot
# exhaust memory.  Frames beyond this limit are silently dropped.
MAX_FRAME_DEPTH = 200


class _Marker(str):
    """Identify converter-generated structure."""


class _ListMarker(_Marker):
    """Identify a generated list marker."""


class _QuoteMarker(_Marker):
    """Identify a generated quote prefix."""


class _ListIndent(_Marker):
    """Identify list continuation indentation."""


class _ParaBreak:
    """Represent a paragraph boundary and its prefix."""

    __slots__ = ("in_quote", "prefix")

    def __init__(self, prefix="", in_quote=False):
        """Initialize a paragraph boundary."""

        # Store the continuation prefix
        self.prefix = prefix

        # Track whether the boundary remains inside a quote
        self.in_quote = in_quote


def convert_between(from_format, to_format, content):
    """Converts between different suported formats. If no conversion exists, or
    the selected one fails, the original text will be returned.

    This function returns the content translated (if required)
    """

    # Map each supported format pair to its converter
    converters = {
        (NotifyFormat.MARKDOWN, NotifyFormat.HTML): markdown_to_html,
        (NotifyFormat.TEXT, NotifyFormat.HTML): text_to_html,
        (NotifyFormat.HTML, NotifyFormat.TEXT): html_to_text,
        (NotifyFormat.HTML, NotifyFormat.MARKDOWN): html_to_markdown,
    }

    # Fetch the converter registered for this format pair.
    convert = converters.get((from_format, to_format))

    # Preserve the original content when no conversion is available
    return convert(content) if convert else content


def markdown_to_html(content):
    """Converts specified content from markdown to HTML."""

    # Enable notification-friendly line-break and table extensions.
    return markdown(
        content,
        extensions=["markdown.extensions.nl2br", "markdown.extensions.tables"],
    )


def text_to_html(content):
    """Converts specified content from plain text to HTML."""

    # First eliminate any carriage returns
    return URLBase.escape_html(content, convert_new_lines=True)


def html_to_text(content):
    """Converts a content from HTML to plain text."""

    # Initialize the plain-text parser.
    parser = HTMLConverter()

    # Feed and finalize the HTML document
    parser.feed(content)
    parser.close()

    # Return the finalized parser output.
    return parser.converted


def html_to_markdown(content):
    """Convert HTML content to CommonMark."""

    # Initialize the Markdown parser.
    parser = HTMLMarkdownConverter()

    # Feed and finalize the HTML document
    parser.feed(content)
    parser.close()

    # Return the finalized parser output.
    return parser.converted


class HTMLConverter(HTMLParser):
    """An HTML to plain text converter tuned for email messages."""

    # The following tags must start on a new line
    BLOCK_TAGS = (
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "div",
        "td",
        "th",
        "code",
        "pre",
        "label",
        "li",
    )

    # the folowing tags ignore any internal text
    IGNORE_TAGS = (
        "form",
        "input",
        "textarea",
        "select",
        "ul",
        "ol",
        "style",
        "link",
        "meta",
        "title",
        "html",
        "head",
        "script",
    )

    # Condense Whitespace
    WS_TRIM = re.compile(r"[\s]+", re.DOTALL | re.MULTILINE)

    # Sentinel value for block tag boundaries, which may be consolidated into a
    # single line break.
    BLOCK_END = {}

    def __init__(self, **kwargs):
        """Initialize the HTML converter."""

        # Initialize the standard-library HTML parser.
        super().__init__(**kwargs)

        # Should we store the text content or not?
        self._do_store = True

        # Initialize internal result list
        self._result = []

        # Initialize public result field (not populated until close() is
        # called)
        self.converted = ""

    def close(self):
        """Finalize the converted content."""

        # Combine buffered fragments into one string.
        string = "".join(self._finalize(self._result))

        # Publish the normalized result.
        self.converted = string.strip()

    def _finalize(self, result):
        """Combines and strips consecutive strings, then converts consecutive
        block ends into singleton newlines.

        [ {be} " Hello " {be} {be} " World!" ] -> "\nHello\nWorld!"
        """

        # None means the last visited item was a block end.
        accum = None

        for item in result:
            if item == self.BLOCK_END:
                # Multiple consecutive block ends; do nothing.
                if accum is None:
                    continue

                # First block end; yield the current string, plus a newline.
                yield accum.strip() + "\n"
                accum = None

            # Multiple consecutive strings; combine them.
            elif accum is not None:
                accum += item

            # First consecutive string; store it.
            else:
                accum = item

        # Yield the last string if we have not already done so.
        if accum is not None:
            yield accum.strip()

    def handle_data(self, data, *args, **kwargs):
        """Store our data if it is not on the ignore list."""

        # Ignore data while an ignored container is active.
        if self._do_store:
            # Collapse whitespace before buffering visible text.
            content = self.WS_TRIM.sub(" ", data)

            # Preserve the normalized fragment for final assembly.
            self._result.append(content)

    def handle_starttag(self, tag, attrs):
        """Process our starting HTML Tag."""

        # Toggle storage according to the newly opened container.
        self._do_store = tag not in self.IGNORE_TAGS

        # Start block elements on a fresh output line.
        if tag in self.BLOCK_TAGS:
            self._result.append(self.BLOCK_END)

        # Prefix each list item with a plain-text bullet.
        if tag == "li":
            self._result.append("- ")

        # Preserve explicit HTML line breaks.
        elif tag == "br":
            self._result.append("\n")

        # Render horizontal rules on their own line.
        elif tag == "hr":
            # Remove spacing that would precede the rule.
            if self._result and isinstance(self._result[-1], str):
                self._result[-1] = self._result[-1].rstrip(" ")

            self._result.append("\n---\n")

        # Mark the start of quoted plain text.
        elif tag == "blockquote":
            self._result.append(" >")

    def handle_endtag(self, tag):
        """Edge case handling of open/close tags."""

        # Resume storage after leaving an ignored container.
        self._do_store = True

        # Close block elements with a line boundary.
        if tag in self.BLOCK_TAGS:
            self._result.append(self.BLOCK_END)


def build_backtick_run_index(text):
    """Index unescaped backtick positions by run length in one pass."""

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


def find_unescaped_run(index, start, run):
    """Find the next indexed backtick run of the requested length."""

    # Nothing to search if no run of this exact length was indexed.
    positions = index.get(run)
    if not positions:
        return None
    # Binary-search for the first position that is >= start.
    pos = bisect_left(positions, start)
    # Return the found position, or None if we went past the end of the list.
    return positions[pos] if pos < len(positions) else None


def commonmark_escape_link_url(url):
    """Adapt a CommonMark URL for ``<url|label>`` dialects."""

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


def commonmark_scan_angle_dest(body, i, n):
    """Find the closing ``>`` of a ``](<url>)`` destination.

    ``i`` points at ``](<`` and ``n`` bounds the scan. Escaped ``>)`` pairs
    are skipped; the closing index or ``None`` is returned.
    """

    # Start immediately after the opening ``](<`` sequence.
    k = i + 3

    # Scan until a complete two-character terminator can no longer fit.
    while k < n - 1:
        if body[k] == "\\" and k + 1 < n:
            # Skip escape sequences -- they cannot be the terminator.
            k += 2
            continue
        if body[k] == ">" and body[k + 1] == ")":
            return k
        k += 1
    return None


def commonmark_emphasis_run(body, i, n, stack, out):
    """Map one CommonMark asterisk run to target emphasis delimiters.

    ``stack`` tracks nested bold/italic spans while ``out`` receives their
    delimiters. The returned index points immediately after the run.
    """
    # Measure the full asterisk run starting at i.
    j = i
    while j < n and body[j] == "*":
        j += 1
    run = j - i

    # Consume the run one span at a time.  Each iteration either closes
    # the top-of-stack span (if the remaining run width satisfies it) or
    # opens a new span.
    while run > 0:
        if stack and (
            (stack[-1][0] == "*" and run >= 2)
            or (stack[-1][0] == "_" and run >= 1)
        ):
            # Close the innermost open span.
            delim, open_index = stack.pop()
            if open_index == len(out) - 1:
                # Span opened but collected no content -- drop the orphan.
                out.pop()
            else:
                # Emit the matching close delimiter.
                out.append(delim)
            # Bold ("*") consumes 2 asterisks; italic ("_") consumes 1.
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

    # Return the position after the full asterisk run.
    return j


def commonmark_force_close_spans(out, stack):
    """Close remaining LIFO emphasis spans and discard empty ones.

    Both ``out`` and ``stack`` are updated in place.
    """

    # Close innermost spans first to preserve valid nesting.
    while stack:
        delim, open_index = stack.pop()
        if open_index == len(out) - 1:
            # Span opened but collected no content -- remove the orphan.
            out.pop()
        else:
            # Emit the close delimiter.
            out.append(delim)


def commonmark_prepend_title(body, title):
    """Prepend a clean CommonMark H1 title above the body.

    Returns ``(body, "")`` so callers can clear their separate title field.
    """

    # Remove whitespace and structural prefixes before adding our heading.
    title_text = title.lstrip("\r\n \t\v\f#-")

    # Add the heading only when meaningful title text remains.
    if title_text:
        body = f"# {title_text}\n{body}" if body else f"# {title_text}"
    return body, ""


class HTMLMarkdownConverter(HTMLConverter):
    """Convert HTML to notification-friendly CommonMark.

    Plugins may adapt this output to their own Markdown dialects.
    """

    # Define tags that create Markdown block boundaries.
    BLOCK_TAGS = frozenset(
        {
            "p",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "div",
            "td",
            "th",
            "pre",
            "samp",
            "label",
            "li",
        }
    )

    # Paragraph-like blocks need blank-line separation in CommonMark.
    _PARA_LIKE_TAGS = frozenset({"p", "div", "td", "th", "label"})

    # Reuse a plain paragraph boundary outside blockquotes.
    PARA_BREAK = _ParaBreak()

    # Escape characters that could become inline Markdown.
    MARKDOWN_ESCAPE = re.compile(
        r"([\\`*_~#\[\]()!<>])", re.DOTALL | re.MULTILINE
    )

    # Block syntax only needs escaping at the start of a line.
    _ORDERED_MARKER_RE = re.compile(r"^\d+\.(?=[ \t]|$)")

    # Match bullet markers at the start of a line.
    _BULLET_MARKER_RE = re.compile(r"^[-+](?=[ \t]|$)")

    # Match thematic breaks and setext heading underlines.
    # Uses separate alternates (no backreference) to avoid ReDoS on
    # inputs like "- - - - - - - - ... -x".
    _THEMATIC_BREAK_RE = re.compile(r"^(?:-[ \t]*){3,}$|^(?:=[ \t]*){3,}$")

    # Collapse ASCII whitespace when flattening table cells.
    _CELL_WHITESPACE_RUN = re.compile(r"[ \t\r\f\v]+")

    # Escape angle-bracket link destinations.
    HREF_ESCAPE = re.compile(r"([\\<>])")

    # Remove ASCII controls, Unicode format/zero-width characters, and
    # BiDi override/embedding controls that browsers silently discard during
    # URL parsing.  These characters can be prepended to a dangerous scheme
    # (e.g. U+200B before "javascript:") or used to visually reverse a URL
    # (e.g. U+202E before "javascript:") so they appear safe on screen while
    # containing an exploitable scheme once the override is decoded.
    _HREF_CONTROL_CHARS = re.compile(
        "[\x00-\x1f\x7f\u00ad\u200b-\u200f\u2028-\u202e\u2066-\u2069\ufeff]"
    )

    # Detect URI schemes before sanitizing links.
    _HREF_SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")

    # Block executable and local URI schemes while allowing app links.
    # "blob" is included because blob: URLs can carry arbitrary payloads.
    _UNSAFE_HREF_SCHEMES = frozenset(
        {"javascript", "vbscript", "data", "file", "blob"}
    )

    # Trim ASCII whitespace without removing deliberate non-breaking spaces.
    _ASCII_WHITESPACE = " \t\n\r\x0b\x0c"

    def __init__(self, **kwargs):
        """Initialize the HTML-to-Markdown converter."""

        # Initialize the base converter
        super().__init__(**kwargs)

        # Cache indentation by list depth.
        self._indent_cache = [""]

        # Cache prefixes by blockquote depth.
        self._quote_prefix_cache = [""]

        # Track open tags for constant-time unmatched-close checks.
        self._tag_open_counts = {}

        # Track whether the current frame emitted real content.
        self._content_seq = 0

        # Context stack.  The sentinel root frame at index 0 is never
        # popped and represents top-level content outside every tag.
        # Each frame is a dict with these keys:
        #   tag         -- str|None  tag that opened this frame
        #   do_store    -- bool      store text nodes encountered here?
        #   preserve_cr -- bool      keep whitespace literally (pre/code)?
        #   list_type   -- str|None  'ul', 'ol', or None
        #   depth       -- int       list nesting depth (1 = outermost),
        #                            clamped to LIST_DEPTH_MAX
        #   counter     -- int|None  next item number for 'ol' lists
        #   list_do_store -- bool    do_store of the list's own parent
        #                            (the nearest non-ul/ol/li ancestor),
        #                            saved here when the ul/ol is pushed
        #                            so <li> can read it directly instead
        #                            of walking back up the stack
        #   quote_depth -- int       blockquote nesting depth (1 = outermost),
        #                            clamped to BLOCKQUOTE_DEPTH_MAX; 0
        #                            means "not inside a blockquote"
        #   list_indent -- str       spaces a continuation line needs to
        #                            stay part of the current <li> --
        #                            "" outside any list. Combined with
        #                            quote_depth's "> " (in whichever
        #                            order they were actually nested)
        #                            by _write_boundary() for any line
        #                            that needs to restate it.
        #   list_indent_base -- str  list_indent from *outside* the
        #                            entire list-nesting chain (e.g.
        #                            from an enclosing <blockquote>) --
        #                            captured once where that chain
        #                            starts (depth 0 -> 1) and inherited
        #                            unchanged by every level nested
        #                            inside it after that. <li> adds
        #                            only its own marker's width on top
        #                            of *this*, not the immediately
        #                            enclosing list's full list_indent,
        #                            since that would double-count: a
        #                            nested marker's own leading spaces
        #                            (from _indent(depth)) already cover
        #                            every outer list level's width.
        #   href        -- str|None  href of an enclosing <a> tag; set
        #                            only on frames pushed by <a>
        #   buffer      -- list[str] raw text accumulated inside a
        #                            code/pre/samp frame; only present
        #                            on frames pushed by those tags --
        #                            the matching close tag needs the
        #                            full text up front to size a
        #                            delimiter that cannot collide with
        #                            backticks already in the content
        self._stack = [
            {
                "tag": None,
                "do_store": True,
                "preserve_cr": False,
                "list_type": None,
                "depth": 0,
                "counter": None,
                "list_do_store": True,
                "quote_depth": 0,
                "list_indent": "",
                "list_indent_base": "",
            }
        ]

    def _make_frame(self, tag, **overrides):
        """Create a frame from the current context."""

        # Inherit frame defaults from the parent context.
        parent = (
            self._stack[-1]
            if self._stack
            else {
                "tag": None,
                "do_store": True,
                "preserve_cr": False,
                "list_type": None,
                "depth": 0,
                "counter": None,
                "list_do_store": True,
                "quote_depth": 0,
                "list_indent": "",
                "list_indent_base": "",
            }
        )
        # Build the new frame by inheriting all context keys from the parent.
        # Callers pass **overrides to replace only the keys they need changed.
        frame = {
            "tag": tag,
            "do_store": parent["do_store"],
            "preserve_cr": parent["preserve_cr"],
            "list_type": parent["list_type"],
            "depth": parent["depth"],
            "counter": parent["counter"],
            "list_do_store": parent["list_do_store"],
            "quote_depth": parent["quote_depth"],
            "list_indent": parent["list_indent"],
            "list_indent_base": parent["list_indent_base"],
        }

        # Apply caller-supplied overrides on top of the inherited defaults.
        frame.update(overrides)
        return frame

    def _indent(self, depth):
        """Return cached indentation for a list depth."""

        # Depth 1 is the outermost level and needs no indentation,
        # so shift by one: depth 1 -> index 0 (empty string).
        idx = max(depth - 1, 0)

        # Work against the shared per-instance indentation cache.
        cache = self._indent_cache

        # Extend the cache on demand -- each level adds two spaces.
        while len(cache) <= idx:
            cache.append(cache[-1] + "  ")

        return cache[idx]

    def _quote_prefix(self, depth):
        """Return the prefix for a quote depth."""

        # Clamp negative depths to zero (should not occur in practice).
        idx = max(depth, 0)

        # Work against the shared per-instance quote-prefix cache.
        cache = self._quote_prefix_cache

        # Extend the cache on demand -- each nesting level prepends "> ".
        while len(cache) <= idx:
            cache.append(_QuoteMarker(cache[-1] + "> "))

        return cache[idx]

    def _continuation_prefix(self, ctx):
        """Return the prefix that any continuation line must carry."""

        # Start with whatever list indentation this context inherited.
        prefix = ctx["list_indent"]

        # If we are inside a blockquote, append its ">" leader as well.
        if ctx["quote_depth"]:
            prefix += self._quote_prefix(ctx["quote_depth"])

        return prefix

    def _write_boundary(self, ctx, strong=False):
        """Append a line break or a nesting-aware paragraph break."""

        # Compute the prefix that any following line must carry.
        prefix = self._continuation_prefix(ctx)

        if not strong:
            # Weak boundary -- a single line break in the output.
            self._result.append(self.BLOCK_END)

            # Restate any active quote or list prefix so the next
            # content line opens inside the correct nesting context.
            if prefix:
                self._result.append(
                    _QuoteMarker(prefix)
                    if ctx["quote_depth"]
                    else _ListIndent(prefix)
                )

            # The ordinary boundary is complete; nothing more to do.
            return

        # Strong boundary -- blank-line paragraph separation.
        if prefix:
            # Carry nesting context into the paragraph break so _finalize()
            # can restate it on the first line of the next paragraph.
            self._result.append(
                _ParaBreak(prefix, in_quote=bool(ctx["quote_depth"]))
            )

        else:
            # No active nesting -- use the cached bare paragraph break.
            self._result.append(self.PARA_BREAK)

    def _open_line_boundary(self, ctx, strong=False):
        """Start a block unless a structural marker owns the line."""

        if self._result and isinstance(self._result[-1], _Marker):
            # A structural marker is already on the line -- suppress the
            # boundary so the block content follows it directly.
            return

        self._write_boundary(ctx, strong=strong)

    def _emit(self, text):
        """Append content and advance the empty-span sequence counter."""

        self._result.append(text)

        # Each emission is a unique sequence point; comparing the counter
        # value at open-time vs. close-time reveals whether the frame was
        # empty without scanning the result buffer.
        self._content_seq += 1

    def _push_frame(self, frame):
        """Push a frame, returning whether the depth limit accepted it.

        ``True`` means the frame and tag counter were stored. ``False`` means
        the depth cap rejected it. Delimiter-producing callers must emit only
        after a successful push or their Markdown would remain unmatched.
        """

        # Reject excessive nesting without emitting unmatched delimiters.
        if len(self._stack) >= MAX_FRAME_DEPTH:
            return False

        # Add the frame to the context stack.
        self._stack.append(frame)

        # Maintain a per-tag count of currently open frames so that
        # _pop_to() can reject unmatched closing tags in O(1).
        tag = frame["tag"]
        self._tag_open_counts[tag] = self._tag_open_counts.get(tag, 0) + 1

        return True

    def _pop_to(self, tag):
        """Pop through the nearest match and report whether one existed."""

        # Reject unmatched closing tags without scanning the stack
        if not self._tag_open_counts.get(tag):
            return False

        # Search backward for the nearest matching frame
        for i in range(len(self._stack) - 1, 0, -1):
            if self._stack[i]["tag"] == tag:
                # Keep tag counts synchronized with removed frames.
                for frame in self._stack[i:]:
                    self._tag_open_counts[frame["tag"]] -= 1

                del self._stack[i:]
                return True

        return False

    def _close_emphasis_frame(self, frame):
        """Close an emphasis frame, dropping it if it collected no content."""

        # Compare the global emission counter now vs. when the frame opened;
        # any difference means at least one _emit() was called inside the span.
        has_content = self._content_seq != frame.get(
            "content_seq_at_open", self._content_seq
        )

        if not has_content:
            # The span opened but collected nothing -- erase from the opening
            # delimiter onward so we do not emit an empty ** or * pair.
            del self._result[frame["emphasis_result_start"] :]
            return

        # CommonMark requires that the closing delimiter not be preceded by
        # whitespace.  Relocate any trailing whitespace to after the delimiter.
        trailing = ""
        while self._result and type(self._result[-1]) is str:
            last = self._result[-1]
            rstripped = last.rstrip(self._ASCII_WHITESPACE)

            # This fragment has no trailing whitespace -- stop scanning.
            if rstripped == last:
                break

            # Accumulate trailing whitespace in front-to-back order.
            trailing = last[len(rstripped) :] + trailing

            if rstripped:
                # Replace the fragment with its trimmed version and stop.
                self._result[-1] = rstripped
                break

            # The entire fragment was whitespace -- remove it and keep going.
            self._result.pop()

        # Emit the closing delimiter (e.g. "**" or "*").
        self._emit(frame["emphasis_delim"])

        # Re-append any whitespace that was after the span content so it
        # falls outside the closed delimiter.
        if trailing:
            self._result.append(trailing)

    @staticmethod
    def _escape_cell_pipes(text):
        """Escape cell delimiters outside CommonMark code spans."""

        # Accumulate escaped fragments without rebuilding the output string.
        out = []

        # Initialize the single-pass scanner.
        i = 0
        n = len(text)

        # Index code delimiters before inspecting table separators.
        backtick_runs = build_backtick_run_index(text)

        while i < n:
            ch = text[i]

            # Keep escape pairs intact so a backslash-escaped "|" does not
            # trigger an extra escape on the next pass.
            if ch == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue

            if ch == "`":
                j = i
                # Measure the backtick run length.
                while j < n and text[j] == "`":
                    j += 1
                run = j - i

                # Find the matching closing run of the same length.
                close = find_unescaped_run(backtick_runs, j, run)
                if close is not None:
                    # Inside a code span, "|" is a literal character --
                    # copy the entire span verbatim without escaping.
                    out.append(text[i : close + run])
                    i = close + run
                    continue

                # No matching close -- not a code span; preserve the
                # raw backticks and let the outer Markdown renderer see them.
                out.append(text[i:j])
                i = j
                continue

            if ch == "|":
                # Outside code spans, "|" is a Markdown table delimiter --
                # escape it so it does not break the table structure.
                out.append("\\|")
                i += 1
                continue

            # All other characters are safe to pass through unchanged.
            out.append(ch)
            i += 1

        # Publish the escaped cell content.
        return "".join(out)

    def _close_cell_frame(self, frame):
        """Capture a completed table cell and store its text."""

        # Splice out all result tokens written since this cell was opened.
        start = frame["cell_result_start"]
        chunk = self._result[start:]
        del self._result[start:]

        if not frame["do_store"]:
            # This cell belongs to a suppressed or nested table -- discard it
            # so we do not emit empty cells or corrupt the outer table.
            return

        # Finalize the buffered tokens into a plain string and strip edges.
        text = "".join(self._finalize(chunk)).strip(self._ASCII_WHITESPACE)

        # CommonMark table cells must live on a single source line.
        # Collapse embedded newlines to spaces and then normalize runs.
        if "\n" in text:
            text = " ".join(text.split("\n"))
            text = self._CELL_WHITESPACE_RUN.sub(" ", text).strip(
                self._ASCII_WHITESPACE
            )

        # Escape cell delimiters except where code spans make them literal.
        if "|" in text:
            text = self._escape_cell_pipes(text)

        # Add the completed value to its enclosing row.
        self._stack[-1]["cells"].append(text)

    def _close_pre_frame(self, ctx, tag):
        """Render a completed code/pre/samp frame's buffered content."""

        # Join the buffered literal content
        content = "".join(ctx.get("buffer", ()))

        # Size the delimiter beyond any embedded backtick run
        run = self._longest_backtick_run(content)

        if tag == "code":
            # Inline code uses a delimiter wider than its content.
            # CommonMark requires padding around edge backticks.
            delim = "`" * (run + 1)
            pad = (
                " "
                if not content or content[0] == "`" or content[-1] == "`"
                else ""
            )

            self._emit(delim + pad + content + pad + delim)
            return

        # Fenced block -- widen the fence past the longest run of
        # backticks already present in the content
        fence = "`" * max(3, run + 1)

        # Restate list and quote prefixes on every fenced-block line.
        prefix = self._continuation_prefix(ctx)

        # Prefix every fenced line inside a list or quote
        if prefix:
            marker = (
                _QuoteMarker(prefix)
                if ctx["quote_depth"]
                else _ListIndent(prefix)
            )
            content = ("\n" + prefix).join(content.split("\n"))

        # Emit the opening fence and terminate its line.
        self._emit(fence)
        self._result.append(self.BLOCK_END)

        # Restate nesting before the code content
        if prefix:
            self._result.append(marker)

        # Emit the literal code body and terminate its final line.
        self._emit(content)
        self._result.append(self.BLOCK_END)

        # Restate nesting before the closing fence
        if prefix:
            self._result.append(marker)

        # Emit the closing fence and restore a block boundary.
        self._emit(fence)
        self._result.append(self.BLOCK_END)

    def _close_row_frame(self, frame):
        """Render a completed table row as a Markdown pipe-table line."""

        # Retrieve the cells collected while the row was open.
        cells = frame["cells"]

        if not cells:
            # An entirely empty row (no cells at all) is not useful -- drop it.
            return

        # Retrieve the enclosing table frame, if one exists.
        table = frame.get("table_frame")

        # The first row of a table is treated as the header row; CommonMark
        # requires a separator line of dashes ("---") immediately after it.
        is_header = table is None or table["table_rows"] == 0

        if table is not None:
            # Count this row so that subsequent rows know they are not headers.
            table["table_rows"] += 1

        # Use the restored parent context for row boundaries and prefixes.
        ctx = self._stack[-1]
        # Ensure the row starts on its own line within any active nesting.
        self._open_line_boundary(ctx, strong=False)
        # Emit the pipe-delimited cell values.
        self._emit("| " + " | ".join(cells) + " |")

        if is_header:
            # Emit the mandatory separator line beneath the header row.
            # Restate list or quote prefixes so it stays inside any nesting.
            self._write_boundary(ctx, strong=False)
            self._emit("| " + " | ".join(["---"] * len(cells)) + " |")

        if table is None:
            # A standalone row has no enclosing table to supply the trailing
            # paragraph boundary, so we must emit it here.
            self._write_boundary(ctx, strong=True)

    def _close_table_frame(self, table_frame=None):
        """Emit the paragraph boundary that follows a completed table."""

        parent = self._stack[-1]

        # Empty visible tables already received their only needed boundary.
        # Suppressed nested tables still need spacing inside their cell.
        if (
            table_frame is not None
            and not table_frame.get("table_rows")
            and table_frame.get("table_do_store")
        ):
            return

        if parent["do_store"]:
            # Separate the table from any following content with a blank line.
            self._write_boundary(parent, strong=True)

    def _close_stale_cell(self):
        """Close a stale cell hidden beneath malformed inline frames."""

        # Walk backward until a cell or its structural boundary is found.
        for i in range(len(self._stack) - 1, 0, -1):
            frame = self._stack[i]
            tag = frame["tag"]
            # A row or table boundary means no stale cell exists here.
            if tag in ("tr", "table"):
                return
            if tag in ("td", "th"):
                # Silently drop any interleaved inline frames above the cell.
                while len(self._stack) > i + 1:
                    # Remove the nearest orphaned inline frame.
                    orphan = self._stack[-1]

                    # Keep its open-tag counter synchronized.
                    self._tag_open_counts[orphan["tag"]] = max(
                        0,
                        self._tag_open_counts.get(orphan["tag"], 0) - 1,
                    )
                    self._stack.pop()
                # Finalize the cell before its sibling begins.
                self._pop_to(tag)
                self._close_cell_frame(frame)
                return

    def _close_stale_row(self):
        """Finalize an unterminated row before its table advances."""

        # A stale row always has a stale cell inside it -- close that first.
        self._close_stale_cell()

        # Inspect the frame exposed after closing any stale cell.
        top = self._stack[-1]

        # If the top of the stack is now a row frame, close it too.
        if top["tag"] == "tr":
            self._pop_to("tr")
            self._close_row_frame(top)

    def close(self):
        """Recover any frames left open at end-of-document, then finalize."""

        # HTML does not require all tags to be closed, so we walk the stack
        # top-down and synthesize the missing close events for each open frame.
        # Only frames that emit Markdown structure need explicit finalization;
        # list and blockquote frames just restore context silently via _pop_to.
        while len(self._stack) > 1:
            top = self._stack[-1]
            tag = top["tag"]

            # Remove the frame from the stack (and update open-tag counts).
            self._pop_to(tag)

            if top.get("emphasis_delim"):
                # Emphasis frame -- emit or drop the closing delimiter.
                self._close_emphasis_frame(top)

            elif tag in ("td", "th"):
                # Cell frame -- finalize and store its content.
                self._close_cell_frame(top)

            elif tag == "tr":
                # Row frame -- emit the pipe-table line.
                self._close_row_frame(top)

            elif tag == "table":
                # Table frame -- emit the trailing paragraph boundary.
                self._close_table_frame(top)

            elif tag in ("code", "pre", "samp") and top["do_store"]:
                # Preformatted frame -- emit the fenced code block.
                self._close_pre_frame(top, tag)

        # Hand off to the base converter to assemble the final output string.
        super().close()

    @staticmethod
    def _longest_backtick_run(text):
        """Return the longest consecutive backtick run."""

        # Track both the active run and the maximum observed width.
        longest = current = 0

        # Scan the content one character at a time
        for ch in text:
            if ch == "`":
                current += 1
                longest = max(longest, current)

            # Reset the active run on non-backtick content
            else:
                current = 0

        # Use the maximum to size a collision-free delimiter.
        return longest

    def _finalize(self, result):
        """Combine tokens into normalized Markdown lines."""

        # Track whether a line is waiting after a boundary.
        accum = None

        # Whether accum, so far, is composed only of marker fragments
        accum_is_marker = False

        # True when a marker absorbed a boundary without content.
        marker_boundary_passed = False

        # True when a complete line is waiting to be flushed.
        terminated = False

        # Set when a plain (no prefix at all) _ParaBreak has been seen since
        # accum was last extended with real content
        para_break_seen = False

        # Active list or quote prefix for the next paragraph line.
        para_break_prefix = None

        # Whether the active paragraph prefix belongs to a quote.
        para_break_in_quote = False

        # Set when a boundary arrives *after* the line was already terminated
        # -- i.e. anything beyond the single boundary that did the terminating.
        boundary_after_terminate = False

        for item in result:
            # Boundaries update state but do not immediately emit text.
            # Collect boundary state before flushing the current line
            if item == self.BLOCK_END or isinstance(item, _ParaBreak):
                if isinstance(item, _ParaBreak):
                    # The latest break carries the current nesting context.
                    if item.prefix:
                        para_break_prefix = item.prefix
                        para_break_in_quote = item.in_quote

                    else:
                        para_break_seen = True
                        para_break_prefix = None
                        para_break_in_quote = False

                # Absorb boundaries until real content arrives.
                if accum is None:
                    continue

                # Keep an unused structural marker pending
                if accum_is_marker:
                    marker_boundary_passed = True
                    continue

                # Remember boundaries beyond the one ending this line
                if terminated:
                    boundary_after_terminate = True

                terminated = True
                continue

            # Flush the previous line before adding new content.
            if terminated:
                if para_break_prefix is not None:
                    # Keep blank lines inside an active quote
                    if para_break_in_quote:
                        blank = para_break_prefix.rstrip(
                            self._ASCII_WHITESPACE
                        )
                        sep = "\n" + blank + "\n"

                    # Lists use an ordinary blank paragraph line
                    else:
                        sep = "\n\n"

                elif para_break_seen:
                    sep = "\n\n"

                # Fall back to a single line break
                else:
                    sep = "\n"

                # Emit the completed line with its chosen separator.
                yield accum.rstrip(self._ASCII_WHITESPACE) + sep

                # Seed the next line with any active list or quote prefix.
                if para_break_prefix is not None:
                    accum = (
                        _QuoteMarker(para_break_prefix)
                        if para_break_in_quote
                        else _ListIndent(para_break_prefix)
                    )
                    accum_is_marker = True
                    marker_boundary_passed = boundary_after_terminate

                else:
                    accum = None
                    accum_is_marker = False
                    marker_boundary_passed = False

                # Reset state gathered for the completed line
                terminated = False
                para_break_seen = False
                para_break_prefix = None
                para_break_in_quote = False
                boundary_after_terminate = False

            if accum is not None:
                # Determine whether this token is generated structure.
                item_is_marker = isinstance(item, _Marker)
                if (
                    marker_boundary_passed
                    and accum_is_marker
                    and item_is_marker
                ):
                    # A new marker after the old one sat through a boundary
                    # unused -- start over with this one
                    accum = item
                    accum_is_marker = True

                else:
                    # Append ordinary content to the pending line.
                    accum += item
                    accum_is_marker = accum_is_marker and item_is_marker

                marker_boundary_passed = False

            else:
                # Seed a new line with this token
                accum = item
                accum_is_marker = isinstance(item, _Marker)
                para_break_seen = False
                para_break_prefix = None
                para_break_in_quote = False

        # Flush the final content line without adding another newline.
        if accum is not None and not accum_is_marker:
            yield accum.rstrip(self._ASCII_WHITESPACE)

    def _escape_line_start(self, content):
        """Escape text that could become block syntax."""

        # Look for an ordered-list marker
        ordered = self._ORDERED_MARKER_RE.match(content)
        if ordered:
            # Escape just the '.', not the digits themselves
            dot = ordered.end() - 1
            return content[:dot] + "\\" + content[dot:]

        # Escape an unordered-list marker
        if self._BULLET_MARKER_RE.match(content):
            return "\\" + content

        # Ignore surrounding whitespace while checking the full line
        trimmed = content.strip(self._ASCII_WHITESPACE)

        # Escape thematic breaks and setext underlines
        if trimmed and self._THEMATIC_BREAK_RE.match(trimmed):
            idx = content.index(trimmed[0])
            return content[:idx] + "\\" + content[idx:]

        # Leave ordinary line starts unchanged.
        return content

    def handle_data(self, data, *args, **kwargs):
        """Store escaped text for the current context."""

        # Read all text-handling flags from the active frame.
        ctx = self._stack[-1]

        # Ignore text inside suppressed containers.
        if not ctx["do_store"]:
            return

        # Preserve literal whitespace inside code blocks
        if ctx["preserve_cr"]:
            # Buffer raw text so the closing delimiter can be sized safely.
            ctx["buffer"].append(data)
            return

        # Preserve deliberate non-breaking spaces even at block boundaries.
        if not data.strip() and "\xa0" in data:
            self._emit("\xa0")
            return

        # Collapse ordinary whitespace outside preformatted content.
        content = self.WS_TRIM.sub(" ", data)

        # Drop indentation-only text around block boundaries.
        if not content.strip() and (
            not self._result
            or self._result[-1] == self.BLOCK_END
            or isinstance(self._result[-1], (_Marker, _ParaBreak))
        ):
            return

        # Detect text that begins a fresh Markdown source line.
        is_line_start = (
            not self._result
            or self._result[-1] == self.BLOCK_END
            or isinstance(self._result[-1], (_Marker, _ParaBreak))
            or (
                type(self._result[-1]) is str
                and self._result[-1].endswith("\n")
            )
        )

        # Escape Markdown punctuation in ordinary text.
        content = self.MARKDOWN_ESCAPE.sub(r"\\\1", content)

        if is_line_start:
            # Prevent plain text from becoming a Markdown block
            content = self._escape_line_start(content)

        # Keep leading whitespace outside an emphasis delimiter.
        if ctx.get("emphasis_delim") and not ctx["emphasis_started"]:
            stripped = content.lstrip(self._ASCII_WHITESPACE)

            # Move leading whitespace before the opening delimiter
            if stripped != content:
                leading = content[: len(content) - len(stripped)]
                delim = self._result.pop()
                self._result.append(leading)
                self._result.append(delim)
                content = stripped

            if not content:
                # The close handler removes an empty span.
                return

            # Mark the emphasis span as started
            ctx["emphasis_started"] = True

        # Append the final escaped fragment to the output stream.
        self._emit(content)

    def handle_starttag(self, tag, attrs):
        """Handle an opening HTML tag."""

        # Capture the parent context before opening another frame.
        ctx = self._stack[-1]

        # Treat nested tags inside preformatted content as literal text.
        if ctx["preserve_cr"]:
            return

        # Track list type, depth, and numbering.

        if tag in ("ul", "ol"):
            # CommonMark ordered lists default to one.
            counter = 1

            if tag == "ol":
                # Read an optional starting number from ordered lists.
                start_attr = next((v for k, v in attrs if k == "start"), None)
                if start_attr is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        # Markdown list markers cannot represent negative
                        # values.
                        counter = max(0, int(start_attr))

            # Prepare the list-specific state inherited by its items.
            overrides = {
                "do_store": False,
                "list_type": tag,
                "depth": min(ctx["depth"] + 1, LIST_DEPTH_MAX),
                "counter": (counter if tag == "ol" else None),
            }

            # Only refresh list_do_store when this is the outermost list (its
            # parent isn't itself a ul/ol).
            if ctx["tag"] not in ("ul", "ol"):
                overrides["list_do_store"] = ctx["do_store"]

            # Capture indentation once at the start of a nested list chain.
            if ctx["depth"] == 0:
                overrides["list_indent_base"] = ctx["list_indent"]

            # A direct child list continues its parent item without a break.
            if ctx["do_store"] and ctx["tag"] != "li":
                self._open_line_boundary(ctx, strong=True)

            # Open the list frame and suppress whitespace-only text nodes.
            self._push_frame(self._make_frame(tag, **overrides))
            return

        # Emit a list marker and enable item content.

        if tag == "li":
            # An item value resets numbering for it and following siblings.
            if ctx["list_type"] == "ol" and ctx["counter"] is not None:
                # Read an optional per-item numbering override.
                value_attr = next((v for k, v in attrs if k == "value"), None)
                if value_attr is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        # Match the non-negative <ol start> constraint.
                        ctx["counter"] = max(0, int(value_attr))

            # Indent scales with nesting depth (depth 1 = no indent), capped at
            # LIST_DEPTH_MAX
            indent = self._indent(ctx["depth"])

            if ctx["list_type"] == "ol" and ctx["counter"] is not None:
                # Render the current ordered-list number.
                marker_text = "{}{}. ".format(indent, ctx["counter"])

            else:
                # Render a bullet for unordered or malformed list items.
                marker_text = "{}- ".format(indent)

            # Tag the marker as converter-generated structure
            marker = _ListMarker(marker_text)

            # Re-enable storage, unless something outside the list itself (e.g.
            # <head>) is suppressing content
            do_store = ctx["list_do_store"]

            # Snapshot content state for constant-time empty-item detection.
            # Gate marker emission on the return value: at MAX_FRAME_DEPTH
            # the frame is discarded and we must not append the marker,
            # otherwise there is nothing to pop it on </li>.
            if not self._push_frame(
                self._make_frame(
                    tag,
                    do_store=do_store,
                    content_seq_at_open=self._content_seq,
                    list_indent=(
                        ctx["list_indent_base"] + " " * len(marker_text)
                    ),
                )
            ):
                return

            if do_store:
                # Reuse a pending quote or list marker on this line.
                if not (
                    self._result and isinstance(self._result[-1], _Marker)
                ):
                    self._result.append(self.BLOCK_END)

                    # Restate an enclosing quote prefix
                    if ctx["quote_depth"]:
                        self._result.append(
                            self._quote_prefix(ctx["quote_depth"])
                        )

                self._result.append(marker)
            return

        # Extend a pending quote/list marker, or begin a fresh quoted line.

        if tag == "blockquote":
            # Clamp quote depth to keep generated prefixes bounded
            depth = min(ctx["quote_depth"] + 1, BLOCKQUOTE_DEPTH_MAX)

            # Open a frame carrying the increased quote depth.
            # Gate marker emission on the return value: at MAX_FRAME_DEPTH
            # the frame is discarded and we must not append a _QuoteMarker,
            # otherwise there is nothing to pop it on </blockquote>.
            new_frame = self._make_frame(tag, quote_depth=depth)
            if not self._push_frame(new_frame):
                return

            if ctx["do_store"]:
                last = self._result[-1] if self._result else None

                # Extend an existing quote prefix
                if isinstance(last, _QuoteMarker) or (
                    isinstance(last, _ParaBreak) and last.in_quote
                ):
                    if depth > ctx["quote_depth"]:
                        self._result.append(_QuoteMarker("> "))

                elif isinstance(last, _Marker):
                    self._result.append(self._quote_prefix(depth))

                # Separate a quote from preceding text.
                elif isinstance(last, str):
                    self._write_boundary(ctx, strong=True)

                    if depth > ctx["quote_depth"]:
                        self._result.append(_QuoteMarker("> "))

                # Emit the prefix directly at the start of a context.
                else:
                    self._result.append(
                        _QuoteMarker(
                            ctx["list_indent"] + self._quote_prefix(depth)
                        )
                    )
            return

        # Table section tags are transparent.

        if tag == "table":
            # Markdown cannot represent a table nested inside a cell.
            nested_in_cell = bool(
                self._tag_open_counts.get("td")
                or self._tag_open_counts.get("th")
            )

            # Separate a representable table from preceding content.
            if ctx["do_store"] and not nested_in_cell:
                self._open_line_boundary(ctx, strong=True)

            self._push_frame(
                self._make_frame(
                    tag,
                    do_store=False,
                    # Nested table cells remain suppressed.
                    table_do_store=(
                        False if nested_in_cell else ctx["do_store"]
                    ),
                    table_rows=0,
                )
            )
            return

        if tag == "tr":
            # Finalize a malformed, unterminated previous row first.
            self._close_stale_row()

            # Capture the table or container that owns the new row.
            row_ctx = self._stack[-1]

            # Remember whether this row belongs to a real table frame.
            is_table = row_ctx["tag"] == "table"

            self._push_frame(
                self._make_frame(
                    tag,
                    do_store=False,
                    cells=[],
                    # A stray row becomes a standalone one-row table.
                    table_frame=(row_ctx if is_table else None),
                    table_do_store=(
                        row_ctx["table_do_store"]
                        if is_table
                        else row_ctx["do_store"]
                    ),
                )
            )
            return

        if tag in ("td", "th"):
            # Finalize an unterminated previous cell first.
            self._close_stale_cell()

            # Capture the row expected to own the new cell.
            cell_ctx = self._stack[-1]

            if cell_ctx["tag"] == "tr":
                # Record where this cell's buffered output begins.
                self._push_frame(
                    self._make_frame(
                        tag,
                        do_store=cell_ctx["table_do_store"],
                        cell_result_start=len(self._result),
                    )
                )
                return
            # No enclosing <tr> -- this isn't really a table cell (e.g. a stray
            # <td> with no surrounding table structure at all).

        # Buffer preformatted content until its closing tag.

        if tag in ("code", "pre", "samp"):
            # Preserve raw whitespace until the matching closing tag.
            self._push_frame(
                self._make_frame(tag, preserve_cr=True, buffer=[])
            )

        # Resume text capture inside the document body.

        elif tag == "body":
            # The document body always resumes visible text capture.
            self._push_frame(self._make_frame(tag, do_store=True))

        # Suppress content inside ignored containers.

        elif tag in self.IGNORE_TAGS:
            # Ignored containers inherit context but disable text storage.
            self._push_frame(self._make_frame(tag, do_store=False))

        # Do not emit Markdown markers for suppressed content.

        if not ctx["do_store"]:
            return

        # Start block-level content on the correct boundary.
        if tag in self.BLOCK_TAGS:
            self._open_line_boundary(ctx, strong=tag in self._PARA_LIKE_TAGS)

        # Emit Markdown syntax for the current tag.

        if tag == "br":
            # CommonMark needs two trailing spaces for a visible hard break.
            self._emit("  \n" + self._continuation_prefix(ctx))

        elif tag == "hr":
            # A void <hr> supplies its own boundaries; the leading blank line
            # prevents it from becoming a setext heading.
            self._open_line_boundary(ctx, strong=True)
            self._emit("---")
            self._result.append(self.BLOCK_END)

        elif tag == "h1":
            # Render a level-one ATX heading marker.
            self._emit("# ")

        elif tag == "h2":
            # Render a level-two ATX heading marker.
            self._emit("## ")

        elif tag == "h3":
            # Render a level-three ATX heading marker.
            self._emit("### ")

        elif tag == "h4":
            # Render a level-four ATX heading marker.
            self._emit("#### ")

        elif tag == "h5":
            # Render a level-five ATX heading marker.
            self._emit("##### ")

        elif tag == "h6":
            # Render a level-six ATX heading marker.
            self._emit("###### ")

        # Open an emphasis frame for bold or italic content
        elif tag in ("strong", "b", "em", "i"):
            # A frame validates closing tags and relocates edge whitespace.
            delim = "**" if tag in ("strong", "b") else "*"

            # Emit a delimiter only when its frame passed the depth limit.
            if self._push_frame(
                self._make_frame(
                    tag,
                    emphasis_delim=delim,
                    emphasis_started=False,
                    content_seq_at_open=self._content_seq,
                    # Exact delimiter index used when removing an empty span.
                    emphasis_result_start=len(self._result),
                )
            ):
                # Buffer the opening delimiter for the matching close tag.
                self._result.append(delim)

        # Open a Markdown link when an href is available
        elif tag == "a":
            # Keep the target on a frame so nested label markup is included.
            href = next(
                (v for k, v in attrs if k == "href"),
                None,
            )

            # Sanitize the destination before emitting Markdown
            if href is not None:
                # Remove controls that browsers ignore during URL parsing.
                href = self._HREF_CONTROL_CHARS.sub("", href)

                # Strip all leading/trailing whitespace, including Unicode
                # space characters that would otherwise bypass scheme checks.
                href = href.strip()

                # Extract an explicit URI scheme when one is present.
                scheme = self._HREF_SCHEME.match(href)

                # Neutralize schemes that can execute or expose local content
                if (
                    scheme
                    and scheme.group(1).lower() in self._UNSAFE_HREF_SCHEMES
                ):
                    # Preserve link shape while neutralizing unsafe targets.
                    href = "#"

            if href is not None:
                # Angle destinations safely contain parentheses.
                safe_href = self.HREF_ESCAPE.sub(r"\\\1", href)
                target = "<{}>".format(safe_href)

                # Store the target only when its frame passes the depth limit.
                if self._push_frame(self._make_frame(tag, href=target)):
                    # Frame accepted: begin the CommonMark link label.
                    self._emit("[")

    def handle_endtag(self, tag):
        """Handle a closing HTML tag."""

        # Capture context before any pop so do_store and any buffered code/pre
        # content can still be read for this closing tag
        ctx = self._stack[-1]

        if tag == "a":
            # Find the href stored in the nearest <a> frame
            href = None

            # Search backward for the matching anchor
            for frame in reversed(self._stack):
                if frame["tag"] == "a":
                    href = frame.get("href")
                    break

            self._pop_to(tag)

            # Bare or suppressed anchors do not create link frames.
            if href is not None:
                # Complete the Markdown link
                self._emit("](" + href + ")")

            return

        # Track list type, depth, and numbering.

        if tag in ("ul", "ol"):
            # Ignore a list closer that has no corresponding open frame.
            if not self._pop_to(tag):
                return

            # Continue rendering in the restored parent context.
            parent = self._stack[-1]

            if parent["do_store"]:
                self._write_boundary(parent, strong=parent["tag"] != "li")
            return

        # Emit a list marker and enable item content.

        if tag == "li":
            # A stray closing tag with no open <li> anywhere on the stack is
            # a no-op -- nothing below should run against an unrelated frame.
            if not self._tag_open_counts.get(tag):
                return

            # Locate the actual li frame -- the top frame may be an unclosed
            # child (e.g. <em> inside <li>text<em>bold</li>).
            li_frame = next(
                (f for f in reversed(self._stack) if f["tag"] == "li"),
                ctx,
            )

            # Empty items are dropped and do not advance ordered-list
            # numbering.
            has_content = li_frame[
                "do_store"
            ] and self._content_seq != li_frame.get(
                "content_seq_at_open", self._content_seq
            )

            # Block boundary closes the item content -- only if the item
            # actually emitted a marker when it opened.
            if li_frame["do_store"]:
                self._result.append(self.BLOCK_END)

            # Pop the li frame (and any unclosed children above it).
            self._pop_to(tag)

            # The enclosing list is exposed after the item frame is removed.
            parent = self._stack[-1]

            # Increment numbering only for items that emitted content
            if parent["list_type"] == "ol" and has_content:
                parent["counter"] += 1

            return

        # Track blockquote depth and emit its prefix.
        if tag == "blockquote":
            # Restore the quote's parent context -- a stray closing tag with
            # no open <blockquote> anywhere on the stack is a no-op.
            if not self._pop_to(tag):
                return
            # Continue rendering in the restored outer context.
            parent = self._stack[-1]

            if parent["do_store"]:
                self._write_boundary(parent, strong=True)
            return

        # Close only matching table frames; ignore stray closing tags.

        if tag in ("td", "th"):
            # Ignore stray cell closers instead of emitting a block boundary.
            if ctx["tag"] == tag:
                # Remove the frame before storing its value on the row.
                self._pop_to(tag)
                self._close_cell_frame(ctx)
            return

        elif tag == "tr":
            # Recover any cell left open by malformed HTML
            self._close_stale_cell()
            row_ctx = self._stack[-1]

            if row_ctx["tag"] == "tr":
                # Remove the row before rendering it in the parent context.
                self._pop_to(tag)
                self._close_row_frame(row_ctx)
            return

        elif tag == "table":
            # Recover any row left open by malformed HTML
            self._close_stale_row()
            table_ctx = self._stack[-1]

            if table_ctx["tag"] == "table":
                # Remove the table before emitting its trailing boundary.
                self._pop_to(tag)
                self._close_table_frame(table_ctx)
            return

        # Buffer preformatted content until its closing tag.

        if tag in ("code", "pre", "samp"):
            # Render only the matching preformatted frame
            if ctx["do_store"] and ctx["tag"] == tag:
                self._close_pre_frame(ctx, tag)

            # Restore the context that preceded the preformatted element.
            self._pop_to(tag)
            return

        # Do not emit Markdown markers for suppressed content.

        if not ctx["do_store"] or ctx["preserve_cr"]:
            if tag == "body" or tag in self.IGNORE_TAGS:
                self._pop_to(tag)
            return

        # Paragraph-like tags strongly separate following bare text.
        if tag in self.BLOCK_TAGS:
            self._write_boundary(ctx, strong=tag in self._PARA_LIKE_TAGS)

        if tag in ("strong", "b", "em", "i"):
            # Only a matching emphasis frame emits a closing delimiter.
            if ctx["tag"] == tag and ctx.get("emphasis_delim"):
                self._pop_to(tag)
                self._close_emphasis_frame(ctx)
            return

        # Pop frames created by container tags.

        if tag == "body" or tag in self.IGNORE_TAGS:
            # Restore storage flags inherited from the enclosing frame.
            self._pop_to(tag)
