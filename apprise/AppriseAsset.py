# -*- coding: utf-8 -*-
#
# Apprise Asset
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

import re

from os.path import join
from os.path import dirname
from os.path import isfile
from os.path import abspath
from .common import NotifyType


class AppriseAsset(object):
    """
    Provides a supplimentary class that can be used to provide extra
    information and details that can be used by Apprise such as providing
    an alternate location to where images/icons can be found and the
    URL masks.

    """
    # A Simple Mapping of Colors; For every NOTIFY_TYPE identified,
    # there should be a mapping to it's color here:
    html_notify_map = {
        NotifyType.INFO: '#3AA3E3',
        NotifyType.SUCCESS: '#3AA337',
        NotifyType.FAILURE: '#A32037',
        NotifyType.WARNING: '#CACF29',
    }

    # The default theme
    theme = 'default'

    # Image URL Mask
    image_url_mask = \
        'http://nuxref.com/apprise/themes/{THEME}/apprise-{TYPE}-{XY}.png'

    # Image Path Mask
    image_path_mask = abspath(join(
        dirname(__file__),
        'assets',
        'themes',
        '{THEME}',
        'apprise-{TYPE}-{XY}.png',
    ))

    def __init__(self, theme='default', image_path_mask=None,
                 image_url_mask=None):
        """
        Asset Initialization

        """
        if theme:
            self.theme = theme

        if image_path_mask:
            self.image_path_mask = image_path_mask

        if image_url_mask:
            self.image_url_mask = image_url_mask

    def html_color(self, notify_type):
        """
        Returns an HTML mapped color based on passed in notify type
        """
        # Attempt to get the type, otherwise return a default grey
        # if we couldn't look up the entry
        return self.html_notify_map.get(notify_type, '#888888')

    def image_url(self, notify_type, image_size):
        """
        Apply our mask to our image URL

        """
        re_map = {
            '{THEME}': self.theme if self.theme else '',
            '{TYPE}': notify_type,
            '{XY}': image_size,
        }

        # Iterate over above list and store content accordingly
        re_table = re.compile(
            r'(' + '|'.join(re_map.keys()) + r')',
            re.IGNORECASE,
        )

        return re_table.sub(lambda x: re_map[x.group()], self.image_url_mask)

    def image_path(self, notify_type, image_size, must_exist=True):
        """
        Apply our mask to our image file path

        """
        re_map = {
            '{THEME}': self.theme if self.theme else '',
            '{TYPE}': notify_type,
            '{XY}': image_size,
        }

        # Iterate over above list and store content accordingly
        re_table = re.compile(
            r'(' + '|'.join(re_map.keys()) + r')',
            re.IGNORECASE,
        )

        # Acquire our path
        path = re_table.sub(lambda x: re_map[x.group()], self.image_path_mask)
        if must_exist and not isfile(path):
            return None

        # Return what we parsed
        return path

    def image_raw(self, notify_type, image_size):
        """
        Returns the raw image if it can (otherwise the function returns None)

        """

        path = self.image_path(notify_type=notify_type, image_size=image_size)
        if path:
            try:
                with open(path, 'rb') as fd:
                    return fd.read()

            except (OSError, IOError):
                # We can't access the file
                pass

        return None
