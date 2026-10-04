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
from urllib.parse import urlparse

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyFormat, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.goalert import NotifyGoAlert

logging.disable(logging.CRITICAL)

# Some integration keys we can use
KEY1 = "ab12cd34-ab12-4c5d-8e9f-0123456789ab"
KEY2 = "ab12cd34-ab12-4c5d-8e9f-0123456789ac"

# Our Testing URLs
apprise_url_tests = (
    (
        "goalert://",
        {
            # No hostname
            "instance": None,
        },
    ),
    (
        "goalerts://localhost",
        {
            # No integration keys; loads but has nothing to notify
            "instance": NotifyGoAlert,
            "notify_response": False,
        },
    ),
    (
        "goalerts://localhost/?to=invalid",
        {
            # Invalid integration key
            "instance": NotifyGoAlert,
            "notify_response": False,
            "privacy_url": "goalerts://localhost/?action=map&to=invalid",
        },
    ),
    (
        f"goalerts://localhost/{KEY1}?action=invalid",
        {
            # Invalid action
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"goalert://localhost/{KEY1}",
        {
            "instance": NotifyGoAlert,
            "privacy_url": "goalert://localhost/a...b/",
        },
    ),
    (
        f"goalerts://localhost:8443/goalert/{KEY1}/{KEY2}",
        {
            # Sub-path and multiple integration keys
            "instance": NotifyGoAlert,
            "privacy_url": "goalerts://localhost:8443/goalert/a...b/a...c/",
        },
    ),
    (
        f"goalerts://localhost/?token={KEY1}&action=close&dedup=disk",
        {
            # ?token=, ?action= and ?dedup=
            "instance": NotifyGoAlert,
        },
    ),
    (
        f"goalerts://localhost/{KEY1}?action=trigger&+env=prod",
        {
            # Metadata
            "instance": NotifyGoAlert,
        },
    ),
    (
        f"goalerts://localhost/{KEY1}",
        {
            "instance": NotifyGoAlert,
            # A 204 is GoAlert's normal response
            "requests_response_code": requests.codes.no_content,
        },
    ),
    (
        f"goalerts://localhost/{KEY1}",
        {
            "instance": NotifyGoAlert,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"goalerts://localhost/{KEY1}",
        {
            "instance": NotifyGoAlert,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"goalerts://localhost/{KEY1}",
        {
            "instance": NotifyGoAlert,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_goalert_urls():
    """NotifyGoAlert() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_goalert_payload(mock_post):
    """NotifyGoAlert() payload, headers and endpoint."""

    response = mock.Mock()
    response.status_code = requests.codes.no_content
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(
        f"goalerts://localhost:8443/goalert/{KEY1}"
        "?dedup=disk&+env=prod&+team=ops"
    )
    assert isinstance(obj, NotifyGoAlert)

    assert obj.notify(
        title="Disk <full> & failing",
        body="Some _markdown_ text",
        notify_type=NotifyType.FAILURE,
    )
    assert mock_post.call_count == 1

    url = mock_post.call_args[0][0]
    assert urlparse(url).hostname == "localhost"
    assert url == ("https://localhost:8443/goalert/api/v2/generic/incoming")

    # The key travels as a bearer token, never in the URL
    headers = mock_post.call_args[1]["headers"]
    assert headers["Authorization"] == f"Bearer {KEY1}"

    # The title is sent untouched as the summary
    payload = loads(mock_post.call_args[1]["data"])
    assert payload == {
        "summary": "Disk <full> & failing",
        "details": "Some _markdown_ text",
        "dedup": "disk",
        "meta": {"env": "prod", "team": "ops"},
    }


@mock.patch("requests.post")
def test_plugin_goalert_actions(mock_post):
    """NotifyGoAlert() raises or closes alerts based on the action."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    def _action(url, notify_type):
        # Send one notification and return the action sent, if any
        mock_post.reset_mock()
        obj = Apprise.instantiate(url)
        assert obj.notify(body="body", notify_type=notify_type)
        return loads(mock_post.call_args[1]["data"]).get("action")

    # Mapping closes alerts on success only
    url = f"goalert://localhost/{KEY1}"
    assert _action(url, NotifyType.SUCCESS) == "close"
    assert _action(url, NotifyType.INFO) is None
    assert _action(url, NotifyType.FAILURE) is None

    # Explicit actions ignore the notification type
    assert _action(f"{url}?action=trigger", NotifyType.SUCCESS) is None
    assert _action(f"{url}?action=c", NotifyType.FAILURE) == "close"

    # Partial and mixed case actions are accepted
    obj = NotifyGoAlert(host="localhost", targets=KEY1, action=" TRIG ")
    assert obj.action == "trigger"

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyGoAlert(host="localhost", targets=KEY1, action="nope")


@mock.patch("requests.post")
def test_plugin_goalert_summary(mock_post):
    """NotifyGoAlert() builds a plain summary when there is no title."""

    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    obj = Apprise.instantiate(f"goalert://localhost/{KEY1}")

    # Plain text gets escaped for markdown; the summary drops them
    assert obj.notify(body="50% done_now *", body_format=NotifyFormat.TEXT)
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["summary"] == "50% done_now *"
    assert payload["details"] != payload["summary"]

    # With no source format the body is relayed untouched
    mock_post.reset_mock()
    assert obj.notify(body="a \\* b")
    payload = loads(mock_post.call_args[1]["data"])
    assert payload["summary"] == "a \\* b"
    assert payload["details"] == "a \\* b"

    # A long body is trimmed to the summary limit
    mock_post.reset_mock()
    assert obj.notify(body="a" * 3000, body_format=NotifyFormat.MARKDOWN)
    payload = loads(mock_post.call_args[1]["data"])
    assert len(payload["summary"]) == obj.title_maxlen
    assert len(payload["details"]) == 3000


@mock.patch("requests.post")
def test_plugin_goalert_multiple_keys(mock_post):
    """NotifyGoAlert() notifies each key and reports partial failures."""

    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = b""

    bad = mock.Mock()
    bad.status_code = requests.codes.unauthorized
    bad.content = b"unauthorized"

    obj = NotifyGoAlert(
        host="localhost", targets=[KEY1, KEY2, "bad-key"], secure=True
    )
    assert len(obj) == 2
    assert obj.invalid_targets == ["bad-key"]

    # Both keys succeed
    mock_post.side_effect = (good, good)
    assert obj.notify(body="body") is True
    assert mock_post.call_count == 2

    # One key fails, the other is still notified
    mock_post.reset_mock()
    mock_post.side_effect = (bad, good)
    assert obj.notify(body="body") is False
    assert mock_post.call_count == 2

    # Mixed case keys are stored in lowercase
    obj = NotifyGoAlert(host="localhost", targets=KEY1.upper())
    assert obj.targets == [KEY1]


@mock.patch("requests.post")
def test_plugin_goalert_retry_skips_delivered(mock_post):
    """NotifyGoAlert() never re-notifies a key that already succeeded."""

    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = b""

    bad = mock.Mock()
    bad.status_code = requests.codes.internal_server_error
    bad.content = b""

    def handler(url, *args, **kwargs):
        # KEY2 always fails
        return bad if KEY2 in kwargs["headers"]["Authorization"] else good

    mock_post.side_effect = handler

    with (
        mock.patch("apprise.plugins.base.time.sleep"),
        mock.patch("apprise.apprise.time.sleep"),
    ):
        aobj = Apprise()
        assert aobj.add(f"goalert://localhost/{KEY1}/{KEY2}?retry=2&wait=0")
        assert not aobj.notify(body="body")

    keys = [c[1]["headers"]["Authorization"] for c in mock_post.call_args_list]
    assert keys.count(f"Bearer {KEY1}") == 1
    assert keys.count(f"Bearer {KEY2}") == 3


def test_plugin_goalert_url_identifier():
    """NotifyGoAlert() identifies the server, not its keys."""

    obj1 = Apprise.instantiate(f"goalerts://localhost/sub/{KEY1}")
    obj2 = Apprise.instantiate(f"goalerts://localhost/sub/{KEY2}")
    obj3 = Apprise.instantiate(f"goalerts://localhost/{KEY1}")
    assert obj1.url_identifier == obj2.url_identifier
    assert obj1.url_identifier != obj3.url_identifier

    # Every option survives a round trip
    obj = Apprise.instantiate(
        f"goalert://localhost:8080/a/b/{KEY1}/{KEY2}"
        "?to=bad&action=close&dedup=x&+env=prod"
    )
    result = NotifyGoAlert.parse_url(obj.url())
    obj2 = NotifyGoAlert(**result)
    assert obj.url_identifier == obj2.url_identifier
    assert sorted(obj.targets) == sorted(obj2.targets)
    assert obj.invalid_targets == obj2.invalid_targets
    assert obj2.action == "close"
    assert obj2.dedup == "x"
    assert obj2.meta == {"env": "prod"}
    assert obj2.fullpath == "/a/b/"
