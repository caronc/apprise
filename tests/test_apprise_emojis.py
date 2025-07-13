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
