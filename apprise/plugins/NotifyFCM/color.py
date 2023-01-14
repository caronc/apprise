# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.

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
