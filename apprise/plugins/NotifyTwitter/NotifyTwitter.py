# -*- coding: utf-8 -*-
#
# Twitter Notify Wrapper
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
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

# Direct Messages have not image support
TWITTER_IMAGE_XY = None


class NotifyTwitter(NotifyBase):
    """
    A wrapper to Twitter Notifications

    """

    # The default secure protocol
    secure_protocol = 'tweet'

    def __init__(self, ckey, csecret, akey, asecret, **kwargs):
        """
        Initialize Twitter Object

        Tweets are restriced to 140 (soon to be 240), but DM messages
        do not have any restriction on them
        """
        super(NotifyTwitter, self).__init__(
            title_maxlen=250, body_maxlen=4096,
            image_size=TWITTER_IMAGE_XY, **kwargs)

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

        try:
            # Attempt to Establish a connection to Twitter
            self.auth = tweepy.OAuthHandler(ckey, csecret)

            # Apply our Access Tokens
            self.auth.set_access_token(akey, asecret)

        except Exception:
            raise TypeError(
                'Twitter authentication failed; '
                'please verify your configuration.'
            )

        return

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Twitter Notification
        """

        text = '%s\r\n%s' % (title, body)
        try:
            # Get our API
            api = tweepy.API(self.auth)

            # Send our Direct Message
            api.send_direct_message(self.user, text=text)

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

        # The first token is stored in the hostnamee
        consumer_key = results['host']

        # Now fetch the remaining tokens
        try:
            consumer_secret, access_token_key, access_token_secret = \
                filter(bool, NotifyBase.split_path(results['fullpath']))[0:3]

        except (AttributeError, IndexError):
            # Force some bad values that will get caught
            # in parsing later
            consumer_secret = None
            access_token_key = None
            access_token_secret = None

        results['ckey'] = consumer_key,
        results['csecret'] = consumer_secret,
        results['akey'] = access_token_key,
        results['asecret'] = access_token_secret,

        return results
