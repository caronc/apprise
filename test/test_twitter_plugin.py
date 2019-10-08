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

import six
import mock
import pytest
import requests
from json import dumps
from datetime import datetime
from apprise import plugins

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_twitter_plugin_init():
    """
    API: NotifyTwitter Plugin() (pt2)

    """

    with pytest.raises(TypeError):
        plugins.NotifyTwitter(
            ckey=None, csecret=None, akey=None, asecret=None)

    with pytest.raises(TypeError):
        plugins.NotifyTwitter(
            ckey='value', csecret=None, akey=None, asecret=None)

    with pytest.raises(TypeError):
        plugins.NotifyTwitter(
            ckey='value', csecret='value', akey=None, asecret=None)

    with pytest.raises(TypeError):
        plugins.NotifyTwitter(
            ckey='value', csecret='value', akey='value', asecret=None)

    assert isinstance(
        plugins.NotifyTwitter(
            ckey='value', csecret='value', akey='value', asecret='value'),
        plugins.NotifyTwitter,
    )

    assert isinstance(
        plugins.NotifyTwitter(
            ckey='value', csecret='value', akey='value', asecret='value',
            user='l2gnux'),
        plugins.NotifyTwitter,
    )

    # Invalid Target User
    with pytest.raises(TypeError):
        plugins.NotifyTwitter(
            ckey='value', csecret='value', akey='value', asecret='value',
            targets='%G@rB@g3')


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_notify_twitter_plugin_general(mock_post, mock_get):
    """
    API: NotifyTwitter() General Tests

    """
    ckey = 'ckey'
    csecret = 'csecret'
    akey = 'akey'
    asecret = 'asecret'
    screen_name = 'apprise'

    response_obj = [{
        'screen_name': screen_name,
        'id': 9876,
    }]

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Epoch time:
    epoch = datetime.utcfromtimestamp(0)

    request = mock.Mock()
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok
    request.headers = {
        'x-rate-limit-reset': (datetime.utcnow() - epoch).total_seconds(),
        'x-rate-limit-remaining': 1,
    }

    # Prepare Mock
    mock_get.return_value = request
    mock_post.return_value = request

    # Variation Initializations
    obj = plugins.NotifyTwitter(
        ckey=ckey,
        csecret=csecret,
        akey=akey,
        asecret=asecret,
        targets=screen_name)

    assert isinstance(obj, plugins.NotifyTwitter) is True
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
    request.headers['x-rate-limit-remaining'] = 0
    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    request.headers['x-rate-limit-remaining'] = 10
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Handle cases where we simply couldn't get this field
    del request.headers['x-rate-limit-remaining']
    assert obj.send(body="test") is True
    # It remains set to the last value
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    request.headers['x-rate-limit-remaining'] = 1

    # Handle cases where our epoch time is wrong
    del request.headers['x-rate-limit-reset']
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers['x-rate-limit-reset'] = \
        (datetime.utcnow() - epoch).total_seconds() + 1
    request.headers['x-rate-limit-remaining'] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    request.headers['x-rate-limit-reset'] = \
        (datetime.utcnow() - epoch).total_seconds() - 1
    request.headers['x-rate-limit-remaining'] = 0
    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our limits to always work
    request.headers['x-rate-limit-reset'] = \
        (datetime.utcnow() - epoch).total_seconds()
    request.headers['x-rate-limit-remaining'] = 1
    obj.ratelimit_remaining = 1

    # Alter pending targets
    obj.targets.append('usera')
    request.content = dumps(response_obj)
    response_obj = [{
        'screen_name': 'usera',
        'id': 1234,
    }]

    assert obj.send(body="test") is True

    # Flush our cache forcing it's re-creating
    del plugins.NotifyTwitter._user_cache
    assert obj.send(body="test") is True

    # Cause content response to be None
    request.content = None
    assert obj.send(body="test") is True

    # Invalid JSON
    request.content = '{'
    assert obj.send(body="test") is True

    # Return it to a parseable string
    request.content = '{}'

    results = plugins.NotifyTwitter.parse_url(
        'twitter://{}/{}/{}/{}?to={}'.format(
            ckey, csecret, akey, asecret, screen_name))
    assert isinstance(results, dict) is True
    assert screen_name in results['targets']

    # cause a json parsing issue now
    response_obj = None
    assert obj.send(body="test") is True

    response_obj = '{'
    assert obj.send(body="test") is True

    # Set ourselves up to handle whoami calls

    # Flush out our cache
    del plugins.NotifyTwitter._user_cache

    response_obj = {
        'screen_name': screen_name,
        'id': 9876,
    }
    request.content = dumps(response_obj)

    obj = plugins.NotifyTwitter(
        ckey=ckey,
        csecret=csecret,
        akey=akey,
        asecret=asecret)

    assert obj.send(body="test") is True

    # Alter the key forcing us to look up a new value of ourselves again
    del plugins.NotifyTwitter._user_cache
    del plugins.NotifyTwitter._whoami_cache
    obj.ckey = 'different.then.it.was'
    assert obj.send(body="test") is True

    del plugins.NotifyTwitter._whoami_cache
    obj.ckey = 'different.again'
    assert obj.send(body="test") is True
