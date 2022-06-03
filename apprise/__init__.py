# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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

__title__ = 'Apprise'
__version__ = '0.9.9'
__author__ = 'Chris Caron'
__license__ = 'MIT'
__copywrite__ = 'Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>'
__email__ = 'lead2gold@gmail.com'
__status__ = 'Production'

from .common import NotifyType
from .common import NOTIFY_TYPES
from .common import NotifyImageSize
from .common import NOTIFY_IMAGE_SIZES
from .common import NotifyFormat
from .common import NOTIFY_FORMATS
from .common import OverflowMode
from .common import OVERFLOW_MODES
from .common import ConfigFormat
from .common import CONFIG_FORMATS
from .common import ContentIncludeMode
from .common import CONTENT_INCLUDE_MODES
from .common import ContentLocation
from .common import CONTENT_LOCATIONS

from .URLBase import URLBase
from .URLBase import PrivacyMode
from .plugins.NotifyBase import NotifyBase
from .config.ConfigBase import ConfigBase
from .attachment.AttachBase import AttachBase

from .Apprise import Apprise
from .AppriseAsset import AppriseAsset
from .AppriseConfig import AppriseConfig
from .AppriseAttachment import AppriseAttachment

# Inherit our logging with our additional entries added to it
from .logger import logging
from .logger import logger
from .logger import LogCapture

# Set default logging handler to avoid "No handler found" warnings.
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    # Core
    'Apprise', 'AppriseAsset', 'AppriseConfig', 'AppriseAttachment', 'URLBase',
    'NotifyBase', 'ConfigBase', 'AttachBase',

    # Reference
    'NotifyType', 'NotifyImageSize', 'NotifyFormat', 'OverflowMode',
    'NOTIFY_TYPES', 'NOTIFY_IMAGE_SIZES', 'NOTIFY_FORMATS', 'OVERFLOW_MODES',
    'ConfigFormat', 'CONFIG_FORMATS',
    'ContentIncludeMode', 'CONTENT_INCLUDE_MODES',
    'ContentLocation', 'CONTENT_LOCATIONS',
    'PrivacyMode',

    # Logging
    'logging', 'logger', 'LogCapture',
]
