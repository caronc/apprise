# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

import requests
from json import loads

from .base import NotifyBase
from .. import exception
from ..common import NotifyType
from ..utils.parse import parse_list, validate_regex
from ..locale import gettext_lazy as _


class PushSaferSound:
    """
    Defines all of the supported PushSafe sounds
    """
    # Silent
    SILENT = 0
    # Ahem (IM)
    AHEM = 1
    # Applause (Mail)
    APPLAUSE = 2
    # Arrow (Reminder)
    ARROW = 3
    # Baby (SMS)
    BABY = 4
    # Bell (Alarm)
    BELL = 5
    # Bicycle (Alarm2)
    BICYCLE = 6
    # Boing (Alarm3)
    BOING = 7
    # Buzzer (Alarm4)
    BUZZER = 8
    # Camera (Alarm5)
    CAMERA = 9
    # Car Horn (Alarm6)
    CAR_HORN = 10
    # Cash Register (Alarm7)
    CASH_REGISTER = 11
    # Chime (Alarm8)
    CHIME = 12
    # Creaky Door (Alarm9)
    CREAKY_DOOR = 13
    # Cuckoo Clock (Alarm10)
    CUCKOO_CLOCK = 14
    # Disconnect (Call)
    DISCONNECT = 15
    # Dog (Call2)
    DOG = 16
    # Doorbell (Call3)
    DOORBELL = 17
    # Fanfare (Call4)
    FANFARE = 18
    # Gun Shot (Call5)
    GUN_SHOT = 19
    # Honk (Call6)
    HONK = 20
    # Jaw Harp (Call7)
    JAW_HARP = 21
    # Morse (Call8)
    MORSE = 22
    # Electricity (Call9)
    ELECTRICITY = 23
    # Radio Tuner (Call10)
    RADIO_TURNER = 24
    # Sirens
    SIRENS = 25
    # Military Trumpets
    MILITARY_TRUMPETS = 26
    # Ufo
    UFO = 27
    # Whah Whah Whah
    LONG_WHAH = 28
    # Man Saying Goodbye
    GOODBYE = 29
    # Man Saying Hello
    HELLO = 30
    # Man Saying No
    NO = 31
    # Man Saying Ok
    OKAY = 32
    # Man Saying Ooohhhweee
    OOOHHHWEEE = 33
    # Man Saying Warning
    WARNING = 34
    # Man Saying Welcome
    WELCOME = 35
    # Man Saying Yeah
    YEAH = 36
    # Man Saying Yes
    YES = 37
    # Beep short
    BEEP1 = 38
    # Weeeee short
    WEEE = 39
    # Cut in and out short
    CUTINOUT = 40
    # Finger flicking glas short
    FLICK_GLASS = 41
    # Wa Wa Waaaa short
    SHORT_WHAH = 42
    # Laser short
    LASER = 43
    # Wind Chime short
    WIND_CHIME = 44
    # Echo short
    ECHO = 45
    # Zipper short
    ZIPPER = 46
    # HiHat short
    HIHAT = 47
    # Beep 2 short
    BEEP2 = 48
    # Beep 3 short
    BEEP3 = 49
    # Beep 4 short
    BEEP4 = 50
    # The Alarm is armed
    ALARM_ARMED = 51
    # The Alarm is disarmed
    ALARM_DISARMED = 52
    # The Backup is ready
    BACKUP_READY = 53
    # The Door is closed
    DOOR_CLOSED = 54
    # The Door is opend
    DOOR_OPENED = 55
    # The Window is closed
    WINDOW_CLOSED = 56
    # The Window is open
    WINDOW_OPEN = 57
    # The Light is off
    LIGHT_ON = 58
    # The Light is on
    LIGHT_OFF = 59
    # The Doorbell rings
    DOORBELL_RANG = 60


