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

from json import dumps
from unittest import mock

import os
import pytest
import requests

from apprise import Apprise
from apprise import NotifyType
from apprise import AppriseAttachment
from apprise.plugins.sendpulse import NotifySendPulse
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

SENDPULSE_GOOD_RESPONSE = dumps({
    "access_token": 'abc123'
})

SENDPULSE_BAD_RESPONSE = '{'

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ('sendpulse://', {
        'instance': None,
    }),
    ('sendpulse://:@/', {
        'instance': None,
    }),
    ('sendpulse://abcd', {
        # invalid from email
        'instance': TypeError,
    }),
    ('sendpulse://abcd@host.com', {
        # Just an Email specified, no client_id or client_secret
        'instance': TypeError,
    }),
    ('sendpulse://user@example.com/client_id/cs1/', {
        'instance': NotifySendPulse,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,
    }),
    ('sendpulse://user@example.com/client_id/cs1a/', {
        'instance': NotifySendPulse,
        'requests_response_text': SENDPULSE_BAD_RESPONSE,
        # Notify will fail because auth failed
        'response': False,
    }),
    ('sendpulse://user@example.com/client_id/cs2/'
     '?bcc=l2g@nuxref.com', {
         # A good email with Blind Carbon Copy
         'instance': NotifySendPulse,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,
     }),
    ('sendpulse://user@example.com/client_id/cs3/'
     '?cc=l2g@nuxref.com', {
         # A good email with Carbon Copy
         'instance': NotifySendPulse,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,
     }),
    ('sendpulse://user@example.com/client_id/cs4/'
     '?to=l2g@nuxref.com', {
         # A good email with Carbon Copy
         'instance': NotifySendPulse,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,
     }),
    ('sendpulse://user@example.com/client_id/cs5/'
     '?template=1234', {
         # A good email with a template + no substitutions
         'instance': NotifySendPulse,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,
     }),
    ('sendpulse://user@example.com/client_id/cs6/'
     '?template=1234&+sub=value&+sub2=value2', {
         # A good email with a template + substitutions
         'instance': NotifySendPulse,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,

         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'sendpulse://user@example.com/c...d/c...6/',
     }),
    ('sendpulse://user@example.com/client_id/cs7/', {
        'instance': NotifySendPulse,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,
    }),
    ('sendpulse://user@example.com/client_id/cs8/', {
        'instance': NotifySendPulse,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,
    }),
    ('sendpulse://user@example.com/client_id/cs9/', {
        'instance': NotifySendPulse,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
        'requests_response_text': SENDPULSE_GOOD_RESPONSE,
    }),
)


def test_plugin_sendpulse_urls():
    """
    NotifySendPulse() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_sendpulse_edge_cases(mock_post, mock_get):
    """
    NotifySendPulse() Edge Cases

    """

    # no client_id
    with pytest.raises(TypeError):
        NotifySendPulse(
            client_id='abcd', client_secret=None,
            from_email='user@example.com')

    with pytest.raises(TypeError):
        NotifySendPulse(
            client_id=None, client_secret='abcd123',
            from_email='user@example.com')

    # invalid from email
    with pytest.raises(TypeError):
        NotifySendPulse(
            client_id='abcd', client_secret='abcd456', from_email='!invalid')

    # no email
    with pytest.raises(TypeError):
        NotifySendPulse(
            client_id='abcd', client_secret='abcd789', from_email=None)

    # Invalid To email address
    NotifySendPulse(
        client_id='abcd', client_secret='abcd321',
        from_email='user@example.com', targets="!invalid")

    # Test invalid bcc/cc entries mixed with good ones
    assert isinstance(NotifySendPulse(
        client_id='abcd', client_secret='abcd654',
        from_email='l2g@example.com',
        bcc=('abc@def.com', '!invalid'),
        cc=('abc@test.org', '!invalid')), NotifySendPulse)


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_sendpulse_attachments(mock_post, mock_get):
    """
    NotifySendPulse() Attachments

    """

    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = SENDPULSE_GOOD_RESPONSE

    # Prepare Mock
    mock_post.return_value = request
    mock_get.return_value = request

    path = os.path.join(TEST_VAR_DIR, 'apprise-test.gif')
    attach = AppriseAttachment(path)
    obj = Apprise.instantiate('sendpulse://user@example.com/aaaa/bbbb')
    assert isinstance(obj, NotifySendPulse)
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    mock_post.reset_mock()
    mock_get.reset_mock()

    # Try again in a use case where we can't access the file
    with mock.patch("os.path.isfile", return_value=False):
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False

    # Try again in a use case where we can't access the file
    with mock.patch("builtins.open", side_effect=OSError):
        assert obj.notify(
            body='body', title='title', notify_type=NotifyType.INFO,
            attach=attach) is False
