# -*- coding: utf-8 -*-
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

import re
import time
from .logger import logger

# All Emoji's are wrapped in this character
DELIM = ':'

# the map simply contains the emoji that should be mapped to the regular
# expression it should be swapped on.
# This list was based on: https://github.com/ikatyang/emoji-cheat-sheet
EMOJI_MAP = {
    #
    # Face Smiling
    #
    DELIM + r'grinning' + DELIM: '😄',
    DELIM + r'smile' + DELIM: '😄',
    DELIM + r'(laughing|satisfied)' + DELIM: '😆',
    DELIM + r'rofl' + DELIM: '🤣',
    DELIM + r'slightly_smiling_face' + DELIM: '🙂',
    DELIM + r'wink' + DELIM: '😉',
    DELIM + r'innocent' + DELIM: '😇',
    DELIM + r'smiley' + DELIM: '😃',
    DELIM + r'grin' + DELIM: '😃',
    DELIM + r'sweat_smile' + DELIM: '😅',
    DELIM + r'joy' + DELIM: '😂',
    DELIM + r'upside_down_face' + DELIM: '🙃',
    DELIM + r'blush' + DELIM: '😊',

    #
    # Face Affection
    #
    DELIM + r'smiling_face_with_three_hearts' + DELIM: '🥰',
    DELIM + r'star_struck' + DELIM: '🤩',
    DELIM + r'kissing' + DELIM: '😗',
    DELIM + r'kissing_closed_eyes' + DELIM: '😚',
    DELIM + r'smiling_face_with_tear' + DELIM: '🥲',
    DELIM + r'heart_eyes' + DELIM: '😍',
    DELIM + r'kissing_heart' + DELIM: '😘',
    DELIM + r'relaxed' + DELIM: '☺️',
    DELIM + r'kissing_smiling_eyes' + DELIM: '😙',

    #
    # Face Tongue
    #
    DELIM + r'yum' + DELIM: '😋',
    DELIM + r'stuck_out_tongue_winking_eye' + DELIM: '😜',
    DELIM + r'stuck_out_tongue_closed_eyes' + DELIM: '😝',
    DELIM + r'stuck_out_tongue' + DELIM: '😛',
    DELIM + r'zany_face' + DELIM: '🤪',
    DELIM + r'money_mouth_face' + DELIM: '🤑',

    #
    # Face Hand
    #
    DELIM + r'hugs' + DELIM: '🤗',
    DELIM + r'shushing_face' + DELIM: '🤫',
    DELIM + r'hand_over_mouth' + DELIM: '🤭',
    DELIM + r'thinking' + DELIM: '🤔',

    #
    # Face Neutral Skeptical
    #
    DELIM + r'zipper_mouth_face' + DELIM: '🤐',
    DELIM + r'neutral_face' + DELIM: '😐',
    DELIM + r'no_mouth' + DELIM: '😶',
    DELIM + r'smirk' + DELIM: '😏',
    DELIM + r'roll_eyes' + DELIM: '🙄',
    DELIM + r'face_exhaling' + DELIM: '😮‍💨',
    DELIM + r'raised_eyebrow' + DELIM: '🤨',
    DELIM + r'expressionless' + DELIM: '😑',
    DELIM + r'face_in_clouds' + DELIM: '😶‍🌫️',
    DELIM + r'unamused' + DELIM: '😒',
    DELIM + r'grimacing' + DELIM: '😬',
    DELIM + r'lying_face' + DELIM: '🤥',

    #
    # Face Sleepy
    #
    DELIM + r'relieved' + DELIM: '😌',
    DELIM + r'sleepy' + DELIM: '😪',
    DELIM + r'sleeping' + DELIM: '😴',
    DELIM + r'pensive' + DELIM: '😔',
    DELIM + r'drooling_face' + DELIM: '🤤',

    #
    # Face Unwell
    #
    DELIM + r'mask' + DELIM: '😷',
    DELIM + r'face_with_head_bandage' + DELIM: '🤕',
    DELIM + r'vomiting_face' + DELIM: '🤮',
    DELIM + r'hot_face' + DELIM: '🥵',
    DELIM + r'woozy_face' + DELIM: '🥴',
    DELIM + r'face_with_spiral_eyes' + DELIM: '😵‍💫',
    DELIM + r'face_with_thermometer' + DELIM: '🤒',
    DELIM + r'nauseated_face' + DELIM: '🤢',
    DELIM + r'sneezing_face' + DELIM: '🤧',
    DELIM + r'cold_face' + DELIM: '🥶',
    DELIM + r'dizzy_face' + DELIM: '😵',
    DELIM + r'exploding_head' + DELIM: '🤯',

    #
    # Face Hat
    #
    DELIM + r'cowboy_hat_face' + DELIM: '🤠',
    DELIM + r'disguised_face' + DELIM: '🥸',
    DELIM + r'partying_face' + DELIM: '🥳',

    #
    # Face Glasses
    #
    DELIM + r'sunglasses' + DELIM: '😎',
    DELIM + r'monocle_face' + DELIM: '🧐',
    DELIM + r'nerd_face' + DELIM: '🤓',

    #
    # Face Concerned
    #
    DELIM + r'confused' + DELIM: '😕',
    DELIM + r'slightly_frowning_face' + DELIM: '🙁',
    DELIM + r'open_mouth' + DELIM: '😮',
    DELIM + r'astonished' + DELIM: '😲',
    DELIM + r'pleading_face' + DELIM: '🥺',
    DELIM + r'anguished' + DELIM: '😧',
    DELIM + r'cold_sweat' + DELIM: '😰',
    DELIM + r'cry' + DELIM: '😢',
    DELIM + r'scream' + DELIM: '😱',
    DELIM + r'persevere' + DELIM: '😣',
    DELIM + r'sweat' + DELIM: '😓',
    DELIM + r'tired_face' + DELIM: '😫',
    DELIM + r'worried' + DELIM: '😟',
    DELIM + r'frowning_face' + DELIM: '☹️',
    DELIM + r'hushed' + DELIM: '😯',
    DELIM + r'flushed' + DELIM: '😳',
    DELIM + r'frowning' + DELIM: '😦',
    DELIM + r'fearful' + DELIM: '😨',
    DELIM + r'disappointed_relieved' + DELIM: '😥',
    DELIM + r'sob' + DELIM: '😭',
    DELIM + r'confounded' + DELIM: '😖',
    DELIM + r'disappointed' + DELIM: '😞',
    DELIM + r'weary' + DELIM: '😩',
    DELIM + r'yawning_face' + DELIM: '🥱',

    #
    # Face Negative
    #
    DELIM + r'triumph' + DELIM: '😤',
    DELIM + r'angry' + DELIM: '😠',
    DELIM + r'smiling_imp' + DELIM: '😈',
    DELIM + r'skull' + DELIM: '💀',
    DELIM + r'(pout|rage)' + DELIM: '😡',
    DELIM + r'cursing_face' + DELIM: '🤬',
    DELIM + r'imp' + DELIM: '👿',
    DELIM + r'skull_and_crossbones' + DELIM: '☠️',

    #
    # Face Costume
    #
    DELIM + r'(hankey|poop|shit)' + DELIM: '💩',
    DELIM + r'japanese_ogre' + DELIM: '👹',
    DELIM + r'ghost' + DELIM: '👻',
    DELIM + r'space_invader' + DELIM: '👾',
    DELIM + r'clown_face' + DELIM: '🤡',
    DELIM + r'japanese_goblin' + DELIM: '👺',
    DELIM + r'alien' + DELIM: '👽',
    DELIM + r'robot' + DELIM: '🤖',

    #
    # Cat Face
    #
    DELIM + r'smiley_cat' + DELIM: '😺',
    DELIM + r'joy_cat' + DELIM: '😹',
    DELIM + r'smirk_cat' + DELIM: '😼',
    DELIM + r'scream_cat' + DELIM: '🙀',
    DELIM + r'pouting_cat' + DELIM: '😾',
    DELIM + r'smile_cat' + DELIM: '😸',
    DELIM + r'heart_eyes_cat' + DELIM: '😻',
    DELIM + r'kissing_cat' + DELIM: '😽',
    DELIM + r'crying_cat_face' + DELIM: '😿',

    #
    # Monkey Face
    #
    DELIM + r'see_no_evil' + DELIM: '🙈',
    DELIM + r'speak_no_evil' + DELIM: '🙊',
    DELIM + r'hear_no_evil' + DELIM: '🙉',

    #
    # Heart
    #
    DELIM + r'love_letter' + DELIM: '💌',
    DELIM + r'gift_heart' + DELIM: '💝',
    DELIM + r'heartpulse' + DELIM: '💗',
    DELIM + r'revolving_hearts' + DELIM: '💞',
    DELIM + r'heart_decoration' + DELIM: '💟',
    DELIM + r'broken_heart' + DELIM: '💔',
    DELIM + r'mending_heart' + DELIM: '❤️‍🩹',
    DELIM + r'orange_heart' + DELIM: '🧡',
    DELIM + r'green_heart' + DELIM: '💚',
    DELIM + r'purple_heart' + DELIM: '💜',
    DELIM + r'black_heart' + DELIM: '🖤',
    DELIM + r'cupid' + DELIM: '💘',
    DELIM + r'sparkling_heart' + DELIM: '💖',
    DELIM + r'heartbeat' + DELIM: '💓',
    DELIM + r'two_hearts' + DELIM: '💕',
    DELIM + r'heavy_heart_exclamation' + DELIM: '❣️',
    DELIM + r'heart_on_fire' + DELIM: '❤️‍🔥',
    DELIM + r'heart' + DELIM: '❤️',
    DELIM + r'yellow_heart' + DELIM: '💛',
    DELIM + r'blue_heart' + DELIM: '💙',
    DELIM + r'brown_heart' + DELIM: '🤎',
    DELIM + r'white_heart' + DELIM: '🤍',

    #
    # Emotion
    #
    DELIM + r'kiss' + DELIM: '💋',
    DELIM + r'anger' + DELIM: '💢',
    DELIM + r'dizzy' + DELIM: '💫',
    DELIM + r'dash' + DELIM: '💨',
    DELIM + r'speech_balloon' + DELIM: '💬',
    DELIM + r'left_speech_bubble' + DELIM: '🗨️',
    DELIM + r'thought_balloon' + DELIM: '💭',
    DELIM + r'100' + DELIM: '💯',
    DELIM + r'(boom|collision)' + DELIM: '💥',
    DELIM + r'sweat_drops' + DELIM: '💦',
    DELIM + r'hole' + DELIM: '🕳️',
    DELIM + r'eye_speech_bubble' + DELIM: '👁️‍🗨️',
    DELIM + r'right_anger_bubble' + DELIM: '🗯️',
    DELIM + r'zzz' + DELIM: '💤',

    #
    # Hand Fingers Open
    #
    DELIM + r'wave' + DELIM: '👋',
    DELIM + r'raised_hand_with_fingers_splayed' + DELIM: '🖐️',
    DELIM + r'vulcan_salute' + DELIM: '🖖',
    DELIM + r'raised_back_of_hand' + DELIM: '🤚',
    DELIM + r'(raised_)?hand' + DELIM: '✋',

    #
    # Hand Fingers Partial
    #
    DELIM + r'ok_hand' + DELIM: '👌',
    DELIM + r'pinched_fingers' + DELIM: '🤌',
    DELIM + r'pinching_hand' + DELIM: '🤏',
    DELIM + r'v' + DELIM: '✌️',
    DELIM + r'crossed_fingers' + DELIM: '🤞',
    DELIM + r'love_you_gesture' + DELIM: '🤟',
    DELIM + r'metal' + DELIM: '🤘',
    DELIM + r'call_me_hand' + DELIM: '🤙',

    #
    # Hand Single Finger
    #
    DELIM + r'point_left' + DELIM: '👈',
    DELIM + r'point_right' + DELIM: '👉',
    DELIM + r'point_up_2' + DELIM: '👆',
    DELIM + r'(fu|middle_finger)' + DELIM: '🖕',
    DELIM + r'point_down' + DELIM: '👇',
    DELIM + r'point_up' + DELIM: '☝️',

    #
    # Hand Fingers Closed
    #
    DELIM + r'(\+1|thumbsup)' + DELIM: '👍',
    DELIM + r'(-1|thumbsdown)' + DELIM: '👎',
    DELIM + r'fist' + DELIM: '✊',
    DELIM + r'(fist_(raised|oncoming)|(face)?punch)' + DELIM: '👊',
    DELIM + r'fist_left' + DELIM: '🤛',
    DELIM + r'fist_right' + DELIM: '🤜',

    #
    # Hands
    #
    DELIM + r'clap' + DELIM: '👏',
    DELIM + r'raised_hands' + DELIM: '🙌',
    DELIM + r'open_hands' + DELIM: '👐',
    DELIM + r'palms_up_together' + DELIM: '🤲',
    DELIM + r'handshake' + DELIM: '🤝',
    DELIM + r'pray' + DELIM: '🙏',

    #
    # Hand Prop
    #
    DELIM + r'writing_hand' + DELIM: '✍️',
    DELIM + r'nail_care' + DELIM: '💅',
    DELIM + r'selfie' + DELIM: '🤳',

    #
    # Body Parts
    #
    DELIM + r'muscle' + DELIM: '💪',
    DELIM + r'mechanical_arm' + DELIM: '🦾',
    DELIM + r'mechanical_leg' + DELIM: '🦿',
    DELIM + r'leg' + DELIM: '🦵',
    DELIM + r'foot' + DELIM: '🦶',
    DELIM + r'ear' + DELIM: '👂',
    DELIM + r'ear_with_hearing_aid' + DELIM: '🦻',
    DELIM + r'nose' + DELIM: '👃',
    DELIM + r'brain' + DELIM: '🧠',
    DELIM + r'anatomical_heart' + DELIM: '🫀',
    DELIM + r'lungs' + DELIM: '🫁',
    DELIM + r'tooth' + DELIM: '🦷',
    DELIM + r'bone' + DELIM: '🦴',
    DELIM + r'eyes' + DELIM: '👀',
    DELIM + r'eye' + DELIM: '👁️',
    DELIM + r'tongue' + DELIM: '👅',
    DELIM + r'lips' + DELIM: '👄',

    #
    # Person
    #
    DELIM + r'baby' + DELIM: '👶',
    DELIM + r'child' + DELIM: '🧒',
    DELIM + r'boy' + DELIM: '👦',
    DELIM + r'girl' + DELIM: '👧',
    DELIM + r'adult' + DELIM: '🧑',
    DELIM + r'blond_haired_person' + DELIM: '👱',
    DELIM + r'man' + DELIM: '👨',
    DELIM + r'bearded_person' + DELIM: '🧔',
    DELIM + r'man_beard' + DELIM: '🧔‍♂️',
    DELIM + r'woman_beard' + DELIM: '🧔‍♀️',
    DELIM + r'red_haired_man' + DELIM: '👨‍🦰',
    DELIM + r'curly_haired_man' + DELIM: '👨‍🦱',
    DELIM + r'white_haired_man' + DELIM: '👨‍🦳',
    DELIM + r'bald_man' + DELIM: '👨‍🦲',
    DELIM + r'woman' + DELIM: '👩',
    DELIM + r'red_haired_woman' + DELIM: '👩‍🦰',
    DELIM + r'person_red_hair' + DELIM: '🧑‍🦰',
    DELIM + r'curly_haired_woman' + DELIM: '👩‍🦱',
    DELIM + r'person_curly_hair' + DELIM: '🧑‍🦱',
    DELIM + r'white_haired_woman' + DELIM: '👩‍🦳',
    DELIM + r'person_white_hair' + DELIM: '🧑‍🦳',
    DELIM + r'bald_woman' + DELIM: '👩‍🦲',
    DELIM + r'person_bald' + DELIM: '🧑‍🦲',
    DELIM + r'blond_(haired_)?woman' + DELIM: '👱‍♀️',
    DELIM + r'blond_haired_man' + DELIM: '👱‍♂️',
    DELIM + r'older_adult' + DELIM: '🧓',
    DELIM + r'older_man' + DELIM: '👴',
    DELIM + r'older_woman' + DELIM: '👵',

    #
    # Person Gesture
    #
    DELIM + r'frowning_person' + DELIM: '🙍',
    DELIM + r'frowning_man' + DELIM: '🙍‍♂️',
    DELIM + r'frowning_woman' + DELIM: '🙍‍♀️',
    DELIM + r'pouting_face' + DELIM: '🙎',
    DELIM + r'pouting_man' + DELIM: '🙎‍♂️',
    DELIM + r'pouting_woman' + DELIM: '🙎‍♀️',
    DELIM + r'no_good' + DELIM: '🙅',
    DELIM + r'(ng|no_good)_man' + DELIM: '🙅‍♂️',
    DELIM + r'(ng_woman|no_good_woman)' + DELIM: '🙅‍♀️',
    DELIM + r'ok_person' + DELIM: '🙆',
    DELIM + r'ok_man' + DELIM: '🙆‍♂️',
    DELIM + r'ok_woman' + DELIM: '🙆‍♀️',
    DELIM + r'(information_desk|tipping_hand_)person' + DELIM: '💁',
    DELIM + r'(sassy_man|tipping_hand_man)' + DELIM: '💁‍♂️',
    DELIM + r'(sassy_woman|tipping_hand_woman)' + DELIM: '💁‍♀️',
    DELIM + r'raising_hand' + DELIM: '🙋',
    DELIM + r'raising_hand_man' + DELIM: '🙋‍♂️',
    DELIM + r'raising_hand_woman' + DELIM: '🙋‍♀️',
    DELIM + r'deaf_person' + DELIM: '🧏',
    DELIM + r'deaf_man' + DELIM: '🧏‍♂️',
    DELIM + r'deaf_woman' + DELIM: '🧏‍♀️',
    DELIM + r'bow' + DELIM: '🙇',
    DELIM + r'bowing_man' + DELIM: '🙇‍♂️',
    DELIM + r'bowing_woman' + DELIM: '🙇‍♀️',
    DELIM + r'facepalm' + DELIM: '🤦',
    DELIM + r'man_facepalming' + DELIM: '🤦‍♂️',
    DELIM + r'woman_facepalming' + DELIM: '🤦‍♀️',
    DELIM + r'shrug' + DELIM: '🤷',
    DELIM + r'man_shrugging' + DELIM: '🤷‍♂️',
    DELIM + r'woman_shrugging' + DELIM: '🤷‍♀️',

    #
    # Person Role
    #
    DELIM + r'health_worker' + DELIM: '🧑‍⚕️',
    DELIM + r'man_health_worker' + DELIM: '👨‍⚕️',
    DELIM + r'woman_health_worker' + DELIM: '👩‍⚕️',
    DELIM + r'student' + DELIM: '🧑‍🎓',
    DELIM + r'man_student' + DELIM: '👨‍🎓',
    DELIM + r'woman_student' + DELIM: '👩‍🎓',
    DELIM + r'teacher' + DELIM: '🧑‍🏫',
    DELIM + r'man_teacher' + DELIM: '👨‍🏫',
    DELIM + r'woman_teacher' + DELIM: '👩‍🏫',
    DELIM + r'judge' + DELIM: '🧑‍⚖️',
    DELIM + r'man_judge' + DELIM: '👨‍⚖️',
    DELIM + r'woman_judge' + DELIM: '👩‍⚖️',
    DELIM + r'farmer' + DELIM: '🧑‍🌾',
    DELIM + r'man_farmer' + DELIM: '👨‍🌾',
    DELIM + r'woman_farmer' + DELIM: '👩‍🌾',
    DELIM + r'cook' + DELIM: '🧑‍🍳',
    DELIM + r'man_cook' + DELIM: '👨‍🍳',
    DELIM + r'woman_cook' + DELIM: '👩‍🍳',
    DELIM + r'mechanic' + DELIM: '🧑‍🔧',
    DELIM + r'man_mechanic' + DELIM: '👨‍🔧',
    DELIM + r'woman_mechanic' + DELIM: '👩‍🔧',
    DELIM + r'factory_worker' + DELIM: '🧑‍🏭',
    DELIM + r'man_factory_worker' + DELIM: '👨‍🏭',
    DELIM + r'woman_factory_worker' + DELIM: '👩‍🏭',
    DELIM + r'office_worker' + DELIM: '🧑‍💼',
    DELIM + r'man_office_worker' + DELIM: '👨‍💼',
    DELIM + r'woman_office_worker' + DELIM: '👩‍💼',
    DELIM + r'scientist' + DELIM: '🧑‍🔬',
    DELIM + r'man_scientist' + DELIM: '👨‍🔬',
    DELIM + r'woman_scientist' + DELIM: '👩‍🔬',
    DELIM + r'technologist' + DELIM: '🧑‍💻',
    DELIM + r'man_technologist' + DELIM: '👨‍💻',
    DELIM + r'woman_technologist' + DELIM: '👩‍💻',
    DELIM + r'singer' + DELIM: '🧑‍🎤',
    DELIM + r'man_singer' + DELIM: '👨‍🎤',
    DELIM + r'woman_singer' + DELIM: '👩‍🎤',
    DELIM + r'artist' + DELIM: '🧑‍🎨',
    DELIM + r'man_artist' + DELIM: '👨‍🎨',
    DELIM + r'woman_artist' + DELIM: '👩‍🎨',
    DELIM + r'pilot' + DELIM: '🧑‍✈️',
    DELIM + r'man_pilot' + DELIM: '👨‍✈️',
    DELIM + r'woman_pilot' + DELIM: '👩‍✈️',
    DELIM + r'astronaut' + DELIM: '🧑‍🚀',
    DELIM + r'man_astronaut' + DELIM: '👨‍🚀',
    DELIM + r'woman_astronaut' + DELIM: '👩‍🚀',
    DELIM + r'firefighter' + DELIM: '🧑‍🚒',
    DELIM + r'man_firefighter' + DELIM: '👨‍🚒',
    DELIM + r'woman_firefighter' + DELIM: '👩‍🚒',
    DELIM + r'cop' + DELIM: '👮',
    DELIM + r'police(_officer|man)' + DELIM: '👮‍♂️',
    DELIM + r'policewoman' + DELIM: '👮‍♀️',
    DELIM + r'detective' + DELIM: '🕵️',
    DELIM + r'male_detective' + DELIM: '🕵️‍♂️',
    DELIM + r'female_detective' + DELIM: '🕵️‍♀️',
    DELIM + r'guard' + DELIM: '💂',
    DELIM + r'guardsman' + DELIM: '💂‍♂️',
    DELIM + r'guardswoman' + DELIM: '💂‍♀️',
    DELIM + r'ninja' + DELIM: '🥷',
    DELIM + r'construction_worker' + DELIM: '👷',
    DELIM + r'construction_worker_man' + DELIM: '👷‍♂️',
    DELIM + r'construction_worker_woman' + DELIM: '👷‍♀️',
    DELIM + r'prince' + DELIM: '🤴',
    DELIM + r'princess' + DELIM: '👸',
    DELIM + r'person_with_turban' + DELIM: '👳',
    DELIM + r'man_with_turban' + DELIM: '👳‍♂️',
    DELIM + r'woman_with_turban' + DELIM: '👳‍♀️',
    DELIM + r'man_with_gua_pi_mao' + DELIM: '👲',
    DELIM + r'woman_with_headscarf' + DELIM: '🧕',
    DELIM + r'person_in_tuxedo' + DELIM: '🤵',
    DELIM + r'man_in_tuxedo' + DELIM: '🤵‍♂️',
    DELIM + r'woman_in_tuxedo' + DELIM: '🤵‍♀️',
    DELIM + r'person_with_veil' + DELIM: '👰',
    DELIM + r'man_with_veil' + DELIM: '👰‍♂️',
    DELIM + r'(bride|woman)_with_veil' + DELIM: '👰‍♀️',
    DELIM + r'pregnant_woman' + DELIM: '🤰',
    DELIM + r'breast_feeding' + DELIM: '🤱',
    DELIM + r'woman_feeding_baby' + DELIM: '👩‍🍼',
    DELIM + r'man_feeding_baby' + DELIM: '👨‍🍼',
    DELIM + r'person_feeding_baby' + DELIM: '🧑‍🍼',

    #
    # Person Fantasy
    #
    DELIM + r'angel' + DELIM: '👼',
    DELIM + r'santa' + DELIM: '🎅',
    DELIM + r'mrs_claus' + DELIM: '🤶',
    DELIM + r'mx_claus' + DELIM: '🧑‍🎄',
    DELIM + r'superhero' + DELIM: '🦸',
    DELIM + r'superhero_man' + DELIM: '🦸‍♂️',
    DELIM + r'superhero_woman' + DELIM: '🦸‍♀️',
    DELIM + r'supervillain' + DELIM: '🦹',
    DELIM + r'supervillain_man' + DELIM: '🦹‍♂️',
    DELIM + r'supervillain_woman' + DELIM: '🦹‍♀️',
    DELIM + r'mage' + DELIM: '🧙',
    DELIM + r'mage_man' + DELIM: '🧙‍♂️',
    DELIM + r'mage_woman' + DELIM: '🧙‍♀️',
    DELIM + r'fairy' + DELIM: '🧚',
    DELIM + r'fairy_man' + DELIM: '🧚‍♂️',
    DELIM + r'fairy_woman' + DELIM: '🧚‍♀️',
    DELIM + r'vampire' + DELIM: '🧛',
    DELIM + r'vampire_man' + DELIM: '🧛‍♂️',
    DELIM + r'vampire_woman' + DELIM: '🧛‍♀️',
    DELIM + r'merperson' + DELIM: '🧜',
    DELIM + r'merman' + DELIM: '🧜‍♂️',
    DELIM + r'mermaid' + DELIM: '🧜‍♀️',
    DELIM + r'elf' + DELIM: '🧝',
    DELIM + r'elf_man' + DELIM: '🧝‍♂️',
    DELIM + r'elf_woman' + DELIM: '🧝‍♀️',
    DELIM + r'genie' + DELIM: '🧞',
    DELIM + r'genie_man' + DELIM: '🧞‍♂️',
    DELIM + r'genie_woman' + DELIM: '🧞‍♀️',
    DELIM + r'zombie' + DELIM: '🧟',
    DELIM + r'zombie_man' + DELIM: '🧟‍♂️',
    DELIM + r'zombie_woman' + DELIM: '🧟‍♀️',

    #
    # Person Activity
    #
    DELIM + r'massage' + DELIM: '💆',
    DELIM + r'massage_man' + DELIM: '💆‍♂️',
    DELIM + r'massage_woman' + DELIM: '💆‍♀️',
    DELIM + r'haircut' + DELIM: '💇',
    DELIM + r'haircut_man' + DELIM: '💇‍♂️',
    DELIM + r'haircut_woman' + DELIM: '💇‍♀️',
    DELIM + r'walking' + DELIM: '🚶',
    DELIM + r'walking_man' + DELIM: '🚶‍♂️',
    DELIM + r'walking_woman' + DELIM: '🚶‍♀️',
    DELIM + r'standing_person' + DELIM: '🧍',
    DELIM + r'standing_man' + DELIM: '🧍‍♂️',
    DELIM + r'standing_woman' + DELIM: '🧍‍♀️',
    DELIM + r'kneeling_person' + DELIM: '🧎',
    DELIM + r'kneeling_man' + DELIM: '🧎‍♂️',
    DELIM + r'kneeling_woman' + DELIM: '🧎‍♀️',
    DELIM + r'person_with_probing_cane' + DELIM: '🧑‍🦯',
    DELIM + r'man_with_probing_cane' + DELIM: '👨‍🦯',
    DELIM + r'woman_with_probing_cane' + DELIM: '👩‍🦯',
    DELIM + r'person_in_motorized_wheelchair' + DELIM: '🧑‍🦼',
    DELIM + r'man_in_motorized_wheelchair' + DELIM: '👨‍🦼',
    DELIM + r'woman_in_motorized_wheelchair' + DELIM: '👩‍🦼',
    DELIM + r'person_in_manual_wheelchair' + DELIM: '🧑‍🦽',
    DELIM + r'man_in_manual_wheelchair' + DELIM: '👨‍🦽',
    DELIM + r'woman_in_manual_wheelchair' + DELIM: '👩‍🦽',
    DELIM + r'runn(er|ing)' + DELIM: '🏃',
    DELIM + r'running_man' + DELIM: '🏃‍♂️',
    DELIM + r'running_woman' + DELIM: '🏃‍♀️',
    DELIM + r'(dancer|woman_dancing)' + DELIM: '💃',
    DELIM + r'man_dancing' + DELIM: '🕺',
    DELIM + r'business_suit_levitating' + DELIM: '🕴️',
    DELIM + r'dancers' + DELIM: '👯',
    DELIM + r'dancing_men' + DELIM: '👯‍♂️',
    DELIM + r'dancing_women' + DELIM: '👯‍♀️',
    DELIM + r'sauna_person' + DELIM: '🧖',
    DELIM + r'sauna_man' + DELIM: '🧖‍♂️',
    DELIM + r'sauna_woman' + DELIM: '🧖‍♀️',
    DELIM + r'climbing' + DELIM: '🧗',
    DELIM + r'climbing_man' + DELIM: '🧗‍♂️',
    DELIM + r'climbing_woman' + DELIM: '🧗‍♀️',

    #
    # Person Sport
    #
    DELIM + r'person_fencing' + DELIM: '🤺',
    DELIM + r'horse_racing' + DELIM: '🏇',
    DELIM + r'skier' + DELIM: '⛷️',
    DELIM + r'snowboarder' + DELIM: '🏂',
    DELIM + r'golfing' + DELIM: '🏌️',
    DELIM + r'golfing_man' + DELIM: '🏌️‍♂️',
    DELIM + r'golfing_woman' + DELIM: '🏌️‍♀️',
    DELIM + r'surfer' + DELIM: '🏄',
    DELIM + r'surfing_man' + DELIM: '🏄‍♂️',
    DELIM + r'surfing_woman' + DELIM: '🏄‍♀️',
    DELIM + r'rowboat' + DELIM: '🚣',
    DELIM + r'rowing_man' + DELIM: '🚣‍♂️',
    DELIM + r'rowing_woman' + DELIM: '🚣‍♀️',
    DELIM + r'swimmer' + DELIM: '🏊',
    DELIM + r'swimming_man' + DELIM: '🏊‍♂️',
    DELIM + r'swimming_woman' + DELIM: '🏊‍♀️',
    DELIM + r'bouncing_ball_person' + DELIM: '⛹️',
    DELIM + r'(basketball|bouncing_ball)_man' + DELIM: '⛹️‍♂️',
    DELIM + r'(basketball|bouncing_ball)_woman' + DELIM: '⛹️‍♀️',
    DELIM + r'weight_lifting' + DELIM: '🏋️',
    DELIM + r'weight_lifting_man' + DELIM: '🏋️‍♂️',
    DELIM + r'weight_lifting_woman' + DELIM: '🏋️‍♀️',
    DELIM + r'bicyclist' + DELIM: '🚴',
    DELIM + r'biking_man' + DELIM: '🚴‍♂️',
    DELIM + r'biking_woman' + DELIM: '🚴‍♀️',
    DELIM + r'mountain_bicyclist' + DELIM: '🚵',
    DELIM + r'mountain_biking_man' + DELIM: '🚵‍♂️',
    DELIM + r'mountain_biking_woman' + DELIM: '🚵‍♀️',
    DELIM + r'cartwheeling' + DELIM: '🤸',
    DELIM + r'man_cartwheeling' + DELIM: '🤸‍♂️',
    DELIM + r'woman_cartwheeling' + DELIM: '🤸‍♀️',
    DELIM + r'wrestling' + DELIM: '🤼',
    DELIM + r'men_wrestling' + DELIM: '🤼‍♂️',
    DELIM + r'women_wrestling' + DELIM: '🤼‍♀️',
    DELIM + r'water_polo' + DELIM: '🤽',
    DELIM + r'man_playing_water_polo' + DELIM: '🤽‍♂️',
    DELIM + r'woman_playing_water_polo' + DELIM: '🤽‍♀️',
    DELIM + r'handball_person' + DELIM: '🤾',
    DELIM + r'man_playing_handball' + DELIM: '🤾‍♂️',
    DELIM + r'woman_playing_handball' + DELIM: '🤾‍♀️',
    DELIM + r'juggling_person' + DELIM: '🤹',
    DELIM + r'man_juggling' + DELIM: '🤹‍♂️',
    DELIM + r'woman_juggling' + DELIM: '🤹‍♀️',

    #
    # Person Resting
    #
    DELIM + r'lotus_position' + DELIM: '🧘',
    DELIM + r'lotus_position_man' + DELIM: '🧘‍♂️',
    DELIM + r'lotus_position_woman' + DELIM: '🧘‍♀️',
    DELIM + r'bath' + DELIM: '🛀',
    DELIM + r'sleeping_bed' + DELIM: '🛌',

    #
    # Family
    #
    DELIM + r'people_holding_hands' + DELIM: '🧑‍🤝‍🧑',
    DELIM + r'two_women_holding_hands' + DELIM: '👭',
    DELIM + r'couple' + DELIM: '👫',
    DELIM + r'two_men_holding_hands' + DELIM: '👬',
    DELIM + r'couplekiss' + DELIM: '💏',
    DELIM + r'couplekiss_man_woman' + DELIM: '👩‍❤️‍💋‍👨',
    DELIM + r'couplekiss_man_man' + DELIM: '👨‍❤️‍💋‍👨',
    DELIM + r'couplekiss_woman_woman' + DELIM: '👩‍❤️‍💋‍👩',
    DELIM + r'couple_with_heart' + DELIM: '💑',
    DELIM + r'couple_with_heart_woman_man' + DELIM: '👩‍❤️‍👨',
    DELIM + r'couple_with_heart_man_man' + DELIM: '👨‍❤️‍👨',
    DELIM + r'couple_with_heart_woman_woman' + DELIM: '👩‍❤️‍👩',
    DELIM + r'family_man_woman_boy' + DELIM: '👨‍👩‍👦',
    DELIM + r'family_man_woman_girl' + DELIM: '👨‍👩‍👧',
    DELIM + r'family_man_woman_girl_boy' + DELIM: '👨‍👩‍👧‍👦',
    DELIM + r'family_man_woman_boy_boy' + DELIM: '👨‍👩‍👦‍👦',
    DELIM + r'family_man_woman_girl_girl' + DELIM: '👨‍👩‍👧‍👧',
    DELIM + r'family_man_man_boy' + DELIM: '👨‍👨‍👦',
    DELIM + r'family_man_man_girl' + DELIM: '👨‍👨‍👧',
    DELIM + r'family_man_man_girl_boy' + DELIM: '👨‍👨‍👧‍👦',
    DELIM + r'family_man_man_boy_boy' + DELIM: '👨‍👨‍👦‍👦',
    DELIM + r'family_man_man_girl_girl' + DELIM: '👨‍👨‍👧‍👧',
    DELIM + r'family_woman_woman_boy' + DELIM: '👩‍👩‍👦',
    DELIM + r'family_woman_woman_girl' + DELIM: '👩‍👩‍👧',
    DELIM + r'family_woman_woman_girl_boy' + DELIM: '👩‍👩‍👧‍👦',
    DELIM + r'family_woman_woman_boy_boy' + DELIM: '👩‍👩‍👦‍👦',
    DELIM + r'family_woman_woman_girl_girl' + DELIM: '👩‍👩‍👧‍👧',
    DELIM + r'family_man_boy' + DELIM: '👨‍👦',
    DELIM + r'family_man_boy_boy' + DELIM: '👨‍👦‍👦',
    DELIM + r'family_man_girl' + DELIM: '👨‍👧',
    DELIM + r'family_man_girl_boy' + DELIM: '👨‍👧‍👦',
    DELIM + r'family_man_girl_girl' + DELIM: '👨‍👧‍👧',
    DELIM + r'family_woman_boy' + DELIM: '👩‍👦',
    DELIM + r'family_woman_boy_boy' + DELIM: '👩‍👦‍👦',
    DELIM + r'family_woman_girl' + DELIM: '👩‍👧',
    DELIM + r'family_woman_girl_boy' + DELIM: '👩‍👧‍👦',
    DELIM + r'family_woman_girl_girl' + DELIM: '👩‍👧‍👧',

    #
    # Person Symbol
    #
    DELIM + r'speaking_head' + DELIM: '🗣️',
    DELIM + r'bust_in_silhouette' + DELIM: '👤',
    DELIM + r'busts_in_silhouette' + DELIM: '👥',
    DELIM + r'people_hugging' + DELIM: '🫂',
    DELIM + r'family' + DELIM: '👪',
    DELIM + r'footprints' + DELIM: '👣',

    #
    # Animal Mammal
    #
    DELIM + r'monkey_face' + DELIM: '🐵',
    DELIM + r'monkey' + DELIM: '🐒',
    DELIM + r'gorilla' + DELIM: '🦍',
    DELIM + r'orangutan' + DELIM: '🦧',
    DELIM + r'dog' + DELIM: '🐶',
    DELIM + r'dog2' + DELIM: '🐕',
    DELIM + r'guide_dog' + DELIM: '🦮',
    DELIM + r'service_dog' + DELIM: '🐕‍🦺',
    DELIM + r'poodle' + DELIM: '🐩',
    DELIM + r'wolf' + DELIM: '🐺',
    DELIM + r'fox_face' + DELIM: '🦊',
    DELIM + r'raccoon' + DELIM: '🦝',
    DELIM + r'cat' + DELIM: '🐱',
    DELIM + r'cat2' + DELIM: '🐈',
    DELIM + r'black_cat' + DELIM: '🐈‍⬛',
    DELIM + r'lion' + DELIM: '🦁',
    DELIM + r'tiger' + DELIM: '🐯',
    DELIM + r'tiger2' + DELIM: '🐅',
    DELIM + r'leopard' + DELIM: '🐆',
    DELIM + r'horse' + DELIM: '🐴',
    DELIM + r'racehorse' + DELIM: '🐎',
    DELIM + r'unicorn' + DELIM: '🦄',
    DELIM + r'zebra' + DELIM: '🦓',
    DELIM + r'deer' + DELIM: '🦌',
    DELIM + r'bison' + DELIM: '🦬',
    DELIM + r'cow' + DELIM: '🐮',
    DELIM + r'ox' + DELIM: '🐂',
    DELIM + r'water_buffalo' + DELIM: '🐃',
    DELIM + r'cow2' + DELIM: '🐄',
    DELIM + r'pig' + DELIM: '🐷',
    DELIM + r'pig2' + DELIM: '🐖',
    DELIM + r'boar' + DELIM: '🐗',
    DELIM + r'pig_nose' + DELIM: '🐽',
    DELIM + r'ram' + DELIM: '🐏',
    DELIM + r'sheep' + DELIM: '🐑',
    DELIM + r'goat' + DELIM: '🐐',
    DELIM + r'dromedary_camel' + DELIM: '🐪',
    DELIM + r'camel' + DELIM: '🐫',
    DELIM + r'llama' + DELIM: '🦙',
    DELIM + r'giraffe' + DELIM: '🦒',
    DELIM + r'elephant' + DELIM: '🐘',
    DELIM + r'mammoth' + DELIM: '🦣',
    DELIM + r'rhinoceros' + DELIM: '🦏',
    DELIM + r'hippopotamus' + DELIM: '🦛',
    DELIM + r'mouse' + DELIM: '🐭',
    DELIM + r'mouse2' + DELIM: '🐁',
    DELIM + r'rat' + DELIM: '🐀',
    DELIM + r'hamster' + DELIM: '🐹',
    DELIM + r'rabbit' + DELIM: '🐰',
    DELIM + r'rabbit2' + DELIM: '🐇',
    DELIM + r'chipmunk' + DELIM: '🐿️',
    DELIM + r'beaver' + DELIM: '🦫',
    DELIM + r'hedgehog' + DELIM: '🦔',
    DELIM + r'bat' + DELIM: '🦇',
    DELIM + r'bear' + DELIM: '🐻',
    DELIM + r'polar_bear' + DELIM: '🐻‍❄️',
    DELIM + r'koala' + DELIM: '🐨',
    DELIM + r'panda_face' + DELIM: '🐼',
    DELIM + r'sloth' + DELIM: '🦥',
    DELIM + r'otter' + DELIM: '🦦',
    DELIM + r'skunk' + DELIM: '🦨',
    DELIM + r'kangaroo' + DELIM: '🦘',
    DELIM + r'badger' + DELIM: '🦡',
    DELIM + r'(feet|paw_prints)' + DELIM: '🐾',

    #
    # Animal Bird
    #
    DELIM + r'turkey' + DELIM: '🦃',
    DELIM + r'chicken' + DELIM: '🐔',
    DELIM + r'rooster' + DELIM: '🐓',
    DELIM + r'hatching_chick' + DELIM: '🐣',
    DELIM + r'baby_chick' + DELIM: '🐤',
    DELIM + r'hatched_chick' + DELIM: '🐥',
    DELIM + r'bird' + DELIM: '🐦',
    DELIM + r'penguin' + DELIM: '🐧',
    DELIM + r'dove' + DELIM: '🕊️',
    DELIM + r'eagle' + DELIM: '🦅',
    DELIM + r'duck' + DELIM: '🦆',
    DELIM + r'swan' + DELIM: '🦢',
    DELIM + r'owl' + DELIM: '🦉',
    DELIM + r'dodo' + DELIM: '🦤',
    DELIM + r'feather' + DELIM: '🪶',
    DELIM + r'flamingo' + DELIM: '🦩',
    DELIM + r'peacock' + DELIM: '🦚',
    DELIM + r'parrot' + DELIM: '🦜',

    #
    # Animal Amphibian
    #
    DELIM + r'frog' + DELIM: '🐸',

    #
    # Animal Reptile
    #
    DELIM + r'crocodile' + DELIM: '🐊',
    DELIM + r'turtle' + DELIM: '🐢',
    DELIM + r'lizard' + DELIM: '🦎',
    DELIM + r'snake' + DELIM: '🐍',
    DELIM + r'dragon_face' + DELIM: '🐲',
    DELIM + r'dragon' + DELIM: '🐉',
    DELIM + r'sauropod' + DELIM: '🦕',
    DELIM + r't-rex' + DELIM: '🦖',

    #
    # Animal Marine
    #
    DELIM + r'whale' + DELIM: '🐳',
    DELIM + r'whale2' + DELIM: '🐋',
    DELIM + r'dolphin' + DELIM: '🐬',
    DELIM + r'(seal|flipper)' + DELIM: '🦭',
    DELIM + r'fish' + DELIM: '🐟',
    DELIM + r'tropical_fish' + DELIM: '🐠',
    DELIM + r'blowfish' + DELIM: '🐡',
    DELIM + r'shark' + DELIM: '🦈',
    DELIM + r'octopus' + DELIM: '🐙',
    DELIM + r'shell' + DELIM: '🐚',

    #
    # Animal Bug
    #
    DELIM + r'snail' + DELIM: '🐌',
    DELIM + r'butterfly' + DELIM: '🦋',
    DELIM + r'bug' + DELIM: '🐛',
    DELIM + r'ant' + DELIM: '🐜',
    DELIM + r'bee' + DELIM: '🐝',
    DELIM + r'honeybee' + DELIM: '🪲',
    DELIM + r'(lady_)?beetle' + DELIM: '🐞',
    DELIM + r'cricket' + DELIM: '🦗',
    DELIM + r'cockroach' + DELIM: '🪳',
    DELIM + r'spider' + DELIM: '🕷️',
    DELIM + r'spider_web' + DELIM: '🕸️',
    DELIM + r'scorpion' + DELIM: '🦂',
    DELIM + r'mosquito' + DELIM: '🦟',
    DELIM + r'fly' + DELIM: '🪰',
    DELIM + r'worm' + DELIM: '🪱',
    DELIM + r'microbe' + DELIM: '🦠',

    #
    # Plant Flower
    #
    DELIM + r'bouquet' + DELIM: '💐',
    DELIM + r'cherry_blossom' + DELIM: '🌸',
    DELIM + r'white_flower' + DELIM: '💮',
    DELIM + r'rosette' + DELIM: '🏵️',
    DELIM + r'rose' + DELIM: '🌹',
    DELIM + r'wilted_flower' + DELIM: '🥀',
    DELIM + r'hibiscus' + DELIM: '🌺',
    DELIM + r'sunflower' + DELIM: '🌻',
    DELIM + r'blossom' + DELIM: '🌼',
    DELIM + r'tulip' + DELIM: '🌷',

    #
    # Plant Other
    #
    DELIM + r'seedling' + DELIM: '🌱',
    DELIM + r'potted_plant' + DELIM: '🪴',
    DELIM + r'evergreen_tree' + DELIM: '🌲',
    DELIM + r'deciduous_tree' + DELIM: '🌳',
    DELIM + r'palm_tree' + DELIM: '🌴',
    DELIM + r'cactus' + DELIM: '🌵',
    DELIM + r'ear_of_rice' + DELIM: '🌾',
    DELIM + r'herb' + DELIM: '🌿',
    DELIM + r'shamrock' + DELIM: '☘️',
    DELIM + r'four_leaf_clover' + DELIM: '🍀',
    DELIM + r'maple_leaf' + DELIM: '🍁',
    DELIM + r'fallen_leaf' + DELIM: '🍂',
    DELIM + r'leaves' + DELIM: '🍃',
    DELIM + r'mushroom' + DELIM: '🍄',

    #
    # Food Fruit
    #
    DELIM + r'grapes' + DELIM: '🍇',
    DELIM + r'melon' + DELIM: '🍈',
    DELIM + r'watermelon' + DELIM: '🍉',
    DELIM + r'(orange|mandarin|tangerine)' + DELIM: '🍊',
    DELIM + r'lemon' + DELIM: '🍋',
    DELIM + r'banana' + DELIM: '🍌',
    DELIM + r'pineapple' + DELIM: '🍍',
    DELIM + r'mango' + DELIM: '🥭',
    DELIM + r'apple' + DELIM: '🍎',
    DELIM + r'green_apple' + DELIM: '🍏',
    DELIM + r'pear' + DELIM: '🍐',
    DELIM + r'peach' + DELIM: '🍑',
    DELIM + r'cherries' + DELIM: '🍒',
    DELIM + r'strawberry' + DELIM: '🍓',
    DELIM + r'blueberries' + DELIM: '🫐',
    DELIM + r'kiwi_fruit' + DELIM: '🥝',
    DELIM + r'tomato' + DELIM: '🍅',
    DELIM + r'olive' + DELIM: '🫒',
    DELIM + r'coconut' + DELIM: '🥥',

    #
    # Food Vegetable
    #
    DELIM + r'avocado' + DELIM: '🥑',
    DELIM + r'eggplant' + DELIM: '🍆',
    DELIM + r'potato' + DELIM: '🥔',
    DELIM + r'carrot' + DELIM: '🥕',
    DELIM + r'corn' + DELIM: '🌽',
    DELIM + r'hot_pepper' + DELIM: '🌶️',
    DELIM + r'bell_pepper' + DELIM: '🫑',
    DELIM + r'cucumber' + DELIM: '🥒',
    DELIM + r'leafy_green' + DELIM: '🥬',
    DELIM + r'broccoli' + DELIM: '🥦',
    DELIM + r'garlic' + DELIM: '🧄',
    DELIM + r'onion' + DELIM: '🧅',
    DELIM + r'peanuts' + DELIM: '🥜',
    DELIM + r'chestnut' + DELIM: '🌰',

    #
    # Food Prepared
    #
    DELIM + r'bread' + DELIM: '🍞',
    DELIM + r'croissant' + DELIM: '🥐',
    DELIM + r'baguette_bread' + DELIM: '🥖',
    DELIM + r'flatbread' + DELIM: '🫓',
    DELIM + r'pretzel' + DELIM: '🥨',
    DELIM + r'bagel' + DELIM: '🥯',
    DELIM + r'pancakes' + DELIM: '🥞',
    DELIM + r'waffle' + DELIM: '🧇',
    DELIM + r'cheese' + DELIM: '🧀',
    DELIM + r'meat_on_bone' + DELIM: '🍖',
    DELIM + r'poultry_leg' + DELIM: '🍗',
    DELIM + r'cut_of_meat' + DELIM: '🥩',
    DELIM + r'bacon' + DELIM: '🥓',
    DELIM + r'hamburger' + DELIM: '🍔',
    DELIM + r'fries' + DELIM: '🍟',
    DELIM + r'pizza' + DELIM: '🍕',
    DELIM + r'hotdog' + DELIM: '🌭',
    DELIM + r'sandwich' + DELIM: '🥪',
    DELIM + r'taco' + DELIM: '🌮',
    DELIM + r'burrito' + DELIM: '🌯',
    DELIM + r'tamale' + DELIM: '🫔',
    DELIM + r'stuffed_flatbread' + DELIM: '🥙',
    DELIM + r'falafel' + DELIM: '🧆',
    DELIM + r'egg' + DELIM: '🥚',
    DELIM + r'fried_egg' + DELIM: '🍳',
    DELIM + r'shallow_pan_of_food' + DELIM: '🥘',
    DELIM + r'stew' + DELIM: '🍲',
    DELIM + r'fondue' + DELIM: '🫕',
    DELIM + r'bowl_with_spoon' + DELIM: '🥣',
    DELIM + r'green_salad' + DELIM: '🥗',
    DELIM + r'popcorn' + DELIM: '🍿',
    DELIM + r'butter' + DELIM: '🧈',
    DELIM + r'salt' + DELIM: '🧂',
    DELIM + r'canned_food' + DELIM: '🥫',

    #
    # Food Asian
    #
    DELIM + r'bento' + DELIM: '🍱',
    DELIM + r'rice_cracker' + DELIM: '🍘',
    DELIM + r'rice_ball' + DELIM: '🍙',
    DELIM + r'rice' + DELIM: '🍚',
    DELIM + r'curry' + DELIM: '🍛',
    DELIM + r'ramen' + DELIM: '🍜',
    DELIM + r'spaghetti' + DELIM: '🍝',
    DELIM + r'sweet_potato' + DELIM: '🍠',
    DELIM + r'oden' + DELIM: '🍢',
    DELIM + r'sushi' + DELIM: '🍣',
    DELIM + r'fried_shrimp' + DELIM: '🍤',
    DELIM + r'fish_cake' + DELIM: '🍥',
    DELIM + r'moon_cake' + DELIM: '🥮',
    DELIM + r'dango' + DELIM: '🍡',
    DELIM + r'dumpling' + DELIM: '🥟',
    DELIM + r'fortune_cookie' + DELIM: '🥠',
    DELIM + r'takeout_box' + DELIM: '🥡',

    #
    # Food Marine
    #
    DELIM + r'crab' + DELIM: '🦀',
    DELIM + r'lobster' + DELIM: '🦞',
    DELIM + r'shrimp' + DELIM: '🦐',
    DELIM + r'squid' + DELIM: '🦑',
    DELIM + r'oyster' + DELIM: '🦪',

    #
    # Food Sweet
    #
    DELIM + r'icecream' + DELIM: '🍦',
    DELIM + r'shaved_ice' + DELIM: '🍧',
    DELIM + r'ice_cream' + DELIM: '🍨',
    DELIM + r'doughnut' + DELIM: '🍩',
    DELIM + r'cookie' + DELIM: '🍪',
    DELIM + r'birthday' + DELIM: '🎂',
    DELIM + r'cake' + DELIM: '🍰',
    DELIM + r'cupcake' + DELIM: '🧁',
    DELIM + r'pie' + DELIM: '🥧',
    DELIM + r'chocolate_bar' + DELIM: '🍫',
    DELIM + r'candy' + DELIM: '🍬',
    DELIM + r'lollipop' + DELIM: '🍭',
    DELIM + r'custard' + DELIM: '🍮',
    DELIM + r'honey_pot' + DELIM: '🍯',

    #
    # Drink
    #
    DELIM + r'baby_bottle' + DELIM: '🍼',
    DELIM + r'milk_glass' + DELIM: '🥛',
    DELIM + r'coffee' + DELIM: '☕',
    DELIM + r'teapot' + DELIM: '🫖',
    DELIM + r'tea' + DELIM: '🍵',
    DELIM + r'sake' + DELIM: '🍶',
    DELIM + r'champagne' + DELIM: '🍾',
    DELIM + r'wine_glass' + DELIM: '🍷',
    DELIM + r'cocktail' + DELIM: '🍸',
    DELIM + r'tropical_drink' + DELIM: '🍹',
    DELIM + r'beer' + DELIM: '🍺',
    DELIM + r'beers' + DELIM: '🍻',
    DELIM + r'clinking_glasses' + DELIM: '🥂',
    DELIM + r'tumbler_glass' + DELIM: '🥃',
    DELIM + r'cup_with_straw' + DELIM: '🥤',
    DELIM + r'bubble_tea' + DELIM: '🧋',
    DELIM + r'beverage_box' + DELIM: '🧃',
    DELIM + r'mate' + DELIM: '🧉',
    DELIM + r'ice_cube' + DELIM: '🧊',

    #
    # Dishware
    #
    DELIM + r'chopsticks' + DELIM: '🥢',
    DELIM + r'plate_with_cutlery' + DELIM: '🍽️',
    DELIM + r'fork_and_knife' + DELIM: '🍴',
    DELIM + r'spoon' + DELIM: '🥄',
    DELIM + r'(hocho|knife)' + DELIM: '🔪',
    DELIM + r'amphora' + DELIM: '🏺',

    #
    # Place Map
    #
    DELIM + r'earth_africa' + DELIM: '🌍',
    DELIM + r'earth_americas' + DELIM: '🌎',
    DELIM + r'earth_asia' + DELIM: '🌏',
    DELIM + r'globe_with_meridians' + DELIM: '🌐',
    DELIM + r'world_map' + DELIM: '🗺️',
    DELIM + r'japan' + DELIM: '🗾',
    DELIM + r'compass' + DELIM: '🧭',

    #
    # Place Geographic
    #
    DELIM + r'mountain_snow' + DELIM: '🏔️',
    DELIM + r'mountain' + DELIM: '⛰️',
    DELIM + r'volcano' + DELIM: '🌋',
    DELIM + r'mount_fuji' + DELIM: '🗻',
    DELIM + r'camping' + DELIM: '🏕️',
    DELIM + r'beach_umbrella' + DELIM: '🏖️',
    DELIM + r'desert' + DELIM: '🏜️',
    DELIM + r'desert_island' + DELIM: '🏝️',
    DELIM + r'national_park' + DELIM: '🏞️',

    #
    # Place Building
    #
    DELIM + r'stadium' + DELIM: '🏟️',
    DELIM + r'classical_building' + DELIM: '🏛️',
    DELIM + r'building_construction' + DELIM: '🏗️',
    DELIM + r'bricks' + DELIM: '🧱',
    DELIM + r'rock' + DELIM: '🪨',
    DELIM + r'wood' + DELIM: '🪵',
    DELIM + r'hut' + DELIM: '🛖',
    DELIM + r'houses' + DELIM: '🏘️',
    DELIM + r'derelict_house' + DELIM: '🏚️',
    DELIM + r'house' + DELIM: '🏠',
    DELIM + r'house_with_garden' + DELIM: '🏡',
    DELIM + r'office' + DELIM: '🏢',
    DELIM + r'post_office' + DELIM: '🏣',
    DELIM + r'european_post_office' + DELIM: '🏤',
    DELIM + r'hospital' + DELIM: '🏥',
    DELIM + r'bank' + DELIM: '🏦',
    DELIM + r'hotel' + DELIM: '🏨',
    DELIM + r'love_hotel' + DELIM: '🏩',
    DELIM + r'convenience_store' + DELIM: '🏪',
    DELIM + r'school' + DELIM: '🏫',
    DELIM + r'department_store' + DELIM: '🏬',
    DELIM + r'factory' + DELIM: '🏭',
    DELIM + r'japanese_castle' + DELIM: '🏯',
    DELIM + r'european_castle' + DELIM: '🏰',
    DELIM + r'wedding' + DELIM: '💒',
    DELIM + r'tokyo_tower' + DELIM: '🗼',
    DELIM + r'statue_of_liberty' + DELIM: '🗽',

    #
    # Place Religious
    #
    DELIM + r'church' + DELIM: '⛪',
    DELIM + r'mosque' + DELIM: '🕌',
    DELIM + r'hindu_temple' + DELIM: '🛕',
    DELIM + r'synagogue' + DELIM: '🕍',
    DELIM + r'shinto_shrine' + DELIM: '⛩️',
    DELIM + r'kaaba' + DELIM: '🕋',

    #
    # Place Other
    #
    DELIM + r'fountain' + DELIM: '⛲',
    DELIM + r'tent' + DELIM: '⛺',
    DELIM + r'foggy' + DELIM: '🌁',
    DELIM + r'night_with_stars' + DELIM: '🌃',
    DELIM + r'cityscape' + DELIM: '🏙️',
    DELIM + r'sunrise_over_mountains' + DELIM: '🌄',
    DELIM + r'sunrise' + DELIM: '🌅',
    DELIM + r'city_sunset' + DELIM: '🌆',
    DELIM + r'city_sunrise' + DELIM: '🌇',
    DELIM + r'bridge_at_night' + DELIM: '🌉',
    DELIM + r'hotsprings' + DELIM: '♨️',
    DELIM + r'carousel_horse' + DELIM: '🎠',
    DELIM + r'ferris_wheel' + DELIM: '🎡',
    DELIM + r'roller_coaster' + DELIM: '🎢',
    DELIM + r'barber' + DELIM: '💈',
    DELIM + r'circus_tent' + DELIM: '🎪',

    #
    # Transport Ground
    #
    DELIM + r'steam_locomotive' + DELIM: '🚂',
    DELIM + r'railway_car' + DELIM: '🚃',
    DELIM + r'bullettrain_side' + DELIM: '🚄',
    DELIM + r'bullettrain_front' + DELIM: '🚅',
    DELIM + r'train2' + DELIM: '🚆',
    DELIM + r'metro' + DELIM: '🚇',
    DELIM + r'light_rail' + DELIM: '🚈',
    DELIM + r'station' + DELIM: '🚉',
    DELIM + r'tram' + DELIM: '🚊',
    DELIM + r'monorail' + DELIM: '🚝',
    DELIM + r'mountain_railway' + DELIM: '🚞',
    DELIM + r'train' + DELIM: '🚋',
    DELIM + r'bus' + DELIM: '🚌',
    DELIM + r'oncoming_bus' + DELIM: '🚍',
    DELIM + r'trolleybus' + DELIM: '🚎',
    DELIM + r'minibus' + DELIM: '🚐',
    DELIM + r'ambulance' + DELIM: '🚑',
    DELIM + r'fire_engine' + DELIM: '🚒',
    DELIM + r'police_car' + DELIM: '🚓',
    DELIM + r'oncoming_police_car' + DELIM: '🚔',
    DELIM + r'taxi' + DELIM: '🚕',
    DELIM + r'oncoming_taxi' + DELIM: '🚖',
    DELIM + r'car' + DELIM: '🚗',
    DELIM + r'(red_car|oncoming_automobile)' + DELIM: '🚘',
    DELIM + r'blue_car' + DELIM: '🚙',
    DELIM + r'pickup_truck' + DELIM: '🛻',
    DELIM + r'truck' + DELIM: '🚚',
    DELIM + r'articulated_lorry' + DELIM: '🚛',
    DELIM + r'tractor' + DELIM: '🚜',
    DELIM + r'racing_car' + DELIM: '🏎️',
    DELIM + r'motorcycle' + DELIM: '🏍️',
    DELIM + r'motor_scooter' + DELIM: '🛵',
    DELIM + r'manual_wheelchair' + DELIM: '🦽',
    DELIM + r'motorized_wheelchair' + DELIM: '🦼',
    DELIM + r'auto_rickshaw' + DELIM: '🛺',
    DELIM + r'bike' + DELIM: '🚲',
    DELIM + r'kick_scooter' + DELIM: '🛴',
    DELIM + r'skateboard' + DELIM: '🛹',
    DELIM + r'roller_skate' + DELIM: '🛼',
    DELIM + r'busstop' + DELIM: '🚏',
    DELIM + r'motorway' + DELIM: '🛣️',
    DELIM + r'railway_track' + DELIM: '🛤️',
    DELIM + r'oil_drum' + DELIM: '🛢️',
    DELIM + r'fuelpump' + DELIM: '⛽',
    DELIM + r'rotating_light' + DELIM: '🚨',
    DELIM + r'traffic_light' + DELIM: '🚥',
    DELIM + r'vertical_traffic_light' + DELIM: '🚦',
    DELIM + r'stop_sign' + DELIM: '🛑',
    DELIM + r'construction' + DELIM: '🚧',

    #
    # Transport Water
    #
    DELIM + r'anchor' + DELIM: '⚓',
    DELIM + r'(sailboat|boat)' + DELIM: '⛵',
    DELIM + r'canoe' + DELIM: '🛶',
    DELIM + r'speedboat' + DELIM: '🚤',
    DELIM + r'passenger_ship' + DELIM: '🛳️',
    DELIM + r'ferry' + DELIM: '⛴️',
    DELIM + r'motor_boat' + DELIM: '🛥️',
    DELIM + r'ship' + DELIM: '🚢',

    #
    # Transport Air
    #
    DELIM + r'airplane' + DELIM: '✈️',
    DELIM + r'small_airplane' + DELIM: '🛩️',
    DELIM + r'flight_departure' + DELIM: '🛫',
    DELIM + r'flight_arrival' + DELIM: '🛬',
    DELIM + r'parachute' + DELIM: '🪂',
    DELIM + r'seat' + DELIM: '💺',
    DELIM + r'helicopter' + DELIM: '🚁',
    DELIM + r'suspension_railway' + DELIM: '🚟',
    DELIM + r'mountain_cableway' + DELIM: '🚠',
    DELIM + r'aerial_tramway' + DELIM: '🚡',
    DELIM + r'artificial_satellite' + DELIM: '🛰️',
    DELIM + r'rocket' + DELIM: '🚀',
    DELIM + r'flying_saucer' + DELIM: '🛸',

    #
    # Hotel
    #
    DELIM + r'bellhop_bell' + DELIM: '🛎️',
    DELIM + r'luggage' + DELIM: '🧳',

    #
    # Time
    #
    DELIM + r'hourglass' + DELIM: '⌛',
    DELIM + r'hourglass_flowing_sand' + DELIM: '⏳',
    DELIM + r'watch' + DELIM: '⌚',
    DELIM + r'alarm_clock' + DELIM: '⏰',
    DELIM + r'stopwatch' + DELIM: '⏱️',
    DELIM + r'timer_clock' + DELIM: '⏲️',
    DELIM + r'mantelpiece_clock' + DELIM: '🕰️',
    DELIM + r'clock12' + DELIM: '🕛',
    DELIM + r'clock1230' + DELIM: '🕧',
    DELIM + r'clock1' + DELIM: '🕐',
    DELIM + r'clock130' + DELIM: '🕜',
    DELIM + r'clock2' + DELIM: '🕑',
    DELIM + r'clock230' + DELIM: '🕝',
    DELIM + r'clock3' + DELIM: '🕒',
    DELIM + r'clock330' + DELIM: '🕞',
    DELIM + r'clock4' + DELIM: '🕓',
    DELIM + r'clock430' + DELIM: '🕟',
    DELIM + r'clock5' + DELIM: '🕔',
    DELIM + r'clock530' + DELIM: '🕠',
    DELIM + r'clock6' + DELIM: '🕕',
    DELIM + r'clock630' + DELIM: '🕡',
    DELIM + r'clock7' + DELIM: '🕖',
    DELIM + r'clock730' + DELIM: '🕢',
    DELIM + r'clock8' + DELIM: '🕗',
    DELIM + r'clock830' + DELIM: '🕣',
    DELIM + r'clock9' + DELIM: '🕘',
    DELIM + r'clock930' + DELIM: '🕤',
    DELIM + r'clock10' + DELIM: '🕙',
    DELIM + r'clock1030' + DELIM: '🕥',
    DELIM + r'clock11' + DELIM: '🕚',
    DELIM + r'clock1130' + DELIM: '🕦',

    # Sky & Weather
    DELIM + r'new_moon' + DELIM: '🌑',
    DELIM + r'waxing_crescent_moon' + DELIM: '🌒',
    DELIM + r'first_quarter_moon' + DELIM: '🌓',
    DELIM + r'moon' + DELIM: '🌔',
    DELIM + r'(waxing_gibbous_moon|full_moon)' + DELIM: '🌕',
    DELIM + r'waning_gibbous_moon' + DELIM: '🌖',
    DELIM + r'last_quarter_moon' + DELIM: '🌗',
    DELIM + r'waning_crescent_moon' + DELIM: '🌘',
    DELIM + r'crescent_moon' + DELIM: '🌙',
    DELIM + r'new_moon_with_face' + DELIM: '🌚',
    DELIM + r'first_quarter_moon_with_face' + DELIM: '🌛',
    DELIM + r'last_quarter_moon_with_face' + DELIM: '🌜',
    DELIM + r'thermometer' + DELIM: '🌡️',
    DELIM + r'sunny' + DELIM: '☀️',
    DELIM + r'full_moon_with_face' + DELIM: '🌝',
    DELIM + r'sun_with_face' + DELIM: '🌞',
    DELIM + r'ringed_planet' + DELIM: '🪐',
    DELIM + r'star' + DELIM: '⭐',
    DELIM + r'star2' + DELIM: '🌟',
    DELIM + r'stars' + DELIM: '🌠',
    DELIM + r'milky_way' + DELIM: '🌌',
    DELIM + r'cloud' + DELIM: '☁️',
    DELIM + r'partly_sunny' + DELIM: '⛅',
    DELIM + r'cloud_with_lightning_and_rain' + DELIM: '⛈️',
    DELIM + r'sun_behind_small_cloud' + DELIM: '🌤️',
    DELIM + r'sun_behind_large_cloud' + DELIM: '🌥️',
    DELIM + r'sun_behind_rain_cloud' + DELIM: '🌦️',
    DELIM + r'cloud_with_rain' + DELIM: '🌧️',
    DELIM + r'cloud_with_snow' + DELIM: '🌨️',
    DELIM + r'cloud_with_lightning' + DELIM: '🌩️',
    DELIM + r'tornado' + DELIM: '🌪️',
    DELIM + r'fog' + DELIM: '🌫️',
    DELIM + r'wind_face' + DELIM: '🌬️',
    DELIM + r'cyclone' + DELIM: '🌀',
    DELIM + r'rainbow' + DELIM: '🌈',
    DELIM + r'closed_umbrella' + DELIM: '🌂',
    DELIM + r'open_umbrella' + DELIM: '☂️',
    DELIM + r'umbrella' + DELIM: '☔',
    DELIM + r'parasol_on_ground' + DELIM: '⛱️',
    DELIM + r'zap' + DELIM: '⚡',
    DELIM + r'snowflake' + DELIM: '❄️',
    DELIM + r'snowman_with_snow' + DELIM: '☃️',
    DELIM + r'snowman' + DELIM: '⛄',
    DELIM + r'comet' + DELIM: '☄️',
    DELIM + r'fire' + DELIM: '🔥',
    DELIM + r'droplet' + DELIM: '💧',
    DELIM + r'ocean' + DELIM: '🌊',

    #
    # Event
    #
    DELIM + r'jack_o_lantern' + DELIM: '🎃',
    DELIM + r'christmas_tree' + DELIM: '🎄',
    DELIM + r'fireworks' + DELIM: '🎆',
    DELIM + r'sparkler' + DELIM: '🎇',
    DELIM + r'firecracker' + DELIM: '🧨',
    DELIM + r'sparkles' + DELIM: '✨',
    DELIM + r'balloon' + DELIM: '🎈',
    DELIM + r'tada' + DELIM: '🎉',
    DELIM + r'confetti_ball' + DELIM: '🎊',
    DELIM + r'tanabata_tree' + DELIM: '🎋',
    DELIM + r'bamboo' + DELIM: '🎍',
    DELIM + r'dolls' + DELIM: '🎎',
    DELIM + r'flags' + DELIM: '🎏',
    DELIM + r'wind_chime' + DELIM: '🎐',
    DELIM + r'rice_scene' + DELIM: '🎑',
    DELIM + r'red_envelope' + DELIM: '🧧',
    DELIM + r'ribbon' + DELIM: '🎀',
    DELIM + r'gift' + DELIM: '🎁',
    DELIM + r'reminder_ribbon' + DELIM: '🎗️',
    DELIM + r'tickets' + DELIM: '🎟️',
    DELIM + r'ticket' + DELIM: '🎫',

    #
    # Award Medal
    #
    DELIM + r'medal_military' + DELIM: '🎖️',
    DELIM + r'trophy' + DELIM: '🏆',
    DELIM + r'medal_sports' + DELIM: '🏅',
    DELIM + r'1st_place_medal' + DELIM: '🥇',
    DELIM + r'2nd_place_medal' + DELIM: '🥈',
    DELIM + r'3rd_place_medal' + DELIM: '🥉',

    #
    # Sport
    #
    DELIM + r'soccer' + DELIM: '⚽',
    DELIM + r'baseball' + DELIM: '⚾',
    DELIM + r'softball' + DELIM: '🥎',
    DELIM + r'basketball' + DELIM: '🏀',
    DELIM + r'volleyball' + DELIM: '🏐',
    DELIM + r'football' + DELIM: '🏈',
    DELIM + r'rugby_football' + DELIM: '🏉',
    DELIM + r'tennis' + DELIM: '🎾',
    DELIM + r'flying_disc' + DELIM: '🥏',
    DELIM + r'bowling' + DELIM: '🎳',
    DELIM + r'cricket_game' + DELIM: '🏏',
    DELIM + r'field_hockey' + DELIM: '🏑',
    DELIM + r'ice_hockey' + DELIM: '🏒',
    DELIM + r'lacrosse' + DELIM: '🥍',
    DELIM + r'ping_pong' + DELIM: '🏓',
    DELIM + r'badminton' + DELIM: '🏸',
    DELIM + r'boxing_glove' + DELIM: '🥊',
    DELIM + r'martial_arts_uniform' + DELIM: '🥋',
    DELIM + r'goal_net' + DELIM: '🥅',
    DELIM + r'golf' + DELIM: '⛳',
    DELIM + r'ice_skate' + DELIM: '⛸️',
    DELIM + r'fishing_pole_and_fish' + DELIM: '🎣',
    DELIM + r'diving_mask' + DELIM: '🤿',
    DELIM + r'running_shirt_with_sash' + DELIM: '🎽',
    DELIM + r'ski' + DELIM: '🎿',
    DELIM + r'sled' + DELIM: '🛷',
    DELIM + r'curling_stone' + DELIM: '🥌',

    #
    # Game
    #
    DELIM + r'dart' + DELIM: '🎯',
    DELIM + r'yo_yo' + DELIM: '🪀',
    DELIM + r'kite' + DELIM: '🪁',
    DELIM + r'gun' + DELIM: '🔫',
    DELIM + r'8ball' + DELIM: '🎱',
    DELIM + r'crystal_ball' + DELIM: '🔮',
    DELIM + r'magic_wand' + DELIM: '🪄',
    DELIM + r'video_game' + DELIM: '🎮',
    DELIM + r'joystick' + DELIM: '🕹️',
    DELIM + r'slot_machine' + DELIM: '🎰',
    DELIM + r'game_die' + DELIM: '🎲',
    DELIM + r'jigsaw' + DELIM: '🧩',
    DELIM + r'teddy_bear' + DELIM: '🧸',
    DELIM + r'pinata' + DELIM: '🪅',
    DELIM + r'nesting_dolls' + DELIM: '🪆',
    DELIM + r'spades' + DELIM: '♠️',
    DELIM + r'hearts' + DELIM: '♥️',
    DELIM + r'diamonds' + DELIM: '♦️',
    DELIM + r'clubs' + DELIM: '♣️',
    DELIM + r'chess_pawn' + DELIM: '♟️',
    DELIM + r'black_joker' + DELIM: '🃏',
    DELIM + r'mahjong' + DELIM: '🀄',
    DELIM + r'flower_playing_cards' + DELIM: '🎴',

    #
    # Arts & Crafts
    #
    DELIM + r'performing_arts' + DELIM: '🎭',
    DELIM + r'framed_picture' + DELIM: '🖼️',
    DELIM + r'art' + DELIM: '🎨',
    DELIM + r'thread' + DELIM: '🧵',
    DELIM + r'sewing_needle' + DELIM: '🪡',
    DELIM + r'yarn' + DELIM: '🧶',
    DELIM + r'knot' + DELIM: '🪢',

    #
    # Clothing
    #
    DELIM + r'eyeglasses' + DELIM: '👓',
    DELIM + r'dark_sunglasses' + DELIM: '🕶️',
    DELIM + r'goggles' + DELIM: '🥽',
    DELIM + r'lab_coat' + DELIM: '🥼',
    DELIM + r'safety_vest' + DELIM: '🦺',
    DELIM + r'necktie' + DELIM: '👔',
    DELIM + r't?shirt' + DELIM: '👕',
    DELIM + r'jeans' + DELIM: '👖',
    DELIM + r'scarf' + DELIM: '🧣',
    DELIM + r'gloves' + DELIM: '🧤',
    DELIM + r'coat' + DELIM: '🧥',
    DELIM + r'socks' + DELIM: '🧦',
    DELIM + r'dress' + DELIM: '👗',
    DELIM + r'kimono' + DELIM: '👘',
    DELIM + r'sari' + DELIM: '🥻',
    DELIM + r'one_piece_swimsuit' + DELIM: '🩱',
    DELIM + r'swim_brief' + DELIM: '🩲',
    DELIM + r'shorts' + DELIM: '🩳',
    DELIM + r'bikini' + DELIM: '👙',
    DELIM + r'womans_clothes' + DELIM: '👚',
    DELIM + r'purse' + DELIM: '👛',
    DELIM + r'handbag' + DELIM: '👜',
    DELIM + r'pouch' + DELIM: '👝',
    DELIM + r'shopping' + DELIM: '🛍️',
    DELIM + r'school_satchel' + DELIM: '🎒',
    DELIM + r'thong_sandal' + DELIM: '🩴',
    DELIM + r'(mans_)?shoe' + DELIM: '👞',
    DELIM + r'athletic_shoe' + DELIM: '👟',
    DELIM + r'hiking_boot' + DELIM: '🥾',
    DELIM + r'flat_shoe' + DELIM: '🥿',
    DELIM + r'high_heel' + DELIM: '👠',
    DELIM + r'sandal' + DELIM: '👡',
    DELIM + r'ballet_shoes' + DELIM: '🩰',
    DELIM + r'boot' + DELIM: '👢',
    DELIM + r'crown' + DELIM: '👑',
    DELIM + r'womans_hat' + DELIM: '👒',
    DELIM + r'tophat' + DELIM: '🎩',
    DELIM + r'mortar_board' + DELIM: '🎓',
    DELIM + r'billed_cap' + DELIM: '🧢',
    DELIM + r'military_helmet' + DELIM: '🪖',
    DELIM + r'rescue_worker_helmet' + DELIM: '⛑️',
    DELIM + r'prayer_beads' + DELIM: '📿',
    DELIM + r'lipstick' + DELIM: '💄',
    DELIM + r'ring' + DELIM: '💍',
    DELIM + r'gem' + DELIM: '💎',

    #
    # Sound
    #
    DELIM + r'mute' + DELIM: '🔇',
    DELIM + r'speaker' + DELIM: '🔈',
    DELIM + r'sound' + DELIM: '🔉',
    DELIM + r'loud_sound' + DELIM: '🔊',
    DELIM + r'loudspeaker' + DELIM: '📢',
    DELIM + r'mega' + DELIM: '📣',
    DELIM + r'postal_horn' + DELIM: '📯',
    DELIM + r'bell' + DELIM: '🔔',
    DELIM + r'no_bell' + DELIM: '🔕',

    #
    # Music
    #
    DELIM + r'musical_score' + DELIM: '🎼',
    DELIM + r'musical_note' + DELIM: '🎵',
    DELIM + r'notes' + DELIM: '🎶',
    DELIM + r'studio_microphone' + DELIM: '🎙️',
    DELIM + r'level_slider' + DELIM: '🎚️',
    DELIM + r'control_knobs' + DELIM: '🎛️',
    DELIM + r'microphone' + DELIM: '🎤',
    DELIM + r'headphones' + DELIM: '🎧',
    DELIM + r'radio' + DELIM: '📻',

    #
    # Musical Instrument
    #
    DELIM + r'saxophone' + DELIM: '🎷',
    DELIM + r'accordion' + DELIM: '🪗',
    DELIM + r'guitar' + DELIM: '🎸',
    DELIM + r'musical_keyboard' + DELIM: '🎹',
    DELIM + r'trumpet' + DELIM: '🎺',
    DELIM + r'violin' + DELIM: '🎻',
    DELIM + r'banjo' + DELIM: '🪕',
    DELIM + r'drum' + DELIM: '🥁',
    DELIM + r'long_drum' + DELIM: '🪘',

    #
    # Phone
    #
    DELIM + r'iphone' + DELIM: '📱',
    DELIM + r'calling' + DELIM: '📲',
    DELIM + r'phone' + DELIM: '☎️',
    DELIM + r'telephone(_receiver)?' + DELIM: '📞',
    DELIM + r'pager' + DELIM: '📟',
    DELIM + r'fax' + DELIM: '📠',

    #
    # Computer
    #
    DELIM + r'battery' + DELIM: '🔋',
    DELIM + r'electric_plug' + DELIM: '🔌',
    DELIM + r'computer' + DELIM: '💻',
    DELIM + r'desktop_computer' + DELIM: '🖥️',
    DELIM + r'printer' + DELIM: '🖨️',
    DELIM + r'keyboard' + DELIM: '⌨️',
    DELIM + r'computer_mouse' + DELIM: '🖱️',
    DELIM + r'trackball' + DELIM: '🖲️',
    DELIM + r'minidisc' + DELIM: '💽',
    DELIM + r'floppy_disk' + DELIM: '💾',
    DELIM + r'cd' + DELIM: '💿',
    DELIM + r'dvd' + DELIM: '📀',
    DELIM + r'abacus' + DELIM: '🧮',

    #
    # Light & Video
    #
    DELIM + r'movie_camera' + DELIM: '🎥',
    DELIM + r'film_strip' + DELIM: '🎞️',
    DELIM + r'film_projector' + DELIM: '📽️',
    DELIM + r'clapper' + DELIM: '🎬',
    DELIM + r'tv' + DELIM: '📺',
    DELIM + r'camera' + DELIM: '📷',
    DELIM + r'camera_flash' + DELIM: '📸',
    DELIM + r'video_camera' + DELIM: '📹',
    DELIM + r'vhs' + DELIM: '📼',
    DELIM + r'mag' + DELIM: '🔍',
    DELIM + r'mag_right' + DELIM: '🔎',
    DELIM + r'candle' + DELIM: '🕯️',
    DELIM + r'bulb' + DELIM: '💡',
    DELIM + r'flashlight' + DELIM: '🔦',
    DELIM + r'(izakaya_)?lantern' + DELIM: '🏮',
    DELIM + r'diya_lamp' + DELIM: '🪔',

    #
    # Book Paper
    #
    DELIM + r'notebook_with_decorative_cover' + DELIM: '📔',
    DELIM + r'closed_book' + DELIM: '📕',
    DELIM + r'(open_)?book' + DELIM: '📖',
    DELIM + r'green_book' + DELIM: '📗',
    DELIM + r'blue_book' + DELIM: '📘',
    DELIM + r'orange_book' + DELIM: '📙',
    DELIM + r'books' + DELIM: '📚',
    DELIM + r'notebook' + DELIM: '📓',
    DELIM + r'ledger' + DELIM: '📒',
    DELIM + r'page_with_curl' + DELIM: '📃',
    DELIM + r'scroll' + DELIM: '📜',
    DELIM + r'page_facing_up' + DELIM: '📄',
    DELIM + r'newspaper' + DELIM: '📰',
    DELIM + r'newspaper_roll' + DELIM: '🗞️',
    DELIM + r'bookmark_tabs' + DELIM: '📑',
    DELIM + r'bookmark' + DELIM: '🔖',
    DELIM + r'label' + DELIM: '🏷️',

    #
    # Money
    #
    DELIM + r'moneybag' + DELIM: '💰',
    DELIM + r'coin' + DELIM: '🪙',
    DELIM + r'yen' + DELIM: '💴',
    DELIM + r'dollar' + DELIM: '💵',
    DELIM + r'euro' + DELIM: '💶',
    DELIM + r'pound' + DELIM: '💷',
    DELIM + r'money_with_wings' + DELIM: '💸',
    DELIM + r'credit_card' + DELIM: '💳',
    DELIM + r'receipt' + DELIM: '🧾',
    DELIM + r'chart' + DELIM: '💹',

    #
    # Mail
    #
    DELIM + r'envelope' + DELIM: '✉️',
    DELIM + r'e-?mail' + DELIM: '📧',
    DELIM + r'incoming_envelope' + DELIM: '📨',
    DELIM + r'envelope_with_arrow' + DELIM: '📩',
    DELIM + r'outbox_tray' + DELIM: '📤',
    DELIM + r'inbox_tray' + DELIM: '📥',
    DELIM + r'package' + DELIM: '📦',
    DELIM + r'mailbox' + DELIM: '📫',
    DELIM + r'mailbox_closed' + DELIM: '📪',
    DELIM + r'mailbox_with_mail' + DELIM: '📬',
    DELIM + r'mailbox_with_no_mail' + DELIM: '📭',
    DELIM + r'postbox' + DELIM: '📮',
    DELIM + r'ballot_box' + DELIM: '🗳️',

    #
    # Writing
    #
    DELIM + r'pencil2' + DELIM: '✏️',
    DELIM + r'black_nib' + DELIM: '✒️',
    DELIM + r'fountain_pen' + DELIM: '🖋️',
    DELIM + r'pen' + DELIM: '🖊️',
    DELIM + r'paintbrush' + DELIM: '🖌️',
    DELIM + r'crayon' + DELIM: '🖍️',
    DELIM + r'(memo|pencil)' + DELIM: '📝',

    #
    # Office
    #
    DELIM + r'briefcase' + DELIM: '💼',
    DELIM + r'file_folder' + DELIM: '📁',
    DELIM + r'open_file_folder' + DELIM: '📂',
    DELIM + r'card_index_dividers' + DELIM: '🗂️',
    DELIM + r'date' + DELIM: '📅',
    DELIM + r'calendar' + DELIM: '📆',
    DELIM + r'spiral_notepad' + DELIM: '🗒️',
    DELIM + r'spiral_calendar' + DELIM: '🗓️',
    DELIM + r'card_index' + DELIM: '📇',
    DELIM + r'chart_with_upwards_trend' + DELIM: '📈',
    DELIM + r'chart_with_downwards_trend' + DELIM: '📉',
    DELIM + r'bar_chart' + DELIM: '📊',
    DELIM + r'clipboard' + DELIM: '📋',
    DELIM + r'pushpin' + DELIM: '📌',
    DELIM + r'round_pushpin' + DELIM: '📍',
    DELIM + r'paperclip' + DELIM: '📎',
    DELIM + r'paperclips' + DELIM: '🖇️',
    DELIM + r'straight_ruler' + DELIM: '📏',
    DELIM + r'triangular_ruler' + DELIM: '📐',
    DELIM + r'scissors' + DELIM: '✂️',
    DELIM + r'card_file_box' + DELIM: '🗃️',
    DELIM + r'file_cabinet' + DELIM: '🗄️',
    DELIM + r'wastebasket' + DELIM: '🗑️',

    #
    # Lock
    #
    DELIM + r'lock' + DELIM: '🔒',
    DELIM + r'unlock' + DELIM: '🔓',
    DELIM + r'lock_with_ink_pen' + DELIM: '🔏',
    DELIM + r'closed_lock_with_key' + DELIM: '🔐',
    DELIM + r'key' + DELIM: '🔑',
    DELIM + r'old_key' + DELIM: '🗝️',

    #
    # Tool
    #
    DELIM + r'hammer' + DELIM: '🔨',
    DELIM + r'axe' + DELIM: '🪓',
    DELIM + r'pick' + DELIM: '⛏️',
    DELIM + r'hammer_and_pick' + DELIM: '⚒️',
    DELIM + r'hammer_and_wrench' + DELIM: '🛠️',
    DELIM + r'dagger' + DELIM: '🗡️',
    DELIM + r'crossed_swords' + DELIM: '⚔️',
    DELIM + r'bomb' + DELIM: '💣',
    DELIM + r'boomerang' + DELIM: '🪃',
    DELIM + r'bow_and_arrow' + DELIM: '🏹',
    DELIM + r'shield' + DELIM: '🛡️',
    DELIM + r'carpentry_saw' + DELIM: '🪚',
    DELIM + r'wrench' + DELIM: '🔧',
    DELIM + r'screwdriver' + DELIM: '🪛',
    DELIM + r'nut_and_bolt' + DELIM: '🔩',
    DELIM + r'gear' + DELIM: '⚙️',
    DELIM + r'clamp' + DELIM: '🗜️',
    DELIM + r'balance_scale' + DELIM: '⚖️',
    DELIM + r'probing_cane' + DELIM: '🦯',
    DELIM + r'link' + DELIM: '🔗',
    DELIM + r'chains' + DELIM: '⛓️',
    DELIM + r'hook' + DELIM: '🪝',
    DELIM + r'toolbox' + DELIM: '🧰',
    DELIM + r'magnet' + DELIM: '🧲',
    DELIM + r'ladder' + DELIM: '🪜',

    #
    # Science
    #
    DELIM + r'alembic' + DELIM: '⚗️',
    DELIM + r'test_tube' + DELIM: '🧪',
    DELIM + r'petri_dish' + DELIM: '🧫',
    DELIM + r'dna' + DELIM: '🧬',
    DELIM + r'microscope' + DELIM: '🔬',
    DELIM + r'telescope' + DELIM: '🔭',
    DELIM + r'satellite' + DELIM: '📡',

    #
    # Medical
    #
    DELIM + r'syringe' + DELIM: '💉',
    DELIM + r'drop_of_blood' + DELIM: '🩸',
    DELIM + r'pill' + DELIM: '💊',
    DELIM + r'adhesive_bandage' + DELIM: '🩹',
    DELIM + r'stethoscope' + DELIM: '🩺',

    #
    # Household
    #
    DELIM + r'door' + DELIM: '🚪',
    DELIM + r'elevator' + DELIM: '🛗',
    DELIM + r'mirror' + DELIM: '🪞',
    DELIM + r'window' + DELIM: '🪟',
    DELIM + r'bed' + DELIM: '🛏️',
    DELIM + r'couch_and_lamp' + DELIM: '🛋️',
    DELIM + r'chair' + DELIM: '🪑',
    DELIM + r'toilet' + DELIM: '🚽',
    DELIM + r'plunger' + DELIM: '🪠',
    DELIM + r'shower' + DELIM: '🚿',
    DELIM + r'bathtub' + DELIM: '🛁',
    DELIM + r'mouse_trap' + DELIM: '🪤',
    DELIM + r'razor' + DELIM: '🪒',
    DELIM + r'lotion_bottle' + DELIM: '🧴',
    DELIM + r'safety_pin' + DELIM: '🧷',
    DELIM + r'broom' + DELIM: '🧹',
    DELIM + r'basket' + DELIM: '🧺',
    DELIM + r'roll_of_paper' + DELIM: '🧻',
    DELIM + r'bucket' + DELIM: '🪣',
    DELIM + r'soap' + DELIM: '🧼',
    DELIM + r'toothbrush' + DELIM: '🪥',
    DELIM + r'sponge' + DELIM: '🧽',
    DELIM + r'fire_extinguisher' + DELIM: '🧯',
    DELIM + r'shopping_cart' + DELIM: '🛒',

    #
    # Other Object
    #
    DELIM + r'smoking' + DELIM: '🚬',
    DELIM + r'coffin' + DELIM: '⚰️',
    DELIM + r'headstone' + DELIM: '🪦',
    DELIM + r'funeral_urn' + DELIM: '⚱️',
    DELIM + r'nazar_amulet' + DELIM: '🧿',
    DELIM + r'moyai' + DELIM: '🗿',
    DELIM + r'placard' + DELIM: '🪧',

    #
    # Transport Sign
    #
    DELIM + r'atm' + DELIM: '🏧',
    DELIM + r'put_litter_in_its_place' + DELIM: '🚮',
    DELIM + r'potable_water' + DELIM: '🚰',
    DELIM + r'wheelchair' + DELIM: '♿',
    DELIM + r'mens' + DELIM: '🚹',
    DELIM + r'womens' + DELIM: '🚺',
    DELIM + r'restroom' + DELIM: '🚻',
    DELIM + r'baby_symbol' + DELIM: '🚼',
    DELIM + r'wc' + DELIM: '🚾',
    DELIM + r'passport_control' + DELIM: '🛂',
    DELIM + r'customs' + DELIM: '🛃',
    DELIM + r'baggage_claim' + DELIM: '🛄',
    DELIM + r'left_luggage' + DELIM: '🛅',

    #
    # Warning
    #
    DELIM + r'warning' + DELIM: '⚠️',
    DELIM + r'children_crossing' + DELIM: '🚸',
    DELIM + r'no_entry' + DELIM: '⛔',
    DELIM + r'no_entry_sign' + DELIM: '🚫',
    DELIM + r'no_bicycles' + DELIM: '🚳',
    DELIM + r'no_smoking' + DELIM: '🚭',
    DELIM + r'do_not_litter' + DELIM: '🚯',
    DELIM + r'non-potable_water' + DELIM: '🚱',
    DELIM + r'no_pedestrians' + DELIM: '🚷',
    DELIM + r'no_mobile_phones' + DELIM: '📵',
    DELIM + r'underage' + DELIM: '🔞',
    DELIM + r'radioactive' + DELIM: '☢️',
    DELIM + r'biohazard' + DELIM: '☣️',

    #
    # Arrow
    #
    DELIM + r'arrow_up' + DELIM: '⬆️',
    DELIM + r'arrow_upper_right' + DELIM: '↗️',
    DELIM + r'arrow_right' + DELIM: '➡️',
    DELIM + r'arrow_lower_right' + DELIM: '↘️',
    DELIM + r'arrow_down' + DELIM: '⬇️',
    DELIM + r'arrow_lower_left' + DELIM: '↙️',
    DELIM + r'arrow_left' + DELIM: '⬅️',
    DELIM + r'arrow_upper_left' + DELIM: '↖️',
    DELIM + r'arrow_up_down' + DELIM: '↕️',
    DELIM + r'left_right_arrow' + DELIM: '↔️',
    DELIM + r'leftwards_arrow_with_hook' + DELIM: '↩️',
    DELIM + r'arrow_right_hook' + DELIM: '↪️',
    DELIM + r'arrow_heading_up' + DELIM: '⤴️',
    DELIM + r'arrow_heading_down' + DELIM: '⤵️',
    DELIM + r'arrows_clockwise' + DELIM: '🔃',
    DELIM + r'arrows_counterclockwise' + DELIM: '🔄',
    DELIM + r'back' + DELIM: '🔙',
    DELIM + r'end' + DELIM: '🔚',
    DELIM + r'on' + DELIM: '🔛',
    DELIM + r'soon' + DELIM: '🔜',
    DELIM + r'top' + DELIM: '🔝',

    #
    # Religion
    #
    DELIM + r'place_of_worship' + DELIM: '🛐',
    DELIM + r'atom_symbol' + DELIM: '⚛️',
    DELIM + r'om' + DELIM: '🕉️',
    DELIM + r'star_of_david' + DELIM: '✡️',
    DELIM + r'wheel_of_dharma' + DELIM: '☸️',
    DELIM + r'yin_yang' + DELIM: '☯️',
    DELIM + r'latin_cross' + DELIM: '✝️',
    DELIM + r'orthodox_cross' + DELIM: '☦️',
    DELIM + r'star_and_crescent' + DELIM: '☪️',
    DELIM + r'peace_symbol' + DELIM: '☮️',
    DELIM + r'menorah' + DELIM: '🕎',
    DELIM + r'six_pointed_star' + DELIM: '🔯',

    #
    # Zodiac
    #
    DELIM + r'aries' + DELIM: '♈',
    DELIM + r'taurus' + DELIM: '♉',
    DELIM + r'gemini' + DELIM: '♊',
    DELIM + r'cancer' + DELIM: '♋',
    DELIM + r'leo' + DELIM: '♌',
    DELIM + r'virgo' + DELIM: '♍',
    DELIM + r'libra' + DELIM: '♎',
    DELIM + r'scorpius' + DELIM: '♏',
    DELIM + r'sagittarius' + DELIM: '♐',
    DELIM + r'capricorn' + DELIM: '♑',
    DELIM + r'aquarius' + DELIM: '♒',
    DELIM + r'pisces' + DELIM: '♓',
    DELIM + r'ophiuchus' + DELIM: '⛎',

    #
    # Av Symbol
    #
    DELIM + r'twisted_rightwards_arrows' + DELIM: '🔀',
    DELIM + r'repeat' + DELIM: '🔁',
    DELIM + r'repeat_one' + DELIM: '🔂',
    DELIM + r'arrow_forward' + DELIM: '▶️',
    DELIM + r'fast_forward' + DELIM: '⏩',
    DELIM + r'next_track_button' + DELIM: '⏭️',
    DELIM + r'play_or_pause_button' + DELIM: '⏯️',
    DELIM + r'arrow_backward' + DELIM: '◀️',
    DELIM + r'rewind' + DELIM: '⏪',
    DELIM + r'previous_track_button' + DELIM: '⏮️',
    DELIM + r'arrow_up_small' + DELIM: '🔼',
    DELIM + r'arrow_double_up' + DELIM: '⏫',
    DELIM + r'arrow_down_small' + DELIM: '🔽',
    DELIM + r'arrow_double_down' + DELIM: '⏬',
    DELIM + r'pause_button' + DELIM: '⏸️',
    DELIM + r'stop_button' + DELIM: '⏹️',
    DELIM + r'record_button' + DELIM: '⏺️',
    DELIM + r'eject_button' + DELIM: '⏏️',
    DELIM + r'cinema' + DELIM: '🎦',
    DELIM + r'low_brightness' + DELIM: '🔅',
    DELIM + r'high_brightness' + DELIM: '🔆',
    DELIM + r'signal_strength' + DELIM: '📶',
    DELIM + r'vibration_mode' + DELIM: '📳',
    DELIM + r'mobile_phone_off' + DELIM: '📴',

    #
    # Gender
    #
    DELIM + r'female_sign' + DELIM: '♀️',
    DELIM + r'male_sign' + DELIM: '♂️',
    DELIM + r'transgender_symbol' + DELIM: '⚧️',

    #
    # Math
    #
    DELIM + r'heavy_multiplication_x' + DELIM: '✖️',
    DELIM + r'heavy_plus_sign' + DELIM: '➕',
    DELIM + r'heavy_minus_sign' + DELIM: '➖',
    DELIM + r'heavy_division_sign' + DELIM: '➗',
    DELIM + r'infinity' + DELIM: '♾️',

    #
    # Punctuation
    #
    DELIM + r'bangbang' + DELIM: '‼️',
    DELIM + r'interrobang' + DELIM: '⁉️',
    DELIM + r'question' + DELIM: '❓',
    DELIM + r'grey_question' + DELIM: '❔',
    DELIM + r'grey_exclamation' + DELIM: '❕',
    DELIM + r'(heavy_exclamation_mark|exclamation)' + DELIM: '❗',
    DELIM + r'wavy_dash' + DELIM: '〰️',

    #
    # Currency
    #
    DELIM + r'currency_exchange' + DELIM: '💱',
    DELIM + r'heavy_dollar_sign' + DELIM: '💲',

    #
    # Other Symbol
    #
    DELIM + r'medical_symbol' + DELIM: '⚕️',
    DELIM + r'recycle' + DELIM: '♻️',
    DELIM + r'fleur_de_lis' + DELIM: '⚜️',
    DELIM + r'trident' + DELIM: '🔱',
    DELIM + r'name_badge' + DELIM: '📛',
    DELIM + r'beginner' + DELIM: '🔰',
    DELIM + r'o' + DELIM: '⭕',
    DELIM + r'white_check_mark' + DELIM: '✅',
    DELIM + r'ballot_box_with_check' + DELIM: '☑️',
    DELIM + r'heavy_check_mark' + DELIM: '✔️',
    DELIM + r'x' + DELIM: '❌',
    DELIM + r'negative_squared_cross_mark' + DELIM: '❎',
    DELIM + r'curly_loop' + DELIM: '➰',
    DELIM + r'loop' + DELIM: '➿',
    DELIM + r'part_alternation_mark' + DELIM: '〽️',
    DELIM + r'eight_spoked_asterisk' + DELIM: '✳️',
    DELIM + r'eight_pointed_black_star' + DELIM: '✴️',
    DELIM + r'sparkle' + DELIM: '❇️',
    DELIM + r'copyright' + DELIM: '©️',
    DELIM + r'registered' + DELIM: '®️',
    DELIM + r'tm' + DELIM: '™️',

    #
    # Keycap
    #
    DELIM + r'hash' + DELIM: '#️⃣',
    DELIM + r'asterisk' + DELIM: '*️⃣',
    DELIM + r'zero' + DELIM: '0️⃣',
    DELIM + r'one' + DELIM: '1️⃣',
    DELIM + r'two' + DELIM: '2️⃣',
    DELIM + r'three' + DELIM: '3️⃣',
    DELIM + r'four' + DELIM: '4️⃣',
    DELIM + r'five' + DELIM: '5️⃣',
    DELIM + r'six' + DELIM: '6️⃣',
    DELIM + r'seven' + DELIM: '7️⃣',
    DELIM + r'eight' + DELIM: '8️⃣',
    DELIM + r'nine' + DELIM: '9️⃣',
    DELIM + r'keycap_ten' + DELIM: '🔟',

    #
    # Alphanum
    #
    DELIM + r'capital_abcd' + DELIM: '🔠',
    DELIM + r'abcd' + DELIM: '🔡',
    DELIM + r'1234' + DELIM: '🔢',
    DELIM + r'symbols' + DELIM: '🔣',
    DELIM + r'abc' + DELIM: '🔤',
    DELIM + r'a' + DELIM: '🅰️',
    DELIM + r'ab' + DELIM: '🆎',
    DELIM + r'b' + DELIM: '🅱️',
    DELIM + r'cl' + DELIM: '🆑',
    DELIM + r'cool' + DELIM: '🆒',
    DELIM + r'free' + DELIM: '🆓',
    DELIM + r'information_source' + DELIM: 'ℹ️',
    DELIM + r'id' + DELIM: '🆔',
    DELIM + r'm' + DELIM: 'Ⓜ️',
    DELIM + r'new' + DELIM: '🆕',
    DELIM + r'ng' + DELIM: '🆖',
    DELIM + r'o2' + DELIM: '🅾️',
    DELIM + r'ok' + DELIM: '🆗',
    DELIM + r'parking' + DELIM: '🅿️',
    DELIM + r'sos' + DELIM: '🆘',
    DELIM + r'up' + DELIM: '🆙',
    DELIM + r'vs' + DELIM: '🆚',
    DELIM + r'koko' + DELIM: '🈁',
    DELIM + r'sa' + DELIM: '🈂️',
    DELIM + r'u6708' + DELIM: '🈷️',
    DELIM + r'u6709' + DELIM: '🈶',
    DELIM + r'u6307' + DELIM: '🈯',
    DELIM + r'ideograph_advantage' + DELIM: '🉐',
    DELIM + r'u5272' + DELIM: '🈹',
    DELIM + r'u7121' + DELIM: '🈚',
    DELIM + r'u7981' + DELIM: '🈲',
    DELIM + r'accept' + DELIM: '🉑',
    DELIM + r'u7533' + DELIM: '🈸',
    DELIM + r'u5408' + DELIM: '🈴',
    DELIM + r'u7a7a' + DELIM: '🈳',
    DELIM + r'congratulations' + DELIM: '㊗️',
    DELIM + r'secret' + DELIM: '㊙️',
    DELIM + r'u55b6' + DELIM: '🈺',
    DELIM + r'u6e80' + DELIM: '🈵',

    #
    # Geometric
    #
    DELIM + r'red_circle' + DELIM: '🔴',
    DELIM + r'orange_circle' + DELIM: '🟠',
    DELIM + r'yellow_circle' + DELIM: '🟡',
    DELIM + r'green_circle' + DELIM: '🟢',
    DELIM + r'large_blue_circle' + DELIM: '🔵',
    DELIM + r'purple_circle' + DELIM: '🟣',
    DELIM + r'brown_circle' + DELIM: '🟤',
    DELIM + r'black_circle' + DELIM: '⚫',
    DELIM + r'white_circle' + DELIM: '⚪',
    DELIM + r'red_square' + DELIM: '🟥',
    DELIM + r'orange_square' + DELIM: '🟧',
    DELIM + r'yellow_square' + DELIM: '🟨',
    DELIM + r'green_square' + DELIM: '🟩',
    DELIM + r'blue_square' + DELIM: '🟦',
    DELIM + r'purple_square' + DELIM: '🟪',
    DELIM + r'brown_square' + DELIM: '🟫',
    DELIM + r'black_large_square' + DELIM: '⬛',
    DELIM + r'white_large_square' + DELIM: '⬜',
    DELIM + r'black_medium_square' + DELIM: '◼️',
    DELIM + r'white_medium_square' + DELIM: '◻️',
    DELIM + r'black_medium_small_square' + DELIM: '◾',
    DELIM + r'white_medium_small_square' + DELIM: '◽',
    DELIM + r'black_small_square' + DELIM: '▪️',
    DELIM + r'white_small_square' + DELIM: '▫️',
    DELIM + r'large_orange_diamond' + DELIM: '🔶',
    DELIM + r'large_blue_diamond' + DELIM: '🔷',
    DELIM + r'small_orange_diamond' + DELIM: '🔸',
    DELIM + r'small_blue_diamond' + DELIM: '🔹',
    DELIM + r'small_red_triangle' + DELIM: '🔺',
    DELIM + r'small_red_triangle_down' + DELIM: '🔻',
    DELIM + r'diamond_shape_with_a_dot_inside' + DELIM: '💠',
    DELIM + r'radio_button' + DELIM: '🔘',
    DELIM + r'white_square_button' + DELIM: '🔳',
    DELIM + r'black_square_button' + DELIM: '🔲',

    #
    # Flag
    #
    DELIM + r'checkered_flag' + DELIM: '🏁',
    DELIM + r'triangular_flag_on_post' + DELIM: '🚩',
    DELIM + r'crossed_flags' + DELIM: '🎌',
    DELIM + r'black_flag' + DELIM: '🏴',
    DELIM + r'white_flag' + DELIM: '🏳️',
    DELIM + r'rainbow_flag' + DELIM: '🏳️‍🌈',
    DELIM + r'transgender_flag' + DELIM: '🏳️‍⚧️',
    DELIM + r'pirate_flag' + DELIM: '🏴‍☠️',

    #
    # Country Flag
    #
    DELIM + r'ascension_island' + DELIM: '🇦🇨',
    DELIM + r'andorra' + DELIM: '🇦🇩',
    DELIM + r'united_arab_emirates' + DELIM: '🇦🇪',
    DELIM + r'afghanistan' + DELIM: '🇦🇫',
    DELIM + r'antigua_barbuda' + DELIM: '🇦🇬',
    DELIM + r'anguilla' + DELIM: '🇦🇮',
    DELIM + r'albania' + DELIM: '🇦🇱',
    DELIM + r'armenia' + DELIM: '🇦🇲',
    DELIM + r'angola' + DELIM: '🇦🇴',
    DELIM + r'antarctica' + DELIM: '🇦🇶',
    DELIM + r'argentina' + DELIM: '🇦🇷',
    DELIM + r'american_samoa' + DELIM: '🇦🇸',
    DELIM + r'austria' + DELIM: '🇦🇹',
    DELIM + r'australia' + DELIM: '🇦🇺',
    DELIM + r'aruba' + DELIM: '🇦🇼',
    DELIM + r'aland_islands' + DELIM: '🇦🇽',
    DELIM + r'azerbaijan' + DELIM: '🇦🇿',
    DELIM + r'bosnia_herzegovina' + DELIM: '🇧🇦',
    DELIM + r'barbados' + DELIM: '🇧🇧',
    DELIM + r'bangladesh' + DELIM: '🇧🇩',
    DELIM + r'belgium' + DELIM: '🇧🇪',
    DELIM + r'burkina_faso' + DELIM: '🇧🇫',
    DELIM + r'bulgaria' + DELIM: '🇧🇬',
    DELIM + r'bahrain' + DELIM: '🇧🇭',
    DELIM + r'burundi' + DELIM: '🇧🇮',
    DELIM + r'benin' + DELIM: '🇧🇯',
    DELIM + r'st_barthelemy' + DELIM: '🇧🇱',
    DELIM + r'bermuda' + DELIM: '🇧🇲',
    DELIM + r'brunei' + DELIM: '🇧🇳',
    DELIM + r'bolivia' + DELIM: '🇧🇴',
    DELIM + r'caribbean_netherlands' + DELIM: '🇧🇶',
    DELIM + r'brazil' + DELIM: '🇧🇷',
    DELIM + r'bahamas' + DELIM: '🇧🇸',
    DELIM + r'bhutan' + DELIM: '🇧🇹',
    DELIM + r'bouvet_island' + DELIM: '🇧🇻',
    DELIM + r'botswana' + DELIM: '🇧🇼',
    DELIM + r'belarus' + DELIM: '🇧🇾',
    DELIM + r'belize' + DELIM: '🇧🇿',
    DELIM + r'canada' + DELIM: '🇨🇦',
    DELIM + r'cocos_islands' + DELIM: '🇨🇨',
    DELIM + r'congo_kinshasa' + DELIM: '🇨🇩',
    DELIM + r'central_african_republic' + DELIM: '🇨🇫',
    DELIM + r'congo_brazzaville' + DELIM: '🇨🇬',
    DELIM + r'switzerland' + DELIM: '🇨🇭',
    DELIM + r'cote_divoire' + DELIM: '🇨🇮',
    DELIM + r'cook_islands' + DELIM: '🇨🇰',
    DELIM + r'chile' + DELIM: '🇨🇱',
    DELIM + r'cameroon' + DELIM: '🇨🇲',
    DELIM + r'cn' + DELIM: '🇨🇳',
    DELIM + r'colombia' + DELIM: '🇨🇴',
    DELIM + r'clipperton_island' + DELIM: '🇨🇵',
    DELIM + r'costa_rica' + DELIM: '🇨🇷',
    DELIM + r'cuba' + DELIM: '🇨🇺',
    DELIM + r'cape_verde' + DELIM: '🇨🇻',
    DELIM + r'curacao' + DELIM: '🇨🇼',
    DELIM + r'christmas_island' + DELIM: '🇨🇽',
    DELIM + r'cyprus' + DELIM: '🇨🇾',
    DELIM + r'czech_republic' + DELIM: '🇨🇿',
    DELIM + r'de' + DELIM: '🇩🇪',
    DELIM + r'diego_garcia' + DELIM: '🇩🇬',
    DELIM + r'djibouti' + DELIM: '🇩🇯',
    DELIM + r'denmark' + DELIM: '🇩🇰',
    DELIM + r'dominica' + DELIM: '🇩🇲',
    DELIM + r'dominican_republic' + DELIM: '🇩🇴',
    DELIM + r'algeria' + DELIM: '🇩🇿',
    DELIM + r'ceuta_melilla' + DELIM: '🇪🇦',
    DELIM + r'ecuador' + DELIM: '🇪🇨',
    DELIM + r'estonia' + DELIM: '🇪🇪',
    DELIM + r'egypt' + DELIM: '🇪🇬',
    DELIM + r'western_sahara' + DELIM: '🇪🇭',
    DELIM + r'eritrea' + DELIM: '🇪🇷',
    DELIM + r'es' + DELIM: '🇪🇸',
    DELIM + r'ethiopia' + DELIM: '🇪🇹',
    DELIM + r'(eu|european_union)' + DELIM: '🇪🇺',
    DELIM + r'finland' + DELIM: '🇫🇮',
    DELIM + r'fiji' + DELIM: '🇫🇯',
    DELIM + r'falkland_islands' + DELIM: '🇫🇰',
    DELIM + r'micronesia' + DELIM: '🇫🇲',
    DELIM + r'faroe_islands' + DELIM: '🇫🇴',
    DELIM + r'fr' + DELIM: '🇫🇷',
    DELIM + r'gabon' + DELIM: '🇬🇦',
    DELIM + r'(uk|gb)' + DELIM: '🇬🇧',
    DELIM + r'grenada' + DELIM: '🇬🇩',
    DELIM + r'georgia' + DELIM: '🇬🇪',
    DELIM + r'french_guiana' + DELIM: '🇬🇫',
    DELIM + r'guernsey' + DELIM: '🇬🇬',
    DELIM + r'ghana' + DELIM: '🇬🇭',
    DELIM + r'gibraltar' + DELIM: '🇬🇮',
    DELIM + r'greenland' + DELIM: '🇬🇱',
    DELIM + r'gambia' + DELIM: '🇬🇲',
    DELIM + r'guinea' + DELIM: '🇬🇳',
    DELIM + r'guadeloupe' + DELIM: '🇬🇵',
    DELIM + r'equatorial_guinea' + DELIM: '🇬🇶',
    DELIM + r'greece' + DELIM: '🇬🇷',
    DELIM + r'south_georgia_south_sandwich_islands' + DELIM: '🇬🇸',
    DELIM + r'guatemala' + DELIM: '🇬🇹',
    DELIM + r'guam' + DELIM: '🇬🇺',
    DELIM + r'guinea_bissau' + DELIM: '🇬🇼',
    DELIM + r'guyana' + DELIM: '🇬🇾',
    DELIM + r'hong_kong' + DELIM: '🇭🇰',
    DELIM + r'heard_mcdonald_islands' + DELIM: '🇭🇲',
    DELIM + r'honduras' + DELIM: '🇭🇳',
    DELIM + r'croatia' + DELIM: '🇭🇷',
    DELIM + r'haiti' + DELIM: '🇭🇹',
    DELIM + r'hungary' + DELIM: '🇭🇺',
    DELIM + r'canary_islands' + DELIM: '🇮🇨',
    DELIM + r'indonesia' + DELIM: '🇮🇩',
    DELIM + r'ireland' + DELIM: '🇮🇪',
    DELIM + r'israel' + DELIM: '🇮🇱',
    DELIM + r'isle_of_man' + DELIM: '🇮🇲',
    DELIM + r'india' + DELIM: '🇮🇳',
    DELIM + r'british_indian_ocean_territory' + DELIM: '🇮🇴',
    DELIM + r'iraq' + DELIM: '🇮🇶',
    DELIM + r'iran' + DELIM: '🇮🇷',
    DELIM + r'iceland' + DELIM: '🇮🇸',
    DELIM + r'it' + DELIM: '🇮🇹',
    DELIM + r'jersey' + DELIM: '🇯🇪',
    DELIM + r'jamaica' + DELIM: '🇯🇲',
    DELIM + r'jordan' + DELIM: '🇯🇴',
    DELIM + r'jp' + DELIM: '🇯🇵',
    DELIM + r'kenya' + DELIM: '🇰🇪',
    DELIM + r'kyrgyzstan' + DELIM: '🇰🇬',
    DELIM + r'cambodia' + DELIM: '🇰🇭',
    DELIM + r'kiribati' + DELIM: '🇰🇮',
    DELIM + r'comoros' + DELIM: '🇰🇲',
    DELIM + r'st_kitts_nevis' + DELIM: '🇰🇳',
    DELIM + r'north_korea' + DELIM: '🇰🇵',
    DELIM + r'kr' + DELIM: '🇰🇷',
    DELIM + r'kuwait' + DELIM: '🇰🇼',
    DELIM + r'cayman_islands' + DELIM: '🇰🇾',
    DELIM + r'kazakhstan' + DELIM: '🇰🇿',
    DELIM + r'laos' + DELIM: '🇱🇦',
    DELIM + r'lebanon' + DELIM: '🇱🇧',
    DELIM + r'st_lucia' + DELIM: '🇱🇨',
    DELIM + r'liechtenstein' + DELIM: '🇱🇮',
    DELIM + r'sri_lanka' + DELIM: '🇱🇰',
    DELIM + r'liberia' + DELIM: '🇱🇷',
    DELIM + r'lesotho' + DELIM: '🇱🇸',
    DELIM + r'lithuania' + DELIM: '🇱🇹',
    DELIM + r'luxembourg' + DELIM: '🇱🇺',
    DELIM + r'latvia' + DELIM: '🇱🇻',
    DELIM + r'libya' + DELIM: '🇱🇾',
    DELIM + r'morocco' + DELIM: '🇲🇦',
    DELIM + r'monaco' + DELIM: '🇲🇨',
    DELIM + r'moldova' + DELIM: '🇲🇩',
    DELIM + r'montenegro' + DELIM: '🇲🇪',
    DELIM + r'st_martin' + DELIM: '🇲🇫',
    DELIM + r'madagascar' + DELIM: '🇲🇬',
    DELIM + r'marshall_islands' + DELIM: '🇲🇭',
    DELIM + r'macedonia' + DELIM: '🇲🇰',
    DELIM + r'mali' + DELIM: '🇲🇱',
    DELIM + r'myanmar' + DELIM: '🇲🇲',
    DELIM + r'mongolia' + DELIM: '🇲🇳',
    DELIM + r'macau' + DELIM: '🇲🇴',
    DELIM + r'northern_mariana_islands' + DELIM: '🇲🇵',
    DELIM + r'martinique' + DELIM: '🇲🇶',
    DELIM + r'mauritania' + DELIM: '🇲🇷',
    DELIM + r'montserrat' + DELIM: '🇲🇸',
    DELIM + r'malta' + DELIM: '🇲🇹',
    DELIM + r'mauritius' + DELIM: '🇲🇺',
    DELIM + r'maldives' + DELIM: '🇲🇻',
    DELIM + r'malawi' + DELIM: '🇲🇼',
    DELIM + r'mexico' + DELIM: '🇲🇽',
    DELIM + r'malaysia' + DELIM: '🇲🇾',
    DELIM + r'mozambique' + DELIM: '🇲🇿',
    DELIM + r'namibia' + DELIM: '🇳🇦',
    DELIM + r'new_caledonia' + DELIM: '🇳🇨',
    DELIM + r'niger' + DELIM: '🇳🇪',
    DELIM + r'norfolk_island' + DELIM: '🇳🇫',
    DELIM + r'nigeria' + DELIM: '🇳🇬',
    DELIM + r'nicaragua' + DELIM: '🇳🇮',
    DELIM + r'netherlands' + DELIM: '🇳🇱',
    DELIM + r'norway' + DELIM: '🇳🇴',
    DELIM + r'nepal' + DELIM: '🇳🇵',
    DELIM + r'nauru' + DELIM: '🇳🇷',
    DELIM + r'niue' + DELIM: '🇳🇺',
    DELIM + r'new_zealand' + DELIM: '🇳🇿',
    DELIM + r'oman' + DELIM: '🇴🇲',
    DELIM + r'panama' + DELIM: '🇵🇦',
    DELIM + r'peru' + DELIM: '🇵🇪',
    DELIM + r'french_polynesia' + DELIM: '🇵🇫',
    DELIM + r'papua_new_guinea' + DELIM: '🇵🇬',
    DELIM + r'philippines' + DELIM: '🇵🇭',
    DELIM + r'pakistan' + DELIM: '🇵🇰',
    DELIM + r'poland' + DELIM: '🇵🇱',
    DELIM + r'st_pierre_miquelon' + DELIM: '🇵🇲',
    DELIM + r'pitcairn_islands' + DELIM: '🇵🇳',
    DELIM + r'puerto_rico' + DELIM: '🇵🇷',
    DELIM + r'palestinian_territories' + DELIM: '🇵🇸',
    DELIM + r'portugal' + DELIM: '🇵🇹',
    DELIM + r'palau' + DELIM: '🇵🇼',
    DELIM + r'paraguay' + DELIM: '🇵🇾',
    DELIM + r'qatar' + DELIM: '🇶🇦',
    DELIM + r'reunion' + DELIM: '🇷🇪',
    DELIM + r'romania' + DELIM: '🇷🇴',
    DELIM + r'serbia' + DELIM: '🇷🇸',
    DELIM + r'ru' + DELIM: '🇷🇺',
    DELIM + r'rwanda' + DELIM: '🇷🇼',
    DELIM + r'saudi_arabia' + DELIM: '🇸🇦',
    DELIM + r'solomon_islands' + DELIM: '🇸🇧',
    DELIM + r'seychelles' + DELIM: '🇸🇨',
    DELIM + r'sudan' + DELIM: '🇸🇩',
    DELIM + r'sweden' + DELIM: '🇸🇪',
    DELIM + r'singapore' + DELIM: '🇸🇬',
    DELIM + r'st_helena' + DELIM: '🇸🇭',
    DELIM + r'slovenia' + DELIM: '🇸🇮',
    DELIM + r'svalbard_jan_mayen' + DELIM: '🇸🇯',
    DELIM + r'slovakia' + DELIM: '🇸🇰',
    DELIM + r'sierra_leone' + DELIM: '🇸🇱',
    DELIM + r'san_marino' + DELIM: '🇸🇲',
    DELIM + r'senegal' + DELIM: '🇸🇳',
    DELIM + r'somalia' + DELIM: '🇸🇴',
    DELIM + r'suriname' + DELIM: '🇸🇷',
    DELIM + r'south_sudan' + DELIM: '🇸🇸',
    DELIM + r'sao_tome_principe' + DELIM: '🇸🇹',
    DELIM + r'el_salvador' + DELIM: '🇸🇻',
    DELIM + r'sint_maarten' + DELIM: '🇸🇽',
    DELIM + r'syria' + DELIM: '🇸🇾',
    DELIM + r'swaziland' + DELIM: '🇸🇿',
    DELIM + r'tristan_da_cunha' + DELIM: '🇹🇦',
    DELIM + r'turks_caicos_islands' + DELIM: '🇹🇨',
    DELIM + r'chad' + DELIM: '🇹🇩',
    DELIM + r'french_southern_territories' + DELIM: '🇹🇫',
    DELIM + r'togo' + DELIM: '🇹🇬',
    DELIM + r'thailand' + DELIM: '🇹🇭',
    DELIM + r'tajikistan' + DELIM: '🇹🇯',
    DELIM + r'tokelau' + DELIM: '🇹🇰',
    DELIM + r'timor_leste' + DELIM: '🇹🇱',
    DELIM + r'turkmenistan' + DELIM: '🇹🇲',
    DELIM + r'tunisia' + DELIM: '🇹🇳',
    DELIM + r'tonga' + DELIM: '🇹🇴',
    DELIM + r'tr' + DELIM: '🇹🇷',
    DELIM + r'trinidad_tobago' + DELIM: '🇹🇹',
    DELIM + r'tuvalu' + DELIM: '🇹🇻',
    DELIM + r'taiwan' + DELIM: '🇹🇼',
    DELIM + r'tanzania' + DELIM: '🇹🇿',
    DELIM + r'ukraine' + DELIM: '🇺🇦',
    DELIM + r'uganda' + DELIM: '🇺🇬',
    DELIM + r'us_outlying_islands' + DELIM: '🇺🇲',
    DELIM + r'united_nations' + DELIM: '🇺🇳',
    DELIM + r'us' + DELIM: '🇺🇸',
    DELIM + r'uruguay' + DELIM: '🇺🇾',
    DELIM + r'uzbekistan' + DELIM: '🇺🇿',
    DELIM + r'vatican_city' + DELIM: '🇻🇦',
    DELIM + r'st_vincent_grenadines' + DELIM: '🇻🇨',
    DELIM + r'venezuela' + DELIM: '🇻🇪',
    DELIM + r'british_virgin_islands' + DELIM: '🇻🇬',
    DELIM + r'us_virgin_islands' + DELIM: '🇻🇮',
    DELIM + r'vietnam' + DELIM: '🇻🇳',
    DELIM + r'vanuatu' + DELIM: '🇻🇺',
    DELIM + r'wallis_futuna' + DELIM: '🇼🇫',
    DELIM + r'samoa' + DELIM: '🇼🇸',
    DELIM + r'kosovo' + DELIM: '🇽🇰',
    DELIM + r'yemen' + DELIM: '🇾🇪',
    DELIM + r'mayotte' + DELIM: '🇾🇹',
    DELIM + r'south_africa' + DELIM: '🇿🇦',
    DELIM + r'zambia' + DELIM: '🇿🇲',
    DELIM + r'zimbabwe' + DELIM: '🇿🇼',

    #
    # Subdivision Flag
    #
    DELIM + r'england' + DELIM: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    DELIM + r'scotland' + DELIM: '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
    DELIM + r'wales' + DELIM: '🏴󠁧󠁢󠁷󠁬󠁳󠁿',
}

# Define our singlton
EMOJI_COMPILED_MAP = None


def apply_emojis(content):
    """
    Takes the content and swaps any matched emoji's found with their
    utf-8 encoded mapping
    """

    global EMOJI_COMPILED_MAP

    if EMOJI_COMPILED_MAP is None:
        t_start = time.time()
        # Perform our compilation
        EMOJI_COMPILED_MAP = re.compile(
            r'(' + '|'.join(EMOJI_MAP.keys()) + r')',
            re.IGNORECASE)
        logger.trace(
            'Emoji engine loaded in {:.4f}s'.format((time.time() - t_start)))

    try:
        return EMOJI_COMPILED_MAP.sub(lambda x: EMOJI_MAP[x.group()], content)

    except TypeError:
        # No change; but force string return
        return ''
