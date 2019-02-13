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

from . import tweepy
from ..NotifyBase import NotifyBase


class NotifyTwitter(NotifyBase):
    """
    A wrapper to Twitter Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = 'Twitter'

    # The services URL
    service_url = 'https://twitter.com/'

    # The default secure protocol
    secure_protocol = 'tweet'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_twitter'

    # The maximum allowable characters allowed in the body per message
    # This is used during a Private DM Message Size (not Public Tweets
    # which are limited to 240 characters)
    body_maxlen = 4096

    def __init__(self, ckey, csecret, akey, asecret, **kwargs):
        """
        Initialize Twitter Object

        """
        super(NotifyTwitter, self).__init__(**kwargs)

        if not ckey:
            raise TypeError(
                'An invalid Consumer API Key was specified.'
            )

        if not csecret:
            raise TypeError(
                'An invalid Consumer Secret API Key was specified.'
            )

        if not akey:
            raise TypeError(
                'An invalid Acess Token API Key was specified.'
            )

        if not asecret:
            raise TypeError(
                'An invalid Acess Token Secret API Key was specified.'
            )

        if not self.user:
            raise TypeError(
                'No user was specified.'
            )

        # Store our data
        self.ckey = ckey
        self.csecret = csecret
        self.akey = akey
        self.asecret = asecret

        return

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Twitter Notification
        """

        try:
            # Attempt to Establish a connection to Twitter
            self.auth = tweepy.OAuthHandler(self.ckey, self.csecret)

            # Apply our Access Tokens
            self.auth.set_access_token(self.akey, self.asecret)

        except Exception:
            self.logger.warning(
                'Twitter authentication failed; '
                'please verify your configuration.'
            )
            return False

        # Only set title if it was specified
        text = body if not title else '%s\r\n%s' % (title, body)

        try:
            # Get our API
            api = tweepy.API(self.auth)

            # Send our Direct Message
            api.send_direct_message(self.user, text=text)
            self.logger.info('Sent Twitter DM notification.')

        except Exception as e:
            self.logger.warning(
                'A Connection error occured sending Twitter '
                'direct message to %s.' % self.user)
            self.logger.debug('Twitter Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Apply our settings now

        # The first token is stored in the hostname
        consumer_key = results['host']

        # Now fetch the remaining tokens
        try:
            consumer_secret, access_token_key, access_token_secret = \
                [x for x in filter(bool, NotifyBase.split_path(
                    results['fullpath']))][0:3]

        except (ValueError, AttributeError, IndexError):
            # Force some bad values that will get caught
            # in parsing later
            consumer_secret = None
            access_token_key = None
            access_token_secret = None

        results['ckey'] = consumer_key
        results['csecret'] = consumer_secret
        results['akey'] = access_token_key
        results['asecret'] = access_token_secret

        return results
