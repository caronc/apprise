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

# Official API reference: https://developer.gitter.im/docs/user-resource

import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Used to break path apart into list of targets
TARGET_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


# Priorities
class ParsePlatformDevice:
    # All Devices
    ALL = 'all'

    # Apple IOS (APNS)
    IOS = 'ios'

    # Android/Firebase (FCM)
    ANDROID = 'android'


PARSE_PLATFORM_DEVICES = (
    ParsePlatformDevice.ALL,
    ParsePlatformDevice.IOS,
    ParsePlatformDevice.ANDROID,
)


class NotifyParsePlatform(NotifyBase):
    """
    A wrapper for Parse Platform Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Parse Platform'

    # The services URL
    service_url = ' https://parseplatform.org/'

    # insecure notifications (using http)
    protocol = 'parsep'

    # Secure notifications (using https)
    secure_protocol = 'parseps'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_parseplatform'

    # Define object templates
    templates = (
        '{schema}://{app_id}:{master_key}@{host}',
        '{schema}://{app_id}:{master_key}@{host}:{port}',
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
        'app_id': {
            'name': _('App ID'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'master_key': {
            'name': _('Master Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'device': {
            'name': _('Device'),
            'type': 'choice:string',
            'values': PARSE_PLATFORM_DEVICES,
            'default': ParsePlatformDevice.ALL,
        },
        'app_id': {
            'alias_of': 'app_id',
        },
        'master_key': {
            'alias_of': 'master_key',
        },
    })

    def __init__(self, app_id, master_key, device=None, **kwargs):
        """
        Initialize Parse Platform Object
        """
        super(NotifyParsePlatform, self).__init__(**kwargs)

        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, str):
            self.fullpath = '/'

        # Application ID
        self.application_id = validate_regex(app_id)
        if not self.application_id:
            msg = 'An invalid Parse Platform Application ID ' \
                  '({}) was specified.'.format(app_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Master Key
        self.master_key = validate_regex(master_key)
        if not self.master_key:
            msg = 'An invalid Parse Platform Master Key ' \
                  '({}) was specified.'.format(master_key)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Initialize Devices Array
        self.devices = []

        if device:
            self.device = device.lower()
            if device not in PARSE_PLATFORM_DEVICES:
                msg = 'An invalid Parse Platform device ' \
                      '({}) was specified.'.format(device)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.device = self.template_args['device']['default']

        if self.device == ParsePlatformDevice.ALL:
            self.devices = [d for d in PARSE_PLATFORM_DEVICES
                            if d != ParsePlatformDevice.ALL]
        else:
            # Store our device
            self.devices.append(device)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Parse Platform Notification
        """

        # Prepare our headers:
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'X-Parse-Application-Id': self.application_id,
            'X-Parse-Master-Key': self.master_key,
        }

        # prepare our payload
        payload = {
            'where': {
                'deviceType': {
                    '$in': self.devices,
                }
            },
            'data': {
                'title': title,
                'alert': body,
            }
        }

        # Set our schema
        schema = 'https' if self.secure else 'http'

        # Our Notification URL
        url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath.rstrip('/') + '/parse/push/'

        self.logger.debug('Parse Platform POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Parse Platform Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyParsePlatform.\
                    http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Parse Platform notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Parse Platform notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Parse Platform '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        params = {
            'device': self.device,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        default_port = 443 if self.secure else 80

        return \
            '{schema}://{app_id}:{master_key}@' \
            '{hostname}{port}{fullpath}/?{params}'.format(
                schema=self.secure_protocol if self.secure else self.protocol,
                app_id=self.pprint(self.application_id, privacy, safe=''),
                master_key=self.pprint(self.master_key, privacy, safe=''),
                hostname=NotifyParsePlatform.quote(self.host, safe=''),
                port='' if self.port is None or self.port == default_port
                     else ':{}'.format(self.port),
                fullpath=NotifyParsePlatform.quote(self.fullpath, safe='/'),
                params=NotifyParsePlatform.urlencode(params))

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

        # App ID is retrieved from the user
        results['app_id'] = NotifyParsePlatform.unquote(results['user'])

        # Master Key is retrieved from the password
        results['master_key'] = \
            NotifyParsePlatform.unquote(results['password'])

        # Device support override
        if 'device' in results['qsd'] and len(results['qsd']['device']):
            results['device'] = results['qsd']['device']

        # Allow app_id attribute over-ride
        if 'app_id' in results['qsd'] and len(results['qsd']['app_id']):
            results['app_id'] = results['qsd']['app_id']

        # Allow master_key attribute over-ride
        if 'master_key' in results['qsd'] \
                and len(results['qsd']['master_key']):
            results['master_key'] = results['qsd']['master_key']

        return results
