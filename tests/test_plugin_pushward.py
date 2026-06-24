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

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, AppriseAsset, NotifyType
from apprise.plugins.pushward import NotifyPushWard

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "pushward://",
        {
            # No API Key specified
            "instance": TypeError,
        },
    ),
    (
        "pushward://invalid",
        {
            # API Key does not match the hlk_ pattern
            "instance": TypeError,
        },
    ),
    (
        "pushward://hlk_abc123",
        {
            # A valid API Key
            "instance": NotifyPushWard,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pushward://h...3/",
        },
    ),
    (
        "pushward://?apikey=hlk_abc123",
        {
            # API Key provided as a query argument
            "instance": NotifyPushWard,
            "privacy_url": "pushward://h...3/",
        },
    ),
    (
        "pushward://hlk_abc123?level=critical&volume=0.8",
        {
            # critical level with a volume
            "instance": NotifyPushWard,
            "privacy_url": "pushward://h...3/",
        },
    ),
    (
        "pushward://hlk_abc123?level=invalid",
        {
            # Invalid level provided
            "instance": TypeError,
        },
    ),
    (
        "pushward://hlk_abc123?volume=2.0",
        {
            # Volume out of range
            "instance": TypeError,
        },
    ),
    (
        "pushward://hlk_abc123?volume=invalid",
        {
            # Volume that cannot be parsed as a float
            "instance": TypeError,
        },
    ),
    (
        "pushward://hlk_abc123",
        {
            "instance": NotifyPushWard,
            # Force a failure with a known response code
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "pushward://hlk_abc123",
        {
            "instance": NotifyPushWard,
            # Throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "pushward://hlk_abc123",
        {
            "instance": NotifyPushWard,
            # Drive it through a series of socket exceptions
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_pushward_urls():
    """NotifyPushWard() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_pushward_edge_cases():
    """NotifyPushWard() Edge Cases."""

    # No API Key
    with pytest.raises(TypeError):
        NotifyPushWard(apikey=None)

    # Whitespace only API Key
    with pytest.raises(TypeError):
        NotifyPushWard(apikey="  ")

    # API Key that does not match the hlk_ pattern
    with pytest.raises(TypeError):
        NotifyPushWard(apikey="invalid")

    # Invalid level
    with pytest.raises(TypeError):
        NotifyPushWard(apikey="hlk_abc123", level="invalid")

    # Volume above the allowable range
    with pytest.raises(TypeError):
        NotifyPushWard(apikey="hlk_abc123", volume=2.0)

    # Volume below the allowable range
    with pytest.raises(TypeError):
        NotifyPushWard(apikey="hlk_abc123", volume=-0.5)

    # Volume that cannot be coerced to a float
    with pytest.raises(TypeError):
        NotifyPushWard(apikey="hlk_abc123", volume="invalid")


@mock.patch("requests.post")
def test_plugin_pushward_send(mock_post):
    """NotifyPushWard() a successful (200) send."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate("pushward://hlk_abc123")
    assert isinstance(obj, NotifyPushWard)
    assert obj.notify(title="title", body="body") is True

    assert mock_post.call_count == 1
    details = mock_post.call_args
    assert details[0][0] == "https://api.pushward.app/notifications"

    headers = details[1]["headers"]
    assert headers["Authorization"] == "Bearer hlk_abc123"
    assert headers["User-Agent"] == obj.app_id

    payload = loads(details[1]["data"])
    assert payload["title"] == "title"
    assert payload["body"] == "body"
    # NotifyType.INFO maps to the "active" level
    assert payload["level"] == "active"
    # An icon is attached (the default asset provides an image mask)
    assert "icon_url" in payload
    # No volume is sent for a non-critical notification
    assert "volume" not in payload


@mock.patch("requests.post")
def test_plugin_pushward_created(mock_post):
    """NotifyPushWard() treats a 201 Created response as success."""

    response = mock.Mock()
    response.status_code = requests.codes.created
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate("pushward://hlk_abc123")
    assert obj.notify(title="title", body="body") is True


@mock.patch("requests.post")
def test_plugin_pushward_level_override(mock_post):
    """NotifyPushWard() honors an explicit ?level= override."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate("pushward://hlk_abc123?level=passive")
    assert isinstance(obj, NotifyPushWard)
    assert obj.level == "passive"
    assert obj.notify(title="t", body="b") is True

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["level"] == "passive"


@mock.patch("requests.post")
def test_plugin_pushward_notify_type_mapping(mock_post):
    """NotifyPushWard() derives the level from notify_type when unset."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate("pushward://hlk_abc123")
    assert (
        obj.notify(title="t", body="b", notify_type=NotifyType.WARNING) is True
    )

    payload = loads(mock_post.call_args[1]["data"])
    # WARNING maps to the "time-sensitive" level
    assert payload["level"] == "time-sensitive"


@mock.patch("requests.post")
def test_plugin_pushward_critical_volume(mock_post):
    """NotifyPushWard() sends a volume only for critical notifications."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "pushward://hlk_abc123?level=critical&volume=0.8"
    )
    assert isinstance(obj, NotifyPushWard)
    assert obj.level == "critical"
    assert obj.volume == 0.8
    assert obj.notify(title="t", body="b") is True

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["level"] == "critical"
    assert payload["volume"] == 0.8

    # The volume is dropped when the level is not critical
    obj = Apprise.instantiate("pushward://hlk_abc123?level=active&volume=0.5")
    assert obj.notify(title="t", body="b") is True
    payload = loads(mock_post.call_args[1]["data"])
    assert "volume" not in payload


@mock.patch("requests.post")
def test_plugin_pushward_no_image(mock_post):
    """NotifyPushWard() omits icon_url when no image is available."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    asset = AppriseAsset(image_url_mask=None)
    obj = Apprise.instantiate("pushward://hlk_abc123", asset=asset)
    assert obj.notify(title="t", body="b") is True

    payload = loads(mock_post.call_args[1]["data"])
    assert "icon_url" not in payload


@mock.patch("requests.post")
def test_plugin_pushward_empty_title(mock_post):
    """NotifyPushWard() falls back to a default when the title is empty."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    # No title provided; falls back to the asset descriptor
    obj = Apprise.instantiate("pushward://hlk_abc123")
    assert obj.notify(body="body only") is True

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"]
    assert payload["title"] == obj.app_desc
    assert payload["body"] == "body only"

    # When the descriptor is also empty, fall back to the application id
    asset = AppriseAsset(app_desc="")
    obj = Apprise.instantiate("pushward://hlk_abc123", asset=asset)
    assert obj.notify(body="body only") is True

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"] == obj.app_id


@mock.patch("requests.post")
def test_plugin_pushward_url_roundtrip(mock_post):
    """NotifyPushWard() url() round-trips losslessly."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "pushward://hlk_abc123?level=critical&volume=0.8"
    )
    assert isinstance(obj, NotifyPushWard)

    # Regenerate the URL and re-instantiate
    obj2 = Apprise.instantiate(obj.url())
    assert isinstance(obj2, NotifyPushWard)
    assert obj.url_identifier == obj2.url_identifier
    assert obj2.apikey == "hlk_abc123"
    assert obj2.level == "critical"
    assert obj2.volume == 0.8


def test_plugin_pushward_parse_url():
    """NotifyPushWard() parse_url() behavior."""

    # An unparseable (non-string) URL returns None
    assert NotifyPushWard.parse_url(None) is None

    # API Key carried in the host
    results = NotifyPushWard.parse_url("pushward://hlk_abc123")
    assert results["apikey"] == "hlk_abc123"

    # API Key carried in a query argument (overrides the host)
    results = NotifyPushWard.parse_url("pushward://?apikey=hlk_xyz")
    assert results["apikey"] == "hlk_xyz"

    # level + volume carried in the query
    results = NotifyPushWard.parse_url(
        "pushward://hlk_abc123?level=critical&volume=0.5"
    )
    assert results["apikey"] == "hlk_abc123"
    assert results["level"] == "critical"
    assert results["volume"] == "0.5"

    # Case is preserved on the key (hlk_ keys are case-sensitive)
    results = NotifyPushWard.parse_url("pushward://hlk_AbC123")
    assert results["apikey"] == "hlk_AbC123"
