# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.
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
