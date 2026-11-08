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
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.pushward import NotifyPushWard, pushward_level

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "pushward://",
        {
            # No API Key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "pushward://invalid",
        {
            # API Key does not match the hlk_ pattern
            "instance": AppriseImproperlyConfigured,
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
        "pushward://hlk_abc123?info=passive&failure=critical",
        {
            # per-notification-type level overrides
            "instance": NotifyPushWard,
            "privacy_url": "pushward://h...3/",
        },
    ),
    (
        "pushward://hlk_abc123?info=bogus",
        {
            # An invalid per-type level
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "pushward://hlk_abc123?level=invalid",
        {
            # Invalid level provided
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "pushward://hlk_abc123?volume=2.0",
        {
            # Volume out of range
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "pushward://hlk_abc123?volume=invalid",
        {
            # Volume that cannot be parsed as a float
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "pushward://hlk_abc123?ack=yes",
        {
            # Acknowledgement with the default repeat and expire
            "instance": NotifyPushWard,
            "privacy_url": "pushward://h...3/",
            "url_matches": r"ack=yes",
        },
    ),
    (
        "pushward://hlk_abc123?ack=yes&repeat=120&expire=7200",
        {
            # Acknowledgement with a custom repeat and expire
            "instance": NotifyPushWard,
            "privacy_url": "pushward://h...3/",
            "url_matches": r"repeat=120.*expire=7200",
        },
    ),
    (
        "pushward://hlk_abc123?repeat=30&expire=10800",
        {
            # repeat and expire are accepted without ack
            "instance": NotifyPushWard,
            "privacy_url": "pushward://h...3/",
        },
    ),
    (
        "pushward://hlk_abc123?ack=no&snooze=15,60",
        {
            # snooze only conflicts with an enabled ack
            "instance": NotifyPushWard,
            "privacy_url": "pushward://h...3/",
            "url_matches": r"snooze=15%2C60",
        },
    ),
    (
        "pushward://hlk_abc123?url=https%3A%2F%2Fexample.com%2Fa&subtitle=Sub"
        "&thread=t1&collapse=c1",
        {
            # All of the optional strings
            "instance": NotifyPushWard,
            "privacy_url": "pushward://h...3/",
            "url_matches": r"url=https.*subtitle=Sub.*thread=t1.*collapse=c1",
        },
    ),
    # repeat must be an integer from 30 to 3600
    (
        "pushward://hlk_abc123?repeat=29",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?repeat=3601",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?repeat=abc",
        {"instance": AppriseImproperlyConfigured},
    ),
    # expire must be an integer from 60 to 10800
    (
        "pushward://hlk_abc123?expire=59",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?expire=10801",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?expire=abc",
        {"instance": AppriseImproperlyConfigured},
    ),
    # snooze takes 1 to 3 different integers from 1 to 1440
    (
        "pushward://hlk_abc123?snooze=0",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?snooze=1441",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?snooze=abc",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?snooze=1,2,3,4",
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?snooze=15,15",
        {"instance": AppriseImproperlyConfigured},
    ),
    # The optional strings are limited in length
    (
        "pushward://hlk_abc123?subtitle=" + "a" * 257,
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?thread=" + "a" * 129,
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?collapse=" + "a" * 65,
        {"instance": AppriseImproperlyConfigured},
    ),
    (
        "pushward://hlk_abc123?url=" + "a" * 2049,
        {"instance": AppriseImproperlyConfigured},
    ),
    # The server refuses snooze together with acknowledge
    (
        "pushward://hlk_abc123?ack=yes&snooze=15",
        {"instance": AppriseImproperlyConfigured},
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
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyPushWard(apikey=None)

    # Whitespace only API Key
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyPushWard(apikey="  ")

    # API Key that does not match the hlk_ pattern
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyPushWard(apikey="invalid")

    # Invalid level
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyPushWard(apikey="hlk_abc123", level="invalid")

    # Volume above the allowable range
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyPushWard(apikey="hlk_abc123", volume=2.0)

    # Volume below the allowable range
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyPushWard(apikey="hlk_abc123", volume=-0.5)

    # Volume that cannot be coerced to a float
    with pytest.raises(AppriseImproperlyConfigured):
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
    assert bool(obj.notify(title="title", body="body")) is True

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
    assert payload["source"] == "apprise"
    assert payload["source_display_name"] == "Apprise"
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
    assert bool(obj.notify(title="title", body="body")) is True


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
    assert bool(obj.notify(title="t", body="b")) is True

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
        bool(obj.notify(title="t", body="b", notify_type=NotifyType.WARNING))
        is True
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
    assert bool(obj.notify(title="t", body="b")) is True

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["level"] == "critical"
    assert payload["volume"] == 0.8

    # The volume is dropped when the level is not critical
    obj = Apprise.instantiate("pushward://hlk_abc123?level=active&volume=0.5")
    assert bool(obj.notify(title="t", body="b")) is True
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
    assert bool(obj.notify(title="t", body="b")) is True

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
    assert bool(obj.notify(body="body only")) is True

    payload = loads(mock_post.call_args[1]["data"])
    assert payload["title"]
    assert payload["title"] == obj.app_desc
    assert payload["body"] == "body only"

    # When the descriptor is also empty, fall back to the application id
    asset = AppriseAsset(app_desc="")
    obj = Apprise.instantiate("pushward://hlk_abc123", asset=asset)
    assert bool(obj.notify(body="body only")) is True

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


def test_plugin_pushward_level_resolution():
    """NotifyPushWard() level short-form resolution."""

    # Full names, short-forms, and unique single-letter prefixes
    assert pushward_level("passive") == "passive"
    assert pushward_level("crit") == "critical"
    assert pushward_level("c") == "critical"
    assert pushward_level("t") == "time-sensitive"
    assert pushward_level("ACTIVE") == "active"

    # Empty or non-matching input resolves to None
    assert pushward_level("") is None
    assert pushward_level("   ") is None
    assert pushward_level("bogus") is None


@mock.patch("requests.post")
def test_plugin_pushward_per_type_levels(mock_post):
    """NotifyPushWard() per-notification-type level overrides."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "pushward://hlk_abc123?info=passive&failure=crit"
    )
    assert isinstance(obj, NotifyPushWard)
    assert obj.level_map[NotifyType.INFO] == "passive"
    # Short-form resolves to the canonical level
    assert obj.level_map[NotifyType.FAILURE] == "critical"
    # Untouched types keep their defaults
    assert obj.level_map[NotifyType.WARNING] == "time-sensitive"

    assert (
        bool(obj.notify(title="t", body="b", notify_type=NotifyType.INFO))
        is True
    )
    assert loads(mock_post.call_args[1]["data"])["level"] == "passive"

    assert (
        bool(obj.notify(title="t", body="b", notify_type=NotifyType.FAILURE))
        is True
    )
    assert loads(mock_post.call_args[1]["data"])["level"] == "critical"

    # A global ?level= still forces every type
    obj = Apprise.instantiate(
        "pushward://hlk_abc123?level=passive&info=critical"
    )
    assert (
        bool(obj.notify(title="t", body="b", notify_type=NotifyType.INFO))
        is True
    )
    assert loads(mock_post.call_args[1]["data"])["level"] == "passive"


@mock.patch("requests.post")
def test_plugin_pushward_default_payload(mock_post):
    """NotifyPushWard() sends only its base keys by default."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate("pushward://hlk_abc123")
    assert bool(obj.notify(title="t", body="b")) is True
    assert loads(mock_post.call_args[1]["data"]) == {
        "title": "t",
        "body": "b",
        "level": "active",
        "source": "apprise",
        "source_display_name": "Apprise",
        "icon_url": obj.image_url(NotifyType.INFO),
    }

    # None of the new options are emitted unless they were set
    for key in (
        "ack",
        "repeat",
        "expire",
        "url",
        "subtitle",
        "thread",
        "collapse",
        "snooze",
    ):
        assert f"{key}=" not in obj.url()

    obj = Apprise.instantiate(
        "pushward://hlk_abc123?level=critical&volume=0.8"
    )
    assert bool(obj.notify(title="t", body="b")) is True
    assert loads(mock_post.call_args[1]["data"]) == {
        "title": "t",
        "body": "b",
        "level": "critical",
        "source": "apprise",
        "source_display_name": "Apprise",
        "volume": 0.8,
        "icon_url": obj.image_url(NotifyType.INFO),
    }


@mock.patch("requests.post")
def test_plugin_pushward_options(mock_post):
    """NotifyPushWard() sends each option under its JSON key."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    keys = {"url", "subtitle", "thread_id", "collapse_id", "snooze"}
    for query, key, expected in (
        ("url=https%3A%2F%2Fexample.com%2Fa", "url", "https://example.com/a"),
        ("subtitle=Sub", "subtitle", "Sub"),
        ("thread=t1", "thread_id", "t1"),
        ("collapse=c1", "collapse_id", "c1"),
        ("snooze=15,60", "snooze", [15, 60]),
        # The order given is kept
        ("snooze=60,15", "snooze", [60, 15]),
    ):
        obj = Apprise.instantiate(f"pushward://hlk_abc123?{query}")
        assert isinstance(obj, NotifyPushWard)
        assert bool(obj.notify(title="t", body="b")) is True

        payload = loads(mock_post.call_args[1]["data"])
        assert payload[key] == expected
        assert not keys.difference({key}).intersection(payload)
        assert "acknowledge" not in payload


@mock.patch("requests.post")
def test_plugin_pushward_acknowledge(mock_post):
    """NotifyPushWard() sends repeat and expire only with ack."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    # Both keys are always sent, with their defaults
    obj = Apprise.instantiate("pushward://hlk_abc123?ack=yes")
    assert isinstance(obj, NotifyPushWard)
    assert bool(obj.notify(title="t", body="b")) is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["acknowledge"] == {
        "repeat_seconds": 60,
        "expire_seconds": 3600,
    }
    assert "repeat=" not in obj.url()
    assert "expire=" not in obj.url()

    # An explicit default is not emitted either
    obj = Apprise.instantiate(
        "pushward://hlk_abc123?ack=yes&repeat=60&expire=3600"
    )
    assert "repeat=" not in obj.url()
    assert "expire=" not in obj.url()

    # Custom values
    obj = Apprise.instantiate(
        "pushward://hlk_abc123?ack=yes&repeat=120&expire=7200"
    )
    assert bool(obj.notify(title="t", body="b")) is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["acknowledge"] == {
        "repeat_seconds": 120,
        "expire_seconds": 7200,
    }

    # repeat and expire on their own send nothing, but are kept in the URL
    obj = Apprise.instantiate("pushward://hlk_abc123?repeat=120&expire=7200")
    assert bool(obj.notify(title="t", body="b")) is True
    assert "acknowledge" not in loads(mock_post.call_args[1]["data"])
    assert "repeat=120" in obj.url()
    assert "expire=7200" in obj.url()
    assert "ack=" not in obj.url()

    # ack=no is the same as leaving it out
    obj = Apprise.instantiate("pushward://hlk_abc123?ack=no")
    assert bool(obj.notify(title="t", body="b")) is True
    assert "acknowledge" not in loads(mock_post.call_args[1]["data"])
    assert "ack=" not in obj.url()


@mock.patch("requests.post")
def test_plugin_pushward_acknowledge_passive(mock_post):
    """NotifyPushWard() drops acknowledge when the level is passive."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    # A forced level applies to every notification type
    obj = Apprise.instantiate("pushward://hlk_abc123?ack=yes&level=passive")
    assert bool(obj.notify(title="t", body="b")) is True
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["level"] == "passive"
    assert "acknowledge" not in payload

    # A per-type level only applies to that notification type
    obj = Apprise.instantiate("pushward://hlk_abc123?ack=yes&info=passive")
    assert (
        bool(obj.notify(title="t", body="b", notify_type=NotifyType.INFO))
        is True
    )
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["level"] == "passive"
    assert "acknowledge" not in payload

    assert (
        bool(obj.notify(title="t", body="b", notify_type=NotifyType.WARNING))
        is True
    )
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["level"] == "time-sensitive"
    assert payload["acknowledge"] == {
        "repeat_seconds": 60,
        "expire_seconds": 3600,
    }


def test_plugin_pushward_option_limits():
    """NotifyPushWard() accepts the limits of each option."""

    for repeat in (30, 3600):
        assert NotifyPushWard("hlk_abc123", repeat=repeat).repeat == repeat

    for expire in (60, 10800):
        assert NotifyPushWard("hlk_abc123", expire=expire).expire == expire

    obj = NotifyPushWard(
        "hlk_abc123",
        supplemental_url="a" * 2048,
        subtitle="a" * 256,
        thread_id="a" * 128,
        collapse_id="a" * 64,
        snooze="1,720,1440",
    )
    assert len(obj.supplemental_url) == 2048
    assert len(obj.subtitle) == 256
    assert len(obj.thread_id) == 128
    assert len(obj.collapse_id) == 64
    assert obj.snooze == [1, 720, 1440]

    # YAML configuration can hand over values that are not strings
    assert NotifyPushWard("hlk_abc123", snooze=[15, 60]).snooze == [15, 60]
    assert NotifyPushWard("hlk_abc123", snooze=15).snooze == [15]
    assert NotifyPushWard("hlk_abc123", subtitle=42).subtitle == "42"

    for snooze in (
        [],
        0,
        "",
        [None],
        ["abc"],
        [15.5],
        [True, 2],
        [float("inf")],
    ):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyPushWard("hlk_abc123", snooze=snooze)

    # Anything but an integer is refused, in range or not
    for value in (object(), 90.5, float("inf")):
        for key in ("repeat", "expire"):
            with pytest.raises(AppriseImproperlyConfigured):
                NotifyPushWard("hlk_abc123", **{key: value})


@mock.patch("requests.post")
def test_plugin_pushward_options_roundtrip(mock_post):
    """NotifyPushWard() url() reproduces the payload of each option."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    strings = (
        "&url=https%3A%2F%2Fexample.com%2Fa%3Fb%3D1%26c%3D2"
        "&subtitle=Sub%20title&thread=t%2F1&collapse=c%201"
    )
    expected = {
        "url": "https://example.com/a?b=1&c=2",
        "subtitle": "Sub title",
        "thread_id": "t/1",
        "collapse_id": "c 1",
    }

    for url, extra in (
        # ack and snooze cannot be combined, so each has its own URL
        (
            "pushward://hlk_abc123?ack=yes&repeat=120&expire=7200" + strings,
            {
                **expected,
                "acknowledge": {
                    "repeat_seconds": 120,
                    "expire_seconds": 7200,
                },
            },
        ),
        (
            "pushward://hlk_abc123?snooze=60,15" + strings,
            {**expected, "snooze": [60, 15]},
        ),
        (
            "pushward://hlk_abc123?ack=yes&repeat=45&expire=90",
            {"acknowledge": {"repeat_seconds": 45, "expire_seconds": 90}},
        ),
        # An escape inside the link itself survives
        (
            "pushward://hlk_abc123?url=https%3A%2F%2Fx.test%2F%3Fq%3Da%2526b",
            {"url": "https://x.test/?q=a%26b"},
        ),
    ):
        obj = Apprise.instantiate(url)
        assert isinstance(obj, NotifyPushWard)
        assert bool(obj.notify(title="t", body="b")) is True
        payload = loads(mock_post.call_args[1]["data"])
        assert payload == {
            "title": "t",
            "body": "b",
            "level": "active",
            "source": "apprise",
            "source_display_name": "Apprise",
            "icon_url": obj.image_url(NotifyType.INFO),
            **extra,
        }

        obj2 = Apprise.instantiate(obj.url())
        assert isinstance(obj2, NotifyPushWard)
        assert obj.url_identifier == obj2.url_identifier
        assert bool(obj2.notify(title="t", body="b")) is True
        assert loads(mock_post.call_args[1]["data"]) == payload
