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

__title__ = 'Apprise'
__version__ = '1.2.1'
__author__ = 'Chris Caron'
__license__ = 'GPLv2'
__copywrite__ = 'Copyright (C) 2023 Chris Caron <lead2gold@gmail.com>'
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

from . import decorators

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

    # Decorator
    'decorators',

    # Logging
    'logging', 'logger', 'LogCapture',
]
