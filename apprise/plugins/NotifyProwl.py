# -*- encoding: utf-8 -*-
#
# Prowl Notify Wrapper
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

# Prowl uses the http protocol with JSON requests
PROWL_URL = 'https://api.prowlapp.com/publicapi/add'

# Used to validate API Key
VALIDATE_APIKEY = re.compile(r'[A-Za-z0-9]{40}')

# Used to validate Provider Key
VALIDATE_PROVIDERKEY = re.compile(r'[A-Za-z0-9]{40}')


# Priorities
class ProwlPriority(object):
    VERY_LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


PROWL_PRIORITIES = (
    ProwlPriority.VERY_LOW,
    ProwlPriority.MODERATE,
    ProwlPriority.NORMAL,
    ProwlPriority.HIGH,
    ProwlPriority.EMERGENCY,
)

# Extend HTTP Error Messages
PROWL_HTTP_ERROR_MAP = dict(HTTP_ERROR_MAP.items() + {
    406: 'IP address has exceeded API limit',
    409: 'Request not aproved.',
}.items())


class NotifyProwl(NotifyBase):
    """
    A wrapper for Prowl Notifications
    """

    # The default protocol
    PROTOCOL = 'prowl'

    # The default secure protocol
    SECURE_PROTOCOL = 'prowl'

    def __init__(self, apikey, providerkey=None,
                 priority=ProwlPriority.NORMAL,
                 **kwargs):
        """
        Initialize Prowl Object
        """
        super(NotifyProwl, self).__init__(
            title_maxlen=1024, body_maxlen=10000,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

        if priority not in PROWL_PRIORITIES:
            self.priority = ProwlPriority.NORMAL
        else:
            self.priority = priority

        if not VALIDATE_APIKEY.match(apikey):
            self.logger.warning(
                'The API key specified (%s) is invalid.' % apikey,
            )
            raise TypeError(
                'The API key specified (%s) is invalid.' % apikey,
            )

        # Store the API key
        self.apikey = apikey

        # Store the provider key (if specified)
        if providerkey:
            if not VALIDATE_PROVIDERKEY.match(providerkey):
                self.logger.warning(
                    'The Provider key specified (%s) '
                    'is invalid.' % providerkey)

                raise TypeError(
                    'The Provider key specified (%s) '
                    'is invalid.' % providerkey)

        # Store the Provider Key
        self.providerkey = providerkey

    def _notify(self, title, body, **kwargs):
        """
        Perform Prowl Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-type': "application/x-www-form-urlencoded",
        }

        # prepare JSON Object
        payload = {
            'apikey': self.apikey,
            'application': self.app_id,
            'event': title,
            'description': body,
            'priority': self.priority,
        }

        if self.providerkey:
            payload['providerkey'] = self.providerkey

        self.logger.debug('Prowl POST URL: %s (cert_verify=%r)' % (
            PROWL_URL, self.verify_certificate,
        ))
        self.logger.debug('Prowl Payload: %s' % str(payload))
        try:
            r = requests.post(
                PROWL_URL,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Prowl notification: '
                        '%s (error=%s).' % (
                            PROWL_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except IndexError:
                    self.logger.warning(
                        'Failed to send Prowl notification '
                        '(error=%s).' % (
                            r.status_code))

                self.logger.debug('Response Details: %s' % r.raw.read())
                # Return; we're done
                return False
            else:
                self.logger.info('Sent Prowl notification.')

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending Prowl notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True
