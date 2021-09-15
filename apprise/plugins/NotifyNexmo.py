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

# Sign-up with https://dashboard.nexmo.com/
#
# Get your (api) key and secret here:
#   - https://dashboard.nexmo.com/getting-started-guide
#
import requests

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotifyNexmo(NotifyBase):
    """
    A wrapper for Nexmo Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Nexmo'

    # The services URL
    service_url = 'https://dashboard.nexmo.com/'

    # The default protocol
    secure_protocol = 'nexmo'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_nexmo'

    # Nexmo uses the http protocol with JSON requests
    notify_url = 'https://rest.nexmo.com/sms/json'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{apikey}:{secret}@{from_phone}',
        '{schema}://{apikey}:{secret}@{from_phone}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'required': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
            'private': True,
        },
        'secret': {
            'name': _('API Secret'),
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
        'key': {
            'alias_of': 'apikey',
        },
        'secret': {
            'alias_of': 'secret',
        },

        # Default Time To Live
        # By default Nexmo attempt delivery for 72 hours, however the maximum
        # effective value depends on the operator and is typically 24 - 48
        # hours. We recommend this value should be kept at its default or at
        # least 30 minutes.
        'ttl': {
            'name': _('ttl'),
            'type': 'int',
            'default': 900000,
            'min': 20000,
            'max': 604800000,
        },
    })

    def __init__(self, apikey, secret, source, targets=None, ttl=None,
                 **kwargs):
        """
        Initialize Nexmo Object
        """
        super(NotifyNexmo, self).__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Nexmo API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # API Secret (associated with project)
        self.secret = validate_regex(
            secret, *self.template_tokens['secret']['regex'])
        if not self.secret:
            msg = 'An invalid Nexmo API Secret ' \
                  '({}) was specified.'.format(secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Set our Time to Live Flag
        self.ttl = self.template_args['ttl']['default']
        try:
            self.ttl = int(ttl)

        except (ValueError, TypeError):
            # Do nothing
            pass

        if self.ttl < self.template_args['ttl']['min'] or \
                self.ttl > self.template_args['ttl']['max']:
            msg = 'The Nexmo TTL specified ({}) is out of range.'\
                .format(self.ttl)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Source Phone #
        self.source = source

        result = is_phone_no(source)
        if not result:
            msg = 'The Account (From) Phone # specified ' \
                  '({}) is invalid.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our parsed value
        self.source = result['full']

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
            self.targets.append(result['full'])

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Nexmo Notification
        """

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # Prepare our payload
        payload = {
            'api_key': self.apikey,
            'api_secret': self.secret,
            'ttl': self.ttl,
            'from': self.source,
            'text': body,

            # The to gets populated in the loop below
            'to': None,
        }

        # Create a copy of the targets list
        targets = list(self.targets)

        if len(targets) == 0:
            # No sources specified, use our own phone no
            targets.append(self.source)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['to'] = target

            # Some Debug Logging
            self.logger.debug('Nexmo POST URL: {} (cert_verify={})'.format(
                self.notify_url, self.verify_certificate))
            self.logger.debug('Nexmo Payload: {}' .format(payload))

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
                        NotifyNexmo.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Nexmo notification to {}: '
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

                else:
                    self.logger.info('Sent Nexmo notification to %s.' % target)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Nexmo:%s '
                    'notification.' % target
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
            'ttl': str(self.ttl),
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{key}:{secret}@{source}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            key=self.pprint(self.apikey, privacy, safe=''),
            secret=self.pprint(
                self.secret, privacy, mode=PrivacyMode.Secret, safe=''),
            source=NotifyNexmo.quote(self.source, safe=''),
            targets='/'.join(
                [NotifyNexmo.quote(x, safe='') for x in self.targets]),
            params=NotifyNexmo.urlencode(params))

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
        results['targets'] = NotifyNexmo.split_path(results['fullpath'])

        # The hostname is our source number
        results['source'] = NotifyNexmo.unquote(results['host'])

        # Get our account_side and auth_token from the user/pass config
        results['apikey'] = NotifyNexmo.unquote(results['user'])
        results['secret'] = NotifyNexmo.unquote(results['password'])

        # API Key
        if 'key' in results['qsd'] and len(results['qsd']['key']):
            # Extract the API Key from an argument
            results['apikey'] = \
                NotifyNexmo.unquote(results['qsd']['key'])

        # API Secret
        if 'secret' in results['qsd'] and len(results['qsd']['secret']):
            # Extract the API Secret from an argument
            results['secret'] = \
                NotifyNexmo.unquote(results['qsd']['secret'])

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyNexmo.unquote(results['qsd']['from'])
        if 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifyNexmo.unquote(results['qsd']['source'])

        # Support the 'ttl' variable
        if 'ttl' in results['qsd'] and len(results['qsd']['ttl']):
            results['ttl'] = \
                NotifyNexmo.unquote(results['qsd']['ttl'])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyNexmo.parse_phone_no(results['qsd']['to'])

        return results
