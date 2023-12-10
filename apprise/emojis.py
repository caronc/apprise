# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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

import re

# All Emoji's are wrapped in this character
EMOJI_WRAPPER = ':'

# the map simply contains the emoji that should be mapped to the regular
# expression it should be swapped on.
# This list was based on: https://github.com/ikatyang/emoji-cheat-sheet
EMOJI_MAP = {
    # Face Smiling
    EMOJI_WRAPPER + r'grinning' + EMOJI_WRAPPER: '😄',
    EMOJI_WRAPPER + r'smile' + EMOJI_WRAPPER: '😄',
    EMOJI_WRAPPER + r'(laughing|satisfied)' + EMOJI_WRAPPER: '😆',
    EMOJI_WRAPPER + r'rofl' + EMOJI_WRAPPER: '🤣',
    EMOJI_WRAPPER + r'slightly_smiling_face' + EMOJI_WRAPPER: '🙂',
    EMOJI_WRAPPER + r'wink' + EMOJI_WRAPPER: '😉',
    EMOJI_WRAPPER + r'innocent' + EMOJI_WRAPPER: '😇',
    EMOJI_WRAPPER + r'smiley' + EMOJI_WRAPPER: '😃',
    EMOJI_WRAPPER + r'grin' + EMOJI_WRAPPER: '😃',
    EMOJI_WRAPPER + r'sweat_smile' + EMOJI_WRAPPER: '😅',
    EMOJI_WRAPPER + r'joy' + EMOJI_WRAPPER: '😂',
    EMOJI_WRAPPER + r'upside_down_face' + EMOJI_WRAPPER: '🙃',
    EMOJI_WRAPPER + r'blush' + EMOJI_WRAPPER: '😊',

    # Face Affection
}

# Our compiled mapping
EMOJI_COMPILED_MAP = re.compile(
    r'(' + '|'.join(EMOJI_MAP.keys()) + r')',
    re.IGNORECASE)


def apply_emojis(content):
    """
    Takes the content and swaps any matched emoji's found with their
    utf-8 encoded mapping
    """

    try:
        return EMOJI_COMPILED_MAP.sub(lambda x: EMOJI_MAP[x.group()], content)

    except TypeError:
        # No change; but force string return
        return ''
