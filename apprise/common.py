# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
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


class NotifyType(object):
    """
    A simple mapping of notification types most commonly used with
    all types of logging and notification services.
    """
    INFO = 'info'
    SUCCESS = 'success'
    FAILURE = 'failure'
    WARNING = 'warning'


NOTIFY_TYPES = (
    NotifyType.INFO,
    NotifyType.SUCCESS,
    NotifyType.FAILURE,
    NotifyType.WARNING,
)


class NotifyImageSize(object):
    """
    A list of pre-defined image sizes to make it easier to work with defined
    plugins.
    """
    XY_32 = '32x32'
    XY_72 = '72x72'
    XY_128 = '128x128'
    XY_256 = '256x256'


NOTIFY_IMAGE_SIZES = (
    NotifyImageSize.XY_32,
    NotifyImageSize.XY_72,
    NotifyImageSize.XY_128,
    NotifyImageSize.XY_256,
)


class NotifyFormat(object):
    """
    A list of pre-defined text message formats that can be passed via the
    apprise library.
    """
    TEXT = 'text'
    HTML = 'html'
    MARKDOWN = 'markdown'


NOTIFY_FORMATS = (
    NotifyFormat.TEXT,
    NotifyFormat.HTML,
    NotifyFormat.MARKDOWN,
)


class OverflowMode(object):
    """
    A list of pre-defined modes of how to handle the text when it exceeds the
    defined maximum message size.
    """

    # Send the data as is; untouched.  Let the upstream server decide how the
    # content is handled.  Some upstream services might gracefully handle this
    # with expected intentions; others might not.
    UPSTREAM = 'upstream'

    # Always truncate the text when it exceeds the maximum message size and
    # send it anyway
    TRUNCATE = 'truncate'

    # Split the message into multiple smaller messages that fit within the
    # limits of what is expected.  The smaller messages are sent
    SPLIT = 'split'


# Define our modes so we can verify if we need to
OVERFLOW_MODES = (
    OverflowMode.UPSTREAM,
    OverflowMode.TRUNCATE,
    OverflowMode.SPLIT,
)


class ConfigFormat(object):
    """
    A list of pre-defined config formats that can be passed via the
    apprise library.
    """

    # A text based configuration. This consists of a list of URLs delimited by
    # a new line.  pound/hashtag (#) or semi-colon (;) can be used as comment
    # characters.
    TEXT = 'text'

    # YAML files allow a more rich of an experience when settig up your
    # apprise configuration files.
    YAML = 'yaml'


# Define our configuration formats mostly used for verification
CONFIG_FORMATS = (
    ConfigFormat.TEXT,
    ConfigFormat.YAML,
)
