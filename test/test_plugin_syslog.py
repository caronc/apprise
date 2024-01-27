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

import re
import sys
import pytest
from unittest import mock

import apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Skip tests when Python environment does not provide the `syslog` package.
if 'syslog' not in sys.modules:
    pytest.skip("Skipping syslog based tests", allow_module_level=True)

from apprise.plugins.NotifySyslog import NotifySyslog  # noqa E402


@mock.patch('syslog.syslog')
@mock.patch('syslog.openlog')
def test_plugin_syslog_by_url(openlog, syslog):
    """
    NotifySyslog() Apprise URLs

    """
    # an invalid URL
    assert NotifySyslog.parse_url(object) is None
    assert NotifySyslog.parse_url(42) is None
    assert NotifySyslog.parse_url(None) is None

    obj = apprise.Apprise.instantiate('syslog://')
    assert obj.url().startswith('syslog://user') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    assert isinstance(
        apprise.Apprise.instantiate(
            'syslog://:@/'), NotifySyslog)

    obj = apprise.Apprise.instantiate('syslog://?logpid=no&logperror=yes')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://user') is True
    assert re.search(r'logpid=no', obj.url()) is not None
    assert re.search(r'logperror=yes', obj.url()) is not None

    # Test sending a notification
    assert obj.notify("body") is True
    assert obj.notify(title="title", body="body") is True

    # Invalid Notification Type
    assert obj.notify("body", notify_type='invalid') is False

    obj = apprise.Apprise.instantiate('syslog://_/?facility=local5')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://local5') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    # Invalid instantiation
    assert apprise.Apprise.instantiate('syslog://_/?facility=invalid') is None

    # j will cause a search to take place and match to daemon
    obj = apprise.Apprise.instantiate('syslog://_/?facility=d')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://daemon') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    # Facility can also be specified on the url as a hostname
    obj = apprise.Apprise.instantiate('syslog://kern?logpid=no&logperror=y')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://kern') is True
    assert re.search(r'logpid=no', obj.url()) is not None
    assert re.search(r'logperror=yes', obj.url()) is not None

    # Facilities specified as an argument always over-ride host
    obj = apprise.Apprise.instantiate('syslog://kern?facility=d')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://daemon') is True


@mock.patch('syslog.syslog')
@mock.patch('syslog.openlog')
def test_plugin_syslog_edge_cases(openlog, syslog):
    """
    NotifySyslog() Edge Cases

    """

    # Default
    obj = NotifySyslog(facility=None)
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://user') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    # Exception should be thrown about the fact no bot token was specified
    with pytest.raises(TypeError):
        NotifySyslog(facility='invalid')

    with pytest.raises(TypeError):
        NotifySyslog(facility=object)
