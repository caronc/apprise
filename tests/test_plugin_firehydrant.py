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

import json
import logging
from unittest import mock
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.firehydrant import FireHydrantAction, NotifyFireHydrant

logging.disable(logging.CRITICAL)

# A realistic (JWT shaped) webhook token
TOKEN = (
    "eyJhbGciOiJIUzI1NiJ9.eyJvcmdhbml6YXRpb25faWQiOiJhYmMtMTIzIn0"
    ".Ab-Cd_EfGhIjKlMnOpQrStUvWxYz0123456789"
)

# Our Testing URLs
apprise_url_tests = (
    (
        "firehydrant://",
        {
            # No token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "firehydrant://invalid!token",
        {
            # An invalid token
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "firehydrant://{}".format(TOKEN),
        {
            # A valid token
            "instance": NotifyFireHydrant,
            "requests_response_code": requests.codes.accepted,
            "privacy_url": "firehydrant://e...9/",
        },
    ),
    (
        "firehydrant://?token={}".format(TOKEN),
        {
            # The token supplied as an argument
            "instance": NotifyFireHydrant,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "firehydrant://{}?action=resolve&level=fatal&priority=low"
        "&dedup=disk-full&click=https://example.com/alert"
        "&tags=service:api,env:prod&image=no&+team=sre".format(TOKEN),
        {
            # Every option in use
            "instance": NotifyFireHydrant,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "firehydrant://{}?action=invalid".format(TOKEN),
        {
            # An invalid action
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "firehydrant://{}?level=invalid".format(TOKEN),
        {
            # An invalid level
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "firehydrant://{}?priority=invalid".format(TOKEN),
        {
            # An invalid priority
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "https://signals.firehydrant.com/v1/process/{}".format(TOKEN),
        {
            # The URL FireHydrant shows on its Sources page
            "instance": NotifyFireHydrant,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "https://signals.firehydrant.com/v1/process/{}/?priority=high".format(
            TOKEN
        ),
        {
            # The same URL with an option added
            "instance": NotifyFireHydrant,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "firehydrant://{}".format(TOKEN),
        {
            "instance": NotifyFireHydrant,
            # A failure has been returned by the server
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "firehydrant://{}".format(TOKEN),
        {
            "instance": NotifyFireHydrant,
            # An unknown response code
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "firehydrant://{}".format(TOKEN),
        {
            "instance": NotifyFireHydrant,
            # Socket errors are handled
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_firehydrant_urls():
    """NotifyFireHydrant() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_firehydrant_payload(mock_post):
    """NotifyFireHydrant() builds the event it sends."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b'{"success": true}'
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "firehydrant://{}?action=res&level=fa&priority=m&dedup=disk-full"
        "&click=https://example.com/alert&tags=service:api,env:prod"
        "&+team=sre".format(TOKEN)
    )
    assert isinstance(obj, NotifyFireHydrant)
    assert obj.action == FireHydrantAction.RESOLVE

    # A title and a body with characters that need no escaping
    assert obj.notify(
        title="Disk & <db01>",
        body="Usage at 95% on _db01_ * # <",
        notify_type=NotifyType.FAILURE,
    )

    # One post to our webhook with no extra credentials
    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "signals.firehydrant.com"
    assert urlparse(url).path == "/v1/process/{}".format(TOKEN)
    assert "Authorization" not in mock_post.call_args[1]["headers"]

    payload = json.loads(mock_post.call_args[1]["data"])
    image = payload.pop("images")
    assert payload == {
        "summary": "Disk & <db01>",
        "body": "Usage at 95% on _db01_ * # <",
        "level": "FATAL",
        "status": "CLOSED",
        "idempotency_key": "disk-full",
        "annotations": {
            "signals.firehydrant.com/notification-priority": "MEDIUM",
            "team": "sre",
        },
        "tags": ["env:prod", "service:api"],
        "links": [
            {
                "href": "https://example.com/alert",
                "text": "https://example.com/alert",
            }
        ],
    }
    assert len(image) == 1
    assert image[0]["alt"] == "failure"
    assert image[0]["src"].startswith("http")

    # Our own annotation can replace the priority one
    mock_post.reset_mock()
    obj = NotifyFireHydrant(
        token=TOKEN,
        priority="high",
        annotations={
            "signals.firehydrant.com/notification-priority": "LOW",
        },
    )
    assert obj.notify(body="test")
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["annotations"] == {
        "signals.firehydrant.com/notification-priority": "LOW",
    }

    # Without a title, the body stands in for the summary and is capped
    mock_post.reset_mock()
    obj = NotifyFireHydrant(token=TOKEN, include_image=False)
    assert obj.notify(body="x" * 300)
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["summary"] == "x" * obj.title_maxlen
    assert payload["body"] == "x" * 300
    for key in ("annotations", "tags", "links", "images"):
        assert key not in payload

    # A passthrough body reaches FireHydrant untouched
    mock_post.reset_mock()
    assert obj.notify(body="**bold** & <b>html</b>", body_format=None)
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["body"] == "**bold** & <b>html</b>"


@mock.patch("requests.post")
def test_plugin_firehydrant_level(mock_post):
    """NotifyFireHydrant() picks a level from the notification type."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    obj = NotifyFireHydrant(token=TOKEN)
    for notify_type, level in (
        (NotifyType.INFO, "INFO"),
        (NotifyType.SUCCESS, "INFO"),
        (NotifyType.WARNING, "WARN"),
        (NotifyType.FAILURE, "ERROR"),
    ):
        assert obj.notify(body="test", notify_type=notify_type)
        payload = json.loads(mock_post.call_args[1]["data"])
        assert payload["level"] == level

    # A level that was set always wins
    obj = NotifyFireHydrant(token=TOKEN, level="WARN")
    assert obj.notify(body="test", notify_type=NotifyType.FAILURE)
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["level"] == "WARN"


@mock.patch("requests.post")
def test_plugin_firehydrant_action_map(mock_post):
    """NotifyFireHydrant() resolves on success and opens otherwise."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    def sent():
        return json.loads(mock_post.call_args[1]["data"])

    # The default action maps the notification type
    obj = NotifyFireHydrant(token=TOKEN)
    assert obj.action == FireHydrantAction.MAP
    for notify_type, status in (
        (NotifyType.INFO, "OPEN"),
        (NotifyType.WARNING, "OPEN"),
        (NotifyType.FAILURE, "OPEN"),
        (NotifyType.SUCCESS, "CLOSED"),
    ):
        assert obj.notify(
            title="Disk full", body="db01", notify_type=notify_type
        )
        assert sent()["status"] == status

    # The same title always produces the same key, so a success
    # resolves the alert a failure opened
    assert obj.notify(
        title="Disk full", body="a", notify_type=NotifyType.FAILURE
    )
    opened = sent()["idempotency_key"]
    assert obj.notify(
        title="Disk full", body="b", notify_type=NotifyType.SUCCESS
    )
    assert sent()["idempotency_key"] == opened

    # A different title is a different alert
    assert obj.notify(title="CPU hot", body="a")
    assert sent()["idempotency_key"] != opened

    # Without a title, the first line of the message is used
    assert obj.notify(body="Disk full\nat 95%")
    assert sent()["idempotency_key"] == opened

    # Trigger ignores the notification type and opens a new alert
    # every time, even with the same title
    obj = NotifyFireHydrant(token=TOKEN, action="trigger")
    assert obj.notify(
        title="Disk full", body="ok", notify_type=NotifyType.SUCCESS
    )
    assert sent()["status"] == "OPEN"
    first = sent()["idempotency_key"]
    assert obj.notify(title="Disk full", body="ok")
    assert sent()["idempotency_key"] != first


def test_plugin_firehydrant_init():
    """NotifyFireHydrant() init and url round trip."""

    obj = NotifyFireHydrant(
        token=TOKEN,
        action="trigger",
        level="error",
        priority="low",
        dedup="  key  ",
        click="  ",
        tags="service:api, env:prod",
        include_image=False,
        annotations={"a": "b"},
    )
    assert obj.action == FireHydrantAction.TRIGGER
    assert obj.dedup == "key"
    assert obj.click is None
    assert len(obj) == 1

    # The URL survives a round trip
    result = NotifyFireHydrant.parse_url(obj.url())
    obj2 = NotifyFireHydrant(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert obj2.action == FireHydrantAction.TRIGGER
    assert obj2.level == "error"
    assert obj2.priority == "low"
    assert obj2.dedup == "key"
    assert obj2.event_tags == obj.event_tags
    assert obj2.include_image is False
    assert obj2.annotations == {"a": "b"}

    # The privacy URL hides the token
    assert TOKEN not in obj.url(privacy=True)

    # A missing or blank token is refused
    for token in (None, "  "):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyFireHydrant(token=token)

    # A different token is a different connection
    other = NotifyFireHydrant(token="abc.def.ghi")
    assert other.url_identifier != obj.url_identifier


@mock.patch("requests.post")
def test_plugin_firehydrant_retry_key(mock_post):
    """NotifyFireHydrant() keeps its trigger key across retries."""

    bad = mock.Mock()
    bad.status_code = requests.codes.bad_request
    bad.content = b'{"errors": ["summary is required"]}'
    good = mock.Mock()
    good.status_code = requests.codes.accepted
    good.content = b'{"success": true}'
    mock_post.side_effect = [bad, good]

    aobj = Apprise()
    assert aobj.add(
        "firehydrant://{}?action=trigger&retry=1&wait=0".format(TOKEN)
    )
    with mock.patch("apprise.apprise.time.sleep"):
        assert aobj.notify(body="Server down")

    # The retry reused the key so FireHydrant sees one alert
    assert mock_post.call_count == 2
    first = json.loads(mock_post.call_args_list[0][1]["data"])
    second = json.loads(mock_post.call_args_list[1][1]["data"])
    assert first["idempotency_key"] == second["idempotency_key"]
