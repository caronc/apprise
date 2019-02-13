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

import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyType
from ..common import NotifyImageSize


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

    # XBMC uses the http protocol with JSON requests
    xbmc_default_port = 8080

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # XBMC default protocol version (v2)
    xbmc_remote_protocol = 2

    # KODI default protocol version (v6)
    kodi_remote_protocol = 6

    def __init__(self, **kwargs):
        """
        Initialize XBMC/KODI Object
        """
        super(NotifyXBMC, self).__init__(**kwargs)

        # Number of micro-seconds to display notification for
        self.duration = 12000

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        # Prepare the default header
        self.headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # Default protocol
        self.protocol = kwargs.get('protocol', self.xbmc_remote_protocol)

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
                # displaytime is defined in microseconds
                'displaytime': self.duration,
            },
            'id': 1,
        }

        image_url = self.image_url(notify_type)
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
                # displaytime is defined in microseconds
                'displaytime': self.duration,
            },
            'id': 1,
        }

        image_url = self.image_url(notify_type)
        if image_url:
            payload['params']['image'] = image_url

        return (self.headers, dumps(payload))

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform XBMC/KODI Notification
        """

        # Limit results to just the first 2 line otherwise
        # there is just to much content to display
        body = re.split('[\r\n]+', body)
        body[0] = body[0].strip('#').strip()
        body = '\r\n'.join(body[0:2])

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
                try:
                    self.logger.warning(
                        'Failed to send XBMC/KODI notification:'
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send XBMC/KODI notification '
                        '(error=%s).' % r.status_code)

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
        }

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=self.quote(self.user, safe=''),
                password=self.quote(self.password, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=self.quote(self.user, safe=''),
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
            hostname=self.host,
            port='' if not self.port or self.port == default_port
                 else ':{}'.format(self.port),
            args=self.urlencode(args),
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

        return results
