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

#
# API: https://github.com/Finb/bark-server/blob/master/docs/API_V2.md#python
#
import requests
import json

from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_list
from ..utils import parse_bool
from ..locale import gettext_lazy as _


# Sounds generated off of: https://github.com/Finb/Bark/tree/master/Sounds
BARK_SOUNDS = (
    "alarm.caf",
    "anticipate.caf",
    "bell.caf",
    "birdsong.caf",
    "bloom.caf",
    "calypso.caf",
    "chime.caf",
    "choo.caf",
    "descent.caf",
    "electronic.caf",
    "fanfare.caf",
    "glass.caf",
    "gotosleep.caf",
    "healthnotification.caf",
    "horn.caf",
    "ladder.caf",
    "mailsent.caf",
    "minuet.caf",
    "multiwayinvitation.caf",
    "newmail.caf",
    "newsflash.caf",
    "noir.caf",
    "paymentsuccess.caf",
    "shake.caf",
    "sherwoodforest.caf",
    "silence.caf",
    "spell.caf",
    "suspense.caf",
    "telegraph.caf",
    "tiptoes.caf",
    "typewriters.caf",
    "update.caf",
)


# Supported Level Entries
class NotifyBarkLevel:
    """
    Defines the Bark Level options
    """
    ACTIVE = 'active'

    TIME_SENSITIVE = 'timeSensitive'

    PASSIVE = 'passive'


BARK_LEVELS = (
    NotifyBarkLevel.ACTIVE,
    NotifyBarkLevel.TIME_SENSITIVE,
    NotifyBarkLevel.PASSIVE,
)


