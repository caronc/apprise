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

import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

import apprise
from apprise.plugins.trigv import NotifyTrigv

logging.disable(logging.CRITICAL)

VALID_API_KEY = "trgv_a1b2c3d4_0123456789abcdef0123456789abcdef"

apprise_url_tests = (
    (
        "trigvs://",
        {
            "instance": TypeError,
        },
    ),
    (
        "trigv://",
        {
            "instance": TypeError,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}",
        {
            "instance": NotifyTrigv,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}/general",
        {
            "instance": NotifyTrigv,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}/deploys",
        {
            "instance": NotifyTrigv,
        },
    ),
    (
        f"trigv://{VALID_API_KEY}@trigv-platform.test/general",
        {
            "instance": NotifyTrigv,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}/?url=https://example.com",
        {
            "instance": NotifyTrigv,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}/?delivery_urgency=time_sensitive",
        {
            "instance": NotifyTrigv,
        },
    ),
    (
        "trigvs://not-a-valid-key",
        {
            "instance": TypeError,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}/INVALID CHANNEL/",
        {
            "instance": TypeError,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}",
        {
            "instance": NotifyTrigv,
            "response": False,
            "requests_response_code": requests.codes.unauthorized,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}",
        {
            "instance": NotifyTrigv,
            "response": False,
            "requests_response_code": requests.codes.unprocessable_entity,
        },
    ),
    (
        f"trigvs://{VALID_API_KEY}",
        {
            "instance": NotifyTrigv,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_trigv_urls():
    """NotifyTrigv() Apprise URLs."""

    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_trigv_general(mock_post):
    """NotifyTrigv() General Checks."""

    response = mock.Mock()
    response.content = b'{"event":{"public_id":"evt_test","status":"queued"}}'
    response.status_code = requests.codes.accepted
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(f"trigvs://{VALID_API_KEY}/alerts")
    assert isinstance(obj, NotifyTrigv)
    assert obj.channel == "alerts"

    assert (
        obj.notify(
            body="Backup failed",
            title="Cron",
            notify_type=apprise.NotifyType.FAILURE,
        )
        is True
    )

    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == (
        "https://api.trigv.com/api/v1/events"
    )

    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers["Authorization"] == f"Bearer {VALID_API_KEY}"
    assert headers["Content-Type"] == "application/json"

    import json

    payload = json.loads(mock_post.call_args_list[0][1]["data"])
    assert payload["channel"] == "alerts"
    assert payload["title"] == "Cron"
    assert payload["description"] == "Backup failed"
    assert payload["level"] == "error"
    assert payload["delivery_urgency"] == "time_sensitive"


@mock.patch("requests.post")
def test_plugin_trigv_local_host(mock_post):
    """NotifyTrigv() custom hostname for local development."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    mock_post.return_value = response

    obj = apprise.Apprise.instantiate(
        f"trigv://{VALID_API_KEY}@trigv-platform.test/general"
    )
    assert isinstance(obj, NotifyTrigv)

    assert obj.notify(body="Hello", title="Test") is True
    assert (
        mock_post.call_args_list[0][0][0]
        == "http://trigv-platform.test/api/v1/events"
    )


@mock.patch("requests.post")
def test_plugin_trigv_duplicate_success(mock_post):
    """NotifyTrigv() treats HTTP 200 idempotent duplicate as success."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    obj = NotifyTrigv(api_key=VALID_API_KEY)
    assert obj.send(body="test", title="title") is True


def test_plugin_trigv_invalid_delivery_urgency():
    """NotifyTrigv() rejects unknown delivery urgency."""

    with pytest.raises(TypeError):
        NotifyTrigv(api_key=VALID_API_KEY, delivery_urgency="critical")


@mock.patch("requests.post")
def test_plugin_trigv_url_roundtrip(mock_post):
    """NotifyTrigv() url() round-trips optional query parameters."""

    mock_post.return_value = mock.Mock()
    mock_post.return_value.status_code = requests.codes.accepted

    obj = NotifyTrigv(
        api_key=VALID_API_KEY,
        channel="deploys",
        supplemental_url="https://example.com/run/1",
        delivery_urgency="time_sensitive",
        event_type="deploy.completed",
    )

    generated = obj.url()
    assert "deploys" in generated
    assert "url=" in generated
    assert "delivery_urgency=time_sensitive" in generated
    assert "event_type=deploy.completed" in generated

    parsed = NotifyTrigv.parse_url(generated)
    obj2 = NotifyTrigv(**parsed)
    assert obj2.channel == "deploys"
    assert obj2.supplemental_url == "https://example.com/run/1"
    assert obj2.delivery_urgency == "time_sensitive"
    assert obj2.event_type == "deploy.completed"
