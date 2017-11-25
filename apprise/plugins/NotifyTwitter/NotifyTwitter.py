# -*- encoding: utf-8 -*-
#
# Twitter Notify Wrapper
#
# Copyright (C) 2014-2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# apprise is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# apprise is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with apprise. If not, see <http://www.gnu.org/licenses/>.

from . import tweepy
from ..NotifyBase import NotifyBase
from ..NotifyBase import NotifyFormat

# Direct Messages have not image support
TWITTER_IMAGE_XY = None


class NotifyTwitter(NotifyBase):
    """
    A wrapper to Twitter Notifications

    """

    # The default protocol
    PROTOCOL = 'tweet'

    # The default secure protocol
    SECURE_PROTOCOL = 'tweet'

    def __init__(self, ckey, csecret, akey, asecret, **kwargs):
        """
        Initialize Twitter Object

        Tweets are restriced to 140 (soon to be 240), but DM messages
        do not have any restriction on them
        """
        super(NotifyTwitter, self).__init__(
            title_maxlen=250, body_maxlen=4096,
            image_size=TWITTER_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

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

    def _notify(self, title, body, notify_type, **kwargs):
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
