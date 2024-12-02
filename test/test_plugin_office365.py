# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import os
from unittest import mock

import pytest
import requests
from datetime import datetime
from json import dumps
from apprise import Apprise
from apprise import NotifyType
from apprise import AppriseAttachment
from apprise.plugins.office365 import NotifyOffice365
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyOffice365
    ##################################
    ('o365://', {
        # Missing tenant, client_id, secret, and targets!
        'instance': TypeError,
    }),
    ('o365://:@/', {
        # invalid url
        'instance': TypeError,
    }),
    ('o365://{aid}/{tenant}/{cid}/{secret}/{targets}'.format(
        # invalid tenant
        tenant=',',
        cid='ab-cd-ef-gh',
        aid='user@example.com',
        secret='abcd/123/3343/@jack/test',
        targets='/'.join(['email1@test.ca'])), {

        # Expected failure
        'instance': TypeError,
    }),
    ('o365://{aid}/{tenant}/{cid}/{secret}/{targets}'.format(
        tenant='tenant',
        # invalid client id
        cid='ab.',
        aid='user2@example.com',
        secret='abcd/123/3343/@jack/test',
        targets='/'.join(['email1@test.ca'])), {

        # Expected failure
        'instance': TypeError,
    }),
    ('o365://{tenant}/{cid}/{secret}/{targets}'.format(
        # email not required if mode is set to self
        tenant='tenant',
        cid='ab-cd-ef-gh',
        secret='abcd/123/3343/@jack/test',
        targets='/'.join(['email1@test.ca'])), {

        # We're valid and good to go
        'instance': NotifyOffice365,

        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'expires_in': 2000,
            'access_token': 'abcd1234',
        },
    }),
    ('o365://{aid}/{tenant}/{cid}/{secret}/{targets}'.format(
        tenant='tenant',
        cid='ab-cd-ef-gh',
        aid='user@example.edu',
        secret='abcd/123/3343/@jack/test',
        targets='/'.join(['email1@test.ca'])), {

        # We're valid and good to go
        'instance': NotifyOffice365,

        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'expires_in': 2000,
            'access_token': 'abcd1234',
        },

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'azure://user@example.edu/t...t/a...h/'
                       '****/email1@test.ca/'}),
    ('o365://{aid}/{tenant}/{cid}/{secret}/{targets}'.format(
        tenant='tenant',
        cid='ab-cd-ef-gh',
        # Source can also be Object ID
        aid='hg-fe-dc-ba',
        secret='abcd/123/3343/@jack/test',
        targets='/'.join(['email1@test.ca'])), {

        # We're valid and good to go
        'instance': NotifyOffice365,

        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'expires_in': 2000,
            'access_token': 'abcd1234',
        },

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'azure://hg-fe-dc-ba/t...t/a...h/'
                       '****/email1@test.ca/'}),

    # ObjectID Specified, but no targets
    ('o365://{aid}/{tenant}/{cid}/{secret}/'.format(
        tenant='tenant',
        cid='ab-cd-ef-gh',
        # Source can also be Object ID
        aid='hg-fe-dc-ba',
        secret='abcd/123/3343/@jack/test'), {

        # We're valid and good to go
        'instance': NotifyOffice365,

        # Test what happens if a batch send fails to return a messageCount
        'requests_response_text': {
            'expires_in': 2000,
            'access_token': 'abcd1234',
        },
        # No emails detected
        'notify_response': False,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'azure://hg-fe-dc-ba/t...t/a...h/****'}),

    # test our arguments
    ('o365://_/?oauth_id={cid}&oauth_secret={secret}&tenant={tenant}'
        '&to={targets}&from={aid}'.format(
            tenant='tenant',
            cid='ab-cd-ef-gh',
            aid='user@example.ca',
            secret='abcd/123/3343/@jack/test',
            targets='email1@test.ca'),
        {
            # We're valid and good to go
            'instance': NotifyOffice365,

            # Test what happens if a batch send fails to return a messageCount
            'requests_response_text': {
                'expires_in': 2000,
                'access_token': 'abcd1234',
            },

            # Our expected url(privacy=True) startswith() response:
            'privacy_url': 'azure://user@example.ca/t...t/a...h/'
                           '****/email1@test.ca/'}),
    # Test invalid JSON (no tenant defaults to email domain)
    ('o365://{aid}/{tenant}/{cid}/{secret}/{targets}'.format(
        tenant='tenant',
        cid='ab-cd-ef-gh',
        aid='user@example.com',
        secret='abcd/123/3343/@jack/test',
        targets='/'.join(['email1@test.ca'])), {

        # We're valid and good to go
        'instance': NotifyOffice365,

        # invalid JSON response
        'requests_response_text': '{',
        'notify_response': False,
    }),
    # No Targets specified
    ('o365://{aid}/{tenant}/{cid}/{secret}'.format(
        tenant='tenant',
        cid='ab-cd-ef-gh',
        aid='user@example.com',
        secret='abcd/123/3343/@jack/test'), {

        # We're valid and good to go
        'instance': NotifyOffice365,

        # There were no targets to notify; so we use our own email
        'requests_response_text': {
            'expires_in': 2000,
            'access_token': 'abcd1234',
        },
    }),
    ('o365://{aid}/{tenant}/{cid}/{secret}/{targets}'.format(
        tenant='tenant',
        cid='zz-zz-zz-zz',
        aid='user@example.com',
        secret='abcd/abc/dcba/@john/test',
        targets='/'.join(['email1@test.ca'])), {
        'instance': NotifyOffice365,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('o365://{tenant}:{aid}/{cid}/{secret}/{targets}'.format(
        tenant='tenant',
        cid='01-12-23-34',
        aid='user@example.com',
        secret='abcd/321/4321/@test/test',
        targets='/'.join(['email1@test.ca'])), {
        'instance': NotifyOffice365,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_office365_urls():
    """
    NotifyOffice365() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_office365_general(mock_post):
    """
    NotifyOffice365() General Testing

    """

    # Initialize some generic (but valid) tokens
    email = 'user@example.net'
    tenant = 'ff-gg-hh-ii-jj'
    client_id = 'aa-bb-cc-dd-ee'
    secret = 'abcd/1234/abcd@ajd@/test'
    targets = 'target@example.com'

    # Prepare Mock return object
    authentication = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234"
    }
    response = mock.Mock()
    response.content = dumps(authentication)
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        'o365://{email}/{tenant}/{secret}/{targets}'.format(
            tenant=tenant,
            email=email,
            secret=secret,
            targets=targets))

    assert isinstance(obj, NotifyOffice365)

    # Test our URL generation
    assert isinstance(obj.url(), str)

    # Test our notification
    assert obj.notify(title='title', body='test') is True

    # Instantiate our object
    obj = Apprise.instantiate(
        'o365://{email}/{tenant}/{client_id}/{secret}/{targets}'
        '?bcc={bcc}&cc={cc}'.format(
            tenant=tenant,
            email=email,
            client_id=client_id,
            secret=secret,
            targets=targets,
            # Test the cc and bcc list (use good and bad email)
            cc='Chuck Norris cnorris@yahoo.ca, Sauron@lotr.me, invalid@!',
            bcc='Bruce Willis bwillis@hotmail.com, Frodo@lotr.me invalid@!',
        ))

    assert isinstance(obj, NotifyOffice365)

    # Test our URL generation
    assert isinstance(obj.url(), str)

    # Test our notification
    assert obj.notify(title='title', body='test') is True

    with pytest.raises(TypeError):
        # No secret
        NotifyOffice365(
            email=email,
            client_id=client_id,
            tenant=tenant,
            secret=None,
            targets=None,
        )

    # One of the targets are invalid
    obj = NotifyOffice365(
        email=email,
        client_id=client_id,
        tenant=tenant,
        secret=secret,
        targets=('Management abc@gmail.com', 'garbage'),
    )
    # Test our notification (this will work and only notify abc@gmail.com)
    assert obj.notify(title='title', body='test') is True

    # all of the targets are invalid
    obj = NotifyOffice365(
        email=email,
        client_id=client_id,
        tenant=tenant,
        secret=secret,
        targets=('invalid', 'garbage'),
    )

    # Test our notification (which will fail because of no entries)
    assert obj.notify(title='title', body='test') is False


@mock.patch('requests.post')
def test_plugin_office365_authentication(mock_post):
    """
    NotifyOffice365() Authentication Testing

    """

    # Initialize some generic (but valid) tokens
    tenant = 'ff-gg-hh-ii-jj'
    email = 'user@example.net'
    client_id = 'aa-bb-cc-dd-ee'
    secret = 'abcd/1234/abcd@ajd@/test'
    targets = 'target@example.com'

    # Prepare Mock return object
    authentication_okay = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234"
    }
    authentication_failure = {
        "error": "invalid_scope",
        "error_description": "AADSTS70011: Blah... Blah Blah... Blah",
        "error_codes": [70011],
        "timestamp": "2020-01-09 02:02:12Z",
        "trace_id": "255d1aef-8c98-452f-ac51-23d051240864",
        "correlation_id": "fb3d2015-bc17-4bb9-bb85-30c5cf1aaaa7",
    }
    response = mock.Mock()
    response.content = dumps(authentication_okay)
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Instantiate our object
    obj = Apprise.instantiate(
        'azure://{email}/{tenant}/{client_id}/{secret}/{targets}'.format(
            client_id=client_id,
            tenant=tenant,
            email=email,
            secret=secret,
            targets=targets))

    assert isinstance(obj, NotifyOffice365)

    # Authenticate
    assert obj.authenticate() is True

    # We're already authenticated
    assert obj.authenticate() is True

    # Expire our token
    obj.token_expiry = datetime.now()

    # Re-authentiate
    assert obj.authenticate() is True

    # Change our response
    response.status_code = 400

    # We'll fail to send a notification now...
    assert obj.notify(title='title', body='test') is False

    # Expire our token
    obj.token_expiry = datetime.now()

    # Set a failure response
    response.content = dumps(authentication_failure)

    # We will fail to authenticate at this point
    assert obj.authenticate() is False

    # Notifications will also fail in this case
    assert obj.notify(title='title', body='test') is False

    # We will fail to authenticate with invalid data

    invalid_auth_entries = authentication_okay.copy()
    invalid_auth_entries['expires_in'] = 'garbage'
    response.content = dumps(invalid_auth_entries)
    response.status_code = requests.codes.ok
    assert obj.authenticate() is False

    invalid_auth_entries['expires_in'] = None
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False

    invalid_auth_entries['expires_in'] = ''
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False

    del invalid_auth_entries['expires_in']
    response.content = dumps(invalid_auth_entries)
    assert obj.authenticate() is False


@mock.patch('requests.post')
def test_plugin_office365_attachments(mock_post):
    """
    NotifyOffice365() Attachments

    """

    # Initialize some generic (but valid) tokens
    email = 'user@example.net'
    tenant = 'ff-gg-hh-ii-jj'
    client_id = 'aa-bb-cc-dd-ee'
    secret = 'abcd/1234/abcd@ajd@/test'
    targets = 'target@example.com'

    # Prepare Mock return object
    authentication = {
        "token_type": "Bearer",
        "expires_in": 6000,
        "access_token": "abcd1234"
    }
    okay_response = mock.Mock()
    okay_response.content = dumps(authentication)
    okay_response.status_code = requests.codes.ok
    mock_post.return_value = okay_response

    # Instantiate our object
    obj = Apprise.instantiate(
        'azure://{email}/{tenant}/{client_id}{secret}/{targets}'.format(
            client_id=client_id,
            tenant=tenant,
            email=email,
            secret=secret,
            targets=targets))

    assert isinstance(obj, NotifyOffice365)

    # Test Valid Attachment
    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://login.microsoftonline.com/{}/oauth2/v2.0/token'.format(tenant)
    assert mock_post.call_args_list[0][1]['headers'] \
        .get('Content-Type') == 'application/x-www-form-urlencoded'
    assert mock_post.call_args_list[1][0][0] == \
        'https://graph.microsoft.com/v1.0/users/{}/sendMail'.format(email)
    assert mock_post.call_args_list[1][1]['headers'] \
        .get('Content-Type') == 'application/json'
    mock_post.reset_mock()

    # Test invalid attachment
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False
    assert mock_post.call_count == 0
    mock_post.reset_mock()

    with mock.patch('base64.b64encode', side_effect=OSError()):
        # We can't send the message if we fail to parse the data
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False
    assert mock_post.call_count == 0
    mock_post.reset_mock()

    # Force a smaller attachment size forcing us to create an attachment
    obj.outlook_attachment_inline_max = 50
    # We can't create an attachment now..
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Can't send attachment
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://graph.microsoft.com/v1.0/users/{}/sendMail'.format(email)
    mock_post.reset_mock()

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # already authenticated
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://graph.microsoft.com/v1.0/users/{}/sendMail'.format(email)
    mock_post.reset_mock()
