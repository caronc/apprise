# -*- coding: utf-8 -*-
#
# Twitter Notify Wrapper
#
# Copyright (C) 2017-2018 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

from . import tweepy
from ..NotifyBase import NotifyBase


class NotifyTwitter(NotifyBase):
    """
    A wrapper to Twitter Notifications

    """

    # The default secure protocol
    secure_protocol = 'tweet'

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

        text = '%s\r\n%s' % (title, body)
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
