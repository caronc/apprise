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

"""Unit tests for :mod:`apprise.utils.sanitize`.
"""

from __future__ import annotations

from hashlib import sha256
import logging
import sys

from apprise.utils.sanitize import SanitizeOptions, sanitize_payload

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)
sys.dont_write_bytecode = True


class _ReprOnly:
    """Helper type that only supports repr(), used to cover fallback paths."""

    def __repr__(self) -> str:
        return "<repr-only>"


def test_sanitize_payload_passthrough_primitives() -> None:
    """Primitives should pass through with minimal transformation."""
    assert sanitize_payload(None) is None
    assert sanitize_payload(True) is True
    assert sanitize_payload(False) is False
    assert sanitize_payload(123) == 123
    assert sanitize_payload(3.14) == 3.14


def test_sanitize_payload_small_string_passthrough() -> None:
    """Small strings are not altered, preserving debugging usefulness."""
    s = "hello world"
    assert sanitize_payload(s) == s


def test_sanitize_payload_large_string_is_summarized() -> None:
    """Strings beyond max_str_len are summarized with head/tail previews."""
    opts = SanitizeOptions(max_str_len=64, preview=8)
    s = "x" * 200
    out = sanitize_payload(s, options=opts)

    assert isinstance(out, str)
    assert out.startswith("<string len=200")
    assert "head=" in out
    assert "tail=" in out


def test_sanitize_payload_bytes_are_summarized_and_hash_is_bounded() -> None:
    """Bytes are always summarized with a bounded sha256 digest."""
    opts = SanitizeOptions(hash_sample_size=8)
    b = b"01234567" + b"EXTRA-DATA"

    out = sanitize_payload(b, options=opts)
    assert isinstance(out, str)
    assert out.startswith(f"<bytes len={len(b)}")

    expected = sha256(b[: opts.hash_sample_size]).hexdigest()[:12]
    assert f"sha256={expected}" in out


def test_sanitize_payload_dict_keys_are_sanitised_for_bytes() -> None:
    """Bytes keys become readable string markers rather than raw bytes."""
    opts = SanitizeOptions(hash_sample_size=16)

    bkey = b"abc"
    payload = {
        bkey: "value1",
        "k": "v",
    }

    out = sanitize_payload(payload, options=opts)
    assert isinstance(out, dict)

    expected_b_digest = sha256(bkey[: opts.hash_sample_size]).hexdigest()[:12]
    bkey_s = f"<bytes len={len(bkey)} sha256={expected_b_digest}>"
    assert bkey_s in out
    assert out[bkey_s] == "value1"
    assert out["k"] == "v"


def test_sanitize_payload_sequence_types() -> None:
    """Lists, tuples, sets, and frozensets are walked safely."""
    payload = [1, "x" * 200, b"xyz"]
    opts = SanitizeOptions(max_str_len=64, preview=8)

    out = sanitize_payload(payload, options=opts)
    assert isinstance(out, list)
    assert out[0] == 1
    assert isinstance(out[1], str) and out[1].startswith("<string len=")
    assert isinstance(out[2], str) and out[2].startswith("<bytes len=3")

    out_t = sanitize_payload(tuple(payload), options=opts)
    assert isinstance(out_t, tuple)

    # Sets are returned as lists for readability in logs.
    out_s = sanitize_payload(set(payload), options=opts)
    assert isinstance(out_s, list)

    out_fs = sanitize_payload(frozenset(payload), options=opts)
    assert isinstance(out_fs, list)


def test_sanitize_payload_recursive_structure_is_detected() -> None:
    """Self-referential objects should not trigger infinite recursion."""
    payload: dict[str, object] = {}
    payload["self"] = payload

    out = sanitize_payload(payload)
    assert isinstance(out, dict)
    assert out["self"] == "<recursive>"


def test_sanitize_payload_max_depth_truncation() -> None:
    """Depth limits protect against overly deep nested structures."""
    opts = SanitizeOptions(max_depth=2)
    payload = {"a": {"b": {"c": "d"}}}

    out = sanitize_payload(payload, options=opts)
    assert isinstance(out, dict)
    assert isinstance(out["a"], dict)
    assert isinstance(out["a"]["b"], dict)
    assert out["a"]["b"]["c"] == "<truncated: max depth reached>"


def test_sanitize_payload_max_items_truncation_in_list_branch() -> None:
    """Item limits protect against very large sequences."""
    opts = SanitizeOptions(max_items=2)
    payload = [1, 2, 3, 4]

    out = sanitize_payload(payload, options=opts)
    assert isinstance(out, list)
    assert out[-1] == "<truncated: limit reached>"


def test_sanitize_payload_global_item_limit_guard_message() -> None:
    """The global max_items guard stops work consistently."""
    opts = SanitizeOptions(max_items=1)
    payload = {"a": "x", "b": "y"}

    out = sanitize_payload(payload, options=opts)
    assert isinstance(out, dict)
    assert any(
        v == "<truncated: global item limit reached>" or v == "..."
        for v in out.values()
    )


def test_sanitize_payload_falls_back_to_repr_for_unknown_objects() -> None:
    """Unknown objects are converted with repr() for logging."""
    assert sanitize_payload(_ReprOnly()) == "<repr-only>"


def test_sanitize_payload_blob_key_enables_blob_mode_and_summarizes() -> None:
    """Blob-like keys enable blob_mode and trigger <blob-string ...>."""
    opts = SanitizeOptions(
        aggressive_blob_keys=True,
        # ensure normal summarization would NOT trigger
        max_str_len=999999,
        preview=8,
    )

    payload = {
        # small string, but blob_mode forces summary
        "base64_attachments": "ABCDEF",
    }

    out = sanitize_payload(payload, options=opts)

    assert isinstance(out, dict)
    assert "base64_attachments" in out
    assert isinstance(out["base64_attachments"], str)
    assert out["base64_attachments"].startswith("<string len=6 blob ")
    assert "head=" in out["base64_attachments"]
    assert "tail=" in out["base64_attachments"]


def test_sanitize_payload_dict_key_passthrough_for_non_str_bytes_key() -> None:
    """
    Verify non-string, non-bytes dictionary keys are preserved unchanged.

    This exercises the fallback path in _summarize_key(), ensuring unexpected
    key types (such as integers) are passed through safely during sanitisation.
    """
    payload = {
        # int key triggers the "return k" branch
        42: "value",
        # keep a normal key too
        "k": "v",
    }

    out = sanitize_payload(payload)

    assert isinstance(out, dict)
    assert 42 in out
    assert out[42] == "value"
    assert out["k"] == "v"
