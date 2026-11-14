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
from apprise.plugins.textkit import NotifyTextKit

logging.disable(logging.CRITICAL)

APIKEY = "ssms_sk_test_aBcD1234eFgH5678"

# Our Testing URLs
apprise_url_tests = (
    (
        "textkit://",
        {
            # No API Key specified
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "textkit://%20/15551232000",
        {
            # An API Key of only whitespace
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"textkit://{APIKEY}",
        {
            # No targets specified
            "instance": NotifyTextKit,
            "notify_response": False,
        },
    ),
    (
        f"textkit://{APIKEY}/123",
        {
            # An invalid target is dropped, leaving nobody to notify
            "instance": NotifyTextKit,
            "notify_response": False,
            "privacy_url": "textkit://****/123/",
        },
    ),
    (
        f"textkit://{APIKEY}/15551232000",
        {
            "instance": NotifyTextKit,
            "requests_response_code": requests.codes.created,
            "privacy_url": "textkit://****/15551232000/",
        },
    ),
    (
        f"textkit://{APIKEY}/15551232000/15551232001/123",
        {
            # A bad target among good ones is skipped
            "instance": NotifyTextKit,
            "requests_response_code": requests.codes.accepted,
        },
    ),
    (
        f"textkit://{APIKEY}/?to=15551232000",
        {
            "instance": NotifyTextKit,
            "requests_response_code": requests.codes.created,
            "privacy_url": "textkit://****/15551232000/",
        },
    ),
    (
        f"textkit://{APIKEY}/15551232000?from=15005550100",
        {
            "instance": NotifyTextKit,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        f"textkit://{APIKEY}/15551232000?source=pool_a1B2c3",
        {
            "instance": NotifyTextKit,
            "requests_response_code": requests.codes.created,
        },
    ),
    (
        f"textkit://{APIKEY}/15551232000",
        {
            # 200 is not a code this API sends for a new message
            "instance": NotifyTextKit,
            "response": False,
            "requests_response_code": requests.codes.ok,
        },
    ),
    (
        f"textkit://{APIKEY}/15551232000",
        {
            "instance": NotifyTextKit,
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"textkit://{APIKEY}/15551232000",
        {
            # A code we can not look up
            "instance": NotifyTextKit,
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"textkit://{APIKEY}/15551232000",
        {
            # Throws a series of i/o exceptions and tests that we gracefully
            # handle them
            "instance": NotifyTextKit,
            "requests_response_code": requests.codes.created,
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_textkit_urls():
    """NotifyTextKit() Apprise URLs."""

    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_textkit_init():
    """NotifyTextKit() initialization."""

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTextKit(apikey=None)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyTextKit(apikey="   ")

    # A phone number is put in E.164; a pool id is left alone
    assert NotifyTextKit(APIKEY, source=" 15005550100 ").source == (
        "+15005550100"
    )
    assert NotifyTextKit(APIKEY, source="pool_a1B2c3").source == "pool_a1B2c3"
    assert NotifyTextKit(APIKEY).source is None


@mock.patch("requests.post")
def test_plugin_textkit_payload(mock_post):
    """NotifyTextKit() sends what the API documents."""

    mock_post.return_value = mock.Mock(
        status_code=requests.codes.created,
        content=dumps({"id": "msg_a1B2c3D4e5F6g7H8", "status": "queued"}),
    )

    obj = Apprise.instantiate(
        f"textkit://{APIKEY}/15551232000/15551232001?from=15005550100"
    )
    assert isinstance(obj, NotifyTextKit)
    assert len(obj) == 2
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert mock_post.call_count == 2

    args, kwargs = mock_post.call_args_list[0]
    assert args[0] == "https://api.jointextkit.com/v1/messages"
    assert kwargs["headers"]["Authorization"] == f"Bearer {APIKEY}"
    assert kwargs["headers"]["Content-Type"] == "application/json"
    assert loads(kwargs["data"]) == {
        "to": "+15551232000",
        "from": "+15005550100",
        "body": "title\r\nbody",
    }

    assert loads(mock_post.call_args_list[1][1]["data"])["to"] == (
        "+15551232001"
    )


@mock.patch("requests.post")
def test_plugin_textkit_no_source(mock_post):
    """NotifyTextKit() leaves from out when none was given."""

    mock_post.return_value = mock.Mock(
        status_code=requests.codes.created, content=b"{}"
    )

    obj = Apprise.instantiate(f"textkit://{APIKEY}/15551232000")
    assert obj.notify(body="body") is True
    assert "from" not in loads(mock_post.call_args[1]["data"])


@mock.patch("requests.post")
@pytest.mark.parametrize(
    "content",
    [
        dumps({"error": {"code": "recipient_opted_out", "message": "Opted"}}),
        dumps({"unexpected": True}),
        b"not json",
        None,
    ],
)
def test_plugin_textkit_error_responses(mock_post, content):
    """NotifyTextKit() reports a refused send whatever came back."""

    mock_post.return_value = mock.Mock(
        status_code=requests.codes.forbidden, content=content
    )

    obj = Apprise.instantiate(f"textkit://{APIKEY}/15551232000")
    assert obj.notify(body="body") is False
    assert mock_post.call_count == 1


def test_plugin_textkit_url_round_trip():
    """NotifyTextKit() url() rebuilds the same object."""

    obj = Apprise.instantiate(
        f"textkit://{APIKEY}/15551232000?from=15005550100"
    )
    again = Apprise.instantiate(obj.url())

    assert again.apikey == APIKEY
    assert again.source == "+15005550100"
    assert again.targets == ["15551232000"]
    assert obj.url_id() == again.url_id()
