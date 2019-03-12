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

import sys
import six

from . import NotifyEmail as NotifyEmailBase

from .NotifyBoxcar import NotifyBoxcar
from .NotifyDBus import NotifyDBus
from .NotifyDiscord import NotifyDiscord
from .NotifyEmail import NotifyEmail
from .NotifyEmby import NotifyEmby
from .NotifyFaast import NotifyFaast
from .NotifyGotify import NotifyGotify
from .NotifyGrowl.NotifyGrowl import NotifyGrowl
from .NotifyGnome import NotifyGnome
from .NotifyIFTTT import NotifyIFTTT
from .NotifyJoin import NotifyJoin
from .NotifyJSON import NotifyJSON
from .NotifyMatrix import NotifyMatrix
from .NotifyMatterMost import NotifyMatterMost
from .NotifyProwl import NotifyProwl
from .NotifyPushed import NotifyPushed
from .NotifyPushBullet import NotifyPushBullet
from .NotifyPushjet.NotifyPushjet import NotifyPushjet
from .NotifyPushover import NotifyPushover
from .NotifyRocketChat import NotifyRocketChat
from .NotifyRyver import NotifyRyver
from .NotifySlack import NotifySlack
from .NotifySNS import NotifySNS
from .NotifyTelegram import NotifyTelegram
from .NotifyTwitter.NotifyTwitter import NotifyTwitter
from .NotifyXBMC import NotifyXBMC
from .NotifyXML import NotifyXML
from .NotifyWindows import NotifyWindows

from .NotifyPushjet import pushjet
from .NotifyGrowl import gntp
from .NotifyTwitter import tweepy

from ..common import NotifyImageSize
from ..common import NOTIFY_IMAGE_SIZES
from ..common import NotifyType
from ..common import NOTIFY_TYPES

# Maintains a mapping of all of the Notification services
SCHEMA_MAP = {}


__all__ = [
    # Notification Services
    'NotifyBoxcar', 'NotifyDBus', 'NotifyEmail', 'NotifyEmby', 'NotifyDiscord',
    'NotifyFaast', 'NotifyGnome', 'NotifyGotify', 'NotifyGrowl', 'NotifyIFTTT',
    'NotifyJoin', 'NotifyJSON', 'NotifyMatrix', 'NotifyMatterMost',
    'NotifyProwl', 'NotifyPushed', 'NotifyPushBullet', 'NotifyPushjet',
    'NotifyPushover', 'NotifyRocketChat', 'NotifyRyver', 'NotifySlack',
    'NotifySNS', 'NotifyTwitter', 'NotifyTelegram', 'NotifyXBMC',
    'NotifyXML', 'NotifyWindows',

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


# Load our Lookup Matrix
def __load_matrix():
    """
    Dynamically load our schema map; this allows us to gracefully
    skip over modules we simply don't have the dependencies for.

    """

    thismodule = sys.modules[__name__]

    # to add it's mapping to our hash table
    for entry in dir(thismodule):

        # Get our plugin
        plugin = getattr(thismodule, entry)
        if not hasattr(plugin, 'app_id'):  # pragma: no branch
            # Filter out non-notification modules
            continue

        # Load protocol(s) if defined
        proto = getattr(plugin, 'protocol', None)
        if isinstance(proto, six.string_types):
            if proto not in SCHEMA_MAP:
                SCHEMA_MAP[proto] = plugin

        elif isinstance(proto, (set, list, tuple)):
            # Support iterables list types
            for p in proto:
                if p not in SCHEMA_MAP:
                    SCHEMA_MAP[p] = plugin

        # Load secure protocol(s) if defined
        protos = getattr(plugin, 'secure_protocol', None)
        if isinstance(protos, six.string_types):
            if protos not in SCHEMA_MAP:
                SCHEMA_MAP[protos] = plugin

        if isinstance(protos, (set, list, tuple)):
            # Support iterables list types
            for p in protos:
                if p not in SCHEMA_MAP:
                    SCHEMA_MAP[p] = plugin


# Dynamically build our module
__load_matrix()
