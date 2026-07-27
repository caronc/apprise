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

# Convert Apprise's TEXT, HTML, and MARKDOWN formats. Service dialects are
# handled separately by ``conversion/dialect.py`` and plugin hooks.

import re

from markdown import markdown

from ..common import NotifyFormat
from ..url import URLBase
from .html import HTMLConverter, HTMLMarkdownConverter

# CommonMark syntax characters, including backslash itself.
# Plain text has no escape state, so escape every occurrence.
_COMMONMARK_ESCAPABLE_RE = re.compile(r"([\\_*\[\]()~`>#+=|{}.!-])")


def convert_between(from_format, to_format, content):
    """Convert content between supported Apprise formats.

    The original content is returned when no converter exists for the pair.
    """

    # Map each supported format pair to its converter
    converters = {
        (NotifyFormat.MARKDOWN, NotifyFormat.HTML): markdown_to_html,
        (NotifyFormat.TEXT, NotifyFormat.HTML): text_to_html,
        (NotifyFormat.HTML, NotifyFormat.TEXT): html_to_text,
        (NotifyFormat.HTML, NotifyFormat.MARKDOWN): html_to_markdown,
        (NotifyFormat.TEXT, NotifyFormat.MARKDOWN): text_to_markdown,
    }

    # Fetch the converter registered for this format pair.
    convert = converters.get((from_format, to_format))

    # Preserve the original content when no conversion is available
    return convert(content) if convert else content


def markdown_to_html(content):
    """Convert Markdown content to HTML."""

    # Enable notification-friendly line-break and table extensions.
    return markdown(
        content,
        extensions=["markdown.extensions.nl2br", "markdown.extensions.tables"],
    )


def text_to_html(content):
    """Convert plain text content to HTML."""

    # First eliminate any carriage returns
    return URLBase.escape_html(content, convert_new_lines=True)


def text_to_markdown(content):
    """Converts specified content from plain text to CommonMark.

    Escapes CommonMark-significant characters, including backslashes, so
    plain text renders literally in Markdown destinations.
    """

    return _COMMONMARK_ESCAPABLE_RE.sub(r"\\\1", content)


def html_to_text(content):
    """Convert HTML content to plain text."""

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
