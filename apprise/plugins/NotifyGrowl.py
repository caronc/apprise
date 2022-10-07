# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _

# Default our global support flag
NOTIFY_GROWL_SUPPORT_ENABLED = False

try:
    import gntp.notifier

    # We're good to go!
    NOTIFY_GROWL_SUPPORT_ENABLED = True

except ImportError:
    # No problem; we just simply can't support this plugin until
    # gntp is installed
    pass


# Priorities
class GrowlPriority:
    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


GROWL_PRIORITIES = {
    # Note: This also acts as a reverse lookup mapping
    GrowlPriority.LOW: 'low',
    GrowlPriority.MODERATE: 'moderate',
    GrowlPriority.NORMAL: 'normal',
    GrowlPriority.HIGH: 'high',
    GrowlPriority.EMERGENCY: 'emergency',
}

GROWL_PRIORITY_MAP = {
    # Maps against string 'low'
    'l': GrowlPriority.LOW,
    # Maps against string 'moderate'
    'm': GrowlPriority.MODERATE,
    # Maps against string 'normal'
    'n': GrowlPriority.NORMAL,
    # Maps against string 'high'
    'h': GrowlPriority.HIGH,
    # Maps against string 'emergency'
    'e': GrowlPriority.EMERGENCY,

    # Entries to additionally support (so more like Growl's API)
    '-2': GrowlPriority.LOW,
    '-1': GrowlPriority.MODERATE,
    '0': GrowlPriority.NORMAL,
    '1': GrowlPriority.HIGH,
    '2': GrowlPriority.EMERGENCY,
}


