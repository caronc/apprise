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

from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.pingram import NotifyPingram

logging.disable(logging.CRITICAL)

PINGRAM_GOOD_RESPONSE = dumps({"trackingId": "abc123"})

PINGRAM_BAD_RESPONSE = "{"

# Our Testing URLs
apprise_url_tests = (
    (
        "pingram://",
        {
            # No API Key at all
            "instance": TypeError,
        },
    ),
    (
        "pingram://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "pingram://abcd",
        {
            # Doesn't match the pingram_(sk|pk)_ prefix
            "instance": TypeError,
        },
    ),
    (
        "pingram://pingram_sk_key/+15551235553/?mode=invalid",
        {
            # Invalid mode
            "instance": TypeError,
        },
    ),
    (
        "pingram://pingram_sk_key/+15551235553/?region=invalid",
        {
            # Invalid region
            "instance": TypeError,
        },
    ),
    (
        "pingram://pingram_sk_key/+15551235553/?type=*(",
        {
            # Invalid type
            "instance": TypeError,
        },
    ),
    (
        "pingram://pingram_sk_key/+15551235553/?channels=bad",
        {
            # Invalid channel
            "instance": TypeError,
        },
    ),
    (
        "pingram://pingram_sk_abc123/g@rb@ge/+15551235553/",
        {
            # g@rb@ge entry ignored (invalid target, dropped with a
            # warning, preserved for round-trip only)
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/g@rb@ge/",
        {
            # Only an invalid target specified; nothing to notify
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
            "notify_response": False,
        },
    ),
    (
        "pingram://pingram_sk_abc123/user1@example.com/user2@example.com",
        {
            # Two emails back to back with no id between them each
            # become their own recipient
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/+15551235553",
        {
            # A bare phone number with no id is valid
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_pk_abc123/user@example.ca",
        {
            # A bare email with no id is valid; public key prefix works
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/+15551235553/+15551235554",
        {
            # Multiple id-less phone numbers become separate targets
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/+15551235553",
        {
            # An id can still optionally be supplied
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/id2/user1@example.com",
        {
            # two ids in a row; first is dropped in favor of the second
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        (
            "pingram://type@pingram_sk_abc123/id10/user2@example.com/"
            "id5/+15551235555/id8/+15551235534"
            "?reply=Chris<chris@example.com>"
        ),
        {
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        (
            "pingram://type@pingram_sk_abc123/abc1/user1@example.com/"
            "id5/+15551235555/?from=Chris&reply=Christopher"
        ),
        {
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        (
            "pingram://type@pingram_sk_abc123/user3@example.com/"
            "?from=joe@example.ca&reply=user@abc.com"
        ),
        {
            # Set from/source
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        (
            "pingram://type@pingram_sk_abc123/user4@example.com/"
            "?from=joe@example.ca&bcc=user1@yahoo.ca&cc=user2@yahoo.ca"
        ),
        {
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pingram://type@p...3/",
        },
    ),
    (
        "pingram://?apikey=pingram_sk_abc123&to=id,user5@example.com"
        "&type=typec",
        {
            # use just kwargs
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
            "privacy_url": "pingram://typec@p...3/",
        },
    ),
    (
        "pingram://pingram_sk_abc123?to=id,user5@example.com&type=typeb",
        {
            # apikey is pulled from the host
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
            "privacy_url": "pingram://typeb@p...3/",
        },
    ),
    (
        "pingram://?apikey=pingram_sk_abc123&type=test-type&region=eu",
        {
            # No targets specified
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
            "notify_response": False,
        },
    ),
    (
        "pingram://?apikey=pingram_sk_abc123&to=id,user5@example.com"
        "&type=typec",
        {
            # bad response
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_BAD_RESPONSE,
            "notify_response": False,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user6@example.ca?bcc=invalid",
        {
            # A good email with a bad Blind Carbon Copy
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user8@example.ca?cc=l2g@nuxref.com",
        {
            # A good email with Carbon Copy
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user8@example.ca"
        "?channels=email,sms,slack,mobile_push,web_push,inapp,call",
        {
            # All channels forced at once
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user9@example.ca"
        "?cc=Chris<l2g@nuxref.com>",
        {
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user10@example.ca?cc=invalid",
        {
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user11@example.ca?to=invalid",
        {
            # an invalid to email
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id1/user12@example.ca"
        "?to=id,Chris<chris2@example.com>",
        {
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id2/user13@example.ca/"
        "id/kris@example.com/id/chris2@example.com/id/+15552341234"
        "?:token=value",
        {
            # Several targets to notify
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user14@example.ca"
        "?bcc=Chris<chris14@example.com>",
        {
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user@example.ca"
        "?:sub=value&:sub2=value2",
        {
            # A good email with template substitutions
            "instance": NotifyPingram,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
            "privacy_url": "pingram://p...3/",
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user@example.ca",
        {
            "instance": NotifyPingram,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user@example.ca",
        {
            "instance": NotifyPingram,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
    (
        "pingram://pingram_sk_abc123/id/user@example.ca",
        {
            "instance": NotifyPingram,
            # Throws connection and transfer exceptions when this
            # flag is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
            "requests_response_text": PINGRAM_GOOD_RESPONSE,
        },
    ),
)


def test_plugin_pingram_urls():
    """NotifyPingram() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_pingram_template_sms_payloads(mock_post):
    """NotifyPingram() Testing Template SMS Payloads."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = PINGRAM_GOOD_RESPONSE

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # Details
    apikey = "pingram_sk_my_key"
    message_type = "apprise-post"
    targets = "userid/+1-555-123-4567"

    obj = Apprise.instantiate(
        f"pingram://{message_type}@{apikey}/{targets}?mode=template"
    )
    assert isinstance(obj, NotifyPingram)
    assert isinstance(obj.url(), str)

    # No calls made yet
    assert mock_post.call_count == 0

    # Send our notification
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # delivery of message
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "https://api.pingram.io/send"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {
        "type": "apprise-post",
        "to": {
            "id": "userid",
            "number": "+15551234567",
        },
        "parameters": {
            "appBody": "body",
            "appTitle": "title",
            "appType": "info",
            "appId": "Apprise",
            "appDescription": "Apprise Notifications",
            "appColor": "#3AA3E3",
            "appImageUrl": (
                "https://github.com/caronc/apprise/raw/master/apprise"
                "/assets/themes/default/apprise-info-72x72.png"
            ),
            "appUrl": "https://github.com/caronc/apprise",
        },
    }
    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
        "User-Agent": "Apprise",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {apikey}",
    }

    # Reset our mock object
    mock_post.reset_mock()


@mock.patch("requests.post")
def test_plugin_pingram_template_email_payloads(mock_post):
    """NotifyPingram() Testing Template Email Payloads."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = PINGRAM_GOOD_RESPONSE

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # Details
    apikey = "pingram_sk_my_key_abc"
    message_type = "apprise-post"
    targets = "userid/test@example.ca"

    obj = Apprise.instantiate(
        f"pingram://{message_type}@{apikey}/{targets}"
        f"?from=Chris<chris@example.eu>&bcc=joe@hidden.com&"
        f"cc=jason@hidden.com&:customToken=customValue&mode=template"
    )
    assert isinstance(obj, NotifyPingram)
    assert isinstance(obj.url(), str)

    # No calls made yet
    assert mock_post.call_count == 0

    # Send our notification
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # delivery of message
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "https://api.pingram.io/send"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {
        "type": "apprise-post",
        "to": {
            "id": "userid",
            "email": "test@example.ca",
        },
        "options": {
            "email": {
                "fromAddress": "chris@example.eu",
                "fromName": "Chris",
                "ccAddresses": ["jason@hidden.com"],
                "bccAddresses": ["joe@hidden.com"],
            }
        },
        "parameters": {
            "customToken": "customValue",
            "appBody": "body",
            "appTitle": "title",
            "appType": "info",
            "appId": "Apprise",
            "appDescription": "Apprise Notifications",
            "appColor": "#3AA3E3",
            "appImageUrl": (
                "https://github.com/caronc/apprise/raw/master/apprise/"
                "assets/themes/default/apprise-info-72x72.png"
            ),
            "appUrl": "https://github.com/caronc/apprise",
        },
    }
    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
        "User-Agent": "Apprise",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {apikey}",
    }

    # Reset our mock object
    mock_post.reset_mock()


@mock.patch("requests.post")
def test_plugin_pingram_message_payloads(mock_post):
    """NotifyPingram() Testing Message Payloads."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = PINGRAM_GOOD_RESPONSE

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # Details
    apikey = "pingram_sk_my_key_abc"
    message_type = "apprise-post"
    targets = "userid/test@example.ca/+15551239876"

    obj = Apprise.instantiate(
        f"pingram://{message_type}@{apikey}/{targets}"
        f"?from=Chris<chris@example.eu>&bcc=joe@hidden.com"
        f"&mode=message"
    )
    assert isinstance(obj, NotifyPingram)
    assert isinstance(obj.url(), str)

    # Send our notification
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # delivery of message
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "https://api.pingram.io/send"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {
        "type": "apprise-post",
        "to": {
            "id": "userid",
            "email": "test@example.ca",
            "number": "+15551239876",
        },
        "email": {
            "subject": "title",
            "html": "body",
            "senderName": "Chris",
            "senderEmail": "chris@example.eu",
        },
        "options": {
            "email": {
                "fromAddress": "chris@example.eu",
                "fromName": "Chris",
                "bccAddresses": ["joe@hidden.com"],
            },
        },
    }
    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
        "User-Agent": "Apprise",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {apikey}",
    }

    # Reset our mock object
    mock_post.reset_mock()

    # Reversing the sms with email causes auto-detection channel to
    # be sms instead of email
    targets = "userid/+15551239876/test@example.ca"

    obj = Apprise.instantiate(
        f"pingram://{apikey}/{targets}"
        f"?from=Chris<chris@example.eu>&bcc=joe@hidden.com"
    )
    assert isinstance(obj, NotifyPingram)
    assert isinstance(obj.url(), str)

    # Send our notification
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # delivery of message
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "https://api.pingram.io/send"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {
        "type": "apprise",
        "to": {
            "id": "userid",
            "number": "+15551239876",
            "email": "test@example.ca",
        },
        "sms": {"message": "title\nbody"},
        "options": {
            "email": {
                "fromAddress": "chris@example.eu",
                "fromName": "Chris",
                "bccAddresses": ["joe@hidden.com"],
            },
        },
    }

    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
        "User-Agent": "Apprise",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {apikey}",
    }

    # Reset our mock object
    mock_post.reset_mock()

    # Experiment with fixed channels (including the call/TTS channel)
    obj = Apprise.instantiate(
        f"pingram://{message_type}@{apikey}/{targets}"
        f"?from=Chris<chris@example.eu>&bcc=joe@hidden.com"
        f"&mode=message&channels=sms,slack,call"
    )
    assert isinstance(obj, NotifyPingram)
    assert isinstance(obj.url(), str)

    # Send our notification
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    # delivery of message
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "https://api.pingram.io/send"

    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {
        "type": "apprise-post",
        "to": {
            "id": "userid",
            "email": "test@example.ca",
            "number": "+15551239876",
        },
        "slack": {"text": "title\nbody"},
        "sms": {"message": "title\nbody"},
        "call": {"message": "title\nbody"},
        "options": {
            "email": {
                "fromAddress": "chris@example.eu",
                "fromName": "Chris",
                "bccAddresses": ["joe@hidden.com"],
            },
        },
    }

    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
        "User-Agent": "Apprise",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {apikey}",
    }


@mock.patch("requests.post")
def test_plugin_pingram_targets(mock_post):
    """NotifyPingram() Testing Target Parsing."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = PINGRAM_GOOD_RESPONSE

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    apikey = "pingram_sk_abc123"

    # A bare phone number with no id is valid
    obj = Apprise.instantiate(f"pingram://{apikey}/+15551234567")
    assert isinstance(obj, NotifyPingram)
    assert isinstance(obj.url(), str)

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )

    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == "https://api.pingram.io/send"

    # No "id" present since none was supplied in the URL
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload == {
        "type": "apprise",
        "to": {
            "number": "+15551234567",
        },
        "sms": {"message": "title\nbody"},
    }

    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
        "User-Agent": "Apprise",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {apikey}",
    }

    mock_post.reset_mock()

    # Multiple id-less phone targets each become their own recipient
    obj = Apprise.instantiate(f"pingram://{apikey}/+15551234567/+15551234568")
    assert isinstance(obj, NotifyPingram)
    assert len(obj.targets) == 2

    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_post.call_count == 2

    mock_post.reset_mock()

    # Region support carries over to the Pingram endpoints too
    obj = Apprise.instantiate(f"pingram://{apikey}/+15551234567?region=eu")
    assert isinstance(obj, NotifyPingram)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0] == "https://api.eu.pingram.io/send"
    )

    mock_post.reset_mock()

    # An id can still optionally be supplied alongside the number
    obj = Apprise.instantiate(f"pingram://{apikey}/myid/+15551234567")
    assert isinstance(obj, NotifyPingram)
    assert (
        obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
        is True
    )
    payload = loads(mock_post.call_args_list[0][1]["data"])
    assert payload["to"] == {"id": "myid", "number": "+15551234567"}


def test_plugin_pingram_edge_cases():
    """NotifyPingram() Edge Cases."""

    # No API Key raises TypeError
    with pytest.raises(TypeError):
        NotifyPingram(apikey=None, targets=["+15551239876"])

    # An invalid API Key (wrong prefix) raises TypeError
    with pytest.raises(TypeError):
        NotifyPingram(apikey="not-a-pingram-key", targets=["+15551239876"])

    # Tests case where tokens is == None
    obj = NotifyPingram(apikey="pingram_sk_my_key", targets=["+15551239876"])
    assert isinstance(obj, NotifyPingram)
    assert isinstance(obj.url(), str)
    assert obj.tokens == {}
