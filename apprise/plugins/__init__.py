# -*- encoding: utf-8 -*-
#
# Our service wrappers
#
# Copyright (C) 2014-2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# apprise is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# apprise is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with apprise. If not, see <http://www.gnu.org/licenses/>.

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

__all__ = [
    # Notification Services
    'NotifyBoxcar', 'NotifyEmail', 'NotifyFaast', 'NotifyGrowl', 'NotifyJSON',
    'NotifyMyAndroid', 'NotifyProwl', 'NotifyPushalot', 'NotifyPushBullet',
    'NotifyPushover', 'NotifyRocketChat', 'NotifyToasty', 'NotifyTwitter',
    'NotifyXBMC', 'NotifyXML', 'NotifySlack', 'NotifyJoin', 'NotifyTelegram',
    'NotifyMatterMost', 'NotifyPushjet'
]
