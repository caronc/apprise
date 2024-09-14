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

# Create an account https://messagebird.com if you don't already have one
#
# Get your auth_id and auth token from the dashboard here:
#   - https://console.plivo.com/dashboard/
#

import re
import requests

from .base import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..utils import validate_regex
from ..locale import gettext_lazy as _

# Some Phone Number Detection
IS_PHONE_NO = re.compile(r'^\+?(?P<phone>[0-9\s)(+-]+)\s*$')


class NotifyPlivo(NotifyBase):
    """
    A wrapper for Plivo Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Plivo'

    # The services URL
    service_url = 'https://plivo.com'

    # The default protocol
    secure_protocol = 'plivo'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_plivo'

    # Plivo uses the http protocol with JSON requests
    notify_url = 'https://api.plivo.com/v1/Account/{auth_id}/Message/'

    # The maximum length of the body
    body_maxlen = 140

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{auth_id}@{token}/{source}',
        '{schema}://{auth_id}@{token}/{source}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'auth_id': {
            'name': _('Auth ID'),
            'type': 'string',
            'required': True,
            'regex': (r'^[a-z0-9]{20,30}$', 'i'),
        },
        'token': {
            'name': _('Auth Token'),
            'type': 'string',
            'required': True,
            'regex': (r'^[a-z0-9]{30,50}$', 'i'),
        },
        'source': {
            'name': _('Source Phone No'),
            'type': 'string',
            'prefix': '+',
            'required': True,
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
        }
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

    def __init__(self, auth_id, token, source, targets=None, **kwargs):
        """
        Initialize Plivo Object
        """
        super(NotifyPlivo, self).__init__(**kwargs)

        self.auth_id = validate_regex(
            auth_id, *self.template_tokens['auth_id']['regex'])
        if not self.auth_id:
            msg = 'The Plivo authentication ID specified ({}) is ' \
                'invalid.'.format(auth_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.token = validate_regex(
            token, *self.template_tokens['token']['regex'])
        if not self.token:
            msg = 'The Plivo authentication token specified ({}) is ' \
                'invalid.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        result = IS_PHONE_NO.match(source)
        if not result:
            msg = 'The Plivo source specified ({}) is invalid.'\
                .format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Further check our phone # for it's digit count
        result = ''.join(re.findall(r'\d+', result.group('phone')))
        if len(result) < 11 or len(result) > 14:
            msg = 'The Plivo source # specified ({}) is invalid.'\
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
        Perform Plivo Notification
        """

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # Prepare our authentication
        auth = (self.auth_id, self.token)

        # Prepare our payload
        payload = {
            'src': self.source,
            'dst': None,
            'text': body,

        }
        # Create a copy of the targets list
        targets = list(self.targets)

        if len(targets) == 0:
            # No sources specified, use our own phone no
            targets.append(self.source)

        # Prepare our phone no (< delimits more then one)
        payload['recipients'] = '<'.join(self.targets)

        # Some Debug Logging
        self.logger.debug(
            'Plivo POST URL: {} (cert_verify={})'.format(
                self.notify_url, self.verify_certificate))
        self.logger.debug('Plivo Payload: {}' .format(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )

            if r.status_code not in (
                    requests.codes.ok, requests.codes.accepted):
                # We had a problem
                status_str = \
                    NotifyPlivo.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send Plivo notification to {}: '
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
                    'Sent Plivo notification to {}.'.format(self.targets))

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Plivo:%s ' % (
                    self.targets) + 'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            return False

        return True

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.auth_id, self.token, self.source,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://{auth_id}@{token}/{source}/' \
            '{targets}/?{args}'.format(
                schema=self.secure_protocol,
                auth_id=self.pprint(self.auth_id, privacy, safe=''),
                token=self.pprint(self.token, privacy, safe=''),
                source=self.source,
                targets='/'.join(
                    [NotifyPlivo.quote(x, safe='') for x in self.targets]),
                args=NotifyPlivo.urlencode(args))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
        targets = len(self.targets)
        return targets if targets > 0 else 1

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

        # The Auth ID is in the username field
        results['auth_id'] = NotifyPlivo.unquote(results['user'])

        # The hostname is our authentication key
        results['token'] = NotifyPlivo.unquote(results['host'])

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifyPlivo.split_path(results['fullpath'])

        try:
            # The first path entry is the source/originator
            results['source'] = results['targets'].pop(0)
        except IndexError:
            # No path specified... this URL is potentially un-parseable; we can
            # hope for a from= entry
            pass

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPlivo.parse_list(results['qsd']['to'])

        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyPlivo.unquote(results['qsd']['from'])

        return results
