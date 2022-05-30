# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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

# For this to work correctly you need to register an app
# and generate an access token
#
#
#  This plugin will simply work using the url of:
#     streamlabs://access_token/
#
# API Documentation on Webhooks:
#    - https://dev.streamlabs.com/
#
import requests

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


# calls
class StrmlabsCall(object):
    ALERT = 'ALERTS'
    DONATION = 'DONATIONS'


# A List of calls we can use for verification
STRMLABS_CALLS = (
    StrmlabsCall.ALERT,
    StrmlabsCall.DONATION,
)


# alerts
class StrmlabsAlert(object):
    FOLLOW = 'follow'
    SUBSCRIPTION = 'subscription'
    DONATION = 'donation'
    HOST = 'host'


# A List of calls we can use for verification
STRMLABS_ALERTS = (
    StrmlabsAlert.FOLLOW,
    StrmlabsAlert.SUBSCRIPTION,
    StrmlabsAlert.DONATION,
    StrmlabsAlert.HOST,
)


class NotifyStreamlabs(NotifyBase):
    """
    A wrapper to Streamlabs Donation Notifications

    """
    # The default descriptive name associated with the Notification
    service_name = 'Streamlabs'

    # The services URL
    service_url = 'https://streamlabs.com/'

    # The default secure protocol
    secure_protocol = 'strmlabs'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_streamlabs'

    # Streamlabs Api endpoint
    notify_url = 'https://streamlabs.com/api/v1.0/'

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 255

    # Define object templates
    templates = (
        '{schema}://{access_token}/',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'access_token': {
            'name': _('Access Token'),
            'private': True,
            'required': True,
            'type': 'string',
            'regex': (r'^[a-z0-9]{40}$', 'i')
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'call': {
            'name': _('Call'),
            'type': 'choice:string',
            'values': STRMLABS_CALLS,
            'default': StrmlabsCall.ALERT,
        },
        'alert_type': {
            'name': _('Alert Type'),
            'type': 'choice:string',
            'values': STRMLABS_ALERTS,
            'default': StrmlabsAlert.DONATION,
        },
        'image_href': {
            'name': _('Image Link'),
            'type': 'string',
            'default': '',
        },
        'sound_href': {
            'name': _('Sound Link'),
            'type': 'string',
            'default': '',
        },
        'duration': {
            'name': _('Duration'),
            'type': 'int',
            'default': 1000,
            'min': 0
        },
        'special_text_color': {
            'name': _('Special Text Color'),
            'type': 'string',
            'default': '',
            'regex': (r'^[A-Z]$', 'i'),
        },
        'amount': {
            'name': _('Amount'),
            'type': 'int',
            'default': 0,
            'min': 0
        },
        'currency': {
            'name': _('Currency'),
            'type': 'string',
            'default': 'USD',
            'regex': (r'^[A-Z]{3}$', 'i'),
        },
        'name': {
            'name': _('Name'),
            'type': 'string',
            'default': 'Anon',
            'regex': (r'^[^\s].{1,24}$', 'i')
        },
        'identifier': {
            'name': _('Identifier'),
            'type': 'string',
            'default': 'Apprise',
        },
    })

    def __init__(self, access_token,
                 call=StrmlabsCall.ALERT,
                 alert_type=StrmlabsAlert.DONATION,
                 image_href='', sound_href='', duration=1000,
                 special_text_color='',
                 amount=0, currency='USD', name='Anon',
                 identifier='Apprise',
                 **kwargs):
        """
        Initialize Streamlabs Object

        """
        super(NotifyStreamlabs, self).__init__(**kwargs)

        # access token is generated by user
        # using https://streamlabs.com/api/v1.0/token
        # Tokens for Streamlabs never need to be refreshed.
        self.access_token = validate_regex(
            access_token,
            *self.template_tokens['access_token']['regex']
        )
        if not self.access_token:
            msg = 'An invalid Streamslabs access token was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store the call
        try:
            if call not in STRMLABS_CALLS:
                # allow the outer except to handle this common response
                raise
            else:
                self.call = call
        except Exception as e:
            # Invalid region specified
            msg = 'The streamlabs call specified ({}) is invalid.' \
                .format(call)
            self.logger.warning(msg)
            self.logger.debug('Socket Exception: %s' % str(e))
            raise TypeError(msg)

        # Store the alert_type
        # only applicable when calling /alerts
        try:
            if alert_type not in STRMLABS_ALERTS:
                # allow the outer except to handle this common response
                raise
            else:
                self.alert_type = alert_type
        except Exception as e:
            # Invalid region specified
            msg = 'The streamlabs alert type specified ({}) is invalid.' \
                .format(call)
            self.logger.warning(msg)
            self.logger.debug('Socket Exception: %s' % str(e))
            raise TypeError(msg)

        # params only applicable when calling /alerts
        self.image_href = image_href
        self.sound_href = sound_href
        self.duration = duration
        self.special_text_color = special_text_color

        # only applicable when calling /donations
        # The amount of this donation.
        self.amount = amount

        # only applicable when calling /donations
        # The 3 letter currency code for this donation.
        # Must be one of the supported currency codes.
        self.currency = validate_regex(
            currency,
            *self.template_args['currency']['regex']
        )

        # only applicable when calling /donations
        if not self.currency:
            msg = 'An invalid Streamslabs currency was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # only applicable when calling /donations
        # The name of the donor
        self.name = validate_regex(
            name,
            *self.template_args['name']['regex']
        )
        if not self.name:
            msg = 'An invalid Streamslabs donor was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # An identifier for this donor,
        # which is used to group donations with the same donor.
        # only applicable when calling /donations
        self.identifier = identifier

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform Streamlabs notification call (either donation or alert)
        """

        headers = {
            'User-Agent': self.app_id,
        }
        if self.call == StrmlabsCall.ALERT:

            data = {
                'access_token': self.access_token,
                'type': self.alert_type.lower(),
                'image_href': self.image_href,
                'sound_href': self.sound_href,
                'message': title,
                'user_massage': body,
                'duration': self.duration,
                'special_text_color': self.special_text_color,
            }

            try:
                r = requests.post(
                    self.notify_url + self.call.lower(),
                    headers=headers,
                    data=data,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyStreamlabs.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Streamlabs alert: '
                        '{}{}error={}.'.format(
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))
                    return False

                else:
                    self.logger.info('Sent Streamlabs alert.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending Streamlabs '
                    'alert.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                return False

        if self.call == StrmlabsCall.DONATION:
            data = {
                'name': self.name,
                'identifier': self.identifier,
                'amount': self.amount,
                'currency': self.currency,
                'access_token': self.access_token,
                'message': body,
            }

            try:
                r = requests.post(
                    self.notify_url + self.call.lower(),
                    headers=headers,
                    data=data,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyStreamlabs.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Streamlabs donation: '
                        '{}{}error={}.'.format(
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))
                    return False

                else:
                    self.logger.info('Sent Streamlabs donation.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending Streamlabs '
                    'donation.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'call': self.call,
            # donation
            'name': self.name,
            'identifier': self.identifier,
            'amount': self.amount,
            'currency': self.currency,
            # alert
            'alert_type': self.alert_type,
            'image_href': self.image_href,
            'sound_href': self.sound_href,
            'duration': self.duration,
            'special_text_color': self.special_text_color,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))
        return '{schema}://{access_token}/?{params}'.format(
            schema=self.secure_protocol,
            access_token=self.pprint(self.access_token, privacy, safe=''),
            params=NotifyStreamlabs.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        Syntax:
          strmlabs://access_token

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store our access code
        access_token = NotifyStreamlabs.unquote(results['host'])
        results['access_token'] = access_token

        # call
        if 'call' in results['qsd'] and results['qsd']['call']:
            results['call'] = NotifyStreamlabs.unquote(
                results['qsd']['call'].strip().upper())
        # donation - amount
        if 'amount' in results['qsd'] and results['qsd']['amount']:
            results['amount'] = NotifyStreamlabs.unquote(
                results['qsd']['amount'])
        # donation - currency
        if 'currency' in results['qsd'] and results['qsd']['currency']:
            results['currency'] = NotifyStreamlabs.unquote(
                results['qsd']['currency'].strip().upper())
        # donation - name
        if 'name' in results['qsd'] and results['qsd']['name']:
            results['name'] = NotifyStreamlabs.unquote(
                results['qsd']['name'].strip().upper())
        # donation - identifier
        if 'identifier' in results['qsd'] and results['qsd']['identifier']:
            results['identifier'] = NotifyStreamlabs.unquote(
                results['qsd']['identifier'].strip().upper())
        # alert - alert_type
        if 'alert_type' in results['qsd'] and results['qsd']['alert_type']:
            results['alert_type'] = NotifyStreamlabs.unquote(
                results['qsd']['alert_type'])
        # alert - image_href
        if 'image_href' in results['qsd'] and results['qsd']['image_href']:
            results['image_href'] = NotifyStreamlabs.unquote(
                results['qsd']['image_href'])
        # alert - sound_href
        if 'sound_href' in results['qsd'] and results['qsd']['sound_href']:
            results['sound_href'] = NotifyStreamlabs.unquote(
                results['qsd']['sound_href'].strip().upper())
        # alert - duration
        if 'duration' in results['qsd'] and results['qsd']['duration']:
            results['duration'] = NotifyStreamlabs.unquote(
                results['qsd']['duration'].strip().upper())
        # alert - special_text_color
        if 'special_text_color' in results['qsd'] \
                and results['qsd']['special_text_color']:
            results['special_text_color'] = NotifyStreamlabs.unquote(
                results['qsd']['special_text_color'].strip().upper())

        return results
