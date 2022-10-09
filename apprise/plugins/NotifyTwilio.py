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

# To use this service you will need a Twilio account to which you can get your
# AUTH_TOKEN and ACCOUNT SID right from your console/dashboard at:
#     https://www.twilio.com/console
#
# You will also need to send the SMS From a phone number or account id name.

# This is identified as the source (or where the SMS message will originate
# from). Activated phone numbers can be found on your dashboard here:
#  - https://www.twilio.com/console/phone-numbers/incoming
#
# Alternatively, you can open your wallet and request a different Twilio
# phone # from:
#    https://www.twilio.com/console/phone-numbers/search
#
# or consider purchasing a short-code from here:
#    https://www.twilio.com/docs/glossary/what-is-a-short-code
#
import requests
from json import loads

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotifyTwilio(NotifyBase):
    """
    A wrapper for Twilio Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Twilio'

    # The services URL
    service_url = 'https://www.twilio.com/'

    # All notification requests are secure
    secure_protocol = 'twilio'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # the number of seconds undelivered messages should linger for
    # in the Twilio queue
    validity_period = 14400

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_twilio'

    # Twilio uses the http protocol with JSON requests
    notify_url = 'https://api.twilio.com/2010-04-01/Accounts/' \
                 '{sid}/Messages.json'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{account_sid}:{auth_token}@{from_phone}',
        '{schema}://{account_sid}:{auth_token}@{from_phone}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'account_sid': {
            'name': _('Account SID'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^AC[a-f0-9]+$', 'i'),
        },
        'auth_token': {
            'name': _('Auth Token'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
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
        'sid': {
            'alias_of': 'account_sid',
        },
        'token': {
            'alias_of': 'auth_token',
        },
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'regex': (r'^SK[a-f0-9]+$', 'i'),
        },
    })

    def __init__(self, account_sid, auth_token, source, targets=None,
                 apikey=None, ** kwargs):
        """
        Initialize Twilio Object
        """
        super().__init__(**kwargs)

        # The Account SID associated with the account
        self.account_sid = validate_regex(
            account_sid, *self.template_tokens['account_sid']['regex'])
        if not self.account_sid:
            msg = 'An invalid Twilio Account SID ' \
                  '({}) was specified.'.format(account_sid)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Authentication Token associated with the account
        self.auth_token = validate_regex(
            auth_token, *self.template_tokens['auth_token']['regex'])
        if not self.auth_token:
            msg = 'An invalid Twilio Authentication Token ' \
                  '({}) was specified.'.format(auth_token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The API Key associated with the account (optional)
        self.apikey = validate_regex(
            apikey, *self.template_args['apikey']['regex'])

        result = is_phone_no(source, min_len=5)
        if not result:
            msg = 'The Account (From) Phone # or Short-code specified ' \
                  '({}) is invalid.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store The Source Phone # and/or short-code
        self.source = result['full']

        if len(self.source) < 11 or len(self.source) > 14:
            # https://www.twilio.com/docs/glossary/what-is-a-short-code
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
            # Validate targets and drop bad ones:
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
        Perform Twilio Notification
        """

        if not self.targets:
            if len(self.source) in (5, 6):
                # Generate a warning since we're a short-code.  We need
                # a number to message at minimum
                self.logger.warning(
                    'There are no valid Twilio targets to notify.')
                return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
        }

        # Prepare our payload
        payload = {
            'Body': body,
            'From': self.source,

            # The To gets populated in the loop below
            'To': None,
        }

        # Prepare our Twilio URL
        url = self.notify_url.format(sid=self.account_sid)

        # Create a copy of the targets list
        targets = list(self.targets)

        # Set up our authentication. Prefer the API Key if provided.
        auth = (self.apikey or self.account_sid, self.auth_token)

        if len(targets) == 0:
            # No sources specified, use our own phone no
            targets.append(self.source)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['To'] = target

            # Some Debug Logging
            self.logger.debug('Twilio POST URL: {} (cert_verify={})'.format(
                url, self.verify_certificate))
            self.logger.debug('Twilio Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    auth=auth,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(r.status_code)

                    # set up our status code to use
                    status_code = r.status_code

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
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
                        'Failed to send Twilio notification to {}: '
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
                        'Sent Twilio notification to {}.'.format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Twilio:%s ' % (
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

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.apikey is not None:
            # apikey specified; pass it back on the url
            params['apikey'] = self.apikey

        return '{schema}://{sid}:{token}@{source}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            sid=self.pprint(
                self.account_sid, privacy, mode=PrivacyMode.Tail, safe=''),
            token=self.pprint(self.auth_token, privacy, safe=''),
            source=NotifyTwilio.quote(self.source, safe=''),
            targets='/'.join(
                [NotifyTwilio.quote(x, safe='') for x in self.targets]),
            params=NotifyTwilio.urlencode(params))

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
        results['targets'] = NotifyTwilio.split_path(results['fullpath'])

        # The hostname is our source number
        results['source'] = NotifyTwilio.unquote(results['host'])

        # Get our account_side and auth_token from the user/pass config
        results['account_sid'] = NotifyTwilio.unquote(results['user'])
        results['auth_token'] = NotifyTwilio.unquote(results['password'])

        # Auth Token
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            # Extract the account sid from an argument
            results['auth_token'] = \
                NotifyTwilio.unquote(results['qsd']['token'])

        # Account SID
        if 'sid' in results['qsd'] and len(results['qsd']['sid']):
            # Extract the account sid from an argument
            results['account_sid'] = \
                NotifyTwilio.unquote(results['qsd']['sid'])

        # API Key
        if 'apikey' in results['qsd'] and len(results['qsd']['apikey']):
            results['apikey'] = results['qsd']['apikey']

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyTwilio.unquote(results['qsd']['from'])
        if 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifyTwilio.unquote(results['qsd']['source'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyTwilio.parse_phone_no(results['qsd']['to'])

        return results
