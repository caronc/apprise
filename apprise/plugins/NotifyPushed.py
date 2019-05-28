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

import re
import requests
from json import dumps
from itertools import chain

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _

# Used to detect and parse channels
IS_CHANNEL = re.compile(r'^#(?P<name>[A-Za-z0-9]+)$')

# Used to detect and parse a users push id
IS_USER_PUSHED_ID = re.compile(r'^@(?P<name>[A-Za-z0-9]+)$')


class NotifyPushed(NotifyBase):
    """
    A wrapper to Pushed Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushed'

    # The services URL
    service_url = 'https://pushed.co/'

    # The default secure protocol
    secure_protocol = 'pushed'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushed'

    # Pushed uses the http protocol with JSON requests
    notify_url = 'https://api.pushed.co/1/push'

    # A title can not be used for Pushed Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 140

    # Define object templates
    templates = (
        '{schema}://{app_key}/{app_secret}',
        '{schema}://{app_key}/{app_secret}@{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'app_key': {
            'name': _('Application Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'app_secret': {
            'name': _('Application Secret'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_user': {
            'name': _('Target User'),
            'prefix': '@',
            'type': 'string',
            'map_to': 'targets',
        },
        'target_channel': {
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
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, app_key, app_secret, targets=None, **kwargs):
        """
        Initialize Pushed Object

        """
        super(NotifyPushed, self).__init__(**kwargs)

        if not app_key:
            msg = 'An invalid Application Key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not app_secret:
            msg = 'An invalid Application Secret was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Initialize channel list
        self.channels = list()

        # Initialize user list
        self.users = list()

        # Validate recipients and drop bad ones:
        for target in parse_list(targets):
            result = IS_CHANNEL.match(target)
            if result:
                # store valid device
                self.channels.append(result.group('name'))
                continue

            result = IS_USER_PUSHED_ID.match(target)
            if result:
                # store valid room
                self.users.append(result.group('name'))
                continue

            self.logger.warning(
                'Dropped invalid channel/userid '
                '(%s) specified.' % target,
            )

        # Store our data
        self.app_key = app_key
        self.app_secret = app_secret

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Pushed Notification
        """

        # Initiaize our error tracking
        has_error = False

        # prepare JSON Object
        payload = {
            'app_key': self.app_key,
            'app_secret': self.app_secret,
            'target_type': 'app',
            'content': body,
        }

        # So the logic is as follows:
        #  - if no user/channel was specified, then we just simply notify the
        #    app.
        #  - if there are user/channels specified, then we only alert them
        #    while respecting throttle limits (in the event there are a lot of
        #    entries.

        if len(self.channels) + len(self.users) == 0:
            # Just notify the app
            return self._send(
                payload=payload, notify_type=notify_type, **kwargs)

        # If our code reaches here, we want to target channels and users (by
        # their Pushed_ID instead...

        # Generate a copy of our original list
        channels = list(self.channels)
        users = list(self.users)

        # Copy our payload
        _payload = dict(payload)
        _payload['target_type'] = 'channel'

        while len(channels) > 0:
            # Get Channel
            _payload['target_alias'] = channels.pop(0)

            if not self._send(
                    payload=_payload, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

        # Copy our payload
        _payload = dict(payload)
        _payload['target_type'] = 'pushed_id'

        # Send all our defined User Pushed ID's
        while len(users):
            # Get User's Pushed ID
            _payload['pushed_id'] = users.pop(0)

            if not self._send(
                    payload=_payload, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

        return not has_error

    def _send(self, payload, notify_type, **kwargs):
        """
        A lower level call that directly pushes a payload to the Pushed
        Notification servers.  This should never be called directly; it is
        referenced automatically through the send() function.
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        self.logger.debug('Pushed POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Pushed Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyPushed.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Pushed notification:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Pushed notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Pushed notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

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

        return '{schema}://{app_key}/{app_secret}/{targets}/?{args}'.format(
            schema=self.secure_protocol,
            app_key=NotifyPushed.quote(self.app_key, safe=''),
            app_secret=NotifyPushed.quote(self.app_secret, safe=''),
            targets='/'.join(
                [NotifyPushed.quote(x) for x in chain(
                    # Channels are prefixed with a pound/hashtag symbol
                    ['#{}'.format(x) for x in self.channels],
                    # Users are prefixed with an @ symbol
                    ['@{}'.format(x) for x in self.users],
                )]),
            args=NotifyPushed.urlencode(args))

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
        app_key = NotifyPushed.unquote(results['host'])

        entries = NotifyPushed.split_path(results['fullpath'])
        # Now fetch the remaining tokens
        try:
            app_secret = entries.pop(0)

        except IndexError:
            # Force some bad values that will get caught
            # in parsing later
            app_secret = None
            app_key = None

        # Get our recipients (based on remaining entries)
        results['targets'] = entries

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPushed.parse_list(results['qsd']['to'])

        results['app_key'] = app_key
        results['app_secret'] = app_secret

        return results
