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

import re
import pytest
import mock
import apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@mock.patch('syslog.syslog')
@mock.patch('syslog.openlog')
def test_notify_syslog_by_url(openlog, syslog):
    """
    API: Syslog URL Testing

    """
    # an invalid URL
    assert apprise.plugins.NotifySyslog.parse_url(object) is None
    assert apprise.plugins.NotifySyslog.parse_url(42) is None
    assert apprise.plugins.NotifySyslog.parse_url(None) is None

    obj = apprise.Apprise.instantiate('syslog://')
    assert obj.url().startswith('syslog://user') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    assert isinstance(
        apprise.Apprise.instantiate(
            'syslog://:@/'), apprise.plugins.NotifySyslog)

    obj = apprise.Apprise.instantiate('syslog://?logpid=no&logperror=yes')
    assert isinstance(obj, apprise.plugins.NotifySyslog)
    assert obj.url().startswith('syslog://user') is True
    assert re.search(r'logpid=no', obj.url()) is not None
    assert re.search(r'logperror=yes', obj.url()) is not None

    # Test sending a notification
    assert obj.notify("body") is True

    # Invalid Notification Type
    assert obj.notify("body", notify_type='invalid') is False

    obj = apprise.Apprise.instantiate('syslog://_/?facility=local5')
    assert isinstance(obj, apprise.plugins.NotifySyslog)
    assert obj.url().startswith('syslog://local5') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    # Invalid instantiation
    assert apprise.Apprise.instantiate('syslog://_/?facility=invalid') is None

    # j will cause a search to take place and match to daemon
    obj = apprise.Apprise.instantiate('syslog://_/?facility=d')
    assert isinstance(obj, apprise.plugins.NotifySyslog)
    assert obj.url().startswith('syslog://daemon') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    # Facility can also be specified on the url as a hostname
    obj = apprise.Apprise.instantiate('syslog://kern?logpid=no&logperror=y')
    assert isinstance(obj, apprise.plugins.NotifySyslog)
    assert obj.url().startswith('syslog://kern') is True
    assert re.search(r'logpid=no', obj.url()) is not None
    assert re.search(r'logperror=yes', obj.url()) is not None

    # Facilities specified as an argument always over-ride host
    obj = apprise.Apprise.instantiate('syslog://kern?facility=d')
    assert isinstance(obj, apprise.plugins.NotifySyslog)
    assert obj.url().startswith('syslog://daemon') is True


@mock.patch('syslog.syslog')
@mock.patch('syslog.openlog')
def test_notify_syslog_by_class(openlog, syslog):
    """
    API: Syslog Class Testing

    """

    # Default
    obj = apprise.plugins.NotifySyslog(facility=None)
    assert isinstance(obj, apprise.plugins.NotifySyslog)
    assert obj.url().startswith('syslog://user') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    # Exception should be thrown about the fact no bot token was specified
    with pytest.raises(TypeError):
        apprise.plugins.NotifySyslog(facility='invalid')

    with pytest.raises(TypeError):
        apprise.plugins.NotifySyslog(facility=object)
