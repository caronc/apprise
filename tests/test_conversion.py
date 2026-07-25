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

from inspect import cleandoc

# Disable logging for a cleaner testing output
import logging
from timeit import default_timer
from unittest import mock

import pytest

from apprise import NotifyFormat
from apprise.conversion import (
    BLOCKQUOTE_DEPTH_MAX,
    LIST_DEPTH_MAX,
    MAX_FRAME_DEPTH,
    HTMLMarkdownConverter,
    commonmark as commonmark_module,
    commonmark_can_close_emphasis,
    commonmark_can_open_emphasis,
    commonmark_decode_backslash_escapes,
    commonmark_emphasis_run,
    commonmark_find_backtick_run,
    commonmark_headings_to_bold,
    commonmark_index_backtick_runs,
    commonmark_match_emphasis,
    commonmark_materialize_repair,
    commonmark_pick_emphasis_sentinel,
    commonmark_render_emphasis_events,
    commonmark_render_emphasis_markers,
    commonmark_repair_chunk,
    commonmark_scan_autolink_dest,
    commonmark_scan_closer_runs,
    commonmark_scan_delimiter_run,
    commonmark_scan_paren_dest,
    commonmark_scan_repair_region,
    convert_between,
    html_to_markdown,
    markdown_to_html,
    split_dialect_chunk,
    truncate_dialect_chunk,
)
from apprise.plugins.google_chat import NotifyGoogleChat
from apprise.plugins.slack import NotifySlack

logging.disable(logging.CRITICAL)


def test_conversion_html_to_text():
    """conversion: Test HTML to plain text"""

    def to_html(body):
        """A function to simply html conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.TEXT, body)

    assert to_html("No HTML code here.") == "No HTML code here."

    clist = to_html("<ul><li>Lots and lots</li><li>of lists.</li></ul>")
    assert "Lots and lots" in clist
    assert "of lists." in clist

    assert "To be or not to be." in to_html(
        "<blockquote>To be or not to be.</blockquote>"
    )

    cspace = to_html(
        "<h2>Fancy heading</h2><p>And a paragraph too.<br>Plus line break.</p>"
    )
    assert "Fancy heading" in cspace
    assert "And a paragraph too.\nPlus line break." in cspace

    assert (
        to_html(
            "<style>body { font: 200%; }</style>"
            "<p>Some obnoxious text here.</p>"
        )
        == "Some obnoxious text here."
    )

    assert (
        to_html("<p>line 1</p><p>line 2</p><p>line 3</p>")
        == "line 1\nline 2\nline 3"
    )

    # Case sensitivity
    assert (
        to_html("<p>line 1</P><P>line 2</P><P>line 3</P>")
        == "line 1\nline 2\nline 3"
    )

    # double new lines (testing <br> and </br>)
    assert (
        to_html("some information<br/><br>and more information")
        == "some information\n\nand more information"
    )

    #
    # Test bad tags
    #

    # first 2 entries are okay, but last will do as best as it can
    assert (
        to_html("<p>line 1</><p>line 2</gar><p>line 3>")
        == "line 1\nline 2\nline 3>"
    )

    # Make sure we ignore fields that aren't important to us
    assert (
        to_html(
            "<script>ignore this</script>"
            "<p>line 1</p>"
            "Another line without being enclosed"
        )
        == "line 1\nAnother line without being enclosed"
    )

    # Test cases when there are no new lines (we're dealing with just inline
    # entries); an empty entry as well
    assert (
        to_html("<span></span<<span>test</span> <a href='#'>my link</a>")
        == "test my link"
    )

    # </p> missing
    assert (
        to_html(
            "<body><div>line 1 <b>bold</b></div>  "
            " <a href='#'>my link</a>"
            "<p>3rd line</body>"
        )
        == "line 1 bold\nmy link\n3rd line"
    )

    # <hr/> on it's own
    assert to_html("<hr/>") == "---"
    assert to_html("<hr>") == "---"

    # We need to handle HTML Encodings
    assert (
        to_html("""
        <html>
            <title>ignore this entry</title>
        <body>
          Let&apos;s handle&nbsp;special html encoding
          <hr/>
        </body>
        """)
        == "Let's handle special html encoding\n---"
    )

    # If you give nothing, you get nothing in return
    assert to_html("") == ""

    # Special case on HR tag
    assert (
        to_html("""
        <html>
            <head></head>
            <body>
                <p><b>FROM: </b>apprise-test@mydomain.yyy
                <apprise-test@mydomain.yyy></p>
                Hi!<br/>
                How are you?<br/>
<font color=3D"#FF0000">red font</font>
<a href=3D"http://www.python.org">link</a> you wanted.<br/>
            </body>
        </html>
        """)
        == "FROM: apprise-test@mydomain.yyy\nHi!\n How are you?\n red font"
        " link you wanted."
    )

    assert (
        to_html("""
        <html>
            <head></head>
            <body>
                <p><b>FROM: </b>apprise-test@mydomain.yyy
                    <apprise-test@mydomain.yyy><hr></p>
                Hi!<br/>
                How are you?<br/>
<font color=3D"#FF0000">red font</font>
<a href=3D"http://www.python.org">link</a> you wanted.<br/>
            </body>
        </html>
        """)
        == "FROM: apprise-test@mydomain.yyy\n---\nHi!\n How are you?\n red"
        " font link you wanted."
    )

    # Special case on HR if text is sorrunded by HR tags
    # its created a dict element
    assert (
        to_html("""
        <html>
            <head></head>
            <body>
                <p><hr><b>FROM: </b>apprise-test@mydomain.yyy
                    <apprise-test@mydomain.yyy><hr></p>
                Hi!<br/>
                How are you?<br/>
<font color=3D"#FF0000">red font</font>
<a href=3D"http://www.python.org">link</a> you wanted.<br/>
            </body>
        </html>
        """)
        == "---\nFROM: apprise-test@mydomain.yyy\n---\nHi!\n How are you?\n"
        " red font link you wanted."
    )

    assert (
        to_html("""
        <html>
            <head></head>
            <body>
                <p>
                    <hr><b>TEST</b><hr>
                </p>
                Hi!<br/>
                How are you?<br/>
<font color=3D"#FF0000">red font</font>
<a href=3D"http://www.python.org">link</a> you wanted.<br/>
            </body>
            </html>
        """)
        == "---\nTEST\n---\nHi!\n How are you?\n red font link you wanted."
    )

    with pytest.raises(TypeError):
        # Invalid input
        assert to_html(None)

    with pytest.raises(TypeError):
        # Invalid input
        assert to_html(42)

    with pytest.raises(TypeError):
        # Invalid input
        assert to_html(object)


def test_conversion_html_to_markdown():
    """Test basic HTML-to-Markdown conversion."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Plain text with no HTML passes through unchanged
    assert to_md("No HTML code here.") == "No HTML code here."

    # Empty string in, empty string out
    assert to_md("") == ""

    # Paragraphs need a full blank line between them.
    assert (
        to_md("<p>line 1</p><p>line 2</p><p>line 3</p>")
        == "line 1\n\nline 2\n\nline 3"
    )

    # Case sensitivity -- tag names are case-insensitive in HTML
    assert (
        to_md("<p>line 1</P><P>line 2</P><P>line 3</P>")
        == "line 1\n\nline 2\n\nline 3"
    )

    # HTMLParser lowercases ALL tag names -- inline tags included
    assert to_md("<B>bold text</B>") == "**bold text**"
    assert to_md("<I>italic</I>") == "*italic*"

    # Uppercase self-closing <BR/> tags also produce CommonMark hard breaks.
    assert (
        to_md("line one<BR/>line two<BR />line three")
        == "line one  \nline two  \nline three"
    )

    # <br> and self-closing <br/> both emit a hard break
    assert (
        to_md("some information<br/><br>and more information")
        == "some information  \n  \nand more information"
    )

    # Each heading level maps to the correct number of # characters
    assert to_md("<h1>Heading 1</h1>") == "# Heading 1"
    assert to_md("<h2>Heading 2</h2>") == "## Heading 2"
    assert to_md("<h3>Heading 3</h3>") == "### Heading 3"
    assert to_md("<h4>Heading 4</h4>") == "#### Heading 4"
    assert to_md("<h5>Heading 5</h5>") == "##### Heading 5"
    assert to_md("<h6>Heading 6</h6>") == "###### Heading 6"

    # Multiple headings and paragraphs together
    assert to_md(
        "<h1>Heading 1</h1>"
        "<h2>Heading 2</h2>"
        "<h3>Heading 3</h3>"
        "<h4>Heading 4</h4>"
        "<h5>Heading 5</h5>"
        "<h6>Heading 6</h6>"
        "<p>line 1</>"
        "<p><em>line 2</em></gar>"
        "<p>line 3>"
    ) == (
        "# Heading 1\n## Heading 2\n### Heading 3\n"
        "#### Heading 4\n##### Heading 5\n###### Heading 6\n\n"
        "line 1\n\n*line 2*\n\nline 3\\>"
    )

    # <b> and <strong> both produce bold markers
    assert to_md("<b>bold text</b>") == "**bold text**"
    assert to_md("<strong>bold text</strong>") == "**bold text**"

    # <i> and <em> both produce italic markers
    assert to_md("<i>italic</i>") == "*italic*"
    assert to_md("<em>italic</em>") == "*italic*"

    # Angle destinations prevent parentheses in an href from ending links.
    assert (
        to_md(
            "<body><div>line 1 <b>bold</b></div> "
            " <a href='/link'>my link</a>"
            "<p>3rd line</body>"
        )
        == "line 1 **bold**\n\n[my link](</link>)\n\n3rd line"
    )

    # <a href="..."> produces Markdown link syntax
    assert (
        to_md("<span></span<<span>test</span> <a href='#'>my link</a>")
        == "test [my link](<#>)"
    )

    # <a> with nested inline markup -- the href must survive the child tags
    assert to_md("<a href='/x'><b>hello</b> world</a>") == (
        "[**hello** world](</x>)"
    )
    assert to_md("<a href='/x'><strong>label</strong></a>") == (
        "[**label**](</x>)"
    )
    assert (
        to_md("<a href='/x'><em>italic</em> and plain</a>")
        == "[*italic* and plain](</x>)"
    )

    # Nested <a> -- inner href wins for its own span; outer wraps the rest
    assert (
        to_md("<a href='/outer'>text <a href='/inner'>link</a></a>")
        == "[text [link](</inner>)](</outer>)"
    )

    # <a> with no href attribute -- content rendered as plain text
    assert to_md("<span>test</span> <a>no link</a>") == "test no link"

    # Bare <a name="..."> anchor (no href) -- text passes through unchanged
    assert to_md("<a name='top'>jump target</a>") == "jump target"

    # <span> is inline -- it passes text through without a newline; <div> is
    # block-level and paragraph-like, so it adds a blank line.
    assert to_md("<div>block</div><span>inline</span>") == "block\n\ninline"

    # HTML comments are stripped entirely; surrounding text is preserved
    assert to_md("<!-- comment --> text") == "text"
    assert to_md("a<!-- c1 -->b<!-- c2 -->c") == "abc"

    # <![CDATA[...]]> sections are gracefully ignored (content is dropped, text
    # outside the CDATA boundary is kept)
    assert to_md("text<![CDATA[data]]> here") == "text here"
    assert to_md("<![CDATA[data]]>text") == "text"

    # Inline <code> wraps in backticks without a block boundary
    assert to_md("<code>func()</code>") == "`func()`"

    # Markdown special characters inside <code> are NOT escaped -- backtick
    # delimiters already make content literal
    assert to_md("<code>x*2 and #tag</code>") == "`x*2 and #tag`"

    # <pre> produces a fenced code block
    assert to_md("<pre>line a\nline b</pre>") == "```\nline a\nline b\n```"

    # <samp> is treated the same as <pre> (fenced block)
    assert to_md("<samp>output\nhere</samp>") == "```\noutput\nhere\n```"

    # Inline code followed immediately by a pre block
    assert to_md(
        "<code>multi-line 1\nmulti-line 2</code>more content"
        "<pre>multi-line 1\nmulti-line 2</pre>more content"
    ) == (
        "`multi-line 1\nmulti-line 2`more content"
        "\n```\nmulti-line 1\nmulti-line 2\n```\nmore content"
    )

    # Unordered lists produce "- " prefixed items
    result = to_md("<ul><li>Lots and lots</li><li>of lists.</li></ul>")
    assert "- Lots and lots" in result
    assert "- of lists." in result

    assert (
        to_md("<blockquote>To be or not to be.</blockquote>")
        == "> To be or not to be."
    )

    # Standalone <hr/> produces just "---"
    assert to_md("<hr/>") == "---"
    assert to_md("<hr>") == "---"

    # <style> content is suppressed
    assert (
        to_md(
            "<style>body { font: 200%; }</style>"
            "<p>Some obnoxious text here.</p>"
        )
        == "Some obnoxious text here."
    )

    # <script> content is suppressed
    assert (
        to_md(
            "<script>ignore this</script>"
            "<p>line 1</p>"
            "Another line without being enclosed"
        )
        == "line 1\n\nAnother line without being enclosed"
    )

    # '*' outside code is escaped so it does not trigger emphasis
    assert to_md("<p>price: 5 * 3</p>") == r"price: 5 \* 3"

    # '#' outside code is escaped so it does not trigger a heading
    assert to_md("<p>Tag #1</p>") == r"Tag \#1"

    # Backtick outside code is escaped
    assert to_md("<p>Use `func`</p>") == r"Use \`func\`"

    assert (
        to_md(
            """
        <html>
            <title>ignore this entry</title>
        <body>
          Let&apos;s handle&nbsp;special html encoding
          <hr/>
        </body>
        """
        )
        == "Let's handle special html encoding\n\n---"
    )

    # Missing </p> is handled gracefully
    assert (
        to_md(
            "<h2>Heading</h2><p>And a paragraph too.<br>Plus line break.</p>"
        )
        == "## Heading\n\nAnd a paragraph too.  \nPlus line break."
    )

    with pytest.raises(TypeError):
        to_md(None)

    with pytest.raises(TypeError):
        to_md(42)

    with pytest.raises(TypeError):
        to_md(object)


