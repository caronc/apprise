# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
from apprise.utils.format import smart_split


def test_smart_split_prefers_newlines_over_spaces_and_punctuation():
    """
    Newlines should win even if there are spaces and punctuation before the
    limit.
    """
    text = "line1\nline2 line3. line4"
    # Long enough to include the newline and some of the next line
    limit = 12

    chunks = smart_split(text, limit, body_format=NotifyFormat.TEXT)

    # First chunk should end immediately after the newline
    assert chunks[0] == "line1\n"
    # Nothing lost
    assert "".join(chunks) == text


def test_smart_split_prefers_spaces_over_hard_split():
    """
    When there are no newlines, split on the last space/tab before falling back
    to a hard character-limit split.
    """
    text = "word1 word2 word3"
    # Force a split between word2 and word3
    limit = 12  # "word1 word2 " is 12 characters

    chunks = smart_split(text, limit, body_format=NotifyFormat.TEXT)

    assert chunks == ["word1 word2 ", "word3"]
    assert "".join(chunks) == text


def test_smart_split_can_split_after_punctuation_plus_whitespace():
    """
    Exercise the punctuation+whitespace pattern. In practice this collapses
    to the same split point as the last space, but we verify the behaviour.
    """
    text = "Hello world. Again"
    # Force the split around ". "

    # "Hello world. " is 13 characters
    limit = 13

    chunks = smart_split(text, limit, body_format=NotifyFormat.TEXT)

    # First chunk should end at the space after the period
    assert chunks[0] == "Hello world. "
    assert chunks[1] == "Again"
    assert "".join(chunks) == text


def test_smart_split_avoids_splitting_inside_html_entity() -> None:
    """
    In HTML mode we must not end a chunk in the middle of '&...;'.

    We do NOT assert exact chunk values. Instead we assert:
    - TEXT mode can split inside the entity.
    - HTML mode never has a chunk that contains '&' without a matching ';'
      after it in the same chunk.
    """
    text = "1234&nbsp;5678"
    limit = 8  # without adjustment, we would cut inside '&nbsp;'

    # Plain text mode: allowed to split anywhere
    chunks_text = smart_split(text, limit, body_format=NotifyFormat.TEXT)
    assert "".join(chunks_text) == text

    # Sanity: in TEXT mode we *do* split inside the entity
    assert any(
        "&" in chunk and ";" not in chunk[chunk.find("&") :]
        for chunk in chunks_text
    )

    # HTML mode: entity-aware
    chunks_html = smart_split(text, limit, body_format=NotifyFormat.HTML)
    assert "".join(chunks_html) == text

    # If a chunk contains '&', it must also contain the terminating ';'
    # for that entity within the same chunk.
    for chunk in chunks_html:
        idx = chunk.find("&")
        if idx == -1:
            continue
        semi = chunk.find(";", idx + 1)
        assert semi != -1, f"Chunk ends inside HTML entity: {chunk!r}"


def test_smart_split_avoids_splitting_inside_markdown_link() -> None:
    """
    In MARKDOWN mode, do not split inside [text](url).

    We only require that the full [link](...) lies in a single chunk and that
    any '[' appearing in a chunk has a matching ')' in that same chunk.
    """
    link = "[link](https://example.com)"
    text = "AAAA" + link
    limit = len(link)

    chunks = smart_split(text, limit, body_format=NotifyFormat.MARKDOWN)
    assert "".join(chunks) == text

    # Entire link must be contained in one chunk
    assert any(link in chunk for chunk in chunks)

    # If a chunk has '[', it must also contain its closing ')'
    for chunk in chunks:
        idx = chunk.find("[")
        if idx == -1:
            continue
        semi = chunk.find(")", idx + 1)
        assert semi != -1, f"Markdown link was split inside chunk: {chunk!r}"


