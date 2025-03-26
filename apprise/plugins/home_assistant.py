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

# You must generate a "Long-Lived Access Token". This can be done from your
# Home Assistant Profile page.
import re
import math
import requests
from itertools import chain
from json import dumps

from uuid import uuid4
from ..utils.parse import (
    parse_bool, parse_domain_service_targets,
    is_domain_service_target)

from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils.parse import validate_regex
from ..locale import gettext_lazy as _

# This regex matches exactly 8 hex digits,
# a dot, then exactly 64 hex digits. it can also be a JWT
# token in which case it will be 180 characters+
RE_IS_LONG_LIVED_TOKEN = re.compile(
    r'^([0-9a-f]{8}\.[0-9a-f]{64}|[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+)$',
    re.I)

# Define our supported device notification formats:
# - service
#     - default domain is always 'notify' if one isn't detected
# - service:target
# - service:target1,target2,target3
# - domain.service
# - domain.service:target
# - domain.service:target1,target2,target3
# -   - targets can be comma/space separated if more hten one
# - service:target1,target2,target3

# Define a persistent entry (used for handling message delivery
PERSISTENT_ENTRY = (None, None, [])


class NotifyHomeAssistant(NotifyBase):
    """
    A wrapper for Home Assistant Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'HomeAssistant'

    # The services URL
    service_url = 'https://www.home-assistant.io/'

    # Insecure Protocol Access
    protocol = 'hassio'

    # Secure Protocol
    secure_protocol = 'hassios'

    # Default to Home Assistant Default Insecure port of 8123 instead of 80
    default_insecure_port = 8123

    # The maximum amount of services that can be notified in a single batch
    default_batch_size = 10

    # The default ha notification domain if one isn't detected
    default_domain = 'notify'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_homeassistant'

    # Define object templates
    templates = (
        '{schema}://{host}/{token}',
        '{schema}://{host}:{port}/{token}',
        '{schema}://{user}@{host}/{token}',
        '{schema}://{user}@{host}:{port}/{token}',
        '{schema}://{user}:{password}@{host}/{token}',
        '{schema}://{user}:{password}@{host}:{port}/{token}',
        '{schema}://{host}/{token}/{targets}',
        '{schema}://{host}:{port}/{token}/{targets}',
        '{schema}://{user}@{host}/{token}/{targets}',
        '{schema}://{user}@{host}:{port}/{token}/{targets}',
        '{schema}://{user}:{password}@{host}/{token}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{token}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
        'user': {
            'name': _('Username'),
            'type': 'string',
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
        'token': {
            'name': _('Long-Lived Access Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_device': {
            'name': _('Target Device'),
            'type': 'string',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'nid': {
            # Optional Unique Notification ID
            'name': _('Notification ID'),
            'type': 'string',
            'regex': (r'^[a-z0-9_-]+$', 'i'),
        },
        'prefix': {
            # Path Prefix to use (for those not hosting their hasio instance
            # in /)
            'name': _('Path Prefix'),
            'type': 'string',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, token, nid=None, targets=None, prefix=None,
                 batch=None, **kwargs):
        """
        Initialize Home Assistant Object
        """
        super().__init__(**kwargs)

        self.prefix = prefix or kwargs.get('fullpath', '')

        if not (self.secure or self.port):
            # Use default insecure port
            self.port = self.default_insecure_port

        # Long-Lived Access token (generated from User Profile)
        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Home Assistant Long-Lived Access Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # An Optional Notification Identifier
        self.nid = None
        if nid:
            self.nid = validate_regex(
                nid, *self.template_args['nid']['regex'])
            if not self.nid:
                msg = 'An invalid Home Assistant Notification Identifier ' \
                      '({}) was specified.'.format(nid)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Prepare Batch Mode Flag
        self.batch = self.template_args['batch']['default'] \
            if batch is None else batch

        # Store our targets
        self.targets = []

        # Track our invalid targets
        self._invalid_targets = list()

        if targets:
            for target in parse_domain_service_targets(targets):
                result = is_domain_service_target(
                    target, domain=self.default_domain)
                if result:
                    self.targets.append((
                        result['domain'],
                        result['service'],
                        result['targets'],
                    ))
                    continue

                self.logger.warning(
                    'Dropped invalid [domain.]service[:target] entry '
                    '({}) specified.'.format(target),
                )
                self._invalid_targets.append(target)
        else:
            self.targets = [PERSISTENT_ENTRY]

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Sends Message
        """

        if not self.targets:
            self.logger.warning(
                'There are no valid Home Assistant targets to notify.')
            return False

        # Prepare our persistent_notification.create payload
        payload = {
            'title': title,
            'message': body,
        }

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.token),
        }

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '{}://{}'.format(schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        # Determine if we're doing it the old way (using persistent notices)
        # or the new (supporting device targets)
        has_targets = True if not self.targets or self.targets[0] \
            is not PERSISTENT_ENTRY else False

        # our base url
        base_url = url + self.prefix.rstrip('/') + \
            '/api/services/persistent_notification/create'

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        for target in self.targets:
            # Use a unique ID so we don't over-write the last message we
            # posted. Otherwise use the notification id specified
            if has_targets:
                # Base target details
                domain = target[0]
                service = target[1]

                # Prepare our URL
                base_url = url + self.prefix.rstrip('/') + \
                    f'/api/services/{domain}/{service}'

                # Possibly prepare batches
                if target[2]:
                    _payload = payload.copy()
                    for index in range(0, len(target[2]), batch_size):
                        _payload['targets'] = \
                            target[2][index:index + batch_size]
                        if not self._ha_post(
                                base_url, _payload, headers, auth):
                            return False

                    # We're done
                    return True

            if not self._ha_post(base_url, payload, headers, auth):
                return False

        return True

    def _ha_post(self, url, payload, headers, auth=None):
        """
        Wrapper to single upstream server post
        """
        # Notification ID
        payload['notification_id'] = self.nid if self.nid else str(uuid4())

        self.logger.debug(
            'Home Assistant POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate))
        self.logger.debug('Home Assistant Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyHomeAssistant.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send Home Assistant notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Home Assistant notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Home Assistant '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
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
            self.user, self.password, self.host,
            self.port if self.port else (
                443 if self.secure else self.default_insecure_port),
            self.prefix.rstrip('/'),
            self.token,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'batch': 'yes' if self.batch else 'no',
        }

        if self.prefix not in ('', '/'):
            params['prefix'] = '/' if not self.prefix \
                else '/{}/'.format(self.prefix.strip('/'))

        if self.nid:
            params['nid'] = self.nid

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyHomeAssistant.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyHomeAssistant.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else self.default_insecure_port

        url = '{schema}://{auth}{hostname}{port}/' \
              '{token}/{targets}?{params}'

        # Determine if we're doing it the old way (using persistent notices)
        # or the new (supporting device targets)
        has_targets = True if not self.targets or self.targets[0] \
            is not PERSISTENT_ENTRY else False

        return url.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if not self.port or self.port == default_port
            else ':{}'.format(self.port),
            token=self.pprint(self.token, privacy, safe=''),
            targets='' if not has_targets else '/'.join(
                chain([NotifyHomeAssistant.quote('{}.{}{}'.format(
                    x[0], x[1], ''
                    if not x[2] else ':' + ','.join(x[2])), safe='')
                    for x in self.targets],
                    [NotifyHomeAssistant.quote(x, safe='')
                     for x in self._invalid_targets])),
            params=NotifyHomeAssistant.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #

        # Determine if we're doing it the old way (using persistent notices)
        # or the new (supporting device targets)
        has_targets = True if not self.targets or self.targets[0] \
            is not PERSISTENT_ENTRY else False

        if not has_targets:
            return 1

        # Handle targets
        batch_size = 1 if not self.batch else self.default_batch_size
        return sum(
            math.ceil(len(identities) / batch_size)
            if identities else 1 for _, _, identities in self.targets)

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

        # Set our path to use:
        if 'prefix' in results['qsd'] and len(results['qsd']['prefix']):
            results['prefix'] = \
                NotifyHomeAssistant.unquote(results['qsd']['prefix'])

        # Long Lived Access token placeholder
        results['token'] = None

        # Get our Long-Lived Access Token (if defined)
        if 'token' in results['qsd'] and \
                len(results['qsd']['token']):
            results['token'] = \
                NotifyHomeAssistant.unquote(results['qsd']['token'])

        # Acquire our full path
        tokens = NotifyHomeAssistant.split_path(results['fullpath'])
        results['targets'] = []

        while tokens:
            # Iterate through our tokens
            token = tokens.pop()
            if not results['token']:
                if RE_IS_LONG_LIVED_TOKEN.match(token):
                    # Store our access token
                    results['token'] = token

                    # Re-assemble our full path
                    results['fullpath'] = '/' + '/'.join(tokens)
                    continue

                # If we don't have an access token, then we can assume
                # it's a device we're storing
                results['targets'].append(token)
                continue

            elif 'prefix' not in results:
                # Re-assemble our full path
                results['fullpath'] = '/' + '/'.join(tokens + [token])

                # We're done
                break

            # prefix is in the result set, so therefore we're dealing with a
            # custom target/service
            results['targets'].append(token)

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch',
                NotifyHomeAssistant.template_args['batch']['default']))

        # Allow the specification of a unique notification_id so that
        # it will always replace the last one sent.
        if 'nid' in results['qsd'] and len(results['qsd']['nid']):
            results['nid'] = \
                NotifyHomeAssistant.unquote(results['qsd']['nid'])

        return results
