# -*- coding: utf-8 -*-
#
# Prowl Notify Wrapper
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

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP

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
PROWL_HTTP_ERROR_MAP = HTTP_ERROR_MAP.copy()
HTTP_ERROR_MAP.update({
    406: 'IP address has exceeded API limit',
    409: 'Request not aproved.',
})


class NotifyProwl(NotifyBase):
    """
    A wrapper for Prowl Notifications
    """

    # The default secure protocol
    secure_protocol = 'prowl'

    # Prowl uses the http protocol with JSON requests
    notify_url = 'https://api.prowlapp.com/publicapi/add'

    def __init__(self, apikey, providerkey=None, priority=ProwlPriority.NORMAL,
                 **kwargs):
        """
        Initialize Prowl Object
        """
        super(NotifyProwl, self).__init__(
            title_maxlen=1024, body_maxlen=10000, **kwargs)

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

    def notify(self, title, body, **kwargs):
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
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Prowl Payload: %s' % str(payload))
        try:
            r = requests.post(
                self.notify_url,
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

        # Apply our settings now

        # optionally find the provider key
        try:
            providerkey = filter(
                bool, NotifyBase.split_path(results['fullpath']))[0]

            if not providerkey:
                providerkey = None

        except (AttributeError, IndexError):
            providerkey = None

        results['apikey'] = results['host']
        results['providerkey'] = providerkey

        return results
