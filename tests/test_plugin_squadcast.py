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
from apprise.plugins.squadcast import (
    NotifySquadcast,
    SquadcastAction,
    SquadcastRegion,
)

logging.disable(logging.CRITICAL)

# A realistic webhook key
KEY = "7f550a9f4c44173a37664d938f1355f0f92a47a7"

# Our Testing URLs
apprise_url_tests = (
    (
        "squadcast://",
        {
            # No webhook key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "squadcast://invalid!key",
        {
            # An invalid webhook key
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "squadcast://{}".format(KEY),
        {
            # A valid webhook key
            "instance": NotifySquadcast,
            "requests_response_code": requests.codes.accepted,
            "privacy_url": "squadcast://7...7/",
        },
    ),
    (
        "squadcast://?key={}".format(KEY),
        {
            # The key supplied as an argument
            "instance": NotifySquadcast,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "squadcast://{}?region=eu&action=resolve&dedup=disk-full"
        "&priority=p2&+severity=high".format(KEY),
        {
            # Every option in use
            "instance": NotifySquadcast,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "squadcast://{}?region=invalid".format(KEY),
        {
            # An invalid region
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "squadcast://{}?action=invalid".format(KEY),
        {
            # An invalid action
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "squadcast://{}?priority=P9".format(KEY),
        {
            # An invalid priority
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "https://api.squadcast.com/v2/incidents/api/{}".format(KEY),
        {
            # The webhook URL Squadcast hands out
            "instance": NotifySquadcast,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "https://api.eu.squadcast.com/v2/incidents/api/{}?priority=1".format(
            KEY
        ),
        {
            # The webhook URL handed out by the EU region
            "instance": NotifySquadcast,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "squadcast://{}".format(KEY),
        {
            "instance": NotifySquadcast,
            # A failure has been returned by the server
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "squadcast://{}".format(KEY),
        {
            "instance": NotifySquadcast,
            # An unknown response code
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "squadcast://{}".format(KEY),
        {
            "instance": NotifySquadcast,
            # Socket errors are handled
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_squadcast_urls():
    """NotifySquadcast() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_squadcast_payload(mock_post):
    """NotifySquadcast() builds the incident it sends."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "squadcast://{}?action=res&dedup=disk-full&priority=3"
        "&+severity=high&+team=ops".format(KEY)
    )
    assert isinstance(obj, NotifySquadcast)
    assert obj.action == SquadcastAction.RESOLVE
    assert obj.priority == "P3"

    # A title and a markdown body
    assert obj.notify(
        title="Disk & <db01>",
        body="Usage at **95%** on `_db01_`.",
        body_format=NotifyFormat.MARKDOWN,
    )

    # One post to the US region with our key
    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "api.squadcast.com"
    assert urlparse(url).path == "/v2/incidents/api/{}".format(KEY)
    headers = mock_post.call_args[1]["headers"]
    assert headers["Content-Type"] == "application/json"

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload == {
        "message": "Disk & <db01>",
        "description": "Usage at **95%** on `_db01_`.",
        "status": "resolve",
        "event_id": "disk-full",
        "priority": "P3",
        "tags": {"severity": "high", "team": "ops"},
    }

    # Without a title, the body becomes the message without the escapes
    # Apprise added when converting text to markdown
    mock_post.reset_mock()
    obj = NotifySquadcast(key=KEY, region_name="EU")
    assert obj.notify(body="Server_1 is *down*", body_format=NotifyFormat.TEXT)
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "api.eu.squadcast.com"
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "Server_1 is *down*"
    assert payload["description"] == "Server\\_1 is \\*down\\*"
    assert payload["status"] == "trigger"
    assert "priority" not in payload
    assert "tags" not in payload

    # A passthrough body is used as the message untouched and capped
    mock_post.reset_mock()
    assert obj.send(body="x" * 300, body_passthrough=True)
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["message"] == "x" * obj.title_maxlen


@mock.patch("requests.post")
def test_plugin_squadcast_action_map(mock_post):
    """NotifySquadcast() resolves on success and triggers otherwise."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    def sent():
        return json.loads(mock_post.call_args[1]["data"])

    # The default action maps the notification type
    obj = NotifySquadcast(key=KEY)
    assert obj.action == SquadcastAction.MAP
    for notify_type, status in (
        (NotifyType.INFO, "trigger"),
        (NotifyType.WARNING, "trigger"),
        (NotifyType.FAILURE, "trigger"),
        (NotifyType.SUCCESS, "resolve"),
    ):
        assert obj.notify(
            title="Disk full", body="db01", notify_type=notify_type
        )
        assert sent()["status"] == status

    # The same title always produces the same event ID, so a success
    # resolves the incident a failure triggered
    assert obj.notify(
        title="Disk full", body="a", notify_type=NotifyType.FAILURE
    )
    raised = sent()["event_id"]
    assert obj.notify(
        title="Disk full", body="b", notify_type=NotifyType.SUCCESS
    )
    assert sent()["event_id"] == raised

    # A different title is a different incident
    assert obj.notify(title="CPU hot", body="a")
    assert sent()["event_id"] != raised

    # Without a title, the first line of the message is used
    assert obj.notify(body="Disk full\nat 95%")
    assert sent()["event_id"] == raised

    # Trigger ignores the notification type and triggers a new incident
    # every time, even with the same title
    obj = NotifySquadcast(key=KEY, action="trigger")
    assert obj.notify(
        title="Disk full", body="ok", notify_type=NotifyType.SUCCESS
    )
    assert sent()["status"] == "trigger"
    first = sent()["event_id"]
    assert obj.notify(title="Disk full", body="ok")
    assert sent()["event_id"] != first

    obj = NotifySquadcast(key=KEY, action="RESOLVE")
    assert obj.notify(body="bad", notify_type=NotifyType.FAILURE)
    assert sent()["status"] == "resolve"


def test_plugin_squadcast_init():
    """NotifySquadcast() init and url round trip."""

    obj = NotifySquadcast(
        key=KEY,
        region_name="eu",
        action="trigger",
        dedup="  key  ",
        priority="  ",
        tags={"a": "b"},
    )
    assert obj.region_name == SquadcastRegion.EU
    assert obj.action == SquadcastAction.TRIGGER
    assert obj.dedup == "key"
    assert obj.priority is None
    assert len(obj) == 1

    # The URL survives a round trip
    result = NotifySquadcast.parse_url(obj.url())
    obj2 = NotifySquadcast(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert obj2.region_name == SquadcastRegion.EU
    assert obj2.dedup == "key"
    assert obj2.tags_map == {"a": "b"}
    assert obj2.action == SquadcastAction.TRIGGER

    # A priority survives too
    obj = NotifySquadcast(key=KEY, priority="p5")
    assert "priority=P5" in obj.url()
    result = NotifySquadcast.parse_url(obj.url())
    assert NotifySquadcast(**result).priority == "P5"

    # A missing or blank key is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifySquadcast(key="  ")

    with pytest.raises(AppriseImproperlyConfigured):
        NotifySquadcast(key=None)

    # The EU region is a different connection
    assert (
        NotifySquadcast(key=KEY).url_identifier
        != NotifySquadcast(key=KEY, region_name="eu").url_identifier
    )

    # The EU webhook URL keeps its region
    result = NotifySquadcast.parse_native_url(
        "https://api.eu.squadcast.com/v2/incidents/api/{}".format(KEY)
    )
    assert result["region_name"] == SquadcastRegion.EU
    assert result["key"] == KEY


@mock.patch("requests.post")
def test_plugin_squadcast_retry_key(mock_post):
    """NotifySquadcast() keeps its trigger event ID across retries."""

    bad = mock.Mock()
    bad.status_code = requests.codes.internal_server_error
    bad.content = b""
    good = mock.Mock()
    good.status_code = requests.codes.accepted
    good.content = b""
    mock_post.side_effect = [bad, good]

    aobj = Apprise()
    assert aobj.add("squadcast://{}?action=trigger&retry=1&wait=0".format(KEY))
    with mock.patch("apprise.apprise.time.sleep"):
        assert aobj.notify(body="Server down")

    # The retry reused the event ID so Squadcast sees one incident
    assert mock_post.call_count == 2
    keys = {
        json.loads(c[1]["data"])["event_id"] for c in mock_post.call_args_list
    }
    assert len(keys) == 1
