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
    #
    # Face Smiling
    #
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

    #
    # Face Affection
    #
    EMOJI_WRAPPER + r'smiling_face_with_three_hearts' + EMOJI_WRAPPER: '🥰',
    EMOJI_WRAPPER + r'star_struck' + EMOJI_WRAPPER: '🤩',
    EMOJI_WRAPPER + r'kissing' + EMOJI_WRAPPER: '😗',
    EMOJI_WRAPPER + r'kissing_closed_eyes' + EMOJI_WRAPPER: '😚',
    EMOJI_WRAPPER + r'smiling_face_with_tear' + EMOJI_WRAPPER: '🥲',
    EMOJI_WRAPPER + r'heart_eyes' + EMOJI_WRAPPER: '😍',
    EMOJI_WRAPPER + r'kissing_heart' + EMOJI_WRAPPER: '😘',
    EMOJI_WRAPPER + r'relaxed' + EMOJI_WRAPPER: '☺️',
    EMOJI_WRAPPER + r'kissing_smiling_eyes' + EMOJI_WRAPPER: '😙',

    #
    # Face Tongue
    #
    EMOJI_WRAPPER + r'yum' + EMOJI_WRAPPER: '😋',
    EMOJI_WRAPPER + r'stuck_out_tongue_winking_eye' + EMOJI_WRAPPER: '😜',
    EMOJI_WRAPPER + r'stuck_out_tongue_closed_eyes' + EMOJI_WRAPPER: '😝',
    EMOJI_WRAPPER + r'stuck_out_tongue' + EMOJI_WRAPPER: '😛',
    EMOJI_WRAPPER + r'zany_face' + EMOJI_WRAPPER: '🤪',
    EMOJI_WRAPPER + r'money_mouth_face' + EMOJI_WRAPPER: '🤑',

    #
    # Face Hand
    #
    EMOJI_WRAPPER + r'hugs' + EMOJI_WRAPPER: '🤗',
    EMOJI_WRAPPER + r'shushing_face' + EMOJI_WRAPPER: '🤫',
    EMOJI_WRAPPER + r'hand_over_mouth' + EMOJI_WRAPPER: '🤭',
    EMOJI_WRAPPER + r'thinking' + EMOJI_WRAPPER: '🤔',

    #
    # Face Neutral Skeptical
    #
    EMOJI_WRAPPER + r'zipper_mouth_face' + EMOJI_WRAPPER: '🤐',
    EMOJI_WRAPPER + r'neutral_face' + EMOJI_WRAPPER: '😐',
    EMOJI_WRAPPER + r'no_mouth' + EMOJI_WRAPPER: '😶',
    EMOJI_WRAPPER + r'smirk' + EMOJI_WRAPPER: '😏',
    EMOJI_WRAPPER + r'roll_eyes' + EMOJI_WRAPPER: '🙄',
    # face_exhaling is comprised of 3 unicode characters:
    # 	1. U+1F62E FACE WITH OPEN MOUTH
    #   2. U+200D ZERO WIDTH JOINER
    #   3. U+1F4A8 DASH SYMBOL
    EMOJI_WRAPPER + r'face_exhaling' + EMOJI_WRAPPER: '😮‍💨',
    EMOJI_WRAPPER + r'raised_eyebrow' + EMOJI_WRAPPER: '🤨',
    EMOJI_WRAPPER + r'expressionless' + EMOJI_WRAPPER: '😑',
    # face_in_clouds is comprised of 4 unicode characters:
    # 	1. U+1F636 FACE WITHOUT MOUTH
    #   2. U+200D ZERO WIDTH JOINER
    #   3. U+1F32B FOG
    #   4. U+FE0F VARIATION SELECTOR-16
    EMOJI_WRAPPER + r'face_in_clouds' + EMOJI_WRAPPER: '😶‍🌫️',
    EMOJI_WRAPPER + r'unamused' + EMOJI_WRAPPER: '😒',
    EMOJI_WRAPPER + r'grimacing' + EMOJI_WRAPPER: '😬',
    EMOJI_WRAPPER + r'lying_face' + EMOJI_WRAPPER: '🤥',

    #
    # Face Sleepy
    #
    EMOJI_WRAPPER + r'relieved' + EMOJI_WRAPPER: '😌',
    EMOJI_WRAPPER + r'sleepy' + EMOJI_WRAPPER: '😪',
    EMOJI_WRAPPER + r'sleeping' + EMOJI_WRAPPER: '😴',
    EMOJI_WRAPPER + r'pensive' + EMOJI_WRAPPER: '😔',
    EMOJI_WRAPPER + r'drooling_face' + EMOJI_WRAPPER: '🤤',

    #
    # Face Unwell
    #
    EMOJI_WRAPPER + r'mask' + EMOJI_WRAPPER: '😷',
    EMOJI_WRAPPER + r'face_with_head_bandage' + EMOJI_WRAPPER: '🤕',
    EMOJI_WRAPPER + r'vomiting_face' + EMOJI_WRAPPER: '🤮',
    EMOJI_WRAPPER + r'hot_face' + EMOJI_WRAPPER: '🥵',
    EMOJI_WRAPPER + r'woozy_face' + EMOJI_WRAPPER: '🥴',
    # face_with_spiral_eyes is comprised of 3 unicode characters:
    # 	1. U+1F635 DIZZY FACE
    #   2. U+200D ZERO WIDTH JOINER
    #   3. U+1F4AB DIZZY SYMBOL
    EMOJI_WRAPPER + r'face_with_spiral_eyes' + EMOJI_WRAPPER: '😵‍💫',
    EMOJI_WRAPPER + r'face_with_thermometer' + EMOJI_WRAPPER: '🤒',
    EMOJI_WRAPPER + r'nauseated_face' + EMOJI_WRAPPER: '🤢',
    EMOJI_WRAPPER + r'sneezing_face' + EMOJI_WRAPPER: '🤧',
    EMOJI_WRAPPER + r'cold_face' + EMOJI_WRAPPER: '🥶',
    EMOJI_WRAPPER + r'dizzy_face' + EMOJI_WRAPPER: '😵',
    EMOJI_WRAPPER + r'exploding_head' + EMOJI_WRAPPER: '🤯',

    #
    # Face Hat
    #
    EMOJI_WRAPPER + r'cowboy_hat_face' + EMOJI_WRAPPER: '🤠',
    EMOJI_WRAPPER + r'disguised_face' + EMOJI_WRAPPER: '🥸',
    EMOJI_WRAPPER + r'partying_face' + EMOJI_WRAPPER: '🥳',

    #
    # Face Glasses
    #
    EMOJI_WRAPPER + r'sunglasses' + EMOJI_WRAPPER: '😎',
    EMOJI_WRAPPER + r'monocle_face' + EMOJI_WRAPPER: '🧐',
    EMOJI_WRAPPER + r'nerd_face' + EMOJI_WRAPPER: '🤓',

    #
    # Face Concerned
    #
    EMOJI_WRAPPER + r'confused' + EMOJI_WRAPPER: '😕',
    EMOJI_WRAPPER + r'slightly_frowning_face' + EMOJI_WRAPPER: '🙁',
    EMOJI_WRAPPER + r'open_mouth' + EMOJI_WRAPPER: '😮',
    EMOJI_WRAPPER + r'astonished' + EMOJI_WRAPPER: '😲',
    EMOJI_WRAPPER + r'pleading_face' + EMOJI_WRAPPER: '🥺',
    EMOJI_WRAPPER + r'anguished' + EMOJI_WRAPPER: '😧',
    EMOJI_WRAPPER + r'cold_sweat' + EMOJI_WRAPPER: '😰',
    EMOJI_WRAPPER + r'cry' + EMOJI_WRAPPER: '😢',
    EMOJI_WRAPPER + r'scream' + EMOJI_WRAPPER: '😱',
    EMOJI_WRAPPER + r'persevere' + EMOJI_WRAPPER: '😣',
    EMOJI_WRAPPER + r'sweat' + EMOJI_WRAPPER: '😓',
    EMOJI_WRAPPER + r'tired_face' + EMOJI_WRAPPER: '😫',
    EMOJI_WRAPPER + r'worried' + EMOJI_WRAPPER: '😟',
    EMOJI_WRAPPER + r'frowning_face' + EMOJI_WRAPPER: '☹️',
    EMOJI_WRAPPER + r'hushed' + EMOJI_WRAPPER: '😯',
    EMOJI_WRAPPER + r'flushed' + EMOJI_WRAPPER: '😳',
    EMOJI_WRAPPER + r'frowning' + EMOJI_WRAPPER: '😦',
    EMOJI_WRAPPER + r'fearful' + EMOJI_WRAPPER: '😨',
    EMOJI_WRAPPER + r'disappointed_relieved' + EMOJI_WRAPPER: '😥',
    EMOJI_WRAPPER + r'sob' + EMOJI_WRAPPER: '😭',
    EMOJI_WRAPPER + r'confounded' + EMOJI_WRAPPER: '😖',
    EMOJI_WRAPPER + r'disappointed' + EMOJI_WRAPPER: '😞',
    EMOJI_WRAPPER + r'weary' + EMOJI_WRAPPER: '😩',
    EMOJI_WRAPPER + r'yawning_face' + EMOJI_WRAPPER: '🥱',

    #
    # Face Negative
    #
    EMOJI_WRAPPER + r'triumph' + EMOJI_WRAPPER: '😤',
    EMOJI_WRAPPER + r'angry' + EMOJI_WRAPPER: '😠',
    EMOJI_WRAPPER + r'smiling_imp' + EMOJI_WRAPPER: '😈',
    EMOJI_WRAPPER + r'skull' + EMOJI_WRAPPER: '💀',
    EMOJI_WRAPPER + r'(pout|rage)' + EMOJI_WRAPPER: '😡',
    EMOJI_WRAPPER + r'cursing_face' + EMOJI_WRAPPER: '🤬',
    EMOJI_WRAPPER + r'imp' + EMOJI_WRAPPER: '👿',
    EMOJI_WRAPPER + r'skull_and_crossbones' + EMOJI_WRAPPER: '☠️',

    #
    # Face Costume
    #
    EMOJI_WRAPPER + r'(hankey|poop|shit)' + EMOJI_WRAPPER: '💩',
    EMOJI_WRAPPER + r'japanese_ogre' + EMOJI_WRAPPER: '👹',
    EMOJI_WRAPPER + r'ghost' + EMOJI_WRAPPER: '👻',
    EMOJI_WRAPPER + r'space_invader' + EMOJI_WRAPPER: '👾',
    EMOJI_WRAPPER + r'clown_face' + EMOJI_WRAPPER: '🤡',
    EMOJI_WRAPPER + r'japanese_goblin' + EMOJI_WRAPPER: '👺',
    EMOJI_WRAPPER + r'alien' + EMOJI_WRAPPER: '👽',
    EMOJI_WRAPPER + r'robot' + EMOJI_WRAPPER: '🤖',

    #
    # Cat Face
    #
    EMOJI_WRAPPER + r'smiley_cat' + EMOJI_WRAPPER: '😺',
    EMOJI_WRAPPER + r'joy_cat' + EMOJI_WRAPPER: '😹',
    EMOJI_WRAPPER + r'smirk_cat' + EMOJI_WRAPPER: '😼',
    EMOJI_WRAPPER + r'scream_cat' + EMOJI_WRAPPER: '🙀',
    EMOJI_WRAPPER + r'pouting_cat' + EMOJI_WRAPPER: '😾',
    EMOJI_WRAPPER + r'smile_cat' + EMOJI_WRAPPER: '😸',
    EMOJI_WRAPPER + r'heart_eyes_cat' + EMOJI_WRAPPER: '😻',
    EMOJI_WRAPPER + r'kissing_cat' + EMOJI_WRAPPER: '😽',
    EMOJI_WRAPPER + r'crying_cat_face' + EMOJI_WRAPPER: '😿',

    #
    # Monkey Face
    #
    EMOJI_WRAPPER + r'see_no_evil' + EMOJI_WRAPPER: '🙈',
    EMOJI_WRAPPER + r'speak_no_evil' + EMOJI_WRAPPER: '🙊',
    EMOJI_WRAPPER + r'hear_no_evil' + EMOJI_WRAPPER: '🙉',

    #
    # Heart
    #
    EMOJI_WRAPPER + r'love_letter' + EMOJI_WRAPPER: '💌',
    EMOJI_WRAPPER + r'gift_heart' + EMOJI_WRAPPER: '💝',
    EMOJI_WRAPPER + r'heartpulse' + EMOJI_WRAPPER: '💗',
    EMOJI_WRAPPER + r'revolving_hearts' + EMOJI_WRAPPER: '💞',
    EMOJI_WRAPPER + r'heart_decoration' + EMOJI_WRAPPER: '💟',
    EMOJI_WRAPPER + r'broken_heart' + EMOJI_WRAPPER: '💔',
    # mending_heart is comprised of 4 unicode characters:
    #   1. U+2764 HEAVY BLACK HEART
    #   2. U+FE0F VARIATION SELECTOR-16
    #   3. U+200D ZERO WIDTH JOINER
    #   4. U+1FA79 ADHESIVE BANDAGE
    EMOJI_WRAPPER + r'mending_heart' + EMOJI_WRAPPER: '❤️‍🩹',
    EMOJI_WRAPPER + r'orange_heart' + EMOJI_WRAPPER: '🧡',
    EMOJI_WRAPPER + r'green_heart' + EMOJI_WRAPPER: '💚',
    EMOJI_WRAPPER + r'purple_heart' + EMOJI_WRAPPER: '💜',
    EMOJI_WRAPPER + r'black_heart' + EMOJI_WRAPPER: '🖤',
    EMOJI_WRAPPER + r'cupid' + EMOJI_WRAPPER: '💘',
    EMOJI_WRAPPER + r'sparkling_heart' + EMOJI_WRAPPER: '💖',
    EMOJI_WRAPPER + r'heartbeat' + EMOJI_WRAPPER: '💓',
    EMOJI_WRAPPER + r'two_hearts' + EMOJI_WRAPPER: '💕',
    EMOJI_WRAPPER + r'heavy_heart_exclamation' + EMOJI_WRAPPER: '❣️',
    # mending_heart is comprised of 4 unicode characters:
    #   1. U+2764 HEAVY BLACK HEART
    #   2. U+FE0F VARIATION SELECTOR-16
    #   3. U+200D ZERO WIDTH JOINER
    #   4. U+1F525 FIRE
    EMOJI_WRAPPER + r'heart_on_fire' + EMOJI_WRAPPER: '❤️‍🔥',
    EMOJI_WRAPPER + r'heart' + EMOJI_WRAPPER: '❤️',
    EMOJI_WRAPPER + r'yellow_heart' + EMOJI_WRAPPER: '💛',
    EMOJI_WRAPPER + r'blue_heart' + EMOJI_WRAPPER: '💙',
    EMOJI_WRAPPER + r'brown_heart' + EMOJI_WRAPPER: '🤎',
    EMOJI_WRAPPER + r'white_heart' + EMOJI_WRAPPER: '🤍',

    #
    # Emotion
    #
    EMOJI_WRAPPER + r'kiss' + EMOJI_WRAPPER: '💋',
    EMOJI_WRAPPER + r'anger' + EMOJI_WRAPPER: '💢',
    EMOJI_WRAPPER + r'dizzy' + EMOJI_WRAPPER: '💫',
    EMOJI_WRAPPER + r'dash' + EMOJI_WRAPPER: '💨',
    EMOJI_WRAPPER + r'speech_balloon' + EMOJI_WRAPPER: '💬',
    EMOJI_WRAPPER + r'left_speech_bubble' + EMOJI_WRAPPER: '🗨️',
    EMOJI_WRAPPER + r'thought_balloon' + EMOJI_WRAPPER: '💭',
    EMOJI_WRAPPER + r'100' + EMOJI_WRAPPER: '💯',
    EMOJI_WRAPPER + r'(boom|collision)' + EMOJI_WRAPPER: '💥',
    EMOJI_WRAPPER + r'sweat_drops' + EMOJI_WRAPPER: '💦',
    EMOJI_WRAPPER + r'hole' + EMOJI_WRAPPER: '🕳️',
    # eye_speech_bubble is comprised of 5 unicode characters:
    #   1. U+1F441 EYE
    #   2. U+FE0F VARIATION SELECTOR-16
    #   3. U+200D ZERO WIDTH JOINER
    #   4. U+1F5E8 LEFT SPEECH BUBBLE
    #   5. U+FE0F VARIATION SELECTOR-16
    EMOJI_WRAPPER + r'eye_speech_bubble' + EMOJI_WRAPPER: '👁️‍🗨️',
    EMOJI_WRAPPER + r'right_anger_bubble' + EMOJI_WRAPPER: '🗯️',
    EMOJI_WRAPPER + r'zzz' + EMOJI_WRAPPER: '💤',

    #
    # Hand Fingers Open
    #
    EMOJI_WRAPPER + r'wave' + EMOJI_WRAPPER: '👋',
    EMOJI_WRAPPER + r'raised_hand_with_fingers_splayed' + EMOJI_WRAPPER: '🖐️',
    EMOJI_WRAPPER + r'vulcan_salute' + EMOJI_WRAPPER: '🖖',
    EMOJI_WRAPPER + r'raised_back_of_hand' + EMOJI_WRAPPER: '🤚',
    EMOJI_WRAPPER + r'(raised_)?hand' + EMOJI_WRAPPER: '✋',
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
