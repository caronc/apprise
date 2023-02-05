# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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
import socket

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
    assert re.search(r'syslog://.*mode=local', obj.url())

    assert isinstance(
        apprise.Apprise.instantiate(
            'syslog://:@/'), NotifySyslog)

    obj = apprise.Apprise.instantiate('syslog://?logpid=no&logperror=yes')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://user') is True
    assert re.search(r'logpid=no', obj.url()) is not None
    assert re.search(r'logperror=yes', obj.url()) is not None
    assert re.search(r'syslog://.*mode=local', obj.url())

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
    assert re.search(r'syslog://.*mode=local', obj.url())

    # Invalid instantiation
    assert apprise.Apprise.instantiate('syslog://_/?facility=invalid') is None

    # j will cause a search to take place and match to daemon
    obj = apprise.Apprise.instantiate('syslog://_/?facility=d')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://daemon') is True
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None
    assert re.search(r'syslog://.*mode=local', obj.url())

    # Facility can also be specified on the url as a hostname
    obj = apprise.Apprise.instantiate('syslog://kern?logpid=no&logperror=y')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://kern') is True
    assert re.search(r'logpid=no', obj.url()) is not None
    assert re.search(r'logperror=yes', obj.url()) is not None
    assert re.search(r'syslog://.*mode=local', obj.url())

    # Facilities specified as an argument always over-ride host
    obj = apprise.Apprise.instantiate('syslog://kern?facility=d')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://daemon') is True
    assert re.search(r'syslog://.*mode=local', obj.url())


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
    assert re.search(r'syslog://.*mode=local', obj.url())

    # Exception should be thrown about the fact no bot token was specified
    with pytest.raises(TypeError):
        NotifySyslog(facility='invalid')

    with pytest.raises(TypeError):
        NotifySyslog(facility=object)


@mock.patch('syslog.syslog')
@mock.patch('syslog.openlog')
@mock.patch('socket.socket')
@mock.patch('os.getpid')
def test_plugin_syslog_remote(
        mock_getpid, mock_socket, mock_openlog, mock_syslog):
    """
    NotifySyslog() Remote Testing

    """
    payload = "test"
    mock_connection = mock.Mock()

    # Fix pid response since it can vary in length and this impacts the
    # sendto() payload response
    mock_getpid.return_value = 123

    # our payload length
    mock_connection.sendto.return_value = 16
    mock_socket.return_value = mock_connection

    # localhost does not lookup to any of the facility codes so this
    # gets interpreted as a host
    obj = apprise.Apprise.instantiate('syslog://localhost')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://localhost') is True
    assert re.search(r'syslog://.*mode=remote', obj.url())
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Test with port
    obj = apprise.Apprise.instantiate('syslog://localhost:518')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://localhost:518') is True
    assert re.search(r'syslog://.*mode=remote', obj.url())
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Test with default port
    obj = apprise.Apprise.instantiate('syslog://localhost:514')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://localhost') is True
    assert re.search(r'syslog://.*mode=remote', obj.url())
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Specify a facility
    obj = apprise.Apprise.instantiate('syslog://localhost/kern')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://localhost/kern') is True
    assert re.search(r'syslog://.*mode=remote', obj.url())
    assert re.search(r'logpid=yes', obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Specify a facility requiring a lookup and having the port identified
    # resolves any ambiguity
    obj = apprise.Apprise.instantiate('syslog://kern:514/d')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://kern/daemon') is True
    assert re.search(r'syslog://.*mode=remote', obj.url())
    assert re.search(r'logpid=yes', obj.url()) is not None
    mock_connection.sendto.return_value = 17  # daemon is one more byte in size
    assert obj.notify(body=payload) is True

    # We can attempt to exclusively set the mode as well without a port
    # to also remove ambiguity; this falls back to sending as the 'user'
    obj = apprise.Apprise.instantiate('syslog://kern/d?mode=remote&logpid=no')
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith('syslog://kern/daemon') is True
    assert re.search(r'syslog://.*mode=remote', obj.url())
    assert re.search(r'logpid=no', obj.url()) is not None
    assert re.search(r'logperror=no', obj.url()) is not None

    # Test notifications
    # + 1 byte in size due to user
    # + length of pid returned
    mock_connection.sendto.return_value = len(payload) + 5 \
        + len(str(mock_getpid.return_value))
    assert obj.notify(body=payload) is True
    # This only fails because the underlining sendto() will return a
    # length different then what was expected
    assert obj.notify(body="a different payload size") is False

    # Test timeouts and errors that can occur
    mock_connection.sendto.return_value = None
    mock_connection.sendto.side_effect = socket.gaierror
    assert obj.notify(body=payload) is False

    mock_connection.sendto.side_effect = socket.timeout
    assert obj.notify(body=payload) is False

    with pytest.raises(TypeError):
        # Handle an invalid mode
        obj = apprise.Apprise.instantiate(
            'syslog://user/?mode=invalid', suppress_exceptions=False)
