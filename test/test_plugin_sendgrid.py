# -*- coding: utf-8 -*-
# BSD 2-Clause License
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

from apprise.plugins.NotifySendGrid import NotifySendGrid
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# a test UUID we can use
UUID4 = '8b799edf-6f98-4d3a-9be7-2862fb4e5752'

# Our Testing URLs
apprise_url_tests = (
    ('sendgrid://', {
        'instance': None,
    }),
    ('sendgrid://:@/', {
        'instance': None,
    }),
    ('sendgrid://abcd', {
        # Just an broken email (no api key or email)
        'instance': None,
    }),
    ('sendgrid://abcd@host', {
        # Just an Email specified, no API Key
        'instance': None,
    }),
    ('sendgrid://invalid-api-key+*-d:user@example.com', {
        # An invalid API Key
        'instance': TypeError,
    }),
    ('sendgrid://abcd:user@example.com', {
        # No To/Target Address(es) specified; so we sub in the same From
        # address
        'instance': NotifySendGrid,
    }),
    ('sendgrid://abcd:user@example.com/newuser@example.com', {
        # A good email
        'instance': NotifySendGrid,
    }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?bcc=l2g@nuxref.com', {
         # A good email with Blind Carbon Copy
         'instance': NotifySendGrid,
     }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?cc=l2g@nuxref.com', {
         # A good email with Carbon Copy
         'instance': NotifySendGrid,
     }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?to=l2g@nuxref.com', {
         # A good email with Carbon Copy
         'instance': NotifySendGrid,
     }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?template={}'.format(UUID4), {
         # A good email with a template + no substitutions
         'instance': NotifySendGrid,
     }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?template={}&+sub=value&+sub2=value2'.format(UUID4), {
         # A good email with a template + substitutions
         'instance': NotifySendGrid,

         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'sendgrid://a...d:user@example.com/',
     }),
    ('sendgrid://abcd:user@example.ca/newuser@example.ca', {
        'instance': NotifySendGrid,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('sendgrid://abcd:user@example.uk/newuser@example.uk', {
        'instance': NotifySendGrid,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('sendgrid://abcd:user@example.au/newuser@example.au', {
        'instance': NotifySendGrid,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_sendgrid_urls():
    """
    NotifySendGrid() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_sendgrid_edge_cases(mock_post, mock_get):
    """
    NotifySendGrid() Edge Cases

    """

    # no apikey
    with pytest.raises(TypeError):
        NotifySendGrid(
            apikey=None, from_email='user@example.com')

    # invalid from email
    with pytest.raises(TypeError):
        NotifySendGrid(
            apikey='abcd', from_email='!invalid')

    # no email
    with pytest.raises(TypeError):
        NotifySendGrid(apikey='abcd', from_email=None)

    # Invalid To email address
    NotifySendGrid(
        apikey='abcd', from_email='user@example.com', targets="!invalid")

    # Test invalid bcc/cc entries mixed with good ones
    assert isinstance(NotifySendGrid(
        apikey='abcd',
        from_email='l2g@example.com',
        bcc=('abc@def.com', '!invalid'),
        cc=('abc@test.org', '!invalid')), NotifySendGrid)