def test_conversion_html_to_markdown_lists():
    """Test list nesting and numbering."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Flat unordered list

    assert (
        to_md("<ul><li>alpha</li><li>beta</li><li>gamma</li></ul>")
        == "- alpha\n- beta\n- gamma"
    )

    # Flat ordered list with auto-incrementing counter

    assert (
        to_md("<ol><li>first</li><li>second</li><li>third</li></ol>")
        == "1. first\n2. second\n3. third"
    )

    # <ol start=> shifts where the auto-incrementing counter begins
    assert to_md('<ol start="4"><li>a</li><li>b</li></ol>') == "4. a\n5. b"
    assert to_md('<ol start="0"><li>a</li></ol>') == "0. a"

    # CommonMark list markers cannot represent negative starting values.
    assert to_md('<ol start="-3"><li>a</li><li>b</li></ol>') == "0. a\n1. b"

    # A non-numeric start is ignored, same as no attribute at all
    assert to_md('<ol start="abc"><li>a</li></ol>') == "1. a"

    # <li value=> resets the counter for that item and every sibling after it
    assert to_md('<ol><li value="5">a</li><li>b</li></ol>') == "5. a\n6. b"
    assert (
        to_md('<ol><li>a</li><li value="10">b</li><li>c</li></ol>')
        == "1. a\n10. b\n11. c"
    )
    assert to_md('<ol><li value="-5">a</li><li>b</li></ol>') == "0. a\n1. b"

    # A non-numeric value is ignored too -- the counter just keeps incrementing
    # normally, same as if the attribute weren't there
    assert to_md('<ol><li value="abc">a</li><li>b</li></ol>') == "1. a\n2. b"

    # Nested unordered lists (2 levels)

    assert (
        to_md(
            "<ul><li>top A<ul><li>nested A</li></ul></li><li>top B</li></ul>"
        )
        == "- top A\n  - nested A\n- top B"
    )

    # Nested unordered lists (3 levels)

    assert (
        to_md("<ul><li>L1<ul><li>L2<ul><li>L3</li></ul></li></ul></li></ul>")
        == "- L1\n  - L2\n    - L3"
    )

    # Mixed nesting: ol inside ul

    assert (
        to_md(
            "<ul>"
            "<li>intro<ol>"
            "<li>step one</li>"
            "<li>step two</li>"
            "</ol></li>"
            "</ul>"
        )
        == "- intro\n  1. step one\n  2. step two"
    )

    # Mixed nesting: ul inside ol

    assert (
        to_md(
            "<ol>"
            "<li>first<ul>"
            "<li>sub A</li>"
            "<li>sub B</li>"
            "</ul></li>"
            "<li>second</li>"
            "</ol>"
        )
        == "1. first\n  - sub A\n  - sub B\n2. second"
    )

    # Malformed HTML: missing </li> in a <ul> HTMLParser does not synthesize
    # implicit close events; each missing </li> is simply absent, but the next.
    assert (
        to_md("<ul><li>item A<li>item B<li>item C</ul>")
        == "- item A\n- item B\n- item C"
    )

    # Without </li>, ordered-list counters cannot advance.
    assert (
        to_md("<ol><li>one<li>two<li>three</ol>") == "1. one\n1. two\n1. three"
    )

    # Malformed HTML: missing closing </ul>

    assert to_md("<ul><li>item A</li><li>item B</li>") == "- item A\n- item B"

    # Malformed HTML: missing </li> AND missing </ul>

    assert to_md("<ul><li>item A<li>item B") == "- item A\n- item B"

    # Malformed HTML: bare text inside <ul> (no <li> wrapper) <ul> is in
    # IGNORE_TAGS so unwrapped text is suppressed entirely
    assert to_md("<ul>bare text</ul>") == ""

    # <code> inside <li>: inline code preserved with backticks

    assert (
        to_md("<ul><li>run <code>cmd --flag</code> now</li></ul>")
        == "- run `cmd --flag` now"
    )

    # Markdown special characters inside <code> are NOT escaped
    assert (
        to_md("<ul><li>see <code>x*2 #tag</code></li></ul>")
        == "- see `x*2 #tag`"
    )

    # Fenced blocks retain content and list indentation.
    assert (
        to_md("<ul><li>code:<pre>  indented\n  here</pre></li></ul>")
        == "- code:\n  ```\n    indented\n    here\n  ```"
    )

    # Nested fenced blocks combine content indentation with list indentation.
    assert (
        to_md(
            "<ul><li>outer<ul><li>inner:<pre>  x = 1</pre></li></ul></li></ul>"
        )
        == "- outer\n  - inner:\n    ```\n      x = 1\n    ```"
    )

    # A first-child block shares the list marker's line.

    # Single item with a <p> first child
    assert to_md("<ul><li><p>alpha</p></li></ul>") == "- alpha"

    # Multiple items each with a <p> first child.
    assert (
        to_md("<ul><li><p>alpha</p></li><li><p>beta</p></li></ul>")
        == "- alpha\n\n- beta"
    )

    # Multiple <p> children inside one <li>
    assert to_md("<ul><li><p>one</p><p>two</p></li></ul>") == "- one\n\n  two"

    # Mixed: direct text for first item, <p> for second.
    assert (
        to_md("<ul><li>direct</li><li><p>wrapped</p></li></ul>")
        == "- direct\n- wrapped"
    )

    # Numbered list with <p> children
    assert (
        to_md("<ol><li><p>first</p></li><li><p>second</p></li></ol>")
        == "1. first\n\n2. second"
    )

    # <a> link as first child of <li> -- the marker must share the line
    assert to_md("<ul><li><a href='/x'>link</a></li></ul>") == "- [link](</x>)"

    # <a> with nested markup as first (and only) child of <li>
    assert (
        to_md("<ul><li><a href='/x'><b>bold link</b></a></li></ul>")
        == "- [**bold link**](</x>)"
    )

    # <a> link followed by a <p> sibling inside the same <li>.
    assert (
        to_md("<ul><li><a href='/x'>link</a><p>more</p></li></ul>")
        == "- [link](</x>)\n\n  more"
    )


def test_conversion_html_to_markdown_escaping():
    """Test Markdown escaping."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Embedded backticks widen code delimiters.
    assert to_md("<code>a`b</code>") == "``a`b``"

    # Content starting or ending with a backtick gets a padding space, per
    # CommonMark's code-span disambiguation rule
    assert to_md("<code>`x</code>") == "`` `x ``"
    assert to_md("<code>x`</code>") == "`` x` ``"

    # A run of 3 backticks inside <pre> widens the fence past 3
    assert to_md("<pre>boom```</pre>") == "````\nboom```\n````"

    # Plain content with no backticks still uses the minimal delimiter
    assert to_md("<pre>x</pre>") == "```\nx\n```"

    # Ignored containers suppress both text and Markdown markers.
    assert (
        to_md(
            "<html><head><b>ignore</b></head><body><p>keep</p></body></html>"
        )
        == "keep"
    )

    # A heading marker ("# ") must not leak from a suppressed container
    assert (
        to_md("<head><h1>hidden heading</h1></head><body>text</body>")
        == "text"
    )

    # A list marker ("- ") must not leak from a <li> nested inside a suppressed
    # container, even though <li> normally re-enables storage
    assert (
        to_md("<head><ul><li>hidden item</li></ul></head><body>text</body>")
        == "text"
    )

    # <script> content (already suppressed) must not leak nested markers
    assert to_md("<script>ignore <b>this</b></script><p>keep</p>") == "keep"

    # A <pre> block fully inside a suppressed container emits nothing, not even
    # an empty fence
    assert to_md("<script>ignore<pre>code</pre></script><p>keep</p>") == "keep"

    # Angle destinations preserve whitespace in link targets.
    assert to_md("<a href='/my page'>link</a>") == "[link](</my page>)"

    # Nested tags are inert inside preformatted content.
    assert (
        to_md("<pre>before <a href='/x'>link</a> after</pre>")
        == "```\nbefore link after\n```"
    )
    assert (
        to_md("<code>before <b>bold</b> after</code>") == "`before bold after`"
    )

    # Stray code/pre/samp close tags
    assert to_md("</code>text") == "text"
    assert to_md("</pre>text") == "text"
    assert to_md("</samp>text") == "text"

    # Markdown/HTML injection via plain text content
    assert (
        to_md("<p>Click [here](https://evil.example.com) now</p>")
        == r"Click \[here\]\(https://evil.example.com\) now"
    )
    assert (
        to_md("<p>An image ![x](https://evil.example.com/x.png) too</p>")
        == r"An image \!\[x\]\(https://evil.example.com/x.png\) too"
    )

    # A literal backslash must itself be escaped
    assert to_md("<p>back\\*slash</p>") == r"back\\\*slash"

    # '_' (CommonMark's other emphasis delimiter) and '~' (GFM/chat- dialect
    # strikethrough) are escaped unconditionally, the same as '*'.
    assert to_md("<p>_literal_</p>") == r"\_literal\_"
    assert to_md("<p>my_variable_name</p>") == r"my\_variable\_name"
    assert to_md("<p>~strikethrough~</p>") == r"\~strikethrough\~"

    # Entity-encoded HTML (decoded to literal "<"/">" text by the parser) must
    # not survive into the Markdown output unescaped
    assert (
        to_md("<p>previously &lt;script&gt;alert(1)&lt;/script&gt;</p>")
        == r"previously \<script\>alert\(1\)\</script\>"
    )

    # href cannot break out of the link destination
    assert to_md(
        '<a href="https://safe.example.com)[FAKE](https://evil.example.com/p)">'
        "legit link</a>"
    ) == (
        "[legit link]"
        "(<https://safe.example.com)[FAKE](https://evil.example.com/p)>)"
    )

    # A '<' or '>' inside the href itself must be escaped, since both are
    # meaningful within the angle-bracket destination form.
    assert to_md('<a href="https://x.example.com/<script>">y</a>') == (
        r"[y](<https://x.example.com/\<script\>>)"
    )

    # Strip line endings before placing a URL in an angle-bracket destination.
    assert (
        to_md('<a href="https://safe/x\n\n# injected">click</a>')
        == "[click](<https://safe/x# injected>)"
    )

    # Neutralize schemes that can execute content or expose local files.
    assert to_md('<a href="javascript:alert(1)">click me</a>') == (
        "[click me](<#>)"
    )
    assert to_md('<a href="data:text/html,x">click</a>') == "[click](<#>)"
    assert to_md('<a href="vbscript:msgbox(1)">click</a>') == "[click](<#>)"
    assert to_md('<a href="file:///etc/passwd">click</a>') == "[click](<#>)"
    assert to_md('<a href="JaVaScRiPt:alert(1)">click</a>') == "[click](<#>)"

    # Leading or trailing whitespace must not defeat scheme detection.
    assert to_md('<a href="  javascript:alert(1)">click</a>') == (
        "[click](<#>)"
    )
    assert to_md('<a href=" \tjavascript:alert(1)">click</a>') == (
        "[click](<#>)"
    )
    assert to_md('<a href="javascript:alert(1)  ">click</a>') == (
        "[click](<#>)"
    )

    # BiDi override/embedding characters must not defeat scheme detection.
    assert to_md('<a href="‮javascript:alert(1)">click</a>') == ("[click](<#>)")
    assert to_md('<a href="‪javascript:alert(1)">click</a>') == ("[click](<#>)")
    # U+2066 (LEFT-TO-RIGHT ISOLATE) must also be stripped.
    assert to_md('<a href="⁦javascript:alert(1)">click</a>') == ("[click](<#>)")

    # Keep legitimate app-specific schemes that are not explicitly unsafe.
    assert to_md('<a href="https://example.com">x</a>') == (
        "[x](<https://example.com>)"
    )
    assert to_md('<a href="mailto:test@example.com">x</a>') == (
        "[x](<mailto:test@example.com>)"
    )
    assert to_md('<a href="tel:+15551234567">x</a>') == (
        "[x](<tel:+15551234567>)"
    )
    assert to_md('<a href="sms:+15551234567">x</a>') == (
        "[x](<sms:+15551234567>)"
    )
    assert to_md('<a href="geo:37.7,-122.4">x</a>') == (
        "[x](<geo:37.7,-122.4>)"
    )
    assert to_md('<a href="msteams:meeting?id=123">x</a>') == (
        "[x](<msteams:meeting?id=123>)"
    )
    assert to_md('<a href="sharepoint://site/doc">x</a>') == (
        "[x](<sharepoint://site/doc>)"
    )
    assert to_md('<a href="/relative/path">x</a>') == ("[x](</relative/path>)")
    assert to_md('<a href="#anchor">x</a>') == "[x](<#anchor>)"


def test_conversion_html_to_markdown_line_start_escaping():
    """Test block syntax escaping."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Escape ordered-list-shaped text only at the start of a line.
    assert to_md("<p>1. Apples</p><p>2. Oranges</p>") == (
        "1\\. Apples\n\n2\\. Oranges"
    )
    assert to_md("<p>23. done</p>") == "23\\. done"

    # Match bullet markers at the start of a line.
    assert to_md("<p>- not a bullet, just a dash</p>") == (
        "\\- not a bullet, just a dash"
    )
    assert to_md("<p>+ plus sign list?</p>") == "\\+ plus sign list?"

    # Escape repeated dashes that could become a thematic break.
    assert to_md("<p>Some text</p><p>---</p><p>more text</p>") == (
        "Some text\n\n\\---\n\nmore text"
    )

    # Escaping the first dash is enough to prevent a thematic break.
    rendered = convert_between(
        NotifyFormat.MARKDOWN,
        NotifyFormat.HTML,
        to_md("<p>Some text</p><p>---</p><p>more text</p>"),
    )
    assert "<hr" not in rendered
    assert "<h1" not in rendered
    assert "<h2" not in rendered
    assert "---" in rendered

    assert to_md("<p>***</p>") == "\\*\\*\\*"
    assert to_md("<p>___</p>") == "\\_\\_\\_"
    assert to_md("<p>- - -</p>") == "\\- - -"
    assert to_md("<p>Hello world<br>===</p>") == "Hello world  \n\\==="
    assert to_md("<p>Heading<br>---</p>") == "Heading  \n\\---"

    # None of this is ambiguous -- and so isn't escaped -- anywhere other than
    # a true line start
    assert to_md("<p>well-known v1.2 it is not - really</p>") == (
        "well-known v1.2 it is not - really"
    )
    assert to_md("<p>price is $5.00</p>") == "price is $5.00"
    assert to_md("<p>a-b-c</p>") == "a-b-c"
    assert to_md("<p>5 - 3 = 2</p>") == "5 - 3 = 2"


def test_conversion_html_to_markdown_hardening():
    """Test malformed stack input."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Stray close tags before any matching open tag

    # </ul> and </ol> take the early-return path in handle_endtag
    assert to_md("</ul>text") == "text"
    assert to_md("</ol>text") == "text"

    # </li> finds no open <li> anywhere on the stack and is a no-op -- the
    # text that follows is unindented and stored normally
    assert to_md("</li>text") == "text"

    # Multiple stray close tags in a row must not crash or corrupt state
    assert to_md("</ul></ol></li>preamble") == "preamble"

    # A valid list after a stray close must still render correctly
    assert to_md("</ul><ul><li>A</li><li>B</li></ul>") == "- A\n- B"

    # A stray close tag with content on BOTH sides must be a complete no-op,
    # not just absorbed because nothing preceded it.
    assert to_md("a</ul>b") == "ab"
    assert to_md("a</ol>b") == "ab"
    assert to_md("a</li>b") == "ab"
    assert to_md("a</blockquote>b") == "ab"
    assert to_md("a</td>b") == "ab"
    assert to_md("a</th>b") == "ab"

    # A stray <td>/<th> close still falls through cleanly when content follows.
    assert to_md("<p>a</td>b</p>") == "ab"

    # _make_frame() empty-stack guard
    conv = HTMLMarkdownConverter()

    # Force the stack empty -- this can only happen via direct attribute
    # manipulation, never through the public parsing API
    conv._stack = []
    frame = conv._make_frame("div")

    # The fallback defaults must match the root sentinel values
    assert frame["tag"] == "div"
    assert frame["do_store"] is True
    assert frame["preserve_cr"] is False
    assert frame["list_type"] is None
    assert frame["depth"] == 0
    assert frame["counter"] is None
    assert frame["list_do_store"] is True

    # A stale open-tag count must not corrupt the stack.
    conv = HTMLMarkdownConverter()
    conv._tag_open_counts["nonexistent"] = 1
    conv._pop_to("nonexistent")  # must not raise or corrupt state
    assert len(conv._stack) == 1  # only the root sentinel remains

    # ignore content found in head
    assert (
        to_md(
            "<head>"
            + "<ul>" * 50
            + "<li>hidden</li>"
            + "</ul>" * 50
            + "</head><body>text</body>"
        )
        == "text"
    )

    # deep <ul> nesting still resolve correctly.
    assert (
        to_md("<ul>" * 50 + "<li>visible</li>" + "</ul>" * 50) == "- visible"
    )

    # List indentation is capped at LIST_DEPTH_MAX ---
    assert LIST_DEPTH_MAX == 4

    one_per_level = "<ul><li>x" * 10 + "</li></ul>" * 10
    out = to_md(one_per_level)
    lines = out.split("\n")
    assert len(lines) == 10
    # Indent grows for the first LIST_DEPTH_MAX levels...
    assert lines[0] == "- x"
    assert lines[1] == "  - x"
    assert lines[2] == "    - x"
    assert lines[3] == "      - x"
    # ...then holds steady for every level beyond the cap
    for line in lines[4:]:
        assert line == "      - x"

    # Performance: same shape, large enough that the old O(N^2)
    n = 20000
    deep = "<ul><li>x" * n + "</li></ul>" * n
    start = default_timer()
    out = to_md(deep)
    elapsed = default_timer() - start
    assert len(out) < 20 * n
    # Generous bound: this must catch a real return to quadratic
    # behavior, not just run fast on a quiet dev machine -- shared or
    # emulated build infrastructure (e.g. a busy Koji builder) can be
    # many times slower.
    assert elapsed < 15.0

    # Performance: many UNCLOSED <li> tags nested directly inside one another.
    n = 20000
    html = "<li>x" * n
    start = default_timer()
    out = to_md(html)
    elapsed = default_timer() - start
    assert len(out) < 10 * n  # output itself is linear, not quadratic
    # Generous bound -- see the note on the equivalent check above.
    assert elapsed < 30.0

    # Performance: many open <blockquote> tags followed by many closing tags of
    # a *different* kind that's never actually open ("</pre>").
    n = 20000
    html = "<blockquote>" * n + "</pre>" * n
    start = default_timer()
    out = to_md(html)
    elapsed = default_timer() - start
    assert len(out) < 20 * n
    # Generous bound: this must catch a real return to quadratic
    # behavior, not just run fast on a quiet dev machine -- shared or
    # emulated build infrastructure (e.g. a busy Koji builder) can be
    # many times slower.
    assert elapsed < 15.0

    # Blockquote depth is capped at BLOCKQUOTE_DEPTH_MAX
    assert BLOCKQUOTE_DEPTH_MAX == 4

    # Each level is its own <p>, so every line of real content is followed by a
    # blank (but still "> "-prefixed) separator line.
    one_per_level = "<blockquote><p>x</p>" * 10 + "</blockquote>" * 10
    out = to_md(one_per_level)
    lines = out.split("\n")
    assert len(lines) == 19
    content_lines = lines[0::2]
    separator_lines = lines[1::2]
    assert len(content_lines) == 10
    assert content_lines[0] == "> x"
    assert content_lines[1] == "> > x"
    assert content_lines[2] == "> > > x"
    assert content_lines[3] == "> > > > x"
    for line in content_lines[4:]:
        assert line == "> > > > x"
    # Each separator matches its preceding content line, minus the "x"
    for content, separator in zip(content_lines, separator_lines):
        assert separator == content[: -len("x")].rstrip()

    n = 20000
    deep = "<blockquote><p>x</p>" * n + "</blockquote>" * n
    start = default_timer()
    out = to_md(deep)
    elapsed = default_timer() - start
    assert len(out) < 20 * n
    # Generous bound: this must catch a real return to quadratic
    # behavior, not just run fast on a quiet dev machine -- shared or
    # emulated build infrastructure (e.g. a busy Koji builder) can be
    # many times slower.
    assert elapsed < 15.0

    # When emphasis or anchor tags are nested past MAX_FRAME_DEPTH, _push_frame
    # returns False and the opening delimiter must NOT be emitted.
    depth = MAX_FRAME_DEPTH + 1
    em_open = "<em>" * depth
    em_close = "</em>" * depth
    out_em = to_md(f"{em_open}text{em_close}")
    # The text must appear; no unmatched bare asterisk may leak through.
    assert "text" in out_em
    assert out_em.replace("*", "").strip() == "text"

    # Same guard for <a> -- no unmatched "[" in the output.
    a_open = '<a href="https://example.com">' * depth
    a_close = "</a>" * depth
    out_a = to_md(f"{a_open}text{a_close}")
    assert "text" in out_a
    # Count "[" and "](" -- every "[" must have a matching "](".
    assert out_a.count("[") == out_a.count("](")

    # At MAX_FRAME_DEPTH the <blockquote> frame is discarded and _push_frame
    # returns False.
    bq_open = "<blockquote>" * depth
    bq_close = "</blockquote>" * depth
    out_bq = to_md(f"{bq_open}text{bq_close}")
    assert "text" in out_bq
    # Every ">" line-prefix must correspond to a real nested blockquote level.
    first_line = out_bq.splitlines()[0] if out_bq else ""
    gt_count = len(first_line) - len(first_line.lstrip("> "))
    assert gt_count <= BLOCKQUOTE_DEPTH_MAX * 2  # ">" + " " per level

    # At MAX_FRAME_DEPTH the <li> frame is discarded and _push_frame returns
    # False.  No _ListMarker must be appended without a backing frame.
    li_open = "<ul>" + "<li>" * depth
    li_close = "</li>" * depth + "</ul>"
    out_li = to_md(f"{li_open}text{li_close}")
    assert "text" in out_li


