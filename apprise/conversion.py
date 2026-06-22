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

    # Fetch the requested converter
    convert = converters.get((from_format, to_format))

    # Preserve the original content when no conversion is available
    return convert(content) if convert else content


def markdown_to_html(content):
    """Converts specified content from markdown to HTML."""

    # Enable line-break and table extensions used by notification content
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

    # Initialize our plain-text parser
    parser = HTMLConverter()

    # Feed and finalize the HTML document
    parser.feed(content)
    parser.close()

    # Return the converted content
    return parser.converted


def html_to_markdown(content):
    """Converts a content from HTML to Markdown."""

    # Initialize our Markdown parser
    parser = HTMLMarkdownConverter()

    # Feed and finalize the HTML document
    parser.feed(content)
    parser.close()

    # Return the converted content
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

        # Initialize the base HTML parser
        super().__init__(**kwargs)

        # Shoudl we store the text content or not?
        self._do_store = True

        # Initialize internal result list
        self._result = []

        # Initialize public result field (not populated until close() is
        # called)
        self.converted = ""

    def close(self):
        """Finalize the converted content."""

        # Combine all buffered content
        string = "".join(self._finalize(self._result))

        # Store the normalized result
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

        # initialize our previous flag
        if self._do_store:
            # Tidy our whitespace
            content = self.WS_TRIM.sub(" ", data)
            self._result.append(content)

    def handle_starttag(self, tag, attrs):
        """Process our starting HTML Tag."""
        # Toggle initial states
        self._do_store = tag not in self.IGNORE_TAGS

        if tag in self.BLOCK_TAGS:
            self._result.append(self.BLOCK_END)

        if tag == "li":
            self._result.append("- ")

        elif tag == "br":
            self._result.append("\n")

        elif tag == "hr":
            if self._result and isinstance(self._result[-1], str):
                self._result[-1] = self._result[-1].rstrip(" ")

            self._result.append("\n---\n")

        elif tag == "blockquote":
            self._result.append(" >")

    def handle_endtag(self, tag):
        """Edge case handling of open/close tags."""
        self._do_store = True

        if tag in self.BLOCK_TAGS:
            self._result.append(self.BLOCK_END)


