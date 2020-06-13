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

# For LaMetric to work, you need to first setup a custom application on their
# website. it can be done as follows:
#
# - Sign Up and login to the developer webpage https://developer.lametric.com
# - Click the Create button in the upper right corner, then select
#    Notification App and click Create again.
# - Enter an app name, a description and a redirect URL. Give it basic, and
#    devices_read permissions.
# - Finally, click Save to create the application.
# - Access your newly created entry so that you can acquire both the Client ID
#    and the Client Secret. These are crutial components needed to assemble
#    the Apprise API with.


# A great source for API examples:
# - https://lametric-documentation.readthedocs.io/en/latest/reference-docs\
#       /device-notifications.html

# A great source for the icon reference:
# - https://developer.lametric.com/icons
import six
import requests
from json import dumps
from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_email
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class LametricMode(object):
    """
    Define Lametric Notification Modes
    """
    # App posts upstream to the developer API on Lametric's website
    APPLICATION = "app"

    # Device mode posts directly to the device that you identify
    DEVICE = "dev"


LAMETRIC_MODES = (
    LametricMode.APPLICATION,
    LametricMode.DEVICE,
)


class LametricPriority(object):
    """
    Priority of the message
    """

    # info: this priority means that notification will be displayed on the
    #        same “level” as all other notifications on the device that come
    #        from apps (for example facebook app). This notification will not
    #        be shown when screensaver is active. By default message is sent
    #        with "info" priority. This level of notification should be used
    #        for notifications like news, weather, temperature, etc.
    INFO = 'info'

    # warning: notifications with this priority will interrupt ones sent with
    #           lower priority (“info”). Should be used to notify the user
    #           about something important but not critical. For example,
    #           events like “someone is coming home” should use this priority
    #           when sending notifications from smart home.
    WARNING = 'warning'

    # critical: the most important notifications. Interrupts notification
    #            with priority info or warning and is displayed even if
    #            screensaver is active. Use with care as these notifications
    #            can pop in the middle of the night. Must be used only for
    #            really important notifications like notifications from smoke
    #            detectors, water leak sensors, etc. Use it for events that
    #            require human interaction immediately.
    CRITICAL = 'critical'


LAMETRIC_PRIORITIES = (
    LametricPriority.INFO,
    LametricPriority.WARNING,
    LametricPriority.CRITICAL,
)


class LametricIconType(object):
    """
    Represents the nature of notification.
    """

    # info  - "i" icon will be displayed prior to the notification. Means that
    #         notification contains information, no need to take actions on it.
    INFO = 'info'

    # alert: "!!!" icon will be displayed prior to the notification. Use it
    #         when you want the user to pay attention to that notification as
    #         it indicates that something bad happened and user must take
    #         immediate action.
    ALERT = 'alert'

    # none: no notification icon will be shown.
    NONE = 'none'


LAMETRIC_ICON_TYPES = (
    LametricPriority.INFO,
    LametricPriority.WARNING,
    LametricPriority.CRITICAL,
)


class LametricSoundCategory(object):
    """
    Define Sound Categories
    """
    NOTIFICATIONS = "notifications"
    ALARMS = "alarms"


