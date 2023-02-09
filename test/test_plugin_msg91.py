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

from apprise.plugins.NotifyMSG91 import NotifyMSG91
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('msg91://', {
        # No hostname/authkey specified
        'instance': TypeError,
    }),
    ('msg91://-', {
        # Invalid AuthKey
        'instance': TypeError,
    }),
    ('msg91://{}'.format('a' * 23), {
        # valid AuthKey
        'instance': NotifyMSG91,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msg91://{}/123'.format('a' * 23), {
        # invalid phone number
        'instance': NotifyMSG91,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msg91://{}/abcd'.format('a' * 23), {
        # No number to notify
        'instance': NotifyMSG91,
        # Since there are no targets specified we expect a False return on
        # send()
        'notify_response': False,
    }),
    ('msg91://{}/15551232000/?country=invalid'.format('a' * 23), {
        # invalid country
        'instance': TypeError,
    }),
    ('msg91://{}/15551232000/?country=99'.format('a' * 23), {
        # invalid country
        'instance': TypeError,
    }),
    ('msg91://{}/15551232000/?route=invalid'.format('a' * 23), {
        # invalid route
        'instance': TypeError,
    }),
    ('msg91://{}/15551232000/?route=99'.format('a' * 23), {
        # invalid route
        'instance': TypeError,
    }),
    ('msg91://{}/15551232000'.format('a' * 23), {
        # a valid message
        'instance': NotifyMSG91,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'msg91://a...a/15551232000',
    }),
    ('msg91://{}/?to=15551232000'.format('a' * 23), {
        # a valid message
        'instance': NotifyMSG91,
    }),
    ('msg91://{}/15551232000?country=91&route=1'.format('a' * 23), {
        # using phone no with no target - we text ourselves in
        # this case
        'instance': NotifyMSG91,
    }),
    ('msg91://{}/15551232000'.format('a' * 23), {
        # use get args to acomplish the same thing
        'instance': NotifyMSG91,
    }),
    ('msg91://{}/15551232000'.format('a' * 23), {
        'instance': NotifyMSG91,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('msg91://{}/15551232000'.format('a' * 23), {
        'instance': NotifyMSG91,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_msg91_urls():
    """
    NotifyMSG91() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_msg91_edge_cases(mock_post):
    """
    NotifyMSG91() Edge Cases

    """

    # Prepare our response
    response = requests.Request()
    response.status_code = requests.codes.ok

    # Prepare Mock
    mock_post.return_value = response

    # Initialize some generic (but valid) tokens
    # authkey = '{}'.format('a' * 24)
    target = '+1 (555) 123-3456'

    # No authkey specified
    with pytest.raises(TypeError):
        NotifyMSG91(authkey=None, targets=target)
    with pytest.raises(TypeError):
        NotifyMSG91(authkey="    ", targets=target)