class NotifyBark(NotifyBase):
    """
    A wrapper for Notify Bark Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Bark'

    # The services URL
    service_url = 'https://github.com/Finb/Bark'

    # The default protocol
    protocol = 'bark'

    # The default secure protocol
    secure_protocol = 'barks'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_bark'

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # Define object templates
    templates = (
        '{schema}://{host}/{targets}',
        '{schema}://{host}:{port}/{targets}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
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
        'target_device': {
            'name': _('Target Device'),
            'type': 'string',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'sound': {
            'name': _('Sound'),
            'type': 'choice:string',
            'values': BARK_SOUNDS,
        },
        'level': {
            'name': _('Level'),
            'type': 'choice:string',
            'values': BARK_LEVELS,
        },
        'click': {
            'name': _('Click'),
            'type': 'string',
        },
        'badge': {
            'name': _('Badge'),
            'type': 'int',
            'min': 0,
        },
        'category': {
            'name': _('Category'),
            'type': 'string',
        },
        'group': {
            'name': _('Group'),
            'type': 'string',
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
    })

    def __init__(self, targets=None, include_image=True, sound=None,
                 category=None, group=None, level=None, click=None,
                 badge=None, **kwargs):
        """
        Initialize Notify Bark Object
        """
        super().__init__(**kwargs)

        # Prepare our URL
        self.notify_url = '%s://%s%s/push' % (
            'https' if self.secure else 'http',
            self.host,
            ':{}'.format(self.port)
            if (self.port and isinstance(self.port, int)) else '',
        )

        # Assign our category
        self.category = \
            category if isinstance(category, str) else None

        # Assign our group
        self.group = group if isinstance(group, str) else None

        # Initialize device list
        self.targets = parse_list(targets)

        # Place an image inline with the message body
        self.include_image = include_image

        # A clickthrough option for notifications
        self.click = click

        # Badge
        try:
            # Acquire our badge count if we can:
            #  - We accept both the integer form as well as a string
            #    representation
            self.badge = int(badge)
            if self.badge < 0:
                raise ValueError()

        except TypeError:
            # NoneType means use Default; this is an okay exception
            self.badge = None

        except ValueError:
            self.badge = None
            self.logger.warning(
                'The specified Bark badge ({}) is not valid ', badge)

        # Sound (easy-lookup)
        self.sound = None if not sound else next(
            (f for f in BARK_SOUNDS if f.startswith(sound.lower())), None)
        if sound and not self.sound:
            self.logger.warning(
                'The specified Bark sound ({}) was not found ', sound)

        # Level
        self.level = None if not level else next(
            (f for f in BARK_LEVELS if f[0] == level[0]), None)
        if level and not self.level:
            self.logger.warning(
                'The specified Bark level ({}) is not valid ', level)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Bark Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not self.targets:
            # We have nothing to notify; we're done
            self.logger.warning('There are no Bark devices to notify')
            return False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json; charset=utf-8',
        }

        # Prepare our payload (sample below)
        # {
        #     "body": "Test Bark Server",
        #     "device_key": "nysrshcqielvoxsa",
        #     "title": "bleem",
        #     "category": "category",
        #     "sound": "minuet.caf",
        #     "badge": 1,
        #     "icon": "https://day.app/assets/images/avatar.jpg",
        #     "group": "test",
        #     "url": "https://mritd.com"
        # }
        payload = {
            'title': title if title else self.app_desc,
            'body': body,
        }

        # Acquire our image url if configured to do so
        image_url = None if not self.include_image else \
            self.image_url(notify_type)

        if image_url:
            payload['icon'] = image_url

        if self.sound:
            payload['sound'] = self.sound

        if self.click:
            payload['url'] = self.click

        if self.badge:
            payload['badge'] = self.badge

        if self.level:
            payload['level'] = self.level

        if self.category:
            payload['category'] = self.category

        if self.group:
            payload['group'] = self.group

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Create a copy of the targets
        targets = list(self.targets)

        while len(targets) > 0:
            # Retrieve our device key
            target = targets.pop()

            payload['device_key'] = target
            self.logger.debug('Bark POST URL: %s (cert_verify=%r)' % (
                self.notify_url, self.verify_certificate,
            ))
            self.logger.debug('Bark Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=json.dumps(payload),
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBark.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Bark notification to {}: '
                        '{}{}error={}.'.format(
                            target,
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
                        'Sent Bark notification to {}.'.format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Bark '
                    'notification to {}.'.format(target))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user, self.password, self.host, self.port,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
        }

        if self.sound:
            params['sound'] = self.sound

        if self.click:
            params['click'] = self.click

        if self.badge:
            params['badge'] = str(self.badge)

        if self.level:
            params['level'] = self.level

        if self.category:
            params['category'] = self.category

        if self.group:
            params['group'] = self.group

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyBark.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyBark.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{targets}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='/'.join(
                [NotifyBark.quote('{}'.format(x)) for x in self.targets]),
            params=NotifyBark.urlencode(params),
        )

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

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Apply our targets
        results['targets'] = NotifyBark.split_path(results['fullpath'])

        # Category
        if 'category' in results['qsd'] and results['qsd']['category']:
            results['category'] = NotifyBark.unquote(
                results['qsd']['category'].strip())

        # Group
        if 'group' in results['qsd'] and results['qsd']['group']:
            results['group'] = NotifyBark.unquote(
                results['qsd']['group'].strip())

        # Badge
        if 'badge' in results['qsd'] and results['qsd']['badge']:
            results['badge'] = NotifyBark.unquote(
                results['qsd']['badge'].strip())

        # Level
        if 'level' in results['qsd'] and results['qsd']['level']:
            results['level'] = NotifyBark.unquote(
                results['qsd']['level'].strip())

        # Click (URL)
        if 'click' in results['qsd'] and results['qsd']['click']:
            results['click'] = NotifyBark.unquote(
                results['qsd']['click'].strip())

        # Sound
        if 'sound' in results['qsd'] and results['qsd']['sound']:
            results['sound'] = NotifyBark.unquote(
                results['qsd']['sound'].strip())

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyBark.parse_list(results['qsd']['to'])

        # use image= for consistency with the other plugins
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results