def test_smart_split_avoids_splitting_inside_markdown_image() -> None:
    """
    In MARKDOWN mode, do not split inside the [alt](url) of an image.

    The implementation currently splits "AAAA![alt](...)" as:
      - "AAAA!"
      - "[alt](...)"
    which is acceptable, as the [alt](url) part is kept intact.
    """
    image = "![alt](https://example.com/image.png)"
    text = "AAAA" + image
    limit = len(image)

    chunks = smart_split(text, limit, body_format=NotifyFormat.MARKDOWN)
    assert "".join(chunks) == text

    inner = "[alt](https://example.com/image.png)"

    # The [alt](...) portion must appear fully within a single chunk
    assert any(inner in chunk for chunk in chunks)

    # As with links, any '[' in a chunk must have its matching ')' within
    # the same chunk so we never split inside the [alt](url) part.
    for chunk in chunks:
        idx = chunk.find("[")
        if idx == -1:
            continue
        semi = chunk.find(")", idx + 1)
        assert semi != -1, f"Markdown image was split inside chunk: {chunk!r}"


def test_smart_split_empty_and_none_input() -> None:
    """
    Empty / None input should be returned as a single-element list unchanged.
    """
    assert smart_split("", 10, body_format=NotifyFormat.TEXT) == [""]
    assert smart_split("", 0, body_format=NotifyFormat.TEXT) == [""]
    assert smart_split("content", 0, body_format=NotifyFormat.TEXT) == [""]
    # None short-circuits before len() is called
    assert smart_split(None, 10, body_format=NotifyFormat.TEXT) == [""]


def test_smart_split_html_entity_exact_boundary() -> None:
    """
    Splitting exactly at an HTML entity boundary should not shift the split
    point (no need to "fix up" a perfectly aligned boundary).
    """
    text = "AAAA&nbsp;BBBB"
    limit = len("AAAA&nbsp;")  # split exactly after the entity

    chunks = smart_split(text, limit, body_format=NotifyFormat.HTML)

    # We expect the entity to remain whole in the first chunk
    assert chunks == ["AAAA&nbsp;", "BBBB"]
    assert "".join(chunks) == text


def test_smart_split_markdown_link_exact_boundary() -> None:
    """
    Splitting exactly after a Markdown link should not cause any adjustment.
    """
    link = "[link](https://example.com)"
    tail = " TAIL"
    text = link + tail
    limit = len(link)  # split immediately after ')'

    chunks = smart_split(text, limit, body_format=NotifyFormat.MARKDOWN)

    # First chunk is exactly the link, second is the remainder
    assert chunks[0] == link
    assert "".join(chunks) == text

    # Sanity: the link itself is not split across chunks
    assert any(link in chunk for chunk in chunks)


def test_smart_split_whitespace_priority_with_tabs_and_newlines() -> None:
    """
    Exercise newline vs space/tab priority with a mix of whitespace.
    """
    text = "word1\tword2\nword3"

    # Case 1: window ends just before the newline, so only tab is visible.
    limit_without_newline = text.index("\n")  # position of '\n'
    chunks_no_nl = smart_split(
        text, limit_without_newline, body_format=NotifyFormat.TEXT
    )
    # First chunk should end after the tab, since that is the last space/tab
    assert chunks_no_nl[0] == "word1\t"
    assert "".join(chunks_no_nl) == text

    # Case 2: window includes the newline; newline should win over tab.
    limit_with_newline = text.index("\n") + 1
    chunks_with_nl = smart_split(
        text, limit_with_newline, body_format=NotifyFormat.TEXT
    )
    # First chunk should now end after the newline
    assert chunks_with_nl[0] == "word1\tword2\n"
    assert "".join(chunks_with_nl) == text


def test_smart_split_very_short_limit() -> None:
    """
    Very small limits should still split deterministically without loss.
    """
    text = "ABC"
    chunks = smart_split(text, 1, body_format=NotifyFormat.TEXT)

    # One character per chunk
    assert chunks == ["A", "B", "C"]
    assert "".join(chunks) == text


def test_smart_split_very_long_limit() -> None:
    """
    Very large limits (>= len(text)) should return a single chunk.
    """
    text = "A short message for testing"
    chunks = smart_split(text, 10_000, body_format=NotifyFormat.TEXT)

    assert chunks == [text]
    assert "".join(chunks) == text
