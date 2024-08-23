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

from json import dumps
from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils import parse_list
from ..locale import gettext_lazy as _


class NotifyNextcloudTalk(NotifyBase):
    """
    A wrapper for Nextcloud Talk Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = _('Nextcloud Talk')

    # The services URL
    service_url = 'https://nextcloud.com/talk'

    # Insecure protocol (for those self hosted requests)
    protocol = 'nctalk'

    # The default protocol (this is secure for notica)
    secure_protocol = 'nctalks'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_nextcloudtalk'

    # Nextcloud title length
    title_maxlen = 255

    # Defines the maximum allowable characters per message.
    body_maxlen = 4000

    # Define object templates
    templates = (
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
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_room_id': {
            'name': _('Room ID'),
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
        'url_prefix': {
            'name': _('URL Prefix'),
            'type': 'string',
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
    }

    def __init__(self, targets=None, headers=None, url_prefix=None, **kwargs):
        """
        Initialize Nextcloud Talk Object
        """
        super().__init__(**kwargs)

        if self.user is None or self.password is None:
            msg = 'User and password have to be specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our targets
        self.targets = parse_list(targets)

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
        Perform Nextcloud Talk Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning(
                'There were no Nextcloud Talk targets to notify.')
            return False

        # Prepare our Header
        headers = {
            'User-Agent': self.app_id,
            'OCS-APIRequest': 'true',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
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
            if not body:
                payload = {
                    'message': title if title else self.app_desc,
                }
            else:
                payload = {
                    'message': title + '\r\n' + body
                    if title else self.app_desc + '\r\n' + body,
                }

            # Nextcloud Talk URL
            notify_url = '{schema}://{host}/{url_prefix}'\
                         '/ocs/v2.php/apps/spreed/api/v1/chat/{target}'

            notify_url = notify_url.format(
                schema='https' if self.secure else 'http',
                host=self.host if not isinstance(self.port, int)
                else '{}:{}'.format(self.host, self.port),
                url_prefix=self.url_prefix,
                target=target,
            )

            self.logger.debug(
                'Nextcloud Talk POST URL: %s (cert_verify=%r)',
                notify_url, self.verify_certificate)
            self.logger.debug(
                'Nextcloud Talk Payload: %s',
                str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    notify_url,
                    data=dumps(payload),
                    headers=headers,
                    auth=(self.user, self.password),
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    # We had a problem
                    status_str = \
                        NotifyNextcloudTalk.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Nextcloud Talk notification:'
                        '{}{}error={}.'.format(
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
                        'Sent Nextcloud Talk notification.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Nextcloud Talk '
                    'notification.')
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

        # Our default set of parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})
        if self.url_prefix:
            params['url_prefix'] = self.url_prefix

        # Determine Authentication
        auth = '{user}:{password}@'.format(
            user=NotifyNextcloudTalk.quote(self.user, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
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
                   targets='/'.join([NotifyNextcloudTalk.quote(x)
                                     for x in self.targets]),
                   params=NotifyNextcloudTalk.urlencode(params),
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
            NotifyNextcloudTalk.split_path(results['fullpath'])

        # Support URL Prefixes
        if 'url_prefix' in results['qsd'] \
                and len(results['qsd']['url_prefix']):
            results['url_prefix'] = \
                NotifyNextcloudTalk.unquote(results['qsd']['url_prefix'])

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results['headers'] = {
            NotifyNextcloudTalk.unquote(x): NotifyNextcloudTalk.unquote(y)
            for x, y in results['qsd+'].items()}

        return results