def test_conversion_headings_to_bold():
    """Convert supported ATX headings for chat dialects without headings."""

    # Convert the common heading forms generated from HTML.
    assert commonmark_headings_to_bold("# Alert") == "**Alert**"
    assert commonmark_headings_to_bold("###### Alert") == "**Alert**"

    # An optional closing sequence of "#" is stripped, not kept as text.
    assert commonmark_headings_to_bold("## foo ##") == "**foo**"
    assert commonmark_headings_to_bold("# foo #####") == "**foo**"

    # A hash without preceding whitespace remains part of the heading text.
    assert commonmark_headings_to_bold("# foo#") == "**foo#**"

    # Preserve up to three spaces allowed before a heading.
    assert commonmark_headings_to_bold(" # one space") == " **one space**"
    assert commonmark_headings_to_bold("   # three spaces") == (
        "   **three spaces**"
    )

    # Four leading spaces make an indented code block, not a heading.
    four_spaces = "    # four spaces"
    assert commonmark_headings_to_bold(four_spaces) == four_spaces

    # Empty headings do not produce empty bold markers.
    assert commonmark_headings_to_bold("###") == ""
    assert commonmark_headings_to_bold("###   ") == ""

    # Heading text requires whitespace after its opening hashes.
    literal = "#nospace"
    assert commonmark_headings_to_bold(literal) == literal

    # Inline code spans are never touched.
    assert commonmark_headings_to_bold("`# inline code`") == (
        "`# inline code`"
    )

    # Backtick and tilde fences protect heading-like code.
    fenced_backtick = "```\n# not a heading\n```"
    assert commonmark_headings_to_bold(fenced_backtick) == fenced_backtick

    fenced_tilde = "~~~\n# not a heading either\n~~~"
    assert commonmark_headings_to_bold(fenced_tilde) == fenced_tilde

    # An unfinished fence protects the remaining text.
    unterminated = "```\n# still not a heading\nmore text"
    assert commonmark_headings_to_bold(unterminated) == unterminated

    # A real heading before and after a fenced block is still converted.
    mixed = "# Before\n```\n# inside\n```\n# After"
    assert commonmark_headings_to_bold(mixed) == (
        "**Before**\n```\n# inside\n```\n**After**"
    )

    # Preserve blockquote markers emitted by HTML-to-CommonMark conversion.
    assert commonmark_headings_to_bold("> # Alert") == "> **Alert**"
    assert commonmark_headings_to_bold("> > # Alert") == "> > **Alert**"
    assert commonmark_headings_to_bold("> > > # Alert") == ("> > > **Alert**")

    # Preserve unordered and ordered list markers.
    assert commonmark_headings_to_bold("- # Alert") == "- **Alert**"
    assert commonmark_headings_to_bold("* # Alert") == "* **Alert**"
    assert commonmark_headings_to_bold("+ # Alert") == "+ **Alert**"
    assert commonmark_headings_to_bold("1. # Alert") == "1. **Alert**"
    assert commonmark_headings_to_bold("2) # Alert") == "2) **Alert**"

    # Preserve combined blockquote and list markers.
    assert commonmark_headings_to_bold("> - # Alert") == "> - **Alert**"

    # Keep the blockquote marker for an empty heading.
    assert commonmark_headings_to_bold("> ###") == "> "

    # Recognize CRLF fences without protecting later headings.
    crlf_fence = "```\r\ncode\r\n```\r\n# Real Heading"
    assert commonmark_headings_to_bold(crlf_fence) == (
        "```\r\ncode\r\n```\r\n**Real Heading**"
    )

    # Invalid backtick fence labels do not protect later headings.
    invalid_opener = (
        "Some `inline` text\n"
        "```code`with`backtick info string\n"
        "more text\n"
        "# Real Heading"
    )
    assert commonmark_headings_to_bold(invalid_opener) == (
        "Some `inline` text\n"
        "```code`with`backtick info string\n"
        "more text\n"
        "**Real Heading**"
    )

    # Tilde fence labels may contain backticks.
    tilde_with_backtick = "~~~code`ok\nreal code\n~~~"
    assert (
        commonmark_headings_to_bold(tilde_with_backtick) == tilde_with_backtick
    )

    # Preserve heading-like text inside a quoted tilde fence.
    quoted_tilde_fence = "> ~~~\n> # literal code\n> ~~~"
    assert (
        commonmark_headings_to_bold(quoted_tilde_fence) == quoted_tilde_fence
    )

    # Repeating ``"- "`` starts a sibling list item, so these are three
    # separate items. The middle heading remains real Markdown and converts.
    three_sibling_items = "- ~~~\n- # literal code\n- ~~~~"
    assert commonmark_headings_to_bold(three_sibling_items) == (
        "- ~~~\n- **literal code**\n- ~~~~"
    )

    # A backtick closer wider than its opener still closes the fence, even
    # when both are nested inside a blockquote.
    quoted_wider_closer = "> ```\n> # literal code\n> ````"
    assert (
        commonmark_headings_to_bold(quoted_wider_closer) == quoted_wider_closer
    )

    # Nested blockquotes around a fence are recognized at every level.
    nested_quoted_fence = "> > ~~~\n> > # literal code\n> > ~~~"
    assert (
        commonmark_headings_to_bold(nested_quoted_fence) == nested_quoted_fence
    )

    # Quote markers may have up to three leading spaces.
    assert commonmark_headings_to_bold("   > # Alert") == "   > **Alert**"
    indented_quoted_fence = "   > ~~~\n   > # literal code\n   > ~~~"
    assert (
        commonmark_headings_to_bold(indented_quoted_fence)
        == indented_quoted_fence
    )

    # Four leading spaces create indented code, not a top-level fence.
    # The following real heading must therefore still be converted.
    four_space_fence_then_heading = (
        "    ~~~\n    not a real fence\n    ~~~\n# Real Heading"
    )
    assert commonmark_headings_to_bold(four_space_fence_then_heading) == (
        "    ~~~\n    not a real fence\n    ~~~\n**Real Heading**"
    )

    # An ordered-list marker can be wider than three characters ("123. "
    # is five), so its continuation lines need more than three leading
    # spaces too. A real heading after the fence must still convert.
    wide_ordered_fence = "123. ~~~\n     # literal\n     ~~~\n\n# real"
    assert commonmark_headings_to_bold(wide_ordered_fence) == (
        "123. ~~~\n     # literal\n     ~~~\n\n**real**"
    )

    # A list containing a quote puts the list marker first, while continuation
    # lines replace it with spaces. Both prefix orders belong to one container.
    list_then_quote_fence = "- > ~~~\n  > # literal\n  > ~~~\n\n# real"
    assert commonmark_headings_to_bold(list_then_quote_fence) == (
        "- > ~~~\n  > # literal\n  > ~~~\n\n**real**"
    )

    # Up to three leading spaces may belong to a top-level fence rather than
    # a list. Its heading-like content must remain protected.
    lightly_indented_fence = " ~~~\n# literal\n ~~~\n# real"
    assert commonmark_headings_to_bold(lightly_indented_fence) == (
        " ~~~\n# literal\n ~~~\n**real**"
    )

    # Opening and closing fences have independent indentation allowances.
    mismatched_indent_fence = "~~~\n# literal\n  ~~~\n# real"
    assert commonmark_headings_to_bold(mismatched_indent_fence) == (
        "~~~\n# literal\n  ~~~\n**real**"
    )

    # The same closer slack applies inside a blockquote.
    quoted_mismatched_indent_fence = "> ~~~\n> # literal\n>   ~~~\n> # real"
    assert commonmark_headings_to_bold(quoted_mismatched_indent_fence) == (
        "> ~~~\n> # literal\n>   ~~~\n> **real**"
    )

    # A lightly indented fence can continue a list item without repeating
    # its marker. An unfinished fence stops when that list item ends.
    unclosed_narrow_list_fence = "- intro\n  ~~~\n  # literal\n\n# real"
    assert commonmark_headings_to_bold(unclosed_narrow_list_fence) == (
        "- intro\n  ~~~\n  # literal\n\n**real**"
    )

    # A later top-level fence cannot close the list's unfinished fence.
    unclosed_narrow_list_fence_with_later_fence = (
        "- intro\n  ~~~\n  # literal\n\n# real\n\n~~~\nunrelated\n~~~"
    )
    assert commonmark_headings_to_bold(
        unclosed_narrow_list_fence_with_later_fence
    ) == ("- intro\n  ~~~\n  # literal\n\n**real**\n\n~~~\nunrelated\n~~~")

    # Blank lines before the fence may remain within the list item.
    unclosed_narrow_list_fence_with_blank = (
        "- intro\n\n  ~~~\n  # literal\n\n# real"
    )
    assert commonmark_headings_to_bold(
        unclosed_narrow_list_fence_with_blank
    ) == ("- intro\n\n  ~~~\n  # literal\n\n**real**")

    # Light indentation without an earlier list marker is top-level.
    unmarked_indent_no_list_behind_it = (
        "Some intro text\n ~~~\n# literal\n ~~~\n# real"
    )
    assert commonmark_headings_to_bold(unmarked_indent_no_list_behind_it) == (
        "Some intro text\n ~~~\n# literal\n ~~~\n**real**"
    )

    # The paragraph lazily continues the list, but one-space fence indentation
    # is still insufficient for the two-space item.
    list_ended_by_unindented_paragraph = (
        "- intro\nunindented paragraph\n ~~~\n# literal\n ~~~\n# real"
    )
    assert commonmark_headings_to_bold(list_ended_by_unindented_paragraph) == (
        "- intro\nunindented paragraph\n ~~~\n# literal\n ~~~\n**real**"
    )

    # Indented list text may appear between the marker and fence.
    unclosed_narrow_list_fence_with_paragraph = (
        "- intro\n  more text in the same item\n  ~~~\n  # literal\n\n# real"
    )
    assert commonmark_headings_to_bold(
        unclosed_narrow_list_fence_with_paragraph
    ) == (
        "- intro\n  more text in the same item\n  ~~~\n  # literal\n\n**real**"
    )

    # The HTML converter replaces a list marker with equal-width spaces on
    # continuation lines. Test that real output as well as synthetic input.
    list_only_fence_html = (
        "<ul><li><pre><code># literal\nmore</code></pre></li></ul>"
        "<h1>Real Heading</h1>"
    )
    list_only_fence_body = html_to_markdown(list_only_fence_html)
    assert list_only_fence_body == (
        "- ```\n  # literal\n  more\n  ```\n\n# Real Heading"
    )
    converted = commonmark_headings_to_bold(list_only_fence_body)
    # The heading-like line inside the fence stays literal code.
    assert "  # literal\n" in converted
    # A real heading placed after the fenced block still converts.
    assert converted.endswith("\n**Real Heading**")

    # Also cover a preceding paragraph and the wider numbered-list marker.
    text_then_fence_html = (
        "<ul><li>intro<pre><code># literal\nmore</code></pre></li></ul>"
        "<h1>Real Heading</h1>"
    )
    text_then_fence_body = html_to_markdown(text_then_fence_html)
    assert text_then_fence_body == (
        "- intro\n  ```\n  # literal\n  more\n  ```\n\n# Real Heading"
    )
    converted = commonmark_headings_to_bold(text_then_fence_body)
    assert "  # literal\n" in converted
    assert converted.endswith("\n**Real Heading**")

    ordered_fence_html = (
        "<ol><li><pre><code># literal\nmore</code></pre></li></ol>"
        "<h1>Real Heading</h1>"
    )
    ordered_fence_body = html_to_markdown(ordered_fence_html)
    assert ordered_fence_body == (
        "1. ```\n   # literal\n   more\n   ```\n\n# Real Heading"
    )
    converted = commonmark_headings_to_bold(ordered_fence_body)
    assert "   # literal\n" in converted
    assert converted.endswith("\n**Real Heading**")

    # List continuation spacing moves before the quote marker on later lines.
    quoted_list_fence_html = (
        "<blockquote><ul><li>intro"
        "<pre><code># literal\nmore</code></pre></li></ul></blockquote>"
        "<h1>Real Heading</h1>"
    )
    quoted_list_fence_body = html_to_markdown(quoted_list_fence_html)
    assert quoted_list_fence_body == (
        "> - intro\n  > ```\n  > # literal\n  > more\n  > ```"
        "\n\n# Real Heading"
    )
    converted = commonmark_headings_to_bold(quoted_list_fence_body)
    assert "  > # literal\n" in converted
    assert converted.endswith("\n**Real Heading**")

    # Leading list indentation contributes to the continuation width, whether
    # the fence begins the item or follows its introductory text.
    indented_marker_then_fence = " - ~~~\n   # literal\n   ~~~\n# real"
    assert commonmark_headings_to_bold(indented_marker_then_fence) == (
        " - ~~~\n   # literal\n   ~~~\n**real**"
    )

    indented_marker_with_intro = " - intro\n   ~~~\n   # literal\n\n# real"
    assert commonmark_headings_to_bold(indented_marker_with_intro) == (
        " - intro\n   ~~~\n   # literal\n\n**real**"
    )

    # A literal "- " inside a closed fence must not create list state for the
    # unfinished top-level fence that follows it.
    marker_like_text_inside_closed_fence = (
        "~~~\n- literal\n  ~~~\n  ~~~\n# still code"
    )
    assert commonmark_headings_to_bold(
        marker_like_text_inside_closed_fence
    ) == ("~~~\n- literal\n  ~~~\n  ~~~\n# still code")

    # Ending an inner list restores the still-open outer list width.
    nested_list_falls_back_to_outer = (
        "- outer\n  - inner\n    text\n  ~~~\n  # literal\n\n# real"
    )
    assert commonmark_headings_to_bold(nested_list_falls_back_to_outer) == (
        "- outer\n  - inner\n    text\n  ~~~\n  # literal\n\n**real**"
    )

    # An unindented paragraph may lazily continue an open list item.
    lazy_continuation_keeps_list_open = (
        "- intro\nlazy continuation\n  ~~~\n  # literal\n\n# real"
    )
    assert commonmark_headings_to_bold(lazy_continuation_keeps_list_open) == (
        "- intro\nlazy continuation\n  ~~~\n  # literal\n\n**real**"
    )

    # A new list marker ends lazy paragraph continuation.
    new_marker_ends_lazy_continuation = (
        "- intro\nordinary text\n- newitem\n  ~~~\n  # literal\n\n# real"
    )
    assert commonmark_headings_to_bold(new_marker_ends_lazy_continuation) == (
        "- intro\nordinary text\n- newitem\n  ~~~\n  # literal\n\n**real**"
    )

    # A list fence closer may add only three columns of indentation.
    # Greater indentation leaves it open until the list ends.
    wildly_overindented_list_closer = (
        "- intro\n  ```\n  code\n                    ```\n# real"
    )
    assert commonmark_headings_to_bold(wildly_overindented_list_closer) == (
        "- intro\n  ```\n  code\n                    ```\n**real**"
    )

    # The same three-column closer limit applies outside lists.
    wildly_overindented_top_level_closer = "```\ncode\n          ```\n# after"
    assert commonmark_headings_to_bold(
        wildly_overindented_top_level_closer
    ) == ("```\ncode\n          ```\n# after")

    # ``-\t`` reaches column four. Two spaces cannot continue that list, so
    # the following unfinished fence is top-level and protects the remainder.
    tab_expanded_marker_width = "-\tintro\n  ```\n  # literal\n\n# real"
    assert commonmark_headings_to_bold(tab_expanded_marker_width) == (
        tab_expanded_marker_width
    )

    # A tab reaches the same column as ``-\t``, keeping the fence in the list.
    tab_expanded_continuation_width = "-\tintro\n\t```\n\t# literal\n\n# real"
    assert commonmark_headings_to_bold(tab_expanded_continuation_width) == (
        "-\tintro\n\t```\n\t# literal\n\n**real**"
    )

    # Accept quote-first continuation lines as well as Apprise's list-first
    # output when a fenced block is nested in both containers.
    quote_then_list_continuation = "- > ~~~\n>   # literal\n>   ~~~\n\n# real"
    assert commonmark_headings_to_bold(quote_then_list_continuation) == (
        "- > ~~~\n>   # literal\n>   ~~~\n\n**real**"
    )

    # A quote-first closer still needs the list's full indentation.
    quote_then_list_insufficient_width = (
        "- > ~~~\n>   # literal\n> ~~~\n>   ~~~\n\n# real"
    )
    assert commonmark_headings_to_bold(quote_then_list_insufficient_width) == (
        "- > ~~~\n>   # literal\n> ~~~\n>   ~~~\n\n**real**"
    )

    # List indentation without the required quote marker ends the container.
    list_width_met_but_no_quote_at_all = (
        "- > ~~~\n   text without quote\n>   ~~~\n\n# real"
    )
    assert commonmark_headings_to_bold(list_width_met_but_no_quote_at_all) == (
        "- > ~~~\n   text without quote\n>   ~~~\n\n**real**"
    )

    # A bare quote marker still satisfies its quote depth.
    bare_quote_marker_line_in_combo = "- > ~~~\n>\n>   ~~~\n\n# real"
    assert commonmark_headings_to_bold(bare_quote_marker_line_in_combo) == (
        "- > ~~~\n>\n>   ~~~\n\n**real**"
    )

    # A heading ends the list, making the following unfinished fence top-level.
    heading_ends_list_before_fence = (
        "- intro\n# outside\n  ~~~\n  # literal\n# still code"
    )
    assert commonmark_headings_to_bold(heading_ends_list_before_fence) == (
        "- intro\n**outside**\n  ~~~\n  # literal\n# still code"
    )

    # A heading inside a list marker cannot gain a lazy continuation.
    marker_content_is_heading = (
        "- # heading\noutside\n  ~~~\n  # literal\n# still code"
    )
    assert commonmark_headings_to_bold(marker_content_is_heading) == (
        "- **heading**\noutside\n  ~~~\n  # literal\n# still code"
    )

    # Blockquotes and thematic breaks also end lazy list continuation.
    blockquote_ends_list_before_fence = (
        "- intro\n> outside\n  ~~~\n  # literal\n# still code"
    )
    assert commonmark_headings_to_bold(blockquote_ends_list_before_fence) == (
        "- intro\n> outside\n  ~~~\n  # literal\n# still code"
    )

    thematic_break_ends_list_before_fence = (
        "- intro\n---\n  ~~~\n  # literal\n# still code"
    )
    assert commonmark_headings_to_bold(
        thematic_break_ends_list_before_fence
    ) == ("- intro\n---\n  ~~~\n  # literal\n# still code")

    # CRLF input follows the same thematic-break boundary rule.
    thematic_break_ends_list_crlf = (
        "- intro\r\n---\r\n  ~~~\r\n  # literal\r\n# still code"
    )
    assert commonmark_headings_to_bold(thematic_break_ends_list_crlf) == (
        "- intro\r\n---\r\n  ~~~\r\n  # literal\r\n# still code"
    )

    # A tab at column zero reaches column four, creating indented code.
    tab_at_column_zero_is_not_slack = "\t# literal"
    assert (
        commonmark_headings_to_bold(tab_at_column_zero_is_not_slack)
        == tab_at_column_zero_is_not_slack
    )

    tab_at_column_zero_fence_is_not_slack = "\t~~~\ncode\n\t~~~\n# real"
    assert commonmark_headings_to_bold(
        tab_at_column_zero_fence_is_not_slack
    ) == ("\t~~~\ncode\n\t~~~\n**real**")

    # A tab after a quote can remain within the three-column allowance.
    tab_after_quote_is_slack = ">\t# literal"
    assert commonmark_headings_to_bold(tab_after_quote_is_slack) == (
        ">\t**literal**"
    )

    # Tabs between nested quote markers use one column of marker padding.
    tab_separated_nested_quote_fence = (
        ">\t>\t~~~\n>\t>\t# literal\n>\t>\t~~~\n>\t>\t# real"
    )
    assert commonmark_headings_to_bold(tab_separated_nested_quote_fence) == (
        ">\t>\t~~~\n>\t>\t# literal\n>\t>\t~~~\n>\t>\t**real**"
    )

    # Nested quote markers also work without separating spaces.
    unspaced_nested_quote_fence = ">>~~~\n>>literal\n>>~~~\n>># real"
    assert commonmark_headings_to_bold(unspaced_nested_quote_fence) == (
        ">>~~~\n>>literal\n>>~~~\n>>**real**"
    )

    # Tab-separated quote/list content uses indentation on continuation lines.
    tab_separated_quote_list_fence = (
        ">\t-\tintro\n>\t  ~~~\n>\t  # literal\n>\t  ~~~\n>\t# real"
    )
    assert commonmark_headings_to_bold(tab_separated_quote_list_fence) == (
        ">\t-\tintro\n>\t  ~~~\n>\t  # literal\n>\t  ~~~\n>\t**real**"
    )

    # HTML blocks end lazy list paragraphs, making the next fence top-level.
    html_block_ends_list_before_fence = (
        "- intro\n<div>\nhtml\n</div>\n\n  ~~~\n  # literal\n# still code"
    )
    assert commonmark_headings_to_bold(html_block_ends_list_before_fence) == (
        "- intro\n<div>\nhtml\n</div>\n\n  ~~~\n  # literal\n# still code"
    )

    html_comment_ends_list_before_fence = (
        "- intro\n<!-- comment -->\n  ~~~\n  # literal\n# still code"
    )
    assert commonmark_headings_to_bold(
        html_comment_ends_list_before_fence
    ) == ("- intro\n<!-- comment -->\n  ~~~\n  # literal\n# still code")

    # A backtick in a backtick fence's info string makes the opener invalid.
    invalid_backtick_info_string_not_a_fence = (
        "- intro\n  ```bad`info\nlazy\n  ~~~\n  # literal\n# real"
    )
    assert commonmark_headings_to_bold(
        invalid_backtick_info_string_not_a_fence
    ) == ("- intro\n  ```bad`info\nlazy\n  ~~~\n  # literal\n**real**")

    # Four extra columns inside a two-column list create indented code.
    six_space_indent_not_a_fence = (
        "- intro\n      ```\nlazy\n  ~~~\n  # literal\n# real"
    )
    assert commonmark_headings_to_bold(six_space_indent_not_a_fence) == (
        "- intro\n      ```\nlazy\n  ~~~\n  # literal\n**real**"
    )

    # A blank line ends a blockquote fence but may remain in a plain list.
    blank_line_ends_blockquote_fence = "> ~~~\n> code\n\n> # real"
    assert commonmark_headings_to_bold(blank_line_ends_blockquote_fence) == (
        "> ~~~\n> code\n\n> **real**"
    )

    # A fence may use up to three extra columns inside an active list.
    fence_with_extra_slack_stays_in_list = (
        "1. item\n    ~~~\n   # literal\n   ~~~\n# real"
    )
    assert commonmark_headings_to_bold(
        fence_with_extra_slack_stays_in_list
    ) == ("1. item\n    ~~~\n   # literal\n   ~~~\n**real**")

    # Active-list indentation can identify a heading without another marker.
    assert commonmark_headings_to_bold("- item\n    # nested") == (
        "- item\n    **nested**"
    )
    assert commonmark_headings_to_bold("- item\n\t# nested") == (
        "- item\n\t**nested**"
    )

    # Content inside an HTML block passes through unchanged.
    heading_inside_html_block_untouched = "<div>\n# literal\n</div>"
    assert (
        commonmark_headings_to_bold(heading_inside_html_block_untouched)
        == heading_inside_html_block_untouched
    )

    # Fence-looking text inside HTML must not consume the following document.
    fence_look_alike_inside_html_block = "<div>\n~~~\n</div>\n\n# real"
    assert (
        commonmark_headings_to_bold(fence_look_alike_inside_html_block)
        == "<div>\n~~~\n</div>\n\n**real**"
    )

    # A lowercase CDATA look-alike is ordinary text.
    lowercase_cdata_is_not_html_block = (
        "- intro\n<![cdata[\n\n  ~~~\n  # literal\n# real"
    )
    assert commonmark_headings_to_bold(lowercase_cdata_is_not_html_block) == (
        "- intro\n<![cdata[\n\n  ~~~\n  # literal\n**real**"
    )

    # A heading nested nine levels deep still converts -- the scanner
    # imposes no depth limit.
    heading_past_old_depth_cap = "> " * 9 + "# real"
    assert commonmark_headings_to_bold(heading_past_old_depth_cap) == (
        "> " * 9 + "**real**"
    )

    # An HTML block is recognized even after an active blockquote prefix,
    # not just at the very start of a line.
    html_block_inside_blockquote = "> <div>\n> # literal\n> </div>"
    assert (
        commonmark_headings_to_bold(html_block_inside_blockquote)
        == html_block_inside_blockquote
    )

    # A tag-looking line inside a real fence is literal fenced content,
    # not an HTML block start -- it must not swallow what follows the
    # fence's own close.
    html_look_alike_inside_fence = "~~~\n<script>\n~~~\n# real"
    assert commonmark_headings_to_bold(html_look_alike_inside_fence) == (
        "~~~\n<script>\n~~~\n**real**"
    )

    # A raw tag's closing form must be complete; a partial closer such as
    # "</script nope" does not end the block.
    raw_tag_requires_exact_close = (
        "<script>\ncontent\n</script nope\nreal end\n</script>\nafter\n"
        "\n# real"
    )
    assert commonmark_headings_to_bold(raw_tag_requires_exact_close) == (
        "<script>\ncontent\n</script nope\nreal end\n</script>\nafter\n"
        "\n**real**"
    )

    # A heading between two same-length backtick runs must not look like
    # a code span spanning across it -- block structure is resolved
    # before inline code-span pairing.
    backtick_run_does_not_cross_heading = "before ``\n# real\nafter ``"
    assert commonmark_headings_to_bold(
        backtick_run_does_not_cross_heading
    ) == ("before ``\n**real**\nafter ``")

    # Type 7: a complete tag for any other name, alone on its own line,
    # starts an HTML block too -- but only when not interrupting an
    # already-open paragraph.
    custom_tag_at_document_start_protects_content = (
        "<custom>\n# literal\n</custom>"
    )
    assert (
        commonmark_headings_to_bold(
            custom_tag_at_document_start_protects_content
        )
        == custom_tag_at_document_start_protects_content
    )
    custom_tag_cannot_interrupt_paragraph = "some text\n<custom>\n# real"
    assert commonmark_headings_to_bold(
        custom_tag_cannot_interrupt_paragraph
    ) == ("some text\n<custom>\n**real**")

    # A space before the self-closing slash makes this an invalid tag.
    malformed_self_close_not_a_tag = "<custom / >\n# real"
    assert commonmark_headings_to_bold(malformed_self_close_not_a_tag) == (
        "<custom / >\n**real**"
    )

    # A ">" inside a quoted attribute does not end the tag early.
    quoted_attribute_value_with_gt = '<custom title=">">\n# literal'
    assert (
        commonmark_headings_to_bold(quoted_attribute_value_with_gt)
        == quoted_attribute_value_with_gt
    )

    # Any raw-tag closer ends a type-1 block, even if its name differs.
    raw_tag_close_need_not_match_open = "<script>\nx\n</style>\n# real"
    assert commonmark_headings_to_bold(raw_tag_close_need_not_match_open) == (
        "<script>\nx\n</style>\n**real**"
    )

    # An empty list item opens no paragraph, so type-7 HTML may follow.
    empty_list_item_allows_type7 = "-\n<custom>\n# literal"
    assert (
        commonmark_headings_to_bold(empty_list_item_allows_type7)
        == empty_list_item_allows_type7
    )
    empty_quote_item_allows_type7 = ">\n<custom>\n# literal"
    assert (
        commonmark_headings_to_bold(empty_quote_item_allows_type7)
        == empty_quote_item_allows_type7
    )

    # Extra marker padding makes this indented code, not a heading.
    excess_list_marker_padding_is_indented_code = "-     # literal"
    assert commonmark_headings_to_bold(
        excess_list_marker_padding_is_indented_code
    ) == ("-     # literal")

    # Nested HTML ends with its blockquote, so the later heading converts.
    html_block_ends_with_its_blockquote = "> <div>\n# real"
    assert commonmark_headings_to_bold(
        html_block_ends_with_its_blockquote
    ) == ("> <div>\n**real**")

    # A quote marker by itself is blank and ends the nested HTML block.
    quote_marker_only_line_ends_html_block = "> <div>\n>\n> # real"
    assert commonmark_headings_to_bold(
        quote_marker_only_line_ends_html_block
    ) == ("> <div>\n>\n> **real**")

    # A blank line ends type-6/7 HTML even inside a list.
    blank_line_ends_html_block_inside_list = "- <div>\n\n  # real"
    assert commonmark_headings_to_bold(
        blank_line_ends_html_block_inside_list
    ) == ("- <div>\n\n  **real**")

    # Excess tab padding belongs to the item's indented code content.
    tab_padding_after_marker_is_indented_code = "-\t\t\t# literal"
    assert commonmark_headings_to_bold(
        tab_padding_after_marker_is_indented_code
    ) == ("-\t\t\t# literal")

    # A setext underline closes the paragraph before the type-7 tag.
    setext_underline_ends_paragraph = "text\n===\n<custom>\n# literal"
    assert (
        commonmark_headings_to_bold(setext_underline_ends_paragraph)
        == setext_underline_ends_paragraph
    )

    # Indented text lazily continues the paragraph, blocking type-7 HTML.
    indented_text_continues_paragraph_lazily = (
        "text\n    continuation\n<custom>\n# real"
    )
    assert commonmark_headings_to_bold(
        indented_text_continues_paragraph_lazily
    ) == ("text\n    continuation\n<custom>\n**real**")

    # An empty list marker cannot interrupt the open paragraph.
    empty_marker_cannot_interrupt_paragraph = "text\n+\n<custom>\n# literal"
    assert commonmark_headings_to_bold(
        empty_marker_cannot_interrupt_paragraph
    ) == ("text\n+\n<custom>\n**literal**")

    # A non-empty list marker interrupts the open paragraph.
    nonempty_marker_interrupts_paragraph = "text\n+ item\n<custom>\n# literal"
    assert (
        commonmark_headings_to_bold(nonempty_marker_interrupts_paragraph)
        == nonempty_marker_interrupts_paragraph
    )


