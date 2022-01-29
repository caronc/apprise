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


def convert_between(from_format, to_format, body):
    """
    Converts between different notification formats. If no conversion exists,
    or the selected one fails, the original text will be returned.
    """

    converters = {
        (NotifyFormat.MARKDOWN, NotifyFormat.HTML): markdown,
        (NotifyFormat.TEXT, NotifyFormat.HTML): text_to_html,
        (NotifyFormat.HTML, NotifyFormat.TEXT): html_to_text,
        # For now; use same converter for Markdown support
        (NotifyFormat.HTML, NotifyFormat.MARKDOWN): html_to_text,
    }

    convert = converters.get((from_format, to_format))
    return convert(body) if convert is not None else body


def text_to_html(body):
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
    return re.sub(
        r'\r*\n', '<br/>\r\n', re_table.sub(lambda x: re_map[x.group()], body))


def html_to_text(body):
    """
    Converts a notification body from HTML to plain text.
    """

    parser = HTMLConverter()
    parser.feed(body)
    parser.close()
    result = parser.converted

    return result


class HTMLConverter(HTMLParser, object):
    """An HTML to plain text converter tuned for email messages."""

    # The following tags must start on a new line
    BLOCK_TAGS = ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                  'div' 'tr', 'th', 'code', 'pre', 'label')

    # the folowing tags ignore any internal text
    IGNORE_TAGS = ('style', 'link', 'meta', 'title', 'html', 'head', 'script')

    # Condense Whitespace
    WS_TRIM = re.compile(r'[\s]+', re.DOTALL | re.MULTILINE)

    def __init__(self, **kwargs):
        super(HTMLConverter, self).__init__(**kwargs)

        # Shoudl we store the text content or not?
        self._do_store = True

        # Track whether we started a block tag and moved into a non-block style
        # we need to write a new_line and flip the dirty switch
        self._dirty_newline = False

        # Track entries pasted on line
        self._line_paste_count = 0

        self.converted = ""

    def close(self):
        # Removes all html before the last "}". Some HTML can return additional
        # style information with text output.
        self.converted = str(self.converted).split('}')[-1].rstrip()

    def handle_data(self, data, *args, **kwargs):
        """
        Store our data if it is not on the ignore list
        """

        # initialize our previous flag
        if self._do_store:

            # Tidy our whitespace
            content = self.WS_TRIM.sub(' ', data)

            # if self._dirty_newline and self._line_paste_count > 0:
            #     self.converted += '\n'
            #     self._line_paste_count = 0
            #     self._dirty_newline = False

            if content:
                self.converted += content \
                    if self._line_paste_count > 0 else content.lstrip()

                # Track our writes
                self._line_paste_count += 1

    def handle_starttag(self, tag, attrs):
        """
        Process our starting HTML Tag
        """
        # Toggle initial states
        self._do_store = False

        if tag not in self.IGNORE_TAGS:
            # Process our data
            self._do_store = True

            if tag == 'li':
                self.converted += '- '
                self._dirty_newline = True

            elif tag == 'br':
                self._dirty_newline = True
                self._line_paste_count = 1

            elif tag in self.BLOCK_TAGS:
                self._dirty_newline = True

            elif tag == 'blockquote':
                self.converted += ' >'
                self._dirty_newline = True

            elif self._dirty_newline:
                self.converted += '\n'
                self._line_paste_count = 0
                self._dirty_newline = False

    def handle_endtag(self, tag):
        """
        Edge case handling of open/close tags
        """
        if tag == 'br':
            # Handle <br/> entries
            self.converted += '\n'
            self._line_paste_count = 0
            self._dirty_newline = False

        elif tag in self.BLOCK_TAGS and self._dirty_newline:
            self.converted += '\n'
            self._line_paste_count = 0
            self._dirty_newline = False
