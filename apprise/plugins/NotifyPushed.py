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
from .NotifyBase import HTTP_ERROR_MAP
from ..utils import compat_is_basestring

# Used to detect and parse channels
IS_CHANNEL = re.compile(r'^#(?P<name>[A-Za-z0-9]+)$')

# Used to detect and parse a users push id
IS_USER_PUSHED_ID = re.compile(r'^@(?P<name>[A-Za-z0-9]+)$')

# Used to break apart list of potential tags by their delimiter
# into a usable list.
LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


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

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 140

    def __init__(self, app_key, app_secret, recipients=None, **kwargs):
        """
        Initialize Pushed Object

        """
        super(NotifyPushed, self).__init__(**kwargs)

        if not app_key:
            raise TypeError(
                'An invalid Application Key was specified.'
            )

        if not app_secret:
            raise TypeError(
                'An invalid Application Secret was specified.'
            )

        # Initialize channel list
        self.channels = list()

        # Initialize user list
        self.users = list()

        if recipients is None:
            recipients = []

        elif compat_is_basestring(recipients):
            recipients = [x for x in filter(bool, LIST_DELIM.split(
                recipients,
            ))]

        elif not isinstance(recipients, (set, tuple, list)):
            raise TypeError(
                'An invalid receipient list was specified.'
            )

        # Validate recipients and drop bad ones:
        for recipient in recipients:
            result = IS_CHANNEL.match(recipient)
            if result:
                # store valid device
                self.channels.append(result.group('name'))
                continue

            result = IS_USER_PUSHED_ID.match(recipient)
            if result:
                # store valid room
                self.users.append(result.group('name'))
                continue

            self.logger.warning(
                'Dropped invalid channel/userid '
                '(%s) specified.' % recipient,
            )

        # Store our data
        self.app_key = app_key
        self.app_secret = app_secret

        return

    def notify(self, title, body, notify_type, **kwargs):
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
            return self.send_notification(
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

            if not self.send_notification(
                    payload=_payload, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

            if len(channels) + len(users) > 0:
                # Prevent thrashing requests
                self.throttle()

        # Copy our payload
        _payload = dict(payload)
        _payload['target_type'] = 'pushed_id'

        # Send all our defined User Pushed ID's
        while len(users):
            # Get User's Pushed ID
            _payload['pushed_id'] = users.pop(0)
            if not self.send_notification(
                    payload=_payload, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

            if len(users) > 0:
                # Prevent thrashing requests
                self.throttle()

        return not has_error

    def send_notification(self, payload, notify_type, **kwargs):
        """
        A lower level call that directly pushes a payload to the Pushed
        Notification servers.  This should never be called directly; it is
        referenced automatically through the notify() function.
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        self.logger.debug('Pushed POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Pushed Payload: %s' % str(payload))
        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Pushed notification: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send Pushed notification '
                        '(error=%s).' % r.status_code)

                self.logger.debug('Response Details: %s' % r.raw.read())

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
        }

        return '{schema}://{app_key}/{app_secret}/{targets}/?{args}'.format(
            schema=self.secure_protocol,
            app_key=self.quote(self.app_key, safe=''),
            app_secret=self.quote(self.app_secret, safe=''),
            targets='/'.join(
                [self.quote(x) for x in chain(
                    # Channels are prefixed with a pound/hashtag symbol
                    ['#{}'.format(x) for x in self.channels],
                    # Users are prefixed with an @ symbol
                    ['@{}'.format(x) for x in self.users],
                )]),
            args=self.urlencode(args))

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
        app_key = results['host']

        # Initialize our recipients
        recipients = None

        # Now fetch the remaining tokens
        try:
            app_secret = \
                [x for x in filter(bool, NotifyBase.split_path(
                    results['fullpath']))][0]

        except (ValueError, AttributeError, IndexError):
            # Force some bad values that will get caught
            # in parsing later
            app_secret = None
            app_key = None

        # Get our recipients
        recipients = \
            [x for x in filter(bool, NotifyBase.split_path(
                results['fullpath']))][1:]

        results['app_key'] = app_key
        results['app_secret'] = app_secret
        results['recipients'] = recipients

        return results
