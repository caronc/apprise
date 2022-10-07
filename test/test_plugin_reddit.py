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

import requests
from apprise import plugins
from helpers import AppriseURLTester
from unittest import mock

from json import dumps
from datetime import datetime
from datetime import timedelta

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    ('reddit://', {
        # Missing all credentials
        'instance': TypeError,
    }),
    ('reddit://:@/', {
        'instance': TypeError,
    }),
    ('reddit://user@app_id/app_secret/', {
        # No password
        'instance': TypeError,
    }),
    ('reddit://user:password@app_id/', {
        # No app secret
        'instance': TypeError,
    }),
    ('reddit://user:password@app%id/appsecret/apprise', {
        # No invalid app_id (has percent)
        'instance': TypeError,
    }),
    ('reddit://user:password@app%id/app_secret/apprise', {
        # No invalid app_secret (has percent)
        'instance': TypeError,
    }),
    ('reddit://user:password@app-id/app-secret/apprise?kind=invalid', {
        # An Invalid Kind
        'instance': TypeError,
    }),
    ('reddit://user:password@app-id/app-secret/apprise', {
        # Login failed
        'instance': plugins.NotifyReddit,
        # Expected notify() response is False because internally we would
        # have failed to login
        'notify_response': False,
    }),
    ('reddit://user:password@app-id/app-secret', {
        # Login successful, but there was no subreddit to notify
        'instance': plugins.NotifyReddit,
        'requests_response_text': {
            "access_token": 'abc123',
            "token_type": "bearer",
            "expires_in": 100000,
            "scope": '*',
            "refresh_token": 'def456',
            # The below is used in the response:
            "json": {
                # No errors during post
                "errors": [],
            },
        },
        # Expected notify() response is False
        'notify_response': False,
    }),
    ('reddit://user:password@app-id/app-secret/apprise', {
        'instance': plugins.NotifyReddit,
        'requests_response_text': {
            "access_token": 'abc123',
            "token_type": "bearer",
            "expires_in": 100000,
            "scope": '*',
            "refresh_token": 'def456',
            # The below is used in the response:
            "json": {
                # Identify an error
                "errors": [('KEY', 'DESC', 'INFO'), ],
            },
        },
        # Expected notify() response is False because the
        # reddit server provided us errors
        'notify_response': False,
    }),

    ('reddit://user:password@app-id/app-secret/apprise', {
        'instance': plugins.NotifyReddit,
        'requests_response_text': {
            "access_token": 'abc123',
            "token_type": "bearer",
            # Test case where 'expires_in' entry is missing
            "scope": '*',
            "refresh_token": 'def456',
            # The below is used in the response:
            "json": {
                # No errors during post
                "errors": [],
            },
        },
        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'reddit://user:****@****/****/apprise',
    }),
    ('reddit://user:password@app-id/app-secret/apprise/subreddit2', {
        # password:login acceptable
        'instance': plugins.NotifyReddit,
        'requests_response_text': {
            "access_token": 'abc123',
            "token_type": "bearer",
            "expires_in": 100000,
            "scope": '*',
            "refresh_token": 'def456',
            # The below is used in the response:
            "json": {
                # No errors during post
                "errors": [],
            },
        },
        # Our expected url(privacy=True) startswith() response:
        'privacy_url':
            'reddit://user:****@****/****/apprise/subreddit2',
    }),
    # Pass in some arguments to over-ride defaults
    ('reddit://user:pass@id/secret/sub/'
     '?ad=yes&nsfw=yes&replies=no&resubmit=yes&spoiler=yes&kind=self', {
         'instance': plugins.NotifyReddit,
         'requests_response_text': {
             "access_token": 'abc123',
             "token_type": "bearer",
             "expires_in": 100000,
             "scope": '*',
             "refresh_token": 'def456',
             # The below is used in the response:
             "json": {
                 # No errors during post
                 "errors": [],
             },
         },
         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'reddit://user:****@****/****/sub'}),
    # Pass in more arguments
    ('reddit://'
     '?user=l2g&pass=pass&app_secret=abc123&app_id=54321&to=sub1,sub2', {
         'instance': plugins.NotifyReddit,
         'requests_response_text': {
             "access_token": 'abc123',
             "token_type": "bearer",
             "expires_in": 100000,
             "scope": '*',
             "refresh_token": 'def456',
             # The below is used in the response:
             "json": {
                 # No errors during post
                 "errors": [],
             },
         },
         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'reddit://l2g:****@****/****/sub1/sub2'}),
    # More arguments ...
    ('reddit://user:pass@id/secret/sub7/sub6/sub5/'
     '?flair_id=wonder&flair_text=not%20for%20you', {
         'instance': plugins.NotifyReddit,
         'requests_response_text': {
             "access_token": 'abc123',
             "token_type": "bearer",
             "expires_in": 100000,
             "scope": '*',
             "refresh_token": 'def456',
             # The below is used in the response:
             "json": {
                 # No errors during post
                 "errors": [],
             },
         },
         # Our expected url(privacy=True) startswith() response:
         'privacy_url': 'reddit://user:****@****/****/sub'}),
    ('reddit://user:password@app-id/app-secret/apprise', {
        'instance': plugins.NotifyReddit,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('reddit://user:password@app-id/app-secret/apprise', {
        'instance': plugins.NotifyReddit,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_reddit_urls():
    """
    NotifyReddit() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.post')
def test_plugin_reddit_general(mock_post):
    """
    NotifyReddit() General Tests

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0
    plugins.NotifyReddit.clock_skew = timedelta(seconds=0)

    # Generate a valid credentials:
    kwargs = {
        'app_id': 'a' * 10,
        'app_secret': 'b' * 20,
        'user': 'user',
        'password': 'pasword',
        'targets': 'apprise',
    }

    # Epoch time:
    epoch = datetime.utcfromtimestamp(0)

    good_response = mock.Mock()
    good_response.content = dumps({
        "access_token": 'abc123',
        "token_type": "bearer",
        "expires_in": 100000,
        "scope": '*',
        "refresh_token": 'def456',
        # The below is used in the response:
        "json": {
            # No errors during post
            "errors": [],
        },
    })
    good_response.status_code = requests.codes.ok
    good_response.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }

    # Prepare Mock
    mock_post.return_value = good_response

    # Variation Initializations
    obj = plugins.NotifyReddit(**kwargs)
    assert isinstance(obj, plugins.NotifyReddit) is True
    assert isinstance(obj.url(), str) is True

    # Dynamically pick up on a link
    assert obj.send(body="http://hostname") is True

    bad_response = mock.Mock()
    bad_response.content = ''
    bad_response.status_code = 401

    # Change our status code and try again
    mock_post.return_value = bad_response
    assert obj.send(body="test") is False
    assert obj.ratelimit_remaining == 1

    # Return the status
    mock_post.return_value = good_response

    # Force a case where there are no more remaining posts allowed
    good_response.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds(),
        'X-RateLimit-Remaining': 0,
    }
    # behind the scenes, it should cause us to update our rate limit
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 0

    # This should cause us to block
    good_response.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds(),
        'X-RateLimit-Remaining': 10,
    }
    assert obj.send(body="test") is True
    assert obj.ratelimit_remaining == 10

    # Handle cases where we simply couldn't get this field
    del good_response.headers['X-RateLimit-Remaining']
    assert obj.send(body="test") is True
    # It remains set to the last value
    assert obj.ratelimit_remaining == 10

    # Reset our variable back to 1
    good_response.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }
    # Handle cases where our epoch time is wrong
    del good_response.headers['X-RateLimit-Reset']
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    good_response.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds() + 1,
        'X-RateLimit-Remaining': 0,
    }

    obj.ratelimit_remaining = 0
    assert obj.send(body="test") is True

    # Return our object, but place it in the future forcing us to block
    good_response.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds() - 1,
        'X-RateLimit-Remaining': 0,
    }
    assert obj.send(body="test") is True

    # Return our limits to always work
    obj.ratelimit_remaining = 1

    # Invalid JSON
    response = mock.Mock()
    response.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }
    response.content = '{'
    response.status_code = requests.codes.ok
    mock_post.return_value = response
    obj = plugins.NotifyReddit(**kwargs)
    assert obj.send(body="test") is False

    # Return it to a parseable string but missing the entries we expect
    response.content = '{}'
    obj = plugins.NotifyReddit(**kwargs)
    assert obj.send(body="test") is False

    # No access token provided
    response.content = dumps({
        "access_token": '',
        "json": {
            # No errors during post
            "errors": [],
        },
    })
    obj = plugins.NotifyReddit(**kwargs)
    assert obj.send(body="test") is False

    # cause a json parsing issue now
    response.content = None
    obj = plugins.NotifyReddit(**kwargs)
    assert obj.send(body="test") is False

    # Reset to what we consider a good response
    good_response.content = dumps({
        "access_token": 'abc123',
        "token_type": "bearer",
        "expires_in": 100000,
        "scope": '*',
        "refresh_token": 'def456',
        # The below is used in the response:
        "json": {
            # No errors during post
            "errors": [],
        },
    })
    good_response.status_code = requests.codes.ok
    good_response.headers = {
        'X-RateLimit-Reset': (datetime.utcnow() - epoch).total_seconds(),
        'X-RateLimit-Remaining': 1,
    }

    # Reset our mock object
    mock_post.reset_mock()

    # Test sucessful re-authentication after failed post
    mock_post.side_effect = [
        good_response, bad_response, good_response, good_response]
    obj = plugins.NotifyReddit(**kwargs)
    assert obj.send(body="test") is True
    assert mock_post.call_count == 4
    assert mock_post.call_args_list[0][0][0] == \
        'https://www.reddit.com/api/v1/access_token'
    assert mock_post.call_args_list[1][0][0] == \
        'https://oauth.reddit.com/api/submit'
    assert mock_post.call_args_list[2][0][0] == \
        'https://www.reddit.com/api/v1/access_token'
    assert mock_post.call_args_list[3][0][0] == \
        'https://oauth.reddit.com/api/submit'

    # Test failed re-authentication
    mock_post.side_effect = [
        good_response, bad_response, bad_response]
    obj = plugins.NotifyReddit(**kwargs)
    assert obj.send(body="test") is False

    # Test exception handing on re-auth attempt
    response.content = '{'
    response.status_code = requests.codes.ok
    mock_post.side_effect = [
        good_response, bad_response, good_response, response]
    obj = plugins.NotifyReddit(**kwargs)
    assert obj.send(body="test") is False
