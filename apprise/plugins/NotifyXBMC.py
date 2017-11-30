# -*- coding: utf-8 -*-
#
# XBMC Notify Wrapper
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyType
from ..common import NotifyImageSize

# Image Support (128x128)
XBMC_IMAGE_XY = NotifyImageSize.XY_128

# XBMC uses v2
XBMC_PROTOCOL_V2 = 2

# Kodi uses v6
XBMC_PROTOCOL_V6 = 6

SUPPORTED_XBMC_PROTOCOLS = (
    XBMC_PROTOCOL_V2,
    XBMC_PROTOCOL_V6,
)


class NotifyXBMC(NotifyBase):
    """
    A wrapper for XBMC/KODI Notifications
    """

    # The default protocols
    protocol = ('xbmc', 'kodi')

    # The default secure protocols
    secure_protocol = ('xbmc', 'kodis')

    # XBMC uses the http protocol with JSON requests
    default_port = 8080

    def __init__(self, **kwargs):
        """
        Initialize XBMC/KODI Object
        """
        super(NotifyXBMC, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            image_size=XBMC_IMAGE_XY, **kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        if not self.port:
            self.port = self.default_port

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

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform XBMC Notification
        """

        # Limit results to just the first 2 line otherwise
        # there is just to much content to display
        body = re.split('[\r\n]+', body)
        body[0] = body[0].strip('#').strip()
        body = '\r\n'.join(body[0:2])

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
