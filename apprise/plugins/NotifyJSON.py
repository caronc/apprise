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

import six
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType


class NotifyJSON(NotifyBase):
    """
    A wrapper for JSON Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'JSON'

    # The default protocol
    protocol = 'json'

    # The default secure protocol
    secure_protocol = 'jsons'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_Custom_JSON'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for JSON requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    def __init__(self, headers=None, **kwargs):
        """
        Initialize JSON Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with

        """
        super(NotifyJSON, self).__init__(**kwargs)

        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, six.string_types):
            self.fullpath = '/'

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        # Append our headers into our args
        args.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyJSON.quote(self.user, safe=''),
                password=NotifyJSON.quote(self.password, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyJSON.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyJSON.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            args=NotifyJSON.urlencode(args),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform JSON Notification
        """

        # prepare JSON Object
        payload = {
            # Version: Major.Minor,  Major is only updated if the entire
            # schema is changed. If just adding new items (or removing
            # old ones, only increment the Minor!
            'version': '1.0',
            'title': title,
            'message': body,
            'type': notify_type,
        }

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath

        self.logger.debug('JSON POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('JSON Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyJSON.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send JSON notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent JSON notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending JSON '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

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

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set
        results['headers'] = results['qsd-']
        results['headers'].update(results['qsd+'])

        # Tidy our header entries by unquoting them
        results['headers'] = {NotifyJSON.unquote(x): NotifyJSON.unquote(y)
                              for x, y in results['headers'].items()}

        return results
