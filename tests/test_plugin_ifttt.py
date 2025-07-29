# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import NotifyType
from apprise.plugins.ifttt import NotifyIFTTT

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "ifttt://",
        {
            "instance": TypeError,
        },
    ),
    (
        "ifttt://:@/",
        {
            "instance": TypeError,
        },
    ),
    # No User
    (
        "ifttt://EventID/",
        {
            "instance": TypeError,
        },
    ),
    # A nicely formed ifttt url with 1 event and a new key/value store
    (
        "ifttt://WebHookID@EventID/?+TemplateKey=TemplateVal",
        {
            "instance": NotifyIFTTT,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "ifttt://W...D",
        },
    ),
    # Test to= in which case we set the host to the webhook id
    (
        "ifttt://WebHookID?to=EventID,EventID2",
        {
            "instance": NotifyIFTTT,
        },
    ),
    # Removing certain keys:
    (
        "ifttt://WebHookID@EventID/?-Value1=&-Value2",
        {
            "instance": NotifyIFTTT,
        },
    ),
    # A nicely formed ifttt url with 2 events defined:
    (
        "ifttt://WebHookID@EventID/EventID2/",
        {
            "instance": NotifyIFTTT,
        },
    ),
    # Support Native URL references
    (
        "https://maker.ifttt.com/use/WebHookID/",
        {
            # No EventID specified
            "instance": TypeError,
        },
    ),
    (
        "https://maker.ifttt.com/use/WebHookID/EventID/",
        {
            "instance": NotifyIFTTT,
        },
    ),
    #  Native URL with arguments
    (
        "https://maker.ifttt.com/use/WebHookID/EventID/?-Value1=",
        {
            "instance": NotifyIFTTT,
        },
    ),
    # Test website connection failures
    (
        "ifttt://WebHookID@EventID",
        {
            "instance": NotifyIFTTT,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "ifttt://WebHookID@EventID",
        {
            "instance": NotifyIFTTT,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "ifttt://WebHookID@EventID",
        {
            "instance": NotifyIFTTT,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_ifttt_urls():
    """NotifyIFTTT() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.get")
@mock.patch("requests.post")
def test_plugin_ifttt_edge_cases(mock_post, mock_get):
    """NotifyIFTTT() Edge Cases."""

    # Initialize some generic (but valid) tokens
    webhook_id = "webhook_id"
    events = ["event1", "event2"]

    # Prepare Mock
    mock_get.return_value = requests.Request()
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok
    mock_get.return_value.status_code = requests.codes.ok
    mock_get.return_value.content = "{}"
    mock_post.return_value.content = "{}"

    # No webhook_id specified
    with pytest.raises(TypeError):
        NotifyIFTTT(webhook_id=None, events=None)

    # Initializes the plugin with an invalid webhook id
    with pytest.raises(TypeError):
        NotifyIFTTT(webhook_id=None, events=events)

    # Whitespace also acts as an invalid webhook id
    with pytest.raises(TypeError):
        NotifyIFTTT(webhook_id="   ", events=events)

    # No events specified
    with pytest.raises(TypeError):
        NotifyIFTTT(webhook_id=webhook_id, events=None)

    obj = NotifyIFTTT(webhook_id=webhook_id, events=events)
    assert isinstance(obj, NotifyIFTTT)

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Test the addition of tokens
    obj = NotifyIFTTT(
        webhook_id=webhook_id,
        events=events,
        add_tokens={"Test": "ValueA", "Test2": "ValueB"},
    )

    assert isinstance(obj, NotifyIFTTT)

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Invalid del_tokens entry
    with pytest.raises(TypeError):
        NotifyIFTTT(
            webhook_id=webhook_id,
            events=events,
            del_tokens=NotifyIFTTT.ifttt_default_title_key,
        )

    assert isinstance(obj, NotifyIFTTT)

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Test removal of tokens by a list
    obj = NotifyIFTTT(
        webhook_id=webhook_id,
        events=events,
        add_tokens={"MyKey": "MyValue"},
        del_tokens=(
            NotifyIFTTT.ifttt_default_title_key,
            NotifyIFTTT.ifttt_default_body_key,
            NotifyIFTTT.ifttt_default_type_key,
        ),
    )

    assert isinstance(obj, NotifyIFTTT)

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # Test removal of tokens as dict
    obj = NotifyIFTTT(
        webhook_id=webhook_id,
        events=events,
        add_tokens={"MyKey": "MyValue"},
        del_tokens={
            NotifyIFTTT.ifttt_default_title_key: None,
            NotifyIFTTT.ifttt_default_body_key: None,
            NotifyIFTTT.ifttt_default_type_key: None,
        },
    )

    assert isinstance(obj, NotifyIFTTT)