class LametricSound(object):
    """
    There are 2 categories of sounds, to make things simple we just lump them
    all togther in one class object.

    Syntax is (Category, (AlarmID, Alias1, Alias2, ...))
    """

    # Alarm Category Sounds
    ALARM01 = (LametricSoundCategory.ALARMS, ('alarm1', 'a1', 'a01'))
    ALARM02 = (LametricSoundCategory.ALARMS, ('alarm2', 'a2', 'a02'))
    ALARM03 = (LametricSoundCategory.ALARMS, ('alarm3', 'a3', 'a03'))
    ALARM04 = (LametricSoundCategory.ALARMS, ('alarm4', 'a4', 'a04'))
    ALARM05 = (LametricSoundCategory.ALARMS, ('alarm5', 'a5', 'a05'))
    ALARM06 = (LametricSoundCategory.ALARMS, ('alarm6', 'a6', 'a06'))
    ALARM07 = (LametricSoundCategory.ALARMS, ('alarm7', 'a7', 'a07'))
    ALARM08 = (LametricSoundCategory.ALARMS, ('alarm8', 'a8', 'a08'))
    ALARM09 = (LametricSoundCategory.ALARMS, ('alarm9', 'a9', 'a09'))
    ALARM10 = (LametricSoundCategory.ALARMS, ('alarm10', 'a10'))
    ALARM11 = (LametricSoundCategory.ALARMS, ('alarm11', 'a11'))
    ALARM12 = (LametricSoundCategory.ALARMS, ('alarm12', 'a12'))
    ALARM13 = (LametricSoundCategory.ALARMS, ('alarm13', 'a13'))

    # Notification Category Sounds
    BICYCLE = (LametricSoundCategory.NOTIFICATIONS, ('bicycle', 'bike'))
    CAR = (LametricSoundCategory.NOTIFICATIONS, ('car', ))
    CASH = (LametricSoundCategory.NOTIFICATIONS, ('cash', ))
    CAT = (LametricSoundCategory.NOTIFICATIONS, ('cat', ))
    DOG01 = (LametricSoundCategory.NOTIFICATIONS, ('dog', 'dog1', 'dog01'))
    DOG02 = (LametricSoundCategory.NOTIFICATIONS, ('dog2', 'dog02'))
    ENERGY = (LametricSoundCategory.NOTIFICATIONS, ('energy', ))
    KNOCK = (LametricSoundCategory.NOTIFICATIONS, ('knock-knock', 'knock'))
    EMAIL = (LametricSoundCategory.NOTIFICATIONS, (
        'letter_email', 'letter', 'email'))
    LOSE01 = (LametricSoundCategory.NOTIFICATIONS, ('lose1', 'lose01', 'lose'))
    LOSE02 = (LametricSoundCategory.NOTIFICATIONS, ('lose2', 'lose02'))
    NEGATIVE01 = (LametricSoundCategory.NOTIFICATIONS, (
        'negative1', 'negative01', 'neg01', 'neg1', '-'))
    NEGATIVE02 = (LametricSoundCategory.NOTIFICATIONS, (
        'negative2', 'negative02', 'neg02', 'neg2', '--'))
    NEGATIVE03 = (LametricSoundCategory.NOTIFICATIONS, (
        'negative3', 'negative03', 'neg03', 'neg3', '---'))
    NEGATIVE04 = (LametricSoundCategory.NOTIFICATIONS, (
        'negative4', 'negative04', 'neg04', 'neg4', '----'))
    NEGATIVE05 = (LametricSoundCategory.NOTIFICATIONS, (
        'negative5', 'negative05', 'neg05', 'neg5', '-----'))
    NOTIFICATION01 = (LametricSoundCategory.NOTIFICATIONS, (
        'notification', 'notification1', 'notification01', 'not01', 'not1'))
    NOTIFICATION02 = (LametricSoundCategory.NOTIFICATIONS, (
        'notification2', 'notification02', 'not02', 'not2'))
    NOTIFICATION03 = (LametricSoundCategory.NOTIFICATIONS, (
        'notification3', 'notification03', 'not03', 'not3'))
    NOTIFICATION04 = (LametricSoundCategory.NOTIFICATIONS, (
        'notification4', 'notification04', 'not04', 'not4'))
    OPEN_DOOR = (LametricSoundCategory.NOTIFICATIONS, (
        'open_door', 'open', 'door'))
    POSITIVE01 = (LametricSoundCategory.NOTIFICATIONS, (
        'positive1', 'positive01', 'pos01', 'p1', '+'))
    POSITIVE02 = (LametricSoundCategory.NOTIFICATIONS, (
        'positive2', 'positive02', 'pos02', 'p2', '++'))
    POSITIVE03 = (LametricSoundCategory.NOTIFICATIONS, (
        'positive3', 'positive03', 'pos03', 'p3', '+++'))
    POSITIVE04 = (LametricSoundCategory.NOTIFICATIONS, (
        'positive4', 'positive04', 'pos04', 'p4', '++++'))
    POSITIVE05 = (LametricSoundCategory.NOTIFICATIONS, (
        'positive5', 'positive05', 'pos05', 'p5', '+++++'))
    POSITIVE06 = (LametricSoundCategory.NOTIFICATIONS, (
        'positive6', 'positive06', 'pos06', 'p6', '++++++'))
    STATISTIC = (LametricSoundCategory.NOTIFICATIONS, ('statistic', 'stat'))
    THUNDER = (LametricSoundCategory.NOTIFICATIONS, ('thunder'))
    WATER01 = (LametricSoundCategory.NOTIFICATIONS, ('water1', 'water01'))
    WATER02 = (LametricSoundCategory.NOTIFICATIONS, ('water2', 'water02'))
    WIN01 = (LametricSoundCategory.NOTIFICATIONS, ('win', 'win01', 'win1'))
    WIN02 = (LametricSoundCategory.NOTIFICATIONS, ('win2', 'win02'))
    WIND = (LametricSoundCategory.NOTIFICATIONS, ('wind', ))
    WIND_SHORT = (LametricSoundCategory.NOTIFICATIONS, ('wind_short', ))


