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
from json import loads
from itertools import chain

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..utils import compat_is_basestring

IS_CHANNEL = re.compile(r'^#(?P<name>[A-Za-z0-9]+)$')
IS_ROOM_ID = re.compile(r'^(?P<name>[A-Za-z0-9]+)$')

# Extend HTTP Error Messages
RC_HTTP_ERROR_MAP = HTTP_ERROR_MAP.copy()
RC_HTTP_ERROR_MAP.update({
    400: 'Channel/RoomId is wrong format, or missing from server.',
    401: 'Authentication tokens provided is invalid or missing.',
})

# Used to break apart list of potential tags by their delimiter
# into a usable list.
LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class NotifyRocketChat(NotifyBase):
    """
    A wrapper for Notify Rocket.Chat Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Rocket.Chat'

    # The services URL
    service_url = 'https://rocket.chat/'

    # The default protocol
    protocol = 'rocket'

    # The default secure protocol
    secure_protocol = 'rockets'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_rocketchat'

    # Defines the maximum allowable characters in the title
    title_maxlen = 200

    def __init__(self, recipients=None, **kwargs):
        """
        Initialize Notify Rocket.Chat Object
        """
        super(NotifyRocketChat, self).__init__(**kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        # Prepare our URL
        self.api_url = '%s://%s' % (self.schema, self.host)

        if isinstance(self.port, int):
            self.api_url += ':%d' % self.port

        self.api_url += '/api/v1/'

        # Initialize channels list
        self.channels = list()

        # Initialize room list
        self.rooms = list()

        if recipients is None:
            recipients = []

        elif compat_is_basestring(recipients):
            recipients = [x for x in filter(bool, LIST_DELIM.split(
                recipients,
            ))]

        elif not isinstance(recipients, (set, tuple, list)):
            recipients = []

        if not (self.user and self.password):
            # Username & Password is required for Rocket Chat to work
            raise TypeError(
                'No Rocket.Chat user/pass combo specified.'
            )

        # Validate recipients and drop bad ones:
        for recipient in recipients:
            result = IS_CHANNEL.match(recipient)
            if result:
                # store valid device
                self.channels.append(result.group('name'))
                continue

            result = IS_ROOM_ID.match(recipient)
            if result:
                # store valid room
                self.rooms.append(result.group('name'))
                continue

            self.logger.warning(
                'Dropped invalid channel/room '
                '(%s) specified.' % recipient,
            )

        if len(self.rooms) == 0 and len(self.channels) == 0:
            raise TypeError(
                'No Rocket.Chat room and/or channels specified to notify.'
            )

        # Used to track token headers upon authentication (if successful)
        self.headers = {}

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
        }

        # Determine Authentication
        auth = '{user}:{password}@'.format(
            user=self.quote(self.user, safe=''),
            password=self.quote(self.password, safe=''),
        )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{targets}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='/'.join(
                [self.quote(x) for x in chain(
                    # Channels are prefixed with a pound/hashtag symbol
                    ['#{}'.format(x) for x in self.channels],
                    # Rooms are as is
                    self.rooms,
                )]),
            args=self.urlencode(args),
        )

    def notify(self, title, body, notify_type, **kwargs):
        """
        wrapper to send_notification since we can alert more then one channel
        """

        # Track whether we authenticated okay

        if not self.login():
            return False

        # Prepare our message
        text = '*%s*\r\n%s' % (title.replace('*', '\\*'), body)

        # Initiaize our error tracking
        has_error = False

        # Create a copy of our rooms and channels to notify against
        channels = list(self.channels)
        rooms = list(self.rooms)

        while len(channels) > 0:
            # Get Channel
            channel = channels.pop(0)

            if not self.send_notification(
                    {
                        'text': text,
                        'channel': channel,
                    }, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

            if len(channels) + len(rooms) > 0:
                # Prevent thrashing requests
                self.throttle()

        # Send all our defined room id's
        while len(rooms):
            # Get Room
            room = rooms.pop(0)

            if not self.send_notification(
                    {
                        'text': text,
                        'roomId': room,
                    }, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

            if len(rooms) > 0:
                # Prevent thrashing requests
                self.throttle()

        # logout
        self.logout()

        return not has_error

    def send_notification(self, payload, notify_type, **kwargs):
        """
        Perform Notify Rocket.Chat Notification
        """

        self.logger.debug('Rocket.Chat POST URL: %s (cert_verify=%r)' % (
            self.api_url + 'chat.postMessage', self.verify_certificate,
        ))
        self.logger.debug('Rocket.Chat Payload: %s' % str(payload))
        try:
            r = requests.post(
                self.api_url + 'chat.postMessage',
                data=payload,
                headers=self.headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Rocket.Chat notification: '
                        '%s (error=%s).' % (
                            RC_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send Rocket.Chat notification '
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

            else:
                self.logger.debug('Rocket.Chat Server Response: %s.' % r.text)
                self.logger.info('Sent Rocket.Chat notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Rocket.Chat '
                'notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def login(self):
        """
        login to our server

        """
        payload = {
            'username': self.user,
            'password': self.password,
        }

        try:
            r = requests.post(
                self.api_url + 'login',
                data=payload,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to authenticate with Rocket.Chat server: '
                        '%s (error=%s).' % (
                            RC_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to authenticate with Rocket.Chat server '
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

            else:
                self.logger.debug('Rocket.Chat authentication successful')
                response = loads(r.text)
                if response.get('status') != "success":
                    self.logger.warning(
                        'Could not authenticate with Rocket.Chat server.')
                    return False

                # Set our headers for further communication
                self.headers['X-Auth-Token'] = response.get(
                    'data', {'authToken': None}).get('authToken')
                self.headers['X-User-Id'] = response.get(
                    'data', {'userId': None}).get('userId')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured authenticating to the '
                'Rocket.Chat server.')
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def logout(self):
        """
        logout of our server
        """
        try:
            r = requests.post(
                self.api_url + 'logout',
                headers=self.headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to log off Rocket.Chat server: '
                        '%s (error=%s).' % (
                            RC_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to log off Rocket.Chat server '
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

            else:
                self.logger.debug(
                    'Rocket.Chat log off successful; response %s.' % (
                        r.text))

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured logging off the '
                'Rocket.Chat server')
            self.logger.debug('Socket Exception: %s' % str(e))
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
        results['recipients'] = NotifyBase.unquote(results['fullpath'])

        return results
