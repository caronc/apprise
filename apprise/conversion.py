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
from markdown import markdown
from .common import NotifyFormat


def convert_between(from_format, to_format, body):
    """
    Converts between different notification formats. If no conversion exists,
    or the selected one fails, the original text will be returned.
    """

    if from_format == NotifyFormat.MARKDOWN and to_format == NotifyFormat.HTML:
        return markdown(body)

    if from_format == NotifyFormat.TEXT and to_format == NotifyFormat.HTML:
        return text_to_html(body)

    return body


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
    return re.sub(r'\r*\n', '<br/>\r\n',
        re_table.sub(
            lambda x: re_map[x.group()], body))
