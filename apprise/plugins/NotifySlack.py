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

# To use this plugin, you need to first access https://api.slack.com
# Specifically https://my.slack.com/services/new/incoming-webhook/
# to create a new incoming webhook for your account. You'll need to
# follow the wizard to pre-determine the channel(s) you want your
# message to broadcast to, and when you're complete, you will
# recieve a URL that looks something like this:
# https://hooks.slack.com/services/T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ
#                                     ^         ^               ^
#                                     |         |               |
#  These are important <--------------^---------^---------------^
#
#
import re
import requests
from json import dumps
from time import time

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize
from ..utils import compat_is_basestring

# Token required as part of the API request
#  /AAAAAAAAA/........./........................
VALIDATE_TOKEN_A = re.compile(r'[A-Z0-9]{9}')

# Token required as part of the API request
#  /........./BBBBBBBBB/........................
VALIDATE_TOKEN_B = re.compile(r'[A-Z0-9]{9}')

# Token required as part of the API request
#  /........./........./CCCCCCCCCCCCCCCCCCCCCCCC
VALIDATE_TOKEN_C = re.compile(r'[A-Za-z0-9]{24}')

# Default User
SLACK_DEFAULT_USER = 'apprise'

# Extend HTTP Error Messages
SLACK_HTTP_ERROR_MAP = HTTP_ERROR_MAP.copy()
SLACK_HTTP_ERROR_MAP.update({
    401: 'Unauthorized - Invalid Token.',
})

# Used to break path apart into list of channels
CHANNEL_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')

# Used to detect a channel
IS_CHANNEL_RE = re.compile(r'[+#@]?([A-Z0-9_]{1,32})', re.I)


class NotifySlack(NotifyBase):
    """
    A wrapper for Slack Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Slack'

    # The services URL
    service_url = 'https://slack.com/'

    # The default secure protocol
    secure_protocol = 'slack'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_slack'

    # Slack uses the http protocol with JSON requests
    notify_url = 'https://hooks.slack.com/services'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    def __init__(self, token_a, token_b, token_c, channels, **kwargs):
        """
        Initialize Slack Object
        """
        super(NotifySlack, self).__init__(**kwargs)

        if not VALIDATE_TOKEN_A.match(token_a.strip()):
            self.logger.warning(
                'The first API Token specified (%s) is invalid.' % token_a,
            )
            raise TypeError(
                'The first API Token specified (%s) is invalid.' % token_a,
            )

        # The token associated with the account
        self.token_a = token_a.strip()

        if not VALIDATE_TOKEN_B.match(token_b.strip()):
            self.logger.warning(
                'The second API Token specified (%s) is invalid.' % token_b,
            )
            raise TypeError(
                'The second API Token specified (%s) is invalid.' % token_b,
            )

        # The token associated with the account
        self.token_b = token_b.strip()

        if not VALIDATE_TOKEN_C.match(token_c.strip()):
            self.logger.warning(
                'The third API Token specified (%s) is invalid.' % token_c,
            )
            raise TypeError(
                'The third API Token specified (%s) is invalid.' % token_c,
            )

        # The token associated with the account
        self.token_c = token_c.strip()

        if not self.user:
            self.logger.warning(
                'No user was specified; using %s.' % SLACK_DEFAULT_USER)

        if compat_is_basestring(channels):
            self.channels = [x for x in filter(bool, CHANNEL_LIST_DELIM.split(
                channels,
            ))]

        elif isinstance(channels, (set, tuple, list)):
            self.channels = channels

        else:
            self.channels = list()

        if len(self.channels) == 0:
            self.logger.warning('No channel(s) were specified.')
            raise TypeError('No channel(s) were specified.')

        # Formatting requirements are defined here:
        # https://api.slack.com/docs/message-formatting
        self._re_formatting_map = {
            # New lines must become the string version
            r'\r\*\n': '\\n',
            # Escape other special characters
            r'&': '&amp;',
            r'<': '&lt;',
            r'>': '&gt;',
        }

        # Iterate over above list and store content accordingly
        self._re_formatting_rules = re.compile(
            r'(' + '|'.join(self._re_formatting_map.keys()) + r')',
            re.IGNORECASE,
        )

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Slack Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # error tracking (used for function return)
        notify_okay = True

        # Perform Formatting
        title = self._re_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_formatting_map[x.group()], title,
        )
        body = self._re_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_formatting_map[x.group()], body,
        )
        url = '%s/%s/%s/%s' % (
            self.notify_url,
            self.token_a,
            self.token_b,
            self.token_c,
        )

        image_url = self.image_url(notify_type)

        # Create a copy of the channel list
        channels = list(self.channels)
        while len(channels):
            channel = channels.pop(0)
            if not IS_CHANNEL_RE.match(channel):
                self.logger.warning(
                    "The specified channel '%s' is invalid; skipping." % (
                        channel,
                    )
                )
                continue

            if len(channel) > 1 and channel[0] == '+':
                # Treat as encoded id if prefixed with a +
                _channel = channel[1:]

            elif len(channel) > 1 and channel[0] == '@':
                # Treat @ value 'as is'
                _channel = channel

            else:
                # Prefix with channel hash tag
                _channel = '#%s' % channel

            # prepare JSON Object
            payload = {
                'channel': _channel,
                'username': self.user if self.user else SLACK_DEFAULT_USER,
                # Use Markdown language
                'mrkdwn': True,
                'attachments': [{
                    'title': title,
                    'text': body,
                    'color': self.color(notify_type),
                    # Time
                    'ts': time(),
                    'footer': self.app_id,
                }],
            }

            if image_url:
                payload['attachments'][0]['footer_icon'] = image_url

            self.logger.debug('Slack POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Slack Payload: %s' % str(payload))
            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    try:
                        self.logger.warning(
                            'Failed to send Slack:%s '
                            'notification: %s (error=%s).' % (
                                channel,
                                SLACK_HTTP_ERROR_MAP[r.status_code],
                                r.status_code))

                    except KeyError:
                        self.logger.warning(
                            'Failed to send Slack:%s '
                            'notification (error=%s).' % (
                                channel,
                                r.status_code))

                    # self.logger.debug('Response Details: %s' % r.raw.read())

                    # Return; we're done
                    notify_okay = False

                else:
                    self.logger.info('Sent Slack notification.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending Slack:%s ' % (
                        channel) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                notify_okay = False

            if len(channels):
                # Prevent thrashing requests
                self.throttle()

        return notify_okay

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
        }

        # Determine if there is a botname present
        botname = ''
        if self.user:
            botname = '{botname}@'.format(
                botname=self.quote(self.user, safe=''),
            )

        return '{schema}://{botname}{token_a}/{token_b}/{token_c}/{targets}/'\
            '?{args}'.format(
                schema=self.secure_protocol,
                botname=botname,
                token_a=self.quote(self.token_a, safe=''),
                token_b=self.quote(self.token_b, safe=''),
                token_c=self.quote(self.token_c, safe=''),
                targets='/'.join(
                    [self.quote(x, safe='') for x in self.channels]),
                args=self.urlencode(args),
            )

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
        token_a = results['host']

        # Now fetch the remaining tokens
        try:
            token_b, token_c = [x for x in filter(
                bool, NotifyBase.split_path(results['fullpath']))][0:2]

        except (ValueError, AttributeError, IndexError):
            # We're done
            return None

        channels = [x for x in filter(
            bool, NotifyBase.split_path(results['fullpath']))][2:]

        results['token_a'] = token_a
        results['token_b'] = token_b
        results['token_c'] = token_c
        results['channels'] = channels

        return results
