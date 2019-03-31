# -*- coding: utf-8 -*-
#
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

import six
import mock
import requests
from apprise import plugins
# from apprise import AppriseAsset
from json import dumps
from datetime import datetime

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_notify_gitter_plugin_general(mock_post, mock_get):
    """
    API: NotifyGitter() General Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.NotifyBase.request_rate_per_sec = 0

    # Generate a valid token (40 characters)
    token = 'a' * 40

    response_obj = [
        {
            'noindex': False,
            'oneToOne': False,
            'avatarUrl': 'https://path/to/avatar/url',
            'url': '/apprise-notifications/community',
            'public': True,
            'tags': [],
            'lurk': False,
            'uri': 'apprise-notifications/community',
            'lastAccessTime': '2019-03-25T00:12:28.144Z',
            'topic': '',
            'roomMember': True,
            'groupId': '5c981cecd73408ce4fbbad2f',
            'githubType': 'REPO_CHANNEL',
            'unreadItems': 0,
            'mentions': 0,
            'security': 'PUBLIC',
            'userCount': 1,
            'id': '5c981cecd73408ce4fbbad31',
            'name': 'apprise/community',
        },
    ]

    # Epoch time:
    epoch = datetime.utcfromtimestamp(0)

    request = mock.Mock()
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok
    request.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }

    # Prepare Mock
    mock_get.return_value = request
    mock_post.return_value = request

    # Variation Initializations (no token)
    try:
        obj = plugins.NotifyGitter(token=None, targets='apprise')
        # No Token should throw an exception
        assert False

    except TypeError:
        # We should get here
        assert True

    # Variation Initializations
    obj = plugins.NotifyGitter(token=token, targets='apprise')
    assert isinstance(obj, plugins.NotifyGitter) is True
    assert isinstance(obj.url(), six.string_types) is True

    # apprise room was found
    assert obj.send(body="test") is True

    # Change our status code and try again
    request.status_code = 403
    assert obj.send(body="test") is False
    assert obj.ratelimit_remaining == 1

    # Return the status
    request.status_code = requests.codes.ok
    # Force a reset
    request.headers['X-RateLimit-Remaining'] = 0
    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    request.headers['X-RateLimit-Remaining'] = 10
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Handle cases where we simply couldn't get this field
    del request.headers['X-RateLimit-Remaining']
    assert obj.send(body="test") is True
    # It remains set to the last value
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    request.headers['X-RateLimit-Remaining'] = 1

    # Handle cases where our epoch time is wrong
    del request.headers['X-RateLimit-Reset']
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers['X-RateLimit-Reset'] = \
        (datetime.utcnow() - epoch).total_seconds() + 1
    request.headers['X-RateLimit-Remaining'] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers['X-RateLimit-Reset'] = \
        (datetime.utcnow() - epoch).total_seconds() - 1
    request.headers['X-RateLimit-Remaining'] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our limits to always work
    request.headers['X-RateLimit-Reset'] = \
        (datetime.utcnow() - epoch).total_seconds()
    request.headers['X-RateLimit-Remaining'] = 1
    obj.ratelimit_remaining = 1

    # Cause content response to be None
    request.content = None
    assert obj.send(body="test") is True

    # Invalid JSON
    request.content = '{'
    assert obj.send(body="test") is True

    # Return it to a parseable string
    request.content = '{}'

    # Support the 'to' as a target
    results = plugins.NotifyGitter.parse_url(
        'gitter://{}?to={}'.format(token, 'apprise'))
    assert isinstance(results, dict) is True
    assert 'apprise' in results['targets']

    # cause a json parsing issue now
    response_obj = None
    assert obj.send(body="test") is True

    response_obj = '{'
    assert obj.send(body="test") is True

    # Variation Initializations
    obj = plugins.NotifyGitter(token=token, targets='missing')
    assert isinstance(obj, plugins.NotifyGitter) is True
    assert isinstance(obj.url(), six.string_types) is True
    # missing room was found
    assert obj.send(body="test") is False
