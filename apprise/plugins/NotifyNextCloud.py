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

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _


class NotifyNextCloud(NotifyBase):
    """
    A wrapper for NextCloud Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'NextCloud'

    # The services URL
    service_url = 'https://github.com/nextcloud/notifications'

    # Insecure protocol (for those self hosted requests)
    protocol = 'nextcloud'

    # The default protocol (this is secure for notica)
    secure_protocol = 'nextclouds'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_nextcloud'

    # NextCloud URL
    notify_url = '{schema}://{host}/ocs/v2.php/apps/admin_notifications/' \
                 'api/v1/notifications/{target}'

    # NextCloud does not support a title
    title_maxlen = 0

    # Defines the maximum allowable characters per message.
    body_maxlen = 4000

    # If the message is less than this number of characters, there is another
    # method of posting the message to Nextcloud. We use this if we can, but
    # otherwise fall back to the larger size (which is our Apprise fixed limit)
    # defined above.
    short_message_length = 255

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

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
    }

    def __init__(self, targets=None, headers=None, **kwargs):
        """
        Initialize NextCloud Object
        """
        super(NotifyNextCloud, self).__init__(**kwargs)

        self.targets = parse_list(targets)
        if len(self.targets) == 0:
            msg = 'At least one NextCloud target user must be specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform NextCloud Notification
        """

        # Prepare our Header
        headers = {
            'User-Agent': self.app_id,
        }

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)

            # Prepare our Payload
            payload = {}
            if len(body) > 255:
                payload['longMessage'] = body

            else:
                payload['shortMessage'] = body

            # Auth is used for SELFHOSTED queries
            auth = (self.user, self.password)

            notify_url = self.notify_url.format(
                schema='https' if self.secure else 'http',
                host=self.host if not isinstance(self.port, int)
                else '{}:{}'.format(self.host, self.port),
                target=target,
            )

            self.logger.debug('NextCloud POST URL: %s (cert_verify=%r)' % (
                notify_url, self.verify_certificate,
            ))
            self.logger.debug('NextCloud Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    notify_url.format(token=self.token),
                    data=payload,
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyNextCloud.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send NextCloud notification:'
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
                    self.logger.info('Sent NextCloud notification.')

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending NextCloud '
                    'notification.',
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # track our failure
                has_error = True
                continue

        return not has_error

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

        # Append our headers into our args
        args.update({'+{}'.format(k): v for k, v in self.headers.items()})

        auth = '{user}:{password}@'.format(
            user=NotifyNextCloud.quote(self.user, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
        )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{targets}?{args}' \
               .format(
                   schema=self.secure_protocol
                   if self.secure else self.protocol,
                   auth=auth,
                   hostname=NotifyNextCloud.quote(self.host, safe=''),
                   port='' if self.port is None or self.port == default_port
                        else ':{}'.format(self.port),
                   fullpath=NotifyNextCloud.quote(
                       self.fullpath, safe='/'),
                   targets='/'.join([NotifyNextCloud.quote(x)
                                     for x in self.targets]),
                   args=NotifyNextCloud.urlencode(args),
               )

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

        # Fetch our targets
        results['targets'] = \
            NotifyNextCloud.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyNextCloud.parse_list(results['qsd']['to'])

        # Add our headers that the user can potentially over-ride if they
        # wish to to our returned result set
        results['headers'] = results['qsd-']
        results['headers'].update(results['qsd+'])

        return results
