# -*- encoding: utf-8 -*-
#
# Notify Rocket.Chat Notify Wrapper
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
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

import requests
import json
import re

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import HTTP_ERROR_MAP

IS_CHANNEL = re.compile(r'^#(?P<name>[A-Za-z0-9]+)$')
IS_ROOM_ID = re.compile(r'^(?P<name>[A-Za-z0-9]+)$')

# Extend HTTP Error Messages
RC_HTTP_ERROR_MAP = dict(HTTP_ERROR_MAP.items() + {
    400: 'Channel/RoomId is wrong format, or missing from server.',
    401: 'Authentication tokens provided is invalid or missing.',
}.items())

# Used to break apart list of potential tags by their delimiter
# into a usable list.
LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class NotifyRocketChat(NotifyBase):
    """
    A wrapper for Notify Rocket.Chat Notifications
    """

    # The default protocol
    PROTOCOL = 'rocket'

    # The default secure protocol
    SECURE_PROTOCOL = 'rockets'

    def __init__(self, recipients=None, **kwargs):
        """
        Initialize Notify Rocket.Chat Object
        """
        super(NotifyRocketChat, self).__init__(
            title_maxlen=200, body_maxlen=32768,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

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

        # Initialize room_id list
        self.room_ids = list()

        if recipients is None:
            recipients = []

        elif isinstance(recipients, basestring):
            recipients = filter(bool, LIST_DELIM.split(
                recipients,
            ))

        elif not isinstance(recipients, (tuple, list)):
            recipients = []

        # Validate recipients and drop bad ones:
        for recipient in recipients:
            result = IS_CHANNEL.match(recipient)
            if result:
                # store valid device
                self.channels.append(result.group('name'))
                continue

            result = IS_ROOM_ID.match(recipient)
            if result:
                # store valid room_id
                self.channels.append(result.group('name'))
                continue

            self.logger.warning(
                'Dropped invalid channel/room_id ' +
                '(%s) specified.' % recipient,
            )

        if len(self.room_ids) == 0 and len(self.channels) == 0:
            raise TypeError(
                'No Rocket.Chat room_id and/or channels specified to notify.'
            )

        # Used to track token headers upon authentication (if successful)
        self.headers = {}

        # Track whether we authenticated okay
        self.authenticated = self.login()

        if not self.authenticated:
            raise TypeError(
                'Authentication to Rocket.Chat server failed.'
            )

    def _notify(self, title, body, notify_type, **kwargs):
        """
        wrapper to send_notification since we can alert more then one channel
        """

        # Prepare our message
        text = '*%s*\r\n%s' % (title.replace('*', '\*'), body)

        # Send all our defined channels
        for channel in self.channels:
            self.send_notification({
                'text': text,
                'channel': channel,
            }, notify_type=notify_type, **kwargs)

        # Send all our defined room id's
        for room_id in self.room_ids:
            self.send_notification({
                'text': text,
                'roomId': room_id,
            }, notify_type=notify_type, **kwargs)

    def send_notification(self, payload, notify_type, **kwargs):
        """
        Perform Notify Rocket.Chat Notification
        """

        if not self.authenticated:
            # We couldn't authenticate; we're done
            return False

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
                        'Failed to send Rocket.Chat notification: ' +
                        '%s (error=%s).' % (
                            RC_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))
                except IndexError:
                    self.logger.warning(
                        'Failed to send Rocket.Chat notification ' +
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

            else:
                self.logger.debug('Rocket.Chat Server Response: %s.' % r.text)
                self.logger.info('Sent Rocket.Chat notification.')

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending Rocket.Chat ' +
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
                        'Failed to authenticate with Rocket.Chat server: ' +
                        '%s (error=%s).' % (
                            RC_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))
                except IndexError:
                    self.logger.warning(
                        'Failed to authenticate with Rocket.Chat server ' +
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

            else:
                self.logger.debug('Rocket.Chat authentication successful')
                response = json.loads(r.text)
                if response.get('status') != "success":
                    self.logger.warning(
                        'Could not authenticate with Rocket.Chat server.')
                    return False

                # Set our headers for further communication
                self.headers['X-Auth-Token'] = \
                    response.get('data').get('authToken')
                self.headers['X-User-Id'] = \
                    response.get('data').get('userId')

                # We're authenticated now
                self.authenticated = True

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured authenticating to the ' +
                'Rocket.Chat server.')
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def logout(self):
        """
        logout of our server
        """
        if not self.authenticated:
            # Nothing to do
            return True

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
                        'Failed to log off Rocket.Chat server: ' +
                        '%s (error=%s).' % (
                            RC_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))
                except IndexError:
                    self.logger.warning(
                        'Failed to log off Rocket.Chat server ' +
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

            else:
                self.logger.debug(
                    'Rocket.Chat log off successful; response %s.' % (
                        r.text))

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured logging off the ' +
                'Rocket.Chat server')
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        # We're no longer authenticated now
        self.authenticated = False
        return True
