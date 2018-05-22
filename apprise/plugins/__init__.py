# -*- coding: utf-8 -*-
#
# Our service wrappers
#
# Copyright (C) 2017-2018 Chris Caron <lead2gold@gmail.com>
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

# Used for Testing; specifically test_email_plugin.py needs access
# to the modules WEBBASE_LOOKUP_TABLE and WebBaseLogin objects
from . import NotifyEmail as NotifyEmailBase

from .NotifyBoxcar import NotifyBoxcar
from .NotifyDiscord import NotifyDiscord
from .NotifyEmail import NotifyEmail
from .NotifyEmby import NotifyEmby
from .NotifyFaast import NotifyFaast
from .NotifyGrowl.NotifyGrowl import NotifyGrowl
from .NotifyIFTTT import NotifyIFTTT
from .NotifyJoin import NotifyJoin
from .NotifyJSON import NotifyJSON
from .NotifyMatterMost import NotifyMatterMost
from .NotifyProwl import NotifyProwl
from .NotifyPushalot import NotifyPushalot
from .NotifyPushBullet import NotifyPushBullet
from .NotifyPushjet.NotifyPushjet import NotifyPushjet
from .NotifyPushover import NotifyPushover
from .NotifyRocketChat import NotifyRocketChat
from .NotifySlack import NotifySlack
from .NotifyStride import NotifyStride
from .NotifyTelegram import NotifyTelegram
from .NotifyToasty import NotifyToasty
from .NotifyTwitter.NotifyTwitter import NotifyTwitter
from .NotifyXBMC import NotifyXBMC
from .NotifyXML import NotifyXML

from .NotifyPushjet import pushjet
from .NotifyGrowl import gntp
from .NotifyTwitter import tweepy

from ..common import NotifyImageSize
from ..common import NOTIFY_IMAGE_SIZES
from ..common import NotifyType
from ..common import NOTIFY_TYPES

__all__ = [
    # Notification Services
    'NotifyBoxcar', 'NotifyEmail', 'NotifyEmby', 'NotifyDiscord',
    'NotifyFaast', 'NotifyGrowl', 'NotifyIFTTT', 'NotifyJoin', 'NotifyJSON',
    'NotifyMatterMost', 'NotifyProwl', 'NotifyPushalot',
    'NotifyPushBullet', 'NotifyPushjet', 'NotifyPushover', 'NotifyRocketChat',
    'NotifySlack', 'NotifyStride', 'NotifyToasty', 'NotifyTwitter',
    'NotifyTelegram', 'NotifyXBMC', 'NotifyXML',

    # Reference
    'NotifyImageSize', 'NOTIFY_IMAGE_SIZES', 'NotifyType', 'NOTIFY_TYPES',

    # NotifyEmail Base References (used for Testing)
    'NotifyEmailBase',

    # gntp (used for NotifyGrowl Testing)
    'gntp',

    # pushjet (used for NotifyPushjet Testing)
    'pushjet',

    # tweepy (used for NotifyTwitter Testing)
    'tweepy',
]
