# -*- coding: utf-8 -*-
# BSD 3-Clause License
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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
from uuid import uuid4
from os.path import join
from os.path import dirname
from os.path import isfile
from os.path import abspath
from .common import NotifyType
from .utils import module_detection


class AppriseAsset:
    """
    Provides a supplimentary class that can be used to provide extra
    information and details that can be used by Apprise such as providing
    an alternate location to where images/icons can be found and the
    URL masks.

    Any variable that starts with an underscore (_) can only be initialized
    by this class manually and will/can not be parsed from a configuration
    file.

    """
    # Application Identifier
    app_id = 'Apprise'

    # Application Description
    app_desc = 'Apprise Notifications'

    # Provider URL
    app_url = 'https://github.com/caronc/apprise'

    # A Simple Mapping of Colors; For every NOTIFY_TYPE identified,
    # there should be a mapping to it's color here:
    html_notify_map = {
        NotifyType.INFO: '#3AA3E3',
        NotifyType.SUCCESS: '#3AA337',
        NotifyType.FAILURE: '#A32037',
        NotifyType.WARNING: '#CACF29',
    }

    # Ascii Notification
    ascii_notify_map = {
        NotifyType.INFO: '[i]',
        NotifyType.SUCCESS: '[+]',
        NotifyType.FAILURE: '[!]',
        NotifyType.WARNING: '[~]',
    }

    # The default color to return if a mapping isn't found in our table above
    default_html_color = '#888888'

    # The default image extension to use
    default_extension = '.png'

    # The default theme
    theme = 'default'

    # Image URL Mask
    image_url_mask = \
        'https://github.com/caronc/apprise/raw/master/apprise/assets/' \
        'themes/{THEME}/apprise-{TYPE}-{XY}{EXTENSION}'

    # Application Logo
    image_url_logo = \
        'https://github.com/caronc/apprise/raw/master/apprise/assets/' \
        'themes/{THEME}/apprise-logo.png'

    # Image Path Mask
    image_path_mask = abspath(join(
        dirname(__file__),
        'assets',
        'themes',
        '{THEME}',
        'apprise-{TYPE}-{XY}{EXTENSION}',
    ))

    # This value can also be set on calls to Apprise.notify(). This allows
    # you to let Apprise upfront the type of data being passed in.  This
    # must be of type NotifyFormat. Possible values could be:
    # - NotifyFormat.TEXT
    # - NotifyFormat.MARKDOWN
    # - NotifyFormat.HTML
    # - None
    #
    # If no format is specified (hence None), then no special pre-formatting
    # actions will take place during a notification. This has been and always
    # will be the default.
    body_format = None

    # Always attempt to send notifications asynchronous (as the same time
    # if possible)
    # This is a Python 3 supported option only. If set to False, then
    # notifications are sent sequentially (one after another)
    async_mode = True

    # Whether or not to interpret escapes found within the input text prior
    # to passing it upstream. Such as converting \t to an actual tab and \n
    # to a new line.
    interpret_escapes = False

    # Defines the encoding of the content passed into Apprise
    encoding = 'utf-8'

    # For more detail see CWE-312 @
    #    https://cwe.mitre.org/data/definitions/312.html
    #
    # By enabling this, the logging output has additional overhead applied to
    # it preventing secure password and secret information from being
    # displayed in the logging. Since there is overhead involved in performing
    # this cleanup; system owners who run in a very isolated environment may
    # choose to disable this for a slight performance bump. It is recommended
    # that you leave this option as is otherwise.
    secure_logging = True

    # Optionally specify one or more path to attempt to scan for Python modules
    # By default, no paths are scanned.
    __plugin_paths = []

    # All internal/system flags are prefixed with an underscore (_)
    # These can only be initialized using Python libraries and are not picked
    # up from (yaml) configuration files (if set)

    # An internal counter that is used by AppriseAPI
    # (https://github.com/caronc/apprise-api). The idea is to allow one
    # instance of AppriseAPI to call another, but to track how many times
    # this occurs. It's intent is to prevent a loop where an AppriseAPI
    # Server calls itself (or loops indefinitely)
    _recursion = 0

    # A unique identifer we can use to associate our calling source
    _uid = str(uuid4())

    def __init__(self, plugin_paths=None, **kwargs):
        """
        Asset Initialization

        """
        # Assign default arguments if specified
        for key, value in kwargs.items():
            if not hasattr(AppriseAsset, key):
                raise AttributeError(
                    'AppriseAsset init(): '
                    'An invalid key {} was specified.'.format(key))

            setattr(self, key, value)

        if plugin_paths:
            # Load any decorated modules if defined
            module_detection(plugin_paths)

    def color(self, notify_type, color_type=None):
        """
        Returns an HTML mapped color based on passed in notify type

        if color_type is:
           None    then a standard hex string is returned as
                   a string format ('#000000').

           int     then the integer representation is returned
           tuple   then the the red, green, blue is returned in a tuple

        """

        # Attempt to get the type, otherwise return a default grey
        # if we couldn't look up the entry
        color = self.html_notify_map.get(notify_type, self.default_html_color)
        if color_type is None:
            # This is the default return type
            return color

        elif color_type is int:
            # Convert the color to integer
            return AppriseAsset.hex_to_int(color)

        # The only other type is tuple
        elif color_type is tuple:
            return AppriseAsset.hex_to_rgb(color)

        # Unsupported type
        raise ValueError(
            'AppriseAsset html_color(): An invalid color_type was specified.')

    def ascii(self, notify_type):
        """
        Returns an ascii representation based on passed in notify type

        """

        # look our response up
        return self.ascii_notify_map.get(notify_type, self.default_html_color)

    def image_url(self, notify_type, image_size, logo=False, extension=None):
        """
        Apply our mask to our image URL

        if logo is set to True, then the logo_url is used instead

        """

        url_mask = self.image_url_logo if logo else self.image_url_mask
        if not url_mask:
            # No image to return
            return None

        if extension is None:
            extension = self.default_extension

        re_map = {
            '{THEME}': self.theme if self.theme else '',
            '{TYPE}': notify_type,
            '{XY}': image_size,
            '{EXTENSION}': extension,
        }

        # Iterate over above list and store content accordingly
        re_table = re.compile(
            r'(' + '|'.join(re_map.keys()) + r')',
            re.IGNORECASE,
        )

        return re_table.sub(lambda x: re_map[x.group()], url_mask)

    def image_path(self, notify_type, image_size, must_exist=True,
                   extension=None):
        """
        Apply our mask to our image file path

        """

        if not self.image_path_mask:
            # No image to return
            return None

        if extension is None:
            extension = self.default_extension

        re_map = {
            '{THEME}': self.theme if self.theme else '',
            '{TYPE}': notify_type,
            '{XY}': image_size,
            '{EXTENSION}': extension,
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

    def image_raw(self, notify_type, image_size, extension=None):
        """
        Returns the raw image if it can (otherwise the function returns None)

        """

        path = self.image_path(
            notify_type=notify_type,
            image_size=image_size,
            extension=extension,
        )
        if path:
            try:
                with open(path, 'rb') as fd:
                    return fd.read()

            except (OSError, IOError):
                # We can't access the file
                return None

        return None

    def details(self):
        """
        Returns the details associated with the AppriseAsset object

        """
        return {
            'app_id': self.app_id,
            'app_desc': self.app_desc,
            'default_extension': self.default_extension,
            'theme': self.theme,
            'image_path_mask': self.image_path_mask,
            'image_url_mask': self.image_url_mask,
            'image_url_logo': self.image_url_logo,
        }

    @staticmethod
    def hex_to_rgb(value):
        """
        Takes a hex string (such as #00ff00) and returns a tuple in the form
        of (red, green, blue)

        eg: #00ff00 becomes : (0, 65535, 0)

        """
        value = value.lstrip('#')
        lv = len(value)
        return tuple(int(value[i:i + lv // 3], 16)
                     for i in range(0, lv, lv // 3))

    @staticmethod
    def hex_to_int(value):
        """
        Takes a hex string (such as #00ff00) and returns its integer
        equivalent

        eg: #00000f becomes : 15

        """
        return int(value.lstrip('#'), 16)
