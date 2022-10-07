# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# New priorities are defined here:
# - https://firebase.google.com/docs/reference/fcm/rest/v1/\
#       projects.messages#NotificationPriority

# Legacy color payload example here:
# https://firebase.google.com/docs/reference/fcm/rest/v1/\
#       projects.messages#androidnotification
import re
from ...utils import parse_bool
from ...common import NotifyType
from ...AppriseAsset import AppriseAsset


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
