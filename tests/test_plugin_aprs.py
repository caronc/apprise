# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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
from timeit import default_timer
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
    assert bool(instance.notify("test")) is True

    # 1N3 callsigns
    instance = apprise.Apprise.instantiate("aprs://D1JSL-15:12345@D1ABC")
    assert isinstance(instance, NotifyAprs)

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
    assert bool(instance.notify("test")) is True

    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC-1/DF1ABC/DF1ABC-15"
    )
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...1/D...C/D...5?"
    )
    assert bool(instance.notify("test")) is True

    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@?to=DF1ABC,DF1DEF"
    )
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...C/D...F?"
    )
    assert bool(instance.notify("test")) is True

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
    assert bool(instance.notify("test")) is True

    instance = apprise.Apprise.instantiate(
        "aprs://DF1JSL-15:12345@DF1ABC?locale=NOAM"
    )
    assert isinstance(instance, NotifyAprs)
    assert instance.url(privacy=True).startswith(
        "aprs://DF1JSL-15:****@D...C?"
    )
    # locale is set in URL
    assert "locale=NOAM" in instance.url(privacy=True)
    assert bool(instance.notify("test")) is True

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
    assert bool(instance.notify("test")) is False

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
    assert bool(instance.notify(body="body", title="title")) is False
    sobj.recv.return_value = "\n\n\n".encode("latin-1")
    assert bool(instance.notify(body="body", title="title")) is False
    sobj.recv.return_value = "".encode("latin-1")
    assert bool(instance.notify(body="body", title="title")) is False
    sobj.recv.return_value = "\ndata".encode("latin-1")
    assert bool(instance.notify(body="body", title="title")) is False
    # Different Call-Sign then what we logged in as
    sobj.recv.return_value = "ping\npong pong DF1JSL-14 verified, pong".encode(
        "latin-1"
    )
    assert bool(instance.notify(body="body", title="title")) is False
    # Unverified
    sobj.recv.return_value = (
        "ping\npong pong DF1JSL-15 unverified, pong".encode("latin-1")
    )
    assert bool(instance.notify(body="body", title="title")) is False

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
    assert bool(instance.notify("test")) is False
    mock_create_connection.side_effect = socket.timeout("timeout")
    assert instance.socket_open() is False
    assert bool(instance.notify("test")) is False
    mock_create_connection.side_effect = OSError("error")
    assert instance.socket_open() is False
    assert bool(instance.notify("test")) is False
    mock_create_connection.side_effect = ConnectionError("ConnectionError")
    assert instance.socket_open() is False
    assert bool(instance.notify("test")) is False

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
    assert bool(instance.notify("test")) is True

    sobj.sendall.return_value = None
    sobj.sendall.side_effect = (True, socket.gaierror("gaierror"))
    assert bool(instance.notify("test")) is False

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

    assert len(ac.services()) == 6
    assert len(aobj) == 6


@mock.patch("socket.create_connection")
def test_plugin_aprs_packet_is_one_line(mock_create_connection):
    """A title and multi-line body are joined into one APRS line."""

    # A socket object
    sobj = mock.Mock()
    sobj.getpeername.return_value = ("localhost", 1234)
    sobj.recv.return_value = "ping\npong pong DF1JSL-15 verified pong".encode(
        "latin-1"
    )
    sobj.sendall.return_value = True

    # Prepare Mock
    mock_create_connection.return_value = sobj

    instance = apprise.Apprise.instantiate("aprs://DF1JSL-15:12345@DF1ABC")
    assert isinstance(instance, NotifyAprs)
    assert instance.notify(body="line one\r\nline two \n\n three", title="T")

    # The message packet is the one addressed to our target
    packets = [
        c[0][0].decode("latin-1")
        for c in sobj.sendall.call_args_list
        if b"::DF1ABC" in c[0][0]
    ]
    assert len(packets) == 1

    # Only the closing CRLF remains; APRS-IS ends a packet there
    assert packets[0].endswith(":T line one line two three\r\n")
    assert packets[0].count("\n") == 1
    assert "\r" not in packets[0][:-2]


@mock.patch("socket.create_connection")
def test_plugin_aprs_retry_skips_delivered(mock_create_connection):
    """An APRS retry only re-sends to the call sign that failed."""

    sent = []

    def sendall(data):
        # Refuse every packet for DF1DEF
        if b"::DF1DEF" in data:
            raise OSError("error")
        sent.append(data)
        return True

    # A socket object
    sobj = mock.Mock()
    sobj.getpeername.return_value = ("localhost", 1234)
    sobj.recv.return_value = "ping\npong pong DF1JSL-15 verified pong".encode(
        "latin-1"
    )
    sobj.sendall.side_effect = sendall

    # Prepare Mock
    mock_create_connection.return_value = sobj

    aobj = apprise.Apprise()
    assert aobj.add("aprs://DF1JSL-15:12345@DF1ABC/DF1DEF?retry=1&wait=0")
    assert not aobj.notify(body="body")

    # The healthy call sign is contacted exactly once
    assert len([p for p in sent if b"::DF1ABC" in p]) == 1


@mock.patch("socket.create_connection")
def test_plugin_aprs_long_space_run_is_fast(mock_create_connection):
    """A long run of tabs with no line break is joined quickly."""

    # A socket object
    sobj = mock.Mock()
    sobj.getpeername.return_value = ("localhost", 1234)
    sobj.recv.return_value = "ping\npong pong DF1JSL-15 verified pong".encode(
        "latin-1"
    )
    sobj.sendall.return_value = True

    # Prepare Mock
    mock_create_connection.return_value = sobj

    instance = apprise.Apprise.instantiate("aprs://DF1JSL-15:12345@DF1ABC")
    assert isinstance(instance, NotifyAprs)

    # Call send() directly; notify() would first cut the body to 67
    # characters and never reach the line joining step
    start = default_timer()
    assert instance.send(body="a" + "\t" * 100000 + "b")
    elapsed = default_timer() - start
    assert elapsed < 5.0

    # The message packet is still cut to the APRS size limit
    packets = [
        c[0][0].decode("latin-1")
        for c in sobj.sendall.call_args_list
        if b"::DF1ABC" in c[0][0]
    ]
    assert len(packets) == 1
    assert packets[0].endswith(":a" + "\t" * 66 + "\r\n")