class HTMLMarkdownConverter(HTMLConverter):
    """An HTML to Markdown converter tuned for notification messages."""

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
    _THEMATIC_BREAK_RE = re.compile(r"^([-=])(?:[ \t]*\1){2,}$")

    # Collapse ASCII whitespace when flattening table cells.
    _CELL_WHITESPACE_RUN = re.compile(r"[ \t\r\f\v]+")

    # Escape angle-bracket link destinations.
    HREF_ESCAPE = re.compile(r"([\\<>])")

    # Remove control characters that invalidate link destinations.
    _HREF_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

    # Detect URI schemes before sanitizing links.
    _HREF_SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")

    # Block executable and local URI schemes while allowing app links.
    _UNSAFE_HREF_SCHEMES = frozenset(
        {"javascript", "vbscript", "data", "file"}
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

        # Apply tag-specific frame state.
        frame.update(overrides)
        return frame

    def _indent(self, depth):
        """Return cached indentation for a list depth."""

        # Convert the one-based depth into a cache index
        idx = max(depth - 1, 0)

        # Reference the cache locally for repeated access
        cache = self._indent_cache

        # Populate any missing indentation levels
        while len(cache) <= idx:
            cache.append(cache[-1] + "  ")

        # Return the requested indentation
        return cache[idx]

    def _quote_prefix(self, depth):
        """Return the prefix for a quote depth."""

        # Normalize the requested quote depth
        idx = max(depth, 0)

        # Reference the cache locally for repeated access
        cache = self._quote_prefix_cache

        # Populate any missing quote levels
        while len(cache) <= idx:
            cache.append(_QuoteMarker(cache[-1] + "> "))

        # Return the requested quote prefix
        return cache[idx]

    def _continuation_prefix(self, ctx):
        """Return the prefix for a continuation line."""

        # Start with the active list indentation
        prefix = ctx["list_indent"]

        # Add any active blockquote prefix
        if ctx["quote_depth"]:
            prefix += self._quote_prefix(ctx["quote_depth"])

        # Return the combined continuation prefix
        return prefix

    def _write_boundary(self, ctx, strong=False):
        """Append a line or paragraph boundary."""

        # Resolve the prefix needed by the next line
        prefix = self._continuation_prefix(ctx)

        # Write an ordinary line boundary
        if not strong:
            self._result.append(self.BLOCK_END)

            # Restate any active quote or list prefix
            if prefix:
                self._result.append(
                    _QuoteMarker(prefix)
                    if ctx["quote_depth"]
                    else _ListIndent(prefix)
                )

            # The ordinary boundary is complete
            return

        # Preserve nesting across a paragraph boundary
        if prefix:
            self._result.append(
                _ParaBreak(prefix, in_quote=bool(ctx["quote_depth"]))
            )

        # Use the shared top-level paragraph boundary
        else:
            self._result.append(self.PARA_BREAK)

    def _open_line_boundary(self, ctx, strong=False):
        """Start a block unless it can join a marker."""

        # Keep pending list and quote markers on the same line
        if self._result and isinstance(self._result[-1], _Marker):
            return  # suppress; marker and content stay on one line

        # Start a new line or paragraph
        self._write_boundary(ctx, strong=strong)

    def _emit(self, text):
        """Append content and update the content sequence."""

        # Append real content to the output buffer
        self._result.append(text)

        # Record that the active frames produced content
        self._content_seq += 1

    def _push_frame(self, frame):
        """Push a frame and track its tag."""

        # Push the new parsing context
        self._stack.append(frame)

        # Track the number of open frames for this tag
        tag = frame["tag"]
        self._tag_open_counts[tag] = self._tag_open_counts.get(tag, 0) + 1

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

                # Remove the matching frame and its descendants
                del self._stack[i:]
                return True

        return False

    def _close_emphasis_frame(self, frame):
        """Close an emphasis frame with content."""

        # Determine whether the span emitted real content
        has_content = self._content_seq != frame.get(
            "content_seq_at_open", self._content_seq
        )

        if not has_content:
            # Remove the opening delimiter and any empty nested tokens.
            del self._result[frame["emphasis_result_start"] :]
            return

        # Collect whitespace that belongs outside the closing delimiter
        trailing = ""
        while self._result and type(self._result[-1]) is str:
            last = self._result[-1]
            rstripped = last.rstrip(self._ASCII_WHITESPACE)

            # Stop once the fragment has no trailing whitespace
            if rstripped == last:
                break

            # Prepend whitespace gathered from this fragment
            trailing = last[len(rstripped) :] + trailing

            # Keep any non-whitespace portion in place
            if rstripped:
                self._result[-1] = rstripped
                break

            # Drop fragments containing only whitespace
            self._result.pop()

        # Emit the closing emphasis delimiter
        self._emit(frame["emphasis_delim"])

        # Restore trailing whitespace outside the span
        if trailing:
            self._result.append(trailing)

    @classmethod
    def _escape_cell_pipes(cls, text):
        """Escape cell delimiters outside CommonMark code spans."""

        out = []
        i = 0
        n = len(text)
        backtick_runs = cls._build_backtick_run_index(text)

        while i < n:
            ch = text[i]

            if ch == "\\" and i + 1 < n:
                out.append(text[i : i + 2])
                i += 2
                continue

            if ch == "`":
                j = i
                while j < n and text[j] == "`":
                    j += 1
                run = j - i

                close = cls._find_unescaped_run(backtick_runs, j, run)
                if close is not None:
                    # Pipes are already literal inside code spans.
                    out.append(text[i : close + run])
                    i = close + run
                    continue

                # Preserve unmatched backticks as literal text.
                out.append(text[i:j])
                i = j
                continue

            if ch == "|":
                out.append("\\|")
                i += 1
                continue

            out.append(ch)
            i += 1

        return "".join(out)

    def _close_cell_frame(self, frame):
        """Capture a completed table cell."""

        # Extract tokens written since this cell opened
        start = frame["cell_result_start"]
        chunk = self._result[start:]
        del self._result[start:]

        if not frame["do_store"]:
            # Suppressed tables must not emit empty cells.
            return

        # Finalize the cell into a single Markdown fragment
        text = "".join(self._finalize(chunk)).strip(self._ASCII_WHITESPACE)

        # Table cells must remain on one Markdown source line.
        if "\n" in text:
            text = " ".join(text.split("\n"))
            text = self._CELL_WHITESPACE_RUN.sub(" ", text).strip(
                self._ASCII_WHITESPACE
            )

        # Escape cell delimiters except where code spans make them literal.
        if "|" in text:
            text = self._escape_cell_pipes(text)

        # Add the completed cell to its row
        self._stack[-1]["cells"].append(text)

    def _close_pre_frame(self, ctx, tag):
        """Render a completed code/pre/samp frame's buffered content."""

        # Join the buffered literal content
        content = "".join(ctx.get("buffer", ()))

        # Size the delimiter beyond any embedded backtick run
        run = self._longest_backtick_run(content)

        if tag == "code":
            # CommonMark requires padding around edge backticks.
            delim = "`" * (run + 1)
            pad = (
                " "
                if not content or content[0] == "`" or content[-1] == "`"
                else ""
            )

            # Emit the complete inline code span
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

        # Emit the opening fence
        self._emit(fence)
        self._result.append(self.BLOCK_END)

        # Restate nesting before the code content
        if prefix:
            self._result.append(marker)

        # Emit the literal block content
        self._emit(content)
        self._result.append(self.BLOCK_END)

        # Restate nesting before the closing fence
        if prefix:
            self._result.append(marker)

        # Emit the closing fence and boundary
        self._emit(fence)
        self._result.append(self.BLOCK_END)

    def _close_row_frame(self, frame):
        """Render a completed table row."""

        # Fetch all cells collected for this row
        cells = frame["cells"]

        # Drop rows that never opened a cell
        if not cells:
            return  # an entirely empty row (no cells at all) is dropped

        # Identify whether this is the table's header row
        table = frame.get("table_frame")
        is_header = table is None or table["table_rows"] == 0

        # Advance the enclosing table's row count
        if table is not None:
            table["table_rows"] += 1

        # Emit the completed row in the parent context
        ctx = self._stack[-1]
        self._open_line_boundary(ctx, strong=False)
        self._emit("| " + " | ".join(cells) + " |")

        # Add the required separator after the header row
        if is_header:
            # Preserve list or quote prefixes on the separator line.
            self._write_boundary(ctx, strong=False)
            self._emit("| " + " | ".join(["---"] * len(cells)) + " |")

        if table is None:
            # A standalone row needs the same trailing boundary as a table.
            self._write_boundary(ctx, strong=True)

    def _close_table_frame(self):
        """Finish a table boundary."""

        # Restore the context surrounding the table
        parent = self._stack[-1]

        # Separate any following content from the table
        if parent["do_store"]:
            self._write_boundary(parent, strong=True)

    def _close_stale_cell(self):
        """Close an implicitly terminated cell."""

        # Inspect the current frame for an unclosed cell
        top = self._stack[-1]

        # Finalize the cell before its sibling begins
        if top["tag"] in ("td", "th"):
            self._pop_to(top["tag"])
            self._close_cell_frame(top)

    def _close_stale_row(self):
        """Close an implicitly terminated row."""

        # Close any cell still open in the row
        self._close_stale_cell()

        # Inspect the remaining top-level frame
        top = self._stack[-1]

        # Finalize the row before its sibling begins
        if top["tag"] == "tr":
            self._pop_to("tr")
            self._close_row_frame(top)

    def close(self):
        """Close malformed frames before finalizing output."""

        # Recover frames left open at the end of the document
        while len(self._stack) > 1:
            top = self._stack[-1]
            tag = top["tag"]

            # Remove the current frame from the active stack
            self._pop_to(tag)

            # Finalize content captured by special frames
            if top.get("emphasis_delim"):
                self._close_emphasis_frame(top)

            elif tag in ("td", "th"):
                self._close_cell_frame(top)

            elif tag == "tr":
                self._close_row_frame(top)

            elif tag == "table":
                self._close_table_frame()

            elif tag in ("code", "pre", "samp") and top["do_store"]:
                self._close_pre_frame(top, tag)

        # Let the base converter assemble the final output
        super().close()

    @staticmethod
    def _longest_backtick_run(text):
        """Return the longest consecutive backtick run."""

        # Track both the active and longest runs
        longest = current = 0

        # Scan the content one character at a time
        for ch in text:
            if ch == "`":
                current += 1
                longest = max(longest, current)

            # Reset the active run on non-backtick content
            else:
                current = 0

        # Return the delimiter width already present in the content
        return longest

    @classmethod
    def _build_backtick_run_index(cls, text):
        """Index unescaped backtick runs by width in one pass."""

        index = {}
        i = 0
        n = len(text)

        while i < n:
            ch = text[i]

            # Consume escapes as pairs so escaped delimiters cannot match.
            if ch == "\\" and i + 1 < n:
                i += 2
                continue

            if ch == "`":
                j = i
                while j < n and text[j] == "`":
                    j += 1
                index.setdefault(j - i, []).append(i)
                i = j
                continue

            i += 1

        return index

    @staticmethod
    def _find_unescaped_run(index, start, run):
        """Find the next indexed backtick run of the requested width."""

        positions = index.get(run)
        if not positions:
            return None

        pos = bisect_left(positions, start)
        return positions[pos] if pos < len(positions) else None

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

        # Process each buffered content or boundary token
        for item in result:
            # Collect boundary state before flushing the current line
            if item == self.BLOCK_END or isinstance(item, _ParaBreak):
                # Record the strongest paragraph boundary in this run
                if isinstance(item, _ParaBreak):
                    # The latest break carries the current nesting context.
                    if item.prefix:
                        # Keep the prefix required by the next line
                        para_break_prefix = item.prefix
                        para_break_in_quote = item.in_quote

                    # Record a top-level paragraph boundary
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
                # Resolve the separator for a prefixed paragraph
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

                # Use a blank line for a top-level paragraph break
                elif para_break_seen:
                    sep = "\n\n"

                # Fall back to a single line break
                else:
                    sep = "\n"

                # Emit the completed line and separator
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

                # Start without a structural prefix
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

            # Append this token to the active line
            if accum is not None:
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
                    # Combine consecutive string fragments
                    accum += item
                    accum_is_marker = accum_is_marker and item_is_marker

                marker_boundary_passed = False

            # Start a new string accumulation.
            else:
                # Seed a new line with this token
                accum = item
                accum_is_marker = isinstance(item, _Marker)
                para_break_seen = False
                para_break_prefix = None
                para_break_in_quote = False

        # Emit the final non-marker content without a trailing newline.
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

        # Return ordinary text unchanged
        return content

    def handle_data(self, data, *args, **kwargs):
        """Store escaped text for the current context."""

        # Read formatting state from the current frame.
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
            # Separate leading whitespace from the emphasized content
            stripped = content.lstrip(self._ASCII_WHITESPACE)

            # Move leading whitespace before the opening delimiter
            if stripped != content:
                leading = content[: len(content) - len(stripped)]
                delim = self._result.pop()
                self._result.append(leading)
                self._result.append(delim)
                content = stripped

            # Drop an emphasis span that still has no real content
            if not content:
                # The close handler removes an empty span.
                return

            # Mark the emphasis span as started
            ctx["emphasis_started"] = True

        # Store the escaped text fragment
        self._emit(content)

    def handle_starttag(self, tag, attrs):
        """Handle an opening HTML tag."""

        # Capture the parent context before pushing a new frame.
        ctx = self._stack[-1]

        # Treat nested tags inside preformatted content as literal text.
        if ctx["preserve_cr"]:
            return

        # Track list type, depth, and numbering.

        if tag in ("ul", "ol"):
            # CommonMark ordered lists default to one.
            counter = 1

            # Read an explicit starting number for ordered lists
            if tag == "ol":
                start_attr = next((v for k, v in attrs if k == "start"), None)
                if start_attr is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        # Markdown list markers cannot represent negative
                        # values.
                        counter = max(0, int(start_attr))

            # Prepare the new list context
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

            # Activate the list context
            self._push_frame(self._make_frame(tag, **overrides))
            return

        # Emit a list marker and enable item content.

        if tag == "li":
            # An item value resets numbering for it and following siblings.
            if ctx["list_type"] == "ol" and ctx["counter"] is not None:
                # Read an item-specific number override
                value_attr = next((v for k, v in attrs if k == "value"), None)
                if value_attr is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        # Match the non-negative <ol start> constraint.
                        ctx["counter"] = max(0, int(value_attr))

            # Indent scales with nesting depth (depth 1 = no indent), capped at
            # LIST_DEPTH_MAX
            indent = self._indent(ctx["depth"])

            # Build the marker for the active list type
            if ctx["list_type"] == "ol" and ctx["counter"] is not None:
                marker_text = "{}{}. ".format(indent, ctx["counter"])

            else:
                marker_text = "{}- ".format(indent)

            # Tag the marker as converter-generated structure
            marker = _ListMarker(marker_text)

            # Re-enable storage, unless something outside the list itself (e.g.
            # <head>) is suppressing content
            do_store = ctx["list_do_store"]

            # Snapshot content state for constant-time empty-item detection.
            self._push_frame(
                self._make_frame(
                    tag,
                    do_store=do_store,
                    content_seq_at_open=self._content_seq,
                    list_indent=(
                        ctx["list_indent_base"] + " " * len(marker_text)
                    ),
                )
            )

            if do_store:
                # Reuse a pending quote or list marker on this line.
                if not (
                    self._result and isinstance(self._result[-1], _Marker)
                ):
                    # Start a fresh line for this list item
                    self._result.append(self.BLOCK_END)

                    # Restate an enclosing quote prefix
                    if ctx["quote_depth"]:
                        self._result.append(
                            self._quote_prefix(ctx["quote_depth"])
                        )

                # Append the item marker before its content
                self._result.append(marker)
            return

        # Extend a pending quote/list marker, or begin a fresh quoted line.

        if tag == "blockquote":
            # Clamp quote depth to keep generated prefixes bounded
            depth = min(ctx["quote_depth"] + 1, BLOCKQUOTE_DEPTH_MAX)

            # Activate the new quote context
            new_frame = self._make_frame(tag, quote_depth=depth)
            self._push_frame(new_frame)

            # Emit a prefix only when this context stores content
            if ctx["do_store"]:
                # Inspect the token preceding this quote
                last = self._result[-1] if self._result else None

                # Extend an existing quote prefix
                if isinstance(last, _QuoteMarker) or (
                    isinstance(last, _ParaBreak) and last.in_quote
                ):
                    if depth > ctx["quote_depth"]:
                        self._result.append(_QuoteMarker("> "))

                # Add the quote prefix after another structural marker
                elif isinstance(last, _Marker):
                    self._result.append(self._quote_prefix(depth))

                # Separate a quote from preceding text.
                elif isinstance(last, str):
                    # Write the boundary using ctx's own (pre-nesting) depth.
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

            # Separate the table from preceding content
            if ctx["do_store"] and not nested_in_cell:
                self._open_line_boundary(ctx, strong=True)

            # Activate a table context and suppress formatting whitespace
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

            # Inspect the context containing this row
            row_ctx = self._stack[-1]

            # Track whether the row belongs to a table
            is_table = row_ctx["tag"] == "table"

            # Activate a row context and collect its cells
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

            # Inspect the context containing this cell
            cell_ctx = self._stack[-1]

            # Capture cell content only inside a row
            if cell_ctx["tag"] == "tr":
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
            self._push_frame(
                self._make_frame(tag, preserve_cr=True, buffer=[])
            )

        # Resume text capture inside the document body.

        elif tag == "body":
            self._push_frame(self._make_frame(tag, do_store=True))

        # Suppress content inside ignored containers.

        elif tag in self.IGNORE_TAGS:
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

        # Emit ATX heading markers
        elif tag == "h1":
            self._emit("# ")

        elif tag == "h2":
            self._emit("## ")

        elif tag == "h3":
            self._emit("### ")

        elif tag == "h4":
            self._emit("#### ")

        elif tag == "h5":
            self._emit("##### ")

        elif tag == "h6":
            self._emit("###### ")

        # Open an emphasis frame for bold or italic content
        elif tag in ("strong", "b", "em", "i"):
            # A frame validates closing tags and relocates edge whitespace.
            delim = "**" if tag in ("strong", "b") else "*"

            # Track the delimiter and output position for this span
            self._push_frame(
                self._make_frame(
                    tag,
                    emphasis_delim=delim,
                    emphasis_started=False,
                    content_seq_at_open=self._content_seq,
                    # Exact delimiter index used when removing an empty span.
                    emphasis_result_start=len(self._result),
                )
            )

            # Emit the opening emphasis delimiter
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
                # Remove controls that invalidate angle-bracket destinations
                href = self._HREF_CONTROL_CHARS.sub("", href)

                # Match browser URL parsing by trimming ASCII whitespace.
                href = href.strip(self._ASCII_WHITESPACE)

                # Identify any explicit URI scheme
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

                # Track the destination until the closing anchor
                self._push_frame(self._make_frame(tag, href=target))

                # Emit the opening link-label delimiter
                self._emit("[")

    def handle_endtag(self, tag):
        """Handle a closing HTML tag."""

        # Capture context before any pop so do_store and any buffered code/pre
        # content can still be read for this closing tag
        ctx = self._stack[-1]

        # Close the nearest open link frame.
        if tag == "a":
            # Find the href stored in the nearest <a> frame
            href = None

            # Search backward for the matching anchor
            for frame in reversed(self._stack):
                if frame["tag"] == "a":
                    href = frame.get("href")
                    break

            # Remove the anchor and any malformed child frames
            self._pop_to(tag)

            # Bare or suppressed anchors do not create link frames.
            if href is not None:
                # Complete the Markdown link
                self._emit("](" + href + ")")

            return

        # Track list type, depth, and numbering.

        if tag in ("ul", "ol"):
            # Restore the list's parent context.
            if not self._pop_to(tag):
                return
            parent = self._stack[-1]

            # Separate following content when storage is active
            if parent["do_store"]:
                self._write_boundary(parent, strong=parent["tag"] != "li")
            return

        # Emit a list marker and enable item content.

        if tag == "li":
            # A stray closing tag with no open <li> anywhere on the stack is
            # a no-op -- nothing below should run against an unrelated frame.
            if not self._tag_open_counts.get(tag):
                return

            # Empty items are dropped and do not advance ordered-list
            # numbering.
            has_content = ctx["do_store"] and self._content_seq != ctx.get(
                "content_seq_at_open", self._content_seq
            )

            # Block boundary closes the item content -- only if the item
            # actually emitted a marker when it opened
            if ctx["do_store"]:
                self._result.append(self.BLOCK_END)

            # Pop the li frame; parent ul/ol frame is now on top
            self._pop_to(tag)

            # Advance the ordered-list counter in the parent frame
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
            parent = self._stack[-1]

            # Separate following content from the completed quote
            if parent["do_store"]:
                self._write_boundary(parent, strong=True)
            return

        # Close only matching table frames; ignore stray closing tags.

        if tag in ("td", "th"):
            # Ignore stray cell closers instead of emitting a block boundary.
            if ctx["tag"] == tag:
                self._pop_to(tag)
                self._close_cell_frame(ctx)
            return

        elif tag == "tr":
            # Recover any cell left open by malformed HTML
            self._close_stale_cell()
            row_ctx = self._stack[-1]

            # Finalize the matching row
            if row_ctx["tag"] == "tr":
                self._pop_to(tag)
                self._close_row_frame(row_ctx)
            return

        elif tag == "table":
            # Recover any row left open by malformed HTML
            self._close_stale_row()
            table_ctx = self._stack[-1]

            # Finalize the matching table
            if table_ctx["tag"] == "table":
                self._pop_to(tag)
                self._close_table_frame()
            return

        # Buffer preformatted content until its closing tag.

        if tag in ("code", "pre", "samp"):
            # Render only the matching preformatted frame
            if ctx["do_store"] and ctx["tag"] == tag:
                self._close_pre_frame(ctx, tag)

            # Restore the context surrounding the code block
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
            self._pop_to(tag)
