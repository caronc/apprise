# -*- encoding: utf-8 -*-
#
# Slack Notify Wrapper
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

# To use this plugin, you need to first access https://api.slack.com
# Specifically https://my.slack.com/services/new/incoming-webhook/
# to create a new incoming webhook for your account. You'll need to
# follow the wizard to pre-determine the channel(s) you want your
# message to broadcast to, and when you're complete, you will
# recieve a URL that looks something like this:
# https://hooks.slack.com/services/T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7F
#                                     ^         ^               ^
#                                     |         |               |
#  These are important <--------------^---------^---------------^
#
#
import requests
import re

from json import dumps
from time import time

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import HTTP_ERROR_MAP
from .NotifyBase import HTML_NOTIFY_MAP
from .NotifyBase import NotifyImageSize

# Slack uses the http protocol with JSON requests
SLACK_URL = 'https://hooks.slack.com/services'

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
SLACK_HTTP_ERROR_MAP = dict(HTTP_ERROR_MAP.items() + {
    401: 'Unauthorized - Invalid Token.',
}.items())

# Used to break path apart into list of devices
CHANNEL_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')

# Used to detect a device
IS_CHANNEL_RE = re.compile(r'#?([A-Za-z0-9_]{1,32})')

# Image Support (72x72)
SLACK_IMAGE_XY = NotifyImageSize.XY_72


class NotifySlack(NotifyBase):
    """
    A wrapper for Slack Notifications
    """

    # The default protocol
    PROTOCOL = 'slack'

    # The default secure protocol
    SECURE_PROTOCOL = 'slack'

    def __init__(self, token_a, token_b, token_c, channels, **kwargs):
        """
        Initialize Slack Object
        """
        super(NotifySlack, self).__init__(
            title_maxlen=250, body_maxlen=1000,
            image_size=SLACK_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

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
            self.user = SLACK_DEFAULT_USER

        if isinstance(channels, basestring):
            self.channels = filter(bool, CHANNEL_LIST_DELIM.split(
                channels,
            ))
        elif isinstance(channels, (tuple, list)):
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
            '\r\*\n': '\\n',
            # Escape other special characters
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
        }

        # Iterate over above list and store content accordingly
        self._re_formatting_rules = re.compile(
            r'(' + '|'.join(self._re_formatting_map.keys()) + r')',
            re.IGNORECASE,
        )

    def _notify(self, title, body, notify_type, **kwargs):
        """
        Perform Slack Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # error tracking (used for function return)
        has_error = False

        # Perform Formatting
        title = self._re_formatting_rules.sub(
            lambda x: self._re_formatting_map[x.group()], title,
        )
        body = self._re_formatting_rules.sub(
            lambda x: self._re_formatting_map[x.group()], body,
        )
        url = '%s/%s/%s/%s' % (
            SLACK_URL,
            self.token_a,
            self.token_b,
            self.token_c,
        )

        image_url = None
        if self.include_image:
            image_url = self.image_url(
                notify_type,
            )

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
                'username': self.user,
                # Use Markdown language
                'mrkdwn': True,
                'attachments': [{
                    'title': title,
                    'text': body,
                    'color': HTML_NOTIFY_MAP[notify_type],
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

                    except IndexError:
                        self.logger.warning(
                            'Failed to send Slack:%s '
                            'notification (error=%s).' % (
                                channel,
                                r.status_code))

                    # self.logger.debug('Response Details: %s' % r.raw.read())

                    # Return; we're done
                    has_error = True

            except requests.ConnectionError as e:
                self.logger.warning(
                    'A Connection error occured sending Slack:%s ' % (
                        channel) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                has_error = True

            if len(channels):
                # Prevent thrashing requests
                self.throttle()

        return has_error
