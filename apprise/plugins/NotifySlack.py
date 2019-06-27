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
from ..common import NotifyImageSize
from ..common import NotifyType
from ..common import NotifyFormat
from ..utils import parse_bool
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _

# Token required as part of the API request
#  /AAAAAAAAA/........./........................
VALIDATE_TOKEN_A = re.compile(r'[A-Z0-9]{9}')

# Token required as part of the API request
#  /........./BBBBBBBBB/........................
VALIDATE_TOKEN_B = re.compile(r'[A-Z0-9]{9}')

# Token required as part of the API request
#  /........./........./CCCCCCCCCCCCCCCCCCCCCCCC
VALIDATE_TOKEN_C = re.compile(r'[A-Za-z0-9]{24}')

# Extend HTTP Error Messages
SLACK_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}

# Used to break path apart into list of channels
CHANNEL_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')

# Used to detect a channel
IS_VALID_TARGET_RE = re.compile(r'[+#@]?([A-Z0-9_]{1,32})', re.I)


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

    # Default Notification Format
    notify_format = NotifyFormat.MARKDOWN

    # Define object templates
    templates = (
        '{schema}://{token_a}/{token_b}{token_c}',
        '{schema}://{botname}@{token_a}/{token_b}{token_c}',
        '{schema}://{token_a}/{token_b}{token_c}/{targets}',
        '{schema}://{botname}@{token_a}/{token_b}{token_c}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'botname': {
            'name': _('Bot Name'),
            'type': 'string',
            'map_to': 'user',
        },
        'token_a': {
            'name': _('Token A'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'[A-Z0-9]{9}', 'i'),
        },
        'token_b': {
            'name': _('Token B'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'[A-Z0-9]{9}', 'i'),
        },
        'token_c': {
            'name': _('Token C'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'[A-Za-z0-9]{24}', 'i'),
        },
        'target_encoded_id': {
            'name': _('Target Encoded ID'),
            'type': 'string',
            'prefix': '+',
            'map_to': 'targets',
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'target_channels': {
            'name': _('Target Channel'),
            'type': 'string',
            'prefix': '#',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, token_a, token_b, token_c, targets,
                 include_image=True, **kwargs):
        """
        Initialize Slack Object
        """
        super(NotifySlack, self).__init__(**kwargs)

        if not token_a:
            msg = 'The first API token is not specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not token_b:
            msg = 'The second API token is not specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not token_c:
            msg = 'The third API token is not specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_TOKEN_A.match(token_a.strip()):
            msg = 'The first API token specified ({}) is invalid.'\
                .format(token_a)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The token associated with the account
        self.token_a = token_a.strip()

        if not VALIDATE_TOKEN_B.match(token_b.strip()):
            msg = 'The second API token specified ({}) is invalid.'\
                .format(token_b)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The token associated with the account
        self.token_b = token_b.strip()

        if not VALIDATE_TOKEN_C.match(token_c.strip()):
            msg = 'The third API token specified ({}) is invalid.'\
                .format(token_c)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The token associated with the account
        self.token_c = token_c.strip()

        if not self.user:
            self.logger.warning(
                'No user was specified; using "%s".' % self.app_id)

        # Build list of channels
        self.channels = parse_list(targets)
        if len(self.channels) == 0:
            # No problem; the webhook is smart enough to just notify the
            # channel it was created for; adding 'None' is just used as
            # a flag lower to not set the channels
            self.channels.append(None)

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

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
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

        # prepare JSON Object
        payload = {
            'username': self.user if self.user else self.app_id,
            # Use Markdown language
            'mrkdwn': (self.notify_format == NotifyFormat.MARKDOWN),
            'attachments': [{
                'title': title,
                'text': body,
                'color': self.color(notify_type),
                # Time
                'ts': time(),
                'footer': self.app_id,
            }],
        }

        # Create a copy of the channel list
        channels = list(self.channels)
        while len(channels):
            channel = channels.pop(0)

            if channel is not None:
                # Channel over-ride was specified
                if not IS_VALID_TARGET_RE.match(channel):
                    self.logger.warning(
                        "The specified target {} is invalid;"
                        "skipping.".format(channel))

                    # Mark our failure
                    has_error = True
                    continue

                if len(channel) > 1 and channel[0] == '+':
                    # Treat as encoded id if prefixed with a +
                    payload['channel'] = channel[1:]

                elif len(channel) > 1 and channel[0] == '@':
                    # Treat @ value 'as is'
                    payload['channel'] = channel

                else:
                    # Prefix with channel hash tag
                    payload['channel'] = '#%s' % channel

            # Acquire our to-be footer icon if configured to do so
            image_url = None if not self.include_image \
                else self.image_url(notify_type)

            if image_url:
                payload['attachments'][0]['footer_icon'] = image_url

            self.logger.debug('Slack POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Slack Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifySlack.http_response_code_lookup(
                            r.status_code, SLACK_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send Slack notification{}: '
                        '{}{}error={}.'.format(
                            ' to {}'.format(channel)
                            if channel is not None else '',
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent Slack notification{}.'.format(
                            ' to {}'.format(channel)
                            if channel is not None else ''))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending Slack '
                    'notification{}.'.format(
                        ' to {}'.format(channel)
                        if channel is not None else ''))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'image': 'yes' if self.include_image else 'no',
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        # Determine if there is a botname present
        botname = ''
        if self.user:
            botname = '{botname}@'.format(
                botname=NotifySlack.quote(self.user, safe=''),
            )

        return '{schema}://{botname}{token_a}/{token_b}/{token_c}/{targets}/'\
            '?{args}'.format(
                schema=self.secure_protocol,
                botname=botname,
                token_a=NotifySlack.quote(self.token_a, safe=''),
                token_b=NotifySlack.quote(self.token_b, safe=''),
                token_c=NotifySlack.quote(self.token_c, safe=''),
                targets='/'.join(
                    [NotifySlack.quote(x, safe='') for x in self.channels]),
                args=NotifySlack.urlencode(args),
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

        # Get unquoted entries
        entries = NotifySlack.split_path(results['fullpath'])

        # The first token is stored in the hostname
        results['token_a'] = NotifySlack.unquote(results['host'])

        # Now fetch the remaining tokens
        try:
            results['token_b'] = entries.pop(0)

        except IndexError:
            # We're done
            results['token_b'] = None

        try:
            results['token_c'] = entries.pop(0)

        except IndexError:
            # We're done
            results['token_c'] = None

        # assign remaining entries to the channels we wish to notify
        results['targets'] = entries

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += [x for x in filter(
                bool, CHANNEL_LIST_DELIM.split(
                    NotifySlack.unquote(results['qsd']['to'])))]

        # Get Image
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://hooks.slack.com/services/TOKEN_A/TOKEN_B/TOKEN_C
        """

        result = re.match(
            r'^https?://hooks\.slack\.com/services/'
            r'(?P<token_a>[A-Z0-9]{9})/'
            r'(?P<token_b>[A-Z0-9]{9})/'
            r'(?P<token_c>[A-Z0-9]{24})/?'
            r'(?P<args>\?[.+])?$', url, re.I)

        if result:
            return NotifySlack.parse_url(
                '{schema}://{token_a}/{token_b}/{token_c}/{args}'.format(
                    schema=NotifySlack.secure_protocol,
                    token_a=result.group('token_a'),
                    token_b=result.group('token_b'),
                    token_c=result.group('token_c'),
                    args='' if not result.group('args')
                    else result.group('args')))

        return None
