# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import re
import six
from markdown import markdown
from .common import NotifyFormat

if six.PY2:
    from HTMLParser import HTMLParser

else:
    from html.parser import HTMLParser


def convert_between(from_format, to_format, body, title=None):
    """
    Converts between different notification formats. If no conversion exists,
    or the selected one fails, the original text will be returned.

    This function returns a tuple as (title, body)
    """

    converters = {
        (NotifyFormat.MARKDOWN, NotifyFormat.HTML): markdown_to_html,
        (NotifyFormat.TEXT, NotifyFormat.HTML): text_to_html,
        (NotifyFormat.HTML, NotifyFormat.TEXT): html_to_text,
        # For now; use same converter for Markdown support
        (NotifyFormat.HTML, NotifyFormat.MARKDOWN): html_to_text,
    }

    if NotifyFormat.MARKDOWN in (from_format, to_format):
        # Tidy any exising pre-formating configuration
        title = '' if not title else title.lstrip('\r\n \t\v\b*#-')

    else:
        title = '' if not title else title

    convert = converters.get((from_format, to_format))
    title, body = convert(title=title, body=body) \
        if convert is not None else (title, body)

    return (title, body)


def markdown_to_html(body, title=None):
    """
    Handle Markdown conversions
    """

    return (
        # Title
        '' if not title else markdown(title),

        # Body
        markdown(body),
    )


def text_to_html(body, title=None):
    """
    Converts a notification body from plain text to HTML.
    """

    # Basic TEXT to HTML format map; supports keys only
    re_map = {
        # Support Ampersand
        r'&': '&amp;',

        # Spaces to &nbsp; for formatting purposes since
        # multiple spaces are treated as one an this may
        # not be the callers intention
        r' ': '&nbsp;',

        # Tab support
        r'\t': '&nbsp;&nbsp;&nbsp;',

        # Greater than and Less than Characters
        r'>': '&gt;',
        r'<': '&lt;',
    }

    # Compile our map
    re_table = re.compile(
        r'(' + '|'.join(
            map(re.escape, re_map.keys())) + r')',
        re.IGNORECASE,
    )

    # Execute our map against our body in addition to
    # swapping out new lines and replacing them with <br/>
    return (
        # Title; swap whitespace with space
        '' if not title else re.sub(
            r'[\r\n]+', ' ', re_table.sub(
                lambda x: re_map[x.group()], title)),

        # Body Formatting
        re.sub(
            r'\r*\n', '<br/>\n', re_table.sub(
                lambda x: re_map[x.group()], body)))


def html_to_text(body, title=None):
    """
    Converts a notification body from HTML to plain text.
    """

    parser = HTMLConverter()
    if six.PY2:
        # Python 2.7 requires an additional parsing to un-escape characters
        body = parser.unescape(body)

    if title:
        if six.PY2:
            # Python 2.7 requires an additional parsing to un-escape characters
            title = parser.unescape(title)

        parser.feed(title)
        parser.close()
        title = parser.converted

    parser.feed(body)
    parser.close()
    body = parser.converted

    return ('' if not title else title, body)


class HTMLConverter(HTMLParser, object):
    """An HTML to plain text converter tuned for email messages."""

    # The following tags must start on a new line
    BLOCK_TAGS = ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'div', 'td', 'th', 'code', 'pre', 'label', 'li',)

    # the folowing tags ignore any internal text
    IGNORE_TAGS = ('style', 'link', 'meta', 'title', 'html', 'head', 'script')

    # Condense Whitespace
    WS_TRIM = re.compile(r'[\s]+', re.DOTALL | re.MULTILINE)

    # Sentinel value for block tag boundaries, which may be consolidated into a
    # single line break.
    BLOCK_END = {}

    def __init__(self, **kwargs):
        super(HTMLConverter, self).__init__(**kwargs)

        # Shoudl we store the text content or not?
        self._do_store = True

        # Initialize internal result list
        self._result = []

        # Initialize public result field (not populated until close() is
        # called)
        self.converted = ""

    def close(self):
        string = ''.join(self._finalize(self._result))
        self.converted = string.strip()

        if six.PY2:
            # See https://stackoverflow.com/questions/10993612/\
            #       how-to-remove-xa0-from-string-in-python
            #
            # This is required since the unescape() nbsp; with \xa0 when
            # using Python 2.7
            self.converted = self.converted.replace(u'\xa0', u' ')

    def _finalize(self, result):
        """
        Combines and strips consecutive strings, then converts consecutive
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
                yield accum.strip() + '\n'
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
        """
        Store our data if it is not on the ignore list
        """

        # initialize our previous flag
        if self._do_store:

            # Tidy our whitespace
            content = self.WS_TRIM.sub(' ', data)
            self._result.append(content)

    def handle_starttag(self, tag, attrs):
        """
        Process our starting HTML Tag
        """
        # Toggle initial states
        self._do_store = tag not in self.IGNORE_TAGS

        if tag in self.BLOCK_TAGS:
            self._result.append(self.BLOCK_END)

        if tag == 'li':
            self._result.append('- ')

        elif tag == 'br':
            self._result.append('\n')

        elif tag == 'hr':
            if self._result:
                self._result[-1] = self._result[-1].rstrip(' ')

            self._result.append('\n---\n')

        elif tag == 'blockquote':
            self._result.append(' >')

    def handle_endtag(self, tag):
        """
        Edge case handling of open/close tags
        """
        self._do_store = True

        if tag in self.BLOCK_TAGS:
            self._result.append(self.BLOCK_END)
