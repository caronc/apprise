# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

# Create an account https://msg91.com/ if you don't already have one
#
# Get your (authkey) from the dashboard here:
#   - https://world.msg91.com/user/index.php#api
#
# Get details on the API used in this plugin here:
#   - https://world.msg91.com/apidoc/textsms/send-sms.php

import requests

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class MSG91Route:
    """
    Transactional SMS Routes
    route=1 for promotional, route=4 for transactional SMS.
    """
    PROMOTIONAL = 1
    TRANSACTIONAL = 4


# Used for verification
MSG91_ROUTES = (
    MSG91Route.PROMOTIONAL,
    MSG91Route.TRANSACTIONAL,
)


class MSG91Country:
    """
    Optional value that can be specified on the MSG91 api
    """
    INTERNATIONAL = 0
    USA = 1
    INDIA = 91


# Used for verification
MSG91_COUNTRIES = (
    MSG91Country.INTERNATIONAL,
    MSG91Country.USA,
    MSG91Country.INDIA,
)


class NotifyMSG91(NotifyBase):
    """
    A wrapper for MSG91 Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'MSG91'

    # The services URL
    service_url = 'https://msg91.com'

    # The default protocol
    secure_protocol = 'msg91'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_msg91'

    # MSG91 uses the http protocol with JSON requests
    notify_url = 'https://world.msg91.com/api/sendhttp.php'

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{authkey}/{targets}',
        '{schema}://{sender}@{authkey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'authkey': {
            'name': _('Authentication Key'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
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
        'sender': {
            'name': _('Sender ID'),
            'type': 'string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'route': {
            'name': _('Route'),
            'type': 'choice:int',
            'values': MSG91_ROUTES,
            'default': MSG91Route.TRANSACTIONAL,
        },
        'country': {
            'name': _('Country'),
            'type': 'choice:int',
            'values': MSG91_COUNTRIES,
        },
    })

    def __init__(self, authkey, targets=None, sender=None, route=None,
                 country=None, **kwargs):
        """
        Initialize MSG91 Object
        """
        super().__init__(**kwargs)

        # Authentication Key (associated with project)
        self.authkey = validate_regex(
            authkey, *self.template_tokens['authkey']['regex'])
        if not self.authkey:
            msg = 'An invalid MSG91 Authentication Key ' \
                  '({}) was specified.'.format(authkey)
            self.logger.warning(msg)
            raise TypeError(msg)

        if route is None:
            self.route = self.template_args['route']['default']

        else:
            try:
                self.route = int(route)
                if self.route not in MSG91_ROUTES:
                    # Let outer except catch thi
                    raise ValueError()

            except (ValueError, TypeError):
                msg = 'The MSG91 route specified ({}) is invalid.'\
                    .format(route)
                self.logger.warning(msg)
                raise TypeError(msg)

        if country:
            try:
                self.country = int(country)
                if self.country not in MSG91_COUNTRIES:
                    # Let outer except catch thi
                    raise ValueError()

            except (ValueError, TypeError):
                msg = 'The MSG91 country specified ({}) is invalid.'\
                    .format(country)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.country = country

        # Store our sender
        self.sender = sender

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
        Perform MSG91 Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no MSG91 targets to notify.')
            return False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # Prepare our payload
        payload = {
            'sender': self.sender if self.sender else self.app_id,
            'authkey': self.authkey,
            'message': body,
            'response': 'json',
            # target phone numbers are sent with a comma delimiter
            'mobiles': ','.join(self.targets),
            'route': str(self.route),
        }

        if self.country:
            payload['country'] = str(self.country)

        # Some Debug Logging
        self.logger.debug('MSG91 POST URL: {} (cert_verify={})'.format(
            self.notify_url, self.verify_certificate))
        self.logger.debug('MSG91 Payload: {}' .format(payload))

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
                    NotifyMSG91.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send MSG91 notification to {}: '
                    '{}{}error={}.'.format(
                        ','.join(self.targets),
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return False

            else:
                self.logger.info(
                    'Sent MSG91 notification to %s.' % ','.join(self.targets))

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending MSG91:%s '
                'notification.' % ','.join(self.targets)
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
            'route': str(self.route),
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.country:
            params['country'] = str(self.country)

        return '{schema}://{authkey}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            authkey=self.pprint(self.authkey, privacy, safe=''),
            targets='/'.join(
                [NotifyMSG91.quote(x, safe='') for x in self.targets]),
            params=NotifyMSG91.urlencode(params))

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
        results['targets'] = NotifyMSG91.split_path(results['fullpath'])

        # The hostname is our authentication key
        results['authkey'] = NotifyMSG91.unquote(results['host'])

        if 'route' in results['qsd'] and len(results['qsd']['route']):
            results['route'] = results['qsd']['route']

        if 'country' in results['qsd'] and len(results['qsd']['country']):
            results['country'] = results['qsd']['country']

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyMSG91.parse_phone_no(results['qsd']['to'])

        return results
