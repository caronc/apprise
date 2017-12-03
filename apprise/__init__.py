# -*- coding: utf-8 -*-
#
# base class for easier library inclusion
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

__title__ = 'apprise'
__version__ = '0.0.3'
__author__ = 'Chris Caron <lead2gold@gmail.com>'
__license__ = 'GPLv3'
__copywrite__ = 'Copyright 2017 Chris Caron <lead2gold@gmail.com>'

from .common import NotifyType
from .common import NOTIFY_TYPES
from .common import NOTIFY_IMAGE_SIZES
from .common import NotifyImageSize
from .plugins.NotifyBase import NotifyFormat

from .Apprise import Apprise
from .AppriseAsset import AppriseAsset

# Set default logging handler to avoid "No handler found" warnings.
import logging
from logging import NullHandler
logging.getLogger(__name__).addHandler(NullHandler())

__all__ = [
    # Core
    'Apprise', 'AppriseAsset',

    # Reference
    'NotifyType', 'NotifyImageSize', 'NotifyFormat', 'NOTIFY_TYPES',
    'NOTIFY_IMAGE_SIZES',
]