def test_conversion_headings_type7_regex_performance():
    """Keep malformed type-7 tags with long whitespace runs near linear."""
    times = []
    for spaces in (1600, 6400):
        body = "<x " + (" " * spaces) + "<\n# real"
        start = default_timer()
        commonmark_headings_to_bold(body)
        times.append(default_timer() - start)

    # A 4x input must stay well below the roughly 16x cost of quadratic work.
    assert times[1] < times[0] * 8 + 0.2


def test_conversion_headings_nested_quotes_performance():
    """Keep deeply nested blockquotes fast without limiting their depth."""
    start = default_timer()
    commonmark_headings_to_bold("> " * 5000 + "x")
    elapsed = default_timer() - start

    assert elapsed < 0.5


def test_conversion_headings_deep_lines_performance():
    """Keep repeated deeply nested lines fast as message size grows."""
    body = ("> " * 8 + "x\n") * 1000

    start = default_timer()
    commonmark_headings_to_bold(body)
    elapsed = default_timer() - start

    assert elapsed < 1.0


def test_conversion_html_block_spans():
    """_commonmark_html_block_spans: per-type closing rules."""

    # Type 6 (a named block tag) closes at the next blank line.
    text = "<div>\ncontent\n</div>\n\nafter"
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, len("<div>\ncontent\n</div>\n"))
    ]

    # Without a blank line, the block runs to the end of the text.
    text = "<div>\ncontent\n</div>"
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, len(text))
    ]

    # A raw tag closes at a complete raw-tag end, even across what would
    # otherwise be a blank-line boundary.
    text = "<script>\nvar x = 1;\n\nmore\n</script>\nafter"
    close = text.index("</script>") + len("</script>")
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, close + 1)
    ]

    # A comment closes at its own terminator, wherever it appears.
    text = "<!-- start\nstill a comment -->\nafter"
    close = text.index("-->") + len("-->")
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, close + 1)
    ]

    # An unterminated comment runs to the end of the text.
    text = "<!-- never closes\nmore text"
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, len(text))
    ]

    # A processing instruction closes at "?>".
    text = "<?php\necho 1;\n?>\nafter"
    close = text.index("?>") + len("?>")
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, close + 1)
    ]

    # A declaration closes at the next literal ">", extended through the
    # end of the line containing it.
    text = "<!DOCTYPE html>\nafter"
    close = text.index(">", text.index("<!DOCTYPE"))
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, close + 2)
    ]

    # A CDATA section closes at "]]>".
    text = "<![CDATA[\ndata\n]]>\nafter"
    close = text.index("]]>") + len("]]>")
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, close + 1)
    ]

    # Lowercase "cdata" is not a valid opener at all -- case-sensitive.
    text = "<![cdata[\nnot a block\n\nafter"
    assert commonmark_module._commonmark_html_block_spans(text) == []

    # Plain text with no HTML block start yields no spans.
    assert commonmark_module._commonmark_html_block_spans("just text") == []

    # A non-raw closing tag does not end a raw HTML block.
    text = "<script>\nvar x = 1;\n</div>\nmore\n</script>\nafter"
    close = text.rindex("</script>") + len("</script>")
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, close + 1)
    ]

    # A partial string like "</script nope" must not count as "</script>".
    text = "<script>\ncontent\n</script nope\nreal end\n</script>\nafter"
    close = text.rindex("</script>") + len("</script>")
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, close + 1)
    ]

    # Type 7: a complete tag for any other name, alone on its own line,
    # starts an HTML block too, when not interrupting an open paragraph.
    text = "<custom>\ncontent\n</custom>\n\nafter"
    assert commonmark_module._commonmark_html_block_spans(text) == [
        (0, len("<custom>\ncontent\n</custom>\n"))
    ]

    # Type 7 cannot interrupt an already-open paragraph.
    text = "some text\n<custom>\nmore text"
    assert commonmark_module._commonmark_html_block_spans(text) == []


def test_conversion_leaf_block_spans_mutual_exclusion():
    """Keep fence-like HTML and HTML-like fenced text inside their opener."""
    # A fence-looking line inside a real (type 6) HTML block is not a
    # fence -- the HTML block's own span covers it.
    text = "<div>\n~~~\n</div>\n\nafter"
    spans = commonmark_module._commonmark_leaf_block_spans(text)
    assert spans == [(0, len("<div>\n~~~\n</div>\n"), "html")]

    # An HTML-looking line inside a real fence is not an HTML block --
    # the fence's own span covers it, and closes normally.
    text = "~~~\n<script>\n~~~\nafter"
    spans = commonmark_module._commonmark_leaf_block_spans(text)
    assert spans == [(0, len("~~~\n<script>\n~~~\n"), "fence")]


def test_conversion_text_width_expands_tabs():
    """_text_width: a tab expands to the next four-column stop."""
    assert commonmark_module._text_width("\t") == 4
    assert commonmark_module._text_width("\t", 1) == 3
    assert commonmark_module._text_width("a\tb") == 5


def test_conversion_html_block_end_bounded_by_quote_container():
    """Stop fixed and blank-line HTML blocks when their blockquote ends."""
    # Type 2 (comment): the terminator search must not run past the
    # blockquote's own end into unquoted text below it.
    text = "> <!-- start\n\n# real"
    spans = commonmark_module._commonmark_leaf_block_spans(text)
    assert spans == [(0, len("> <!-- start\n"), "html")]

    # Type 6 (a named block tag): same boundary, via the blank-line rule.
    text = "> <div>\n\n# real"
    spans = commonmark_module._commonmark_leaf_block_spans(text)
    assert spans == [(0, len("> <div>\n"), "html")]

    # A properly quoted continuation line still satisfies the container,
    # so the terminator search continues through it and finds a closer
    # on a later line, rather than stopping early.
    text = "> <!-- comment\n> still comment -->\nafter"
    spans = commonmark_module._commonmark_leaf_block_spans(text)
    assert spans == [(0, len("> <!-- comment\n> still comment -->\n"), "html")]

    # When the quote holds all the way through and no terminator ever
    # appears, the block runs to the end of the text.
    text = "> <!-- never closes\n> more text"
    spans = commonmark_module._commonmark_leaf_block_spans(text)
    assert spans == [(0, len(text), "html")]


def test_conversion_html_block_end_blank_line_rule_differs_by_type():
    """Keep fixed-terminator HTML open; end types 6/7 at a blank line.

    Lists may span blank lines, but that does not extend type-6/7 HTML.
    """
    text = "- <!-- start\n\nafter"
    spans = commonmark_module._commonmark_leaf_block_spans(text)
    assert spans == [(0, len("- <!-- start\n\n"), "html")]

    text = "- <div>\n\nafter"
    spans = commonmark_module._commonmark_leaf_block_spans(text)
    assert spans == [(0, len("- <div>\n"), "html")]


def test_conversion_fenced_code_spans_stay_within_text_bounds():
    """A fence with no trailing newline must not report an out-of-range end."""

    text = "```\nx\n```"
    spans = commonmark_module._commonmark_fenced_code_spans(text)
    assert spans == [(0, len(text))]
    for start, end in spans:
        assert 0 <= start <= len(text)
        assert 0 <= end <= len(text)


def test_conversion_code_spans_do_not_cross_block_boundaries():
    """Backtick pairing must not cross a block boundary between the runs.

    CommonMark resolves block structure before parsing inlines, so a
    heading (or any other block) sitting between two same-length
    backtick runs must not make them look like one matched code span.
    """
    # A heading between two double-backtick runs ends the paragraph, so
    # neither run may pair with the other.
    text = "before ``\n# heading\nafter ``"
    assert commonmark_module._commonmark_code_spans(text) == []

    # A blank line has the same effect.
    text = "before ``\n\nafter ``"
    assert commonmark_module._commonmark_code_spans(text) == []

    # Without a boundary in between, pairing within one paragraph's
    # continuous lines still works as before.
    text = "before ``\nstill one paragraph`` after"
    assert commonmark_module._commonmark_code_spans(text) == [
        (7, len(text) - len(" after"))
    ]


