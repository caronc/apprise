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
import sys
import os

import pytest

from apprise.common import NOTIFY_MODULE_MAP

sys.path.append(os.path.join(os.path.dirname(__file__), 'helpers'))


@pytest.fixture(scope="session", autouse=True)
def no_throttling_everywhere(session_mocker):
    """
    A pytest session fixture which disables throttling on all notifiers.
    It is automatically enabled.
    """
    for notifier in NOTIFY_MODULE_MAP.values():
        plugin = notifier["plugin"]
        session_mocker.patch.object(plugin, "request_rate_per_sec", 0)