PUSHSAFER_SOUND_MAP = {
    # Device Default,
    'silent': PushSaferSound.SILENT,
    'ahem': PushSaferSound.AHEM,
    'applause': PushSaferSound.APPLAUSE,
    'arrow': PushSaferSound.ARROW,
    'baby': PushSaferSound.BABY,
    'bell': PushSaferSound.BELL,
    'bicycle': PushSaferSound.BICYCLE,
    'bike': PushSaferSound.BICYCLE,
    'boing': PushSaferSound.BOING,
    'buzzer': PushSaferSound.BUZZER,
    'camera': PushSaferSound.CAMERA,
    'carhorn': PushSaferSound.CAR_HORN,
    'horn': PushSaferSound.CAR_HORN,
    'cashregister': PushSaferSound.CASH_REGISTER,
    'chime': PushSaferSound.CHIME,
    'creakydoor': PushSaferSound.CREAKY_DOOR,
    'cuckooclock': PushSaferSound.CUCKOO_CLOCK,
    'cuckoo': PushSaferSound.CUCKOO_CLOCK,
    'disconnect': PushSaferSound.DISCONNECT,
    'dog': PushSaferSound.DOG,
    'doorbell': PushSaferSound.DOORBELL,
    'fanfare': PushSaferSound.FANFARE,
    'gunshot': PushSaferSound.GUN_SHOT,
    'honk': PushSaferSound.HONK,
    'jawharp': PushSaferSound.JAW_HARP,
    'morse': PushSaferSound.MORSE,
    'electric': PushSaferSound.ELECTRICITY,
    'radiotuner': PushSaferSound.RADIO_TURNER,
    'sirens': PushSaferSound.SIRENS,
    'militarytrumpets': PushSaferSound.MILITARY_TRUMPETS,
    'military': PushSaferSound.MILITARY_TRUMPETS,
    'trumpets': PushSaferSound.MILITARY_TRUMPETS,
    'ufo': PushSaferSound.UFO,
    'whahwhah': PushSaferSound.LONG_WHAH,
    'whah': PushSaferSound.SHORT_WHAH,
    'goodye': PushSaferSound.GOODBYE,
    'hello': PushSaferSound.HELLO,
    'no': PushSaferSound.NO,
    'okay': PushSaferSound.OKAY,
    'ok': PushSaferSound.OKAY,
    'ooohhhweee': PushSaferSound.OOOHHHWEEE,
    'warn': PushSaferSound.WARNING,
    'warning': PushSaferSound.WARNING,
    'welcome': PushSaferSound.WELCOME,
    'yeah': PushSaferSound.YEAH,
    'yes': PushSaferSound.YES,
    'beep': PushSaferSound.BEEP1,
    'beep1': PushSaferSound.BEEP1,
    'weee': PushSaferSound.WEEE,
    'wee': PushSaferSound.WEEE,
    'cutinout': PushSaferSound.CUTINOUT,
    'flickglass': PushSaferSound.FLICK_GLASS,
    'laser': PushSaferSound.LASER,
    'windchime': PushSaferSound.WIND_CHIME,
    'echo': PushSaferSound.ECHO,
    'zipper': PushSaferSound.ZIPPER,
    'hihat': PushSaferSound.HIHAT,
    'beep2': PushSaferSound.BEEP2,
    'beep3': PushSaferSound.BEEP3,
    'beep4': PushSaferSound.BEEP4,
    'alarmarmed': PushSaferSound.ALARM_ARMED,
    'armed': PushSaferSound.ALARM_ARMED,
    'alarmdisarmed': PushSaferSound.ALARM_DISARMED,
    'disarmed': PushSaferSound.ALARM_DISARMED,
    'backupready': PushSaferSound.BACKUP_READY,
    'dooropen': PushSaferSound.DOOR_OPENED,
    'dopen': PushSaferSound.DOOR_OPENED,
    'doorclosed': PushSaferSound.DOOR_CLOSED,
    'dclosed': PushSaferSound.DOOR_CLOSED,
    'windowopen': PushSaferSound.WINDOW_OPEN,
    'wopen': PushSaferSound.WINDOW_OPEN,
    'windowclosed': PushSaferSound.WINDOW_CLOSED,
    'wclosed': PushSaferSound.WINDOW_CLOSED,
    'lighton': PushSaferSound.LIGHT_ON,
    'lon': PushSaferSound.LIGHT_ON,
    'lightoff': PushSaferSound.LIGHT_OFF,
    'loff': PushSaferSound.LIGHT_OFF,
    'doorbellrang': PushSaferSound.DOORBELL_RANG,
}


