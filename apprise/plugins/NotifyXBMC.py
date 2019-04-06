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

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..common import NotifyImageSize
from ..utils import parse_bool


class NotifyXBMC(NotifyBase):
    """
    A wrapper for XBMC/KODI Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Kodi/XBMC'

    # The services URL
    service_url = 'http://kodi.tv/'

    xbmc_protocol = 'xbmc'
    xbmc_secure_protocol = 'xbmcs'
    kodi_protocol = 'kodi'
    kodi_secure_protocol = 'kodis'

    # The default protocols
    protocol = (xbmc_protocol, kodi_protocol)

    # The default secure protocols
    secure_protocol = (xbmc_secure_protocol, kodi_secure_protocol)

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_kodi'

    # Disable throttle rate for XBMC/KODI requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Limit results to just the first 2 line otherwise there is just to much
    # content to display
    body_max_line_count = 2

    # XBMC uses the http protocol with JSON requests
    xbmc_default_port = 8080

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # The number of seconds to display the popup for
    default_popup_duration_sec = 12

    # XBMC default protocol version (v2)
    xbmc_remote_protocol = 2

    # KODI default protocol version (v6)
    kodi_remote_protocol = 6

    def __init__(self, include_image=True, duration=None, **kwargs):
        """
        Initialize XBMC/KODI Object
        """
        super(NotifyXBMC, self).__init__(**kwargs)

        # Number of seconds to display notification for
        self.duration = self.default_popup_duration_sec \
            if not (isinstance(duration, int) and duration > 0) else duration

        # Build our schema
        self.schema = 'https' if self.secure else 'http'

        # Prepare the default header
        self.headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # Default protocol
        self.protocol = kwargs.get('protocol', self.xbmc_remote_protocol)

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

    def _payload_60(self, title, body, notify_type, **kwargs):
        """
        Builds payload for KODI API v6.0

        Returns (headers, payload)
        """

        # prepare JSON Object
        payload = {
            'jsonrpc': '2.0',
            'method': 'GUI.ShowNotification',
            'params': {
                'title': title,
                'message': body,
                # displaytime is defined in microseconds so we need to just
                # do some simple math
                'displaytime': int(self.duration * 1000),
            },
            'id': 1,
        }

        # Acquire our image url if configured to do so
        image_url = None if not self.include_image else \
            self.image_url(notify_type)

        if image_url:
            payload['params']['image'] = image_url
            if notify_type is NotifyType.FAILURE:
                payload['type'] = 'error'

            elif notify_type is NotifyType.WARNING:
                payload['type'] = 'warning'

            else:
                payload['type'] = 'info'

        return (self.headers, dumps(payload))

    def _payload_20(self, title, body, notify_type, **kwargs):
        """
        Builds payload for XBMC API v2.0

        Returns (headers, payload)
        """

        # prepare JSON Object
        payload = {
            'jsonrpc': '2.0',
            'method': 'GUI.ShowNotification',
            'params': {
                'title': title,
                'message': body,
                # displaytime is defined in microseconds so we need to just
                # do some simple math
                'displaytime': int(self.duration * 1000),
            },
            'id': 1,
        }

        # Include our logo if configured to do so
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if image_url:
            payload['params']['image'] = image_url

        return (self.headers, dumps(payload))

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform XBMC/KODI Notification
        """

        if self.protocol == self.xbmc_remote_protocol:
            # XBMC v2.0
            (headers, payload) = self._payload_20(
                title, body, notify_type, **kwargs)

        else:
            # KODI v6.0
            (headers, payload) = self._payload_60(
                title, body, notify_type, **kwargs)

        auth = None
        if self.user:
            auth = (self.user, self.password)

        url = '%s://%s' % (self.schema, self.host)
        if self.port:
            url += ':%d' % self.port

        url += '/jsonrpc'

        self.logger.debug('XBMC/KODI POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('XBMC/KODI Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=payload,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyXBMC.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send XBMC/KODI notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent XBMC/KODI notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending XBMC/KODI '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
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
            'image': 'yes' if self.include_image else 'no',
            'duration': str(self.duration),
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyXBMC.quote(self.user, safe=''),
                password=NotifyXBMC.quote(self.password, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyXBMC.quote(self.user, safe=''),
            )

        default_schema = self.xbmc_protocol if (
            self.protocol <= self.xbmc_remote_protocol) else self.kodi_protocol
        default_port = 443 if self.secure else self.xbmc_default_port
        if self.secure:
            # Append 's' to schema
            default_schema + 's'

        return '{schema}://{auth}{hostname}{port}/?{args}'.format(
            schema=default_schema,
            auth=auth,
            hostname=NotifyXBMC.quote(self.host, safe=''),
            port='' if not self.port or self.port == default_port
                 else ':{}'.format(self.port),
            args=NotifyXBMC.urlencode(args),
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

        # We want to set our protocol depending on whether we're using XBMC
        # or KODI
        if results.get('schema', '').startswith('xbmc'):
            # XBMC Support
            results['protocol'] = NotifyXBMC.xbmc_remote_protocol

            # Assign Default XBMC Port
            if not results['port']:
                results['port'] = NotifyXBMC.xbmc_default_port

        else:
            # KODI Support
            results['protocol'] = NotifyXBMC.kodi_remote_protocol

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        # Set duration
        try:
            results['duration'] = abs(int(results['qsd'].get('duration')))

        except (TypeError, ValueError):
            # Not a valid integer; ignore entry
            pass

        return results
