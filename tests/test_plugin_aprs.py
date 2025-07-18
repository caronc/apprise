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
import socket
from unittest import mock

import apprise
from apprise.plugins.aprs import NotifyAprs

logging.disable(logging.CRITICAL)


@mock.patch("socket.create_connection")
def test_plugin_aprs_urls(mock_create_connection):
    """NotifyAprs() Apprise URLs."""
    # A socket object
    sobj = mock.Mock()
    sobj.return_value = 1
    sobj.getpeername.return_value = ("localhost", 1234)
    sobj.socket_close.return_value = None
    sobj.setblocking.return_value = True
    sobj.recv.return_value = "ping\npong pong DF1JSL-15 verified pong".encode(
        "latin-1"
    )
    sobj.sendall.return_value = True
    sobj.settimeout.return_value = True

    # Prepare Mock
    mock_create_connection.return_value = sobj

    # Test invalid URLs
    assert apprise.Apprise.instantiate("aprs://") is None
    assert apprise.Apprise.instantiate("aprs://:@/") is None

    # No call-sign specified
    assert apprise.Apprise.instantiate("aprs://DF1JSL-15:12345") is None

    # Garbage
    assert NotifyAprs.parse_url(None) is None

    # Valid call-sign but no password
    assert apprise.Apprise.instantiate("aprs://DF1JSL-15:@DF1ABC") is None
    assert apprise.Apprise.instantiate("aprs://DF1JSL-15@DF1ABC") is None
    # Password of -1 not supported
    assert apprise.Apprise.instantiate("aprs://DF1JSL-15:-1@DF1ABC") is None
    # Alpha Password not supported
    assert apprise.Apprise.instantiate("aprs://DF1JSL-15:abcd@DF1ABC") is None

    # Valid instances
    instance = apprise.Apprise.instantiate("aprs://DF1JSL-15:12345@DF1ABC")
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...C?"
    )
    assert instance.notify("test") is True

    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC?delay=3.0"
    )
    assert isinstance(instance, NotifyAprs)
    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC?delay=2"
    )
    assert isinstance(instance, NotifyAprs)
    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC?delay=-3.0"
    )
    assert instance is None
    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC?delay=40.0"
    )
    assert instance is None
    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC?delay=invalid"
    )
    assert instance is None

    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC/DF1DEF"
    )
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...C/D...F?"
    )
    assert instance.notify("test") is True

    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC-1/DF1ABC/DF1ABC-15"
    )
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...1/D...C/D...5?"
    )
    assert instance.notify("test") is True

    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@?to=DF1ABC,DF1DEF"
    )
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...C/D...F?"
    )
    assert instance.notify("test") is True

    # Test Locale settings
    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC?locale=EURO"
    )
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...C?"
    )
    # we used the default locale, so no setting
    assert "locale=" not in instance.url(privacy=True)
    assert instance.notify("test") is True

    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC?locale=NOAM"
    )
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...C?"
    )
    # locale is set in URL
    assert "locale=NOAM" in instance.url(privacy=True)
    assert instance.notify("test") is True

    # Invalid locale
    assert (
        apprise.Apprise.instantiate(
            "aprs://DF1JSL-15:12345@DF1ABC?locale=invalid"
        )
        is None
    )

    # Invalid call signs
    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@abcdefghi/a"
    )

    # We still instantiate
    assert isinstance(instance, NotifyAprs)

    # We still load our bad entries
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@A...I/A...A?"
    )

    # But with only bad entries, we have nothing to notify
    assert instance.notify("test") is False

    # Enforces a close
    del instance


