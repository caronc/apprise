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

from .NotifyBase import NotifyBase
from ..common import NotifyType

# Used to validate API Key
VALIDATE_APIKEY = re.compile(r'[A-Za-z0-9]{40}')

# Used to validate Provider Key
VALIDATE_PROVIDERKEY = re.compile(r'[A-Za-z0-9]{40}')


# Priorities
class ProwlPriority(object):
    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


PROWL_PRIORITIES = (
    ProwlPriority.LOW,
    ProwlPriority.MODERATE,
    ProwlPriority.NORMAL,
    ProwlPriority.HIGH,
    ProwlPriority.EMERGENCY,
)

# Provide some known codes Prowl uses and what they translate to:
PROWL_HTTP_ERROR_MAP = {
    406: 'IP address has exceeded API limit',
    409: 'Request not aproved.',
}


class NotifyProwl(NotifyBase):
    """
    A wrapper for Prowl Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Prowl'

    # The services URL
    service_url = 'https://www.prowlapp.com/'

    # The default secure protocol
    secure_protocol = 'prowl'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_prowl'

    # Prowl uses the http protocol with JSON requests
    notify_url = 'https://api.prowlapp.com/publicapi/add'

    # Disable throttle rate for Prowl requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 10000

    # Defines the maximum allowable characters in the title
    title_maxlen = 1024

    def __init__(self, apikey, providerkey=None, priority=None, **kwargs):
        """
        Initialize Prowl Object
        """
        super(NotifyProwl, self).__init__(**kwargs)

        if priority not in PROWL_PRIORITIES:
            self.priority = ProwlPriority.NORMAL

        else:
            self.priority = priority

        if not VALIDATE_APIKEY.match(apikey):
            msg = 'The API key specified ({}) is invalid.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store the API key
        self.apikey = apikey

        # Store the provider key (if specified)
        if providerkey:
            if not VALIDATE_PROVIDERKEY.match(providerkey):
                msg = \
                    'The Provider key specified ({}) is invalid.' \
                    .format(providerkey)

                self.logger.warning(msg)
                raise TypeError(msg)

        # Store the Provider Key
        self.providerkey = providerkey

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
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

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyBase.http_response_code_lookup(
                        r.status_code, PROWL_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Prowl notification:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Prowl notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Prowl notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        _map = {
            ProwlPriority.LOW: 'low',
            ProwlPriority.MODERATE: 'moderate',
            ProwlPriority.NORMAL: 'normal',
            ProwlPriority.HIGH: 'high',
            ProwlPriority.EMERGENCY: 'emergency',
        }

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'priority': 'normal' if self.priority not in _map
                        else _map[self.priority],
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://{apikey}/{providerkey}/?{args}'.format(
            schema=self.secure_protocol,
            apikey=NotifyProwl.quote(self.apikey, safe=''),
            providerkey='' if not self.providerkey
                        else NotifyProwl.quote(self.providerkey, safe=''),
            args=NotifyProwl.urlencode(args),
        )

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

        # Set the API Key
        results['apikey'] = NotifyProwl.unquote(results['host'])

        # Optionally try to find the provider key
        try:
            results['providerkey'] = \
                NotifyProwl.split_path(results['fullpath'])[0]

        except IndexError:
            pass

        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            _map = {
                'l': ProwlPriority.LOW,
                'm': ProwlPriority.MODERATE,
                'n': ProwlPriority.NORMAL,
                'h': ProwlPriority.HIGH,
                'e': ProwlPriority.EMERGENCY,
            }
            try:
                results['priority'] = \
                    _map[results['qsd']['priority'][0].lower()]

            except KeyError:
                # No priority was set
                pass

        return results
