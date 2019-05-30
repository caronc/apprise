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
import six
import requests
from json import loads
from json import dumps
from itertools import chain

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _

IS_CHANNEL = re.compile(r'^#(?P<name>[A-Za-z0-9_-]+)$')
IS_USER = re.compile(r'^@(?P<name>[A-Za-z0-9._-]+)$')
IS_ROOM_ID = re.compile(r'^(?P<name>[A-Za-z0-9]+)$')

# Extend HTTP Error Messages
RC_HTTP_ERROR_MAP = {
    400: 'Channel/RoomId is wrong format, or missing from server.',
    401: 'Authentication tokens provided is invalid or missing.',
}

# Used to break apart list of potential tags by their delimiter
# into a usable list.
LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class RocketChatAuthMode(object):
    """
    The Chat Authentication mode is detected
    """
    # providing a webhook
    WEBHOOK = "webhook"

    # Providing a username and password (default)
    BASIC = "basic"


# Define our authentication modes
ROCKETCHAT_AUTH_MODES = (
    RocketChatAuthMode.WEBHOOK,
    RocketChatAuthMode.BASIC,
)


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

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # The title is not used
    title_maxlen = 0

    # The maximum size of the message
    body_maxlen = 1000

    # Default to markdown
    notify_format = NotifyFormat.MARKDOWN

    # Define object templates
    templates = (
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{webhook}@{host}',
        '{schema}://{webhook}@{host}:{port}',
        '{schema}://{webhook}@{host}/{targets}',
        '{schema}://{webhook}@{host}:{port}/{targets}',
    )

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
        'user': {
            'name': _('Username'),
            'type': 'string',
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
        'webhook': {
            'name': _('Webhook'),
            'type': 'string',
        },
        'target_channel': {
            'name': _('Target Channel'),
            'type': 'string',
            'prefix': '#',
            'map_to': 'targets',
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'target_room': {
            'name': _('Target Room ID'),
            'type': 'string',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'mode': {
            'name': _('Webhook Mode'),
            'type': 'choice:string',
            'values': ROCKETCHAT_AUTH_MODES,
        },
        'avatar': {
            'name': _('Use Avatar'),
            'type': 'bool',
            'default': True,
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, webhook=None, targets=None, mode=None, avatar=True,
                 **kwargs):
        """
        Initialize Notify Rocket.Chat Object
        """
        super(NotifyRocketChat, self).__init__(**kwargs)

        # Set our schema
        self.schema = 'https' if self.secure else 'http'

        # Prepare our URL
        self.api_url = '%s://%s' % (self.schema, self.host)

        if isinstance(self.port, int):
            self.api_url += ':%d' % self.port

        # Initialize channels list
        self.channels = list()

        # Initialize room list
        self.rooms = list()

        # Initialize user list (webhook only)
        self.users = list()

        # Assign our webhook (if defined)
        self.webhook = webhook

        # Place an avatar image to associate with our content
        self.avatar = avatar

        # Used to track token headers upon authentication (if successful)
        # This is only used if not on webhook mode
        self.headers = {}

        # Authentication mode
        self.mode = None \
            if not isinstance(mode, six.string_types) \
            else mode.lower()

        if self.mode and self.mode not in ROCKETCHAT_AUTH_MODES:
            msg = 'The authentication mode specified ({}) is invalid.'.format(
                mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Detect our mode if it wasn't specified
        if not self.mode:
            if self.webhook is not None:
                # Just a username was specified, we treat this as a webhook
                self.mode = RocketChatAuthMode.WEBHOOK
            else:
                self.mode = RocketChatAuthMode.BASIC

        if self.mode == RocketChatAuthMode.BASIC \
                and not (self.user and self.password):
            # Username & Password is required for Rocket Chat to work
            msg = 'No Rocket.Chat user/pass combo was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        elif self.mode == RocketChatAuthMode.WEBHOOK and not self.webhook:
            msg = 'No Rocket.Chat Incoming Webhook was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate recipients and drop bad ones:
        for recipient in parse_list(targets):
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

            result = IS_USER.match(recipient)
            if result:
                # store valid room
                self.users.append(result.group('name'))
                continue

            self.logger.warning(
                'Dropped invalid channel/room/user '
                '({}) specified.'.format(recipient),
            )

        if self.mode == RocketChatAuthMode.BASIC and \
                len(self.rooms) == 0 and len(self.channels) == 0:
            msg = 'No Rocket.Chat room and/or channels specified to notify.'
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
            'avatar': 'yes' if self.avatar else 'no',
            'mode': self.mode,
        }

        # Determine Authentication
        if self.mode == RocketChatAuthMode.BASIC:
            auth = '{user}:{password}@'.format(
                user=NotifyRocketChat.quote(self.user, safe=''),
                password=NotifyRocketChat.quote(self.password, safe=''),
            )
        else:
            auth = '{user}{webhook}@'.format(
                user='{}:'.format(NotifyRocketChat.quote(self.user, safe=''))
                if self.user else '',
                webhook=NotifyRocketChat.quote(self.webhook, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{targets}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyRocketChat.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='/'.join(
                [NotifyRocketChat.quote(x, safe='') for x in chain(
                    # Channels are prefixed with a pound/hashtag symbol
                    ['#{}'.format(x) for x in self.channels],
                    # Rooms are as is
                    self.rooms,
                    # Users
                    ['@{}'.format(x) for x in self.users],
                )]),
            args=NotifyRocketChat.urlencode(args),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        wrapper to _send since we can alert more then one channel
        """

        # Call the _send_ function applicable to whatever mode we're in
        # - calls _send_webhook_notification if the mode variable is set
        # - calls _send_basic_notification if the mode variable is not set
        return getattr(self, '_send_{}_notification'.format(self.mode))(
            body=body, title=title, notify_type=notify_type, **kwargs)

    def _send_webhook_notification(self, body, title='',
                                   notify_type=NotifyType.INFO, **kwargs):
        """
        Sends a webhook notification
        """

        # Our payload object
        payload = self._payload(body, title, notify_type)

        # Assemble our webhook URL
        path = 'hooks/{}'.format(self.webhook)

        # Build our list of channels/rooms/users (if any identified)
        targets = ['@{}'.format(u) for u in self.users]
        targets.extend(['#{}'.format(c) for c in self.channels])
        targets.extend(['{}'.format(r) for r in self.rooms])

        if len(targets) == 0:
            # We can take an early exit
            return self._send(
                payload, notify_type=notify_type, path=path, **kwargs)

        # Otherwise we want to iterate over each of the targets

        # Initiaize our error tracking
        has_error = False

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        while len(targets):
            # Retrieve our target
            target = targets.pop(0)

            # Assign our channel/room/user
            payload['channel'] = target

            if not self._send(
                    dumps(payload), notify_type=notify_type, path=path,
                    headers=headers, **kwargs):

                # toggle flag
                has_error = True

        return not has_error

    def _send_basic_notification(self, body, title='',
                                 notify_type=NotifyType.INFO, **kwargs):
        """
        Authenticates with the server using a user/pass combo for
        notifications.
        """
        # Track whether we authenticated okay

        if not self.login():
            return False

        # prepare JSON Object
        payload = self._payload(body, title, notify_type)

        # Initiaize our error tracking
        has_error = False

        # Create a copy of our channels to notify against
        channels = list(self.channels)
        _payload = payload.copy()
        while len(channels) > 0:
            # Get Channel
            channel = channels.pop(0)
            _payload['channel'] = channel

            if not self._send(
                    _payload, notify_type=notify_type, headers=self.headers,
                    **kwargs):

                # toggle flag
                has_error = True

        # Create a copy of our room id's to notify against
        rooms = list(self.rooms)
        _payload = payload.copy()
        while len(rooms):
            # Get Room
            room = rooms.pop(0)
            _payload['roomId'] = room

            if not self._send(
                    payload, notify_type=notify_type, headers=self.headers,
                    **kwargs):

                # toggle flag
                has_error = True

        # logout
        self.logout()

        return not has_error

    def _payload(self, body, title='', notify_type=NotifyType.INFO):
        """
        Prepares a payload object
        """
        # prepare JSON Object
        payload = {
            "text": body,
        }

        # apply our images if they're set to be displayed
        image_url = self.image_url(notify_type)
        if self.avatar:
            payload['avatar'] = image_url

        return payload

    def _send(self, payload, notify_type, path='api/v1/chat.postMessage',
              headers=None, **kwargs):
        """
        Perform Notify Rocket.Chat Notification
        """

        api_url = '{}/{}'.format(self.api_url, path)

        self.logger.debug('Rocket.Chat POST URL: %s (cert_verify=%r)' % (
            api_url, self.verify_certificate))
        self.logger.debug('Rocket.Chat Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                api_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyRocketChat.http_response_code_lookup(
                        r.status_code, RC_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Rocket.Chat {}:notification: '
                    '{}{}error={}.'.format(
                        self.mode,
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info(
                    'Sent Rocket.Chat {}:notification.'.format(self.mode))

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Rocket.Chat '
                '{}:notification.'.format(self.mode))
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

        api_url = '{}/{}'.format(self.api_url, 'api/v1/login')

        try:
            r = requests.post(
                api_url,
                data=payload,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyRocketChat.http_response_code_lookup(
                        r.status_code, RC_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to authenticate {} with Rocket.Chat: '
                    '{}{}error={}.'.format(
                        self.user,
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.debug('Rocket.Chat authentication successful')
                response = loads(r.content)
                if response.get('status') != "success":
                    self.logger.warning(
                        'Could not authenticate {} with Rocket.Chat.'.format(
                            self.user))
                    return False

                # Set our headers for further communication
                self.headers['X-Auth-Token'] = response.get(
                    'data', {'authToken': None}).get('authToken')
                self.headers['X-User-Id'] = response.get(
                    'data', {'userId': None}).get('userId')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured authenticating {} on '
                'Rocket.Chat.'.format(self.user))
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def logout(self):
        """
        logout of our server
        """

        api_url = '{}/{}'.format(self.api_url, 'api/v1/logout')

        try:
            r = requests.post(
                api_url,
                headers=self.headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyRocketChat.http_response_code_lookup(
                        r.status_code, RC_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to logoff {} from Rocket.Chat: '
                    '{}{}error={}.'.format(
                        self.user,
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.debug(
                    'Rocket.Chat log off successful; response %s.' % (
                        r.content))

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

        try:
            # Attempt to detect the webhook (if specified in the URL)
            # If no webhook is specified, then we just pass along as if nothing
            # happened. However if we do find a webhook, we want to rebuild our
            # URL without it since it conflicts with standard URLs. Support
            # %2F since that is a forward slash escaped

            # rocket://webhook@host
            # rocket://user:webhook@host
            match = re.match(
                r'^\s*(?P<schema>[^:]+://)((?P<user>[^:]+):)?'
                r'(?P<webhook>[a-z0-9]+(/|%2F)'
                r'[a-z0-9]+)\@(?P<url>.+)$', url, re.I)

        except TypeError:
            # Not a string
            return None

        if match:
            # Re-assemble our URL without the webhook
            url = '{schema}{user}{url}'.format(
                schema=match.group('schema'),
                user='{}@'.format(match.group('user'))
                if match.group('user') else '',
                url=match.group('url'),
            )

        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        if match:
            # store our webhook
            results['webhook'] = \
                NotifyRocketChat.unquote(match.group('webhook'))

            # Take on the password too in the event we're in basic mode
            # We do not unquote() as this is done at a later state
            results['password'] = match.group('webhook')

        # Apply our targets
        results['targets'] = NotifyRocketChat.split_path(results['fullpath'])

        # The user may have forced the mode
        if 'mode' in results['qsd'] and len(results['qsd']['mode']):
            results['mode'] = \
                NotifyRocketChat.unquote(results['qsd']['mode'])

        # avatar icon
        results['avatar'] = \
            parse_bool(results['qsd'].get('avatar', True))

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyRocketChat.parse_list(results['qsd']['to'])

        # The 'webhook' over-ride (if specified)
        if 'webhook' in results['qsd'] and len(results['qsd']['webhook']):
            results['webhook'] = \
                NotifyRocketChat.unquote(results['qsd']['webhook'])

        return results