class NotifyGrowl(NotifyBase):
    """
    A wrapper to Growl Notifications

    """
    # Set our global enabled flag
    enabled = NOTIFY_GROWL_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        'packages_required': 'gntp'
    }

    # The default descriptive name associated with the Notification
    service_name = 'Growl'

    # The services URL
    service_url = 'http://growl.info/'

    # The default protocol
    protocol = 'growl'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_growl'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # Disable throttle rate for Growl requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Limit results to just the first 10 line otherwise there is just to much
    # content to display
    body_max_line_count = 2

    # Default Growl Port
    default_port = 23053

    # The Growl notification type used
    growl_notification_type = "New Messages"

    # Define object templates
    templates = (
        '{schema}://{host}',
        '{schema}://{host}:{port}',
        '{schema}://{password}@{host}',
        '{schema}://{password}@{host}:{port}',
    )

    # Define our template tokens
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
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'values': GROWL_PRIORITIES,
            'default': GrowlPriority.NORMAL,
        },
        'version': {
            'name': _('Version'),
            'type': 'choice:int',
            'values': (1, 2),
            'default': 2,
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
        'sticky': {
            'name': _('Sticky'),
            'type': 'bool',
            'default': True,
            'map_to': 'sticky',
        },
    })

    def __init__(self, priority=None, version=2, include_image=True,
                 sticky=False, **kwargs):
        """
        Initialize Growl Object
        """
        super(NotifyGrowl, self).__init__(**kwargs)

        if not self.port:
            self.port = self.default_port

        # The Priority of the message
        self.priority = NotifyGrowl.template_args['priority']['default'] \
            if not priority else \
            next((
                v for k, v in GROWL_PRIORITY_MAP.items()
                if str(priority).lower().startswith(k)),
                NotifyGrowl.template_args['priority']['default'])

        # Our Registered object
        self.growl = None

        # Sticky flag
        self.sticky = sticky

        # Store Version
        self.version = version

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

        return

    def register(self):
        """
        Registers with the Growl server
        """
        payload = {
            'applicationName': self.app_id,
            'notifications': [self.growl_notification_type, ],
            'defaultNotifications': [self.growl_notification_type, ],
            'hostname': self.host,
            'port': self.port,
        }

        if self.password is not None:
            payload['password'] = self.password

        self.logger.debug('Growl Registration Payload: %s' % str(payload))
        self.growl = gntp.notifier.GrowlNotifier(**payload)

        try:
            self.growl.register()

        except gntp.errors.NetworkError:
            msg = 'A network error error occurred registering ' \
                  'with Growl at {}.'.format(self.host)
            self.logger.warning(msg)
            return False

        except gntp.errors.ParseError:
            msg = 'A parsing error error occurred registering ' \
                  'with Growl at {}.'.format(self.host)
            self.logger.warning(msg)
            return False

        except gntp.errors.AuthError:
            msg = 'An authentication error error occurred registering ' \
                  'with Growl at {}.'.format(self.host)
            self.logger.warning(msg)
            return False

        except gntp.errors.UnsupportedError:
            msg = 'An unsupported error occurred registering with ' \
                  'Growl at {}.'.format(self.host)
            self.logger.warning(msg)
            return False

        self.logger.debug(
            'Growl server registration completed successfully.'
        )

        # Return our state
        return True

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Growl Notification
        """
        # Register ourselves with the server if we haven't done so already
        if not self.growl and not self.register():
            # We failed to register
            return False

        icon = None
        if self.version >= 2:
            # URL Based
            icon = None if not self.include_image \
                else self.image_url(notify_type)

        else:
            # Raw
            icon = None if not self.include_image \
                else self.image_raw(notify_type)

        payload = {
            'noteType': self.growl_notification_type,
            'title': title,
            'description': body,
            'icon': icon is not None,
            'sticky': self.sticky,
            'priority': self.priority,
        }
        self.logger.debug('Growl Payload: %s' % str(payload))

        # Update icon of payload to be raw data; this is intentionally done
        # here after we spit the debug message above (so we don't try to
        # print the binary contents of an image
        payload['icon'] = icon

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            # Perform notification
            response = self.growl.notify(**payload)
            if not isinstance(response, bool):
                self.logger.warning(
                    'Growl notification failed to send with response: %s' %
                    str(response),
                )

            else:
                self.logger.info('Sent Growl notification.')

        except gntp.errors.BaseError as e:
            # Since Growl servers listen for UDP broadcasts, it's possible
            # that you will never get to this part of the code since there is
            # no acknowledgement as to whether it accepted what was sent to it
            # or not.

            # However, if the host/server is unavailable, you will get to this
            # point of the code.
            self.logger.warning(
                'A Connection error occurred sending Growl '
                'notification to %s.' % self.host)
            self.logger.debug('Growl Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
            'sticky': 'yes' if self.sticky else 'no',
            'priority':
                GROWL_PRIORITIES[self.template_args['priority']['default']]
                if self.priority not in GROWL_PRIORITIES
                else GROWL_PRIORITIES[self.priority],
            'version': self.version,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        auth = ''
        if self.user:
            # The growl password is stored in the user field
            auth = '{password}@'.format(
                password=self.pprint(
                    self.user, privacy, mode=PrivacyMode.Secret, safe=''),
            )

        return '{schema}://{auth}{hostname}{port}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == self.default_port
                 else ':{}'.format(self.port),
            params=NotifyGrowl.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        version = None
        if 'version' in results['qsd'] and len(results['qsd']['version']):
            # Allow the user to specify the version of the protocol to use.
            try:
                version = int(
                    NotifyGrowl.unquote(
                        results['qsd']['version']).strip().split('.')[0])

            except (AttributeError, IndexError, TypeError, ValueError):
                NotifyGrowl.logger.warning(
                    'An invalid Growl version of "%s" was specified and will '
                    'be ignored.' % results['qsd']['version']
                )
                pass

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyGrowl.unquote(results['qsd']['priority'])

        # Because of the URL formatting, the password is actually where the
        # username field is. For this reason, we just preform this small hack
        # to make it (the URL) conform correctly. The following strips out the
        # existing password entry (if exists) so that it can be swapped with
        # the new one we specify.
        if results.get('password', None) is None:
            results['password'] = results.get('user', None)

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image',
                       NotifyGrowl.template_args['image']['default']))

        # Include images with our message
        results['sticky'] = \
            parse_bool(results['qsd'].get('sticky',
                       NotifyGrowl.template_args['sticky']['default']))

        # Set our version
        if version:
            results['version'] = version

        return results
