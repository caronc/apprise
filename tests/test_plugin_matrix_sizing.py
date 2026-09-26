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

import random

from apprise.asset import AppriseAsset
from apprise.common import NotifyFormat
from apprise.plugins.matrix import NotifyMatrix, sizing


def test_plugin_matrix_utf8_char_len():
    """Calculate UTF-8 widths without encoding each character."""
    assert sizing.utf8_char_len("a") == 1
    assert sizing.utf8_char_len("é") == 2
    assert sizing.utf8_char_len("中") == 3
    assert sizing.utf8_char_len("\U0001f600") == 4


def test_plugin_matrix_json_char_bytes():
    """Include JSON escaping in each character's byte cost."""
    assert sizing.json_char_bytes("a") == 1
    assert sizing.json_char_bytes('"') == 2
    assert sizing.json_char_bytes("\\") == 2

    # Short control escapes use two bytes.
    for ch in ("\b", "\f", "\n", "\r", "\t"):
        assert sizing.json_char_bytes(ch) == 2

    # Other control characters use the six-byte Unicode form.
    assert sizing.json_char_bytes("\x00") == 6
    assert sizing.json_char_bytes("\x1f") == 6
    assert sizing.json_char_bytes("é") == 2
    assert sizing.json_char_bytes("中") == 3
    assert sizing.json_char_bytes("\U0001f600") == 4


def test_plugin_matrix_max_byte_budget():
    """Find the largest input accepted by the event cost model."""
    assert sizing.max_byte_budget(lambda value: value + 10, 110, 1000) == 100
    assert sizing.max_byte_budget(lambda value: value + 1000, 10, 1000) == 0


def test_plugin_matrix_sanitize_text():
    """Replace lone surrogates while preserving regular text."""
    assert sizing.sanitize_text(None) is None
    assert sizing.sanitize_text("") == ""
    assert sizing.sanitize_text("hello") == "hello"

    sanitized = sizing.sanitize_text("a" + chr(0xD800) + "b")
    assert sanitized == "a?b"
    sanitized.encode("utf-8")


def test_plugin_matrix_trim_bounds():
    """Find normal strip boundaries without copying the input."""
    assert sizing.rstrip_end("hello") == len("hello")
    assert sizing.rstrip_end("hello   ") == len("hello")
    assert sizing.rstrip_end("   ") == 0
    assert sizing.rstrip_end("") == 0

    assert sizing.strip_bounds("hello") == (0, len("hello"))
    text = "   hello   "
    start, end = sizing.strip_bounds(text)
    assert text[start:end] == "hello"

    start, end = sizing.strip_bounds("   ")
    assert start == end
    assert sizing.strip_bounds("") == (0, 0)


def test_plugin_matrix_payload_budget():
    """Match every branch of the asset's payload-cap allocation."""
    assert sizing.payload_budget(AppriseAsset(), 500, 500) == (500, 500)

    asset = AppriseAsset(payload_max_size=100)
    assert sizing.payload_budget(asset, 10, 10) == (10, 10)
    assert sizing.payload_budget(asset, 0, 5000) == (0, 100)
    assert sizing.payload_budget(asset, 5000, 0) == (100, 0)
    assert sizing.payload_budget(asset, 5, 5000) == (5, 95)
    assert sizing.payload_budget(asset, 5000, 5) == (95, 5)
    assert sizing.payload_budget(asset, 5000, 5000) == (50, 50)

    # A local generator avoids changing randomness for unrelated tests.
    generator = random.Random(2026)
    for _ in range(500):
        cap = generator.choice([0, 1, 5, 25, 50, 100, 300])
        threshold = generator.choice([1, 5, 10, 20])
        min_buffer = generator.choice([1, 5, 25, 50])
        title_len = generator.choice([0, 1, 5, 10, 50, 100, 500])
        body_len = generator.choice([0, 1, 5, 10, 50, 100, 500, 5000])

        asset = AppriseAsset(
            payload_max_size=cap,
            payload_buffer_threshold=threshold,
            payload_min_buffer=min_buffer,
        )
        real_title, real_body = asset.enforce_payload_max_size(
            "T" * title_len, "B" * body_len
        )
        assert sizing.payload_budget(asset, title_len, body_len) == (
            len(real_title),
            len(real_body),
        )


def test_plugin_matrix_title_overhead_bytes():
    """Measure title wrappers exactly as Matrix embeds them."""

    def json_bytes(value):
        return sum(sizing.json_char_bytes(ch) for ch in value)

    escape_html = NotifyMatrix.escape_html
    assert sizing.title_overhead_bytes("", NotifyFormat.TEXT, escape_html) == 0

    plain = sizing.title_overhead_bytes("hi", NotifyFormat.TEXT, escape_html)
    assert plain == json_bytes("# hi\r\n")

    html = sizing.title_overhead_bytes("hi", NotifyFormat.HTML, escape_html)
    assert html == json_bytes("# hi\r\n") + json_bytes("<h1>hi</h1>")

    markdown = sizing.title_overhead_bytes(
        "<b>", NotifyFormat.MARKDOWN, escape_html
    )
    escaped = escape_html("<b>", whitespace=False)
    assert markdown == json_bytes("# <b>\r\n") + json_bytes(
        f"<h1>{escaped}</h1>"
    )

    heavy = sizing.title_overhead_bytes(
        "\x01" * 10, NotifyFormat.TEXT, escape_html
    )
    assert heavy == json_bytes("# \r\n") + 10 * 6


def test_plugin_matrix_device_id_overhead_bytes():
    """Measure known device IDs and use a fallback for unknown IDs."""
    assert (
        sizing.device_id_overhead_bytes(None)
        == sizing.MATRIX_DEVICE_ID_FALLBACK_BYTES
    )
    assert sizing.device_id_overhead_bytes("ABCDEFGHIJ") == 10
    assert sizing.device_id_overhead_bytes("D" * 500) == 500


def test_plugin_matrix_title_sizing_stays_separate():
    """Keep Matrix title sizing independent from body chunk lengths."""
    assert NotifyMatrix.title_maxlen == 250
    assert NotifyMatrix.overflow_amalgamate_title is False


def test_plugin_matrix_fit_limit_performance(monkeypatch):
    """Keep the sizing scan linear for large messages."""

    def cost_fn(window_bytes):
        return window_bytes + 200

    length = 1_000_000
    body = "a" * length
    calls = {"count": 0}
    real_json_char_bytes = sizing.json_char_bytes

    def counting_json_char_bytes(ch):
        calls["count"] += 1
        return real_json_char_bytes(ch)

    monkeypatch.setattr(sizing, "json_char_bytes", counting_json_char_bytes)
    result = sizing.fit_char_limit(body, 61536, cost_fn)

    assert result > 0
    assert calls["count"] <= length * 3
