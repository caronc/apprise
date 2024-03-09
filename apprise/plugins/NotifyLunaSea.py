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
# API:
#   https://docs.lunasea.app/lunasea/notifications/custom-notifications
#
import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..common import NotifyImageSize
from ..utils import parse_list
from ..utils import is_hostname
from ..utils import is_ipaddr
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _
from ..URLBase import PrivacyMode


class LunaSeaMode:
    """
    Define LunaSea Notification Modes
    """
    # App posts upstream to the developer API on LunaSea's website
    CLOUD = "cloud"

    # Running a dedicated private ntfy Server
    PRIVATE = "private"


LUNASEA_MODES = (
    LunaSeaMode.CLOUD,
    LunaSeaMode.PRIVATE,
)


class NotifyLunaSea(NotifyBase):
    """
    A wrapper for LunaSea Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'LunaSea'

    # The services URL
    service_url = 'https://luasea.app'

    # The default insecure protocol
    protocol = ('lunasea', 'lsea')

    # The default secure protocol
    secure_protocol = ('lunaseas', 'lseas')

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_lunasea'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # LunaSea Notification Details
    cloud_notify_url = 'https://notify.lunasea.app'
    notify_user_path = '/v1/custom/user/{}'
    notify_device_path = '/v1/custom/device/{}'

    # if our hostname matches the following we automatically enforce
    # cloud mode
    __auto_cloud_host = re.compile(r'(notify\.)?lunasea\.app', re.IGNORECASE)

    # Define object templates
    templates = (
        '{schema}://{targets}',
        '{schema}://{host}/{targets}',
        '{schema}://{host}:{port}/{targets}',
        '{schema}://{user}@{host}/{targets}',
        '{schema}://{user}@{host}:{port}/{targets}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
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
        'token': {
            'name': _('Token'),
            'type': 'string',
            'private': True,
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'target_device': {
            'name': _('Target Device'),
            'type': 'string',
            'prefix': '+',
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
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
        'mode': {
            'name': _('Mode'),
            'type': 'choice:string',
            'values': LUNASEA_MODES,
            'default': LunaSeaMode.PRIVATE,
        },
    })

    def __init__(self, targets=None, mode=None, token=None,
                 include_image=False, **kwargs):
        """
        Initialize LunaSea Object
        """
        super().__init__(**kwargs)

        # Show image associated with notification
        self.include_image = \
            self.template_args['image']['default'] \
            if include_image is None else include_image

        # Prepare our mode
        self.mode = mode.strip().lower() \
            if isinstance(mode, str) \
            else self.template_args['mode']['default']

        if self.mode not in LUNASEA_MODES:
            msg = 'An invalid LunaSea mode ({}) was specified.'.format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.targets = []
        for target in parse_list(targets):
            if len(target) < 4:
                self.logger.warning(
                    'A specified target ({}) is invalid and will be '
                    'ignored'.format(target))
                continue

            if target[0] == '+':
                # Device
                self.targets.append(('+', target[1:]))

            elif target[0] == '@':
                # User
                self.targets.append(('@', target[1:]))

            else:
                # User
                self.targets.append(('@', target))

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform LunaSea Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not len(self.targets):
            # We have nothing to notify; we're done
            self.logger.warning('There are no LunaSea targets to notify')
            return False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # prepare payload
        payload = {
            'title': title if title else self.app_desc,
            'body': body,
        }

        # Acquire image_url
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if image_url:
            payload['image'] = image_url

        # Prepare our Authentication (if defined)
        if self.user and self.password:
            auth = (self.user, self.password)

        else:
            # No Auth
            auth = None

        if self.mode == LunaSeaMode.CLOUD:
            # Cloud Service
            notify_url = self.cloud_notify_url

        else:
            # Local Hosting
            schema = 'https' if self.secure else 'http'

            notify_url = '%s://%s' % (schema, self.host)
            if isinstance(self.port, int):
                notify_url += ':%d' % self.port

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)

            if target[0] == '+':
                url = notify_url + self.notify_device_path.format(target[1])

            else:
                url = notify_url + self.notify_user_path.format(target[1])

            self.logger.debug('LunaSea POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('LunaSea Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                        requests.codes.ok, requests.codes.no_content):
                    # We had a problem
                    status_str = \
                        NotifyLunaSea.http_response_code_lookup(r.status_code)

                    self.logger.warning(
                        'Failed to deliver payload to LunaSea:'
                        '{}{}error={}.'.format(
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    has_error = True

                # otherwise we were successful
                continue

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred communicating with LunaSea.')
                self.logger.debug('Socket Exception: %s' % str(e))

                has_error = True

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        params = {
            'mode': self.mode,
            'image': 'yes' if self.include_image else 'no',
        }

        # Our URL parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyLunaSea.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret,
                    safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyLunaSea.quote(self.user, safe=''),
            )

        if self.mode == LunaSeaMode.PRIVATE:
            default_port = 443 if self.secure else 80
            return '{schema}://{auth}{host}{port}/{targets}?{params}'.format(
                schema=self.secure_protocol[0]
                if self.secure else self.protocol[0],
                auth=auth,
                host=self.host,
                port='' if self.port is None or self.port == default_port
                else ':{}'.format(self.port),
                targets='/'.join(
                    [NotifyLunaSea.quote(x[0] + x[1], safe='@+')
                     for x in self.targets]),
                params=NotifyLunaSea.urlencode(params)
            )

        else:  # Cloud mode
            return '{schema}://{auth}{targets}?{params}'.format(
                schema=self.protocol[0],
                auth=auth,
                targets='/'.join(
                    [NotifyLunaSea.quote(x[0] + x[1], safe='@+')
                     for x in self.targets]),
                params=NotifyLunaSea.urlencode(params)
            )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        # always return 1
        return 1 if not self.targets else len(self.targets)

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
        results['targets'] = NotifyLunaSea.split_path(results['fullpath'])

        # Boolean to include an image or not
        results['include_image'] = parse_bool(results['qsd'].get(
            'image', NotifyLunaSea.template_args['image']['default']))

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyLunaSea.parse_list(results['qsd']['to'])

        # Mode override
        if 'mode' in results['qsd'] and results['qsd']['mode']:
            results['mode'] = NotifyLunaSea.unquote(
                results['qsd']['mode'].strip().lower())

        else:
            # We can try to detect the mode based on the validity of the
            # hostname.
            #
            # This isn't a surfire way to do things though; it's best to
            # specify the mode= flag
            results['mode'] = LunaSeaMode.PRIVATE \
                if ((is_hostname(results['host'])
                    or is_ipaddr(results['host'])) and results['targets']) \
                else LunaSeaMode.CLOUD

        if results['mode'] == LunaSeaMode.CLOUD:
            # Store first entry as it can be a topic too in this case
            # But only if we also rule it out not being the words
            # lunasea.app itself, something that starts wiht an non-alpha
            # numeric character:
            if not NotifyLunaSea.__auto_cloud_host.search(results['host']):
                # Add it to the front of the list for consistency
                results['targets'].insert(0, results['host'])

        elif results['mode'] == LunaSeaMode.PRIVATE and \
                not (is_hostname(results['host'] or
                     is_ipaddr(results['host']))):
            # Invalid Host for LunaSeaMode.PRIVATE
            return None

        return results
