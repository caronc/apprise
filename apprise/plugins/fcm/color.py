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

# New priorities are defined here:
# - https://firebase.google.com/docs/reference/fcm/rest/v1/\
#       projects.messages#NotificationPriority

# Legacy color payload example here:
# https://firebase.google.com/docs/reference/fcm/rest/v1/\
#       projects.messages#androidnotification
import re
from ...utils.parse import parse_bool
from ...common import NotifyType
from ...asset import AppriseAsset


class FCMColorManager:
    """
    A Simple object to accept either a boolean value
      - True: Use colors provided by Apprise
      - False: Do not use colors at all
      - rrggbb: where you provide the rgb values (hence #333333)
      - rgb: is also accepted as rgb values (hence #333)

      For RGB colors, the hashtag is optional
    """

    __color_rgb = re.compile(
        r'#?((?P<r1>[0-9A-F]{2})(?P<g1>[0-9A-F]{2})(?P<b1>[0-9A-F]{2})'
        r'|(?P<r2>[0-9A-F])(?P<g2>[0-9A-F])(?P<b2>[0-9A-F]))', re.IGNORECASE)

    def __init__(self, color, asset=None):
        """
        Parses the color object accordingly
        """

        # Initialize an asset object if one isn't otherwise defined
        self.asset = asset \
            if isinstance(asset, AppriseAsset) else AppriseAsset()

        # Prepare our color
        self.color = color
        if isinstance(color, str):
            self.color = self.__color_rgb.match(color)
            if self.color:
                # Store our RGB value as #rrggbb
                self.color = '{red}{green}{blue}'.format(
                    red=self.color.group('r1'),
                    green=self.color.group('g1'),
                    blue=self.color.group('b1')).lower() \
                    if self.color.group('r1') else \
                    '{red1}{red2}{green1}{green2}{blue1}{blue2}'.format(
                    red1=self.color.group('r2'),
                    red2=self.color.group('r2'),
                    green1=self.color.group('g2'),
                    green2=self.color.group('g2'),
                    blue1=self.color.group('b2'),
                    blue2=self.color.group('b2')).lower()

        if self.color is None:
            # Color not determined, so base it on boolean parser
            self.color = parse_bool(color)

    def get(self, notify_type=NotifyType.INFO):
        """
        Returns color or true/false value based on configuration
        """

        if isinstance(self.color, bool) and self.color:
            # We want to use the asset value
            return self.asset.color(notify_type=notify_type)

        elif self.color:
            # return our color as is
            return '#' + self.color

        # No color to return
        return None

    def __str__(self):
        """
        our color representation
        """
        if isinstance(self.color, bool):
            return 'yes' if self.color else 'no'

        # otherwise return our color
        return self.color

    def __bool__(self):
        """
        Allows this object to be wrapped in an 'if statement'.
        True is returned if a color was loaded
        """
        return True if self.color is True or \
            isinstance(self.color, str) else False
