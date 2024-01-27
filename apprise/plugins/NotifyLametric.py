# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# For LaMetric to work, you need to first setup a custom application on their
# website. it can be done as follows:

# Cloud Mode:
# - Sign Up and login to the developer webpage https://developer.lametric.com
#
# - Create a **Indicator App** if you haven't already done so from here:
#     https://developer.lametric.com/applications/sources
#
#   There is a great official tutorial on how to do this here:
#     https://lametric-documentation.readthedocs.io/en/latest/\
#           guides/first-steps/first-lametric-indicator-app.html
#
# - Make sure to set the **Communication Type** to **PUSH**.
#
# - You will be able to **Publish** your app once you've finished setting it
#   up.  This will allow it to be accessible from the internet using the
#   `cloud` mode of this Apprise Plugin. The **Publish** button shows up
#   from within the settings of your Lametric App upon clicking on the
#   **Draft Vx** folder (where `x` is the version - usually a 1)
#
# When you've completed, the site would have provided you a **PUSH URL** that
# looks like this:
#    https://developer.lametric.com/api/v1/dev/widget/update/\
#             com.lametric.{app_id}/{app_ver}
#
# You will need to record the `{app_id}` and `{app_ver}` to use the `cloud`
# mode.
#
# The same page should also provide you with an **Access Token**.  It's
# approximately 86 characters with two equal (`=`) characters at the end of it.
# This becomes your `{app_token}`. Here is an example of what one might
# look like:
#    K2MxWI0NzU0ZmI2NjJlZYTgViMDgDRiN8YjlmZjRmNTc4NDVhJzk0RiNjNh0EyKWW==`
#
# The syntax for the cloud mode is:
# * `lametric://{app_token}@{app_id}/{app_ver}?mode=cloud`

# Device Mode:
# - Sign Up and login to the developer webpage https://developer.lametric.com
# - Locate your Device API Key; you can find it here:
#      https://developer.lametric.com/user/devices
# - From here you can get your your API Key for the device you plan to notify.
# - Your devices IP Address can be found in LaMetric Time app at:
#       Settings -> Wi-Fi -> IP Address
#
# The syntax for the device mode is:
#  * `lametric://{apikey}@{host}`

# A great source for API examples (Device Mode):
# - https://lametric-documentation.readthedocs.io/en/latest/reference-docs\
#       /device-notifications.html
#
# A great source for API examples (Cloud Mode):
# - https://lametric-documentation.readthedocs.io/en/latest/reference-docs\
#       /lametric-cloud-reference.html

# A great source for the icon reference:
# - https://developer.lametric.com/icons


import re
import requests
from json import dumps
from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _
from ..utils import is_hostname
from ..utils import is_ipaddr

# A URL Parser to detect App ID
LAMETRIC_APP_ID_DETECTOR_RE = re.compile(
    r'(com\.lametric\.)?(?P<app_id>[0-9a-z.-]{1,64})'
    r'(/(?P<app_ver>[1-9][0-9]*))?', re.I)

# Tokens are huge
LAMETRIC_IS_APP_TOKEN = re.compile(r'^[a-z0-9]{80,}==$', re.I)


class LametricMode:
    """
    Define Lametric Notification Modes
    """
    # App posts upstream to the developer API on Lametric's website
    CLOUD = "cloud"

    # Device mode posts directly to the device that you identify
    DEVICE = "device"


LAMETRIC_MODES = (
    LametricMode.CLOUD,
    LametricMode.DEVICE,
)


class LametricPriority:
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


class LametricIconType:
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
    LametricIconType.INFO,
    LametricIconType.ALERT,
    LametricIconType.NONE,
)


class LametricSoundCategory:
    """
    Define Sound Categories
    """
    NOTIFICATIONS = "notifications"
    ALARMS = "alarms"


