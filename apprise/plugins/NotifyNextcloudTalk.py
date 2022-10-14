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
# OUT OF OR IN CON

import requests

from json import dumps
from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _


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
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
            'required': True,
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
    }

    def __init__(self, targets=None, headers=None, **kwargs):
        """
        Initialize Nextcloud Talk Object
        """
        super().__init__(**kwargs)

        if self.user is None or self.password is None:
            msg = 'User and password have to be specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        self.targets = parse_list(targets)
        if len(self.targets) == 0:
            msg = 'At least one Nextcloud Talk Room ID must be specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Nextcloud Talk Notification
        """

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
            notify_url = '{schema}://{host}'\
                         '/ocs/v2.php/apps/spreed/api/v1/chat/{target}'

            notify_url = notify_url.format(
                schema='https' if self.secure else 'http',
                host=self.host if not isinstance(self.port, int)
                else '{}:{}'.format(self.host, self.port),
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
                if r.status_code != requests.codes.created:
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

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Determine Authentication
        auth = '{user}:{password}@'.format(
            user=NotifyNextcloudTalk.quote(self.user, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
        )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{targets}' \
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
               )

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

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results['headers'] = {
            NotifyNextcloudTalk.unquote(x): NotifyNextcloudTalk.unquote(y)
            for x, y in results['qsd+'].items()}

        return results
