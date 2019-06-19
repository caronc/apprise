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

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _

# Flag used as a placeholder to sending to all devices
PUSHOVER_SEND_TO_ALL = 'ALL_DEVICES'

# Used to validate API Key
VALIDATE_TOKEN = re.compile(r'^[a-z0-9]{30}$', re.I)

# Used to detect a User and/or Group
VALIDATE_USER_KEY = re.compile(r'^[a-z0-9]{30}$', re.I)

# Used to detect a User and/or Group
VALIDATE_DEVICE = re.compile(r'^[a-z0-9_]{1,25}$', re.I)


# Priorities
class PushoverPriority(object):
    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


# Sounds
class PushoverSound(object):
    PUSHOVER = 'pushover'
    BIKE = 'bike'
    BUGLE = 'bugle'
    CASHREGISTER = 'cashregister'
    CLASSICAL = 'classical'
    COSMIC = 'cosmic'
    FALLING = 'falling'
    GAMELAN = 'gamelan'
    INCOMING = 'incoming'
    INTERMISSION = 'intermission'
    MAGIC = 'magic'
    MECHANICAL = 'mechanical'
    PIANOBAR = 'pianobar'
    SIREN = 'siren'
    SPACEALARM = 'spacealarm'
    TUGBOAT = 'tugboat'
    ALIEN = 'alien'
    CLIMB = 'climb'
    PERSISTENT = 'persistent'
    ECHO = 'echo'
    UPDOWN = 'updown'
    NONE = 'none'


PUSHOVER_SOUNDS = (
    PushoverSound.PUSHOVER,
    PushoverSound.BIKE,
    PushoverSound.BUGLE,
    PushoverSound.CASHREGISTER,
    PushoverSound.CLASSICAL,
    PushoverSound.COSMIC,
    PushoverSound.FALLING,
    PushoverSound.GAMELAN,
    PushoverSound.INCOMING,
    PushoverSound.INTERMISSION,
    PushoverSound.MAGIC,
    PushoverSound.MECHANICAL,
    PushoverSound.PIANOBAR,
    PushoverSound.SIREN,
    PushoverSound.SPACEALARM,
    PushoverSound.TUGBOAT,
    PushoverSound.ALIEN,
    PushoverSound.CLIMB,
    PushoverSound.PERSISTENT,
    PushoverSound.ECHO,
    PushoverSound.UPDOWN,
    PushoverSound.NONE,
)

PUSHOVER_PRIORITIES = (
    PushoverPriority.LOW,
    PushoverPriority.MODERATE,
    PushoverPriority.NORMAL,
    PushoverPriority.HIGH,
    PushoverPriority.EMERGENCY,
)

# Extend HTTP Error Messages
PUSHOVER_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}


