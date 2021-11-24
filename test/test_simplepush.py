# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
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
import sys
import mock
import pytest
import requests
import json
from apprise import Apprise
from apprise import plugins
from helpers import ModuleManipulation, RestFrameworkTester

# Our Testing URLs
apprise_url_tests = (
    ('spush://', {
        # No api key
        'instance': TypeError,
    }),
    ('spush://{}'.format('A' * 14), {
        # API Key specified however expected server response
        # didn't have 'OK' in JSON response
        'instance': plugins.NotifySimplePush,
        # Expected notify() response
        'notify_response': False,
    }),
    ('spush://{}'.format('Y' * 14), {
        # API Key valid and expected response was valid
        'instance': plugins.NotifySimplePush,
        # Set our response to OK
        'requests_response_text': {
            'status': 'OK',
        },

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'spush://Y...Y/',
    }),
    ('spush://{}?event=Not%20So%20Good'.format('X' * 14), {
        # API Key valid and expected response was valid
        'instance': plugins.NotifySimplePush,
        # Set our response to something that is not okay
        'requests_response_text': {
            'status': 'NOT-OK',
        },
        # Expected notify() response
        'notify_response': False,
    }),
    ('spush://salt:pass@{}'.format('X' * 14), {
        # Now we'll test encrypted messages with new salt
        'instance': plugins.NotifySimplePush,
        # Set our response to OK
        'requests_response_text': {
            'status': 'OK',
        },

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'spush://****:****@X...X/',
    }),
    ('spush://{}'.format('Y' * 14), {
        'instance': plugins.NotifySimplePush,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
        # Set a failing message too
        'requests_response_text': {
            'status': 'BadRequest',
            'message': 'Title or message too long',
        },
    }),
    ('spush://{}'.format('Z' * 14), {
        'instance': plugins.NotifySimplePush,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="requires cryptography")
@mock.patch('requests.post')
def test_simple_push_plugin(mock_post):
    """
    API: NotifySimplePush() General Checks

    """

    # Run our general tests
    RestFrameworkTester(tests=apprise_url_tests).run_all()


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="requires cryptography")
@mock.patch('requests.post')
def test_simple_push_cryptography_dependency(mock_post):
    """
    NotifySimplePush() Cryptography loading failure
    """

    with ModuleManipulation(
            "cryptography",
            base=r"^(apprise|apprise.plugins(\.NotifySimplePush(\..*)?)?)$"):

        # Disable Throttling to speed testing
        plugins.NotifyBase.request_rate_per_sec = 0

        # Prepare a good response
        response = mock.Mock()
        response.content = \
            json.dumps({'requests_response_text': {'status': 'OK'}})
        response.status_code = requests.codes.ok
        mock_post.return_value = response

        # Attempt to instantiate our object
        obj = Apprise.instantiate('spush://{}'.format('Y' * 14))

        # It's not possible because our cryptography depedancy is missing
        assert obj is None

    # Verify we restored everything okay
    obj = Apprise.instantiate('spush://{}'.format('Y' * 14))
    assert obj is not None


@pytest.mark.skipif(
    'cryptography' not in sys.modules, reason="requires cryptography")
def test_notify_simplepush_plugin():
    """
    NotifySimplePush() Edge Case Testing

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # No token
    with pytest.raises(TypeError):
        plugins.NotifySimplePush(apikey=None)

    with pytest.raises(TypeError):
        plugins.NotifySimplePush(apikey="  ")

    # Bad event
    with pytest.raises(TypeError):
        plugins.NotifySimplePush(apikey="abc", event=object)

    with pytest.raises(TypeError):
        plugins.NotifySimplePush(apikey="abc", event="  ")
