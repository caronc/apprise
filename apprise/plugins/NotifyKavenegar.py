# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

# To use this service you will need a Kavenegar account from their website
# at https://kavenegar.com/
#
# After you've established your account you can get your API Key from your
# account profile: https://panel.kavenegar.com/client/setting/account
#
# This provider does not accept +1 (for example) as a country code. You need
# to specify 001 instead.
#
import re
import requests
from json import loads

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Extend HTTP Error Messages
# Based on https://kavenegar.com/rest.html
KAVENEGAR_HTTP_ERROR_MAP = {
    200: 'The request was approved',
    400: 'Parameters are incomplete',
    401: 'Account has been disabled',
    402: 'The operation failed',
    403: 'The API Key is invalid',
    404: 'The method is unknown',
    405: 'The GET/POST request is wrong',
    406: 'Invalid mandatory parameters sent',
    407: 'You canot access the information you want',
    409: 'The server is unable to response',
    411: 'The recipient is invalid',
    412: 'The sender is invalid',
    413: 'Message empty or message length exceeded',
    414: 'The number of recipients is more than 200',
    415: 'The start index is larger then the total',
    416: 'The source IP of the service does not match the settings',
    417: 'The submission date is incorrect, '
         'either expired or not in the correct format',
    418: 'Your account credit is insufficient',
    422: 'Data cannot be processed due to invalid characters',
    501: 'SMS can only be sent to the account holder number',
}

# Some Phone Number Detection
IS_PHONE_NO = re.compile(r'^\+?(?P<phone>[0-9\s)(+-]+)\s*$')


class NotifyKavenegar(NotifyBase):
    """
    A wrapper for Kavenegar Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Kavenegar'

    # The services URL
    service_url = 'https://kavenegar.com/'

    # All notification requests are secure
    secure_protocol = 'kavenegar'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_kavenegar'

    # Kavenegar single notification URL
    notify_url = 'http://api.kavenegar.com/v1/{apikey}/sms/send.json'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{apikey}/{targets}',
        '{schema}://{source}@{apikey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
        },
        'source': {
            'name': _('Source Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'from': {
            'alias_of': 'source',
        },
    })

    def __init__(self, apikey, source=None, targets=None, **kwargs):
        """
        Initialize Kavenegar Object
        """
        super(NotifyKavenegar, self).__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Kavenegar API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.source = None
        if source is not None:
            result = IS_PHONE_NO.match(source)
            if not result:
                msg = 'The Kavenegar source specified ({}) is invalid.'\
                    .format(source)
                self.logger.warning(msg)
                raise TypeError(msg)

            # Further check our phone # for it's digit count
            result = ''.join(re.findall(r'\d+', result.group('phone')))
            if len(result) < 11 or len(result) > 14:
                msg = 'The MessageBird source # specified ({}) is invalid.'\
                    .format(source)
                self.logger.warning(msg)
                raise TypeError(msg)

            # Store our source
            self.source = result

        # Parse our targets
        self.targets = list()

        for target in parse_list(targets):
            # Validate targets and drop bad ones:
            result = IS_PHONE_NO.match(target)
            if result:
                # Further check our phone # for it's digit count
                # if it's less than 10, then we can assume it's
                # a poorly specified phone no and spit a warning
                result = ''.join(re.findall(r'\d+', result.group('phone')))
                if len(result) < 11 or len(result) > 14:
                    self.logger.warning(
                        'Dropped invalid phone # '
                        '({}) specified.'.format(target),
                    )
                    continue

                # store valid phone number
                self.targets.append(result)
                continue

            self.logger.warning(
                'Dropped invalid phone # ({}) specified.'.format(target))

        if len(self.targets) == 0:
            msg = 'There are no valid targets identified to notify.'
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Sends SMS Message
        """

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
        }

        # Our URL
        url = self.notify_url.format(apikey=self.apikey)

        # use the list directly
        targets = list(self.targets)

        while len(targets):
            # Get our target(s) to notify
            target = targets.pop(0)

            # Prepare our payload
            payload = {
                'receptor': target,
                'message': body,
            }

            if self.source:
                # Only set source if specified
                payload['sender'] = self.source

            # Some Debug Logging
            self.logger.debug(
                'Kavenegar POST URL: {} (cert_verify={})'.format(
                    url, self.verify_certificate))
            self.logger.debug('Kavenegar Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    params=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code, KAVENEGAR_HTTP_ERROR_MAP)

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
                        status_str = json_response.get('message', status_str)

                    except (AttributeError, TypeError, ValueError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        'Failed to send Kavenegar SMS notification to {}: '
                        '{}{}error={}.'.format(
                            target,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                # If we reach here; the message was sent
                self.logger.info(
                    'Sent Kavenegar SMS notification to {}.'.format(target))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Kavenegar:%s ' % (
                        ', '.join(self.targets)) + 'notification.'
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

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{source}{apikey}/{targets}?{params}'.format(
            schema=self.secure_protocol,
            source='' if not self.source else '{}@'.format(self.source),
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='/'.join(
                [NotifyKavenegar.quote(x, safe='') for x in self.targets]),
            params=NotifyKavenegar.urlencode(params))

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

        # Store the source if specified
        if results.get('user', None):
            results['source'] = results['user']

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifyKavenegar.split_path(results['fullpath'])

        # The hostname is our authentication key
        results['apikey'] = NotifyKavenegar.unquote(results['host'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyKavenegar.parse_list(results['qsd']['to'])

        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyKavenegar.unquote(results['qsd']['from'])

        return results
