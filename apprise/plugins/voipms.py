# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

# Create an account https://voip.ms/ if you don't already have one
#
# Enable API and set an API password here:
#   - https://voip.ms/m/api.php
#
# Read more about VoIP.ms API here:
#   - https://voip.ms/m/apidocs.php

import requests
from json import loads

from .base import NotifyBase
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import is_email
from ..utils import parse_phone_no
from ..locale import gettext_lazy as _


class NotifyVoipms(NotifyBase):
    """
    A wrapper for Voipms Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'VoIPms'

    # The services URL
    service_url = 'https://voip.ms'

    # The default protocol
    secure_protocol = 'voipms'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_voipms'

    # Voipms uses the http protocol with JSON requests
    notify_url = 'https://voip.ms/api/v1/rest.php'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{password}:{email}/{from_phone}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'email': {
            'name': _('User Email'),
            'type': 'string',
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'from_phone': {
            'name': _('From Phone No'),
            'type': 'string',
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
            'required': True,
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
    })

    def __init__(self, email, source=None, targets=None, **kwargs):
        """
        Initialize Voipms Object
        """
        super().__init__(**kwargs)

        # Validate our params here.

        if self.password is None:
            msg = 'Password has to be specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # User is the email associated with the account
        result = is_email(email)
        if not result:
            msg = 'An invalid Voipms user email: ' \
                '({}) was specified.'.format(email)
            self.logger.warning(msg)
            raise TypeError(msg)
        self.email = result['full_email']

        # Validate our source Phone #
        result = is_phone_no(source)
        if not result:
            msg = 'An invalid Voipms source phone # ' \
                  '({}) was specified.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Source Phone # only supports +1 country code
        # Allow 7 digit phones (presume they're local with +1 country code)
        if result['country'] and result['country'] != '1':
            msg = 'Voipms only supports +1 country code ' \
                  '({}) was specified.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our source phone number (without country code)
        self.source = result['area'] + result['line']

        # Parse our targets
        self.targets = list()

        if targets:
            for target in parse_phone_no(targets):
                # Validate targets and drop bad ones:
                result = is_phone_no(target)

                # Target Phone # only supports +1 country code
                if result['country'] != '1':
                    self.logger.warning(
                        'Dropped invalid phone # '
                        '({}) specified.'.format(target),
                    )
                    continue

                # store valid phone number
                self.targets.append(result['area'] + result['line'])

        else:
            # Send a message to ourselves
            self.targets.append(self.source)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Voipms Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no Voipms targets to notify.')
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # Prepare our payload
        payload = {
            'api_username': self.email,
            'api_password': self.password,
            'did': self.source,
            'message': body,
            'method': 'sendSMS',

            # Gets filled in the loop below
            'dst': None
        }

        # Create a copy of the targets list
        targets = list(self.targets)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Add target Phone #
            payload['dst'] = target

            # Some Debug Logging
            self.logger.debug('Voipms GET URL: {} (cert_verify={})'.format(
                self.notify_url, self.verify_certificate))
            self.logger.debug('Voipms Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            response = {'status': 'unknown', 'message': ''}

            try:
                r = requests.get(
                    self.notify_url,
                    params=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                try:
                    response = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # ValueError = r.content is Unparsable
                    # TypeError = r.content is None
                    # AttributeError = r is None
                    pass

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyVoipms.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Voipms notification to {}: '
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

                # Voipms sends 200 OK even if there is an error
                # check if status in response and if it is not success

                if response is not None and response['status'] != 'success':
                    self.logger.warning(
                        'Failed to send Voipms notification to {}: '
                        'status: {}, message: {}'.format(
                            target, response['status'], response['message'])
                    )

                    # Mark our failure
                    has_error = True
                    continue
                else:
                    self.logger.info(
                        'Sent Voipms notification to %s' % target)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Voipms:%s '
                    'notification.' % target
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
        return (
            self.secure_protocol, self.email, self.password, self.source,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        schemaStr =  \
            '{schema}://{password}:{email}/{from_phone}/{targets}/?{params}'
        return schemaStr.format(
            schema=self.secure_protocol,
            email=self.email,
            password=self.pprint(self.password, privacy, safe=''),
            from_phone='1' + self.pprint(self.source, privacy, safe=''),
            targets='/'.join(
                ['1' + NotifyVoipms.quote(x, safe='') for x in self.targets]),
            params=NotifyVoipms.urlencode(params))

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

        results['targets'] = \
            NotifyVoipms.split_path(results['fullpath'])

        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyVoipms.unquote(results['qsd']['from'])

        elif results['targets']:
            # The from phone no is the first entry in the list otherwise
            results['source'] = results['targets'].pop(0)

        # Swap user for pass since our input is: password:email
        #   where email is user@hostname (or user@domain)
        user = results['password']
        password = results['user']
        results['password'] = password
        results['user'] = user

        results['email'] = '{}@{}'.format(
            NotifyVoipms.unquote(user),
            NotifyVoipms.unquote(results['host']),
        )

        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyVoipms.parse_phone_no(results['qsd']['to'])

        return results
