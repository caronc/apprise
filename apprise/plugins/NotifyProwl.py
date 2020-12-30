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

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


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

    # Define object templates
    templates = (
        '{schema}://{apikey}',
        '{schema}://{apikey}/{providerkey}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Za-z0-9]{40}$', 'i'),
        },
        'providerkey': {
            'name': _('Provider Key'),
            'type': 'string',
            'private': True,
            'regex': (r'^[A-Za-z0-9]{40}$', 'i'),
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'values': PROWL_PRIORITIES,
            'default': ProwlPriority.NORMAL,
        },
    })

    def __init__(self, apikey, providerkey=None, priority=None, **kwargs):
        """
        Initialize Prowl Object
        """
        super(NotifyProwl, self).__init__(**kwargs)

        if priority not in PROWL_PRIORITIES:
            self.priority = self.template_args['priority']['default']

        else:
            self.priority = priority

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Prowl API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store the provider key (if specified)
        if providerkey:
            self.providerkey = validate_regex(
                providerkey, *self.template_tokens['providerkey']['regex'])
            if not self.providerkey:
                msg = 'An invalid Prowl Provider Key ' \
                      '({}) was specified.'.format(providerkey)
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            # No provider key was set
            self.providerkey = None

        return

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
                timeout=self.request_timeout,
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
                'A Connection error occurred sending Prowl notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
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

        # Define any URL parameters
        params = {
            'priority': 'normal' if self.priority not in _map
                        else _map[self.priority],
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{apikey}/{providerkey}/?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            providerkey=self.pprint(self.providerkey, privacy, safe=''),
            params=NotifyProwl.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
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
                # Letter Assignments
                'l': ProwlPriority.LOW,
                'm': ProwlPriority.MODERATE,
                'n': ProwlPriority.NORMAL,
                'h': ProwlPriority.HIGH,
                'e': ProwlPriority.EMERGENCY,
                'lo': ProwlPriority.LOW,
                'me': ProwlPriority.MODERATE,
                'no': ProwlPriority.NORMAL,
                'hi': ProwlPriority.HIGH,
                'em': ProwlPriority.EMERGENCY,
                # Support 3rd Party Documented Scale
                '-2': ProwlPriority.LOW,
                '-1': ProwlPriority.MODERATE,
                '0': ProwlPriority.NORMAL,
                '1': ProwlPriority.HIGH,
                '2': ProwlPriority.EMERGENCY,
            }
            try:
                results['priority'] = \
                    _map[results['qsd']['priority'][0:2].lower()]

            except KeyError:
                # No priority was set
                pass

        return results
