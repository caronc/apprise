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

# Disable logging for a cleaner testing output
import logging
import sys

from apprise import emojis

logging.disable(logging.CRITICAL)

# Ensure we don't create .pyc files for these tests
sys.dont_write_bytecode = True


def test_emojis():
    "emojis: apply_emojis() testing"

    assert emojis.apply_emojis("") == ""
    assert emojis.apply_emojis("no change") == "no change"
    assert emojis.apply_emojis(":smile:") == "😄"
    assert emojis.apply_emojis(":smile::smile:") == "😄😄"

    # Missing Delimiters
    assert emojis.apply_emojis(":smile") == ":smile"
    assert emojis.apply_emojis("smile:") == "smile:"

    # Bad data
    assert emojis.apply_emojis(None) == ""
    assert emojis.apply_emojis(object) == ""
    assert emojis.apply_emojis(True) == ""
    assert emojis.apply_emojis(4.0) == ""


def test_emojis_alternation_aliases():
    """emojis: apply_emojis() handles regex alternation keys correctly."""

    # thumbsup / +1
    assert emojis.apply_emojis(":thumbsup:") == "👍"
    assert emojis.apply_emojis(":+1:") == "👍"

    # thumbsdown / -1
    assert emojis.apply_emojis(":thumbsdown:") == "👎"
    assert emojis.apply_emojis(":-1:") == "👎"

    # laughing / satisfied
    assert emojis.apply_emojis(":laughing:") == "😆"
    assert emojis.apply_emojis(":satisfied:") == "😆"

    # poop aliases
    assert emojis.apply_emojis(":poop:") == "💩"
    assert emojis.apply_emojis(":hankey:") == "💩"
    assert emojis.apply_emojis(":shit:") == "💩"

    # boom / collision
    assert emojis.apply_emojis(":boom:") == "💥"
    assert emojis.apply_emojis(":collision:") == "💥"

    # exclamation aliases
    assert emojis.apply_emojis(":exclamation:") == "❗"
    assert emojis.apply_emojis(":heavy_exclamation_mark:") == "❗"

    # knife / hocho
    assert emojis.apply_emojis(":knife:") == "🔪"
    assert emojis.apply_emojis(":hocho:") == "🔪"

    # memo / pencil
    assert emojis.apply_emojis(":memo:") == "📝"
    assert emojis.apply_emojis(":pencil:") == "📝"

    # uk / gb
    assert emojis.apply_emojis(":uk:") == "🇬🇧"
    assert emojis.apply_emojis(":gb:") == "🇬🇧"

    # aliases embedded in text
    assert emojis.apply_emojis("hello :thumbsup: world") == "hello 👍 world"
    assert emojis.apply_emojis(":poop::boom:") == "💩💥"

    # optional-group patterns: ':hand:' and ':raised_hand:' both map to ✋
    assert emojis.apply_emojis(":hand:") == "✋"
    assert emojis.apply_emojis(":raised_hand:") == "✋"

    # runner / running
    assert emojis.apply_emojis(":runner:") == "🏃"
    assert emojis.apply_emojis(":running:") == "🏃"


def test_emojis_lookup_no_pattern_match():
    """emojis: _lookup() returns the raw token when _EMOJI_PATTERN_LIST is
    empty (defensive fallback -- return text branch)."""

    # Ensure the engine is initialised first.
    emojis.apply_emojis(":smile:")

    original = emojis._EMOJI_PATTERN_LIST
    emojis._EMOJI_PATTERN_LIST = []
    try:
        # With no patterns to match against, _lookup falls through to
        # "return text", so the matched token is passed back unchanged.
        result = emojis.apply_emojis(":smile:")
        assert result == ":smile:"
    finally:
        emojis._EMOJI_PATTERN_LIST = original
