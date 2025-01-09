# -*- coding: utf-8 -*-
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
from unittest import mock
import pytest
import requests
from apprise.plugins.seven import NotifySeven
from helpers import AppriseURLTester
# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)
# Our Testing URLs
apprise_url_tests = (
    ('seven://', {
        # No hostname/apikey specified
        'instance': TypeError,
    }),
    ('seven://{}/15551232000'.format('a' * 25), {
        # target phone number becomes who we text too; all is good
        'instance': NotifySeven,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'seven://a...a/15551232000',
    }),
    ('seven://{}/15551232000'.format('a' * 25), {
        'instance': NotifySeven,
        # force a failure
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('seven://{}/15551232000'.format('a' * 25), {
        'instance': NotifySeven,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('seven://{}/15551232000'.format('a' * 25), {
        'instance': NotifySeven,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracefully handle them
        'test_requests_exceptions': True,
    }),
    ('seven://{}/?to=15551232000'.format('a' * 25), {
        # target phone number using to=
        'instance': NotifySeven,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'seven://a...a/15551232000',
    }),
    ('seven://{}/15551'.format('a' * 25), {
        # target phone number invalid
        'instance': NotifySeven,
        # Our call to notify() under the hood will fail
        'notify_response': False,
    }),
)


def test_plugin_seven_urls():
    """
    NotifyTemplate() Apprise URLs
    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_seven_edge_cases(mock_post):
    """
    NotifySeven() Edge Cases
    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok
    # Prepare Mock
    mock_post.return_value = response
    source = '+1 (555) 123-3456'
    # No apikey specified
    with pytest.raises(TypeError):
        NotifySeven(apikey=None, source=source)
