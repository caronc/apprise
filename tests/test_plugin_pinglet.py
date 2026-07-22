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
from json import loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

import apprise
from apprise import NotifyType
from apprise.plugins.pinglet import NotifyPinglet, PingletPriority

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "pinglet://",
        {
            "instance": None,
        },
    ),
    # An invalid url
    (
        "pinglet://:@/",
        {
            "instance": None,
        },
    ),
    # No API Key specified
    (
        "pinglet://hostname/acme/deploys",
        {
            "instance": TypeError,
        },
    ),
    # No namespace and/or topic specified
    (
        "pinglet://token@hostname",
        {
            "instance": TypeError,
        },
    ),
    (
        "pinglet://token@hostname/deploys",
        {
            "instance": TypeError,
        },
    ),
    # Provide an API Key, namespace, and topic
    (
        "pinglet://abc123@hostname/acme/deploys",
        {
            "instance": NotifyPinglet,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pinglet://****@hostname/acme/deploys",
        },
    ),
    # Secure protocol
    (
        "pinglets://abc123@hostname/acme/deploys",
        {
            "instance": NotifyPinglet,
            "privacy_url": "pinglets://****@hostname/acme/deploys",
        },
    ),
    # API Key as a query argument
    (
        "pinglets://hostname/acme/deploys?token=abc123",
        {
            "instance": NotifyPinglet,
            "privacy_url": "pinglets://****@hostname/acme/deploys",
        },
    ),
    # A path prefix (such as a reverse-proxy mount point)
    (
        "pinglet://abc123@hostname/prefix/acme/deploys",
        {
            "instance": NotifyPinglet,
            "privacy_url": "pinglet://****@hostname/prefix/acme/deploys",
        },
    ),
    # Host with a port
    (
        "pinglet://abc123@hostname:8080/acme/deploys",
        {
            "instance": NotifyPinglet,
            "privacy_url": "pinglet://****@hostname:8080/acme/deploys",
        },
    ),
    # Provide a priority
    (
        "pinglet://abc123@hostname/acme/deploys?priority=urgent",
        {
            "instance": NotifyPinglet,
        },
    ),
    # Priorities support prefix matching (s => silent)
    (
        "pinglet://abc123@hostname/acme/deploys?priority=s",
        {
            "instance": NotifyPinglet,
        },
    ),
    # An invalid priority takes on the default (normal)
    (
        "pinglet://abc123@hostname/acme/deploys?priority=invalid",
        {
            "instance": NotifyPinglet,
        },
    ),
    # Badges (:key=value) and metadata (+key=value)
    (
        "pinglet://abc123@hostname/acme/deploys?:CPU=95%25&+region=eu-west",
        {
            "instance": NotifyPinglet,
        },
    ),
    (
        "pinglet://abc123@hostname/acme/deploys",
        {
            "instance": NotifyPinglet,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "pinglets://abc123@localhost/acme/deploys",
        {
            "instance": NotifyPinglet,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pinglet://abc123@localhost/acme/deploys",
        {
            "instance": NotifyPinglet,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pinglet_urls():
    """NotifyPinglet() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_pinglet_edge_cases():
    """NotifyPinglet() Edge Cases."""
    # Initializes the plugin with an invalid token
    with pytest.raises(TypeError):
        NotifyPinglet(token=None, namespace="acme", topic="deploys")
    # Whitespace also acts as an invalid token value
    with pytest.raises(TypeError):
        NotifyPinglet(token="   ", namespace="acme", topic="deploys")

    # Missing namespace and/or topic
    with pytest.raises(TypeError):
        NotifyPinglet(token="abc123", namespace=None, topic="deploys")
    with pytest.raises(TypeError):
        NotifyPinglet(token="abc123", namespace="acme", topic=None)


@mock.patch("requests.post")
def test_plugin_pinglet_payload(mock_post):
    """NotifyPinglet() Payload Construction."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    aobj = apprise.Apprise()
    assert aobj.add(
        "pinglets://mykey@app.pinglet.co.uk/acme/deploys"
        "?priority=urgent&:CPU=95%25&:Host=web-1&+region=eu-west"
    )

    assert (
        aobj.notify(
            title="Hello",
            body="It works",
            notify_type=NotifyType.FAILURE,
        )
        is True
    )

    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://app.pinglet.co.uk/acme/deploys"
    )

    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers["Authorization"] == "Bearer mykey"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["title"] == "Hello"
    assert payload["message"] == "It works"
    assert payload["priority"] == PingletPriority.URGENT
    # The FAILURE notification type maps to Pinglet's 'error' level
    assert payload["level"] == "error"
    assert payload["badges"] == {"CPU": "95%", "Host": "web-1"}
    assert payload["data"] == {"region": "eu-west"}


@mock.patch("requests.post")
def test_plugin_pinglet_payload_defaults(mock_post):
    """NotifyPinglet() Payload Defaults."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    aobj = apprise.Apprise()
    assert aobj.add("pinglet://mykey@hostname/acme/deploys")

    assert aobj.notify(body="It works") is True

    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "http://hostname/acme/deploys"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    # An empty title is omitted entirely
    assert "title" not in payload
    # No badges/metadata were specified so they are omitted
    assert "badges" not in payload
    assert "data" not in payload
    assert payload["priority"] == PingletPriority.NORMAL
    # The INFO notification type maps to Pinglet's 'info' level
    assert payload["level"] == "info"


def test_plugin_pinglet_limits():
    """NotifyPinglet() Badge and Metadata Limits."""

    # Badges are capped at 3 entries; keys are truncated to 24
    # characters, and values to 32
    obj = apprise.Apprise.instantiate(
        "pinglet://abc123@hostname/acme/deploys"
        "?:{}={}&:b=2&:c=3&:d=4&:e=5".format("k" * 30, "v" * 40)
    )
    assert isinstance(obj, NotifyPinglet)
    assert len(obj.badges) == 3
    assert "k" * 24 in obj.badges
    assert obj.badges["k" * 24] == "v" * 32

    # Metadata keys are truncated to 64 characters, and values to 256
    obj = apprise.Apprise.instantiate(
        "pinglet://abc123@hostname/acme/deploys?+{}={}".format(
            "k" * 70, "v" * 300
        )
    )
    assert isinstance(obj, NotifyPinglet)
    assert obj.data == {"k" * 64: "v" * 256}


def test_plugin_pinglet_priorities():
    """NotifyPinglet() Priority Handling."""

    for priority, expected in (
        ("silent", PingletPriority.SILENT),
        ("s", PingletPriority.SILENT),
        ("NORMAL", PingletPriority.NORMAL),
        ("urgent", PingletPriority.URGENT),
        ("u", PingletPriority.URGENT),
        # Invalid entries take on the default
        ("invalid", PingletPriority.NORMAL),
        ("", PingletPriority.NORMAL),
    ):
        obj = apprise.Apprise.instantiate(
            f"pinglet://abc123@hostname/acme/deploys?priority={priority}"
        )
        assert isinstance(obj, NotifyPinglet)
        assert obj.priority == expected, f"priority={priority}"
