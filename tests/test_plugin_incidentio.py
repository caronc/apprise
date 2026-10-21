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
from apprise.plugins.incidentio import IncidentIOAction, NotifyIncidentIO

logging.disable(logging.CRITICAL)

# A realistic alert source ID
SOURCE = "01GW2G3V0S59R238FAHPDS1R66"

# Our Testing URLs
apprise_url_tests = (
    (
        "incidentio://",
        {
            # No alert source ID specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "incidentio://{}".format(SOURCE),
        {
            # No token specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "incidentio://invalid-source!/token",
        {
            # An invalid alert source ID
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "incidentio://{}/secret".format(SOURCE),
        {
            # A valid alert source and token
            "instance": NotifyIncidentIO,
            "requests_response_code": requests.codes.accepted,
            "privacy_url": "incidentio://{}/s...t/".format(SOURCE),
        },
    ),
    (
        "incidentio://?source={}&token=secret".format(SOURCE),
        {
            # Everything supplied as arguments
            "instance": NotifyIncidentIO,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "incidentio://{}/secret?action=resolve&dedup=disk-full"
        "&click=https://example.com/alert&+service=web".format(SOURCE),
        {
            # Every option in use
            "instance": NotifyIncidentIO,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "incidentio://{}/secret?action=invalid".format(SOURCE),
        {
            # An invalid action
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "https://api.incident.io/v2/alert_events/http/{}?token=secret".format(
            SOURCE
        ),
        {
            # The URL incident.io shows when the source is created
            "instance": NotifyIncidentIO,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        "incidentio://{}/secret".format(SOURCE),
        {
            "instance": NotifyIncidentIO,
            # A failure has been returned by the server
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "incidentio://{}/secret".format(SOURCE),
        {
            "instance": NotifyIncidentIO,
            # An unknown response code
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "incidentio://{}/secret".format(SOURCE),
        {
            "instance": NotifyIncidentIO,
            # Socket errors are handled
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_incidentio_urls():
    """NotifyIncidentIO() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_incidentio_payload(mock_post):
    """NotifyIncidentIO() builds the alert it sends."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        "incidentio://{}/secret?action=res&dedup=disk-full"
        "&click=https://example.com/alert&+service=web&+team=ops".format(
            SOURCE
        )
    )
    assert isinstance(obj, NotifyIncidentIO)
    assert obj.action == IncidentIOAction.RESOLVE

    # A title and a markdown body
    assert obj.notify(
        title="Disk & <db01>",
        body="Usage at **95%** on `_db01_`.",
        body_format=NotifyFormat.MARKDOWN,
    )

    # One post to our alert source with our secret
    assert mock_post.call_count == 1
    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "api.incident.io"
    assert urlparse(url).path == "/v2/alert_events/http/{}".format(SOURCE)
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer secret"

    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload == {
        "title": "Disk & <db01>",
        "description": "Usage at **95%** on `_db01_`.",
        "status": "resolved",
        "deduplication_key": "disk-full",
        "source_url": "https://example.com/alert",
        "metadata": {"service": "web", "team": "ops"},
    }

    # Without a title, the body becomes the title without the escapes
    # Apprise added when converting text to markdown
    mock_post.reset_mock()
    obj = NotifyIncidentIO(source=SOURCE, token="secret")
    assert obj.notify(body="Server_1 is *down*", body_format=NotifyFormat.TEXT)
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "Server_1 is *down*"
    assert payload["description"] == "Server\\_1 is \\*down\\*"
    assert "source_url" not in payload
    assert "metadata" not in payload

    # A passthrough body is used as the title untouched and capped
    mock_post.reset_mock()
    assert obj.send(body="x" * 300, body_passthrough=True)
    payload = json.loads(mock_post.call_args[1]["data"])
    assert payload["title"] == "x" * obj.title_maxlen


@mock.patch("requests.post")
def test_plugin_incidentio_action_map(mock_post):
    """NotifyIncidentIO() resolves on success and raises otherwise."""

    response = mock.Mock()
    response.status_code = requests.codes.accepted
    response.content = b""
    mock_post.return_value = response

    def sent():
        return json.loads(mock_post.call_args[1]["data"])

    # The default action maps the notification type
    obj = NotifyIncidentIO(source=SOURCE, token="secret")
    assert obj.action == IncidentIOAction.MAP
    for notify_type, status in (
        (NotifyType.INFO, "firing"),
        (NotifyType.WARNING, "firing"),
        (NotifyType.FAILURE, "firing"),
        (NotifyType.SUCCESS, "resolved"),
    ):
        assert obj.notify(
            title="Disk full", body="db01", notify_type=notify_type
        )
        assert sent()["status"] == status

    # The same title always produces the same key, so a success
    # resolves the alert a failure raised
    assert obj.notify(
        title="Disk full", body="a", notify_type=NotifyType.FAILURE
    )
    raised = sent()["deduplication_key"]
    assert obj.notify(
        title="Disk full", body="b", notify_type=NotifyType.SUCCESS
    )
    assert sent()["deduplication_key"] == raised

    # A different title is a different alert
    assert obj.notify(title="CPU hot", body="a")
    assert sent()["deduplication_key"] != raised

    # Without a title, the first line of the message is used
    assert obj.notify(body="Disk full\nat 95%")
    assert sent()["deduplication_key"] == raised
    assert obj.notify(body="one")
    untitled = sent()["deduplication_key"]
    assert obj.notify(body="two")
    assert sent()["deduplication_key"] != untitled

    # Trigger ignores the notification type and raises a new alert
    # every time, even with the same title
    obj = NotifyIncidentIO(source=SOURCE, token="secret", action="trigger")
    assert obj.notify(
        title="Disk full", body="ok", notify_type=NotifyType.SUCCESS
    )
    assert sent()["status"] == "firing"
    first = sent()["deduplication_key"]
    assert obj.notify(title="Disk full", body="ok")
    assert sent()["deduplication_key"] != first

    obj = NotifyIncidentIO(source=SOURCE, token="secret", action="RESOLVE")
    assert obj.notify(body="bad", notify_type=NotifyType.FAILURE)
    assert sent()["status"] == "resolved"


def test_plugin_incidentio_init():
    """NotifyIncidentIO() init and url round trip."""

    obj = NotifyIncidentIO(
        source=SOURCE,
        token="secret",
        action="trigger",
        dedup="  key  ",
        click="  ",
        metadata={"a": "b"},
    )
    assert obj.action == IncidentIOAction.TRIGGER
    assert obj.dedup == "key"
    assert obj.click is None
    assert len(obj) == 1

    # The URL survives a round trip
    result = NotifyIncidentIO.parse_url(obj.url())
    obj2 = NotifyIncidentIO(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert obj2.dedup == "key"
    assert obj2.metadata == {"a": "b"}
    assert obj2.action == IncidentIOAction.TRIGGER

    # A missing or blank token is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyIncidentIO(source=SOURCE, token="  ")

    # A missing source is refused
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyIncidentIO(source=None, token="secret")

    # A different source is a different connection
    other = NotifyIncidentIO(source="01ABC", token="secret")
    assert other.url_identifier != obj.url_identifier


@mock.patch("requests.post")
def test_plugin_incidentio_retry_key(mock_post):
    """NotifyIncidentIO() keeps its trigger key across retries."""

    bad = mock.Mock()
    bad.status_code = requests.codes.internal_server_error
    bad.content = b""
    good = mock.Mock()
    good.status_code = requests.codes.accepted
    good.content = b""
    mock_post.side_effect = [bad, good]

    aobj = Apprise()
    assert aobj.add(
        "incidentio://{}/secret?action=trigger&retry=1&wait=0".format(SOURCE)
    )
    with mock.patch("apprise.apprise.time.sleep"):
        assert aobj.notify(body="Server down")

    # The retry reused the key so incident.io sees one alert
    assert mock_post.call_count == 2
    keys = {
        json.loads(c[1]["data"])["deduplication_key"]
        for c in mock_post.call_args_list
    }
    assert len(keys) == 1
