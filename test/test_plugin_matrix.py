# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

import requests
import pytest
from apprise import plugins
from apprise import AppriseAsset
from json import dumps
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyMatrix
    ##################################
    ('matrix://', {
        'instance': None,
    }),
    ('matrixs://', {
        'instance': None,
    }),
    ('matrix://localhost?mode=off', {
        # treats it as a anonymous user to register
        'instance': plugins.NotifyMatrix,
        # response is false because we have nothing to notify
        'response': False,
    }),
    ('matrix://localhost', {
        # response is TypeError because we'll try to initialize as
        # a t2bot and fail (localhost is too short of a api key)
        'instance': TypeError
    }),
    ('matrix://user:pass@localhost/#room1/#room2/#room3', {
        'instance': plugins.NotifyMatrix,
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('matrix://user:pass@localhost/#room1/#room2/!room1', {
        'instance': plugins.NotifyMatrix,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('matrix://user:pass@localhost:1234/#room', {
        'instance': plugins.NotifyMatrix,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'matrix://user:****@localhost:1234/',
    }),

    # Matrix supports webhooks too; the following tests this now:
    ('matrix://user:token@localhost?mode=matrix&format=text', {
        # user and token correctly specified with webhook
        'instance': plugins.NotifyMatrix,
        'response': False,
    }),
    ('matrix://user:token@localhost?mode=matrix&format=html', {
        # user and token correctly specified with webhook
        'instance': plugins.NotifyMatrix,
    }),
    ('matrix://user:token@localhost?mode=slack&format=text', {
        # user and token correctly specified with webhook
        'instance': plugins.NotifyMatrix,
    }),
    ('matrixs://user:token@localhost?mode=SLACK&format=markdown', {
        # user and token specified; slack webhook still detected
        # despite uppercase characters
        'instance': plugins.NotifyMatrix,
    }),
    ('matrix://user@localhost?mode=SLACK&format=markdown&token=mytoken', {
        # user and token specified; slack webhook still detected
        # despite uppercase characters; token also set on URL as arg
        'instance': plugins.NotifyMatrix,
    }),
    ('matrix://_?mode=t2bot&token={}'.format('b' * 64), {
        # Testing t2bot initialization and setting the password using the
        # token directive
        'instance': plugins.NotifyMatrix,
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'matrix://b...b/',
    }),
    # Image Reference
    ('matrixs://user:token@localhost?mode=slack&format=markdown&image=True', {
        # user and token specified; image set to True
        'instance': plugins.NotifyMatrix,
    }),
    ('matrixs://user:token@localhost?mode=slack&format=markdown&image=False', {
        # user and token specified; image set to True
        'instance': plugins.NotifyMatrix,
    }),
    # A Bunch of bad ports
    ('matrixs://user:pass@hostname:port/#room_alias', {
        # Invalid Port specified (was a string)
        'instance': TypeError,
    }),
    ('matrixs://user:pass@hostname:0/#room_alias', {
        # Invalid Port specified (was a string)
        'instance': TypeError,
    }),
    ('matrixs://user:pass@hostname:65536/#room_alias', {
        # Invalid Port specified (was a string)
        'instance': TypeError,
    }),
    # More general testing...
    ('matrixs://user@{}?mode=t2bot&format=markdown&image=True'
     .format('a' * 64), {
         # user and token specified; image set to True
         'instance': plugins.NotifyMatrix}),
    ('matrix://user@{}?mode=t2bot&format=html&image=False'
     .format('z' * 64), {
         # user and token specified; image set to True
         'instance': plugins.NotifyMatrix}),
    # This will default to t2bot because no targets were specified and no
    # password
    ('matrixs://{}'.format('c' * 64), {
        'instance': plugins.NotifyMatrix,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    # Test Native URL
    ('https://webhooks.t2bot.io/api/v1/matrix/hook/{}/'.format('d' * 64), {
        # user and token specified; image set to True
        'instance': plugins.NotifyMatrix,
    }),
    ('matrix://user:token@localhost?mode=On', {
        # invalid webhook specified (unexpected boolean)
        'instance': TypeError,
    }),
    ('matrix://token@localhost/?mode=Matrix', {
        'instance': plugins.NotifyMatrix,
        'response': False,
        'requests_response_code': requests.codes.internal_server_error,
    }),
    ('matrix://user:token@localhost/mode=matrix', {
        'instance': plugins.NotifyMatrix,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('matrix://token@localhost:8080/?mode=slack', {
        'instance': plugins.NotifyMatrix,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    ('matrix://{}/?mode=t2bot'.format('b' * 64), {
        'instance': plugins.NotifyMatrix,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_matrix_urls():
    """
    NotifyMatrix() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_matrix_general(mock_post, mock_get):
    """
    NotifyMatrix() General Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response_obj = {
        'room_id': '!abc123:localhost',
        'room_alias': '#abc123:localhost',
        'joined_rooms': ['!abc123:localhost', '!def456:localhost'],
        'access_token': 'abcd1234',
        'home_server': 'localhost',
    }
    request = mock.Mock()
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok

    # Prepare Mock
    mock_get.return_value = request
    mock_post.return_value = request

    # Variation Initializations
    obj = plugins.NotifyMatrix(host='host', targets='#abcd')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert isinstance(obj.url(), str) is True
    # Registration successful
    assert obj.send(body="test") is True

    obj = plugins.NotifyMatrix(host='host', user='user', targets='#abcd')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert isinstance(obj.url(), str) is True
    # Registration successful
    assert obj.send(body="test") is True

    obj = plugins.NotifyMatrix(host='host', password='passwd', targets='#abcd')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert isinstance(obj.url(), str) is True
    # A username gets automatically generated in these cases
    assert obj.send(body="test") is True

    obj = plugins.NotifyMatrix(
        host='host', user='user', password='passwd', targets='#abcd')
    assert isinstance(obj.url(), str) is True
    assert isinstance(obj, plugins.NotifyMatrix) is True
    # Registration Successful
    assert obj.send(body="test") is True

    # Test sending other format types
    kwargs = plugins.NotifyMatrix.parse_url(
        'matrix://user:passwd@hostname/#abcd?format=html')
    obj = plugins.NotifyMatrix(**kwargs)
    assert isinstance(obj.url(), str) is True
    assert isinstance(obj, plugins.NotifyMatrix) is True
    obj.send(body="test") is True
    obj.send(title="title", body="test") is True

    kwargs = plugins.NotifyMatrix.parse_url(
        'matrix://user:passwd@hostname/#abcd/#abcd:localhost?format=markdown')
    obj = plugins.NotifyMatrix(**kwargs)
    assert isinstance(obj.url(), str) is True
    assert isinstance(obj, plugins.NotifyMatrix) is True
    obj.send(body="test") is True
    obj.send(title="title", body="test") is True

    kwargs = plugins.NotifyMatrix.parse_url(
        'matrix://user:passwd@hostname/#abcd/!abcd:localhost?format=text')
    obj = plugins.NotifyMatrix(**kwargs)
    assert isinstance(obj.url(), str) is True
    assert isinstance(obj, plugins.NotifyMatrix) is True
    obj.send(body="test") is True
    obj.send(title="title", body="test") is True

    # Test notice type notifications
    kwargs = plugins.NotifyMatrix.parse_url(
        'matrix://user:passwd@hostname/#abcd?msgtype=notice')
    obj = plugins.NotifyMatrix(**kwargs)
    assert isinstance(obj.url(), str) is True
    assert isinstance(obj, plugins.NotifyMatrix) is True
    obj.send(body="test") is True
    obj.send(title="title", body="test") is True

    with pytest.raises(TypeError):
        # invalid message type specified
        kwargs = plugins.NotifyMatrix.parse_url(
            'matrix://user:passwd@hostname/#abcd?msgtype=invalid')
        obj = plugins.NotifyMatrix(**kwargs)

    # Force a failed login
    ro = response_obj.copy()
    del ro['access_token']
    request.content = dumps(ro)
    request.status_code = 404

    # Fails because we couldn't register because of 404 errors
    assert obj.send(body="test") is False

    obj = plugins.NotifyMatrix(host='host', user='test', targets='#abcd')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    # Fails because we still couldn't register
    assert obj.send(user='test', password='passwd', body="test") is False

    obj = plugins.NotifyMatrix(
        host='host', user='test', password='passwd', targets='#abcd')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    # Fails because we still couldn't register
    assert obj.send(body="test") is False

    obj = plugins.NotifyMatrix(host='host', password='passwd', targets='#abcd')
    # Fails because we still couldn't register
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.send(body="test") is False

    # Force a empty joined list response
    ro = response_obj.copy()
    ro['joined_rooms'] = []
    request.content = dumps(ro)
    assert obj.send(user='test', password='passwd', body="test") is False

    # Fall back to original template
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok

    # update our response object so logins now succeed
    response_obj['user_id'] = '@apprise:localhost'

    # Login was successful but not get a room_id
    ro = response_obj.copy()
    del ro['room_id']
    request.content = dumps(ro)
    assert obj.send(user='test', password='passwd', body="test") is False

    # Fall back to original template
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok

    obj = plugins.NotifyMatrix(host='host', targets=None)
    assert isinstance(obj, plugins.NotifyMatrix) is True

    # Force a empty joined list response
    ro = response_obj.copy()
    ro['joined_rooms'] = []
    request.content = dumps(ro)
    assert obj.send(user='test', password='passwd', body="test") is False

    # Fall back to original template
    request.content = dumps(response_obj)
    request.status_code = requests.codes.ok

    # our room list is empty so we'll have retrieved the joined_list
    # as our backup
    assert obj.send(user='test', password='passwd', body="test") is True


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_matrix_fetch(mock_post, mock_get):
    """
    NotifyMatrix() Server Fetch/API Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response_obj = {
        'room_id': '!abc123:localhost',
        'room_alias': '#abc123:localhost',
        'joined_rooms': ['!abc123:localhost', '!def456:localhost'],

        # Login details
        'access_token': 'abcd1234',
        'user_id': '@apprise:localhost',
        'home_server': 'localhost',
    }

    def fetch_failed(url, *args, **kwargs):

        # Default configuration
        request = mock.Mock()
        request.status_code = requests.codes.ok
        request.content = dumps(response_obj)

        if url.find('/rooms/') > -1:
            # over-ride on room query
            request.status_code = 403
            request.content = dumps({
                u'errcode': u'M_UNKNOWN',
                u'error': u'Internal server error',
            })

        return request

    mock_get.side_effect = fetch_failed
    mock_post.side_effect = fetch_failed

    obj = plugins.NotifyMatrix(
        host='host', user='user', password='passwd', include_image=True)
    assert isinstance(obj, plugins.NotifyMatrix) is True
    # We would hve failed to send our image notification
    assert obj.send(user='test', password='passwd', body="test") is False

    # Do the same query with no images to fetch
    asset = AppriseAsset(image_path_mask=False, image_url_mask=False)
    obj = plugins.NotifyMatrix(
        host='host', user='user', password='passwd', asset=asset)
    assert isinstance(obj, plugins.NotifyMatrix) is True
    # We would hve failed to send our notification
    assert obj.send(user='test', password='passwd', body="test") is False

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response_obj = {
        # Registration
        'access_token': 'abcd1234',
        'user_id': '@apprise:localhost',
        'home_server': 'localhost',

        # For room joining
        'room_id': '!abc123:localhost',
    }

    # Default configuration
    mock_get.side_effect = None
    mock_post.side_effect = None

    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    mock_post.return_value = request
    mock_get.return_value = request

    obj = plugins.NotifyMatrix(host='host', include_image=True)
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None
    assert obj._register() is True
    assert obj.access_token is not None

    # Cause retries
    request.status_code = 429
    request.content = dumps({
        'retry_after_ms': 1,
    })
    code, response = obj._fetch('/retry/apprise/unit/test')
    assert code is False

    request.content = dumps({
        'error': {
            'retry_after_ms': 1,
        }
    })
    code, response = obj._fetch('/retry/apprise/unit/test')
    assert code is False

    request.content = dumps({
        'error': {}
    })
    code, response = obj._fetch('/retry/apprise/unit/test')
    assert code is False


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_matrix_auth(mock_post, mock_get):
    """
    NotifyMatrix() Server Authentication

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response_obj = {
        # Registration
        'access_token': 'abcd1234',
        'user_id': '@apprise:localhost',
        'home_server': 'localhost',
    }

    # Default configuration
    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    mock_post.return_value = request
    mock_get.return_value = request

    obj = plugins.NotifyMatrix(host='localhost')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None
    # logging out without an access_token is silently a success
    assert obj._logout() is True
    assert obj.access_token is None

    assert obj._register() is True
    assert obj.access_token is not None

    # Logging in is silently treated as a success because we
    # already had success registering
    assert obj._login() is True
    assert obj.access_token is not None

    # However if we log out
    assert obj._logout() is True
    assert obj.access_token is None

    # And set ourselves up for failure
    request.status_code = 403
    assert obj._login() is False
    assert obj.access_token is None

    # Reset our token
    obj.access_token = None

    # Adjust our response to be invalid - missing access_token in response
    request.status_code = requests.codes.ok
    ro = response_obj.copy()
    del ro['access_token']
    request.content = dumps(ro)
    # Our registration will fail now
    assert obj._register() is False
    assert obj.access_token is None

    # So will login
    obj = plugins.NotifyMatrix(host='host', user='user', password='password')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj._login() is False
    assert obj.access_token is None

    # Adjust our response to be invalid - invalid json response
    request.content = "{"
    # Our registration will fail now
    assert obj._register() is False
    assert obj.access_token is None

    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    assert obj._register() is True
    assert obj.access_token is not None
    # Test logoff when getting a 403 error
    request.status_code = 403
    assert obj._logout() is False
    assert obj.access_token is not None

    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    assert obj._register() is True
    assert obj.access_token is not None
    request.status_code = 403
    request.content = dumps({
        u'errcode': u'M_UNKNOWN_TOKEN',
        u'error': u'Access Token unknown or expired',
    })
    # Test logoff when getting a 403 error; but if we have the right error
    # code in the response, then we return a True
    assert obj._logout() is True
    assert obj.access_token is None


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_matrix_rooms(mock_post, mock_get):
    """
    NotifyMatrix() Room Testing

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    response_obj = {
        # Registration
        'access_token': 'abcd1234',
        'user_id': '@apprise:localhost',
        'home_server': 'localhost',

        # For joined_room response
        'joined_rooms': ['!abc123:localhost', '!def456:localhost'],

        # For room joining
        'room_id': '!abc123:localhost',
    }

    # Default configuration
    request = mock.Mock()
    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    mock_post.return_value = request
    mock_get.return_value = request

    obj = plugins.NotifyMatrix(host='host')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None

    # Can't get room listing if we're not connnected
    assert obj._room_join('#abc123') is None

    assert obj._register() is True
    assert obj.access_token is not None

    assert obj._room_join('!abc123') == response_obj['room_id']
    # Use cache to get same results
    assert len(obj._room_cache) == 1
    assert obj._room_join('!abc123') == response_obj['room_id']

    obj._room_cache = {}
    assert obj._room_join('!abc123:localhost') == response_obj['room_id']
    # Use cache to get same results
    assert len(obj._room_cache) == 1
    assert obj._room_join('!abc123:localhost') == response_obj['room_id']

    obj._room_cache = {}
    assert obj._room_join('abc123') == response_obj['room_id']
    # Use cache to get same results
    assert len(obj._room_cache) == 1
    assert obj._room_join('abc123') == response_obj['room_id']

    obj._room_cache = {}
    assert obj._room_join('abc123:localhost') == response_obj['room_id']
    # Use cache to get same results
    assert len(obj._room_cache) == 1
    assert obj._room_join('abc123:localhost') == response_obj['room_id']

    obj._room_cache = {}
    assert obj._room_join('#abc123:localhost') == response_obj['room_id']
    # Use cache to get same results
    assert len(obj._room_cache) == 1
    assert obj._room_join('#abc123:localhost') == response_obj['room_id']

    obj._room_cache = {}
    assert obj._room_join('%') is None
    assert obj._room_join(None) is None

    # 403 response; this will push for a room creation for alias based rooms
    # and these will fail
    request.status_code = 403
    obj._room_cache = {}
    assert obj._room_join('!abc123') is None
    obj._room_cache = {}
    assert obj._room_join('!abc123:localhost') is None
    obj._room_cache = {}
    assert obj._room_join('abc123') is None
    obj._room_cache = {}
    assert obj._room_join('abc123:localhost') is None
    obj._room_cache = {}
    assert obj._room_join('#abc123:localhost') is None

    # Room creation
    request.status_code = requests.codes.ok
    obj = plugins.NotifyMatrix(host='host')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None

    # Can't get room listing if we're not connnected
    assert obj._room_create('#abc123') is None

    assert obj._register() is True
    assert obj.access_token is not None

    # You can't add room_id's, they must be aliases
    assert obj._room_create('!abc123') is None
    assert obj._room_create('!abc123:localhost') is None
    obj._room_cache = {}
    assert obj._room_create('abc123') == response_obj['room_id']
    obj._room_cache = {}
    assert obj._room_create('abc123:localhost') == response_obj['room_id']
    obj._room_cache = {}
    assert obj._room_create('#abc123:localhost') == response_obj['room_id']
    obj._room_cache = {}
    assert obj._room_create('%') is None
    assert obj._room_create(None) is None

    # 403 response; this will push for a room creation for alias based rooms
    # and these will fail
    request.status_code = 403
    obj._room_cache = {}
    assert obj._room_create('abc123') is None
    obj._room_cache = {}
    assert obj._room_create('abc123:localhost') is None
    obj._room_cache = {}
    assert obj._room_create('#abc123:localhost') is None

    request.status_code = 403
    request.content = dumps({
        u'errcode': u'M_ROOM_IN_USE',
        u'error': u'Room alias already taken',
    })
    obj._room_cache = {}
    # This causes us to look up a channel ID if we get a ROOM_IN_USE response
    assert obj._room_create('#abc123:localhost') is None

    # Room detection
    request.status_code = requests.codes.ok
    request.content = dumps(response_obj)
    obj = plugins.NotifyMatrix(host='localhost')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None

    # No rooms if we're not connected
    response = obj._joined_rooms()
    assert isinstance(response, list) is True
    assert len(response) == 0

    # register our account
    assert obj._register() is True
    assert obj.access_token is not None

    response = obj._joined_rooms()
    assert isinstance(response, list) is True
    assert len(response) == len(response_obj['joined_rooms'])
    for r in response:
        assert r in response_obj['joined_rooms']

    request.status_code = 403
    response = obj._joined_rooms()
    assert isinstance(response, list) is True
    assert len(response) == 0

    # Room id lookup
    request.status_code = requests.codes.ok
    obj = plugins.NotifyMatrix(host='localhost')
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None

    # Can't get room listing if we're not connnected
    assert obj._room_id('#abc123') is None

    assert obj._register() is True
    assert obj.access_token is not None

    # You can't add room_id's, they must be aliases
    assert obj._room_id('!abc123') is None
    assert obj._room_id('!abc123:localhost') is None
    obj._room_cache = {}
    assert obj._room_id('abc123') == response_obj['room_id']
    obj._room_cache = {}
    assert obj._room_id('abc123:localhost') == response_obj['room_id']
    obj._room_cache = {}
    assert obj._room_id('#abc123:localhost') == response_obj['room_id']
    obj._room_cache = {}
    assert obj._room_id('%') is None
    assert obj._room_id(None) is None

    # If we can't look the code up, we return None
    request.status_code = 403
    obj._room_cache = {}
    assert obj._room_id('#abc123:localhost') is None


def test_plugin_matrix_url_parsing():
    """
    NotifyMatrix() URL Testing

    """
    result = plugins.NotifyMatrix.parse_url(
        'matrix://user:token@localhost?to=#room')
    assert isinstance(result, dict) is True
    assert len(result['targets']) == 1
    assert '#room' in result['targets']

    result = plugins.NotifyMatrix.parse_url(
        'matrix://user:token@localhost?to=#room1,#room2,#room3')
    assert isinstance(result, dict) is True
    assert len(result['targets']) == 3
    assert '#room1' in result['targets']
    assert '#room2' in result['targets']
    assert '#room3' in result['targets']


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_matrix_image_errors(mock_post, mock_get):
    """
    NotifyMatrix() Image Error Handling

    """

    def mock_function_handing(url, data, **kwargs):
        """
        dummy function for handling image posts (as a failure)
        """
        response_obj = {
            'room_id': '!abc123:localhost',
            'room_alias': '#abc123:localhost',
            'joined_rooms': ['!abc123:localhost', '!def456:localhost'],
            'access_token': 'abcd1234',
            'home_server': 'localhost',
        }

        request = mock.Mock()
        request.content = dumps(response_obj)
        request.status_code = requests.codes.ok

        if 'm.image' in data:
            # Fail for images
            request.status_code = 400

        return request

    # Prepare Mock
    mock_get.side_effect = mock_function_handing
    mock_post.side_effect = mock_function_handing

    obj = plugins.NotifyMatrix(host='host', include_image=True)
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None

    # Notification was successful, however we could not post image and since
    # we had post errors (of any kind) we still report a failure.
    assert obj.notify('test', 'test') is False

    obj = plugins.NotifyMatrix(host='host', include_image=False)
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None

    # We didn't post an image (which was set to fail) and therefore our
    # post was okay
    assert obj.notify('test', 'test') is True

    def mock_function_handing(url, data, **kwargs):
        """
        dummy function for handling image posts (successfully)
        """
        response_obj = {
            'room_id': '!abc123:localhost',
            'room_alias': '#abc123:localhost',
            'joined_rooms': ['!abc123:localhost', '!def456:localhost'],
            'access_token': 'abcd1234',
            'home_server': 'localhost',
        }

        request = mock.Mock()
        request.content = dumps(response_obj)
        request.status_code = requests.codes.ok

        return request

    # Prepare Mock
    mock_get.side_effect = mock_function_handing
    mock_post.side_effect = mock_function_handing
    obj = plugins.NotifyMatrix(host='host', include_image=True)
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None

    assert obj.notify('test', 'test') is True

    obj = plugins.NotifyMatrix(host='host', include_image=False)
    assert isinstance(obj, plugins.NotifyMatrix) is True
    assert obj.access_token is None

    assert obj.notify('test', 'test') is True