class NotifyPushover(NotifyBase):
    """
    A wrapper for Pushover Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushover'

    # The services URL
    service_url = 'https://pushover.net/'

    # All pushover requests are secure
    secure_protocol = 'pover'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushover'

    # Pushover uses the http protocol with JSON requests
    notify_url = 'https://api.pushover.net/1/messages.json'

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 512

    # Default Pushover sound
    default_pushover_sound = PushoverSound.PUSHOVER

    # Define object templates
    templates = (
        '{schema}://{user_key}@{token}',
        '{schema}://{user_key}@{token}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user_key': {
            'name': _('User Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'[a-z0-9]{30}', 'i'),
            'map_to': 'user',
        },
        'token': {
            'name': _('Access Token'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'[a-z0-9]{30}', 'i'),
        },
        'target_device': {
            'name': _('Target Device'),
            'type': 'string',
            'regex': (r'[a-z0-9_]{1,25}', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'values': PUSHOVER_PRIORITIES,
            'default': PushoverPriority.NORMAL,
        },
        'sound': {
            'name': _('Sound'),
            'type': 'string',
            'regex': (r'[a-z]{1,12}', 'i'),
            'default': PushoverSound.PUSHOVER,
        },
        'retry': {
            'name': _('Retry'),
            'type': 'int',
            'min': 30,
            'default': 900,  # 15 minutes
        },
        'expire': {
            'name': _('Expire'),
            'type': 'int',
            'min': 0,
            'max': 10800,
            'default': 3600,  # 1 hour
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, token, targets=None, priority=None, sound=None,
                 retry=None, expire=None,
                 **kwargs):
        """
        Initialize Pushover Object
        """
        super(NotifyPushover, self).__init__(**kwargs)

        try:
            # The token associated with the account
            self.token = token.strip()

        except AttributeError:
            # Token was None
            msg = 'No API Token was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_TOKEN.match(self.token):
            msg = 'The API Token specified (%s) is invalid.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.targets = parse_list(targets)
        if len(self.targets) == 0:
            self.targets = (PUSHOVER_SEND_TO_ALL, )

        # Setup our sound
        self.sound = NotifyPushover.default_pushover_sound \
            if not isinstance(sound, six.string_types) else sound.lower()
        if self.sound and self.sound not in PUSHOVER_SOUNDS:
            msg = 'The sound specified ({}) is invalid.'.format(sound)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Priority of the message
        if priority not in PUSHOVER_PRIORITIES:
            self.priority = PushoverPriority.NORMAL

        else:
            self.priority = priority

        # The following are for emergency alerts
        if self.priority == PushoverPriority.EMERGENCY:

            # How often to resend notification, in seconds
            self.retry = NotifyPushover.template_args['retry']['default']
            try:
                self.retry = int(retry)
            except (ValueError, TypeError):
                # Do nothing
                pass

            # How often to resend notification, in seconds
            self.expire = NotifyPushover.template_args['expire']['default']
            try:
                self.expire = int(expire)
            except (ValueError, TypeError):
                # Do nothing
                pass

            if self.retry < 30:
                msg = 'Retry must be at least 30.'
                self.logger.warning(msg)
                raise TypeError(msg)
            if self.expire < 0 or self.expire > 10800:
                msg = 'Expire has a max value of at most 10800 seconds.'
                self.logger.warning(msg)
                raise TypeError(msg)

        if not self.user:
            msg = 'No user key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_USER_KEY.match(self.user):
            msg = 'The user key specified (%s) is invalid.' % self.user
            self.logger.warning(msg)
            raise TypeError(msg)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Pushover Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        auth = (self.token, '')

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the devices list
        devices = list(self.targets)
        while len(devices):
            device = devices.pop(0)

            if VALIDATE_DEVICE.match(device) is None:
                self.logger.warning(
                    'The device specified (%s) is invalid.' % device,
                )

                # Mark our failure
                has_error = True
                continue

            # prepare JSON Object
            payload = {
                'token': self.token,
                'user': self.user,
                'priority': str(self.priority),
                'title': title,
                'message': body,
                'device': device,
                'sound': self.sound,
            }

            if self.priority == PushoverPriority.EMERGENCY:
                payload.update({'retry': self.retry, 'expire': self.expire})

            self.logger.debug('Pushover POST URL: %s (cert_verify=%r)' % (
                self.notify_url, self.verify_certificate,
            ))
            self.logger.debug('Pushover Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    data=payload,
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyPushover.http_response_code_lookup(
                            r.status_code, PUSHOVER_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send Pushover notification to {}: '
                        '{}{}error={}.'.format(
                            device,
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
                        'Sent Pushover notification to %s.' % device)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending Pushover:%s ' % (
                        device) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        _map = {
            PushoverPriority.LOW: 'low',
            PushoverPriority.MODERATE: 'moderate',
            PushoverPriority.NORMAL: 'normal',
            PushoverPriority.HIGH: 'high',
            PushoverPriority.EMERGENCY: 'emergency',
        }

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'priority':
                _map[PushoverPriority.NORMAL] if self.priority not in _map
                else _map[self.priority],
            'verify': 'yes' if self.verify_certificate else 'no',
        }
        # Only add expire and retry for emergency messages,
        # pushover ignores for all other priorities
        if self.priority == PushoverPriority.EMERGENCY:
            args.update({'expire': self.expire, 'retry': self.retry})

        # Escape our devices
        devices = '/'.join([NotifyPushover.quote(x, safe='')
                            for x in self.targets])

        if devices == PUSHOVER_SEND_TO_ALL:
            # keyword is reserved for internal usage only; it's safe to remove
            # it from the devices list
            devices = ''

        return '{schema}://{auth}{token}/{devices}/?{args}'.format(
            schema=self.secure_protocol,
            auth='' if not self.user
                 else '{user}@'.format(
                     user=NotifyPushover.quote(self.user, safe='')),
            token=NotifyPushover.quote(self.token, safe=''),
            devices=devices,
            args=NotifyPushover.urlencode(args))

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

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            _map = {
                'l': PushoverPriority.LOW,
                'm': PushoverPriority.MODERATE,
                'n': PushoverPriority.NORMAL,
                'h': PushoverPriority.HIGH,
                'e': PushoverPriority.EMERGENCY,
            }
            try:
                results['priority'] = \
                    _map[results['qsd']['priority'][0].lower()]

            except KeyError:
                # No priority was set
                pass

        # Retrieve all of our targets
        results['targets'] = NotifyPushover.split_path(results['fullpath'])

        # Get the sound
        if 'sound' in results['qsd'] and len(results['qsd']['sound']):
            results['sound'] = \
                NotifyPushover.unquote(results['qsd']['sound'])

        # Get expire and retry
        if 'expire' in results['qsd'] and len(results['qsd']['expire']):
            results['expire'] = results['qsd']['expire']
        if 'retry' in results['qsd'] and len(results['qsd']['retry']):
            results['retry'] = results['qsd']['retry']

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPushover.parse_list(results['qsd']['to'])

        # Token
        results['token'] = NotifyPushover.unquote(results['host'])

        return results
