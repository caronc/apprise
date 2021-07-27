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

# To use this service you will need a Sinch account to which you can get your
# API_TOKEN and SERVICE_PLAN_ID right from your console/dashboard at:
#     https://dashboard.sinch.com/sms/overview
#
# You will also need to send the SMS From a phone number or account id name.

# This is identified as the source (or where the SMS message will originate
# from). Activated phone numbers can be found on your dashboard here:
#  - https://dashboard.sinch.com/numbers/your-numbers/numbers
#
import six
import requests
import json

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class SinchRegion(object):
    """
    Defines the Sinch Server Regions
    """
    USA = 'us'
    EUROPE = 'eu'


# Used for verification purposes
SINCH_REGIONS = (SinchRegion.USA, SinchRegion.EUROPE)


class NotifySinch(NotifyBase):
    """
    A wrapper for Sinch Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Sinch'

    # The services URL
    service_url = 'https://sinch.com/'

    # All notification requests are secure
    secure_protocol = 'sinch'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # the number of seconds undelivered messages should linger for
    # in the Sinch queue
    validity_period = 14400

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_sinch'

    # Sinch uses the http protocol with JSON requests
    #   - the 'spi' gets substituted with the Service Provider ID
    #     provided as part of the Apprise URL.
    notify_url = 'https://{region}.sms.api.sinch.com/xms/v1/{spi}/batches'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{service_plan_id}:{api_token}@{from_phone}',
        '{schema}://{service_plan_id}:{api_token}@{from_phone}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'service_plan_id': {
            'name': _('Account SID'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-f0-9]+$', 'i'),
        },
        'api_token': {
            'name': _('Auth Token'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-f0-9]+$', 'i'),
        },
        'from_phone': {
            'name': _('From Phone No'),
            'type': 'string',
            'required': True,
            'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            'map_to': 'source',
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'short_code': {
            'name': _('Target Short Code'),
            'type': 'string',
            'regex': (r'^[0-9]{5,6}$', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'alias_of': 'from_phone',
        },
        'spi': {
            'alias_of': 'service_plan_id',
        },
        'region': {
            'name': _('Region'),
            'type': 'string',
            'regex': (r'^[a-z]{2}$', 'i'),
            'default': SinchRegion.USA,
        },
        'token': {
            'alias_of': 'api_token',
        },
    })

    def __init__(self, service_plan_id, api_token, source, targets=None,
                 region=None, **kwargs):
        """
        Initialize Sinch Object
        """
        super(NotifySinch, self).__init__(**kwargs)

        # The Account SID associated with the account
        self.service_plan_id = validate_regex(
            service_plan_id, *self.template_tokens['service_plan_id']['regex'])
        if not self.service_plan_id:
            msg = 'An invalid Sinch Account SID ' \
                  '({}) was specified.'.format(service_plan_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Authentication Token associated with the account
        self.api_token = validate_regex(
            api_token, *self.template_tokens['api_token']['regex'])
        if not self.api_token:
            msg = 'An invalid Sinch Authentication Token ' \
                  '({}) was specified.'.format(api_token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Setup our region
        self.region = self.template_args['region']['default'] \
            if not isinstance(region, six.string_types) else region.lower()
        if self.region and self.region not in SINCH_REGIONS:
            msg = 'The region specified ({}) is invalid.'.format(region)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Source Phone # and/or short-code
        result = is_phone_no(source, min_len=5)
        if not result:
            msg = 'The Account (From) Phone # or Short-code specified ' \
                  '({}) is invalid.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Tidy source
        self.source = result['full']

        if len(self.source) < 11 or len(self.source) > 14:
            # A short code is a special 5 or 6 digit telephone number
            # that's shorter than a full phone number.
            if len(self.source) not in (5, 6):
                msg = 'The Account (From) Phone # specified ' \
                      '({}) is invalid.'.format(source)
                self.logger.warning(msg)
                raise TypeError(msg)

            # else... it as a short code so we're okay

        else:
            # We're dealing with a phone number; so we need to just
            # place a plus symbol at the end of it
            self.source = '+{}'.format(self.source)

        # Parse our targets
        self.targets = list()

        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    'Dropped invalid phone # '
                    '({}) specified.'.format(target),
                )
                continue

            # store valid phone number
            self.targets.append('+{}'.format(result['full']))

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Sinch Notification
        """

        if not self.targets:
            if len(self.source) in (5, 6):
                # Generate a warning since we're a short-code.  We need
                # a number to message at minimum
                self.logger.warning(
                    'There are no valid Sinch targets to notify.')
                return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Authorization': 'Bearer {}'.format(self.api_token),
            'Content-Type': 'application/json',
        }

        # Prepare our payload
        payload = {
            'body': body,
            'from': self.source,

            # The To gets populated in the loop below
            'to': None,
        }

        # Prepare our Sinch URL (spi = Service Provider ID)
        url = self.notify_url.format(
            region=self.region, spi=self.service_plan_id)

        # Create a copy of the targets list
        targets = list(self.targets)

        if len(targets) == 0:
            # No sources specified, use our own phone no
            targets.append(self.source)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['to'] = [target]

            # Some Debug Logging
            self.logger.debug('Sinch POST URL: {} (cert_verify={})'.format(
                url, self.verify_certificate))
            self.logger.debug('Sinch Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    data=json.dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # The responsne might look like:
                # {
                #  "id": "CJloRJOe3MtDITqx",
                #  "to": ["15551112222"],
                #  "from": "15553334444",
                #  "canceled": false,
                #  "body": "This is a test message from your Sinch account",
                #  "type": "mt_text",
                #  "created_at": "2020-01-14T01:05:20.694Z",
                #  "modified_at": "2020-01-14T01:05:20.694Z",
                #  "delivery_report": "none",
                #  "expire_at": "2020-01-17T01:05:20.694Z",
                #  "flash_message": false
                # }
                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    # set up our status code to use
                    status_code = r.status_code

                    try:
                        # Update our status response if we can
                        json_response = json.loads(r.content)
                        status_code = json_response.get('code', status_code)
                        status_str = json_response.get('message', status_str)

                    except (AttributeError, TypeError, ValueError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        'Failed to send Sinch notification to {}: '
                        '{}{}error={}.'.format(
                            target,
                            status_str,
                            ', ' if status_str else '',
                            status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent Sinch notification to {}.'.format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Sinch:%s ' % (
                        target) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'region': self.region,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{spi}:{token}@{source}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            spi=self.pprint(
                self.service_plan_id, privacy, mode=PrivacyMode.Tail, safe=''),
            token=self.pprint(self.api_token, privacy, safe=''),
            source=NotifySinch.quote(self.source, safe=''),
            targets='/'.join(
                [NotifySinch.quote(x, safe='') for x in self.targets]),
            params=NotifySinch.urlencode(params))

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifySinch.split_path(results['fullpath'])

        # The hostname is our source number
        results['source'] = NotifySinch.unquote(results['host'])

        # Get our service_plan_ide and api_token from the user/pass config
        results['service_plan_id'] = NotifySinch.unquote(results['user'])
        results['api_token'] = NotifySinch.unquote(results['password'])

        # Auth Token
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            # Extract the account spi from an argument
            results['api_token'] = \
                NotifySinch.unquote(results['qsd']['token'])

        # Account SID
        if 'spi' in results['qsd'] and len(results['qsd']['spi']):
            # Extract the account spi from an argument
            results['service_plan_id'] = \
                NotifySinch.unquote(results['qsd']['spi'])

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifySinch.unquote(results['qsd']['from'])

        if 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifySinch.unquote(results['qsd']['source'])

        # Allow one to define a region
        if 'region' in results['qsd'] and len(results['qsd']['region']):
            results['region'] = \
                NotifySinch.unquote(results['qsd']['region'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifySinch.parse_phone_no(results['qsd']['to'])

        return results
