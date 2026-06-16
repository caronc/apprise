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

import pytest

from apprise import NotifyFormat
from apprise.conversion import HTMLMarkdownConverter, convert_between

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
    """conversion: Test HTML to Markdown."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Plain text with no HTML passes through unchanged
    assert to_md("No HTML code here.") == "No HTML code here."

    # Empty string in, empty string out
    assert to_md("") == ""

    # Paragraphs collapse to newline-separated text
    assert (
        to_md("<p>line 1</p><p>line 2</p><p>line 3</p>")
        == "line 1\nline 2\nline 3"
    )

    # Case sensitivity -- tag names are case-insensitive in HTML
    assert (
        to_md("<p>line 1</P><P>line 2</P><P>line 3</P>")
        == "line 1\nline 2\nline 3"
    )

    # HTMLParser lowercases ALL tag names -- inline tags included
    assert to_md("<B>bold text</B>") == "**bold text**"
    assert to_md("<I>italic</I>") == "*italic*"

    # Uppercase and mixed-case self-closing <BR/> also produce newlines
    assert (
        to_md("line one<BR/>line two<BR />line three")
        == "line one\nline two\nline three"
    )

    # <br> and self-closing <br/> both emit a literal newline
    assert (
        to_md("some information<br/><br>and more information")
        == "some information\n\nand more information"
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
        "#### Heading 4\n##### Heading 5\n###### Heading 6\n"
        "line 1\n*line 2*\nline 3>"
    )

    # <b> and <strong> both produce bold markers
    assert to_md("<b>bold text</b>") == "**bold text**"
    assert to_md("<strong>bold text</strong>") == "**bold text**"

    # <i> and <em> both produce italic markers
    assert to_md("<i>italic</i>") == "*italic*"
    assert to_md("<em>italic</em>") == "*italic*"

    # Inline bold wrapping a paragraph
    assert (
        to_md(
            "<body><div>line 1 <b>bold</b></div> "
            " <a href='/link'>my link</a>"
            "<p>3rd line</body>"
        )
        == "line 1 **bold**\n[my link](/link)\n3rd line"
    )

    # <a href="..."> produces Markdown link syntax
    assert (
        to_md("<span></span<<span>test</span> <a href='#'>my link</a>")
        == "test [my link](#)"
    )

    # <a> with nested inline markup -- the href must survive the child tags
    assert (
        to_md("<a href='/x'><b>hello</b> world</a>") == "[**hello** world](/x)"
    )
    assert (
        to_md("<a href='/x'><strong>label</strong></a>") == "[**label**](/x)"
    )
    assert (
        to_md("<a href='/x'><em>italic</em> and plain</a>")
        == "[*italic* and plain](/x)"
    )

    # Nested <a> -- inner href wins for its own span; outer wraps the rest
    assert (
        to_md("<a href='/outer'>text <a href='/inner'>link</a></a>")
        == "[text [link](/inner)](/outer)"
    )

    # <a> with no href attribute -- content rendered as plain text
    assert to_md("<span>test</span> <a>no link</a>") == "test no link"

    # Bare <a name="..."> anchor (no href) -- text passes through unchanged
    assert to_md("<a name='top'>jump target</a>") == "jump target"

    # <span> is inline -- it passes text through without a newline;
    # <div> is block-level and always produces a newline around its content
    assert to_md("<div>block</div><span>inline</span>") == "block\ninline"

    # HTML comments are stripped entirely; surrounding text is preserved
    assert to_md("<!-- comment --> text") == "text"
    assert to_md("a<!-- c1 -->b<!-- c2 -->c") == "abc"

    # <![CDATA[...]]> sections are gracefully ignored (content is dropped,
    # text outside the CDATA boundary is kept)
    assert to_md("text<![CDATA[data]]> here") == "text here"
    assert to_md("<![CDATA[data]]>text") == "text"

    # Inline <code> wraps in backticks without a block boundary
    assert to_md("<code>func()</code>") == "`func()`"

    # Markdown special characters inside <code> are NOT escaped --
    # backtick delimiters already make content literal
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
        == "line 1\nAnother line without being enclosed"
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
        == "Let's handle special html encoding\n---"
    )

    # Missing </p> is handled gracefully
    assert (
        to_md(
            "<h2>Heading</h2><p>And a paragraph too.<br>Plus line break.</p>"
        )
        == "## Heading\nAnd a paragraph too.\nPlus line break."
    )

    with pytest.raises(TypeError):
        to_md(None)

    with pytest.raises(TypeError):
        to_md(42)

    with pytest.raises(TypeError):
        to_md(object)


def test_conversion_html_to_markdown_lists():
    """conversion: Test HTML list nesting and numbering in Markdown."""

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

    # Malformed HTML: missing </li> in a <ul>
    # HTMLParser does not synthesize implicit close events; each missing
    # </li> is simply absent, but the next <li> still starts a new item
    assert (
        to_md("<ul><li>item A<li>item B<li>item C</ul>")
        == "- item A\n- item B\n- item C"
    )

    # Malformed HTML: missing </li> in a <ol>
    # Without </li> the counter is never incremented, so all items
    # render as "1." -- this is expected garbage-in/garbage-out behaviour
    assert (
        to_md("<ol><li>one<li>two<li>three</ol>") == "1. one\n1. two\n1. three"
    )

    # Malformed HTML: missing closing </ul>

    assert to_md("<ul><li>item A</li><li>item B</li>") == "- item A\n- item B"

    # Malformed HTML: missing </li> AND missing </ul>

    assert to_md("<ul><li>item A<li>item B") == "- item A\n- item B"

    # Malformed HTML: bare text inside <ul> (no <li> wrapper)
    # <ul> is in IGNORE_TAGS so unwrapped text is suppressed entirely
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

    # <pre> inside <li>: fenced block with indentation preserved

    assert (
        to_md("<ul><li>code:<pre>  indented\n  here</pre></li></ul>")
        == "- code:\n```\n  indented\n  here\n```"
    )

    # <pre> inside a nested <li>: indentation inside the fence is
    # preserved regardless of the surrounding list nesting depth
    assert (
        to_md(
            "<ul><li>outer<ul><li>inner:<pre>  x = 1</pre></li></ul></li></ul>"
        )
        == "- outer\n  - inner:\n```\n  x = 1\n```"
    )

    # A block element as the first child of <li> used to emit a spurious
    # BLOCK_END that orphaned the marker on its own line.  The fix detects
    # a list marker as _result[-1] and suppresses the redundant BLOCK_END.

    # Single item with a <p> first child
    assert to_md("<ul><li><p>alpha</p></li></ul>") == "- alpha"

    # Multiple items each with a <p> first child
    assert (
        to_md("<ul><li><p>alpha</p></li><li><p>beta</p></li></ul>")
        == "- alpha\n- beta"
    )

    # Multiple <p> children inside one <li>: first is joined to marker,
    # subsequent ones start on new lines
    assert to_md("<ul><li><p>one</p><p>two</p></li></ul>") == "- one\ntwo"

    # Mixed: direct text for first item, <p> for second
    assert (
        to_md("<ul><li>direct</li><li><p>wrapped</p></li></ul>")
        == "- direct\n- wrapped"
    )

    # Numbered list with <p> children
    assert (
        to_md("<ol><li><p>first</p></li><li><p>second</p></li></ol>")
        == "1. first\n2. second"
    )

    # <a> link as first child of <li> -- the marker must share the line
    assert to_md("<ul><li><a href='/x'>link</a></li></ul>") == "- [link](/x)"

    # <a> with nested markup as first (and only) child of <li>
    assert (
        to_md("<ul><li><a href='/x'><b>bold link</b></a></li></ul>")
        == "- [**bold link**](/x)"
    )

    # <a> link followed by a <p> sibling inside the same <li>
    assert (
        to_md("<ul><li><a href='/x'>link</a><p>more</p></li></ul>")
        == "- [link](/x)\nmore"
    )


def test_conversion_html_to_markdown_escaping():
    """conversion: HTMLMarkdownConverter avoids generating broken
    Markdown when content collides with its own delimiters, or when
    ignored containers would otherwise leak Markdown syntax."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Code/pre delimiter collision
    # A backtick inside <code> widens the inline delimiter so it can't
    # be closed early by a backtick already present in the content
    assert to_md("<code>a`b</code>") == "``a`b``"

    # Content starting or ending with a backtick gets a padding space,
    # per CommonMark's code-span disambiguation rule
    assert to_md("<code>`x</code>") == "`` `x ``"
    assert to_md("<code>x`</code>") == "`` x` ``"

    # A run of 3 backticks inside <pre> widens the fence past 3
    assert to_md("<pre>boom```</pre>") == "````\nboom```\n````"

    # Plain content with no backticks still uses the minimal delimiter
    assert to_md("<pre>x</pre>") == "```\nx\n```"

    # Ignored containers must not leak Markdown markers
    # Only the suppressed text is dropped in the original report --
    # here the "**" markers from <b> must not leak either
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

    # A list marker ("- ") must not leak from a <li> nested inside a
    # suppressed container, even though <li> normally re-enables storage
    assert (
        to_md("<head><ul><li>hidden item</li></ul></head><body>text</body>")
        == "text"
    )

    # <script> content (already suppressed) must not leak nested markers
    assert to_md("<script>ignore <b>this</b></script><p>keep</p>") == "keep"

    # A <pre> block fully inside a suppressed container emits nothing,
    # not even an empty fence
    assert to_md("<script>ignore<pre>code</pre></script><p>keep</p>") == "keep"

    # --- Link destinations with whitespace ---
    # A bare Markdown link destination cannot contain a space; wrap it
    # in angle brackets so the link target isn't silently truncated
    assert to_md("<a href='/my page'>link</a>") == "[link](</my page>)"

    # --- Nested tags inside code/pre are inert ---
    # Their own markup carries no meaning, but their literal text still
    # joins the buffered content (no out-of-order marker leakage)
    assert (
        to_md("<pre>before <a href='/x'>link</a> after</pre>")
        == "```\nbefore link after\n```"
    )
    assert (
        to_md("<code>before <b>bold</b> after</code>") == "`before bold after`"
    )

    # --- Stray code/pre/samp close tags ---
    # _pop_to() finds no matching frame; the early-return path in
    # handle_endtag must not crash or emit a spurious delimiter
    assert to_md("</code>text") == "text"
    assert to_md("</pre>text") == "text"
    assert to_md("</samp>text") == "text"


def test_conversion_html_to_markdown_hardening():
    """conversion: HTMLMarkdownConverter is robust against stack edge cases."""

    def to_md(body):
        """Wrapper to simplify html-to-markdown conversion tests."""
        return convert_between(NotifyFormat.HTML, NotifyFormat.MARKDOWN, body)

    # Stray close tags before any matching open tag
    # _pop_to() must find no matching frame and silently do nothing;
    # the root sentinel frame must remain untouched throughout.

    # </ul> and </ol> take the early-return path in handle_endtag
    assert to_md("</ul>text") == "text"
    assert to_md("</ol>text") == "text"

    # </li> emits a BLOCK_END but _pop_to still finds nothing -- the
    # text that follows is unindented and stored normally
    assert to_md("</li>text") == "text"

    # Multiple stray close tags in a row must not crash or corrupt state
    assert to_md("</ul></ol></li>preamble") == "preamble"

    # A valid list after a stray close must still render correctly
    assert to_md("</ul><ul><li>A</li><li>B</li></ul>") == "- A\n- B"

    # _make_frame() empty-stack guard
    # The root sentinel makes this path unreachable through normal
    # parsing; we force it by clearing _stack directly to verify the
    # fallback produces safe root-equivalent defaults.

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
