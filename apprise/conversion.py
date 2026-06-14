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

from html.parser import HTMLParser
import re

from markdown import markdown

from .common import NotifyFormat
from .url import URLBase


def convert_between(from_format, to_format, content):
    """Converts between different suported formats. If no conversion exists, or
    the selected one fails, the original text will be returned.

    This function returns the content translated (if required)
    """

    converters = {
        (NotifyFormat.MARKDOWN, NotifyFormat.HTML): markdown_to_html,
        (NotifyFormat.TEXT, NotifyFormat.HTML): text_to_html,
        (NotifyFormat.HTML, NotifyFormat.TEXT): html_to_text,
        (NotifyFormat.HTML, NotifyFormat.MARKDOWN): html_to_markdown,
    }

    convert = converters.get((from_format, to_format))
    return convert(content) if convert else content


def markdown_to_html(content):
    """Converts specified content from markdown to HTML."""
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

    parser = HTMLConverter()
    parser.feed(content)
    parser.close()
    return parser.converted


def html_to_markdown(content):
    """Converts a content from HTML to Markdown."""

    parser = HTMLMarkdownConverter()
    parser.feed(content)
    parser.close()
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
        super().__init__(**kwargs)

        # Shoudl we store the text content or not?
        self._do_store = True

        # Initialize internal result list
        self._result = []

        # Initialize public result field (not populated until close() is
        # called)
        self.converted = ""

    def close(self):
        string = "".join(self._finalize(self._result))
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
    """An HTML to Markdown converter tuned for email messages."""

    # Override BLOCK_TAGS to exclude 'code' (handled inline with backticks)
    # and include 'samp' (treated as a fenced pre block like 'pre').
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
        "pre",
        "samp",
        "label",
        "li",
    )

    # Escape content characters that carry special meaning in Markdown
    MARKDOWN_ESCAPE = re.compile(r"([`*#])", re.DOTALL | re.MULTILINE)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # href value of the current <a> tag; empty string means no link
        self._link = ""

        # True while inside a <code>, <pre>, or <samp> block so that
        # carriage returns in the content are preserved rather than
        # collapsed by WS_TRIM
        self._preserve_cr = False

    def handle_data(self, data, *args, **kwargs):
        """Store data, escaping Markdown special characters."""

        if not self._do_store:
            return

        # Preserve whitespace literally inside code/pre blocks;
        # collapse whitespace runs to a single space everywhere else
        content = data if self._preserve_cr else self.WS_TRIM.sub(" ", data)

        # Escape Markdown special characters only outside code/pre blocks --
        # content inside backtick/fence delimiters is already treated as
        # literal by all Markdown parsers; escaping there produces wrong output
        if not self._preserve_cr:
            content = self.MARKDOWN_ESCAPE.sub(r"\\\1", content)

        # Wrap in link syntax when we are inside an <a href="..."> tag
        if self._link:
            self._result.append("[" + content + "]" + self._link)

        else:
            self._result.append(content)

    def handle_starttag(self, tag, attrs):
        """Process a starting HTML tag."""

        # Determine whether text content inside this tag should be kept
        self._do_store = tag not in self.IGNORE_TAGS
        self._link = ""

        # Block-level elements force a line break before their content
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
            self._result.append("> ")

        elif tag == "h1":
            self._result.append("# ")

        elif tag == "h2":
            self._result.append("## ")

        elif tag == "h3":
            self._result.append("### ")

        elif tag == "h4":
            self._result.append("#### ")

        elif tag == "h5":
            self._result.append("##### ")

        elif tag == "h6":
            self._result.append("###### ")

        elif tag in ("strong", "b"):
            self._result.append("**")

        elif tag in ("em", "i"):
            self._result.append("*")

        elif tag == "code":
            # Inline code -- no block boundary, just wrap in backticks
            self._result.append("`")
            self._preserve_cr = True

        elif tag in ("pre", "samp"):
            # Fenced code block -- the BLOCK_END above separates it from
            # preceding content; a second BLOCK_END after the fence
            # marker ensures the content starts on its own line
            self._result.append("```")
            self._result.append(self.BLOCK_END)
            self._preserve_cr = True

        elif tag == "a":
            # Build the link target from the href attribute
            href = next(
                (v for k, v in attrs if k == "href"),
                None,
            )
            if href is not None:
                self._link = "(" + href + ")"

    def handle_endtag(self, tag):
        """Edge case handling of close tags."""

        self._do_store = True
        self._link = ""

        # Block-level elements force a line break after their content
        if tag in self.BLOCK_TAGS:
            self._result.append(self.BLOCK_END)

        if tag in ("strong", "b"):
            self._result.append("**")

        elif tag in ("em", "i"):
            self._result.append("*")

        elif tag == "code":
            self._result.append("`")
            self._preserve_cr = False

        elif tag in ("pre", "samp"):
            # The BLOCK_END from BLOCK_TAGS above ends the content line;
            # the closing fence and a second BLOCK_END close the block
            self._result.append("```")
            self._result.append(self.BLOCK_END)
            self._preserve_cr = False