def test_conversion_headings_to_bold_repeated_fences_linear_time():
    """Keep repeated, lightly indented fence checks near linear time.

    Every line remains a possible list continuation, exercising the full
    ambiguous-fence path instead of ending a lookup early.
    """

    small = " ~~~\n text\n ~~~\n" * 2000
    large = " ~~~\n text\n ~~~\n" * 4000

    # Create and reuse one scanner for the entire conversion.
    with mock.patch(
        "apprise.conversion.commonmark._ContainerScanner",
        wraps=commonmark_module._ContainerScanner,
    ) as spy:
        commonmark_headings_to_bold(large)
    assert spy.call_count == 1

    start = default_timer()
    commonmark_headings_to_bold(small)
    small_time = default_timer() - start

    start = default_timer()
    commonmark_headings_to_bold(large)
    large_time = default_timer() - start

    # Allow timing noise while rejecting clear quadratic growth.
    assert large_time < small_time * 2.5 + 0.5


def test_conversion_headings_to_bold_repeated_fences_bounded_memory():
    """Avoid storing one list-width entry for every preceding line."""
    tracemalloc = pytest.importorskip("tracemalloc")

    baseline = "\n" * 800_000 + "# heading\n"
    ambiguous = "\n" * 800_000 + " ~~~\n"

    tracemalloc.start()
    commonmark_headings_to_bold(baseline)
    _, baseline_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    commonmark_headings_to_bold(ambiguous)
    _, ambiguous_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Allow allocator overhead while rejecting a document-sized index.
    assert ambiguous_peak < baseline_peak * 5 + 1024 * 1024


def test_conversion_decode_backslash_escapes():
    """Only decode backslashes used for CommonMark punctuation escapes."""

    # A backslash before ASCII punctuation is a real CommonMark escape.
    assert commonmark_decode_backslash_escapes(r"a\*b") == "a*b"
    assert commonmark_decode_backslash_escapes(r"a\_b") == "a_b"
    assert commonmark_decode_backslash_escapes(r"a\\b") == "a\\b"

    # Preserve backslashes before letters so paths and URLs are not corrupted.
    assert commonmark_decode_backslash_escapes(r"a\qb") == r"a\qb"
    assert commonmark_decode_backslash_escapes(r"C:\Users") == r"C:\Users"

    # A trailing, unescaped backslash has nothing to escape and is kept.
    assert commonmark_decode_backslash_escapes("a\\") == "a\\"


def test_conversion_html_to_markdown_blockquotes():
    """Test blockquote conversion."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Single paragraph -- marker and content share the first line
    assert to_md("<blockquote><p>line1</p></blockquote>") == "> line1"

    # Multiple paragraphs
    assert (
        to_md("<blockquote><p>line1</p><p>line2</p></blockquote>")
        == "> line1\n>\n> line2"
    )
    assert (
        to_md("<blockquote><p>a</p><p>b</p><p>c</p></blockquote>")
        == "> a\n>\n> b\n>\n> c"
    )

    # A heading doesn't need that same blank-line treatment.
    assert (
        to_md("<blockquote><h2>Title</h2><p>body</p></blockquote>")
        == "> ## Title\n> body"
    )

    # Inline-only content needs no internal prefixing -- it never hits a
    # boundary inside the quote in the first place
    assert (
        to_md("<blockquote>To be or not to be.</blockquote>")
        == "> To be or not to be."
    )

    # Nested blockquotes accumulate one "> " per level, not per ancestor's full
    # cumulative prefix, which would double-count outer quote levels.
    assert (
        to_md("<blockquote><blockquote>nested</blockquote></blockquote>")
        == "> > nested"
    )
    assert to_md(
        "<blockquote><blockquote><p>a</p><p>b</p></blockquote></blockquote>"
    ) == ("> > a\n> >\n> > b")

    # Bare text follows the same one-prefix-per-level rule.
    assert (
        to_md("<blockquote>outer<blockquote>inner</blockquote></blockquote>")
        == "> outer\n>\n> > inner"
    )
    assert to_md(
        "<blockquote>a<blockquote>b<blockquote>c</blockquote>"
        "</blockquote></blockquote>"
    ) == ("> a\n>\n> > b\n> >\n> > > c")

    # The same text-then-nested-blockquote transition, once depth is already
    # clamped at BLOCKQUOTE_DEPTH_MAX, must not add yet another level.
    assert BLOCKQUOTE_DEPTH_MAX == 4
    capped = (
        "<blockquote>" * 4
        + "x<blockquote>y</blockquote>"
        + ("</blockquote>" * 4)
    )
    out = to_md(capped)
    assert "> > > > x" in out
    assert "> > > > > y" not in out
    assert "> > > > y" in out

    # Content after a blockquote needs a full boundary without the quote
    # prefix.
    assert (
        to_md("<blockquote><p>line1</p></blockquote><p>after</p>")
        == "> line1\n\nafter"
    )
    assert (
        to_md("<p>before</p><blockquote><p>line1</p></blockquote>")
        == "before\n\n> line1"
    )

    # An entirely empty blockquote (no children at all, nested or not) produces
    # no output.
    assert to_md("<blockquote></blockquote>") == ""
    assert to_md("<blockquote><blockquote></blockquote></blockquote>") == ""

    # A blockquote entirely inside a suppressed context contributes nothing,
    # and does not disturb sibling content outside it
    assert (
        to_md(
            "<head><blockquote><p>hidden</p></blockquote></head>"
            "<body>text</body>"
        )
        == "text"
    )

    # A blockquote following bare text still needs its own boundary.
    assert to_md("text<blockquote>quoted</blockquote>") == ("text\n\n> quoted")
    assert to_md("text<blockquote></blockquote>") == "text"
    assert to_md("<p>text<blockquote></blockquote></p>") == "text"


def test_conversion_html_to_markdown_emphasis():
    """Test emphasis edge cases."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Leading/trailing whitespace inside the tag must end up outside the
    # delimiters.
    assert to_md("<em> text </em>") == "*text*"
    assert to_md("<strong> bold </strong>") == "**bold**"
    assert to_md("<em>  multi  space  </em>") == "*multi space*"

    # Leading-only and trailing-only whitespace
    assert to_md("<em> text</em>") == "*text*"
    assert to_md("<em>text </em>") == "*text*"

    # Relocating emphasis whitespace must not disturb surrounding text.
    assert (
        to_md("<p>Hello <strong> bold </strong> world</p>")
        == "Hello  **bold**  world"
    )

    # Relocate trailing whitespace even when empty tags split the text
    # fragments.
    assert to_md("<strong>text<span></span> </strong>x") == "**text** x"

    # Fully empty, or whitespace-only, spans contribute nothing at all -- not
    # even an unpaired delimiter
    assert to_md("<strong></strong>") == ""
    assert to_md("<em>   </em>") == ""
    assert to_md("<strong><em></em></strong>") == ""

    # Adjacent tags, one empty -- the empty one's delimiters must not collide
    # with the next tag's into an ambiguous run of asterisks
    assert to_md("<strong></strong><strong>bold</strong>") == "**bold**"
    assert to_md("<em></em><em>x</em>") == "*x*"

    # A stray close tag with no matching open is a no-op, the same as other
    # malformed- HTML cases elsewhere in this parser.
    assert to_md("</b>text") == "text"
    assert to_md("<p>a</b>b</p>") == "ab"

    # Mismatched open/close tags ("<i>x</b>y").
    assert to_md("<i>x</b>y") == "*xy*"

    # A tag left open with no closing tag at all is auto-closed at end of
    # document rather than leaving its opening delimiter unpaired
    assert to_md("<b>text") == "**text**"
    assert to_md("<p><em>a<strong>b") == "*a**b***"

    # Normal, well-formed cases are unaffected
    assert to_md("<strong>bold</strong>") == "**bold**"
    assert to_md("<em>italic</em>") == "*italic*"
    assert to_md("<strong>A</strong><strong>B</strong>") == "**A****B**"

    # Empty block content inside emphasis must not leave an opening delimiter.
    assert to_md("<em><ul><li></li></ul></em>x") == "x"
    assert to_md("a<em><ul><li></li></ul></em>b") == "ab"

    # Empty trailing blocks must not hide whitespace from emphasis cleanup.
    assert to_md("<em>text<blockquote></blockquote></em>") == ("*text\n\n> *")


def test_conversion_html_to_markdown_empty_blocks():
    """Test empty block handling."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Plain, marker-less block tags with nothing inside them already collapse
    # to nothing extra -- no separate blank line is added for each one.
    assert to_md("<div></div><div></div><p>text</p>") == "text"
    assert to_md("<p>a</p><div></div><p>b</p>") == "a\n\nb"
    assert (
        to_md("<p>a</p><div></div><div></div><div></div><p>b</p>") == "a\n\nb"
    )

    # Empty blocks do not detach a marker from later content.
    assert (
        to_md("<ul><li><div></div><div></div><p>text</p></li></ul>")
        == "- text"
    )
    assert to_md("<blockquote><div></div><p>text</p></blockquote>") == "> text"

    # Drop markers that never receive content.
    assert to_md("<ul><li></li></ul>") == ""
    assert to_md("<ul><li><div></div></li></ul>") == ""

    # A sibling marker arriving after the first one's empty block tags replaces
    # it rather than gluing onto it.
    assert to_md("<ul><li><div></div></li><li>real</li></ul>") == "- real"

    # Empty blocks do not duplicate a blockquote prefix.
    assert (
        to_md("<blockquote><p>line1</p><div></div><p>line2</p></blockquote>")
        == "> line1\n>\n> line2"
    )

    # Real text between two empty blocks still resets the suppression, so the
    # block tag right after it starts a new line as normal.
    assert to_md("<div></div>text<div></div><p>more</p>") == "text\n\nmore"

    # Plain whitespace between tags never counts as content
    assert to_md("<p>a</p>   <p>b</p>") == "a\n\nb"

    # A standalone &nbsp; is a deliberate space, not incidental formatting
    # whitespace.
    assert to_md("<p>a</p>&nbsp;<p>b</p>") == "a\n\n\xa0\n\nb"

    # &nbsp; used inline within real text is unaffected, and still collapses to
    # a regular space like any other inline whitespace
    assert (
        to_md("Let's handle&nbsp;special html encoding")
        == "Let's handle special html encoding"
    )

    # <hr> is a void element (its closing tag may never fire), but it still
    # writes real, non-marker content ("---").
    assert to_md("<hr><hr>") == "---\n\n---"
    assert to_md("<hr>     <hr>") == "---\n\n---"
    assert to_md("<hr/><hr/><hr/>") == "---\n\n---\n\n---"
    assert to_md("<p>a</p><hr><hr><p>b</p>") == "a\n\n---\n\n---\n\nb"

    # <hr> as the first thing in a blockquote/list item glues onto the marker;
    # inside an open blockquote, its own opening boundary still applies.
    assert to_md("<ul><li><hr></li></ul>") == "- ---"
    assert to_md("<blockquote><p>a</p><hr></blockquote>") == "> a\n>\n> ---"

    # Real page text that happens to *look* like a generated marker (e.g.
    assert to_md("<p>- </p><p>real</p>") == "\\-\n\nreal"
    assert to_md("<p>-  </p>") == "\\-"
    assert (
        to_md("<p>- </p><div>real div content</div>")
        == "\\-\n\nreal div content"
    )
    # Real text directly inside a real <li> that itself looks like a marker is
    # escaped too.
    assert to_md("<ul><li>- </li></ul>") == "- \\-"


def test_conversion_html_to_markdown_list_indentation():
    """Test list continuation indentation."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Baseline: a single <p> as an <li>'s only child still just glues onto the
    # marker.
    assert to_md("<li><p>text</p></li>") == "- text"

    # Later paragraphs use the current item's continuation indentation.
    assert to_md("<ul><li><p>one</p><p>two</p></li></ul>") == "- one\n\n  two"

    # Ordered lists need the indentation to match their own (wider) marker
    # width, not the bullet list's fixed 2 spaces
    assert (
        to_md("<ol><li><p>one</p><p>two</p></li></ol>") == "1. one\n\n   two"
    )

    # Sibling <li>s must NOT pick up any indentation from each other -- only a
    # *continuation within the same item* should ever be indented
    assert (
        to_md("<ul><li><p>alpha</p></li><li><p>beta</p></li></ul>")
        == "- alpha\n\n- beta"
    )
    assert (
        to_md("<ol><li><p>a</p></li><li><p>b</p></li><li><p>c</p></li></ol>")
        == "1. a\n\n2. b\n\n3. c"
    )

    # A nested sublist's own marker (computed independently for its own depth)
    # must not be *additionally* indented on top of that.
    assert to_md("<ul><li>x<ul><li>x</li></ul></li></ul>") == "- x\n  - x"
    assert (
        to_md("<ul><li>L1<ul><li>L2<ul><li>L3</li></ul></li></ul></li></ul>")
        == "- L1\n  - L2\n    - L3"
    )

    # Nested quotes combine list indentation with quote prefixes.
    assert to_md(
        "<ul><li><blockquote><p>a</p><p>b</p></blockquote></li></ul>"
    ) == ("- > a\n  >\n  > b")

    # A first-child list inside a blockquote retains the quote prefix.
    assert to_md("<blockquote><ul><li>text</li></ul></blockquote>") == (
        "> - text"
    )

    # Multiple <li>s inside a <blockquote> each need "> " restated
    assert to_md("<blockquote><ul><li>a</li><li>b</li></ul></blockquote>") == (
        "> - a\n> - b"
    )

    # Chained blockquotes retain nesting after a paragraph boundary.
    assert to_md(
        "<blockquote><p>a</p><blockquote>nested</blockquote></blockquote>"
    ) == ("> a\n>\n> > nested")

    # <pre>/<samp> inside an <li>: every line of the fence.
    assert to_md("<ul><li>code:<pre>  indented\n  here</pre></li></ul>") == (
        "- code:\n  ```\n    indented\n    here\n  ```"
    )

    # A deeper list adds another indentation level to the fence.
    assert to_md(
        "<ul><li>outer<ul><li>inner:<pre>  x = 1</pre></li></ul></li></ul>"
    ) == ("- outer\n  - inner:\n    ```\n      x = 1\n    ```")


def test_conversion_html_to_markdown_br():
    """Test CommonMark hard breaks."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Two trailing spaces then a newline -- a bare "\n" is only a soft break
    # under CommonMark (most renderers collapse it to a single space rather.
    assert to_md("line1<br>line2") == "line1  \nline2"
    assert to_md("line1<br/>line2") == "line1  \nline2"
    assert to_md("line1<br />line2") == "line1  \nline2"

    # Verified against an actual renderer, not just the raw Markdown shape.
    rendered = convert_between(
        NotifyFormat.MARKDOWN, NotifyFormat.HTML, to_md("line1<br>line2")
    )
    assert "<br" in rendered
    assert "\\" not in rendered

    # Consecutive <br> tags each contribute their own hard break
    assert to_md("a<br><br>b") == "a  \n  \nb"

    # A trailing <br> with nothing after it doesn't leave a dangling hard break
    # at the very end of the output
    assert to_md("<p>line1<br></p>") == "line1"

    # A hard break inside a blockquote must restate the "> " prefix on its
    # continuation line.
    assert to_md("<blockquote>line1<br>line2</blockquote>") == (
        "> line1  \n> line2"
    )

    # Same, but inside a list item -- the continuation line must keep the
    # marker's indentation so it stays part of the same item.
    assert to_md("<ul><li>line1<br>line2</li></ul>") == ("- line1  \n  line2")

    # Both nested together -- a blockquote containing a list item.
    assert to_md(
        "<blockquote><ul><li>line1<br>line2</li></ul></blockquote>"
    ) == ("> - line1  \n  > line2")


def test_conversion_html_to_markdown_tables():
    """Test GFM table conversion."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Basic table -- first row becomes the header, a "---" separator row is
    # inserted right after it
    assert to_md(
        "<table><tr><td>A</td><td>B</td></tr>"
        "<tr><td>1</td><td>2</td></tr></table>"
    ) == ("| A | B |\n| --- | --- |\n| 1 | 2 |")

    # <thead>/<tbody>/<th> are fully transparent -- header-vs-body is decided
    # purely by row order, the same as <thead>-less markup
    assert to_md(
        "<table><thead><tr><th>Name</th><th>Age</th></tr></thead>"
        "<tbody><tr><td>Bob</td><td>42</td></tr></tbody></table>"
    ) == ("| Name | Age |\n| --- | --- |\n| Bob | 42 |")

    # A single-row table still gets its separator row
    assert to_md("<table><tr><td>only</td></tr></table>") == (
        "| only |\n| --- |"
    )

    # Inline formatting inside cells is preserved
    assert to_md(
        "<table><tr><td><b>bold</b></td>"
        '<td><a href="https://x.com">link</a></td></tr></table>'
    ) == ("| **bold** | [link](<https://x.com>) |\n| --- | --- |")

    # A literal '|' inside a cell is escaped -- it's the cell delimiter itself,
    # and would otherwise be misread as starting a new column
    assert to_md("<table><tr><td>a | b</td></tr></table>") == (
        "| a \\| b |\n| --- |"
    )

    # A newline a cell's own content produced (here, a <br>) is flattened to a
    # single space.
    assert to_md("<table><tr><td>a<br>b</td></tr></table>") == (
        "| a b |\n| --- |"
    )

    # Surrounding content gets ordinary paragraph separation from the table,
    # the same as a list or blockquote would
    assert to_md("<p>before</p><table><tr><td>A</td></tr></table>") == (
        "before\n\n| A |\n| --- |"
    )
    assert to_md("<table><tr><td>A</td></tr></table><p>after</p>") == (
        "| A |\n| --- |\n\nafter"
    )

    # An entirely empty table, or a table whose only row has no cells at all,
    # produces nothing
    assert to_md("<table></table>") == ""
    assert to_md("<table><tr></tr></table>") == ""

    # A table fully inside a suppressed container (e.g. <head>) contributes
    # nothing -- not even an empty "| |" row
    assert (
        to_md(
            "<head><table><tr><td>x</td></tr></table></head><body>text</body>"
        )
        == "text"
    )

    # Suppress text outside table cells.
    assert to_md("<table>stray<tr><td>A</td></tr></table>") == (
        "| A |\n| --- |"
    )
    assert to_md("<table><tr>stray<td>A</td></tr></table>") == (
        "| A |\n| --- |"
    )
    assert to_md("<table>\n  <tr>\n    <td>A</td>\n  </tr>\n</table>") == (
        "| A |\n| --- |"
    )

    # A stray <td> with no enclosing <tr> at all falls back to ordinary
    # paragraph-like treatment -- the same as before table support existed
    assert to_md("<td>standalone</td>") == "standalone"

    # A stray <tr> with no enclosing <table> is treated as a one-row table of
    # its own
    assert to_md("<tr><td>a</td><td>b</td></tr>") == (
        "| a | b |\n| --- | --- |"
    )


