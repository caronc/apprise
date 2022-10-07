# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
from unittest import mock

import pytest
import requests
from apprise import plugins
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
        'instance': plugins.NotifySendGrid,
    }),
    ('sendgrid://abcd:user@example.com/newuser@example.com', {
        # A good email
        'instance': plugins.NotifySendGrid,
    }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?bcc=l2g@nuxref.com', {
         # A good email with Blind Carbon Copy
         'instance': plugins.NotifySendGrid,
     }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?cc=l2g@nuxref.com', {
         # A good email with Carbon Copy
         'instance': plugins.NotifySendGrid,
     }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?to=l2g@nuxref.com', {
         # A good email with Carbon Copy
         'instance': plugins.NotifySendGrid,
     }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?template={}'.format(UUID4), {
         # A good email with a template + no substitutions
         'instance': plugins.NotifySendGrid,
     }),
    ('sendgrid://abcd:user@example.com/newuser@example.com'
     '?template={}&+sub=value&+sub2=value2'.format(UUID4), {
         # A good email with a template + substitutions
         'instance': plugins.NotifySendGrid,

         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'sendgrid://a...d:user@example.com/',
     }),
    ('sendgrid://abcd:user@example.ca/newuser@example.ca', {
        'instance': plugins.NotifySendGrid,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('sendgrid://abcd:user@example.uk/newuser@example.uk', {
        'instance': plugins.NotifySendGrid,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('sendgrid://abcd:user@example.au/newuser@example.au', {
        'instance': plugins.NotifySendGrid,
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
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # no apikey
    with pytest.raises(TypeError):
        plugins.NotifySendGrid(
            apikey=None, from_email='user@example.com')

    # invalid from email
    with pytest.raises(TypeError):
        plugins.NotifySendGrid(
            apikey='abcd', from_email='!invalid')

    # no email
    with pytest.raises(TypeError):
        plugins.NotifySendGrid(apikey='abcd', from_email=None)

    # Invalid To email address
    plugins.NotifySendGrid(
        apikey='abcd', from_email='user@example.com', targets="!invalid")

    # Test invalid bcc/cc entries mixed with good ones
    assert isinstance(plugins.NotifySendGrid(
        apikey='abcd',
        from_email='l2g@example.com',
        bcc=('abc@def.com', '!invalid'),
        cc=('abc@test.org', '!invalid')), plugins.NotifySendGrid)
