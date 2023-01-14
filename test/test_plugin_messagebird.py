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

from apprise.plugins.NotifyMessageBird import NotifyMessageBird
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('msgbird://', {
        # No hostname/apikey specified
        'instance': TypeError,
    }),
    ('msgbird://{}/abcd'.format('a' * 25), {
        # invalid characters in source phone number
        'instance': TypeError,
    }),
    ('msgbird://{}/123'.format('a' * 25), {
        # invalid source phone number
        'instance': TypeError,
    }),
    ('msgbird://{}/15551232000'.format('a' * 25), {
        # target phone number becomes who we text too; all is good
        'instance': NotifyMessageBird,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'msgbird://a...a/15551232000',
    }),
    ('msgbird://{}/15551232000/abcd'.format('a' * 25), {
        # valid credentials
        'instance': NotifyMessageBird,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msgbird://{}/15551232000/123'.format('a' * 25), {
        # valid credentials
        'instance': NotifyMessageBird,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msgbird://{}/?from=15551233000&to=15551232000'.format('a' * 25), {
        # reference to to= and from=
        'instance': NotifyMessageBird,
    }),
    ('msgbird://{}/15551232000'.format('a' * 25), {
        'instance': NotifyMessageBird,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('msgbird://{}/15551232000'.format('a' * 25), {
        'instance': NotifyMessageBird,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('msgbird://{}/15551232000'.format('a' * 25), {
        'instance': NotifyMessageBird,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_messagebird_urls():
    """
    NotifyTemplate() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_messagebird_edge_cases(mock_post):
    """
    NotifyMessageBird() Edge Cases

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    # authkey = '{}'.format('a' * 24)
    source = '+1 (555) 123-3456'

    # No apikey specified
    with pytest.raises(TypeError):
        NotifyMessageBird(apikey=None, source=source)
    with pytest.raises(TypeError):
        NotifyMessageBird(apikey="     ", source=source)
