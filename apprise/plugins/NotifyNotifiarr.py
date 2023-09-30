# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

import re
import requests
from json import dumps
from itertools import chain

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _
from ..common import NotifyImageSize
from ..utils import parse_list

# Used to break path apart into list of channels
CHANNEL_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')

CHANNEL_REGEX = re.compile(
    r'^\s*(\#|\%35)?(?P<channel>[a-z0-9_-]+)', re.I)

USER_REGEX = re.compile(
    r'^\s*(\@|\%40)(?P<user>[a-z0-9_-]+)', re.I)

ROLE_REGEX = re.compile(
    r'^\s*(\+|\%2B)(?P<role>[a-z0-9_-]+)', re.I)

# For API Details see:
# https://notifiarr.wiki/Client/Installation


class NotifyNotifiarr(NotifyBase):
    """
    A wrapper for Notifiarr Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Notifiarr'

    # The services URL
    service_url = 'https://notifiarr.com/'

    # The default protocol
    protocol = ('nfiarr', 'notifiarr')

    # The default secure protocol
    secure_protocol = ('nfiarrs', 'notifiarrs')

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_notifiarr'

    # Disable throttle rate for Notifiarr requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # Define object templates
    templates = (
        '{schema}://{host}/{apikey}/{targets}',
        '{schema}://{host}:{port}/{apikey}/{targets}',
        '{schema}://{user}@{host}/{apikey}/{targets}',
        '{schema}://{user}@{host}:{port}/{apikey}/{targets}',
        '{schema}://{user}:{password}@{host}/{apikey}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{apikey}/{targets}',
    )

    # Define our apikeys; these are the minimum apikeys required required to
    # be passed into this function (as arguments). The syntax appends any
    # previously defined in the base package and builds onto them
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
        'apikey': {
            'name': _('Token'),
            'type': 'string',
            'required': True,
            'private': True,
        },
        'target_role': {
            'name': _('Target Role'),
            'type': 'string',
            'prefix': '+',
            'map_to': 'targets',
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'target_channels': {
            'name': _('Target Channel'),
            'type': 'string',
            'prefix': '#',
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
        'key': {
            'alias_of': 'apikey',
        },
        'apikey': {
            'alias_of': 'apikey',
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
    }

    def __init__(self, apikey=None, headers=None, include_image=None,
                 targets=None, **kwargs):
        """
        Initialize Notifiarr Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with

        """
        super().__init__(**kwargs)

        self.apikey = apikey
        if not self.apikey:
            msg = 'An invalid Notifiarr APIKey ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Place a thumbnail image inline with the message body
        self.include_image = include_image \
            if isinstance(include_image, bool) \
            else self.template_args['image']['default']

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        # Prepare our targets
        self.targets = {
            'channels': [],
            'users': [],
            'roles': [],
            'invalid': [],
        }

        for target in parse_list(targets):

            result = USER_REGEX.match(target)
            if result:
                # Store user information
                self.targets['users'].append(result.group('user'))
                continue

            result = ROLE_REGEX.match(target)
            if result:
                # Store role information
                self.targets['roles'].append(result.group('role'))
                continue

            result = CHANNEL_REGEX.match(target)
            if result:
                # Store role information
                self.targets['channels'].append(result.group('channel'))
                continue

            self.logger.warning(
                'Dropped invalid phone/group/contact '
                '({}) specified.'.format(target),
            )
            self.targets['invalid'].append(target)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no'
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyNotifiarr.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyNotifiarr.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{apikey}' \
            '/{targets}?{params}'.format(
                schema=self.secure_protocol[0]
                if self.secure else self.protocol[0],
                auth=auth,
                # never encode hostname since we're expecting it to be a valid
                # one
                hostname=self.host,
                port='' if self.port is None or self.port == default_port
                     else ':{}'.format(self.port),
                apikey=self.pprint(self.apikey, privacy, safe=''),
                targets='/'.join(
                    [NotifyNotifiarr.quote(x, safe='+#@') for x in chain(
                        # Channels
                        ['#{}'.format(x) for x in self.targets['channels']],
                        # Users
                        ['@{}'.format(x) for x in self.targets['users']],
                        # Users
                        ['+{}'.format(x) for x in self.targets['roles']],
                        # Pass along the same invalid entries as were provided
                        self.targets['invalid'],
                    )]),
                params=NotifyNotifiarr.urlencode(params),
            )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Notifiarr Notification
        """

        if not self.targets['channels'] and not self.targets['users'] \
                and not self.targets['roles']:
            # There were no services to notify
            self.logger.warning(
                'There were no Notifiarr targets to notify.')
            return False

        # Prepare HTTP Headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Accept': 'text/plain'
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        # Acquire image_url
        image_url = self.image_url(notify_type)

        # prepare Notifiarr Object
        payload = {
            'text': body,
        }

        # Prepare our parameters
        payload = {
            'notification': {
                'update': False,
                'name': self.app_id,
                'event': 0
            },
            'discord': {
                'color': self.color(notify_type),
                'ping': {
                    'pingUser': None,  # TODO
                    'pingRole': None,  # TODO
                },
                'text': {
                    'title': title,
                    'content': '',
                    'description': body,
                },
                'ids': {
                    'channel': None,  # TODO
                }
            }
        }

        if self.include_image and image_url:
            payload['text']['icon'] = image_url

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        # append the passthrough URL
        url += f'/api/v1/notification/passthrough/{self.apikey}'

        self.logger.debug('Notifiarr POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Notifiarr Payload: %s' % str(payload))

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
            if r.status_code < 200 or r.status_code >= 300:
                # We had a problem
                status_str = \
                    NotifyNotifiarr.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Notifiarr %s notification: '
                    '%serror=%s.',
                    status_str,
                    ', ' if status_str else '',
                    str(r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Notifiarr notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Notifiarr '
                'Chat notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

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

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results['headers'] = {
            NotifyNotifiarr.unquote(x): NotifyNotifiarr.unquote(y)
            for x, y in results['qsd+'].items()}

        # Get unquoted entries
        entries = NotifyNotifiarr.split_path(results['fullpath'])

        # Set our apikey if found as an argument
        if 'apikey' in results['qsd'] and len(results['qsd']['apikey']):
            results['apikey'] = \
                NotifyNotifiarr.unquote(results['qsd']['apikey'])

        elif 'key' in results['qsd'] and len(results['qsd']['key']):
            results['apikey'] = \
                NotifyNotifiarr.unquote(results['qsd']['key'])

        elif entries:
            # Pop the first element (this is the api key)
            results['apikey'] = entries.pop(0)

        # the remaining items are our targets
        results['targets'] = entries

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += [x for x in filter(
                bool, CHANNEL_LIST_DELIM.split(
                    NotifyNotifiarr.unquote(results['qsd']['to'])))]

        return results
