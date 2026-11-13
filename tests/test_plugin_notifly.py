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
from json import dumps, loads
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.base import _delivery_memo, _delivery_tracker
from apprise.plugins.notifly import NotifyNotifly

logging.disable(logging.CRITICAL)

# A stand-in API key
APIKEY = "nfly_" + "a" * 32

# What Notifly answers when the workflow ran
PROCESSED = dumps({"data": {"acknowledged": True, "status": "processed"}})

# Our Testing URLs
apprise_url_tests = (
    (
        "notifly://",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        # An API key but no workflow
        "notifly://apikey",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "notifly://apikey/workflow",
        {
            # No subscribers is allowed at load time, nothing is sent
            "instance": NotifyNotifly,
            "notify_response": False,
        },
    ),
    (
        "notifly://apikey/workflow/subscriber",
        {
            "instance": NotifyNotifly,
            "privacy_url": "notifly://a...y/workflow/subscriber",
        },
    ),
    (
        "notifly://apikey/workflow/sub1/sub2/sub3",
        {
            "instance": NotifyNotifly,
        },
    ),
    (
        "notifly://apikey/workflow?to=sub1,sub2",
        {
            "instance": NotifyNotifly,
        },
    ),
    (
        "notifly://apikey/workflow/sub1?:order=1234&:team=ops",
        {
            "instance": NotifyNotifly,
        },
    ),
    (
        "notifly://apikey/workflow/subscriber",
        {
            "instance": NotifyNotifly,
            # Created is what Notifly really answers with
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        "notifly://apikey/workflow/subscriber",
        {
            "instance": NotifyNotifly,
            "response": False,
            "requests_response_code": requests.codes.unauthorized,
        },
    ),
    (
        "notifly://apikey/workflow/subscriber",
        {
            "instance": NotifyNotifly,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "notifly://apikey/workflow/subscriber",
        {
            "instance": NotifyNotifly,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_notifly_urls():
    """NotifyNotifly() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_notifly_edge_cases():
    """NotifyNotifly() Edge Cases."""

    # no apikey
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyNotifly(apikey=None, workflow="workflow")

    # no workflow
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyNotifly(apikey="abcd", workflow=None)

    # Subscribers can be given as a list or a string
    obj = NotifyNotifly(apikey="abcd", workflow="wf", targets="s1, s2")
    assert obj.targets == ["s1", "s2"]
    assert len(obj) == 2

    # Without any, we still count as one so the framework keeps us
    obj = NotifyNotifly(apikey="abcd", workflow="wf")
    assert obj.targets == []
    assert len(obj) == 1


@mock.patch("requests.post")
def test_plugin_notifly_payload(mock_post):
    """NotifyNotifly() Payload."""

    request = mock.Mock()
    request.status_code = requests.codes.created
    request.content = PROCESSED.encode("utf-8")
    mock_post.return_value = request

    obj = Apprise.instantiate(
        f"notifly://{APIKEY}/my-workflow/sub1/sub2?:order=1234"
    )
    assert isinstance(obj, NotifyNotifly)
    assert obj.notify(
        body="body", title="title", notify_type=NotifyType.WARNING
    )

    # One request per subscriber
    assert mock_post.call_count == 2
    first, second = mock_post.call_args_list

    assert first[0][0] == "https://api.notifly.io/v1/events/trigger"

    headers = first[1]["headers"]
    assert headers["Authorization"] == f"ApiKey {APIKEY}"
    assert headers["Content-Type"] == "application/json"
    assert headers["Idempotency-Key"]

    assert loads(first[1]["data"]) == {
        "name": "my-workflow",
        "to": {"subscriberId": "sub1"},
        "payload": {
            "title": "title",
            "body": "body",
            "type": "warning",
            "order": "1234",
        },
    }
    assert loads(second[1]["data"])["to"] == {"subscriberId": "sub2"}

    # Each subscriber gets its own Idempotency-Key
    assert (
        first[1]["headers"]["Idempotency-Key"]
        != second[1]["headers"]["Idempotency-Key"]
    )

    # Our URL can be rebuilt from itself
    new_obj = Apprise.instantiate(obj.url())
    assert isinstance(new_obj, NotifyNotifly)
    assert new_obj.url() == obj.url()
    assert new_obj.apikey == APIKEY
    assert new_obj.workflow == "my-workflow"
    assert new_obj.targets == ["sub1", "sub2"]
    assert new_obj.payload_extras == {"order": "1234"}

    # The API key never appears in the privacy URL
    assert APIKEY not in obj.url(privacy=True)


@mock.patch("requests.post")
def test_plugin_notifly_response_status(mock_post):
    """NotifyNotifly() reads the body of a 201 answer."""

    obj = NotifyNotifly(apikey="abcd", workflow="wf", targets="s1")

    request = mock.Mock()
    request.status_code = requests.codes.created
    mock_post.return_value = request

    # The workflow ran
    request.content = PROCESSED.encode("utf-8")
    assert obj.notify(body="body") is True

    # Answers that do not name a workflow result are taken at their
    # status code: no body, text, a bare list or no data section
    for content in (b"", b"not json", b"[]", b"{}", None):
        request.content = content
        assert obj.notify(body="body") is True

    # Accepted but the workflow could not run
    for data in (
        {"acknowledged": True, "status": "trigger_not_active"},
        {"acknowledged": False, "status": "processed"},
        {"acknowledged": False, "status": "error", "error": ["oops"]},
        {"acknowledged": True},
    ):
        request.content = dumps({"data": data}).encode("utf-8")
        assert obj.notify(body="body") is False

    # A plain 200 is accepted too
    request.status_code = requests.codes.ok
    request.content = PROCESSED.encode("utf-8")
    assert obj.notify(body="body") is True

    # Anything else is a failure
    for code in (400, 401, 403, 404, 409, 422, 429, 500):
        request.status_code = code
        assert obj.notify(body="body") is False


@mock.patch("requests.post")
def test_plugin_notifly_no_targets(mock_post):
    """NotifyNotifly() with nobody to notify."""

    obj = NotifyNotifly(apikey="abcd", workflow="wf")
    assert obj.notify(body="body") is False
    assert mock_post.call_count == 0


@mock.patch("requests.post")
def test_plugin_notifly_partial_failure(mock_post):
    """NotifyNotifly() reports failure if one subscriber is refused."""

    ok = mock.Mock()
    ok.status_code = requests.codes.created
    ok.content = PROCESSED.encode("utf-8")

    bad = mock.Mock()
    bad.status_code = requests.codes.not_found
    bad.content = b'{"statusCode":404,"message":"Not Found"}'

    obj = NotifyNotifly(apikey="abcd", workflow="wf", targets=["s1", "s2"])

    # The first is refused, we still try the second
    mock_post.side_effect = [bad, ok]
    assert obj.notify(body="body") is False
    assert mock_post.call_count == 2

    # A connection problem is handled the same way
    mock_post.reset_mock()
    mock_post.side_effect = [requests.ConnectionError("down"), ok]
    assert obj.notify(body="body") is False
    assert mock_post.call_count == 2


@mock.patch("requests.post")
def test_plugin_notifly_retry_keeps_idempotency_key(mock_post):
    """NotifyNotifly() reuses its Idempotency-Key on a retry."""

    ok = mock.Mock()
    ok.status_code = requests.codes.created
    ok.content = PROCESSED.encode("utf-8")

    bad = mock.Mock()
    bad.status_code = requests.codes.service_unavailable
    bad.content = b""

    obj = NotifyNotifly(apikey="abcd", workflow="wf", targets=["s1", "s2"])

    # Retries turn on delivery marks and remembered values together
    token = _delivery_tracker.set(set())
    memo_token = _delivery_memo.set({})
    try:
        # The first subscriber is accepted, the second is not
        mock_post.side_effect = [ok, bad]
        assert obj.send(body="body") is False
        assert mock_post.call_count == 2
        first_s2 = mock_post.call_args_list[1][1]["headers"]["Idempotency-Key"]

        # The retry only contacts the second one, with the same key
        mock_post.reset_mock()
        mock_post.side_effect = [ok]
        assert obj.send(body="body") is True
        assert mock_post.call_count == 1
        retry = mock_post.call_args_list[0][1]
        assert loads(retry["data"])["to"] == {"subscriberId": "s2"}
        assert retry["headers"]["Idempotency-Key"] == first_s2

    finally:
        _delivery_tracker.reset(token)
        _delivery_memo.reset(memo_token)


@mock.patch("requests.post")
def test_plugin_notifly_debug_logging(mock_post, caplog):
    """NotifyNotifly() never logs the API key."""

    request = mock.Mock()
    request.status_code = requests.codes.created
    request.content = PROCESSED.encode("utf-8")
    mock_post.return_value = request

    obj = NotifyNotifly(apikey=APIKEY, workflow="wf", targets="s1")

    logging.disable(logging.NOTSET)
    try:
        with caplog.at_level(logging.DEBUG):
            assert obj.notify(body="body", title="title") is True

    finally:
        logging.disable(logging.CRITICAL)

    assert "Notifly POST URL" in caplog.text
    assert "Notifly Payload" in caplog.text
    assert APIKEY not in caplog.text
