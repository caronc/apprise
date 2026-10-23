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

from apprise import Apprise, NotifyFormat, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.ilert import ILertAction, NotifyILert

logging.disable(logging.CRITICAL)

# A realistic integration key
KEY = "il1api0123456789abcdef0123456789abcdef"

# Our Testing URLs
apprise_url_tests = (
    (
        "ilert://",
        {
            # No integration key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "ilert://invalid!key",
        {
            # An invalid integration key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "ilert://{}".format(KEY),
        {
            # A valid integration key
            "instance": NotifyILert,
            "requests_response_code": requests.codes.accepted,
            "privacy_url": "ilert://i...f/",
        },
    ),
    (
        "ilert://?key={}".format(KEY),
        {
            # The key supplied as an argument
            "instance": NotifyILert,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "ilert://{}?action=ack&dedup=disk-full&priority=high&route=ops"
        "&click=https://example.com&image=no&+env=prod".format(KEY),
        {
            # Every option in use
            "instance": NotifyILert,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "ilert://{}?action=invalid".format(KEY),
        {
            # An invalid action
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "ilert://{}?priority=urgent".format(KEY),
        {
            # An invalid priority
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "ilert://{}".format(KEY),
        {
            "instance": NotifyILert,
            # A failure has been returned by the server
            "response": False,
            "requests_response_code": requests.codes.bad_request,
        },
    ),
    (
        "ilert://{}".format(KEY),
        {
            "instance": NotifyILert,
            # An unknown response code
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "ilert://{}".format(KEY),
        {
            "instance": NotifyILert,
            # Socket errors are handled
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_ilert_urls():
    """NotifyILert() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_ilert_payload(mock_post):
    """NotifyILert() builds the event it sends."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "ilert://{}?action=res&dedup=disk-full&priority=L&route=db-team"
        "&click=https://example.com/db01&image=no&+env=prod&+team=ops".format(
            KEY
        )
    )
    assert isinstance(obj, NotifyILert)
    assert obj.action == ILertAction.RESOLVE
    assert obj.priority == "low"

    # A title and a markdown body
    assert obj.notify(
        title="Disk & <db01>",
        body="Usage at **95%** on `_db01_`.",
        body_format=NotifyFormat.MARKDOWN,
    )

    # One post to the events API
    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "api.ilert.com"
    assert urlparse(url).path == "/api/events"
    headers = mock_post.call_args[1]["headers"]
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload == {
        "integrationKey": KEY,
        "eventType": "RESOLVE",
        "summary": "Disk & <db01>",
        "details": "Usage at **95%** on `_db01_`.",
        "alertKey": "disk-full",
        "priority": "LOW",
        "routingKey": "db-team",
        "links": [{"href": "https://example.com/db01"}],
        "labels": {"env": "prod", "team": "ops"},
    }

    # Without a title, the body becomes the summary without the escapes
    # Apprise added when converting text to markdown
    mock_post.reset_mock()
    obj = NotifyILert(key=KEY)
    assert obj.notify(
        body="Server_1 is *down*",
        body_format=NotifyFormat.TEXT,
        notify_type=NotifyType.FAILURE,
    )
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["summary"] == "Server_1 is *down*"
    assert payload["details"] == "Server\\_1 is \\*down\\*"
    assert payload["eventType"] == "ALERT"
    assert payload["images"][0]["src"].startswith("http")
    assert payload["images"][0]["alt"] == "failure"
    for field in ("priority", "routingKey", "links", "labels"):
        assert field not in payload

    # A passthrough body is used as the summary untouched and capped
    mock_post.reset_mock()
    assert obj.send(body="x" * 300, body_passthrough=True)
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["summary"] == "x" * obj.title_maxlen


@mock.patch("requests.post")
def test_plugin_ilert_actions(mock_post):
    """NotifyILert() picks the event type and alert key per action."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    def sent():
        return json.loads(mock_post.call_args[1]["data"])

    # The default action maps the notification type
    obj = NotifyILert(key=KEY)
    assert obj.action == ILertAction.MAP
    for notify_type, event_type in (
        (NotifyType.INFO, "ALERT"),
        (NotifyType.WARNING, "ALERT"),
        (NotifyType.FAILURE, "ALERT"),
        (NotifyType.SUCCESS, "RESOLVE"),
    ):
        assert obj.notify(
            title="Disk full", body="db01", notify_type=notify_type
        )
        assert sent()["eventType"] == event_type

    # The same title always produces the same alert key, so a success
    # resolves the alert a failure raised
    assert obj.notify(
        title="Disk full", body="a", notify_type=NotifyType.FAILURE
    )
    raised = sent()["alertKey"]
    assert obj.notify(
        title="Disk full", body="b", notify_type=NotifyType.SUCCESS
    )
    assert sent()["alertKey"] == raised

    # A different title is a different alert
    assert obj.notify(title="CPU hot", body="a")
    assert sent()["alertKey"] != raised

    # Without a title, the first line of the message is used
    assert obj.notify(body="Disk full\nat 95%")
    assert sent()["alertKey"] == raised

    # Trigger ignores the notification type and raises a new alert
    # every time, even with the same title
    obj = NotifyILert(key=KEY, action="trigger")
    assert obj.notify(
        title="Disk full", body="ok", notify_type=NotifyType.SUCCESS
    )
    assert sent()["eventType"] == "ALERT"
    first = sent()["alertKey"]
    assert obj.notify(title="Disk full", body="ok")
    assert sent()["alertKey"] != first

    # Acknowledge accepts the alert the title points to
    obj = NotifyILert(key=KEY, action="ACKNOWLEDGE")
    assert obj.notify(title="Disk full", body="on it")
    assert sent()["eventType"] == "ACCEPT"
    assert sent()["alertKey"] == raised

    # Resolve ignores the notification type
    obj = NotifyILert(key=KEY, action="r")
    assert obj.notify(body="bad", notify_type=NotifyType.FAILURE)
    assert sent()["eventType"] == "RESOLVE"


def test_plugin_ilert_init():
    """NotifyILert() init and url round trip."""

    obj = NotifyILert(
        key=KEY,
        action="trigger",
        dedup="  key  ",
        priority="  ",
        routing_key="  ",
        click="  ",
        include_image="no",
        labels={"a": "b"},
    )
    assert obj.action == ILertAction.TRIGGER
    assert obj.dedup == "key"
    assert obj.priority is None
    assert obj.routing_key is None
    assert obj.click is None
    assert obj.include_image is False
    assert len(obj) == 1

    # The URL survives a round trip
    result = NotifyILert.parse_url(obj.url())
    obj2 = NotifyILert(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert obj2.dedup == "key"
    assert obj2.labels == {"a": "b"}
    assert obj2.action == ILertAction.TRIGGER
    assert obj2.include_image is False

    # Every other option survives too
    obj = NotifyILert(
        key=KEY,
        priority="HIGH",
        routing_key="db-team",
        click="https://example.com",
    )
    result = NotifyILert.parse_url(obj.url())
    obj2 = NotifyILert(**result)
    assert obj2.priority == "high"
    assert obj2.routing_key == "db-team"
    assert obj2.click == "https://example.com"
    assert obj2.action == ILertAction.MAP
    assert obj2.include_image is True

    # A missing or blank key is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyILert(key="  ")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyILert(key=None)


@mock.patch("requests.post")
def test_plugin_ilert_retry_key(mock_post):
    """NotifyILert() keeps its trigger alert key across retries."""

    bad = mock.Mock()
    bad.status_code = requests.codes.internal_server_error
    bad.content = b""
    good = mock.Mock()
    good.status_code = requests.codes.accepted
    good.content = b""
    mock_post.side_effect = [bad, good]

    aobj = Apprise()
    assert aobj.add("ilert://{}?action=trigger&retry=1&wait=0".format(KEY))
    with mock.patch("apprise.apprise.time.sleep"):
        assert aobj.notify(body="Server down")

    # The retry reused the alert key so ilert sees one alert
    assert mock_post.call_count == 2
    keys = {
        json.loads(c[1]["data"])["alertKey"] for c in mock_post.call_args_list
    }
    assert len(keys) == 1
