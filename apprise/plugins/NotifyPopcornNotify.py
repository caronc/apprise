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

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import is_email
from ..utils import is_phone_no
from ..utils import parse_list
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotifyPopcornNotify(NotifyBase):
    """
    A wrapper for PopcornNotify Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'PopcornNotify'

    # The services URL
    service_url = 'https://popcornnotify.com/'

    # The default protocol
    secure_protocol = 'popcorn'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_popcornnotify'

    # PopcornNotify uses the http protocol
    notify_url = 'https://popcornnotify.com/notify'

    # The maximum targets to include when doing batch transfers
    default_batch_size = 10

    # Define object templates
    templates = (
        '{schema}://{apikey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'regex': (r'^[a-z0-9]+$', 'i'),
            'required': True,
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'target_email': {
            'name': _('Target Email'),
            'type': 'string',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
            'required': True,
        }
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, apikey, targets=None, batch=False, **kwargs):
        """
        Initialize PopcornNotify Object
        """
        super().__init__(**kwargs)

        # Access Token (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid PopcornNotify API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare Batch Mode Flag
        self.batch = batch

        # Parse our targets
        self.targets = list()

        for target in parse_list(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if result:
                # store valid phone number
                self.targets.append(result['full'])
                continue

            result = is_email(target)
            if result:
                # store valid email
                self.targets.append(result['full_email'])
                continue

            self.logger.warning(
                'Dropped invalid target '
                '({}) specified.'.format(target),
            )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform PopcornNotify Notification
        """

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning(
                'There were no PopcornNotify targets to notify.')
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
            'message': body,
            'subject': title,
        }

        auth = (self.apikey, None)

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        for index in range(0, len(self.targets), batch_size):
            # Prepare our recipients
            payload['recipients'] = \
                ','.join(self.targets[index:index + batch_size])

            self.logger.debug('PopcornNotify POST URL: %s (cert_verify=%r)' % (
                self.notify_url, self.verify_certificate,
            ))
            self.logger.debug('PopcornNotify Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    auth=auth,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyPopcornNotify.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send {} PopcornNotify notification{}: '
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
                        'Sent {} PopcornNotify notification{}.'
                        .format(
                            len(self.targets[index:index + batch_size]),
                            ' to {}'.format(self.targets[index])
                            if batch_size == 1 else '(s)',
                        ))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending {} PopcornNotify '
                    'notification(s).'.format(
                        len(self.targets[index:index + batch_size])))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'batch': 'yes' if self.batch else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{apikey}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='/'.join(
                [NotifyPopcornNotify.quote(x, safe='') for x in self.targets]),
            params=NotifyPopcornNotify.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + \
                (1 if targets % batch_size else 0)

        return targets

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
        results['targets'] = \
            NotifyPopcornNotify.split_path(results['fullpath'])

        # The hostname is our authentication key
        results['apikey'] = NotifyPopcornNotify.unquote(results['host'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPopcornNotify.parse_list(results['qsd']['to'])

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get('batch', False))

        return results
