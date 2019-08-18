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

# Create an account https://msg91.com/ if you don't already have one
#
# Get your (authkey) from the dashboard here:
#   - https://world.msg91.com/user/index.php#api
#
# Get details on the API used in this plugin here:
#   - https://world.msg91.com/apidoc/textsms/send-sms.php

import re
import requests

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _

# Token required as part of the API request
VALIDATE_AUTHKEY = re.compile(r'^[a-z0-9]+$', re.I)

# Some Phone Number Detection
IS_PHONE_NO = re.compile(r'^\+?(?P<phone>[0-9\s)(+-]+)\s*$')


class MSG91Route(object):
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


class MSG91Country(object):
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
    body_maxlen = 140

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
            'regex': (r'AC[a-z0-9]+', 'i'),
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'[0-9\s)(+-]+', 'i'),
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
            'name': _('Route'),
            'type': 'choice:int',
            'values': MSG91_COUNTRIES,
        },
    })

    def __init__(self, authkey, targets=None, sender=None, route=None,
                 country=None, **kwargs):
        """
        Initialize MSG91 Object
        """
        super(NotifyMSG91, self).__init__(**kwargs)

        try:
            # The authentication key associated with the account
            self.authkey = authkey.strip()

        except AttributeError:
            # Token was None
            msg = 'No MSG91 authentication key was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_AUTHKEY.match(self.authkey):
            msg = 'The MSG91 authentication key specified ({}) is invalid.'\
                .format(self.authkey)
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

        for target in parse_list(targets):
            # Validate targets and drop bad ones:
            result = IS_PHONE_NO.match(target)
            if result:
                # Further check our phone # for it's digit count
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
                'Dropped invalid phone # '
                '({}) specified.'.format(target),
            )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform MSG91 Notification
        """

        if not len(self.targets):
            # There were no services to notify
            self.logger.warning('There were no MSG91 targets to notify')
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
                'A Connection error occured sending MSG91:%s '
                'notification.' % ','.join(self.targets)
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
            'route': str(self.route),
        }

        if self.country:
            args['country'] = str(self.country)

        return '{schema}://{authkey}/{targets}/?{args}'.format(
            schema=self.secure_protocol,
            authkey=self.authkey,
            targets='/'.join(
                [NotifyMSG91.quote(x, safe='') for x in self.targets]),
            args=NotifyMSG91.urlencode(args))

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
                NotifyMSG91.parse_list(results['qsd']['to'])

        return results
