# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

from unittest import mock

import pytest
import requests
from json import dumps

from apprise.plugins.NotifyRingCentral import NotifyRingCentral
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

GOOD_RESPONSE = {
    # Authentication (JWT / Auth)
    "access_token": "abc123",
    "token_type": "bearer",
    "expires_in": 3600,
    "scope": "Faxes SMS TeamMessaging A2PSMS",
    "owner_id": "123",
    "endpoint_id": "akfJbWJYQ7GEUev2CaR37k",

    # SMS Message
    "uri": "https://platform.devtest.ringcentral.com/restapi/v1.0/"
           "account/123/extension/123/message-store/123",
    "id": 123,
    "to": [{
        "phoneNumber": "+14223453486",
        "name": "Chris",
        "location": "Mars, MW",
    }],
    "from": {
        "phoneNumber": "+14223452386",
        "name": "Chris",
        "location": "Mars, MW",
    },
    "type": "SMS",
    "creationTime": "2023-05-22T22:54:36.000Z",
    "readStatus": "Read",
    "priority": "Normal",
    "attachments": [{
        "id": 123,
        "uri": "https://platform.devtest.ringcentral.com/restapi/v1.0/" \
                "account/123/extension/123/message-store/123/content/123",
                "type": "Text",
                "contentType": "text/plain",
    }],
    "direction": "Outbound",
    "availability": "Alive",
    "subject": "Test SMS using a RingCentral Developer account - test",
    "messageStatus": "Queued",
    "smsSendingAttemptsCount": 1,
    "conversationId": 18765,
    "conversation": {
        "id": "13456",
        "uri": "https://platform.devtest.ringcentral.com/restapi/v1.0/"
        "conversation/1439618117011964583",
    },
    "lastModifiedTime": "2023-05-22T22:54:36.907Z",
}

# Our Testing URLs
apprise_url_tests = (
    ('ringc://', {
        # No credentials at all
        'instance': TypeError,
    }),
    ('ringc://:@/', {
        # No credentials at all
        'instance': TypeError,
    }),
    ('ringc://password@client_id/18005554321', {
        # Just a key provided - no client secret
        'instance': TypeError,
    }),
    ('ringc://password@client_id/18005554321', {
        # Just a key provided - no client secret
        'instance': TypeError,
    }),
    ('ringc://18005554321:jwt{}@client_id'.format('a' * 60), {
        # JWT Provided but no client secret
        'instance': TypeError,
    }),
    ('ringc://18005554321:jwt{}@%!%/secret'.format('b' * 60), {
        # Invalid client id
        'instance': TypeError,
    }),
    ('ringc://18005554321:jwt{}@client_id/%!%/'.format('c' * 60), {
        # Invalid client secret
        'instance': TypeError,
    }),
    ('ringc://18005554321:jwt{}@client_id/secret/1555123456'.format(
        'c' * 60), {
            # Valid everything
            'instance': NotifyRingCentral,

            # Return a good response
            'requests_response_text': GOOD_RESPONSE,

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'ringc://18005554321:j...c@c...d/****/',
    }),
    ('ringc://18005554321:jwt{}@client_id/secret'.format('c' * 60), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': NotifyRingCentral,
        # Return a good response
        'requests_response_text': GOOD_RESPONSE,
    }),
    ('ringc://_?token={}&secret={}&from={}'.format(
        'a' * 8, 'b' * 16, '5' * 11), {
        # Return a good response
        'requests_response_text': GOOD_RESPONSE,
        # use get args to acomplish the same thing
        'instance': NotifyRingCentral,
    }),
    ('ringc://_?token={}&secret={}&source={}'.format(
        'a' * 8, 'b' * 16, '5' * 11), {
        # Return a good response
        'requests_response_text': GOOD_RESPONSE,
        # use get args to acomplish the same thing (use source instead of from)
        'instance': NotifyRingCentral,
    }),
    ('ringc://_?token={}&secret={}&from={}&to={}'.format(
        'a' * 8, 'b' * 16, '5' * 11, '7' * 13), {
        # Return a good response
        'requests_response_text': GOOD_RESPONSE,
        # use to=
        'instance': NotifyRingCentral,
    }),
    ('ringc://18005554321:jwt{}@client_id/secret'.format('c' * 60), {
        'instance': NotifyRingCentral,
        # Return a good response
        'requests_response_text': GOOD_RESPONSE,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('ringc://18005554321:jwt{}@client_id/secret'.format('c' * 60), {
        'instance': NotifyRingCentral,
        # Return a good response
        'requests_response_text': GOOD_RESPONSE,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_ringc_urls():
    """
    NotifyRingCentral() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_ringc_edge_cases(mock_post):
    """
    NotifyRingCentral() Edge Cases

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    client_id = 'client_id'
    client_secret = 'client-secret'
    source = '+1 (555) 123-3456'

    # No client_id specified
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=None, client_secret=client_secret, source=source)

    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id="  ", client_secret=client_secret, source=source)

    # No secret specified
    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=client_id, client_secret=None, source=source)

    with pytest.raises(TypeError):
        NotifyRingCentral(
            client_id=client_id, client_secret="  ", source=source)

    # a error response
    response.status_code = 400
    response.content = dumps({
        'code': 21211,
        'message': "The 'To' number +1234567 is not a valid phone number.",
    })
    mock_post.return_value = response

    # Initialize our object
    obj = NotifyRingCentral(
        client_id=client_id, client_secret=client_secret, source=source)

    # We will fail with the above error code
    assert obj.notify('title', 'body', 'info') is False