# A listing of all the sounds; the order DOES matter, content is read from
# top down and then right to left (over aliases). Longer similar sounding
# elements should be placed higher in the list over others. for example
# ALARM10 should come before ALARM01 (because ALARM01 can match on 'alarm1'
# which is very close to 'alarm10'
LAMETRIC_SOUNDS = (
    # Alarm Category Entries
    LametricSound.ALARM13, LametricSound.ALARM12, LametricSound.ALARM11,
    LametricSound.ALARM10, LametricSound.ALARM09, LametricSound.ALARM08,
    LametricSound.ALARM07, LametricSound.ALARM06, LametricSound.ALARM05,
    LametricSound.ALARM04, LametricSound.ALARM03, LametricSound.ALARM02,
    LametricSound.ALARM01,

    # Notification Category Entries
    LametricSound.BICYCLE, LametricSound.CAR, LametricSound.CASH,
    LametricSound.CAT, LametricSound.DOG02, LametricSound.DOG01,
    LametricSound.ENERGY, LametricSound.KNOCK, LametricSound.EMAIL,
    LametricSound.LOSE02, LametricSound.LOSE01, LametricSound.NEGATIVE01,
    LametricSound.NEGATIVE02, LametricSound.NEGATIVE03,
    LametricSound.NEGATIVE04, LametricSound.NEGATIVE05,
    LametricSound.NOTIFICATION04, LametricSound.NOTIFICATION03,
    LametricSound.NOTIFICATION02, LametricSound.NOTIFICATION01,
    LametricSound.OPEN_DOOR, LametricSound.POSITIVE01,
    LametricSound.POSITIVE02, LametricSound.POSITIVE03,
    LametricSound.POSITIVE04, LametricSound.POSITIVE05,
    LametricSound.POSITIVE01, LametricSound.STATISTIC, LametricSound.THUNDER,
    LametricSound.WATER02, LametricSound.WATER01, LametricSound.WIND,
    LametricSound.WIND_SHORT, LametricSound.WIN01, LametricSound.WIN02,
)


