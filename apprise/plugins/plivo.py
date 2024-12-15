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

import requests

from json import dumps
from .base import NotifyBase
from ..common import NotifyType
from ..utils.parse import (
    parse_bool, is_phone_no, parse_phone_no, validate_regex)
from ..locale import gettext_lazy as _


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

    # The maximum number of messages that can be sent in a single batch
    default_batch_size = 20

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
        'token': {
            'alias_of': 'token',
        },
        'id': {
            'alias_of': 'auth_id',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, auth_id, token, source, targets=None, batch=None,
                 **kwargs):
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

        result = is_phone_no(source)
        if not result:
            msg = 'The Plivo source specified ({}) is invalid.'\
                .format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our source; enforce E.164 format
        self.source = f'+{result["full"]}'

        # Parse our targets
        self.targets = list()

        if targets:
            for target in parse_phone_no(targets):
                # Validate targets and drop bad ones:
                result = is_phone_no(target)
                if result:
                    # store valid phone number; enforce E.164 format
                    self.targets.append(f'+{result["full"]}')
                    continue

                self.logger.warning(
                    'Dropped invalid phone # '
                    '({}) specified.'.format(target),
                )
        else:
            # No sources specified, use our own phone no
            self.targets.append(self.source)

        # Set batch
        self.batch = batch if batch is not None \
            else self.template_args['batch']['default']

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Plivo Notification
        """

        if not self.targets:
            # There were no services to notify
            self.logger.warning(
                'There were no Plivo targets to notify.')
            return False

        # Initialize our has_error flag
        has_error = False

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

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        for index in range(0, len(self.targets), batch_size):
            # Prepare our phone no (< delimits more then one)
            payload['recipients'] = \
                ','.join(self.targets[index:index + batch_size])

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
                    data=dumps(payload),
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                        requests.codes.ok, requests.codes.accepted):
                    # We had a problem
                    status_str = \
                        NotifyPlivo.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send {} Plivo notification{}: '
                        '{}{}error={}.'.format(
                            len(self.targets[index:index + batch_size]),
                            ' to {}'.format(self.targets[index])
                            if batch_size == 1 else '(s)',
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Send {} Plivo notification{}'.format(
                            len(self.targets[index:index + batch_size]),
                            ' to {}'.format(self.targets[index])
                            if batch_size == 1 else '(s)',
                        ))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending Plivo:%s ' % (
                        self.targets) + 'notification.'
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
            self.secure_protocol if self.secure else self.protocol,
            self.auth_id, self.token, self.source,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        params = {
            'batch': 'yes' if self.batch else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{auth_id}@{token}/{source}/' \
            '{targets}/?{params}'.format(
                schema=self.secure_protocol,
                auth_id=self.pprint(self.auth_id, privacy, safe=''),
                token=self.pprint(self.token, privacy, safe=''),
                source=self.source,
                targets='/'.join(
                    [NotifyPlivo.quote(x, safe='+') for x in self.targets]),
                params=NotifyPlivo.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The Auth ID is in the username field
        if 'id' in results['qsd'] and len(results['qsd']['id']):
            results['auth_id'] = NotifyPlivo.unquote(results['qsd']['id'])

        else:
            results['auth_id'] = NotifyPlivo.unquote(results['user'])

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifyPlivo.split_path(results['fullpath'])
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            # Store token
            results['token'] = NotifyPlivo.unquote(results['qsd']['token'])

            # go ahead and put the host entry in the targets list
            if results['host']:
                results['targets'].insert(
                    0, NotifyPlivo.unquote(results['host']))

        else:
            # The hostname is our authentication key
            results['token'] = NotifyPlivo.unquote(results['host'])

        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyPlivo.unquote(results['qsd']['from'])

        else:
            try:
                # The first path entry is the source/originator
                results['source'] = results['targets'].pop(0)

            except IndexError:
                # No source specified...
                results['source'] = None
                pass

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPlivo.parse_phone_no(results['qsd']['to'])

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifyPlivo.template_args['batch']['default']))

        return results
