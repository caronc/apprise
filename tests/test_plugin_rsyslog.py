# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

# Disable logging for a cleaner testing output
import logging
import re
import socket
from unittest import mock

import pytest

import apprise

logging.disable(logging.CRITICAL)

from apprise.plugins.rsyslog import NotifyRSyslog  # noqa E402


@mock.patch("socket.socket")
@mock.patch("os.getpid")
def test_plugin_rsyslog_by_url(mock_getpid, mock_socket):
    """NotifyRSyslog() Apprise URLs."""
    payload = "test"
    mock_connection = mock.Mock()

    # Fix pid response since it can vary in length and this impacts the
    # sendto() payload response
    mock_getpid.return_value = 123

    # our payload length
    mock_connection.sendto.return_value = 16
    mock_socket.return_value = mock_connection

    # an invalid URL
    assert NotifyRSyslog.parse_url(object) is None
    assert NotifyRSyslog.parse_url(42) is None
    assert NotifyRSyslog.parse_url(None) is None

    # localhost does not lookup to any of the facility codes so this
    # gets interpreted as a host
    obj = apprise.Apprise.instantiate("rsyslog://localhost")
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost") is True
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert obj.notify(body=payload) is True

    mock_connection.sendto.return_value = 18
    obj = apprise.Apprise.instantiate("rsyslog://localhost/?facility=local5")
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost/local5") is True
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Invalid instantiation
    assert (
        apprise.Apprise.instantiate("rsyslog://localhost/?facility=invalid")
        is None
    )

    mock_connection.sendto.return_value = 17
    # j will cause a search to take place and match to daemon
    obj = apprise.Apprise.instantiate("rsyslog://localhost/?facility=d")
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost/daemon") is True
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Test bad return count
    mock_connection.sendto.return_value = 0
    assert obj.notify(body=payload) is False

    # Test with port
    mock_connection.sendto.return_value = 17
    obj = apprise.Apprise.instantiate("rsyslog://localhost:518")
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost:518") is True
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Set length to include title (for test)
    mock_connection.sendto.return_value = 39
    assert obj.notify(body=payload, title="Testing a title entry") is True

    # Return length back to where it was
    mock_connection.sendto.return_value = 16

    # Test with default port
    obj = apprise.Apprise.instantiate("rsyslog://localhost:514")
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost") is True
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Specify a facility
    obj = apprise.Apprise.instantiate("rsyslog://localhost/kern")
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost/kern") is True
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert obj.notify(body=payload) is True

    # Specify a facility requiring a lookup and having the port identified
    # resolves any ambiguity
    obj = apprise.Apprise.instantiate("rsyslog://localhost:514/d")
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost/daemon") is True
    assert re.search(r"logpid=yes", obj.url()) is not None
    mock_connection.sendto.return_value = 17  # daemon is one more byte in size
    assert obj.notify(body=payload) is True

    obj = apprise.Apprise.instantiate("rsyslog://localhost:9000/d?logpid=no")
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost:9000/daemon") is True
    assert re.search(r"logpid=no", obj.url()) is not None

    # Verify our URL ID is generated
    assert isinstance(obj.url_id(), str)

    # Test notifications
    # + 1 byte in size due to user
    # + length of pid returned
    mock_connection.sendto.return_value = (
        len(payload) + 5 + len(str(mock_getpid.return_value))
    )
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


def test_plugin_rsyslog_edge_cases():
    """NotifyRSyslog() Edge Cases."""

    # Default
    obj = NotifyRSyslog(host="localhost", facility=None)
    assert isinstance(obj, NotifyRSyslog)
    assert obj.url().startswith("rsyslog://localhost/user") is True
    assert re.search(r"logpid=yes", obj.url()) is not None

    # Exception should be thrown about the fact no bot token was specified
    with pytest.raises(TypeError):
        NotifyRSyslog(host="localhost", facility="invalid")

    with pytest.raises(TypeError):
        NotifyRSyslog(host="localhost", facility=object)
