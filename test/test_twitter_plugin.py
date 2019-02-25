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

from apprise import plugins
from apprise import NotifyType
from apprise import Apprise
import mock

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


TEST_URLS = (
    ##################################
    # NotifyTwitter
    ##################################
    ('tweet://', {
        'instance': None,
    }),
    ('tweet://consumer_key', {
        # Missing Keys
        'instance': TypeError,
    }),
    ('tweet://consumer_key/consumer_key/', {
        # Missing Keys
        'instance': TypeError,
    }),
    ('tweet://consumer_key/consumer_key/access_token/', {
        # Missing Access Secret
        'instance': TypeError,
    }),
    ('tweet://consumer_key/consumer_key/access_token/access_secret', {
        # Missing User
        'instance': TypeError,
    }),
    ('tweet://user@consumer_key/consumer_key/access_token/access_secret', {
        # We're good!
        'instance': plugins.NotifyTwitter,
    }),
    ('tweet://:@/', {
        'instance': None,
    }),
)


@mock.patch('apprise.plugins.tweepy.API')
@mock.patch('apprise.plugins.tweepy.OAuthHandler')
def test_plugin(mock_oauth, mock_api):
    """
    API: NotifyTwitter Plugin() (pt1)

    """

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected server objects
        self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Allow us to force the server response code to be something other then
        # the defaults
        response = meta.get(
            'response', True if response else False)

        try:
            obj = Apprise.instantiate(url, suppress_exceptions=False)

            if instance is None:
                # Check that we got what we came for
                assert obj is instance
                continue

            assert(isinstance(obj, instance))

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert(hasattr(key, obj))
                    assert(getattr(key, obj) == val)

            # check that we're as expected
            assert obj.notify(
                title='test', body='body',
                notify_type=NotifyType.INFO) == response

        except AssertionError:
            # Don't mess with these entries
            raise

        except Exception as e:
            # Handle our exception
            assert(instance is not None)
            assert(isinstance(e, instance))


@mock.patch('apprise.plugins.tweepy.API.send_direct_message')
@mock.patch('apprise.plugins.tweepy.OAuthHandler.set_access_token')
def test_twitter_plugin_init(set_access_token, send_direct_message):
    """
    API: NotifyTwitter Plugin() (pt2)

    """

    try:
        plugins.NotifyTwitter(
            ckey=None, csecret=None, akey=None, asecret=None)
        assert False
    except TypeError:
        # All keys set to none
        assert True

    try:
        plugins.NotifyTwitter(
            ckey='value', csecret=None, akey=None, asecret=None)
        assert False
    except TypeError:
        # csecret not set
        assert True

    try:
        plugins.NotifyTwitter(
            ckey='value', csecret='value', akey=None, asecret=None)
        assert False
    except TypeError:
        # akey not set
        assert True

    try:
        plugins.NotifyTwitter(
            ckey='value', csecret='value', akey='value', asecret=None)
        assert False
    except TypeError:
        # asecret not set
        assert True

    try:
        plugins.NotifyTwitter(
            ckey='value', csecret='value', akey='value', asecret='value')
        assert False
    except TypeError:
        # user not set
        assert True

    try:
        obj = plugins.NotifyTwitter(
            ckey='value', csecret='value', akey='value', asecret='value',
            user='l2g')
        # We should initialize properly
        assert True

    except TypeError:
        # We should not reach here
        assert False

    set_access_token.side_effect = TypeError('Invalid')

    assert obj.notify(
        title='test', body='body',
        notify_type=NotifyType.INFO) is False

    # Make it so we can pass authentication, but fail on message
    # delivery
    set_access_token.side_effect = None
    set_access_token.return_value = True
    send_direct_message.side_effect = plugins.tweepy.error.TweepError(
        0, 'tweepy.error.TweepyError() not handled'),

    assert obj.notify(
        title='test', body='body',
        notify_type=NotifyType.INFO) is False
