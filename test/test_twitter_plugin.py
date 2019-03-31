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
from random import choice
from string import ascii_uppercase as str_alpha
from string import digits as str_num

from apprise import plugins
from apprise import NotifyType
from apprise import Apprise
from apprise import OverflowMode

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
    ('tweet://:@/', {
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
    ('tweet://usera@consumer_key/consumer_key/access_token/'
        'access_secret/?to=userb', {
            # We're good!
            'instance': plugins.NotifyTwitter,
        }),
)


@mock.patch('apprise.plugins.tweepy.API')
@mock.patch('apprise.plugins.tweepy.OAuthHandler')
def test_plugin(mock_oauth, mock_api):
    """
    API: NotifyTwitter Plugin() (pt1)

    """
    # Disable Throttling to speed testing
    plugins.NotifyBase.NotifyBase.request_rate_per_sec = 0

    # Define how many characters exist per line
    row = 80

    # Some variables we use to control the data we work with
    body_len = 1024
    title_len = 1024

    # Create a large body and title with random data
    body = ''.join(choice(str_alpha + str_num + ' ') for _ in range(body_len))
    body = '\r\n'.join([body[i: i + row] for i in range(0, len(body), row)])

    # Create our title using random data
    title = ''.join(choice(str_alpha + str_num) for _ in range(title_len))

    # iterate over our dictionary and test it out
    for (url, meta) in TEST_URLS:

        # Our expected instance
        instance = meta.get('instance', None)

        # Our expected server objects
        self = meta.get('self', None)

        # Our expected Query response (True, False, or exception type)
        response = meta.get('response', True)

        # Allow notification type override, otherwise default to INFO
        notify_type = meta.get('notify_type', NotifyType.INFO)

        # Allow us to force the server response code to be something other then
        # the defaults
        response = meta.get(
            'response', True if response else False)

        try:
            obj = Apprise.instantiate(url, suppress_exceptions=False)

            if obj is None:
                if instance is not None:
                    # We're done (assuming this is what we were expecting)
                    print("{} didn't instantiate itself "
                          "(we expected it to)".format(url))
                    assert False
                continue

            if instance is None:
                # Expected None but didn't get it
                print('%s instantiated %s (but expected None)' % (
                    url, str(obj)))
                assert False

            assert isinstance(obj, instance) is True

            if isinstance(obj, plugins.NotifyBase.NotifyBase):
                # We loaded okay; now lets make sure we can reverse this url
                assert isinstance(obj.url(), six.string_types) is True

                # Instantiate the exact same object again using the URL from
                # the one that was already created properly
                obj_cmp = Apprise.instantiate(obj.url())

                # Our object should be the same instance as what we had
                # originally expected above.
                if not isinstance(obj_cmp, plugins.NotifyBase.NotifyBase):
                    # Assert messages are hard to trace back with the way
                    # these tests work. Just printing before throwing our
                    # assertion failure makes things easier to debug later on
                    print('TEST FAIL: {} regenerated as {}'.format(
                        url, obj.url()))
                    assert False

            if self:
                # Iterate over our expected entries inside of our object
                for key, val in self.items():
                    # Test that our object has the desired key
                    assert hasattr(key, obj) is True
                    assert getattr(key, obj) == val

            obj.request_rate_per_sec = 0

            # check that we're as expected
            assert obj.notify(
                title='test', body='body',
                notify_type=NotifyType.INFO) == response

            # check that this doesn't change using different overflow
            # methods
            assert obj.notify(
                body=body, title=title,
                notify_type=notify_type,
                overflow=OverflowMode.UPSTREAM) == response
            assert obj.notify(
                body=body, title=title,
                notify_type=notify_type,
                overflow=OverflowMode.TRUNCATE) == response
            assert obj.notify(
                body=body, title=title,
                notify_type=notify_type,
                overflow=OverflowMode.SPLIT) == response

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
