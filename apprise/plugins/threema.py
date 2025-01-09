# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Create an account https://gateway.threema.ch/en/ if you don't already have
# one
#
# Read more about Threema Gateway API here:
#   - https://gateway.threema.ch/en/developer/api

import requests
from itertools import chain

from .base import NotifyBase
from ..common import NotifyType
from ..utils.parse import is_phone_no, validate_regex, is_email, parse_list
from ..url import PrivacyMode
from ..locale import gettext_lazy as _


class ThreemaRecipientTypes:
    """
    The supported recipient specifiers
    """
    THREEMA_ID = 'to'
    PHONE = 'phone'
    EMAIL = 'email'


class NotifyThreema(NotifyBase):
    """
    A wrapper for Threema Gateway Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Threema Gateway'

    # The services URL
    service_url = 'https://gateway.threema.ch/'

    # The default protocol
    secure_protocol = 'threema'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_threema'

    # Threema Gateway uses the http protocol with JSON requests
    notify_url = 'https://msgapi.threema.ch/send_simple'

    # The maximum length of the body
    body_maxlen = 3500

    # No title support
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{gateway_id}@{secret}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'gateway_id': {
            'name': _('Gateway ID'),
            'type': 'string',
            'private': True,
            'required': True,
            'map_to': 'user',
        },
        'secret': {
            'name': _('API Secret'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'target_email': {
            'name': _('Target Email'),
            'type': 'string',
            'map_to': 'targets',
        },
        'target_threema_id': {
            'name': _('Target Threema ID'),
            'type': 'string',
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
            'alias_of': 'gateway_id',
        },
        'gwid': {
            'alias_of': 'gateway_id',
        },
        'secret': {
            'alias_of': 'secret',
        },
    })

    def __init__(self, secret=None, targets=None, **kwargs):
        """
        Initialize Threema Gateway Object
        """
        super().__init__(**kwargs)

        # Validate our params here.

        if not self.user:
            msg = 'Threema Gateway ID must be specified'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Verify our Gateway ID
        if len(self.user) != 8:
            msg = 'Threema Gateway ID must be 8 characters in length'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Verify our secret
        self.secret = validate_regex(secret)
        if not self.secret:
            msg = \
                'An invalid Threema API Secret ({}) was specified'.format(
                    secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse our targets
        self.targets = list()

        # Used for URL generation afterwards only
        self.invalid_targets = list()

        for target in parse_list(targets, allow_whitespace=False):
            if len(target) == 8:
                # Store our user
                self.targets.append(
                    (ThreemaRecipientTypes.THREEMA_ID, target))
                continue

            # Check if an email was defined
            result = is_email(target)
            if result:
                # Store our user
                self.targets.append(
                    (ThreemaRecipientTypes.EMAIL, result['full_email']))
                continue

            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if result:
                # store valid phone number
                self.targets.append((
                    ThreemaRecipientTypes.PHONE, result['full']))
                continue

            self.logger.warning(
                'Dropped invalid user/email/phone '
                '({}) specified'.format(target),
            )
            self.invalid_targets.append(target)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Threema Gateway Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning(
                'There were no Threema Gateway targets to notify')
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
            'Accept': '*/*',
        }

        # Prepare our payload
        _payload = {
            'secret': self.secret,
            'from': self.user,
            'text': body.encode('utf-8'),
        }

        # Create a copy of the targets list
        targets = list(self.targets)

        while len(targets):
            # Get our target to notify
            key, target = targets.pop(0)

            # Prepare a payload object
            payload = _payload.copy()

            # Set Target
            payload[key] = target

            # Some Debug Logging
            self.logger.debug(
                'Threema Gateway GET URL: {} (cert_verify={})'.format(
                    self.notify_url, self.verify_certificate))
            self.logger.debug('Threema Gateway Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    params=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyThreema.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Threema Gateway notification to {}: '
                        '{}{}error={}'.format(
                            target,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                # We wee successful
                self.logger.info(
                    'Sent Threema Gateway notification to %s' % target)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Threema Gateway:%s '
                    'notification' % target
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.user, self.secret)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        schemaStr =  \
            '{schema}://{gatewayid}@{secret}/{targets}?{params}'
        return schemaStr.format(
            schema=self.secure_protocol,
            gatewayid=NotifyThreema.quote(self.user),
            secret=self.pprint(
                self.secret, privacy, mode=PrivacyMode.Secret, safe=''),
            targets='/'.join(chain(
                [NotifyThreema.quote(x[1], safe='@+') for x in self.targets],
                [NotifyThreema.quote(x, safe='@+')
                 for x in self.invalid_targets])),
            params=NotifyThreema.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
        return targets if targets > 0 else 1

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

        results['targets'] = list()

        if 'secret' in results['qsd'] and len(results['qsd']['secret']):
            results['secret'] = \
                NotifyThreema.unquote(results['qsd']['secret'])

        else:
            results['secret'] = NotifyThreema.unquote(results['host'])

        results['targets'] += \
            NotifyThreema.split_path(results['fullpath'])

        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['user'] = \
                NotifyThreema.unquote(results['qsd']['from'])

        elif 'gwid' in results['qsd'] and len(results['qsd']['gwid']):
            results['user'] = \
                NotifyThreema.unquote(results['qsd']['gwid'])

        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyThreema.parse_list(
                    results['qsd']['to'], allow_whitespace=False)

        return results