# Priorities
class PushSaferPriority:
    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


PUSHSAFER_PRIORITIES = (
    PushSaferPriority.LOW,
    PushSaferPriority.MODERATE,
    PushSaferPriority.NORMAL,
    PushSaferPriority.HIGH,
    PushSaferPriority.EMERGENCY,
)

PUSHSAFER_PRIORITY_MAP = {
    # short for 'low'
    'low': PushSaferPriority.LOW,
    # short for 'medium'
    'medium': PushSaferPriority.MODERATE,
    # short for 'normal'
    'normal': PushSaferPriority.NORMAL,
    # short for 'high'
    'high': PushSaferPriority.HIGH,
    # short for 'emergency'
    'emergency': PushSaferPriority.EMERGENCY,
}

# Identify the priority ou want to designate as the fall back
DEFAULT_PRIORITY = "normal"


# Vibrations
class PushSaferVibration:
    """
    Defines the acceptable vibration settings for notification
    """
    # x1
    LOW = 1
    # x2
    NORMAL = 2
    # x3
    HIGH = 3


# Identify all of the vibrations in one place
PUSHSAFER_VIBRATIONS = (
    PushSaferVibration.LOW,
    PushSaferVibration.NORMAL,
    PushSaferVibration.HIGH,
)

# At this time, the following pictures can be attached to each notification
# at one time. When more are supported, just add their argument below
PICTURE_PARAMETER = (
    'p',
    'p2',
    'p3',
)


# Flag used as a placeholder to sending to all devices
PUSHSAFER_SEND_TO_ALL = 'a'


