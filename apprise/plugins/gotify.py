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

# Gotify Docker configuration: https://hub.docker.com/r/gotify/server
# Example: https://github.com/gotify/server/blob/\
#        f2c2688f0b5e6a816bbcec768ca1c0de5af76b88/ADD_MESSAGE_EXAMPLES.md#python
# API: https://gotify.net/docs/swagger-docs

import requests
from json import dumps

from .base import NotifyBase
from ..common import NotifyType, NotifyFormat
from ..utils.parse import validate_regex
from ..locale import gettext_lazy as _


# Priorities
class GotifyPriority:
    LOW = 0
    MODERATE = 3
    NORMAL = 5
    HIGH = 8
    EMERGENCY = 10


GOTIFY_PRIORITIES = {
    # Note: This also acts as a reverse lookup mapping
    GotifyPriority.LOW: 'low',
    GotifyPriority.MODERATE: 'moderate',
    GotifyPriority.NORMAL: 'normal',
    GotifyPriority.HIGH: 'high',
    GotifyPriority.EMERGENCY: 'emergency',
}

GOTIFY_PRIORITY_MAP = {
    # Maps against string 'low'
    'l': GotifyPriority.LOW,
    # Maps against string 'moderate'
    'm': GotifyPriority.MODERATE,
    # Maps against string 'normal'
    'n': GotifyPriority.NORMAL,
    # Maps against string 'high'
    'h': GotifyPriority.HIGH,
    # Maps against string 'emergency'
    'e': GotifyPriority.EMERGENCY,

    # Entries to additionally support (so more like Gotify's API)
    '10': GotifyPriority.EMERGENCY,
    # ^ 10 needs to be checked before '1' below or it will match the wrong
    # priority
    '0': GotifyPriority.LOW, '1': GotifyPriority.LOW, '2': GotifyPriority.LOW,
    '3': GotifyPriority.MODERATE, '4': GotifyPriority.MODERATE,
    '5': GotifyPriority.NORMAL, '6': GotifyPriority.NORMAL,
    '7': GotifyPriority.NORMAL,
    '8': GotifyPriority.HIGH, '9': GotifyPriority.HIGH,
}


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
        super().__init__(**kwargs)

        # Token (associated with project)
        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Gotify Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # prepare our fullpath
        self.fullpath = kwargs.get('fullpath', '/')

        # The Priority of the message
        self.priority = int(
            NotifyGotify.template_args['priority']['default']
            if priority is None else
            next((
                v for k, v in GOTIFY_PRIORITY_MAP.items()
                if str(priority).lower().startswith(k)),
                NotifyGotify.template_args['priority']['default']))

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

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user, self.password, self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.fullpath.rstrip('/'),
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'priority':
                GOTIFY_PRIORITIES[self.template_args['priority']['default']]
                if self.priority not in GOTIFY_PRIORITIES
                else GOTIFY_PRIORITIES[self.priority],
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

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyGotify.unquote(results['qsd']['priority'])

        return results
