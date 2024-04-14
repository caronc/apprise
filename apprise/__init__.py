# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

__title__ = 'Apprise'
__version__ = '1.7.6'
__author__ = 'Chris Caron'
__license__ = 'BSD'
__copywrite__ = 'Copyright (C) 2024 Chris Caron <lead2gold@gmail.com>'
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
