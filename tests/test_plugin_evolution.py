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

from json import loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.evolution import NotifyEvolution

logging.disable(logging.CRITICAL)

# ---------------------------------------------------------------------------
# URL-based tests — exercised by AppriseURLTester
# ---------------------------------------------------------------------------

apprise_url_tests = (
    # No host — parse_url returns None
    (
        "evolution://",
        {
            "instance": None,
        },
    ),
    # No host, explicit empty credentials
    (
        "evolution://:@/",
        {
            "instance": None,
        },
    ),
    # Missing apikey (no user field)
    (
        "evolution://hostname/myinstance/5511999999999",
        {
            "instance": TypeError,
        },
    ),
    # Missing instance (single path entry treated as instance; no phone left)
    (
        "evolution://myapikey@hostname/5511999999999",
        {
            "instance": TypeError,
        },
    ),
    # Missing phone number
    (
        "evolution://myapikey@hostname/myinstance",
        {
            "instance": TypeError,
        },
    ),
    # Invalid phone number
    (
        "evolution://myapikey@hostname/myinstance/notaphone",
        {
            "instance": TypeError,
        },
    ),
    # Valid HTTP — minimal
    (
        "evolution://myapikey@hostname/myinstance/5511999999999",
        {
            "instance": NotifyEvolution,
            "privacy_url": (
                "evolution://m...y@hostname/myinstance/5511999999999"
            ),
        },
    ),
    # Valid HTTPS
    (
        "evolutions://myapikey@hostname/myinstance/5511999999999",
        {
            "instance": NotifyEvolution,
            "privacy_url": (
                "evolutions://m...y@hostname/myinstance/5511999999999"
            ),
        },
    ),
    # Custom port
    (
        "evolution://myapikey@hostname:8080/myinstance/5511999999999",
        {
            "instance": NotifyEvolution,
            "privacy_url": (
                "evolution://m...y@hostname:8080/myinstance/5511999999999"
            ),
        },
    ),
    # Multiple targets
    (
        "evolution://myapikey@hostname/myinstance/5511999999999/5521888888888",
        {
            "instance": NotifyEvolution,
        },
    ),
    # Target via ?to=
    (
        "evolution://myapikey@hostname/myinstance/5511999999999"
        "?to=5521888888888",
        {
            "instance": NotifyEvolution,
        },
    ),
    # Force HTTP error
    (
        "evolution://myapikey@hostname/myinstance/5511999999999",
        {
            "instance": NotifyEvolution,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    # Unknown HTTP response code
    (
        "evolution://myapikey@hostname/myinstance/5511999999999",
        {
            "instance": NotifyEvolution,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    # Connection exceptions
    (
        "evolution://myapikey@hostname/myinstance/5511999999999",
        {
            "instance": NotifyEvolution,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_evolution_urls():
    """NotifyEvolution() Apprise URLs."""
    AppriseURLTester(tests=apprise_url_tests).run_all()


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_plugin_evolution_parse_url_no_path():
    """NotifyEvolution.parse_url() returns instance=None when path is empty."""
    result = NotifyEvolution.parse_url("evolution://key@host")
    assert result is not None
    assert result["instance"] is None


def test_plugin_evolution_edge_cases():
    """NotifyEvolution() direct instantiation edge cases."""

    # No apikey
    with pytest.raises(TypeError):
        NotifyEvolution(
            apikey=None, instance="inst", targets=["5511999999999"]
        )

    # Blank apikey
    with pytest.raises(TypeError):
        NotifyEvolution(
            apikey="   ", instance="inst", targets=["5511999999999"]
        )

    # No instance
    with pytest.raises(TypeError):
        NotifyEvolution(apikey="key", instance=None, targets=["5511999999999"])

    # No targets
    with pytest.raises(TypeError):
        NotifyEvolution(apikey="key", instance="inst", targets=[])

    # All targets invalid
    with pytest.raises(TypeError):
        NotifyEvolution(
            apikey="key", instance="inst", targets=["notaphone", "xx"]
        )


# ---------------------------------------------------------------------------
# send() payload and header verification
# ---------------------------------------------------------------------------


@mock.patch("requests.post")
def test_plugin_evolution_send(mock_post):
    """NotifyEvolution() verifies POST payload and headers."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    obj = Apprise.instantiate(
        "evolution://MYAPIKEY@localhost:8080/myinstance/5511999999999"
    )
    assert isinstance(obj, NotifyEvolution)

    assert obj.notify(body="Hello World", title="Test") is True
    assert mock_post.call_count == 1

    # Verify URL
    call = mock_post.call_args
    assert "localhost:8080" in call[0][0]
    assert "/message/sendText/myinstance" in call[0][0]

    # Verify headers
    headers = call[1]["headers"]
    assert headers["apikey"] == "MYAPIKEY"
    assert headers["Content-Type"] == "application/json"

    # Verify payload
    payload = loads(call[1]["data"])
    assert payload["number"] == "5511999999999"
    assert "Hello World" in payload["text"]


@mock.patch("requests.post")
def test_plugin_evolution_multiple_targets(mock_post):
    """NotifyEvolution() sends one request per target."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    obj = Apprise.instantiate(
        "evolution://key@host/inst/5511111111111/5522222222222/5533333333333"
    )
    assert isinstance(obj, NotifyEvolution)
    assert len(obj) == 3

    assert obj.notify(body="msg") is True
    assert mock_post.call_count == 3

    numbers = [loads(c[1]["data"])["number"] for c in mock_post.call_args_list]
    assert "5511111111111" in numbers
    assert "5522222222222" in numbers
    assert "5533333333333" in numbers


@mock.patch("requests.post")
def test_plugin_evolution_partial_failure(mock_post):
    """NotifyEvolution() returns False if any target fails."""

    r_ok = requests.Request()
    r_ok.status_code = requests.codes.ok
    r_ok.content = b""

    r_err = requests.Request()
    r_err.status_code = requests.codes.internal_server_error
    r_err.content = b"error"

    mock_post.side_effect = [r_ok, r_err]

    obj = Apprise.instantiate(
        "evolution://key@host/inst/5511111111111/5522222222222"
    )
    assert obj.notify(body="msg") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_evolution_title_in_body(mock_post):
    """NotifyEvolution() merges the title into the body via Apprise."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    obj = Apprise.instantiate("evolution://key@host/inst/5511999999999")
    assert obj.notify(body="body text", title="My Title") is True

    payload = loads(mock_post.call_args[1]["data"])
    assert "My Title" in payload["text"]
    assert "body text" in payload["text"]


@mock.patch("requests.post")
def test_plugin_evolution_https(mock_post):
    """NotifyEvolution() uses HTTPS when evolutions:// schema is given."""

    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    obj = Apprise.instantiate(
        "evolutions://key@secure.host/inst/5511999999999"
    )
    assert isinstance(obj, NotifyEvolution)
    assert obj.secure is True

    assert obj.notify(body="secure msg") is True
    url = mock_post.call_args[0][0]
    assert url.startswith("https://")
