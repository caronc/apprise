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

import requests

from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils import parse_list
from ..locale import gettext_lazy as _


class NotifyNextcloud(NotifyBase):
    """
    A wrapper for Nextcloud Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Nextcloud'

    # The services URL
    service_url = 'https://nextcloud.com/'

    # Insecure protocol (for those self hosted requests)
    protocol = 'ncloud'

    # The default protocol (this is secure for notica)
    secure_protocol = 'nclouds'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_nextcloud'

    # Nextcloud title length
    title_maxlen = 255

    # Defines the maximum allowable characters per message.
    body_maxlen = 4000

    # Define object templates
    templates = (
        '{schema}://{host}/{targets}',
        '{schema}://{host}:{port}/{targets}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
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
        'target_user': {
            'name': _('Target User'),
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
        # Nextcloud uses different API end points depending on the version
        # being used however the (API) payload remains the same.  Allow users
        # to specify the version they are using:
        'version': {
            'name': _('Version'),
            'type': 'int',
            'min': 1,
            'default': 21,
        },
        'url_prefix': {
            'name': _('URL Prefix'),
            'type': 'string',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
    }

    def __init__(self, targets=None, version=None, headers=None,
                 url_prefix=None, **kwargs):
        """
        Initialize Nextcloud Object
        """
        super().__init__(**kwargs)

        # Store our targets
        self.targets = parse_list(targets)

        self.version = self.template_args['version']['default']
        if version is not None:
            try:
                self.version = int(version)
                if self.version < self.template_args['version']['min']:
                    # Let upper exception handle this
                    raise ValueError()

            except (ValueError, TypeError):
                msg = 'At invalid Nextcloud version ({}) was specified.'\
                    .format(version)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Support URL Prefix
        self.url_prefix = '' if not url_prefix \
            else url_prefix.strip('/')

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Nextcloud Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning('There were no Nextcloud targets to notify.')
            return False

        # Prepare our Header
        headers = {
            'User-Agent': self.app_id,
            'OCS-APIREQUEST': 'true',
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)

            # Prepare our Payload
            payload = {
                'shortMessage': title if title else self.app_desc,
            }
            if body:
                # Only store the longMessage if a body was defined; nextcloud
                # doesn't take kindly to empty longMessage entries.
                payload['longMessage'] = body

            auth = None
            if self.user:
                auth = (self.user, self.password)

            # Nextcloud URL based on version used
            notify_url = '{schema}://{host}/{url_prefix}/ocs/v2.php/'\
                'apps/admin_notifications/' \
                'api/v1/notifications/{target}' \
                if self.version < 21 else \
                '{schema}://{host}/{url_prefix}/ocs/v2.php/'\
                'apps/notifications/'\
                'api/v2/admin_notifications/{target}'

            notify_url = notify_url.format(
                schema='https' if self.secure else 'http',
                host=self.host if not isinstance(self.port, int)
                else '{}:{}'.format(self.host, self.port),
                url_prefix=self.url_prefix,
                target=target,
            )

            self.logger.debug(
                'Nextcloud v%d POST URL: %s (cert_verify=%r)',
                self.version, notify_url, self.verify_certificate)
            self.logger.debug(
                'Nextcloud v%d Payload: %s',
                self.version, str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    notify_url,
                    data=payload,
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyNextcloud.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Nextcloud v{} notification:'
                        '{}{}error={}.'.format(
                            self.version,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))
                    # track our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent Nextcloud %d notification.', self.version)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Nextcloud v%d'
                    'notification.', self.version)
                self.logger.debug('Socket Exception: %s' % str(e))

                # track our failure
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
            self.user, self.password, self.host, self.port,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Create URL parameters from our headers
        params = {'+{}'.format(k): v for k, v in self.headers.items()}

        # Set our version
        params['version'] = str(self.version)

        if self.url_prefix:
            params['url_prefix'] = self.url_prefix

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyNextcloud.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyNextcloud.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{targets}?{params}' \
               .format(
                   schema=self.secure_protocol
                   if self.secure else self.protocol,
                   auth=auth,
                   # never encode hostname since we're expecting it to be a
                   # valid one
                   hostname=self.host,
                   port='' if self.port is None or self.port == default_port
                        else ':{}'.format(self.port),
                   targets='/'.join([NotifyNextcloud.quote(x)
                                     for x in self.targets]),
                   params=NotifyNextcloud.urlencode(params),
               )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
        return targets if targets else 1

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Fetch our targets
        results['targets'] = \
            NotifyNextcloud.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyNextcloud.parse_list(results['qsd']['to'])

        # Allow users to over-ride the Nextcloud version being used
        if 'version' in results['qsd'] and len(results['qsd']['version']):
            results['version'] = \
                NotifyNextcloud.unquote(results['qsd']['version'])

        # Support URL Prefixes
        if 'url_prefix' in results['qsd'] \
                and len(results['qsd']['url_prefix']):
            results['url_prefix'] = \
                NotifyNextcloud.unquote(results['qsd']['url_prefix'])

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results['headers'] = {
            NotifyNextcloud.unquote(x): NotifyNextcloud.unquote(y)
            for x, y in results['qsd+'].items()}

        return results
