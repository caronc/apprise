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

import re
import requests
from json import dumps
from itertools import chain

from .base import NotifyBase
from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..common import NotifyImageSize
from ..utils.parse import parse_list, parse_bool, validate_regex
from .discord import USER_ROLE_DETECTION_RE

# Used to break path apart into list of channels
CHANNEL_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')

CHANNEL_REGEX = re.compile(
    r'^\s*(\#|\%35)?(?P<channel>[0-9]+)', re.I)

# For API Details see:
# https://notifiarr.wiki/Client/Installation

# Another good example:
# https://notifiarr.wiki/en/Website/ \
#              Integrations/Passthrough#payload-example-1


class NotifyNotifiarr(NotifyBase):
    """
    A wrapper for Notifiarr Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Notifiarr'

    # The services URL
    service_url = 'https://notifiarr.com/'

    # The default secure protocol
    secure_protocol = 'notifiarr'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_notifiarr'

    # The Notification URL
    notify_url = 'https://notifiarr.com/api/v1/notification/apprise'

    # Notifiarr Throttling (knowing in advance reduces 429 responses)
    # define('NOTIFICATION_LIMIT_SECOND_USER', 5);
    # define('NOTIFICATION_LIMIT_SECOND_PATRON', 15);

    # Throttle requests ever so slightly
    request_rate_per_sec = 0.04

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # Define object templates
    templates = (
        '{schema}://{apikey}/{targets}',
    )

    # Define our apikeys; these are the minimum apikeys required required to
    # be passed into this function (as arguments). The syntax appends any
    # previously defined in the base package and builds onto them
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('Token'),
            'type': 'string',
            'required': True,
            'private': True,
        },
        'target_channel': {
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
        'event': {
            'name': _('Discord Event ID'),
            'type': 'int',
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
        'source': {
            'name': _('Source'),
            'type': 'string',
        },
        'from': {
            'alias_of': 'source'
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, apikey=None, include_image=None,
                 event=None, targets=None, source=None, **kwargs):
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

        # Prepare our source (if set)
        self.source = validate_regex(source)

        self.event = 0
        if event:
            try:
                self.event = int(event)

            except (ValueError, TypeError):
                msg = 'An invalid Notifiarr Discord Event ID ' \
                      '({}) was specified.'.format(event)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Prepare our targets
        self.targets = {
            'channels': [],
            'invalid': [],
        }

        for target in parse_list(targets):
            result = CHANNEL_REGEX.match(target)
            if result:
                # Store role information
                self.targets['channels'].append(int(result.group('channel')))
                continue

            self.logger.warning(
                'Dropped invalid channel '
                '({}) specified.'.format(target),
            )
            self.targets['invalid'].append(target)

        return

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.apikey,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
        }

        if self.source:
            params['source'] = self.source

        if self.event:
            params['event'] = self.event

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{apikey}' \
            '/{targets}?{params}'.format(
                schema=self.secure_protocol,
                apikey=self.pprint(self.apikey, privacy, safe=''),
                targets='/'.join(
                    [NotifyNotifiarr.quote(x, safe='+#@') for x in chain(
                        # Channels
                        ['#{}'.format(x) for x in self.targets['channels']],
                        # Pass along the same invalid entries as were provided
                        self.targets['invalid'],
                    )]),
                params=NotifyNotifiarr.urlencode(params),
            )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Notifiarr Notification
        """

        if not self.targets['channels']:
            # There were no services to notify
            self.logger.warning(
                'There were no Notifiarr channels to notify.')
            return False

        # No error to start with
        has_error = False

        # Acquire image_url
        image_url = self.image_url(notify_type)

        # Define our mentions
        mentions = {
            'pingUser': [],
            'pingRole': [],
            'content': [],
        }

        # parse for user id's <@123> and role IDs <@&456>
        results = USER_ROLE_DETECTION_RE.findall(body)
        if results:
            for (is_role, no, value) in results:
                if value:
                    # @everybody, @admin, etc - unsupported
                    mentions['content'].append(f'@{value}')

                elif is_role:
                    mentions['pingRole'].append(no)
                    mentions['content'].append(f'<@&{no}>')

                else:  # is_user
                    mentions['pingUser'].append(no)
                    mentions['content'].append(f'<@{no}>')

        for idx, channel in enumerate(self.targets['channels']):
            # prepare Notifiarr Object
            payload = {
                'source': self.source if self.source else self.app_id,
                'type': notify_type,
                'notification': {
                    'update': True if self.event else False,
                    'name': self.app_id,
                    'event': str(self.event)
                    if self.event else "",
                },
                'discord': {
                    'color': self.color(notify_type),
                    'ping': {
                        # Only 1 user is supported, so truncate the rest
                        'pingUser': 0 if not mentions['pingUser']
                        else mentions['pingUser'][0],
                        # Only 1 role is supported, so truncate the rest
                        'pingRole': 0 if not mentions['pingRole']
                        else mentions['pingRole'][0],
                    },
                    'text': {
                        'title': title,
                        'content': '' if not mentions['content']
                        else '👉 ' + ' '.join(mentions['content']),
                        'description': body,
                        'footer': self.app_desc,
                    },
                    'ids': {
                        'channel': channel,
                    }
                }
            }

            if self.include_image and image_url:
                payload['discord']['text']['icon'] = image_url
                payload['discord']['images'] = {
                    'thumbnail': image_url,
                }

            if not self._send(payload):
                has_error = True

        return not has_error

    def _send(self, payload):
        """
        Send notification
        """
        self.logger.debug('Notifiarr POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Notifiarr Payload: %s' % str(payload))

        # Prepare HTTP Headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Accept': 'text/plain',
            'X-api-Key': self.apikey,
        }

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
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

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets['channels']) + len(self.targets['invalid'])
        return targets if targets > 0 else 1

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

        # Get channels
        results['targets'] = NotifyNotifiarr.split_path(results['fullpath'])

        if 'event' in results['qsd'] and \
                len(results['qsd']['event']):
            results['event'] = \
                NotifyNotifiarr.unquote(results['qsd']['event'])

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', False))

        # Track if we need to extract the hostname as a target
        host_is_potential_target = False

        if 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifyNotifiarr.unquote(results['qsd']['source'])

        elif 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyNotifiarr.unquote(results['qsd']['from'])

        # Set our apikey if found as an argument
        if 'apikey' in results['qsd'] and len(results['qsd']['apikey']):
            results['apikey'] = \
                NotifyNotifiarr.unquote(results['qsd']['apikey'])

            host_is_potential_target = True

        elif 'key' in results['qsd'] and len(results['qsd']['key']):
            results['apikey'] = \
                NotifyNotifiarr.unquote(results['qsd']['key'])

            host_is_potential_target = True

        else:
            # Pop the first element (this is the api key)
            results['apikey'] = \
                NotifyNotifiarr.unquote(results['host'])

        if host_is_potential_target is True and results['host']:
            results['targets'].append(NotifyNotifiarr.unquote(results['host']))

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += [x for x in filter(
                bool, CHANNEL_LIST_DELIM.split(
                    NotifyNotifiarr.unquote(results['qsd']['to'])))]

        return results
