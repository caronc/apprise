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
from ...common import NotifyType
from ...utils import parse_list


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

    # Twitter does have titles when creating a message
    title_maxlen = 0

    def __init__(self, ckey, csecret, akey, asecret, targets=None, **kwargs):
        """
        Initialize Twitter Object

        """
        super(NotifyTwitter, self).__init__(**kwargs)

        if not ckey:
            msg = 'An invalid Consumer API Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not csecret:
            msg = 'An invalid Consumer Secret API Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not akey:
            msg = 'An invalid Access Token API Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not asecret:
            msg = 'An invalid Access Token Secret API Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Identify our targets
        self.targets = parse_list(targets)

        if len(self.targets) == 0 and not self.user:
            msg = 'No user(s) were specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our data
        self.ckey = ckey
        self.csecret = csecret
        self.akey = akey
        self.asecret = asecret

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
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

        # Get ourselves a list of targets
        users = list(self.targets)
        if not users:
            # notify ourselves
            users.append(self.user)

        # Error Tracking
        has_error = False

        while len(users) > 0:
            # Get our user
            user = users.pop(0)

            # Always call throttle before any remote server i/o is made to
            # avoid thrashing the remote server and risk being blocked.
            self.throttle()

            try:
                # Get our API
                api = tweepy.API(self.auth)

                # Send our Direct Message
                api.send_direct_message(user, text=body)
                self.logger.info(
                    'Sent Twitter DM notification to {}.'.format(user))

            except Exception as e:
                self.logger.warning(
                    'A Connection error occured sending Twitter '
                    'direct message to %s.' % user)
                self.logger.debug('Twitter Exception: %s' % str(e))

                # Track our error
                has_error = True

        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        if len(self.targets) > 0:
            args['to'] = ','.join([NotifyTwitter.quote(x, safe='')
                                   for x in self.targets])

        return '{schema}://{auth}{ckey}/{csecret}/{akey}/{asecret}' \
            '/?{args}'.format(
                auth='' if not self.user else '{user}@'.format(
                    user=NotifyTwitter.quote(self.user, safe='')),
                schema=self.secure_protocol,
                ckey=NotifyTwitter.quote(self.ckey, safe=''),
                asecret=NotifyTwitter.quote(self.csecret, safe=''),
                akey=NotifyTwitter.quote(self.akey, safe=''),
                csecret=NotifyTwitter.quote(self.asecret, safe=''),
                args=NotifyTwitter.urlencode(args))

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
        consumer_key = NotifyTwitter.unquote(results['host'])

        # Now fetch the remaining tokens
        try:
            consumer_secret, access_token_key, access_token_secret = \
                NotifyTwitter.split_path(results['fullpath'])[0:3]

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

        # Support the to= allowing one to identify more then one user to tweet
        # too
        results['targets'] = NotifyTwitter.parse_list(results['qsd'].get('to'))

        return results
