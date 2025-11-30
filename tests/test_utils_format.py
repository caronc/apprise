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
from apprise.utils.format import html_adjust, markdown_adjust, smart_split


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


def test_html_adjust_guard_paths_and_no_entity() -> None:
    """
    Cover the early-return guard in html_adjust and the path where there is
    no '&' at all in the search window.
    """
    text = "abcdef"

    # split_at <= window_start -> early-return unchanged
    assert html_adjust(text, window_start=2, split_at=2) == 2

    # split_at beyond the end of the text -> early-return unchanged
    assert html_adjust(
        text, window_start=0, split_at=len(text) + 5) == len(text) + 5

    # No '&' in window, nothing to adjust
    assert html_adjust(text, window_start=0, split_at=3) == 3


def test_html_adjust_inside_and_at_boundary_of_entity() -> None:
    """
    Exercise the path where html_adjust moves the split back to '&' when the
    split falls inside an entity, and the path where the split is exactly at
    the entity boundary and should not move.
    """
    text = "1234&nbsp;5678"
    # indexes: 0..3 '1234', 4 '&', 5 'n', 6 'b', 7 's', 8 'p', 9 ';', 10 '5'...

    # Split inside '&nbsp;' (at index 8) -> move back to '&' (index 4)
    assert html_adjust(text, window_start=0, split_at=8) == 4

    # Split exactly after the ';' (index 10) -> already outside entity
    assert html_adjust(text, window_start=0, split_at=10) == 10


def test_markdown_adjust_guard_and_no_construct() -> None:
    """
    Cover the guard in markdown_adjust and the case where there is no
    '[' or '!' in the window.
    """
    text = "plain text"

    # split_at <= window_start -> early-return unchanged
    assert markdown_adjust(text, window_start=4, split_at=4) == 4

    # split_at past the end -> early-return unchanged
    assert markdown_adjust(
        text, window_start=0, split_at=len(text) + 3) == len(text) + 3

    # No markdown constructs -> nothing to adjust
    assert markdown_adjust(text, window_start=0, split_at=5) == 5


def test_markdown_adjust_inside_construct_moves_to_start() -> None:
    """
    Exercise the positive path in markdown_adjust where the split lands
    inside a [text](url) construct and the function moves the split
    back to the start of the construct.
    """
    link = "[link](https://example.com)"
    # Choose a split point inside the URL
    split_at = link.index("(") + 3  # somewhere inside "(https..."
    adjusted = markdown_adjust(link, window_start=0, split_at=split_at)

    # Should move back to the '[' at index 0
    assert adjusted == 0


def test_smart_split_markdown_guard_split_at_start_is_reset() -> None:
    """
    Cover the smart_split guard 'if split_at <= start: split_at = orig_split'.

    We force markdown_adjust to move the split back to the window start,
    then verify smart_split resets to the original split so progress is
    still made and chunks join back to the original text.
    """
    text = "[link](https://example.com)"
    limit = 5  # will cause the first soft split to land inside the link

    chunks = smart_split(text, limit, body_format=NotifyFormat.MARKDOWN)

    # We should never get stuck; all chunks must be non-empty
    assert len(chunks) >= 2
    assert all(chunks)

    # Re-joining all chunks must restore the original text
    assert "".join(chunks) == text


def test_smart_split_uses_punctuation_branch_on_rare_whitespace() -> None:
    """
    When punctuation is followed by rare whitespace (vertical tab / form feed)
    and there are no spaces/tabs/newlines, we should use the punctuation
    + whitespace split branch.
    """
    vt = "\x0b"  # vertical tab
    text = f"Hello.{vt}World"
    # Window includes 'Hello.' and the VT
    limit = len("Hello.") + 1

    chunks = smart_split(text, limit, body_format=NotifyFormat.TEXT)

    assert "".join(chunks) == text
    # We expect the first chunk to end after the rare whitespace
    assert chunks[0] == f"Hello.{vt}"
    assert chunks[1] == "World"
