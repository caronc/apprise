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

from json import dumps, loads

# Disable logging for a cleaner testing output
import logging
import os
from unittest import mock

from helpers import AppriseURLTester
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.notificationapi import NotifyNotificationAPI

logging.disable(logging.CRITICAL)

NOTIFICATIONAPI_GOOD_RESPONSE = dumps({})

NOTIFICATIONAPI_BAD_RESPONSE = "{"

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# Our Testing URLs
apprise_url_tests = (
    ("napi://", {
        "instance": TypeError,
    }),
    ("napi://:@/", {
        "instance": TypeError,
    }),
    ("napi://abcd", {
        # invalid from email
        "instance": TypeError,
    }),
    ("napi://abcd@host.com", {
        # Just an Email specified, no client_id or client_secret
        "instance": TypeError,
    }),
    ("napi://user@client_id/cs14a/user@example.ca", {
        # No id matched
        "instance": TypeError,
    }),
    ("napi://user@client_id/cs14b/+15551235553", {
        # No id matched
        "instance": TypeError,
    }),
    ("napi://user@client_id/cs14c/+15551235553/user@example.ca", {
        # No id matched
        "instance": TypeError,
    }),

    ("napi://type@client_id/client_secret/id/+15551235553/?mode=invalid", {
        # Invalid mode
        "instance": TypeError,
    }),
    ("napi://type@client_id/client_secret/id/+15551235553/?region=invalid", {
        # Invalid region
        "instance": TypeError,
    }),
    ((
        "napi://type@client_id/client_secret/id/user@example.ca/"
        "user2@example.ca"
        ), {
        # to many emails assigned to id (variation 1)
        "instance": TypeError,
    }),
    ((
        "napi://type@client_id/client_secret/user@example.ca/"
        "user2@example.ca"
        ), {
        # to many emails assigned to id (variation 2)
        "instance": TypeError,
    }),
    ((
        "napi://type@client_id/client_secret/id/+15551235553/"
        "+15551235555"
        ), {
        # to many phone no's assigned to id (variation 1)
        "instance": TypeError,
    }),
    ((
        "napi://type@client_id/client_secret/+15551235553/"
        "+15551235555"
        ), {
        # to many phone no's assigned to id (variation 2)
        "instance": TypeError,
    }),
    ("napi://type@client_id/client_secret/id/+15551235553/?mode=invalid", {
        # Invalid mode
        "instance": TypeError,
    }),
    ("napi://client_id/client_secret/id/+15551231234/?type=*(", {
        # Invalid type
        "instance": TypeError,
    }),
    ("napi://client_id/client_secret/id/+15551231234/?channels=bad", {
        # Invalid channel
        "instance": TypeError,
    }),
    ("napi://?secret=cs&to=id,user404@example.com&type=typed", {
        # No id found
        "instance": TypeError,
    }),
    ("napi://client_id/client_secret/id/g@rb@ge/+15551235553/", {
        # g@rb@ge entry ignored
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://cid/secret/id/user1@example.com/?type=apprise-msg", {
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("notificationapi://cid/secret/id/user1@example.com", {
        # Support full schema:// of notificationapi://
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://cid/secret/id/id2/user1@example.com", {
        # two id's in a row
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    (("napi://type@cid/secret/id10/user2@example.com/"
      "id5/+15551235555/id8/+15551235534"
      "?reply=Chris<chris@example.com>"), {
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    (("napi://type@cid/secret/abc1/user1@example.com/"
      "id5/+15551235555/?from=Chris&reply=Christopher"), {
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    (("napi://type@cid/secret/id/user3@example.com/"
      "?from=joe@example.ca&reply=user@abc.com"), {
        # Set from/source
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    (("napi://type@cid/secret/id/user4@example.com/"
      "?from=joe@example.ca&bcc=user1@yahoo.ca&cc=user2@yahoo.ca"), {
        # Set from/source
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
        # Our expected url(privacy=True) startswith() response:
        "privacy_url": "napi://type@c...d/s...t/",
    }),
    ("napi://?id=ci&secret=cs&to=id,user5@example.com&type=typec", {
        # use just kwargs
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
        # Our expected url(privacy=True) startswith() response:
        "privacy_url": "napi://typec@c...i/c...s/",
    }),
    ("napi://id?secret=cs&to=id,user5@example.com&type=typeb", {
        # id is pull from the host
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
        # Our expected url(privacy=True) startswith() response:
        "privacy_url": "napi://typeb@i...d/c...s/",
    }),
    ("napi://secret?id=ci&to=id,user5@example.com&type=typea", {
        # id pulled from kwargs still allows secret to be the
        # next parsed entry from cli
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
        # Our expected url(privacy=True) startswith() response:
        "privacy_url": "napi://typea@c...i/s...t/",
    }),
    ("napi://?id=ci&secret=cs&type=test-type&region=eu", {
        # No targets specified
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
        "notify_response": False,
    }),
    ("napi://?id=ci&secret=cs&to=id,user5@example.com&type=typec", {
        # bad response
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_BAD_RESPONSE,
        "notify_response": False,
    }),
    ("napi://user@client_id/cs2/id/user6@example.ca"
     "?bcc=invalid", {
         # A good email with a bad Blind Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs3/id/user8@example.ca"
     "?cc=l2g@nuxref.com", {
         # A good email with Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://client_id/cs3/id/user8@example.ca"
     "?channels=email,sms,slack,mobile_push,web_push,inapp", {
         # A good email with Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs4/id/user9@example.ca"
     "?cc=Chris<l2g@nuxref.com>", {
         # A good email with Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs5/id/user10@example.ca"
     "?cc=invalid", {
         # A good email with Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs6/id/user11@example.ca"
     "?to=invalid", {
         # an invalid to email
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs7/id/chris1@example.com", {
        # An email with a designated to email
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs8/id1/user12@example.ca"
     "?to=id,Chris<chris2@example.com>", {
         # An email with a full name in in To field
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs9/id2/user13@example.ca/"
     "id/kris@example.com/id/chris2@example.com/id/+15552341234"
     "?:token=value", {
         # Several emails to notify
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs10/id/user14@example.ca"
     "?cc=Chris<chris10@example.com>", {
         # An email with a full name in cc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs11/id/user15@example.ca"
     "?cc=chris12@example.com", {
         # An email with a full name in cc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs12/id/user16@example.ca"
     "?bcc=Chris<chris14@example.com>", {
         # An email with a full name in bcc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs13/id/user@example.ca"
     "?bcc=chris13@example.com", {
         # An email with a full name in bcc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs14/id/user@example.ca"
     "?to=Chris<chris9@example.com>,id14", {
         # An email with a full name in bcc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs15/id"
     "?to=user@example.com", {
         # An email with a full name in bcc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs16/id/user@example.ca"
     "?template=1234&+sub=value&+sub2=value2", {
         # A good email with a template + substitutions
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,

         # Our expected url(privacy=True) startswith() response:
         "privacy_url": "napi://user@c...d/c...6/",
     }),
    ("napi://user@client_id/cs17/id/user@example.ca", {
        "instance": NotifyNotificationAPI,
        # force a failure
        "response": False,
        "requests_response_code": requests.codes.internal_server_error,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://user@client_id/cs18/id/user@example.ca", {
        "instance": NotifyNotificationAPI,
        # throw a bizarre code forcing us to fail to look it up
        "response": False,
        "requests_response_code": 999,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://user@client_id/cs19/id/user@example.ca", {
        "instance": NotifyNotificationAPI,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracefully handle them
        "test_requests_exceptions": True,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
)


def test_plugin_napi_urls():
    """
    NotifyNotificationAPI() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_napi_template_sms_payloads(mock_post):
    """NotifyNotificationAPI() Testing Template SMS Payloads."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = NOTIFICATIONAPI_GOOD_RESPONSE

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # Details
    client_id = "my_id"
    client_secret = "my_secret"
    message_type = "apprise-post"
    targets = "userid/+1-555-123-4567"

    obj = Apprise.instantiate(
        f"napi://{message_type}@{client_id}/{client_secret}/"
        f"{targets}?mode=template")
    assert isinstance(obj, NotifyNotificationAPI)
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
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://api.notificationapi.com/{client_id}/sender"
    )

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
                "/assets/themes/default/apprise-info-72x72.png"),
            "appUrl": "https://github.com/caronc/apprise"},
    }
    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
            "User-Agent": "Apprise",
            "Content-Type": "application/json",
            "Authorization": "Basic bXlfaWQ6bXlfc2VjcmV0"}

    # Reset our mock object
    mock_post.reset_mock()


@mock.patch("requests.post")
def test_plugin_napi_template_email_payloads(mock_post):
    """NotifyNotificationAPI() Testing Template Email Payloads."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = NOTIFICATIONAPI_GOOD_RESPONSE

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # Details
    client_id = "my_id_abc"
    client_secret = "my_secret"
    message_type = "apprise-post"
    targets = "userid/test@example.ca"

    obj = Apprise.instantiate(
        f"napi://{message_type}@{client_id}/{client_secret}/"
        f"{targets}?from=Chris<chris@example.eu>&bcc=joe@hidden.com&"
        f"cc=jason@hidden.com&:customToken=customValue&mode=template")
    assert isinstance(obj, NotifyNotificationAPI)
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
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://api.notificationapi.com/{client_id}/sender"
    )

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
                "bccAddresses": ["joe@hidden.com"]}
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
                "assets/themes/default/apprise-info-72x72.png"),
            "appUrl": "https://github.com/caronc/apprise"
        },
    }
    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
        "User-Agent": "Apprise",
        "Content-Type": "application/json",
        "Authorization": "Basic bXlfaWRfYWJjOm15X3NlY3JldA=="}

    # Reset our mock object
    mock_post.reset_mock()


@mock.patch("requests.post")
def test_plugin_napi_message_payloads(mock_post):
    """NotifyNotificationAPI() Testing Message Payloads."""

    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = NOTIFICATIONAPI_GOOD_RESPONSE

    # Assign our mock object our return value
    mock_post.return_value = okay_response

    # Details
    client_id = "my_id_abc"
    client_secret = "my_secret"
    message_type = "apprise-post"
    targets = "userid/test@example.ca/+15551239876"

    obj = Apprise.instantiate(
        f"napi://{message_type}@{client_id}/{client_secret}/"
        f"{targets}?from=Chris<chris@example.eu>&bcc=joe@hidden.com"
        f"&mode=message")
    assert isinstance(obj, NotifyNotificationAPI)
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
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://api.notificationapi.com/{client_id}/sender"
    )

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
        "Authorization": "Basic bXlfaWRfYWJjOm15X3NlY3JldA=="}

    # Reset our mock object
    mock_post.reset_mock()

    # Reversing the sms with email causes auto-detection channel to
    # be sms instead of email
    targets = "userid/+15551239876/test@example.ca"

    obj = Apprise.instantiate(
        f"napi://{client_id}/{client_secret}/"
        f"{targets}?from=Chris<chris@example.eu>&bcc=joe@hidden.com")
    assert isinstance(obj, NotifyNotificationAPI)
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
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://api.notificationapi.com/{client_id}/sender"
    )

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
                "bccAddresses": ["joe@hidden.com"]},
        },
    }

    headers = mock_post.call_args_list[0][1]["headers"]
    assert headers == {
        "User-Agent": "Apprise",
        "Content-Type": "application/json",
        "Authorization": "Basic bXlfaWRfYWJjOm15X3NlY3JldA=="}

    # Reset our mock object
    mock_post.reset_mock()

    # Experiment with fixed channels:
    obj = Apprise.instantiate(
        f"napi://{message_type}@{client_id}/{client_secret}/"
        f"{targets}?from=Chris<chris@example.eu>&bcc=joe@hidden.com"
        f"&mode=message&channels=sms,slack")
    assert isinstance(obj, NotifyNotificationAPI)
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
    assert (
        mock_post.call_args_list[0][0][0]
        == f"https://api.notificationapi.com/{client_id}/sender"
    )

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
        "Authorization": "Basic bXlfaWRfYWJjOm15X3NlY3JldA=="}


def test_plugin_napi_edge_cases():
    """
    NotifyNotificationAPI() Edge Cases

    """
    client_id = "my_id_abc"
    client_secret = "my_secret"
    targets = ["userid", "test@example.ca", "+15551239876"]

    # Tests case where tokens is == None
    obj = NotifyNotificationAPI(client_id, client_secret, targets=targets)
    assert isinstance(obj, NotifyNotificationAPI)
    assert isinstance(obj.url(), str)
