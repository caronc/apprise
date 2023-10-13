# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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

from apprise import NotifyFormat
from apprise.conversion import convert_between
import pytest

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_conversion_html_to_text():
    """conversion: Test HTML to plain text
    """

    def to_html(body):
        """
        A function to simply html conversion tests
        """
        return convert_between(NotifyFormat.HTML, NotifyFormat.TEXT, body)

    assert to_html("No HTML code here.") == "No HTML code here."

    clist = to_html("<ul><li>Lots and lots</li><li>of lists.</li></ul>")
    assert "Lots and lots" in clist
    assert "of lists." in clist

    assert "To be or not to be." in to_html(
        "<blockquote>To be or not to be.</blockquote>")

    cspace = to_html(
        "<h2>Fancy heading</h2>"
        "<p>And a paragraph too.<br>Plus line break.</p>")
    assert "Fancy heading" in cspace
    assert "And a paragraph too.\nPlus line break." in cspace

    assert to_html(
        "<style>body { font: 200%; }</style>"
        "<p>Some obnoxious text here.</p>") == "Some obnoxious text here."

    assert to_html(
        "<p>line 1</p>"
        "<p>line 2</p>"
        "<p>line 3</p>") == "line 1\nline 2\nline 3"

    # Case sensitivity
    assert to_html(
        "<p>line 1</P>"
        "<P>line 2</P>"
        "<P>line 3</P>") == "line 1\nline 2\nline 3"

    # double new lines (testing <br> and </br>)
    assert to_html(
        "some information<br/><br>and more information") == \
        "some information\n\nand more information"

    #
    # Test bad tags
    #

    # first 2 entries are okay, but last will do as best as it can
    assert to_html(
        "<p>line 1</>"
        "<p>line 2</gar>"
        "<p>line 3>") == "line 1\nline 2\nline 3>"

    # Make sure we ignore fields that aren't important to us
    assert to_html(
        "<script>ignore this</script>"
        "<p>line 1</p>"
        "Another line without being enclosed") == \
        "line 1\nAnother line without being enclosed"

    # Test cases when there are no new lines (we're dealing with just inline
    # entries); an empty entry as well
    assert to_html("<span></span<<span>test</span> "
                   "<a href='#'>my link</a>") == \
        "test my link"

    # </p> missing
    assert to_html("<body><div>line 1 <b>bold</b></div>  "
                   " <a href='#'>my link</a>"
                   "<p>3rd line</body>") == \
        "line 1 bold\nmy link\n3rd line"

    # <hr/> on it's own
    assert to_html("<hr/>") == "---"
    assert to_html("<hr>") == "---"

    # We need to handle HTML Encodings
    assert to_html("""
        <html>
            <title>ignore this entry</title>
        <body>
          Let&apos;s handle&nbsp;special html encoding
          <hr/>
        </body>
        """) == "Let's handle special html encoding\n---"

    # If you give nothing, you get nothing in return
    assert to_html("") == ""

    with pytest.raises(TypeError):
        # Invalid input
        assert to_html(None)

    with pytest.raises(TypeError):
        # Invalid input
        assert to_html(42)

    with pytest.raises(TypeError):
        # Invalid input
        assert to_html(object)


def test_conversion_text_to():
    """conversion: Test Text to all types
    """

    response = convert_between(
        NotifyFormat.TEXT, NotifyFormat.HTML,
        "<title>Test Message</title><body>Body</body>")

    assert response == \
        '&lt;title&gt;Test&nbsp;Message&lt;/title&gt;&lt;body&gt;Body&lt;'\
        '/body&gt;'