class NotifyLametric(NotifyBase):
    """
    A wrapper for LaMetric Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'LaMetric'

    # The services URL
    service_url = 'https://lametric.com'

    # The default protocol
    protocol = 'lametric'

    # The default secure protocol
    secure_protocol = 'lametrics'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_lametric'

    # Lametric does have titles when creating a message
    title_maxlen = 0

    # URL used for notifying Lametric App's created in the Dev Portal
    app_notify_url = 'https://developer.lametric.com/api/v1' \
                     '/dev/widget/update/com.lametric.{client_id}'

    # URL used for local notifications directly to the device
    dev_notify_url = '{schema}://{host}{port}/api/v2/device/notifications'

    # LaMetric Default port
    default_dev_port = 8080

    # The default User ID when making a local connection and one isn't
    # otherwise specified
    default_local_user = 'dev'

    # Track all icon mappings back to Apprise Icon NotifyType's
    # See: https://developer.lametric.com/icons
    # Icon ID looks like <prefix>XXX, where <prefix> is:
    #   - "i" (for static icon)
    #   - "a" (for animation)
    #   - XXX - is the number of the icon and can be found at:
    #            https://developer.lametric.com/icons
    lametric_icon_id_mapping = {
        # 620/Info
        NotifyType.INFO: 'i620',
        # 9182/info_good
        NotifyType.SUCCESS: 'i9182',
        # 9183/info_caution
        NotifyType.WARNING: 'i9183',
        # 9184/info_error
        NotifyType.FAILURE: 'i9184',
    }

    # Define object templates
    templates = (
        # App Mode
        '{schema}://{client_id}@{secret}',

        # Device Mode
        '{schema}://{apikey}@{host}',
        '{schema}://{apikey}@{host}:{port}',
        '{schema}://{user}:{apikey}@{host}:{port}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'client_id': {
            'name': _('Client ID'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9-]+$', 'i'),
        },
        'secret': {
            'name': _('Client Secret'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'oauth_id': {
            'alias_of': 'client_id',
        },
        'oauth_secret': {
            'alias_of': 'secret',
        },
        'priority': {
            'name': _('Priority'),
            'type': 'choice:string',
            'values': LAMETRIC_PRIORITIES,
            'default': LametricPriority.INFO,
        },
        'icon_type': {
            'name': _('Icon Type'),
            'type': 'choice:string',
            'values': LAMETRIC_ICON_TYPES,
            'default': LametricIconType.NONE,
        },
        'mode': {
            'name': _('Mode'),
            'type': 'choice:string',
            'values': LAMETRIC_MODES,
            'default': LametricMode.DEVICE,
        },
        'sound': {
            'name': _('Sound'),
            'type': 'string',
            'default': LametricIconType.NONE,
        },
    })

    def __init__(self, client_id, secret, priority=None, icon_type=None,
                 sound=None, mode=None, **kwargs):
        """
        Initialize LaMetric Object
        """
        super(NotifyLametric, self).__init__(**kwargs)

        # Client ID
        self.client_id = validate_regex(
            client_id, *self.template_tokens['client_id']['regex'])
        if not self.client_id:
            msg = 'An invalid LaMetric Client OAuth2 ID ' \
                  '({}) was specified.'.format(client_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Client Secret
        self.secret = validate_regex(secret)
        if not self.secret:
            msg = 'An invalid LaMetric Client OAuth2 Secret ' \
                  '({}) was specified.'.format(secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.mode = mode.strip().lower() \
            if isinstance(sound, six.string_types) \
            else self.template_args['mode']['default']

        if self.mode not in LAMETRIC_MODES:
            msg = 'An invalid LaMetric Mode ' \
                  '({}) was specified.'.format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        if priority not in LAMETRIC_PRIORITIES:
            self.priority = self.template_args['priority']['default']

        else:
            self.priority = priority

        if icon_type not in LAMETRIC_ICON_TYPES:
            self.icon_type = self.template_args['icon_type']['default']

        else:
            self.icon_type = icon_type

        # If sound is set, get it's match
        self.sound = self.sound_lookup(sound.strip().lower()) \
            if isinstance(sound, six.string_types) else None

        return

    @staticmethod
    def sound_lookup(lookup):
        """
        A simple match function that takes string and returns the
        LametricSound object it was found in.

        """

        for x in LAMETRIC_SOUNDS:
            match = next((f for f in x[1] if f.startswith(lookup)), None)
            if match:
                # We're done
                return x

        # No match was found
        return None

    def _app_notification_payload(self, body, notify_type, headers):
        """
        Return URL and Payload for Application directed requests
        """

        # Update header entries
        headers.update({
            'X-Access-Token': self.secret,
        })

        payload = {}
        auth = None

        # Prepare our App Notify URL
        notify_url = self.app_notify_url.format(client_id=self.client_id)

        # Return request parameters
        return (notify_url, auth, payload)

    def _dev_notification_payload(self, body, notify_type, headers):
        """
        Return URL and Payload for Device directed requests
        """

        # Our Payload
        payload = {
            "priority": self.priority,
            "icon_type": self.icon_type,
            "model": {
                "cycles": 1,
                "frames": [
                    {
                        "icon": self.lametric_icon_id_mapping[notify_type],
                        "text": body,
                    }
                ]
            }
        }

        if self.sound:
            # Sound was set, so add it to the payload
            payload["model"]["sound"] = {
                "category": self.sound[0],
                # The first element of our tuple is always the id
                "id": self.sound[1][0],
            }

        if self.password and not self.user:
            # Use default user if there wasn't one otherwise specified
            self.user = self.default_local_user

        auth = (self.user, self.password)

        # Prepare our Direct Access Notify URL
        notify_url = self.dev_notify_url.format(
            schema="https" if self.secure else "http",
            host=self.host,
            port=':{}'.format(self.port)
            if self.port else self.default_dev_port)

        # Return request parameters
        return (notify_url, auth, payload)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform LaMetric Notification
        """

        # Prepare our headers:
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # Depending on the mode, the payload is gathered by
        # - _dev_notification_payload()
        # - _app_notification_payload()
        (notify_url, auth, payload) = getattr(
            self, '_{}_notification_payload'.format(
                self.mode, body=body, notify_type=notify_type,
                headers=headers))

        self.logger.debug('LaMetric POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('LaMetric Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyLametric.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send LaMetric notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent LaMetric notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending LaMetric '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'priority': self.priority,
            'icon_type': self.icon_type,
            'mode': self.mode,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.sound:
            # Store our sound entry
            # The first element of our tuple is always the id
            params['sound'] = self.sound[1][0]

        if self.mode == LametricMode.APPLICATION:
            # Upstream/LaMetric App Return
            return '{schema}://{client_id}@{secret}' \
                '/{targets}/?{params}'.format(
                    schema=self.secure_protocol,
                    client_id=self.pprint(self.client_id, privacy, safe=''),
                    secret=self.pprint(
                        self.secret, privacy, mode=PrivacyMode.Secret,
                        safe=''),
                    params=NotifyLametric.urlencode(params))

        # If we reach here then we're dealing with LametricMode.DEVICE
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyLametric.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        else:  # self.password is set
            auth = '{password}@'.format(
                user=NotifyLametric.quote(self.password, safe=''),
            )

        # Local Return
        return '{schema}://{auth}{hostname}{port}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyLametric.quote(self.host, safe=''),
            port='' if self.port is None or self.port == self.default_dev_port
                 else ':{}'.format(self.port),
            params=NotifyLametric.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Now make a list of all our path entries
        # We need to read each entry back one at a time in reverse order
        # where each email found we mark as a target. Once we run out
        # of targets, the presume the remainder of the entries are part
        # of the secret key (since it can contain slashes in it)
        entries = NotifyLametric.split_path(results['fullpath'])

        try:
            # Get our client_id is the first entry on the path
            results['client_id'] = NotifyLametric.unquote(entries.pop(0))

        except IndexError:
            # no problem, we may get the client_id another way through
            # arguments...
            pass

        # Prepare our target listing
        results['targets'] = list()
        while entries:
            # Pop the last entry
            entry = NotifyLametric.unquote(entries.pop(-1))

            if is_email(entry):
                # Store our email and move on
                results['targets'].append(entry)
                continue

            # If we reach here, the entry we just popped is part of the secret
            # key, so put it back
            entries.append(NotifyLametric.quote(entry, safe=''))

            # We're done
            break

        # Initialize our tenant
        results['tenant'] = None

        # Assemble our secret key which is a combination of the host followed
        # by all entries in the full path that follow up until the first email
        results['secret'] = '/'.join(
            [NotifyLametric.unquote(x) for x in entries])

        # Assemble our client id from the user@hostname
        if results['password']:
            results['email'] = '{}@{}'.format(
                NotifyLametric.unquote(results['password']),
                NotifyLametric.unquote(results['host']),
            )
            # Update our tenant
            results['tenant'] = NotifyLametric.unquote(results['user'])

        else:
            # No tenant specified..
            results['email'] = '{}@{}'.format(
                NotifyLametric.unquote(results['user']),
                NotifyLametric.unquote(results['host']),
            )

        # OAuth2 ID
        if 'oauth_id' in results['qsd'] and len(results['qsd']['oauth_id']):
            # Extract the API Key from an argument
            results['client_id'] = \
                NotifyLametric.unquote(results['qsd']['oauth_id'])

        # OAuth2 Secret
        if 'oauth_secret' in results['qsd'] and \
                len(results['qsd']['oauth_secret']):
            # Extract the API Secret from an argument
            results['secret'] = \
                NotifyLametric.unquote(results['qsd']['oauth_secret'])

        # Mode (just look 3 charaters in)
        if 'mode' in results['qsd'] and len(results['qsd']['mode']):
            results['mode'] = results['qsd']['mode'].strip().lower()[:3]

        # Priority Handling
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = results['qsd']['priority'].strip().lower()

        # Icon Type
        if 'icon_type' in results['qsd'] and len(results['qsd']['icon_type']):
            results['icon_type'] = results['qsd']['icon_type'].strip().lower()

        # Sound
        if 'sound' in results['qsd'] and len(results['qsd']['sound']):
            results['sound'] = results['qsd']['sound'].strip().lower()

        return results