def test_conversion_html_to_markdown_tables_indentation():
    """Test nested table indentation."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    assert to_md(
        "<ul><li>before<table><tr><td>A</td></tr></table></li></ul>"
    ) == ("- before\n\n  | A |\n  | --- |")

    assert to_md(
        "<ul><li>before<table><tr><td>A</td><td>B</td></tr>"
        "<tr><td>1</td><td>2</td></tr></table></li></ul>"
    ) == ("- before\n\n  | A | B |\n  | --- | --- |\n  | 1 | 2 |")

    assert to_md(
        "<blockquote><table><tr><td>A</td><td>B</td></tr>"
        "<tr><td>1</td><td>2</td></tr></table></blockquote>"
    ) == ("> | A | B |\n> | --- | --- |\n> | 1 | 2 |")


def test_conversion_html_to_markdown_tables_hardening():
    """Test malformed table input."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Neither <td> nor <tr> ever closed -- extremely common in real-
    # world/legacy table markup
    assert to_md("<table><tr><td>A<td>B<tr><td>1<td>2</table>") == (
        "| A | B |\n| --- | --- |\n| 1 | 2 |"
    )

    # Same, but the enclosing </table> is missing too -- the last row and cell
    # are recovered at end of document
    assert to_md("<table><tr><td>A<td>B<tr><td>1<td>2") == (
        "| A | B |\n| --- | --- |\n| 1 | 2 |"
    )

    # A stray </tr> or </table> with nothing matching open at all (no enclosing
    # structure whatsoever, not even an open cell) is a no-op.
    assert to_md("</tr>text") == "text"
    assert to_md("</table>text") == "text"
    assert to_md("<p>a</tr>b</p>") == "ab"
    assert to_md("<p>a</table>b</p>") == "ab"

    # A stray <tr> with no enclosing <table> renders as a one-row table of its
    # own and remains separated from following content.
    assert to_md("<tr><td>cell</td></tr>after") == (
        "| cell |\n| --- |\n\nafter"
    )

    # A <table> nested inside another table's cell has no Markdown
    # representation.
    assert to_md(
        "<table><tr><td>outer<table><tr><td>inner</td></tr></table>"
        "</td></tr></table>"
    ) == ("| outer |\n| --- |")

    # Same, with content both before and after the nested table, and the
    # nested table itself containing more than one row.
    assert to_md(
        "<table><tr><td>a<table><tr><td>b</td></tr><tr><td>c</td></tr>"
        "</table>d</td></tr></table>"
    ) == ("| a d |\n| --- |")

    # Three levels deep -- only the outermost table survives.
    assert to_md(
        "<table><tr><td>L1<table><tr><td>L2<table><tr><td>L3</td></tr>"
        "</table></td></tr></table></td></tr></table>"
    ) == ("| L1 |\n| --- |")

    # A literal '|' alongside a nested table in the same cell -- the '|' is
    # still escaped normally; the nested table still contributes nothing.
    assert to_md(
        "<table><tr><td>a|b<table><tr><td>c</td></tr></table></td></tr>"
        "</table>"
    ) == ("| a\\|b |\n| --- |")

    # Only the very first <tr> is ever closed
    assert to_md("<table><tr><td>A</td></tr><tr><td>B<tr><td>C</table>") == (
        "| A |\n| --- |\n| B |\n| C |"
    )

    # An unclosed inline element (<em>) inside a <td> is silently discarded
    # when a sibling <td> opens; the cell's text is still captured.
    assert (
        to_md(
            "<table><tr><td><em>unclosed text<td>second cell</td></tr></table>"
        )
        == "| *unclosed text | second cell |\n| --- | --- |"
    )

    # Performance: many rows, each with unclosed <td>/<tr> tags (the legacy-
    # markup shape), large enough to expose quadratic recovery.
    n = 20000
    html = "<table>" + "<tr><td>a<td>b" * n + "</table>"
    start = default_timer()
    out = to_md(html)
    elapsed = default_timer() - start
    assert out.count("\n") == n  # one line per row, output stays linear
    # Generous bound -- see the note on the equivalent check above.
    assert elapsed < 40.0


def test_conversion_html_to_markdown_pre_code_whitespace():
    """Test preformatted whitespace."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Internal leading whitespace and blank-looking indentation differences
    # between lines are preserved exactly
    assert (
        to_md("<pre>  leading\n    more leading\nback to zero</pre>")
        == "```\n  leading\n    more leading\nback to zero\n```"
    )

    # Leading/trailing spaces inside inline <code> survive too
    assert to_md("<code>  leading spaces  </code>") == "`  leading spaces  `"

    # Whitespace is preserved the same way even when nested inside a list item
    # (which now adds its own 2-space indentation in front.
    assert to_md("<ul><li><pre>  a\n    b\nc</pre></li></ul>") == (
        "- ```\n    a\n      b\n  c\n  ```"
    )


def test_conversion_html_to_markdown_unterminated_pre_code():
    """Test <pre>/<code>/<samp> left open at end of document."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # A <pre>/<code>/<samp> with no closing tag at all is auto-closed and
    # rendered at end of document.
    assert to_md("<pre>unterminated code") == "```\nunterminated code\n```"
    assert to_md("<code>inline unterminated") == "`inline unterminated`"
    assert to_md("<samp>unterminated output") == (
        "```\nunterminated output\n```"
    )

    # Still works with real content before the unterminated block.
    assert to_md("text<pre>code") == "text\n```\ncode\n```"

    # A suppressed (non-storing) unterminated frame contributes nothing.
    assert to_md("<head><pre>hidden") == ""


