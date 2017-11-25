# -*- encoding: utf-8 -*-
#
# Notify My Android (NMA) Notify Wrapper
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

import requests
import re

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import HTTP_ERROR_MAP

# Notify My Android uses the http protocol with JSON requests
NMA_URL = 'https://www.notifymyandroid.com/publicapi/notify'

# Extend HTTP Error Messages
NMA_HTTP_ERROR_MAP = dict(HTTP_ERROR_MAP.items() + {
    400: 'Data is wrong format, invalid length or null.',
    401: 'API Key provided is invalid',
    402: 'Maximum number of API calls per hour reached.',
}.items())

# Used to validate Authorization Token
VALIDATE_APIKEY = re.compile(r'[A-Za-z0-9]{48}')


# Priorities
class NotifyMyAndroidPriority(object):
    VERY_LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


NMA_PRIORITIES = (
    NotifyMyAndroidPriority.VERY_LOW,
    NotifyMyAndroidPriority.MODERATE,
    NotifyMyAndroidPriority.NORMAL,
    NotifyMyAndroidPriority.HIGH,
    NotifyMyAndroidPriority.EMERGENCY,
)


class NotifyMyAndroid(NotifyBase):
    """
    A wrapper for Notify My Android (NMA) Notifications
    """

    # The default protocol
    PROTOCOL = 'nma'

    # The default secure protocol
    SECURE_PROTOCOL = 'nma'

    def __init__(self, apikey, priority=NotifyMyAndroidPriority.NORMAL,
                 devapikey=None, **kwargs):
        """
        Initialize Notify My Android Object
        """
        super(NotifyMyAndroid, self).__init__(
            title_maxlen=1000, body_maxlen=10000,
            notify_format=NotifyFormat.HTML,
            **kwargs)

        # The Priority of the message
        if priority not in NMA_PRIORITIES:
            self.priority = NotifyMyAndroidPriority.NORMAL
        else:
            self.priority = priority

        # Validate apikey
        if not VALIDATE_APIKEY.match(apikey):
            self.logger.warning(
                'Invalid NMA API Key specified.'
            )
            raise TypeError(
                'Invalid NMA API Key specified.'
            )
        self.apikey = apikey

        if devapikey:
            # Validate apikey
            if not VALIDATE_APIKEY.match(devapikey):
                self.logger.warning(
                    'Invalid NMA DEV API Key specified.'
                )
                raise TypeError(
                    'Invalid NMA DEV API Key specified.'
                )
        self.devapikey = devapikey

    def _notify(self, title, body, notify_type, **kwargs):
        """
        Perform Notify My Android Notification
        """

        headers = {
            'User-Agent': self.app_id,
        }

        # prepare JSON Object
        payload = {
            'apikey': self.apikey,
            'application': self.app_id,
            'event': title,
            'description': body,
            'priority': self.priority,
        }

        if self.notify_format == NotifyFormat.HTML:
            payload['content-type'] = 'text/html'

        if self.devapikey:
            payload['developerkey'] = self.devapikey

        self.logger.debug('NMA POST URL: %s (cert_verify=%r)' % (
            NMA_URL, self.verify_certificate,
        ))
        self.logger.debug('NMA Payload: %s' % str(payload))
        try:
            r = requests.post(
                NMA_URL,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send NMA notification: %s (error=%s).' % (
                            NMA_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except IndexError:
                    self.logger.warning(
                        'Failed to send NMA notification (error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

            else:
                self.logger.debug('NMA Server Response: %s.' % r.text)
                self.logger.info('Sent NMA notification.')

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending NMA notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True