@mock.patch("socket.create_connection")
def test_plugin_aprs_edge_cases(mock_create_connection):
    """NotifyAprs() Edge Cases."""

    # A socket object
    sobj = mock.Mock()
    sobj.return_value = 1
    sobj.getpeername.return_value = ("localhost", 1234)
    sobj.socket_close.return_value = None
    sobj.setblocking.return_value = True
    sobj.recv.return_value = "ping\npong pong DF1JSL-15 verified pong".encode(
        "latin-1"
    )
    sobj.sendall.return_value = True
    sobj.settimeout.return_value = True

    # Prepare Mock
    mock_create_connection.return_value = sobj

    # Valid instances
    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC/DF1DEF"
    )
    assert isinstance(instance, NotifyAprs)

    # our URL Identifier
    assert isinstance(instance.url_id(), str)

    # Objects read
    assert len(instance) == 2

    # Bad data
    sobj.recv.return_value = "one line".encode("latin-1")
    assert instance.notify(body="body", title="title") is False
    sobj.recv.return_value = "\n\n\n".encode("latin-1")
    assert instance.notify(body="body", title="title") is False
    sobj.recv.return_value = "".encode("latin-1")
    assert instance.notify(body="body", title="title") is False
    sobj.recv.return_value = "\ndata".encode("latin-1")
    assert instance.notify(body="body", title="title") is False
    # Different Call-Sign then what we logged in as
    sobj.recv.return_value = "ping\npong pong DF1JSL-14 verified, pong".encode(
        "latin-1"
    )
    assert instance.notify(body="body", title="title") is False
    # Unverified
    sobj.recv.return_value = (
        "ping\npong pong DF1JSL-15 unverified, pong".encode("latin-1")
    )
    assert instance.notify(body="body", title="title") is False

    #
    # Test Login edge cases
    #
    sobj.return_value = False
    assert instance.aprsis_login() is False
    sobj.return_value = 1
    sobj.recv.return_value = "".encode("latin-1")
    assert instance.aprsis_login() is False
    sobj.recv.return_value = "ping\npong pong DF1JSL-15 verified pong".encode(
        "latin-1"
    )

    #
    # Test Socket Send Exceptions
    #
    sobj.sendall.return_value = None
    sobj.sendall.side_effect = socket.gaierror("gaierror")
    # No connection
    assert instance.socket_send("data") is False
    # Ensure we have a connection before calling socket_send()
    assert instance.socket_open() is True
    assert instance.socket_send("data") is False
    sobj.sendall.side_effect = socket.timeout("timeout")
    assert instance.socket_open() is True
    assert instance.socket_send("data") is False
    assert instance.socket_open() is True
    sobj.sendall.side_effect = OSError("error")
    assert instance.socket_send("data") is False

    # Login is impacted by socket_send
    sobj.return_value = 1
    assert instance.socket_open() is True
    assert instance.aprsis_login() is False

    # Return some of our
    sobj.sendall.side_effect = None
    sobj.sendall.return_value = True

    assert instance.socket_open() is True
    sobj.close.return_value = None
    sobj.close.side_effect = socket.gaierror("gaierror")
    instance.socket_close()
    sobj.close.side_effect = socket.timeout("timeout")
    instance.socket_close()
    sobj.close.side_effect = OSError("error")
    instance.socket_close()
    sobj.return_value = None
    instance.socket_close()
    # Socket isn't open; so we can't get content
    assert instance.socket_receive(100) is False
    sobj.close.side_effect = None
    sobj.close.return_value = None
    # Double close test
    instance.socket_close()

    sobj.return_value = 1
    mock_create_connection.return_value = None
    mock_create_connection.side_effect = socket.gaierror("gaierror")
    assert instance.socket_open() is False
    assert instance.notify("test") is False
    mock_create_connection.side_effect = socket.timeout("timeout")
    assert instance.socket_open() is False
    assert instance.notify("test") is False
    mock_create_connection.side_effect = OSError("error")
    assert instance.socket_open() is False
    assert instance.notify("test") is False
    mock_create_connection.side_effect = ConnectionError("ConnectionError")
    assert instance.socket_open() is False
    assert instance.notify("test") is False

    # Restore our good connection
    mock_create_connection.return_value = sobj
    mock_create_connection.side_effect = None

    # Functionality has been restored
    assert instance.socket_open() is True

    # Now play with getpeername
    sobj.getpeername.return_value = None
    sobj.getpeername.side_effect = ValueError("getpeername ValueError")
    assert instance.socket_open() is True

    sobj.getpeername.return_value = ("localhost", 1234)
    assert instance.socket_open() is True
    # Test different receive settings
    assert instance.socket_receive(0)
    assert instance.socket_receive(-1)
    assert instance.socket_receive(100)

    sobj.recv.side_effect = socket.gaierror("gaierror")
    assert instance.socket_open() is True
    assert instance.socket_receive(100) is False
    sobj.recv.side_effect = socket.timeout("timeout")
    assert instance.socket_open() is True
    assert instance.socket_receive(100) is False
    sobj.recv.side_effect = OSError("error")
    assert instance.socket_open() is True
    assert instance.socket_receive(100) is False

    # Restore
    sobj.recv.side_effect = None
    sobj.recv.return_value = "ping\npong pong DF1JSL-15 verified pong".encode(
        "latin-1"
    )

    # Simulate a successful connection, but a failed notification
    # To do this we need to have a login succeed, but the second call to send
    # to fail
    sobj.sendall.return_value = True
    assert instance.notify("test") is True

    sobj.sendall.return_value = None
    sobj.sendall.side_effect = (True, socket.gaierror("gaierror"))
    assert instance.notify("test") is False

    sobj.sendall.return_value = True
    sobj.sendall.side_effect = None
    del sobj


def test_plugin_aprs_config_files():
    """NotifyAprs() Config File Cases."""
    content = """
    urls:
      - aprs://DF1JSL-15:12345@DF1ABC":
          - locale: NOAM

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: SOAM

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: EURO

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: ASIA

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: AUNZ

      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: ROTA

      # This will fail to load because the locale is bad
      - aprs://DF1JSL-15:12345@DF1ABC:
          - locale: aprs_invalid
    """

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    assert len(ac.servers()) == 6
    assert len(aobj) == 6
