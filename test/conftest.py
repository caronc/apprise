# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
import os

import pytest

from apprise import NotifyBase
from apprise.plugins.NotifyPushBullet import NotifyPushBullet

sys.path.append(os.path.join(os.path.dirname(__file__), 'helpers'))


@pytest.fixture
def no_throttling():
    """
    A pytest fixture which disables Apprise throttling.
    """
    backup = {}
    backup["NotifyBase"] = NotifyBase.request_rate_per_sec
    backup["NotifyPushBullet"] = NotifyPushBullet.request_rate_per_sec
    NotifyBase.request_rate_per_sec = 0
    NotifyPushBullet.request_rate_per_sec = 0
    yield
    NotifyBase.request_rate_per_sec = backup["NotifyBase"]
    NotifyPushBullet.request_rate_per_sec = backup["NotifyPushBullet"]
