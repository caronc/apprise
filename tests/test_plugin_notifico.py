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
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise.common import NotifyType
from apprise.plugins.notifico import NotificoMode, NotifyNotifico

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "notifico://",
        {
            "instance": TypeError,
        },
    ),
    (
        "notifico://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "notifico://1234",
        {
            # Just a project id provided (no message token)
            "instance": TypeError,
        },
    ),
    (
        "notifico://abcd/ckhrjW8w672m6HG",
        {
            # an invalid project id provided (not all digits)
            "instance": TypeError,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            # A project id and message hook provided (official mode)
            "instance": NotifyNotifico,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?prefix=no",
        {
            # Disable our prefix
            "instance": NotifyNotifico,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "info",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "success",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "warning",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "failure",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "invalid",
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG?color=no",
        {
            # Test our color flag by having it set to off
            "instance": NotifyNotifico,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "notifico://1...4/c...G",
        },
    ),
    # Native URL (official endpoint)
    (
        "https://n.tkte.ch/h/2144/uJmKaBW9WFk42miB146ci3Kj",
        {
            "instance": NotifyNotifico,
        },
    ),
    # Self-hosted HTTP
    (
        "notifico://example.com/1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
        },
    ),
    # Self-hosted HTTPS
    (
        "notificos://example.com/1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            "privacy_url": "notificos://example.com/1...4/c...G",
        },
    ),
    # Self-hosted with port and color
    (
        "notifico://user@example.com:20/1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "info",
        },
    ),
    # Self-hosted HTTPS with auth
    (
        "notificos://user:pass@example.com/1234/ckhrjW8w672m6HG?color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "success",
            "privacy_url": "notificos://user:****@example.com/1...4/c...G",
        },
    ),
    # Self-hosted: project and token supplied as query params
    (
        "notificos://user:pass@example.com/"
        "?project=1234&token=ckhrjW8w672m6HG&color=yes",
        {
            "instance": NotifyNotifico,
            "notify_type": "success",
            "privacy_url": "notificos://user:****@example.com/1...4/c...G",
        },
    ),
    # Self-hosted: invalid project_id in path
    (
        "notifico://example.com/abcd/ckhrjW8w672m6HG",
        {
            "instance": TypeError,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            # don't include an image by default
            "include_image": False,
        },
    ),
    # Official: HTTP error responses
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notifico://1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            # Throws a series of i/o exceptions with this flag set
            # and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    # Self-hosted: HTTP error responses
    (
        "notifico://example.com/1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "notifico://example.com/1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notifico://example.com/1234/ckhrjW8w672m6HG",
        {
            "instance": NotifyNotifico,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_notifico_urls():
    """NotifyNotifico() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
def test_plugin_notifico_official_mode(mock_get):
    """NotifyNotifico() official-mode init and round-trip."""

    # Prepare a successful response
    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_get.return_value = response

    # Valid official-mode instance
    obj = NotifyNotifico(
        project_id="2144",
        msghook="uJmKaBW9WFk42miB146ci3Kj",
    )
    assert obj.mode == NotificoMode.OFFICIAL
    assert not obj.host

    # url() round-trip preserves identity
    url = obj.url()
    assert "2144" in url
    assert "uJmKaBW9WFk42miB146ci3Kj" in url

    result = NotifyNotifico.parse_url(url)
    assert result is not None
    obj2 = NotifyNotifico(**result)
    assert obj2.url_identifier == obj.url_identifier

    # send() succeeds and hits the official n.tkte.ch endpoint
    assert obj.send(body="test") is True
    assert mock_get.call_count == 1
    call_url = mock_get.call_args[0][0]
    assert "n.tkte.ch" in call_url
    assert "2144" in call_url
    assert "uJmKaBW9WFk42miB146ci3Kj" in call_url


@mock.patch("requests.get")
def test_plugin_notifico_selfhosted_http(mock_get):
    """NotifyNotifico() self-hosted HTTP mode."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_get.return_value = response

    obj = NotifyNotifico(
        project_id="1234",
        msghook="ckhrjW8w672m6HG",
        host="myhost.local",
    )
    assert obj.mode == NotificoMode.SELFHOSTED
    assert obj.host == "myhost.local"
    assert obj.secure is False

    # url() encodes the hostname
    url = obj.url()
    assert url.startswith("notifico://myhost.local/1234/ckhrjW8w672m6HG")

    # Round-trip preserves identity
    result = NotifyNotifico.parse_url(url)
    assert result is not None
    obj2 = NotifyNotifico(**result)
    assert obj2.url_identifier == obj.url_identifier

    # send() uses HTTP against the self-hosted host
    assert obj.send(body="test") is True
    call_url = mock_get.call_args[0][0]
    parsed = urlparse(call_url)
    assert parsed.scheme == "http"
    assert parsed.hostname == "myhost.local"
    assert "1234" in call_url
    assert "ckhrjW8w672m6HG" in call_url


@mock.patch("requests.get")
def test_plugin_notifico_selfhosted_https(mock_get):
    """NotifyNotifico() self-hosted HTTPS mode with auth and port."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_get.return_value = response

    # Parse a notificos:// URL with credentials and non-default port
    result = NotifyNotifico.parse_url(
        "notificos://user:secret@myhost.local:8443/9999/AbCdEfGh"
    )
    assert result is not None
    obj = NotifyNotifico(**result)

    assert obj.mode == NotificoMode.SELFHOSTED
    assert obj.secure is True
    assert obj.host == "myhost.local"
    assert obj.port == 8443
    assert obj.user == "user"

    # url() emits notificos:// with the non-default port
    url = obj.url()
    assert url.startswith("notificos://user:")
    assert "myhost.local:8443" in url
    assert "9999" in url

    # Privacy URL hides the password
    privacy = obj.url(privacy=True)
    assert "****" in privacy

    # send() uses HTTPS against the self-hosted host
    assert obj.send(body="test") is True
    call_url = mock_get.call_args[0][0]
    parsed = urlparse(call_url)
    assert parsed.scheme == "https"
    assert parsed.hostname == "myhost.local"
    assert parsed.port == 8443
    assert "9999" in call_url
    assert "AbCdEfGh" in call_url


@mock.patch("requests.get")
def test_plugin_notifico_invalid_params(mock_get):
    """NotifyNotifico() invalid init parameters raise TypeError."""

    # Invalid project_id (not all digits)
    with pytest.raises(TypeError):
        NotifyNotifico(project_id="abc", msghook="validhook")

    # Invalid msghook (contains special characters)
    with pytest.raises(TypeError):
        NotifyNotifico(project_id="1234", msghook="bad hook!")

    # None project_id
    with pytest.raises(TypeError):
        NotifyNotifico(project_id=None, msghook="validhook")

    # None msghook
    with pytest.raises(TypeError):
        NotifyNotifico(project_id="1234", msghook=None)

    # No HTTP calls should have been made
    assert mock_get.call_count == 0


@mock.patch("requests.get")
def test_plugin_notifico_parse_url(mock_get):
    """NotifyNotifico() parse_url edge cases."""

    # Official mode: numeric host is the project_id
    result = NotifyNotifico.parse_url("notifico://1234/hookABC")
    assert result is not None
    assert result["project_id"] == "1234"
    assert result["msghook"] == "hookABC"
    assert not result["host"]

    # Official mode must clear port/user/password even when present
    # in the URL (e.g. notifico://user:pass@1234:8080/hook);
    # these fields have no meaning for the official n.tkte.ch endpoint
    result = NotifyNotifico.parse_url("notifico://user:pass@1234:8080/hookABC")
    assert result is not None
    assert result["project_id"] == "1234"
    assert result["msghook"] == "hookABC"
    assert not result["host"]
    assert result["port"] is None
    assert result["user"] is None
    assert result["password"] is None

    # Self-hosted mode: hostname in host position
    result = NotifyNotifico.parse_url("notifico://myhost.example/5678/hookXYZ")
    assert result is not None
    assert result["project_id"] == "5678"
    assert result["msghook"] == "hookXYZ"
    assert result["host"] == "myhost.example"

    # Query-param aliases override path-based values
    result = NotifyNotifico.parse_url(
        "notificos://example.com/?project=9999&token=hookQQQ"
    )
    assert result is not None
    assert result["project_id"] == "9999"
    assert result["msghook"] == "hookQQQ"

    # Color and prefix default to True
    result = NotifyNotifico.parse_url("notifico://1234/hook")
    assert result["color"] is True
    assert result["prefix"] is True

    # Explicit color=no and prefix=no
    result = NotifyNotifico.parse_url(
        "notifico://1234/hook?color=no&prefix=no"
    )
    assert result["color"] is False
    assert result["prefix"] is False

    # parse_url returns None only when parse_url itself cannot parse the URL
    assert NotifyNotifico.parse_url(None) is None

    assert mock_get.call_count == 0


@mock.patch("requests.get")
def test_plugin_notifico_send_http_errors(mock_get):
    """NotifyNotifico() handles HTTP error responses gracefully."""

    obj = NotifyNotifico(project_id="1234", msghook="validHook")

    # HTTP 500
    response = mock.Mock()
    response.status_code = requests.codes.internal_server_error
    response.content = b""
    mock_get.return_value = response
    assert obj.send(body="test") is False

    # Unrecognised HTTP status
    response.status_code = 999
    assert obj.send(body="test") is False

    # Network exception
    mock_get.side_effect = requests.RequestException("connection refused")
    assert obj.send(body="test") is False


@mock.patch("requests.get")
def test_plugin_notifico_send_notify_types(mock_get):
    """NotifyNotifico() sends all four notification types successfully."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_get.return_value = response

    obj = NotifyNotifico(
        project_id="1234",
        msghook="validHook",
        color=True,
        prefix=True,
    )

    for notify_type in (
        NotifyType.INFO,
        NotifyType.SUCCESS,
        NotifyType.WARNING,
        NotifyType.FAILURE,
    ):
        mock_get.reset_mock()
        assert obj.send(body="msg", notify_type=notify_type) is True
        assert mock_get.call_count == 1


@mock.patch("requests.get")
def test_plugin_notifico_color_prefix_flags(mock_get):
    """NotifyNotifico() color=False strips IRC codes; prefix=False omits it."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_get.return_value = response

    # color=False, prefix=False -- payload should be the raw body
    obj = NotifyNotifico(
        project_id="1234",
        msghook="validHook",
        color=False,
        prefix=False,
    )
    assert obj.send(body="plain text") is True
    payload = mock_get.call_args[1]["params"]["payload"]
    assert payload == "plain text"

    # color=True, prefix=True -- payload contains the prefix bracket
    mock_get.reset_mock()
    obj2 = NotifyNotifico(
        project_id="1234",
        msghook="validHook",
        color=True,
        prefix=True,
    )
    assert obj2.send(body="colored text", notify_type=NotifyType.INFO) is True
    payload2 = mock_get.call_args[1]["params"]["payload"]
    assert "colored text" in payload2
    assert "[" in payload2


@mock.patch("requests.get")
def test_plugin_notifico_native_url(mock_get):
    """NotifyNotifico() parse_native_url() parses n.tkte.ch URLs."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_get.return_value = response

    # Standard native URL
    result = NotifyNotifico.parse_native_url(
        "https://n.tkte.ch/h/2144/uJmKaBW9WFk42miB146ci3Kj"
    )
    assert result is not None
    obj = NotifyNotifico(**result)
    assert obj.mode == NotificoMode.OFFICIAL
    assert obj.project_id == "2144"
    assert obj.msghook == "uJmKaBW9WFk42miB146ci3Kj"
    assert obj.send(body="test") is True

    # Non-matching URL returns None
    assert (
        NotifyNotifico.parse_native_url("https://other.host/h/1/abc") is None
    )
