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

import pytest

from apprise import NotifyFormat
from apprise.conversion import (
    BLOCKQUOTE_DEPTH_MAX,
    LIST_DEPTH_MAX,
    MAX_FRAME_DEPTH,
    HTMLMarkdownConverter,
    convert_between,
)

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

    # Leading/trailing whitespace must not defeat scheme detection\
    assert to_md('<a href="  javascript:alert(1)">click</a>') == (
        "[click](<#>)"
    )
    assert to_md('<a href=" \tjavascript:alert(1)">click</a>') == (
        "[click](<#>)"
    )
    assert to_md('<a href="javascript:alert(1)  ">click</a>') == (
        "[click](<#>)"
    )

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
    assert elapsed < 3.0

    # Performance: many UNCLOSED <li> tags nested directly inside one another.
    n = 20000
    html = "<li>x" * n
    start = default_timer()
    out = to_md(html)
    elapsed = default_timer() - start
    assert len(out) < 10 * n  # output itself is linear, not quadratic
    assert elapsed < 3.0

    # Performance: many open <blockquote> tags followed by many closing tags of
    # a *different* kind that's never actually open ("</pre>").
    n = 20000
    html = "<blockquote>" * n + "</pre>" * n
    start = default_timer()
    out = to_md(html)
    elapsed = default_timer() - start
    assert len(out) < 20 * n
    assert elapsed < 3.0

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
    assert elapsed < 3.0

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
    assert elapsed < 5.0


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

    # build_backtick_run_index() / find_unescaped_run() skip escape pairs
    # while indexing, and the lookup returns None when no run of the exact.
    assert (
        conv.find_unescaped_run(conv.build_backtick_run_index("\\` `"), 0, 1)
        == 3
    )
    assert (
        conv.find_unescaped_run(
            conv.build_backtick_run_index("no backticks here"), 0, 1
        )
        is None
    )
    assert (
        conv.find_unescaped_run(
            conv.build_backtick_run_index("``too short"), 0, 3
        )
        is None
    )

    # A genuine match arbitrarily far from `start` is still found.
    far = "a" * 200_000 + "`"
    assert (
        conv.find_unescaped_run(conv.build_backtick_run_index(far), 0, 1)
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

    # Doubling the adversarial width count should roughly double the (tiny)
    # runtime, not quadruple it.
    assert large_time < small_time * 6 + 0.05


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
