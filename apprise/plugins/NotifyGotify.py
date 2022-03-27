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

# For this plugin to work correct, the Gotify server must be set up to allow
# for remote connections.

# Gotify Docker configuration: https://hub.docker.com/r/gotify/server
# Example: https://github.com/gotify/server/blob/\
#        f2c2688f0b5e6a816bbcec768ca1c0de5af76b88/ADD_MESSAGE_EXAMPLES.md#python
# API: https://gotify.net/docs/swagger-docs

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType, NotifyFormat
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


# Priorities
class GotifyPriority(object):
    LOW = 0
    MODERATE = 3
    NORMAL = 5
    HIGH = 8
    EMERGENCY = 10


GOTIFY_PRIORITIES = (
    GotifyPriority.LOW,
    GotifyPriority.MODERATE,
    GotifyPriority.NORMAL,
    GotifyPriority.HIGH,
    GotifyPriority.EMERGENCY,
)


class NotifyGotify(NotifyBase):
    """
    A wrapper for Gotify Notifications
    """
    # The default descriptive name associated with the Notification
    service_name = 'Gotify'

    # The services URL
    service_url = 'https://github.com/gotify/server'

    # The default protocol
    protocol = 'gotify'

    # The default secure protocol
    secure_protocol = 'gotifys'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_gotify'

    # Disable throttle rate
    request_rate_per_sec = 0

    # Define object templates
    templates = (
        '{schema}://{host}/{token}',
        '{schema}://{host}:{port}/{token}',
        '{schema}://{host}{path}{token}',
        '{schema}://{host}:{port}{path}{token}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'token': {
            'name': _('Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'path': {
            'name': _('Path'),
            'type': 'string',
            'map_to': 'fullpath',
            'default': '/',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'values': GOTIFY_PRIORITIES,
            'default': GotifyPriority.NORMAL,
        },
    })

    def __init__(self, token, priority=None, **kwargs):
        """
        Initialize Gotify Object

        """
        super(NotifyGotify, self).__init__(**kwargs)

        # Token (associated with project)
        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Gotify Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # prepare our fullpath
        self.fullpath = kwargs.get('fullpath', '/')

        if priority not in GOTIFY_PRIORITIES:
            self.priority = GotifyPriority.NORMAL

        else:
            self.priority = priority

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Gotify Notification
        """

        url = '%s://%s' % (self.schema, self.host)
        if self.port:
            url += ':%d' % self.port

        # Append our remaining path
        url += '{fullpath}message'.format(fullpath=self.fullpath)

        # Prepare Gotify Object
        payload = {
            'priority': self.priority,
            'title': title,
            'message': body,
        }

        if self.notify_format == NotifyFormat.MARKDOWN:
            payload["extras"] = {
                "client::display": {
                    "contentType": "text/markdown"
                }
            }

        # Our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'X-Gotify-Key': self.token,
        }

        self.logger.debug('Gotify POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Gotify Payload: %s' % str(payload))

        # Always call throttle before the requests are made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyGotify.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Gotify notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return False

            else:
                self.logger.info('Sent Gotify notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Gotify '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'priority': self.priority,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our default port
        default_port = 443 if self.secure else 80

        return '{schema}://{hostname}{port}{fullpath}{token}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            fullpath=NotifyGotify.quote(self.fullpath, safe='/'),
            token=self.pprint(self.token, privacy, safe=''),
            params=NotifyGotify.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early
            return results

        # Retrieve our escaped entries found on the fullpath
        entries = NotifyBase.split_path(results['fullpath'])

        # optionally find the provider key
        try:
            # The last entry is our token
            results['token'] = entries.pop()

        except IndexError:
            # No token was set
            results['token'] = None

        # Re-assemble our full path
        results['fullpath'] = \
            '/' if not entries else '/{}/'.format('/'.join(entries))

        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            _map = {
                'l': GotifyPriority.LOW,
                'm': GotifyPriority.MODERATE,
                'n': GotifyPriority.NORMAL,
                'h': GotifyPriority.HIGH,
                'e': GotifyPriority.EMERGENCY,
            }
            try:
                results['priority'] = \
                    _map[results['qsd']['priority'][0].lower()]

            except KeyError:
                # No priority was set
                pass

        return results