class NotifyPushSafer(NotifyBase):
    """
    A wrapper for PushSafer Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushsafer'

    # The services URL
    service_url = 'https://www.pushsafer.com/'

    # The default insecure protocol
    protocol = 'psafer'

    # The default secure protocol
    secure_protocol = 'psafers'

    # Support attachments
    attachment_support = True

    # Number of requests to a allow per second
    request_rate_per_sec = 1.2

    # The icon ID of 25 looks like a megaphone
    default_pushsafer_icon = 25

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushsafer'

    # Defines the hostname to post content to; since this service supports
    # both insecure and secure methods, we set the {schema} just before we
    # post the message upstream.
    notify_url = '{schema}://www.pushsafer.com/api'

    # Define object templates
    templates = (
        '{schema}://{privatekey}',
        '{schema}://{privatekey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'privatekey': {
            'name': _('Private Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_device': {
            'name': _('Target Device'),
            'type': 'string',
            'map_to': 'targets',
        },
        'target_email': {
            'name': _('Target Email'),
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
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'values': PUSHSAFER_PRIORITIES,
        },
        'sound': {
            'name': _('Sound'),
            'type': 'choice:string',
            'values': PUSHSAFER_SOUND_MAP,
        },
        'vibration': {
            'name': _('Vibration'),
            'type': 'choice:int',
            'values': PUSHSAFER_VIBRATIONS,
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, privatekey, targets=None, priority=None, sound=None,
                 vibration=None, **kwargs):
        """
        Initialize PushSafer Object
        """
        super().__init__(**kwargs)

        #
        # Priority
        #
        try:
            # Acquire our priority if we can:
            #  - We accept both the integer form as well as a string
            #    representation
            self.priority = int(priority)

        except TypeError:
            # NoneType means use Default; this is an okay exception
            self.priority = None

        except ValueError:
            # Input is a string; attempt to get the lookup from our
            # priority mapping
            priority = priority.lower().strip()

            # This little bit of black magic allows us to match against
            # low, lo, l (for low);
            # normal, norma, norm, nor, no, n (for normal)
            # ... etc
            match = next((key for key in PUSHSAFER_PRIORITY_MAP.keys()
                         if key.startswith(priority)), None) \
                if priority else None

            # Now test to see if we got a match
            if not match:
                msg = 'An invalid PushSafer priority ' \
                      '({}) was specified.'.format(priority)
                self.logger.warning(msg)
                raise TypeError(msg)

            # store our successfully looked up priority
            self.priority = PUSHSAFER_PRIORITY_MAP[match]

        if self.priority is not None and \
                self.priority not in PUSHSAFER_PRIORITY_MAP.values():
            msg = 'An invalid PushSafer priority ' \
                  '({}) was specified.'.format(priority)
            self.logger.warning(msg)
            raise TypeError(msg)

        #
        # Sound
        #
        try:
            # Acquire our sound if we can:
            #  - We accept both the integer form as well as a string
            #    representation
            self.sound = int(sound)

        except TypeError:
            # NoneType means use Default; this is an okay exception
            self.sound = None

        except ValueError:
            # Input is a string; attempt to get the lookup from our
            # sound mapping
            sound = sound.lower().strip()

            # This little bit of black magic allows us to match against
            # against multiple versions of the same string
            # ... etc
            match = next((key for key in PUSHSAFER_SOUND_MAP.keys()
                         if key.startswith(sound)), None) \
                if sound else None

            # Now test to see if we got a match
            if not match:
                msg = 'An invalid PushSafer sound ' \
                      '({}) was specified.'.format(sound)
                self.logger.warning(msg)
                raise TypeError(msg)

            # store our successfully looked up sound
            self.sound = PUSHSAFER_SOUND_MAP[match]

        if self.sound is not None and \
                self.sound not in PUSHSAFER_SOUND_MAP.values():
            msg = 'An invalid PushSafer sound ' \
                  '({}) was specified.'.format(sound)
            self.logger.warning(msg)
            raise TypeError(msg)

        #
        # Vibration
        #
        try:
            # Use defined integer as is if defined, no further error checking
            # is performed
            self.vibration = int(vibration)

        except TypeError:
            # NoneType means use Default; this is an okay exception
            self.vibration = None

        except ValueError:
            msg = 'An invalid PushSafer vibration ' \
                  '({}) was specified.'.format(vibration)
            self.logger.warning(msg)
            raise TypeError(msg)

        if self.vibration and self.vibration not in PUSHSAFER_VIBRATIONS:
            msg = 'An invalid PushSafer vibration ' \
                  '({}) was specified.'.format(vibration)
            self.logger.warning(msg)
            raise TypeError(msg)

        #
        # Private Key (associated with project)
        #
        self.privatekey = validate_regex(privatekey)
        if not self.privatekey:
            msg = 'An invalid PushSafer Private Key ' \
                  '({}) was specified.'.format(privatekey)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.targets = parse_list(targets)
        if len(self.targets) == 0:
            self.targets = (PUSHSAFER_SEND_TO_ALL, )

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform PushSafer Notification
        """

        # error tracking (used for function return)
        has_error = False

        # Initialize our list of attachments
        attachments = []

        if attach and self.attachment_support:
            # We need to upload our payload first so that we can source it
            # in remaining messages
            for no, attachment in enumerate(attach, start=1):
                # prepare payload
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access PushSafer attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                if not attachment.mimetype.startswith('image/'):
                    # Attachment not supported; continue peacefully
                    self.logger.debug(
                        'Ignoring unsupported PushSafer attachment {}.'.format(
                            attachment.url(privacy=True)))
                    continue

                self.logger.debug(
                    'Posting PushSafer attachment {}'.format(
                        attachment.url(privacy=True)))

                try:
                    # Output must be in a DataURL format (that's what
                    # PushSafer calls it):
                    attachments.append((
                        attachment.name
                        if attachment.name else f'file{no:03}.dat',
                        'data:{};base64,{}'.format(
                            attachment.mimetype,
                            attachment.base64(),
                        )
                    ))

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access PushSafer attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                self.logger.debug(
                    'Appending PushSafer attachment {}'.format(
                        attachment.url(privacy=True)))

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            recipient = targets.pop(0)

            # prepare payload
            payload = {
                't': title,
                'm': body,
                # Our default icon to use
                'i': self.default_pushsafer_icon,
                # Notification Color
                'c': self.color(notify_type),
                # Target Recipient
                'd': recipient,
            }

            if self.sound is not None:
                # Only apply sound setting if it was specified
                payload['s'] = str(self.sound)

            if self.vibration is not None:
                # Only apply vibration setting
                payload['v'] = str(self.vibration)

            if not attachments:
                okay, response = self._send(payload)
                if not okay:
                    has_error = True
                    continue

                self.logger.info(
                    'Sent PushSafer notification to "%s".' % (recipient))

            else:
                # Create a copy of our payload object
                _payload = payload.copy()

                for idx in range(
                        0, len(attachments), len(PICTURE_PARAMETER)):
                    # Send our attachments to our same user (already prepared
                    # as our payload object)
                    for c, attachment in enumerate(
                            attachments[idx:idx + len(PICTURE_PARAMETER)]):

                        # Get our attachment information
                        filename, dataurl = attachment
                        _payload.update({PICTURE_PARAMETER[c]: dataurl})

                        self.logger.debug(
                            'Added attachment (%s) to "%s".' % (
                                filename, recipient))

                    okay, response = self._send(_payload)
                    if not okay:
                        has_error = True
                        continue

                    self.logger.info(
                        'Sent PushSafer attachment (%s) to "%s".' % (
                            filename, recipient))

                    # More then the maximum messages shouldn't cause all of
                    # the text to loop on future iterations
                    _payload = payload.copy()
                    _payload['t'] = ''
                    _payload['m'] = '...'

        return not has_error

    def _send(self, payload, **kwargs):
        """
        Wrapper to the requests (post) object
        """

        headers = {
            'User-Agent': self.app_id,
        }

        # Prepare the notification URL to post to
        notify_url = self.notify_url.format(
            schema='https' if self.secure else 'http'
        )

        # Store the payload key
        payload['k'] = self.privatekey

        self.logger.debug('PushSafer POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('PushSafer Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Default response type
        response = None

        # Initialize our Pushsafer expected responses
        _code = None
        _str = 'Unknown'

        try:
            # Open our attachment path if required:
            r = requests.post(
                notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            try:
                response = loads(r.content)
                _code = response.get('status')
                _str = response.get('success', _str) \
                    if _code == 1 else response.get('error', _str)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None

                # Fall back to the existing unparsed value
                response = r.content

            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):
                # We had a problem
                status_str = \
                    NotifyPushSafer.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to deliver payload to PushSafer:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False, response

            elif _code != 1:
                # It's a bit backwards, but:
                #    1 is returned if we succeed
                #    0 is returned if we fail
                self.logger.warning(
                    'Failed to deliver payload to PushSafer;'
                    ' error={}.'.format(_str))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False, response

            # otherwise we were successful
            return True, response

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred communicating with PushSafer.')
            self.logger.debug('Socket Exception: %s' % str(e))

            return False, response

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.privatekey,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.priority is not None:
            # Store our priority; but only if it was specified
            params['priority'] = \
                next((key for key, value in PUSHSAFER_PRIORITY_MAP.items()
                      if value == self.priority),
                     DEFAULT_PRIORITY)  # pragma: no cover

        if self.sound is not None:
            # Store our sound; but only if it was specified
            params['sound'] = \
                next((key for key, value in PUSHSAFER_SOUND_MAP.items()
                      if value == self.sound), '')  # pragma: no cover

        if self.vibration is not None:
            # Store our vibration; but only if it was specified
            params['vibration'] = str(self.vibration)

        targets = '/'.join([NotifyPushSafer.quote(x) for x in self.targets])
        if targets == PUSHSAFER_SEND_TO_ALL:
            # keyword is reserved for internal usage only; it's safe to remove
            # it from the recipients list
            targets = ''

        return '{schema}://{privatekey}/{targets}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            privatekey=self.pprint(self.privatekey, privacy, safe=''),
            targets=targets,
            params=NotifyPushSafer.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return len(self.targets)

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

        # Fetch our targets
        results['targets'] = \
            NotifyPushSafer.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPushSafer.parse_list(results['qsd']['to'])

        # Setup the token; we store it in Private Key for global
        # plugin consistency with naming conventions
        results['privatekey'] = NotifyPushSafer.unquote(results['host'])

        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyPushSafer.unquote(results['qsd']['priority'])

        if 'sound' in results['qsd'] and len(results['qsd']['sound']):
            results['sound'] = \
                NotifyPushSafer.unquote(results['qsd']['sound'])

        if 'vibration' in results['qsd'] and len(results['qsd']['vibration']):
            results['vibration'] = \
                NotifyPushSafer.unquote(results['qsd']['vibration'])

        return results
