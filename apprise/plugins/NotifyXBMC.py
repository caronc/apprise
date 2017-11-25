# -*- encoding: utf-8 -*-
#
# XBMC Notify Wrapper
#
# Copyright (C) 2014-2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# apprise is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# apprise is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with apprise. If not, see <http://www.gnu.org/licenses/>.

from json import dumps
import requests

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import NotifyType
from .NotifyBase import NotifyImageSize
from .NotifyBase import HTTP_ERROR_MAP

# Image Support (128x128)
XBMC_IMAGE_XY = NotifyImageSize.XY_128

# XBMC uses the http protocol with JSON requests
XBMC_PORT = 8080

XBMC_PROTOCOL_V2 = 2
XBMC_PROTOCOL_V6 = 6

SUPPORTED_XBMC_PROTOCOLS = (
    XBMC_PROTOCOL_V2,
    XBMC_PROTOCOL_V6,
)


class NotifyXBMC(NotifyBase):
    """
    A wrapper for XBMC/KODI Notifications
    """

    # The default protocol
    PROTOCOL = ('xbmc', 'kodi')

    # The default secure protocol
    SECURE_PROTOCOL = ('xbmc', 'kodis')

    def __init__(self, **kwargs):
        """
        Initialize XBMC/KODI Object
        """
        super(NotifyXBMC, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            image_size=XBMC_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

        if self.secure:
            self.schema = 'https'
        else:
            self.schema = 'http'

        if not self.port:
            self.port = XBMC_PORT

        self.protocol = kwargs.get('protocol', XBMC_PROTOCOL_V2)
        if self.protocol not in SUPPORTED_XBMC_PROTOCOLS:
            raise TypeError("Invalid protocol specified.")

        return

    def _payload_60(self, title, body, notify_type, **kwargs):
        """
        Builds payload for KODI API v6.0

        Returns (headers, payload)
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # prepare JSON Object
        payload = {
            'jsonrpc': '6.0',
            'method': 'GUI.ShowNotification',
            'params': {
                'title': title,
                'message': body,
                # displaytime is defined in microseconds
                'displaytime': 12000,
            },
            'id': 1,
        }

        if self.include_image:
            image_url = self.image_url(
                notify_type,
            )
            if image_url:
                payload['image'] = image_url
                if notify_type is NotifyType.Error:
                    payload['type'] = 'error'
                elif notify_type is NotifyType.Warning:
                    payload['type'] = 'warning'
                else:
                    payload['type'] = 'info'

        return (headers, dumps(payload))

    def _payload_20(self, title, body, notify_type, **kwargs):
        """
        Builds payload for XBMC API v2.0

        Returns (headers, payload)
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # prepare JSON Object
        payload = {
            'jsonrpc': '2.0',
            'method': 'GUI.ShowNotification',
            'params': {
                'title': title,
                'message': body,
                # displaytime is defined in microseconds
                'displaytime': 12000,
            },
            'id': 1,
        }

        if self.include_image:
            image_url = self.image_url(
                notify_type,
            )
            if image_url:
                payload['image'] = image_url

        return (headers, dumps(payload))

    def _notify(self, title, body, notify_type, **kwargs):
        """
        Perform XBMC Notification
        """

        if self.protocol == XBMC_PROTOCOL_V2:
            # XBMC v2.0
            (headers, payload) = self._payload_20(
                title, body, notify_type, **kwargs)

        else:
            # XBMC v6.0
            (headers, payload) = self._payload_60(
                title, body, notify_type, **kwargs)

        auth = None
        if self.user:
            auth = (self.user, self.password)

        url = '%s://%s' % (self.schema, self.host)
        if isinstance(self.port, int):
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

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending XBMC/KODI '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True
