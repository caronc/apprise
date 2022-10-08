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

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..common import NotifyFormat
from ..conversion import convert_between
from ..utils import parse_list
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _
from ..attachment.AttachBase import AttachBase

# Flag used as a placeholder to sending to all devices
PUSHOVER_SEND_TO_ALL = 'ALL_DEVICES'

# Used to detect a Device
VALIDATE_DEVICE = re.compile(r'^[a-z0-9_]{1,25}$', re.I)


# Priorities
class PushoverPriority:
    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


# Sounds
class PushoverSound:
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

PUSHOVER_PRIORITIES = {
    # Note: This also acts as a reverse lookup mapping
    PushoverPriority.LOW: 'low',
    PushoverPriority.MODERATE: 'moderate',
    PushoverPriority.NORMAL: 'normal',
    PushoverPriority.HIGH: 'high',
    PushoverPriority.EMERGENCY: 'emergency',
}

PUSHOVER_PRIORITY_MAP = {
    # Maps against string 'low'
    'l': PushoverPriority.LOW,
    # Maps against string 'moderate'
    'm': PushoverPriority.MODERATE,
    # Maps against string 'normal'
    'n': PushoverPriority.NORMAL,
    # Maps against string 'high'
    'h': PushoverPriority.HIGH,
    # Maps against string 'emergency'
    'e': PushoverPriority.EMERGENCY,

    # Entries to additionally support (so more like Pushover's API)
    '-2': PushoverPriority.LOW,
    '-1': PushoverPriority.MODERATE,
    '0': PushoverPriority.NORMAL,
    '1': PushoverPriority.HIGH,
    '2': PushoverPriority.EMERGENCY,
}

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

    # 2.5MB is the maximum supported image filesize as per documentation
    # here: https://pushover.net/api#attachments (Dec 26th, 2019)
    attach_max_size_bytes = 2621440

    # The regular expression of the current attachment supported mime types
    # At this time it is only images
    attach_supported_mime_type = r'^image/.*'

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
        },
        'token': {
            'name': _('Access Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_device': {
            'name': _('Target Device'),
            'type': 'string',
            'regex': (r'^[a-z0-9_]{1,25}$', 'i'),
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
            'regex': (r'^[a-z]{1,12}$', 'i'),
            'default': PushoverSound.PUSHOVER,
        },
        'url': {
            'name': _('URL'),
            'map_to': 'supplemental_url',
            'type': 'string',
        },
        'url_title': {
            'name': _('URL Title'),
            'map_to': 'supplemental_url_title',
            'type': 'string'
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

    def __init__(self, user_key, token, targets=None, priority=None,
                 sound=None, retry=None, expire=None, supplemental_url=None,
                 supplemental_url_title=None, **kwargs):
        """
        Initialize Pushover Object
        """
        super().__init__(**kwargs)

        # Access Token (associated with project)
        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Pushover Access Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # User Key (associated with project)
        self.user_key = validate_regex(user_key)
        if not self.user_key:
            msg = 'An invalid Pushover User Key ' \
                  '({}) was specified.'.format(user_key)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.targets = parse_list(targets)
        if len(self.targets) == 0:
            self.targets = (PUSHOVER_SEND_TO_ALL, )

        # Setup supplemental url
        self.supplemental_url = supplemental_url
        self.supplemental_url_title = supplemental_url_title

        # Setup our sound
        self.sound = NotifyPushover.default_pushover_sound \
            if not isinstance(sound, str) else sound.lower()
        if self.sound and self.sound not in PUSHOVER_SOUNDS:
            msg = 'The sound specified ({}) is invalid.'.format(sound)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Priority of the message
        self.priority = int(
            NotifyPushover.template_args['priority']['default']
            if priority is None else
            next((
                v for k, v in PUSHOVER_PRIORITY_MAP.items()
                if str(priority).lower().startswith(k)),
                NotifyPushover.template_args['priority']['default']))

        # The following are for emergency alerts
        if self.priority == PushoverPriority.EMERGENCY:

            # How often to resend notification, in seconds
            self.retry = self.template_args['retry']['default']
            try:
                self.retry = int(retry)
            except (ValueError, TypeError):
                # Do nothing
                pass

            # How often to resend notification, in seconds
            self.expire = self.template_args['expire']['default']
            try:
                self.expire = int(expire)
            except (ValueError, TypeError):
                # Do nothing
                pass

            if self.retry < 30:
                msg = 'Pushover retry must be at least 30 seconds.'
                self.logger.warning(msg)
                raise TypeError(msg)

            if self.expire < 0 or self.expire > 10800:
                msg = 'Pushover expire must reside in the range of ' \
                      '0 to 10800 seconds.'
                self.logger.warning(msg)
                raise TypeError(msg)
        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform Pushover Notification
        """

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
                'user': self.user_key,
                'priority': str(self.priority),
                'title': title if title else self.app_desc,
                'message': body,
                'device': device,
                'sound': self.sound,
            }

            if self.supplemental_url:
                payload['url'] = self.supplemental_url
            if self.supplemental_url_title:
                payload['url_title'] = self.supplemental_url_title

            if self.notify_format == NotifyFormat.HTML:
                # https://pushover.net/api#html
                payload['html'] = 1
            elif self.notify_format == NotifyFormat.MARKDOWN:
                payload['message'] = convert_between(
                    NotifyFormat.MARKDOWN, NotifyFormat.HTML, body)
                payload['html'] = 1

            if self.priority == PushoverPriority.EMERGENCY:
                payload.update({'retry': self.retry, 'expire': self.expire})

            if attach:
                # Create a copy of our payload
                _payload = payload.copy()

                # Send with attachments
                for attachment in attach:
                    # Simple send
                    if not self._send(_payload, attachment):
                        # Mark our failure
                        has_error = True
                        # clean exit from our attachment loop
                        break

                    # To handle multiple attachments, clean up our message
                    _payload['title'] = '...'
                    _payload['message'] = attachment.name
                    # No need to alarm for each consecutive attachment uploaded
                    # afterwards
                    _payload['sound'] = PushoverSound.NONE

            else:
                # Simple send
                if not self._send(payload):
                    # Mark our failure
                    has_error = True

        return not has_error

    def _send(self, payload, attach=None):
        """
        Wrapper to the requests (post) object
        """

        if isinstance(attach, AttachBase):
            # Perform some simple error checking
            if not attach:
                # We could not access the attachment
                self.logger.error(
                    'Could not access attachment {}.'.format(
                        attach.url(privacy=True)))
                return False

            # Perform some basic checks as we want to gracefully skip
            # over unsupported mime types.
            if not re.match(
                    self.attach_supported_mime_type,
                    attach.mimetype,
                    re.I):
                # No problem; we just don't support this attachment
                # type; gracefully move along
                self.logger.debug(
                    'Ignored unsupported Pushover attachment ({}): {}'
                    .format(
                        attach.mimetype,
                        attach.url(privacy=True)))

                attach = None

            else:
                # If we get here, we're dealing with a supported image.
                # Verify that the filesize is okay though.
                file_size = len(attach)
                if not (file_size > 0
                        and file_size <= self.attach_max_size_bytes):

                    # File size is no good
                    self.logger.warning(
                        'Pushover attachment size ({}B) exceeds limit: {}'
                        .format(file_size, attach.url(privacy=True)))

                    return False

                self.logger.debug(
                    'Posting Pushover attachment {}'.format(
                        attach.url(privacy=True)))

        # Default Header
        headers = {
            'User-Agent': self.app_id,
        }

        # Authentication
        auth = (self.token, '')

        # Some default values for our request object to which we'll update
        # depending on what our payload is
        files = None

        self.logger.debug('Pushover POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Pushover Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            # Open our attachment path if required:
            if attach:
                files = {'attachment': (attach.name, open(attach.path, 'rb'))}

            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                files=files,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyPushover.http_response_code_lookup(
                        r.status_code, PUSHOVER_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Pushover notification to {}: '
                    '{}{}error={}.'.format(
                        payload['device'],
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False

            else:
                self.logger.info(
                    'Sent Pushover notification to %s.' % payload['device'])

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Pushover:%s ' % (
                    payload['device']) + 'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            return False

        except (OSError, IOError) as e:
            self.logger.warning(
                'An I/O error occurred while reading {}.'.format(
                    attach.name if attach else 'attachment'))
            self.logger.debug('I/O Exception: %s' % str(e))
            return False

        finally:
            # Close our file (if it's open) stored in the second element
            # of our files tuple (index 1)
            if files:
                files['attachment'][1].close()

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'priority':
                PUSHOVER_PRIORITIES[self.template_args['priority']['default']]
                if self.priority not in PUSHOVER_PRIORITIES
                else PUSHOVER_PRIORITIES[self.priority],
        }

        # Only add expire and retry for emergency messages,
        # pushover ignores for all other priorities
        if self.priority == PushoverPriority.EMERGENCY:
            params.update({'expire': self.expire, 'retry': self.retry})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Escape our devices
        devices = '/'.join([NotifyPushover.quote(x, safe='')
                            for x in self.targets])

        if devices == PUSHOVER_SEND_TO_ALL:
            # keyword is reserved for internal usage only; it's safe to remove
            # it from the devices list
            devices = ''

        return '{schema}://{user_key}@{token}/{devices}/?{params}'.format(
            schema=self.secure_protocol,
            user_key=self.pprint(self.user_key, privacy, safe=''),
            token=self.pprint(self.token, privacy, safe=''),
            devices=devices,
            params=NotifyPushover.urlencode(params))

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyPushover.unquote(results['qsd']['priority'])

        # Retrieve all of our targets
        results['targets'] = NotifyPushover.split_path(results['fullpath'])

        # User Key is retrieved from the user
        results['user_key'] = NotifyPushover.unquote(results['user'])

        # Get the sound
        if 'sound' in results['qsd'] and len(results['qsd']['sound']):
            results['sound'] = \
                NotifyPushover.unquote(results['qsd']['sound'])

        # Get the supplementary url
        if 'url' in results['qsd'] and len(results['qsd']['url']):
            results['supplemental_url'] = NotifyPushover.unquote(
                results['qsd']['url']
            )
        if 'url_title' in results['qsd'] and len(results['qsd']['url_title']):
            results['supplemental_url_title'] = results['qsd']['url_title']

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
