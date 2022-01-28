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

from apprise import NotifyFormat
from apprise.conversion import convert_between

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_html_to_text():
    """conversion: Test HTML to plain text
    """

    def convert(body):
        return convert_between(NotifyFormat.HTML, NotifyFormat.TEXT, body)

    assert convert("No HTML code here.") == "No HTML code here."

    clist = convert("<ul><li>Lots and lots</li><li>of lists.</li></ul>")
    assert "Lots and lots" in clist
    assert "of lists." in clist

    assert "To be or not to be." in convert(
        "<blockquote>To be or not to be.</blockquote>")

    cspace = convert(
        "<h2>Fancy heading</h2>"
        "<p>And a paragraph too.<br>Plus line break.</p>")
    assert "Fancy heading" in cspace
    assert "And a paragraph too.\nPlus line break." in cspace

    assert convert(
        "<style>body { font: 200%; }</style>"
        "<p>Some obnoxious text here.</p>") == "Some obnoxious text here."
