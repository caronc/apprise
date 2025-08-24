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

from json import dumps

# Disable logging for a cleaner testing output
import logging
import os

from helpers import AppriseURLTester
import requests

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
    ("napi://type@client_id/client_secret/id:+15551235555/", {
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://type@cid/secret/id:user@example.com/", {
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    (("napi://type@cid/secret/id:user@example.com/"
      "id:+15551235555/id:+15551235534"), {
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    (("napi://type@cid/secret/id:user@example.com/"
      "?from=joe@example.ca"), {
        # Set from/source
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    (("napi://type@cid/secret/id:user@example.com/"
      "?from=joe@example.ca&bcc=user1@yahoo.ca&cc=user2@yahoo.ca"), {
        # Set from/source
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://?id=ci&secret=cs&to=id:user@example.com&type=type", {
        # use just kwargs
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://?id=ci&secret=cs&type=test-type", {
        # No targets specified
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
        "notify_response": False,
    }),
    ("napi://user@client_id/cs2/id:user@example.ca"
     "?bcc=invalid", {
         # A good email with a bad Blind Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs3/id:user@example.ca"
     "?cc=l2g@nuxref.com", {
         # A good email with Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs4/id:user@example.ca"
     "?cc=Chris<l2g@nuxref.com>", {
         # A good email with Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs5/id:user@example.ca"
     "?cc=invalid", {
         # A good email with Carbon Copy
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs6/id:user@example.ca"
     "?to=invalid", {
         # an invalid to email
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
     ("napi://user@client_id/cs7/id:chris@example.com", {
        # An email with a designated to email
        "instance": NotifyNotificationAPI,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://user@client_id/cs8/id:user@example.ca"
     "?to=id:Chris<chris@example.com>", {
         # An email with a full name in in To field
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs9/id:user@example.ca"
     "id:chris@example.com/id:chris2@example.com/id:+15552341234", {
         # Several emails to notify
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs10/id:user@example.ca"
     "?cc=Chris<chris@example.com>", {
         # An email with a full name in cc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs11/id:user@example.ca"
     "?cc=chris@example.com", {
         # An email with a full name in cc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs12/id:user@example.ca"
     "?bcc=Chris<chris@example.com>", {
         # An email with a full name in bcc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs13/id:user@example.ca"
     "?bcc=chris@example.com", {
         # An email with a full name in bcc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs14/id:user@example.ca"
     "?to=Chris<chris@example.com>", {
         # An email with a full name in bcc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs15/id:user@example.ca"
     "?to=chris@example.com", {
         # An email with a full name in bcc
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
     }),
    ("napi://user@client_id/cs16/id:user@example.ca"
     "?template=1234&+sub=value&+sub2=value2", {
         # A good email with a template + substitutions
         "instance": NotifyNotificationAPI,
         "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,

         # Our expected url(privacy=True) startswith() response:
         "privacy_url": "napi://user@c...d/c...6/",
     }),
    ("napi://user@client_id/cs17/id:user@example.ca", {
        "instance": NotifyNotificationAPI,
        # force a failure
        "response": False,
        "requests_response_code": requests.codes.internal_server_error,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://user@client_id/cs18/id:user@example.ca", {
        "instance": NotifyNotificationAPI,
        # throw a bizzare code forcing us to fail to look it up
        "response": False,
        "requests_response_code": 999,
        "requests_response_text": NOTIFICATIONAPI_GOOD_RESPONSE,
    }),
    ("napi://user@client_id/cs19/id:user@example.ca", {
        "instance": NotifyNotificationAPI,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
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
