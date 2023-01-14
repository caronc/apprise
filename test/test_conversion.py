# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.

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
