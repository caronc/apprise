# -*- coding: utf-8 -*-
#
# Our service wrappers
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

from .NotifyBoxcar import NotifyBoxcar
from .NotifyEmail import NotifyEmail
from .NotifyFaast import NotifyFaast
from .NotifyGrowl import NotifyGrowl
from .NotifyJSON import NotifyJSON
from .NotifyMyAndroid import NotifyMyAndroid
from .NotifyProwl import NotifyProwl
from .NotifyPushalot import NotifyPushalot
from .NotifyPushBullet import NotifyPushBullet
from .NotifyPushover import NotifyPushover
from .NotifyRocketChat import NotifyRocketChat
from .NotifyToasty import NotifyToasty
from .NotifyTwitter import NotifyTwitter
from .NotifyXBMC import NotifyXBMC
from .NotifyXML import NotifyXML
from .NotifySlack import NotifySlack
from .NotifyJoin import NotifyJoin
from .NotifyTelegram import NotifyTelegram
from .NotifyMatterMost import NotifyMatterMost
from .NotifyPushjet import NotifyPushjet

from ..common import NotifyImageSize
from ..common import NOTIFY_IMAGE_SIZES
from ..common import NotifyType
from ..common import NOTIFY_TYPES

__all__ = [
    # Notification Services
    'NotifyBoxcar', 'NotifyEmail', 'NotifyFaast', 'NotifyGrowl', 'NotifyJSON',
    'NotifyMyAndroid', 'NotifyProwl', 'NotifyPushalot', 'NotifyPushBullet',
    'NotifyPushover', 'NotifyRocketChat', 'NotifyToasty', 'NotifyTwitter',
    'NotifyXBMC', 'NotifyXML', 'NotifySlack', 'NotifyJoin', 'NotifyTelegram',
    'NotifyMatterMost', 'NotifyPushjet',

    # Reference
    'NotifyImageSize', 'NOTIFY_IMAGE_SIZES', 'NotifyType', 'NOTIFY_TYPES',
]