class LametricSound:
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
    cloud_notify_url = 'https://developer.lametric.com/api/v1' \
                       '/dev/widget/update/com.lametric.{app_id}/{app_ver}'

    # URL used for local notifications directly to the device
    device_notify_url = '{schema}://{host}{port}/api/v2/device/notifications'

    # The Device User ID
    default_device_user = 'dev'

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
        # Cloud (App) Mode
        '{schema}://{app_token}@{app_id}',
        '{schema}://{app_token}@{app_id}/{app_ver}',

        # Device Mode
        '{schema}://{apikey}@{host}',
        '{schema}://{user}:{apikey}@{host}',
        '{schema}://{apikey}@{host}:{port}',
        '{schema}://{user}:{apikey}@{host}:{port}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        # Used for Local Device mode
        'apikey': {
            'name': _('Device API Key'),
            'type': 'string',
            'private': True,
        },
        # Used for Cloud mode
        'app_id': {
            'name': _('App ID'),
            'type': 'string',
            'private': True,
        },
        # Used for Cloud mode
        'app_ver': {
            'name': _('App Version'),
            'type': 'string',
            'regex': (r'^[1-9][0-9]*$', ''),
            'default': '1',
        },
        # Used for Cloud mode
        'app_token': {
            'name': _('App Access Token'),
            'type': 'string',
            'regex': (r'^[A-Z0-9]{80,}==$', 'i'),
        },
        'host': {
            'name': _('Hostname'),
            'type': 'string',
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
            'default': 8080,
        },
        'user': {
            'name': _('Username'),
            'type': 'string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'apikey': {
            'alias_of': 'apikey',
        },
        'app_id': {
            'alias_of': 'app_id',
        },
        'app_ver': {
            'alias_of': 'app_ver',
        },
        'app_token': {
            'alias_of': 'app_token',
        },
        'priority': {
            'name': _('Priority'),
            'type': 'choice:string',
            'values': LAMETRIC_PRIORITIES,
            'default': LametricPriority.INFO,
        },
        'icon': {
            'name': _('Custom Icon'),
            'type': 'string',
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
        },
        # Lifetime is in seconds
        'cycles': {
            'name': _('Cycles'),
            'type': 'int',
            'min': 0,
            'default': 1,
        },
    })

    def __init__(self, apikey=None, app_token=None, app_id=None,
                 app_ver=None, priority=None, icon=None, icon_type=None,
                 sound=None, mode=None, cycles=None, **kwargs):
        """
        Initialize LaMetric Object
        """
        super().__init__(**kwargs)

        self.mode = mode.strip().lower() \
            if isinstance(mode, str) \
            else self.template_args['mode']['default']

        # Default Cloud Argument
        self.lametric_app_id = None
        self.lametric_app_ver = None
        self.lametric_app_access_token = None

        # Default Device/Cloud Argument
        self.lametric_apikey = None

        if self.mode not in LAMETRIC_MODES:
            msg = 'An invalid LaMetric Mode ({}) was specified.'.format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        if self.mode == LametricMode.CLOUD:
            try:
                results = LAMETRIC_APP_ID_DETECTOR_RE.match(app_id)
            except TypeError:
                msg = 'An invalid LaMetric Application ID ' \
                      '({}) was specified.'.format(app_id)
                self.logger.warning(msg)
                raise TypeError(msg)

            # Detect our Access Token
            self.lametric_app_access_token = validate_regex(
                app_token,
                *self.template_tokens['app_token']['regex'])
            if not self.lametric_app_access_token:
                msg = 'An invalid LaMetric Application Access Token ' \
                      '({}) was specified.'.format(app_token)
                self.logger.warning(msg)
                raise TypeError(msg)

            # If app_ver is specified, it over-rides all
            if app_ver:
                self.lametric_app_ver = validate_regex(
                    app_ver, *self.template_tokens['app_ver']['regex'])
                if not self.lametric_app_ver:
                    msg = 'An invalid LaMetric Application Version ' \
                          '({}) was specified.'.format(app_ver)
                    self.logger.warning(msg)
                    raise TypeError(msg)

            else:
                # If app_ver wasn't specified, we parse it from the
                # Application ID
                self.lametric_app_ver = results.group('app_ver') \
                    if results.group('app_ver') else \
                    self.template_tokens['app_ver']['default']

            # Store our Application ID
            self.lametric_app_id = results.group('app_id')

        if self.mode == LametricMode.DEVICE:
            self.lametric_apikey = validate_regex(apikey)
            if not self.lametric_apikey:
                msg = 'An invalid LaMetric Device API Key ' \
                      '({}) was specified.'.format(apikey)
                self.logger.warning(msg)
                raise TypeError(msg)

        if priority not in LAMETRIC_PRIORITIES:
            self.priority = self.template_args['priority']['default']

        else:
            self.priority = priority

        # assign our icon (if it was defined); we also eliminate
        # any hashtag (#) entries that might be present
        self.icon = re.search(r'[#\s]*(?P<value>.+?)\s*$', icon) \
            .group('value') if isinstance(icon, str) else None

        if icon_type not in LAMETRIC_ICON_TYPES:
            self.icon_type = self.template_args['icon_type']['default']

        else:
            self.icon_type = icon_type

        # The number of times the message should be displayed
        self.cycles = self.template_args['cycles']['default'] \
            if not (isinstance(cycles, int) and
                    cycles > self.template_args['cycles']['min']) else cycles

        self.sound = None
        if isinstance(sound, str):
            # If sound is set, get it's match
            self.sound = self.sound_lookup(sound.strip().lower())
            if self.sound is None:
                self.logger.warning(
                    'An invalid LaMetric sound ({}) was specified.'.format(
                        sound))
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

    def _cloud_notification_payload(self, body, notify_type, headers):
        """
        Return URL and payload for cloud directed requests
        """

        # Update header entries
        headers.update({
            'X-Access-Token': self.lametric_apikey,
        })

        if self.sound:
            self.logger.warning(
                'LaMetric sound setting is unavailable in Cloud mode')

        if self.priority != self.template_args['priority']['default']:
            self.logger.warning(
                'LaMetric priority setting is unavailable in Cloud mode')

        if self.icon_type != self.template_args['icon_type']['default']:
            self.logger.warning(
                'LaMetric icon_type setting is unavailable in Cloud mode')

        if self.cycles != self.template_args['cycles']['default']:
            self.logger.warning(
                'LaMetric cycle settings is unavailable in Cloud mode')

        # Assign our icon if the user specified a custom one, otherwise
        # choose from our pre-set list (based on notify_type)
        icon = self.icon if self.icon \
            else self.lametric_icon_id_mapping[notify_type]

        # Our Payload
        # Cloud Notifications don't have as much functionality
        # You can not set priority and/or sound
        payload = {
            "frames": [
                {
                    "icon": icon,
                    "text": body,
                    "index": 0,
                }
            ]
        }

        # Prepare our Cloud Notify URL
        notify_url = self.cloud_notify_url.format(
            app_id=self.lametric_app_id, app_ver=self.lametric_app_ver)

        # Return request parameters
        return (notify_url, None, payload)

    def _device_notification_payload(self, body, notify_type, headers):
        """
        Return URL and Payload for Device directed requests
        """

        # Assign our icon if the user specified a custom one, otherwise
        # choose from our pre-set list (based on notify_type)
        icon = self.icon if self.icon \
            else self.lametric_icon_id_mapping[notify_type]

        # Our Payload
        payload = {
            # Priority of the message
            "priority": self.priority,

            # Icon Type: Represents the nature of notification
            "icon_type": self.icon_type,

            # The time notification lives in queue to be displayed in
            # milliseconds (ms). The default lifetime is 2 minutes (120000ms).
            # If notification stayed in queue for longer than lifetime
            # milliseconds - it will not be displayed.
            "lifetime": 120000,

            "model": {
                # cycles - the number of times message should be displayed. If
                # cycles is set to 0, notification will stay on the screen
                # until user dismisses it manually. By default it is set to 1.
                "cycles": self.cycles,
                "frames": [
                    {
                        "icon": icon,
                        "text": body,
                    }
                ]
            }
        }

        if self.sound:
            # Sound was set, so add it to the payload
            payload["model"]["sound"] = {
                # The sound category
                "category": self.sound[0],

                # The first element of our tuple is always the id
                "id": self.sound[1][0],

                # repeat - defines the number of times sound must be played.
                # If set to 0 sound will be played until notification is
                # dismissed. By default the value is set to 1.
                "repeat": 1,
            }

        if not self.user:
            # Use default user if there wasn't one otherwise specified
            self.user = self.default_device_user

        # Prepare our authentication
        auth = (self.user, self.password)

        # Prepare our Direct Access Notify URL
        notify_url = self.device_notify_url.format(
            schema="https" if self.secure else "http",
            host=self.host,
            port=':{}'.format(
                self.port if self.port
                else self.template_tokens['port']['default']))

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
            'Cache-Control': 'no-cache',
        }

        # Depending on the mode, the payload is gathered by
        # - _device_notification_payload()
        # - _cloud_notification_payload()
        (notify_url, auth, payload) = getattr(
            self, '_{}_notification_payload'.format(self.mode))(
                body=body, notify_type=notify_type, headers=headers)

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
                timeout=self.request_timeout,
            )
            # An ideal response would be:
            # {
            #   "success": {
            #     "id": "<notification id>"
            #   }
            # }

            if r.status_code not in (
                    requests.codes.created, requests.codes.ok):
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
            'mode': self.mode,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.icon:
            # Assign our icon IF one was specified
            params['icon'] = self.icon

        if self.mode == LametricMode.CLOUD:
            # Upstream/LaMetric App Return
            return '{schema}://{token}@{app_id}/{app_ver}/?{params}'.format(
                schema=self.protocol,
                token=self.pprint(
                    self.lametric_app_access_token, privacy, safe=''),
                app_id=self.pprint(self.lametric_app_id, privacy, safe=''),
                app_ver=NotifyLametric.quote(self.lametric_app_ver, safe=''),
                params=NotifyLametric.urlencode(params))

        #
        # If we reach here then we're dealing with LametricMode.DEVICE
        #
        if self.priority != self.template_args['priority']['default']:
            params['priority'] = self.priority

        if self.icon_type != self.template_args['icon_type']['default']:
            params['icon_type'] = self.icon_type

        if self.cycles != self.template_args['cycles']['default']:
            params['cycles'] = self.cycles

        if self.sound:
            # Store our sound entry
            # The first element of our tuple is always the id
            params['sound'] = self.sound[1][0]

        auth = ''
        if self.user and self.password:
            auth = '{user}:{apikey}@'.format(
                user=NotifyLametric.quote(self.user, safe=''),
                apikey=self.pprint(self.lametric_apikey, privacy, safe=''),
            )
        else:  # self.apikey is set
            auth = '{apikey}@'.format(
                apikey=self.pprint(self.lametric_apikey, privacy, safe=''),
            )

        # Local Return
        return '{schema}://{auth}{hostname}{port}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None
                 or self.port == self.template_tokens['port']['default']
                 else ':{}'.format(self.port),
            params=NotifyLametric.urlencode(params),
        )

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

        if results.get('user') and not results.get('password'):
            # Handle URL like:
            # schema://user@host

            # This becomes the password
            results['password'] = results['user']
            results['user'] = None

        # Priority Handling
        if 'priority' in results['qsd'] and results['qsd']['priority']:
            results['priority'] = NotifyLametric.unquote(
                results['qsd']['priority'].strip().lower())

        # Icon Type
        if 'icon' in results['qsd'] and results['qsd']['icon']:
            results['icon'] = NotifyLametric.unquote(
                results['qsd']['icon'].strip().lower())

        # Icon Type
        if 'icon_type' in results['qsd'] and results['qsd']['icon_type']:
            results['icon_type'] = NotifyLametric.unquote(
                results['qsd']['icon_type'].strip().lower())

        # Sound
        if 'sound' in results['qsd'] and results['qsd']['sound']:
            results['sound'] = NotifyLametric.unquote(
                results['qsd']['sound'].strip().lower())

        # API Key (Device Mode)
        if 'apikey' in results['qsd'] and results['qsd']['apikey']:
            # Extract API Key from an argument
            results['apikey'] = \
                NotifyLametric.unquote(results['qsd']['apikey'])

        # App ID
        if 'app' in results['qsd'] \
                and results['qsd']['app']:

            # Extract the App ID from an argument
            results['app_id'] = \
                NotifyLametric.unquote(results['qsd']['app'])

        # App Version
        if 'app_ver' in results['qsd'] \
                and results['qsd']['app_ver']:

            # Extract the App ID from an argument
            results['app_ver'] = \
                NotifyLametric.unquote(results['qsd']['app_ver'])

        if 'token' in results['qsd'] and results['qsd']['token']:
            # Extract Application Access Token from an argument
            results['app_token'] = \
                NotifyLametric.unquote(results['qsd']['token'])

        # Mode override
        if 'mode' in results['qsd'] and results['qsd']['mode']:
            results['mode'] = NotifyLametric.unquote(
                results['qsd']['mode'].strip().lower())
        else:
            # We can try to detect the mode based on the validity of the
            # hostname. We can also scan the validity of the Application
            # Access token
            #
            # This isn't a surfire way to do things though; it's best to
            # specify the mode= flag
            results['mode'] = LametricMode.DEVICE \
                if ((is_hostname(results['host']) or
                    is_ipaddr(results['host'])) and

                    # make sure password is not an Access Token
                    (results['password'] and not
                        LAMETRIC_IS_APP_TOKEN.match(results['password'])) and

                    # Scan for app_ flags
                    next((f for f in results.keys() \
                          if f.startswith('app_')), None) is None) \
                else LametricMode.CLOUD

        # Handle defaults if not set
        if results['mode'] == LametricMode.DEVICE:
            # Device Mode Defaults
            if 'apikey' not in results:
                results['apikey'] = \
                    NotifyLametric.unquote(results['password'])

        else:
            # CLOUD Mode Defaults
            if 'app_id' not in results:
                results['app_id'] = \
                    NotifyLametric.unquote(results['host'])
            if 'app_token' not in results:
                results['app_token'] = \
                    NotifyLametric.unquote(results['password'])

        # Set cycles
        try:
            results['cycles'] = abs(int(results['qsd'].get('cycles')))

        except (TypeError, ValueError):
            # Not a valid integer; ignore entry
            pass

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support
           https://developer.lametric.com/api/v1/dev/\
                   widget/update/com.lametric.{APP_ID}/1

           https://developer.lametric.com/api/v1/dev/\
                   widget/update/com.lametric.{APP_ID}/{APP_VER}
        """

        # If users do provide the Native URL they wll also want to add
        # ?token={APP_ACCESS_TOKEN} to the parameters at the end or the
        # URL will fail to load in later stages.
        result = re.match(
            r'^http(?P<secure>s)?://(?P<host>[^/]+)'
            r'/api/(?P<api_ver>v[1-9]*[0-9]+)'
            r'/dev/widget/update/'
            r'com\.lametric\.(?P<app_id>[0-9a-z.-]{1,64})'
            r'(/(?P<app_ver>[1-9][0-9]*))?/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            return NotifyLametric.parse_url(
                '{schema}://{app_id}{app_ver}/{params}'.format(
                    schema=NotifyLametric.secure_protocol
                    if result.group('secure') else NotifyLametric.protocol,
                    app_id=result.group('app_id'),
                    app_ver='/{}'.format(result.group('app_ver'))
                    if result.group('app_ver') else '',
                    params='' if not result.group('params')
                    else result.group('params')))

        return None