def test_conversion_html_to_markdown_table_code_pipe():
    """Test '|' inside an inline code span within a table cell."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # A '|' inside a code span is already literal there.
    assert to_md("<table><tr><td><code>a|b</code></td></tr></table>") == (
        "| `a|b` |\n| --- |"
    )

    # A '|' outside any code span in the same cell is still escaped.
    assert to_md("<table><tr><td>x|<code>a|b</code>|y</td></tr></table>") == (
        "| x\\|`a|b`\\|y |\n| --- |"
    )

    # Literal backtick CHARACTERS typed as ordinary text (not an actual <code>
    # element) get backslash-escaped by MARKDOWN_ESCAPE like any other.
    assert to_md("<table><tr><td>`a|b`</td></tr></table>") == (
        "| \\`a\\|b\\` |\n| --- |"
    )

    # A real code span and escaped literal backticks can coexist in the same
    # cell -- only the real one's '|' stays unescaped.
    assert to_md(
        "<table><tr><td><code>x|y</code> and `lit|eral`</td></tr></table>"
    ) == ("| `x|y` and \\`lit\\|eral\\` |\n| --- |")

    # A real code span immediately preceded by an ESCAPED literal backslash (an
    # even number of '\' characters, i.e.
    assert to_md(
        "<table><tr><td>text\\<code>a|b</code></td></tr></table>"
    ) == ("| text\\\\`a|b` |\n| --- |")
    assert to_md(
        "<table><tr><td>text\\\\<code>a|b</code></td></tr></table>"
    ) == ("| text\\\\\\\\`a|b` |\n| --- |")

    # An unmatched (unbalanced) bare backtick run inside a cell.
    conv = HTMLMarkdownConverter()
    assert conv._escape_cell_pipes("a`b|c") == "a`b\\|c"

    # The shared index skips escape pairs and groups runs by exact width.
    # A lookup returns None when the requested width does not exist.
    assert (
        commonmark_find_backtick_run(
            commonmark_index_backtick_runs("\\` `"), 0, 1
        )
        == 3
    )
    assert (
        commonmark_find_backtick_run(
            commonmark_index_backtick_runs("no backticks here"), 0, 1
        )
        is None
    )
    assert (
        commonmark_find_backtick_run(
            commonmark_index_backtick_runs("``too short"), 0, 3
        )
        is None
    )

    # Runs of different widths are indexed separately.
    assert (
        commonmark_find_backtick_run(
            commonmark_index_backtick_runs("`` `"), 0, 1
        )
        == 3
    )

    # Skip an escaped single backtick before matching a width-two run.
    assert (
        commonmark_find_backtick_run(
            commonmark_index_backtick_runs("\\` ``x"), 0, 2
        )
        == 3
    )

    # Skip an unescaped run of the wrong width before matching width two.
    assert (
        commonmark_find_backtick_run(
            commonmark_index_backtick_runs("` ``x"), 0, 2
        )
        == 2
    )

    # A genuine match arbitrarily far from `start` is still found.
    far = "a" * 200_000 + "`"
    assert (
        commonmark_find_backtick_run(commonmark_index_backtick_runs(far), 0, 1)
        == 200_000
    )

    # A cell containing many distinct, non-matching backtick-run lengths must
    # still resolve in roughly linear time, not quadratic.
    def adversarial_cell(width_count):
        body = ["`" * w + "x" for w in range(1, width_count + 1)]
        body.append("`")
        return "".join(body)

    small = adversarial_cell(400)
    large = adversarial_cell(800)

    start = default_timer()
    conv._escape_cell_pipes(small)
    small_time = default_timer() - start

    start = default_timer()
    conv._escape_cell_pipes(large)
    large_time = default_timer() - start

    # Double the adversarial width count. The additive term absorbs
    # scheduler/measurement noise -- generous so a busy or throttled
    # build machine (where even trivial calls can take longer) does not
    # trip this on noise alone; the multiplier is what actually catches
    # a real return to quadratic behavior.
    assert large_time < small_time * 6 + 0.5


def test_conversion_text_to():
    """conversion: Test Text to all types"""

    response = convert_between(
        NotifyFormat.TEXT,
        NotifyFormat.HTML,
        "<title>Test Message</title><body>Body</body>",
    )

    assert (
        response
        == "&lt;title&gt;Test&nbsp;Message&lt;/title&gt;&lt;body&gt;Body&lt;"
        "/body&gt;"
    )


def test_conversion_text_to_markdown():
    """conversion: Test Text to Markdown"""

    def to_markdown(body):
        """Convert plain text through the public dispatcher."""
        return convert_between(NotifyFormat.TEXT, NotifyFormat.MARKDOWN, body)

    # CommonMark-significant characters are escaped so they read as
    # literal text instead of being misread as formatting.
    response = to_markdown("Some *text* with _markdown_ looking chars.")
    assert response == "Some \\*text\\* with \\_markdown\\_ looking chars\\."

    # Text without Markdown-significant characters is unchanged.
    assert to_markdown("hello world") == "hello world"

    # Every Markdown-significant punctuation character gets escaped.
    response = to_markdown("_*[]()~`>#+=|{}.!-")
    assert response == "\\_\\*\\[\\]\\(\\)\\~\\`\\>\\#\\+\\=\\|\\{\\}\\.\\!\\-"

    # Plain text has no escape state, so a literal backslash is escaped.
    response = to_markdown("already \\* escaped")
    assert response == "already \\\\\\* escaped"
    assert markdown_to_html(response) == "<p>already \\* escaped</p>"

    # Windows-style paths survive CommonMark rendering unchanged.
    response = to_markdown("C:\\Users\\foo")
    assert response == "C:\\\\Users\\\\foo"
    assert markdown_to_html(response) == "<p>C:\\Users\\foo</p>"

    # Backslash-plus-syntax is still literal plain text.
    response = to_markdown("\\# heading")
    assert response == "\\\\\\# heading"
    assert markdown_to_html(response) == "<p>\\# heading</p>"

    # The generic dispatcher resolves the same conversion pair.
    assert (
        convert_between(NotifyFormat.TEXT, NotifyFormat.MARKDOWN, "hello")
        == "hello"
    )


def test_conversion_markdown_to_html():
    """conversion: Test markdown to html"""

    # While this uses the underlining markdown library
    # what we're testing for are the edge cases we know it doesn't support
    # hence, `-` (a dash) with the markdown library must be a `*` to work
    # correctly
    response = convert_between(
        NotifyFormat.MARKDOWN,
        NotifyFormat.HTML,
        cleandoc("""
        ## Some Heading

        With Data:

        - Foo
        - Bar
        """),
    )

    assert "<li>Foo</li>" in response
    assert "<li>Bar</li>" in response
    assert "<h2>Some Heading</h2>" in response
    assert "<br />" not in response

    # if the - follows With Data on the very next line, it's consider to not
    # requiring indentation
    response = convert_between(
        NotifyFormat.MARKDOWN,
        NotifyFormat.HTML,
        cleandoc("""
        ## Some Heading

        With Data:
        - Foo
        - Bar
        """),
    )

    # Breaks are added:
    assert "<br />" in response
    assert "- Foo" in response
    assert "- Bar" in response

    # Table formatting
    response = convert_between(
        NotifyFormat.MARKDOWN,
        NotifyFormat.HTML,
        cleandoc("""
        First Header   | Second Header
        -------------- | -------------
        Content Cell1  | Content Cell3
        Content Cell2  | Content Cell4
        """),
    )

    assert "<table>" in response
    assert "<th>First Header</th>" in response
    assert "<th>Second Header</th>" in response
    assert "<td>Content Cell1</td>" in response
    assert "<td>Content Cell2</td>" in response
    assert "<td>Content Cell3</td>" in response
    assert "<td>Content Cell4</td>" in response


def test_conversion_commonmark_repair_chunk():
    """Test dialect-neutral repair of split or truncated CommonMark."""

    # No cut at all: input passes through unchanged.
    assert commonmark_repair_chunk("**bold** and *italic*", {}) == (
        "**bold** and *italic*",
        {},
    )

    # A complete, uncut code span within a single chunk is untouched.
    assert commonmark_repair_chunk("before ```code``` after", {}) == (
        "before ```code``` after",
        {},
    )

    # A complete, uncut link within a single chunk is untouched.
    assert commonmark_repair_chunk(
        "[label](<https://example.com>) tail", {}
    ) == ("[label](<https://example.com>) tail", {})

    # Escape a non-opening run so dialect adapters preserve it literally.
    assert commonmark_repair_chunk("a**** b", {}) == ("a\\*\\*\\*\\* b", {})

    # Preserve existing escapes rather than treating them as delimiters.
    assert commonmark_repair_chunk("a\\*b\\*c", {}) == ("a\\*b\\*c", {})

    # A message split exactly between a backslash and the character it
    # escapes must not double the backslash or free that character to
    # act as a fresh delimiter -- the escape is carried across the split.
    first, pending = commonmark_repair_chunk("aaaaa\\", {})
    assert (first, pending) == ("aaaaa\\", {"in_escape": True})
    assert commonmark_repair_chunk("*literal", pending) == (
        "*literal",
        {},
    )
    # An empty continuation chunk keeps waiting rather than losing track.
    assert commonmark_repair_chunk("", pending) == ("", {"in_escape": True})

    # Close split bold early, then discard its original closing marker.
    # Lookahead containing the delimiter justifies carrying the open span.
    assert commonmark_repair_chunk("**xxxxx", {}, next_chunk="xxxx**TAIL") == (
        "**xxxxx**",
        {"**": 1},
    )
    assert commonmark_repair_chunk("xxxx**TAIL", {"**": 1}) == (
        "xxxxTAIL",
        {"**": 0},
    )

    # Same for an italic span.
    assert commonmark_repair_chunk("*hello wor", {}, next_chunk="ld*end") == (
        "*hello wor*",
        {"*": 1},
    )
    assert commonmark_repair_chunk("ld*end", {"*": 1}) == ("ldend", {"*": 0})

    # A triple-asterisk run (bold+italic combined) cut mid-content.
    assert commonmark_repair_chunk(
        "***strong italic", {}, next_chunk="text***tail"
    ) == ("***strong italic***", {"**": 1, "*": 1})
    assert commonmark_repair_chunk("text***tail", {"**": 1, "*": 1}) == (
        "texttail",
        {"**": 0, "*": 0},
    )

    # Carry each span only when lookahead provides enough closing width.
    assert commonmark_repair_chunk(
        "**bold _italic", {}, next_chunk="a_ and b** more"
    ) == ("**bold _italic_**", {"_": 1, "**": 1})

    # Repair underscore emphasis when the later run can genuinely close.
    assert commonmark_repair_chunk("_hello wor", {}, next_chunk="ld_ end") == (
        "_hello wor_",
        {"_": 1},
    )
    assert commonmark_repair_chunk("ld_ end", {"_": 1}) == (
        "ld end",
        {"_": 0},
    )

    # Underscore-based CommonMark bold ("__") behaves the same way.
    assert commonmark_repair_chunk(
        "__strong wor", {}, next_chunk="ld__ end"
    ) == ("__strong wor__", {"__": 1})
    assert commonmark_repair_chunk("ld__ end", {"__": 1}) == (
        "ld end",
        {"__": 0},
    )

    # Ignore an intraword underscore that cannot close CommonMark emphasis.
    # The opener never gets to pair with anything, so it is escaped too.
    assert commonmark_repair_chunk("_hello wor", {}, next_chunk="ld_end") == (
        "\\_hello wor",
        {},
    )

    # Preserve complete underscore spans. A run that fails the
    # flanking rule (here, followed by whitespace) stays literal.
    assert commonmark_repair_chunk("_italic text_ done", {}) == (
        "_italic text_ done",
        {},
    )
    # Same for underscore-based strong emphasis -- never matches anything,
    # so it is escaped too.
    assert commonmark_repair_chunk("a____ b", {}) == ("a\\_\\_\\_\\_ b", {})

    # A trailing run after whitespace cannot open or close either, so it
    # is also escaped rather than left as a bare, ambiguous-looking pair.
    assert commonmark_repair_chunk("text **", {}) == ("text \\*\\*", {})

    # A lone trailing run that can theoretically open (the lookahead's
    # first character is a real letter) but finds no actual "*"/"_" in
    # that lookahead is still just literal text here -- escaped, since
    # this occurrence is never going to be carried forward either.
    assert commonmark_repair_chunk("a" * 5 + "*", {}, next_chunk="b" * 5) == (
        "a" * 5 + "\\*",
        {},
    )
    assert commonmark_repair_chunk("(_", {}, next_chunk="y") == ("(\\_", {})

    # Without a possible closer in lookahead, preserve the trailing run --
    # escaped, since this occurrence will never be carried forward.
    assert commonmark_repair_chunk("a**", {}, next_chunk="b") == (
        "a\\*\\*",
        {},
    )

    # With a possible closer, discard the trailing empty pair as noise.
    assert commonmark_repair_chunk("a**", {}, next_chunk="more*text") == (
        "a",
        {},
    )

    # Preserve a literal asterisk before valid underscore emphasis.
    assert commonmark_repair_chunk("*_a_", {}, next_chunk=" " + "x" * 99) == (
        "\\*_a_",
        {},
    )

    # A possible closer makes the same opener eligible for continuation.
    assert commonmark_repair_chunk("*_a_", {}, next_chunk=" x*x") == (
        "*_a_*",
        {"*": 1},
    )

    # Ignore a whitespace-boxed delimiter that cannot close the earlier span.
    assert commonmark_repair_chunk(
        "*_a_", {}, next_chunk=" literal * end"
    ) == ("\\*_a_", {})

    # Ignore a later opener-only run when repairing an earlier span.
    assert commonmark_repair_chunk("*_a_", {}, next_chunk=" *end") == (
        "\\*_a_",
        {},
    )

    # A delimiter-like character sitting inside a code span in the
    # lookahead is literal code content, not a real closer -- it must be
    # skipped the same way it would be if it were in this same chunk.
    assert commonmark_repair_chunk("*abc", {}, next_chunk="`x* y` tail") == (
        "\\*abc",
        {},
    )
    # Same idea for a delimiter-like character inside a link destination.
    assert commonmark_repair_chunk(
        "*abc", {}, next_chunk="](<http://x.com/a*b>) tail"
    ) == ("\\*abc", {})

    # Following text can make a boundary underscore intraword and literal.
    assert commonmark_repair_chunk("*_a_", {}, next_chunk="x" * 100) == (
        "\\*\\_a\\_",
        {},
    )

    # Use the current chunk's final character to classify a boundary closer.
    assert commonmark_repair_chunk("*hello", {}, next_chunk="* world") == (
        "*hello*",
        {"*": 1},
    )
    # Splitting the same source keeps the resulting markers balanced.
    pieces = split_dialect_chunk("*hello* world", 6, lambda body: body)
    joined = "".join(pieces)
    assert joined.count("*") % 2 == 0

    # Adjacent delimiters use source characters rather than placeholders.
    assert commonmark_repair_chunk("*_a_", {}) == ("\\*_a_", {})
    assert commonmark_repair_chunk("**_a_", {}) == ("\\*\\*_a_", {})

    # The character after bounded lookahead classifies its trailing delimiter
    # without becoming part of the scanned content.
    assert commonmark_repair_chunk(
        "_abc", {}, next_chunk="xxxx_", next_chunk_boundary_ch="w"
    ) == ("\\_abc", {})
    assert commonmark_repair_chunk(
        "_abc", {}, next_chunk="xxxx_", next_chunk_boundary_ch=" "
    ) == ("_abc_", {"_": 1})
    assert commonmark_repair_chunk("_abc", {}, next_chunk="xxxx_") == (
        "_abc_",
        {"_": 1},
    )

    # A delimiter just beyond bounded lookahead must not validate an earlier
    # opener as though it were inside the scanned slice.
    body = "_abc" + ("x" * 32) + "_word"
    lookahead_span = 4 * 8
    lookahead = body[4 : 4 + lookahead_span]
    boundary_next_ch = body[4 + lookahead_span : 4 + lookahead_span + 1]
    assert commonmark_repair_chunk(
        body[:4],
        {},
        next_chunk=lookahead,
        next_chunk_boundary_ch=boundary_next_ch or None,
    ) == ("\\_abc", {})

    # A single closer carries regular emphasis and escapes the excess marker.
    assert commonmark_repair_chunk("**bold", {}, next_chunk="x* end") == (
        "\\**bold*",
        {"*": 1},
    )
    # Consuming the pending single marker preserves an unrelated bold pair.
    assert commonmark_repair_chunk(
        "x* end unrelated **bold** later", {"*": 1}
    ) == ("x end unrelated **bold** later", {"*": 0})

    # Carry one verified regular closer and escape remaining local width.
    assert commonmark_repair_chunk("a****b", {}, next_chunk="more *text*") == (
        "a\\*\\*\\**b*",
        {"*": 1},
    )
    assert commonmark_repair_chunk("(____x", {}, next_chunk="more _text_") == (
        "(\\_\\_\\__x_",
        {"_": 1},
    )

    # Drop a split code fence while carrying its width to the next chunk.
    assert commonmark_repair_chunk("text ```code sti", {}) == (
        "text code sti",
        {"in_code": 3},
    )

    # Render a cross-message code continuation as plain text.
    assert commonmark_repair_chunk("ll going```code done", {"in_code": 3}) == (
        "ll goingcode done",
        {},
    )

    # Carry an unclosed code span into another chunk.
    assert commonmark_repair_chunk("more code", {"in_code": 3}) == (
        "more code",
        {"in_code": 3},
    )

    # Drop and carry a newly opened single-backtick span.
    assert commonmark_repair_chunk("`code no close", {}) == (
        "code no close",
        {"in_code": 1},
    )

    # Escape a link label cut across the chunk boundary.
    assert commonmark_repair_chunk("[click", {}) == ("\\[click", {})

    # Render the unmatched destination side as literal text.
    assert commonmark_repair_chunk(
        "here](<https://example.com/path>) rest", {}
    ) == ("here\\]\\(https://example.com/path\\>\\) rest", {})

    # Carry a closing marker split after its trailing ">".
    c1, pending = commonmark_repair_chunk("[label](<https://x.com>", {})
    assert (c1, pending) == (
        "[label\\]\\(https://x.com\\>",
        {"in_link_dest": True, "dest_gt": True},
    )
    c2, pending = commonmark_repair_chunk(") tail", pending)
    assert (c2, pending) == ("\\) tail", {})

    # Ignore a mid-destination ">" and continue to the real terminator.
    assert commonmark_repair_chunk("a>b>) tail", {"in_link_dest": True}) == (
        "a\\>b\\>\\) tail",
        {},
    )

    # Carry a link destination cut across chunks.
    assert commonmark_repair_chunk("[label](<https://example.com/", {}) == (
        "[label\\]\\(https://example.com/",
        {"in_link_dest": True},
    )

    # Render a carried destination's closing fragment as literal text.
    assert commonmark_repair_chunk(
        "more-path>) tail", {"in_link_dest": True}
    ) == ("more-path\\>\\) tail", {})

    # Ignore escaped characters while finding a destination terminator.
    assert commonmark_repair_chunk("a\\)b>) tail", {"in_link_dest": True}) == (
        "a\\\\\\)b\\>\\) tail",
        {},
    )

    # Carry a destination that remains unclosed.
    assert commonmark_repair_chunk(
        "still not done", {"in_link_dest": True}
    ) == ("still not done", {"in_link_dest": True})

    # Complete a destination terminator spread across three chunks.
    c1, pending = commonmark_repair_chunk(
        "[label](<https://example.com/path", {}
    )
    assert (c1, pending) == (
        "[label\\]\\(https://example.com/path",
        {"in_link_dest": True},
    )
    c2, pending = commonmark_repair_chunk("/more>", pending)
    assert (c2, pending) == (
        "/more\\>",
        {"in_link_dest": True, "dest_gt": True},
    )
    c3, pending = commonmark_repair_chunk(") tail text", pending)
    assert (c3, pending) == ("\\) tail text", {})

    # Treat a trailing ">" as literal when the next chunk lacks ")".
    c2b, pending = commonmark_repair_chunk("more>", {"in_link_dest": True})
    assert (c2b, pending) == (
        "more\\>",
        {"in_link_dest": True, "dest_gt": True},
    )
    c3b, pending = commonmark_repair_chunk("no closing paren here", pending)
    assert (c3b, pending) == (
        "no closing paren here",
        {"in_link_dest": True},
    )

    # User-provided Private Use text must not collide with internal emphasis
    # placeholders, with or without real emphasis in the same chunk.
    marker = chr(0xE000)
    attack = f"before {marker}0{marker} after"
    assert commonmark_repair_chunk(attack, {}) == (attack, {})
    assert commonmark_repair_chunk(f"*bold* {attack}", {}) == (
        f"*bold* {attack}",
        {},
    )

    # Preserve an opener-only chunk when lookahead verifies its closer.
    assert commonmark_repair_chunk("**", {}, next_chunk="abc**") == (
        "****",
        {"**": 1},
    )


def test_conversion_commonmark_scan_autolink_dest():
    """commonmark_scan_autolink_dest: scheme validation and termination."""

    # A complete autolink -- "*" inside it is not a delimiter.
    body = "<https://a*b>"
    assert commonmark_scan_autolink_dest(body, 0, len(body)) == (12, True)

    # No scheme colon at all -- never a genuine autolink.
    body = "<hello world>"
    assert commonmark_scan_autolink_dest(body, 0, len(body)) == (None, False)

    # A nested "<" disqualifies it outright.
    body = "<http:<x>"
    assert commonmark_scan_autolink_dest(body, 0, len(body)) == (None, False)

    # Whitespace inside the destination disqualifies it too.
    body = "<http: x>"
    assert commonmark_scan_autolink_dest(body, 0, len(body)) == (None, False)

    # A control character disqualifies it the same way.
    body = "<http:\x01x>"
    assert commonmark_scan_autolink_dest(body, 0, len(body)) == (None, False)

    # Valid so far but no ">" anywhere yet -- still could complete later.
    body = "<https://example.com"
    assert commonmark_scan_autolink_dest(body, 0, len(body)) == (None, True)


def test_conversion_commonmark_scan_paren_dest():
    """commonmark_scan_paren_dest: balanced parens and disqualifiers."""

    # A complete, simple bare destination.
    body = "](abc)"
    assert commonmark_scan_paren_dest(body, 1, len(body)) == 5

    # An escaped ")" does not close the destination early.
    body = "](a\\)b)"
    assert commonmark_scan_paren_dest(body, 1, len(body)) == 6

    # One level of balanced, unescaped parens is allowed.
    body = "](a(b)c)"
    assert commonmark_scan_paren_dest(body, 1, len(body)) == 7

    # Whitespace disqualifies a bare destination entirely.
    body = "](a b)"
    assert commonmark_scan_paren_dest(body, 1, len(body)) is None

    # A control character disqualifies it the same way.
    body = "](a\x01b)"
    assert commonmark_scan_paren_dest(body, 1, len(body)) is None

    # An embedded "<" also disqualifies it.
    body = "](a<b)"
    assert commonmark_scan_paren_dest(body, 1, len(body)) is None

    # No closing ")" anywhere in the slice.
    body = "](abc"
    assert commonmark_scan_paren_dest(body, 1, len(body)) is None


def test_conversion_lookahead_with_unfinished_angle_url():
    """An unterminated ``](<url`` in the lookahead stops the scan early.

    This covers the angle-bracket branch alongside the existing bare URL case.
    """
    widths = commonmark_module.commonmark_lookahead_closer_widths(
        "](<https://example.com"
    )
    assert widths == {}


def test_conversion_commonmark_repair_chunk_autolinks():
    """Standalone autolinks keep markup-like URL characters as text."""

    # URL punctuation must not close unrelated emphasis in the same chunk.
    body = "Note *this is important, see <https://a*b> for details"
    assert commonmark_repair_chunk(body, {}) == (
        "Note \\*this is important, see <https://a*b> for details",
        {},
    )

    # Lookahead ignores false emphasis closers inside URLs.
    c1, pending = commonmark_repair_chunk(
        "hello *world", {}, next_chunk=" <https://a*b> end"
    )
    assert (c1, pending) == ("hello \\*world", {})
    c2, pending = commonmark_repair_chunk(" <https://a*b> end", pending)
    assert (c2, pending) == (" <https://a*b> end", {})

    # The same split, but the terminator itself lands in a third chunk.
    c1, pending = commonmark_repair_chunk(
        "see <https://a", {}, next_chunk="*b> end"
    )
    assert (c1, pending) == ("see \\<https://a", {"in_autolink": True})
    c2, pending = commonmark_repair_chunk("*b", pending)
    assert (c2, pending) == ("\\*b", {"in_autolink": True})
    c3, pending = commonmark_repair_chunk("> end", pending)
    assert (c3, pending) == ("\\> end", {})

    # A "<" that never forms a valid scheme is left as ordinary text.
    assert commonmark_repair_chunk("a < b", {}) == ("a < b", {})


def test_conversion_commonmark_repair_chunk_bare_links():
    """commonmark_repair_chunk: bare (non-angle-bracket) link destinations."""

    # Preserve labeled bare links without scanning their URLs as emphasis.
    assert commonmark_repair_chunk("[x](https://a*b)", {}) == (
        "[x](https://a*b)",
        {},
    )

    # Escape an orphan destination and keep its contents literal.
    assert commonmark_repair_chunk("see ](a*b) now", {}) == (
        "see \\]\\(a\\*b\\) now",
        {},
    )

    # Leave an unfinished bare URL untouched without carrying state.
    assert commonmark_repair_chunk("[x](https://a*b", {}) == (
        "[x](https://a*b",
        {},
    )


def test_conversion_commonmark_lookahead_ignores_link_markup():
    """Lookahead ignores markup-like characters inside links."""

    # A complete bare link cannot close earlier emphasis.
    assert commonmark_repair_chunk(
        "*word", {}, next_chunk=" see ](a*b) now"
    ) == ("\\*word", {})

    # An unfinished bare URL cannot close earlier emphasis either.
    assert commonmark_repair_chunk("*word", {}, next_chunk=" see ](a*b") == (
        "\\*word",
        {},
    )

    # A complete autolink cannot close earlier emphasis.
    assert commonmark_repair_chunk(
        "*word", {}, next_chunk=" see <https://a*b> now"
    ) == ("\\*word", {})

    # An autolink that never closes within the lookahead span.
    assert commonmark_repair_chunk(
        "*word", {}, next_chunk=" see <https://a*b"
    ) == ("\\*word", {})

    # An invalid autolink falls back to ordinary delimiter scanning.
    assert commonmark_repair_chunk("*word", {}, next_chunk=" a < b* end") == (
        "*word*",
        {"*": 1},
    )


def test_conversion_commonmark_materialize_repair():
    """Reusable scans must match direct repair for every requested prefix."""

    lookahead_span = 64

    def _direct(body, offset, cut, pending, lookahead_span=lookahead_span):
        # The behavior commonmark_materialize_repair() must reproduce:
        # an ordinary, independent repair of body[offset:offset + cut].
        abs_cut = offset + cut
        lookahead = body[abs_cut : abs_cut + lookahead_span]
        boundary = (
            body[abs_cut + lookahead_span : abs_cut + lookahead_span + 1]
            or None
        )
        return commonmark_repair_chunk(
            body[offset:abs_cut],
            dict(pending),
            next_chunk=lookahead or None,
            next_chunk_boundary_ch=boundary,
        )

    # A shared scan answers many different cut lengths from one pass,
    # matching a direct repair of each individual prefix.
    body = "**hello** world *and* more"
    atoms, covered_end, sentinel = commonmark_scan_repair_region(
        body, {}, lookahead_span
    )
    for cut in range(1, len(body) + 1):
        assert commonmark_materialize_repair(
            body, 0, cut, {}, atoms, covered_end, sentinel, lookahead_span
        ) == _direct(body, 0, cut, {})

    # A cut inside a complete code span uses direct repair because the recorded
    # section cannot be safely reused in part.
    body = "text `code span` tail"
    atoms, covered_end, sentinel = commonmark_scan_repair_region(
        body, {}, lookahead_span
    )
    cut = body.index("code") + 2  # inside the backtick span
    assert commonmark_materialize_repair(
        body, 0, cut, {}, atoms, covered_end, sentinel, lookahead_span
    ) == _direct(body, 0, cut, {})

    # An empty prefix can still clear carried state, so it uses direct repair.
    body = ")rest of the body"
    pending = {"in_link_dest": True, "dest_gt": True}
    atoms, covered_end, sentinel = commonmark_scan_repair_region(
        body, dict(pending), lookahead_span
    )
    assert commonmark_materialize_repair(
        body,
        0,
        0,
        dict(pending),
        atoms,
        covered_end,
        sentinel,
        lookahead_span,
    ) == commonmark_repair_chunk("", dict(pending))

    # Reused scans must replay a run that only partly clears prior state.
    body = "****tail"
    pending = {"**": 1}
    atoms, covered_end, sentinel = commonmark_scan_repair_region(
        body, dict(pending), lookahead_span
    )
    assert commonmark_materialize_repair(
        body,
        0,
        len(body),
        dict(pending),
        atoms,
        covered_end,
        sentinel,
        lookahead_span,
    ) == commonmark_repair_chunk(body, dict(pending))

    # A cut beyond the reusable range falls back to direct repair.
    body = "plain text [link] tail"
    atoms, covered_end, sentinel = commonmark_scan_repair_region(
        body, {}, lookahead_span
    )
    assert covered_end < len(body)
    cut = len(body)
    assert commonmark_materialize_repair(
        body, 0, cut, {}, atoms, covered_end, sentinel, lookahead_span
    ) == _direct(body, 0, cut, {})

    # The shared closing-marker index must match direct lookahead scans.
    body = "*word" + " " * 20 + "** end"
    atoms, covered_end, sentinel = commonmark_scan_repair_region(
        body, {}, lookahead_span
    )
    closer_index, closer_covered_end = commonmark_scan_closer_runs(body)
    for cut in range(1, len(body) - lookahead_span + 1):
        assert commonmark_materialize_repair(
            body,
            0,
            cut,
            {},
            atoms,
            covered_end,
            sentinel,
            lookahead_span,
            closer_index=closer_index,
            closer_covered_end=closer_covered_end,
        ) == _direct(body, 0, cut, {})

    # A lookahead boundary inside a marker run must use direct repair because
    # the shortened run may be classified differently. Put it at the far edge
    # to exercise the closing-marker index rather than the main section scan.
    closer_lookahead_span = 8
    cut = 2
    body = "ab" + "c" * 7 + "***" + "d" * 60
    atoms, covered_end, sentinel = commonmark_scan_repair_region(
        body, {}, closer_lookahead_span
    )
    closer_index, closer_covered_end = commonmark_scan_closer_runs(body)
    assert commonmark_materialize_repair(
        body,
        0,
        cut,
        {},
        atoms,
        covered_end,
        sentinel,
        closer_lookahead_span,
        closer_index=closer_index,
        closer_covered_end=closer_covered_end,
    ) == _direct(body, 0, cut, {}, lookahead_span=closer_lookahead_span)


def test_conversion_commonmark_repair_chunk_record_atoms_link_labels():
    """record_atoms must cover a resolved "[" with no gap, in every way
    a link label can be resolved within one chunk."""

    def _assert_gapless(text, pending=None):
        # Every recorded atom's start must equal the previous atom's end,
        # beginning at 0 and reaching the end of the input text, so a
        # caller replaying these atoms never has to guess at a skipped
        # span (the exact invariant commonmark_materialize_repair() relies
        # on for cutting a shorter prefix from reusable sections).
        atoms = []
        commonmark_repair_chunk(text, dict(pending or {}), record_atoms=atoms)
        assert atoms, "expected at least one recorded atom"
        assert atoms[0][0] == 0
        for prev_atom, next_atom in zip(atoms, atoms[1:]):
            assert prev_atom[1] == next_atom[0], (prev_atom, next_atom)
        assert atoms[-1][1] == len(text)
        return atoms

    # A link label that resolves successfully within the same chunk, via
    # both the angle-bracket and bare-paren destination forms.
    _assert_gapless("prefix [label](<https://example.com>) suffix")
    _assert_gapless("prefix [label](https://example.com) suffix")

    # A label whose destination fails to parse (falls back to escaped
    # literal text) still leaves the "[" itself covered.
    _assert_gapless("prefix [label](has space) suffix")

    # A label that never reaches "](" at all in this chunk -- resolved
    # only by the end-of-scan force-escape cleanup.
    _assert_gapless("prefix [never closes")

    # Multiple pending labels, only some of which ever see a "](" attempt,
    # so both the mid-scan and end-of-scan resolution paths fire together.
    _assert_gapless("[outer [inner](<bad text](https://example.com)")

    # A label carried in from a previous chunk plus a fresh one that
    # resolves normally.
    _assert_gapless(
        "dest>) more [fresh](https://example.com)",
        pending={"in_link_dest": True},
    )

    # The atoms replay to the same text commonmark_repair_chunk() produces
    # directly, for a body whose sole link resolves within the chunk (so
    # the recorded region spans the whole body, matching what a caller
    # bypassing commonmark_scan_repair_region()'s conservative
    # before-the-first-"[" truncation would now be able to reuse).
    body = "[label](https://example.com) tail"
    atoms = []
    direct_result, _ = commonmark_repair_chunk(body, {}, record_atoms=atoms)
    sentinel = commonmark_pick_emphasis_sentinel(body)
    materialized_result, _ = commonmark_materialize_repair(
        body, 0, len(body), {}, atoms, len(body), sentinel, 64
    )
    assert materialized_result == direct_result


def test_conversion_split_dialect_chunk():
    """conversion: Test split_dialect_chunk()"""

    def identity(body):
        # Nothing to escape, so a single piece is returned untouched
        # whenever it already fits.
        return body

    assert split_dialect_chunk("", 10, identity) == [""]
    assert split_dialect_chunk("hello", 10, identity) == ["hello"]

    def double(body):
        # Doubles every character (worst-case backslash escaping).
        return "".join(f"{c}{c}" for c in body)

    # Conversion growth splits the source without dropping content.
    pieces = split_dialect_chunk("." * 10, 8, double)
    assert len(pieces) > 1
    for piece in pieces:
        assert len(piece) <= 8
    # Reversing the test conversion reconstructs the original source.
    assert "".join(piece[::2] for piece in pieces) == "." * 10

    # Emit one oversized character when necessary to guarantee progress.
    pieces = split_dialect_chunk("ab", 1, double)
    assert pieces == ["aa", "bb"]

    def escape_dots(body):
        # Mimic a dialect whose escaping requires a second split.
        return body.replace(".", "\\.")

    # Carry forced-closed bold state so the later real closer is consumed.
    body = "**" + "a.b.c." * 6 + "**" + " tail"
    pieces = split_dialect_chunk(body, 20, escape_dots)
    assert len(pieces) > 1
    joined = "".join(pieces)
    assert joined.count("**") == 2

    def strip_x(body):
        # Make every ten source characters produce one output character.
        return body.replace("x", "")

    body = "xxxxxxxxxa" * 100
    pieces = split_dialect_chunk(body, 10, strip_x)
    assert len(pieces) == 10
    assert all(piece == "a" * 10 for piece in pieces)

    # A large body with a small limit should remain linear and preserve text.
    n = 200000
    body = "hello world " * (n // 12)
    start = default_timer()
    pieces = split_dialect_chunk(body, 100, identity)
    elapsed = default_timer() - start
    assert "".join(pieces) == body
    # Generous bound -- see the note on the equivalent check above.
    assert elapsed < 90.0

    # Many dangling openers share one scan and remain escaped literals.
    many_openers = " *a" * 5000
    huge_tail = "x" * 2000000
    start = default_timer()
    text, pending = commonmark_repair_chunk(
        many_openers, {}, next_chunk=huge_tail
    )
    elapsed = default_timer() - start
    assert text == " \\*a" * 5000
    assert pending == {}
    # Generous bound -- see the note on the equivalent check above.
    assert elapsed < 40.0

    # Ignore a closer beyond bounded lookahead, matching a full repair pass.
    body = "_abc" + ("x" * 32) + "_word"
    pieces = split_dialect_chunk(body, 4, identity)
    assert "".join(pieces) == "\\_abc" + ("x" * 32) + "\\_word"

    # A tiny limit must preserve opening bold markers without blank pieces.
    pieces = split_dialect_chunk("**abc**", 4, identity)
    assert "" not in pieces
    assert pieces == ["****", "abc"]

    # Repeat dangling openers to verify bounded correction remains accurate
    # and fast across many pieces.
    unit = "_abc" + ("x" * 32) + "_word "
    body = unit * 2000
    start = default_timer()
    pieces = split_dialect_chunk(body, 50, identity)
    elapsed = default_timer() - start
    assert "".join(pieces) == body.replace("_", "\\_")
    # Generous bound -- see the note on the equivalent check above.
    assert elapsed < 90.0

    # A longer repaired prefix can fit after an earlier one overflows.
    # Verify the discarded bisection range with a real dialect conversion.
    body = (
        "|\t-(|::+<_\ta(*&__][]:\t>{)] =#= \t.(\\-[){~]+-]{{#=_\\>)-{\t#>[*_"
    )
    pieces = split_dialect_chunk(
        body, 22, NotifyGoogleChat._commonmark_to_google_chat
    )
    assert pieces[0] == "|\t-(|::+<\\_\ta(_&amp;_"
    assert len(pieces[0]) == 21

    # A repaired prefix may fit just above the result found by bisection.
    # Checking upward catches it without crossing the entire failed range.
    body = "*)\\\\`<*(>([*] \\>_]`\\>(]*`))_`_ \\]`[.<*_*<*<]>.>\\a)], _ <a"
    pieces = split_dialect_chunk(body, 29, NotifySlack._commonmark_to_slack)
    assert len(pieces[0]) <= 29
    reconstructed_len = 19  # confirmed via exhaustive brute-force search
    repaired, _ = commonmark_repair_chunk(
        body[:reconstructed_len], {}, next_chunk=body[reconstructed_len:]
    )
    assert pieces[0] == NotifySlack._commonmark_to_slack(repaired)

    # A repaired prefix may also fit near the far end of the checked range.
    body = "*(`<]<[xxxxxxxxxxxx`<xxxxxxxxxx_]"

    def strip_x(text):
        # Simulate a converter that removes a long run so the result fits.
        return text.replace("x", "")

    pieces = split_dialect_chunk(body, 10, strip_x)
    assert pieces == ["\\*(`<]<[`<", "\\_]"]
    assert "".join(pieces).replace("x", "") == "".join(pieces)

    # Many unmatched ``*`` markers must scale with input size. The generous
    # limit allows slow test hosts while still catching severe regressions.
    n = 20000
    body = ("*a " * (n // 3))[:n]
    start = default_timer()
    pieces = split_dialect_chunk(body, 160, identity)
    elapsed = default_timer() - start
    assert "".join(pieces) == body.replace("*", "\\*")
    assert elapsed < 45.0

    # Exercise real Slack-sized splits and the shared repair path. This checks
    # whole-message splitting; matcher scaling has a focused test below.
    small_n = 40000
    large_n = 80000
    small_body = ("*a " * ((small_n + 2) // 3))[:small_n]
    large_body = ("*a " * ((large_n + 2) // 3))[:large_n]

    # Interleave two rounds and keep each size's fastest result to reduce
    # timing noise.
    small_time = large_time = None
    for _ in range(2):
        start = default_timer()
        split_dialect_chunk(
            small_body, 35000, NotifySlack._commonmark_to_slack
        )
        elapsed = default_timer() - start
        small_time = (
            elapsed if small_time is None else min(small_time, elapsed)
        )

        start = default_timer()
        split_dialect_chunk(
            large_body, 35000, NotifySlack._commonmark_to_slack
        )
        elapsed = default_timer() - start
        large_time = (
            elapsed if large_time is None else min(large_time, elapsed)
        )

    # Doubling the body should not approach four times the runtime.
    assert large_time < small_time * 3.5 + 1.0


def test_conversion_truncate_dialect_chunk():
    """conversion: Test truncate_dialect_chunk()"""

    def identity(body):
        return body

    # An empty body has nothing to convert or truncate.
    assert truncate_dialect_chunk("", 10, identity) == ""

    # A body that already fits after conversion is returned whole.
    assert truncate_dialect_chunk("hello", 10, identity) == "hello"

    def double(body):
        # Doubles every character (worst-case backslash escaping).
        return "".join(f"{c}{c}" for c in body)

    # Truncation keeps only the longest converted prefix that fits.
    piece = truncate_dialect_chunk("." * 10, 8, double)
    assert len(piece) <= 8
    assert piece == ".." * 4

    # Return one oversized character rather than making no progress.
    assert truncate_dialect_chunk("ab", 1, double) == "aa"

    def strip_x(body):
        # Make every source block contribute one output character.
        return body.replace("x", "")

    # Continue searching beyond a fixed limit-derived window.
    body = "xxxxxxxxxa" * 100
    piece = truncate_dialect_chunk(body, 10, strip_x)
    assert piece == "a" * 10


def test_conversion_commonmark_scan_delimiter_run():
    """conversion: Test commonmark_scan_delimiter_run()"""

    # Middle runs read both neighbors directly.
    assert commonmark_scan_delimiter_run("a**b", 1) == (3, "a", "b")

    # A starting run uses the optional preceding boundary.
    assert commonmark_scan_delimiter_run("*a", 0) == (1, None, "a")
    assert commonmark_scan_delimiter_run("*a", 0, boundary_prev_ch="x") == (
        1,
        "x",
        "a",
    )

    # An ending run uses the optional following boundary.
    assert commonmark_scan_delimiter_run("a*", 1) == (2, "a", None)
    assert commonmark_scan_delimiter_run("a*", 1, boundary_next_ch="y") == (
        2,
        "a",
        "y",
    )

    # Both boundaries can apply at once to a run that is the entire text.
    assert commonmark_scan_delimiter_run(
        "**", 0, boundary_prev_ch="x", boundary_next_ch="y"
    ) == (2, "x", "y")

    # Underscore runs measure the same way as asterisk runs.
    assert commonmark_scan_delimiter_run("a___b", 1) == (4, "a", "b")


def test_conversion_commonmark_can_open_close_emphasis():
    """conversion: Test commonmark_can_open_emphasis()/
    commonmark_can_close_emphasis()"""

    # A run at the very start of the text, followed by real content,
    # is left-flanking only: it can open but not close.
    assert commonmark_can_open_emphasis("*", None, "f") is True
    assert commonmark_can_close_emphasis("*", None, "f") is False

    # A run at the very end, preceded by real content, is
    # right-flanking only: it can close but not open.
    assert commonmark_can_open_emphasis("*", "o", None) is False
    assert commonmark_can_close_emphasis("*", "o", None) is True

    # A run with real content on both sides can do either, for "*".
    assert commonmark_can_open_emphasis("*", "o", "b") is True
    assert commonmark_can_close_emphasis("*", "o", "b") is True

    # "_" carries an extra intraword restriction "*" does not: a run
    # flanked by real content on both sides is both left- and
    # right-flanking at once, which underscore is never allowed to
    # open or close with, so it is left as literal text instead.
    assert commonmark_can_open_emphasis("_", "o", "b") is False
    assert commonmark_can_close_emphasis("_", "o", "b") is False


def test_conversion_commonmark_pick_emphasis_sentinel():
    """conversion: Test commonmark_pick_emphasis_sentinel()"""

    # An ordinary body with no Private Use Area characters at all
    # picks a single one, the narrowest candidate available.
    assert commonmark_pick_emphasis_sentinel("hello world") == chr(0xE000)

    # Existing candidates make the sentinel double until it is unique.
    assert commonmark_pick_emphasis_sentinel(chr(0xE000)) == chr(0xE000) * 2
    assert commonmark_pick_emphasis_sentinel(chr(0xE000) * 3) == (
        chr(0xE000) * 4
    )

    # Doubling also handles long collision runs efficiently.
    picked = commonmark_pick_emphasis_sentinel(chr(0xE000) * 100000)
    assert picked not in chr(0xE000) * 100000
    assert len(picked) == 131072

    # Sentinel selection remains deterministic for the same input.
    assert commonmark_pick_emphasis_sentinel(
        "hello world"
    ) == commonmark_pick_emphasis_sentinel("hello world")


def test_conversion_commonmark_emphasis_sentinel_collision():
    """Preserve user text shaped like an internal emphasis placeholder."""
    # Build the former hard-coded placeholder without embedding invisible text.
    marker = chr(0xE000)
    attack = f"before {marker}0{marker} after"

    out = []
    delimiters = []
    i = 0
    n = len(attack)
    sentinel = commonmark_pick_emphasis_sentinel(attack)
    while i < n:
        if attack[i] == "*":
            i = commonmark_emphasis_run(
                attack, i, n, delimiters, out, sentinel
            )
            continue
        out.append(attack[i])
        i += 1
    rendered = commonmark_render_emphasis_markers(
        "".join(out), delimiters, ("*", "*"), ("_", "_"), sentinel
    )

    # No real emphasis was present, so the attempted collision passes
    # straight through untouched rather than raising or corrupting.
    assert rendered == attack


def test_conversion_commonmark_emphasis_run():
    """conversion: Test commonmark_emphasis_run()"""

    def convert(body):
        # Collect, resolve, and render runs like the dialect adapters.
        out = []
        delimiters = []
        i = 0
        n = len(body)
        sentinel = commonmark_pick_emphasis_sentinel(body)
        while i < n:
            if body[i] == "*":
                i = commonmark_emphasis_run(
                    body, i, n, delimiters, out, sentinel
                )
                continue
            out.append(body[i])
            i += 1
        return commonmark_render_emphasis_markers(
            "".join(out), delimiters, ("*", "*"), ("_", "_"), sentinel
        )

    # Preserve an opener with no closer.
    assert convert("****a") == "****a"

    # Keep the ambiguous middle run literal under the modulo-three rule.
    assert convert("*foo**bar*") == "_foo**bar_"

    # Split one closing run across two nested regular spans.
    assert convert("*foo *bar**") == "_foo _bar__"

    # Split a width-three opener between regular and strong emphasis.
    assert convert("***foo* bar**") == "*_foo_ bar*"

    assert convert("*a*") == "_a_"
    assert convert("**a**") == "*a*"

    # A single run wide enough to supply both kinds of emphasis nests
    # regular emphasis outermost and bold innermost.
    assert convert("***a***") == "_*a*_"


def test_conversion_commonmark_match_emphasis():
    """conversion: Test commonmark_match_emphasis()"""

    def descriptor(char, numdelims, can_open, can_close):
        return {
            "char": char,
            "numdelims": numdelims,
            "origdelims": numdelims,
            "can_open": can_open,
            "can_close": can_close,
            "events": [],
        }

    # Match the outer pair while leaving an ambiguous middle run literal.
    delimiters = [
        descriptor("*", 1, True, False),
        descriptor("*", 2, True, True),
        descriptor("*", 1, False, True),
    ]
    commonmark_match_emphasis(delimiters)
    assert delimiters[0]["numdelims"] == 0
    assert delimiters[0]["events"] == [("open", False)]
    assert delimiters[1]["numdelims"] == 2
    assert delimiters[1]["events"] == []
    assert delimiters[2]["numdelims"] == 0
    assert delimiters[2]["events"] == [("close", False)]

    # A run wide enough to open both regular and strong emphasis
    # records both events against a matching closer run, strong first.
    delimiters = [
        descriptor("*", 3, True, False),
        descriptor("*", 3, False, True),
    ]
    commonmark_match_emphasis(delimiters)
    assert delimiters[0]["numdelims"] == 0
    assert delimiters[0]["events"] == [("open", True), ("open", False)]
    assert delimiters[1]["numdelims"] == 0
    assert delimiters[1]["events"] == [("close", True), ("close", False)]

    # Different characters never close each other, even with matching
    # widths and flanking on both sides.
    delimiters = [
        descriptor("*", 1, True, False),
        descriptor("_", 1, False, True),
    ]
    commonmark_match_emphasis(delimiters)
    assert delimiters[0]["numdelims"] == 1
    assert delimiters[0]["events"] == []
    assert delimiters[1]["numdelims"] == 1
    assert delimiters[1]["events"] == []

    # Compare two adversarial sizes so quadratic matching approaches 4x
    # growth. The ratio also tolerates slower test hosts.
    small_n = 6000
    large_n = 12000
    small_body = ("*a " * small_n) + ("b* " * small_n)
    large_body = ("*a " * large_n) + ("b* " * large_n)

    # Interleave several rounds and keep each size's fastest result. This
    # reduces noise from scheduling, garbage collection, and background load.
    small_time = large_time = None
    for _ in range(5):
        start = default_timer()
        text, pending = commonmark_repair_chunk(small_body, {})
        elapsed = default_timer() - start
        small_time = (
            elapsed if small_time is None else min(small_time, elapsed)
        )
        # Every opener has a closer, so the complete message stays unchanged.
        assert text == small_body
        assert pending == {}

        start = default_timer()
        text, pending = commonmark_repair_chunk(large_body, {})
        elapsed = default_timer() - start
        large_time = (
            elapsed if large_time is None else min(large_time, elapsed)
        )
        assert text == large_body
        assert pending == {}

    # Doubling input should remain near linear; the additive margin covers
    # timer noise at these short runtimes.
    assert large_time < small_time * 3.0 + 0.1


def test_conversion_commonmark_render_emphasis_events():
    """conversion: Test commonmark_render_emphasis_events()"""

    strong = ("<b>", "</b>")
    regular = ("<i>", "</i>")

    # No events at all: nothing renders around the leftover text.
    assert commonmark_render_emphasis_events([], strong, regular) == (
        "",
        "",
    )

    # A single open renders on the open side only.
    assert commonmark_render_emphasis_events(
        [("open", False)], strong, regular
    ) == ("", "<i>")

    # A single close renders on the close side only.
    assert commonmark_render_emphasis_events(
        [("close", True)], strong, regular
    ) == ("</b>", "")

    # Two opens render outermost first, since the last one recorded is
    # the outermost span.
    assert commonmark_render_emphasis_events(
        [("open", True), ("open", False)], strong, regular
    ) == ("", "<i><b>")

    # Two closes render innermost first, in the order they were
    # recorded.
    assert commonmark_render_emphasis_events(
        [("close", True), ("close", False)], strong, regular
    ) == ("</b></i>", "")
