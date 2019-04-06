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

import six
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType


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

    def __init__(self, token, priority=None, **kwargs):
        """
        Initialize Gotify Object

        """
        super(NotifyGotify, self).__init__(**kwargs)

        if not isinstance(token, six.string_types):
            msg = 'An invalid Gotify token was specified.'
            self.logger.warning('msg')
            raise TypeError(msg)

        if priority not in GOTIFY_PRIORITIES:
            self.priority = GotifyPriority.NORMAL

        else:
            self.priority = priority

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        # Our access token does not get created until we first
        # authenticate with our Gotify server. The same goes for the
        # user id below.
        self.token = token

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Gotify Notification
        """

        url = '%s://%s' % (self.schema, self.host)
        if self.port:
            url += ':%d' % self.port

        # Append our remaining path
        url += '/message'

        # Define our parameteers
        params = {
            'token': self.token,
        }

        # Prepare Gotify Object
        payload = {
            'priority': self.priority,
            'title': title,
            'message': body,
        }

        # Our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
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
                params=params,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
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
                'A Connection error occured sending Gotify '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'priority': self.priority,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        default_port = 443 if self.secure else 80

        return '{schema}://{hostname}{port}/{token}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            hostname=NotifyGotify.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            token=NotifyGotify.quote(self.token, safe=''),
            args=NotifyGotify.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early
            return results

        # Retrieve our escaped entries found on the fullpath
        entries = NotifyBase.split_path(results['fullpath'])

        # optionally find the provider key
        try:
            # The first entry is our token
            results['token'] = entries.pop(0)

        except IndexError:
            # No token was set
            results['token'] = None

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
