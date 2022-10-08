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

import os
from unittest import mock

import pytest
import requests
from json import dumps
from datetime import datetime
from apprise import Apprise
from apprise import plugins
from apprise import NotifyType
from apprise import AppriseAttachment
from helpers import AppriseURLTester

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')

# Our Testing URLs
apprise_url_tests = (
    ##################################
    # NotifyTwitter
    ##################################
    ('twitter://', {
        # Missing Consumer API Key
        'instance': TypeError,
    }),
    ('twitter://:@/', {
        'instance': TypeError,
    }),
    ('twitter://consumer_key', {
        # Missing Keys
        'instance': TypeError,
    }),
    ('twitter://consumer_key/consumer_secret/', {
        # Missing Keys
        'instance': TypeError,
    }),
    ('twitter://consumer_key/consumer_secret/access_token/', {
        # Missing Access Secret
        'instance': TypeError,
    }),
    ('twitter://consumer_key/consumer_secret/access_token/access_secret', {
        # No user mean's we message ourselves
        'instance': plugins.NotifyTwitter,
        # Expected notify() response False (because we won't be able
        # to detect our user)
        'notify_response': False,

        # Our expected url(privacy=True) startswith() response:
        'privacy_url': 'twitter://c...y/****/a...n/****',
    }),
    ('twitter://consumer_key/consumer_secret/access_token/access_secret'
        '?cache=no', {
            # No user mean's we message ourselves
            'instance': plugins.NotifyTwitter,
            # However we'll be okay if we return a proper response
            'requests_response_text': {
                'id': 12345,
                'screen_name': 'test',
                # For attachment handling
                'media_id': 123,
            },
        }),
    ('twitter://consumer_key/consumer_secret/access_token/access_secret', {
        # No user mean's we message ourselves
        'instance': plugins.NotifyTwitter,
        # However we'll be okay if we return a proper response
        'requests_response_text': {
            'id': 12345,
            'screen_name': 'test',
            # For attachment handling
            'media_id': 123,
        },
    }),
    # A duplicate of the entry above, this will cause cache to be referenced
    ('twitter://consumer_key/consumer_secret/access_token/access_secret', {
        # No user mean's we message ourselves
        'instance': plugins.NotifyTwitter,
        # However we'll be okay if we return a proper response
        'requests_response_text': {
            'id': 12345,
            'screen_name': 'test',
            # For attachment handling
            'media_id': 123,
        },
    }),
    # handle cases where the screen_name is missing from the response causing
    # an exception during parsing
    ('twitter://consumer_key/consumer_secret2/access_token/access_secret', {
        # No user mean's we message ourselves
        'instance': plugins.NotifyTwitter,
        # However we'll be okay if we return a proper response
        'requests_response_text': {
            'id': 12345,
            # For attachment handling
            'media_id': 123,
        },
        # due to a mangled response_text we'll fail
        'notify_response': False,
    }),
    ('twitter://user@consumer_key/csecret2/access_token/access_secret/-/%/', {
        # One Invalid User
        'instance': plugins.NotifyTwitter,
        # Expected notify() response False (because we won't be able
        # to detect our user)
        'notify_response': False,
    }),
    ('twitter://user@consumer_key/csecret/access_token/access_secret'
        '?cache=No&batch=No', {
            # No Cache & No Batch
            'instance': plugins.NotifyTwitter,
            'requests_response_text': [{
                'id': 12345,
                'screen_name': 'user'
            }],
        }),
    ('twitter://user@consumer_key/csecret/access_token/access_secret', {
        # We're good!
        'instance': plugins.NotifyTwitter,
        'requests_response_text': [{
            'id': 12345,
            'screen_name': 'user'
        }],
    }),
    # A duplicate of the entry above, this will cause cache to be referenced
    # for this reason, we don't even need to return a valid response
    ('twitter://user@consumer_key/csecret/access_token/access_secret', {
        # We're identifying the same user we already sent to
        'instance': plugins.NotifyTwitter,
    }),
    ('twitter://ckey/csecret/access_token/access_secret?mode=tweet', {
        # A Public Tweet
        'instance': plugins.NotifyTwitter,
    }),
    ('twitter://user@ckey/csecret/access_token/access_secret?mode=invalid', {
        # An invalid mode
        'instance': TypeError,
    }),
    ('twitter://usera@consumer_key/consumer_secret/access_token/'
        'access_secret/user/?to=userb', {
            # We're good!
            'instance': plugins.NotifyTwitter,
            'requests_response_text': [{
                'id': 12345,
                'screen_name': 'usera'
            }, {
                'id': 12346,
                'screen_name': 'userb'
            }, {
                # A garbage entry we can test exception handling on
                'id': 123,
            }],
        }),
    ('twitter://ckey/csecret/access_token/access_secret', {
        'instance': plugins.NotifyTwitter,
        # throw a bizzare code forcing us to fail to look it up
        'response': False,
        'requests_response_code': 999,
    }),
    ('twitter://ckey/csecret/access_token/access_secret', {
        'instance': plugins.NotifyTwitter,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
    ('twitter://ckey/csecret/access_token/access_secret?mode=tweet', {
        'instance': plugins.NotifyTwitter,
        # Throws a series of connection and transfer exceptions when this flag
        # is set and tests that we gracfully handle them
        'test_requests_exceptions': True,
    }),
)


def test_plugin_twitter_urls():
    """
    NotifyTwitter() Apprise URLs

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch('requests.get')
@mock.patch('requests.post')
def test_plugin_twitter_general(mock_post, mock_get):
    """
    NotifyTwitter() General Tests

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
    assert isinstance(obj.url(), str) is True

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


def test_plugin_twitter_edge_cases():
    """
    NotifyTwitter() Edge Cases

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


@mock.patch('requests.post')
@mock.patch('requests.get')
def test_plugin_twitter_dm_attachments(mock_get, mock_post):
    """
    NotifyTwitter() DM Attachment Checks

    """
    ckey = 'ckey'
    csecret = 'csecret'
    akey = 'akey'
    asecret = 'asecret'
    screen_name = 'apprise'

    good_dm_response_obj = {
        'screen_name': screen_name,
        'id': 9876,
    }

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare a good DM response
    good_dm_response = mock.Mock()
    good_dm_response.content = dumps(good_dm_response_obj)
    good_dm_response.status_code = requests.codes.ok

    # Prepare bad response
    bad_response = mock.Mock()
    bad_response.content = dumps({})
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare a good media response
    good_media_response = mock.Mock()
    good_media_response.content = dumps({
        "media_id": 710511363345354753,
        "media_id_string": "710511363345354753",
        "media_key": "3_710511363345354753",
        "size": 11065,
        "expires_after_secs": 86400,
        "image": {
            "image_type": "image/jpeg",
            "w": 800,
            "h": 320
        }
    })
    good_media_response.status_code = requests.codes.ok

    # Prepare a bad media response
    bad_media_response = mock.Mock()
    bad_media_response.content = dumps({
        "errors": [
            {
                "code": 93,
                "message": "This application is not allowed to access or "
                "delete your direct messages.",
            }]})
    bad_media_response.status_code = requests.codes.internal_server_error

    mock_post.side_effect = [good_media_response, good_dm_response]
    mock_get.return_value = good_dm_response

    twitter_url = 'twitter://{}/{}/{}/{}'.format(ckey, csecret, akey, asecret)

    # attach our content
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # Send our notification
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test our call count
    assert mock_get.call_count == 1
    assert mock_get.call_args_list[0][0][0] == \
        'https://api.twitter.com/1.1/account/verify_credentials.json'
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://api.twitter.com/1.1/direct_messages/events/new.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    # Test case where upload fails
    mock_get.return_value = good_dm_response
    mock_post.side_effect = [bad_media_response, good_dm_response]

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # Send our notification; it will fail because of the media response
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Test our call count
    assert mock_get.call_count == 0
    # No get request as cached response is used
    assert mock_post.call_count == 1
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    # Test case where upload fails
    mock_get.return_value = good_dm_response
    mock_post.side_effect = [good_media_response, bad_response]

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # Send our notification; it will fail because of the media response
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    assert mock_get.call_count == 0
    # No get request as cached response is used
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://api.twitter.com/1.1/direct_messages/events/new.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    mock_post.side_effect = [good_media_response, good_dm_response]
    mock_get.return_value = good_dm_response

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    # No get request as cached response is used
    assert mock_get.call_count == 0

    # No post request as attachment is no good anyway
    assert mock_post.call_count == 0

    mock_get.reset_mock()
    mock_post.reset_mock()

    mock_post.side_effect = [
        good_media_response, good_media_response, good_media_response,
        good_media_response, good_dm_response, good_dm_response,
        good_dm_response, good_dm_response]
    mock_get.return_value = good_dm_response

    # 4 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.jpeg'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.png'),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, 'apprise-test.mp4'),
    ]

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    assert mock_get.call_count == 0
    # No get request as cached response is used
    assert mock_post.call_count == 8
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[2][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[3][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[4][0][0] == \
        'https://api.twitter.com/1.1/direct_messages/events/new.json'
    assert mock_post.call_args_list[5][0][0] == \
        'https://api.twitter.com/1.1/direct_messages/events/new.json'
    assert mock_post.call_args_list[6][0][0] == \
        'https://api.twitter.com/1.1/direct_messages/events/new.json'
    assert mock_post.call_args_list[7][0][0] == \
        'https://api.twitter.com/1.1/direct_messages/events/new.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    # We have an OSError thrown in the middle of our preparation
    mock_post.side_effect = [good_media_response, OSError()]
    mock_get.return_value = good_dm_response

    # 2 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.png'),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, 'apprise-test.mp4'),
    ]

    # We'll fail to send this time
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    assert mock_get.call_count == 0
    # No get request as cached response is used
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'


@mock.patch('requests.post')
@mock.patch('requests.get')
def test_plugin_twitter_tweet_attachments(mock_get, mock_post):
    """
    NotifyTwitter() Tweet Attachment Checks

    """
    ckey = 'ckey'
    csecret = 'csecret'
    akey = 'akey'
    asecret = 'asecret'
    screen_name = 'apprise'

    good_tweet_response_obj = {
        'screen_name': screen_name,
        'id': 9876,
    }

    # Disable Throttling to speed testing
    plugins.NotifyBase.request_rate_per_sec = 0

    # Prepare a good DM response
    good_tweet_response = mock.Mock()
    good_tweet_response.content = dumps(good_tweet_response_obj)
    good_tweet_response.status_code = requests.codes.ok

    # Prepare bad response
    bad_response = mock.Mock()
    bad_response.content = dumps({})
    bad_response.status_code = requests.codes.internal_server_error

    # Prepare a good media response
    good_media_response = mock.Mock()
    good_media_response.content = dumps({
        "media_id": 710511363345354753,
        "media_id_string": "710511363345354753",
        "media_key": "3_710511363345354753",
        "size": 11065,
        "expires_after_secs": 86400,
        "image": {
            "image_type": "image/jpeg",
            "w": 800,
            "h": 320
        }
    })
    good_media_response.status_code = requests.codes.ok

    # Prepare a bad media response
    bad_media_response = mock.Mock()
    bad_media_response.content = dumps({
        "errors": [
            {
                "code": 93,
                "message": "This application is not allowed to access or "
                "delete your direct messages.",
            }]})
    bad_media_response.status_code = requests.codes.internal_server_error

    mock_post.side_effect = [good_media_response, good_tweet_response]
    mock_get.return_value = good_tweet_response

    twitter_url = 'twitter://{}/{}/{}/{}?mode=tweet'.format(
        ckey, csecret, akey, asecret)

    # attach our content
    attach = AppriseAttachment(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'))

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # Send our notification
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test our call count
    assert mock_get.call_count == 0
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'

    # Update our good response to have more details in it
    good_tweet_response_obj = {
        'screen_name': screen_name,
        'id': 9876,
        # needed for additional logging
        'id_str': '12345',
        'user': {
            'screen_name': screen_name,
        }
    }

    good_tweet_response.content = dumps(good_tweet_response_obj)

    mock_get.reset_mock()
    mock_post.reset_mock()

    mock_post.side_effect = [good_media_response, good_tweet_response]
    mock_get.return_value = good_tweet_response

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # Send our notification (again); this time there willb e more tweet logging
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    # Test our call count
    assert mock_get.call_count == 0
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    mock_post.side_effect = [good_media_response, bad_media_response]

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # Our notification will fail now since our tweet will error out
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Test our call count
    assert mock_get.call_count == 0
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    bad_media_response.content = ''

    mock_post.side_effect = [good_media_response, bad_media_response]

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # Our notification will fail now since our tweet will error out
    # This is the same test as above, except our error response isn't parseable
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    # Test our call count
    assert mock_get.call_count == 0
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    # Test case where upload fails
    mock_get.return_value = good_tweet_response
    mock_post.side_effect = [good_media_response, bad_response]

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # Send our notification; it will fail because of the media response
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    assert mock_get.call_count == 0
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    mock_post.side_effect = [good_media_response, good_tweet_response]
    mock_get.return_value = good_tweet_response

    # An invalid attachment will cause a failure
    path = os.path.join(TEST_VAR_DIR, '/invalid/path/to/an/invalid/file.jpg')
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=path) is False

    # No get request as cached response is used
    assert mock_get.call_count == 0

    # No post request as attachment is no good anyway
    assert mock_post.call_count == 0

    mock_get.reset_mock()
    mock_post.reset_mock()

    mock_post.side_effect = [
        good_media_response, good_media_response, good_media_response,
        good_media_response, good_tweet_response, good_tweet_response,
        good_tweet_response, good_tweet_response]
    mock_get.return_value = good_tweet_response

    # instantiate our object (without a batch mode)
    obj = Apprise.instantiate(twitter_url + "&batch=no")

    # 4 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.jpeg'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.png'),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, 'apprise-test.mp4'),
    ]

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    assert mock_get.call_count == 0
    # No get request as cached response is used
    assert mock_post.call_count == 8
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[2][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[3][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[4][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'
    assert mock_post.call_args_list[5][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'
    assert mock_post.call_args_list[6][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'
    assert mock_post.call_args_list[7][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    mock_post.side_effect = [
        good_media_response, good_media_response, good_media_response,
        good_media_response, good_tweet_response, good_tweet_response,
        good_tweet_response, good_tweet_response]
    mock_get.return_value = good_tweet_response

    # instantiate our object
    obj = Apprise.instantiate(twitter_url)

    # 4 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.jpeg'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.png'),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, 'apprise-test.mp4'),
    ]

    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is True

    assert mock_get.call_count == 0
    # No get request as cached response is used
    assert mock_post.call_count == 7
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[2][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[3][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[4][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'
    assert mock_post.call_args_list[5][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'
    # The 2 images are grouped together (batch mode)
    assert mock_post.call_args_list[6][0][0] == \
        'https://api.twitter.com/1.1/statuses/update.json'

    mock_get.reset_mock()
    mock_post.reset_mock()

    # We have an OSError thrown in the middle of our preparation
    mock_post.side_effect = [good_media_response, OSError()]
    mock_get.return_value = good_tweet_response

    # 2 images are produced
    attach = [
        os.path.join(TEST_VAR_DIR, 'apprise-test.gif'),
        os.path.join(TEST_VAR_DIR, 'apprise-test.png'),
        # This one is not supported, so it's ignored gracefully
        os.path.join(TEST_VAR_DIR, 'apprise-test.mp4'),
    ]

    # We'll fail to send this time
    assert obj.notify(
        body='body', title='title', notify_type=NotifyType.INFO,
        attach=attach) is False

    assert mock_get.call_count == 0
    # No get request as cached response is used
    assert mock_post.call_count == 2
    assert mock_post.call_args_list[0][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
    assert mock_post.call_args_list[1][0][0] == \
        'https://upload.twitter.com/1.1/media/upload.json'
