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

import requests

from ..common import NotifyType
from .base import NotifyBase
from ..utils.parse import validate_regex
from ..locale import gettext_lazy as _

# Syntax:
#  schan://{key}/


class NotifyPushDeer(NotifyBase):
    """
    A wrapper for PushDeer Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'PushDeer'

    # The services URL
    service_url = 'https://www.pushdeer.com/'

    # Insecure Protocol Access
    protocol = 'pushdeer'

    # Secure Protocol
    secure_protocol = 'pushdeers'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_PushDeer'

    # Default hostname
    default_hostname = 'api2.pushdeer.com'

    # PushDeer API
    notify_url = '{schema}://{host}:{port}/message/push?pushkey={pushKey}'

    # Define object templates
    templates = (
        '{schema}://{pushkey}',
        '{schema}://{host}/{pushkey}',
        '{schema}://{host}:{port}/{pushkey}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
        'pushkey': {
            'name': _('Pushkey'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
        },
    })

    def __init__(self, pushkey, **kwargs):
        """
        Initialize PushDeer Object
        """
        super().__init__(**kwargs)

        # PushKey (associated with project)
        self.push_key = validate_regex(
            pushkey, *self.template_tokens['pushkey']['regex'])
        if not self.push_key:
            msg = 'An invalid PushDeer API Pushkey ' \
                  '({}) was specified.'.format(pushkey)
            self.logger.warning(msg)
            raise TypeError(msg)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform PushDeer Notification
        """

        # Prepare our persistent_notification.create payload
        payload = {
            'text': title if title else body,
            'type': 'text',
            'desp': body if title else '',
        }

        # Set our schema
        schema = 'https' if self.secure else 'http'

        # Set host
        host = self.default_hostname
        if self.host:
            host = self.host

        # Set port
        port = 443 if self.secure else 80
        if self.port:
            port = self.port

        # Our Notification URL
        notify_url = self.notify_url.format(
            schema=schema, host=host, port=port, pushKey=self.push_key)

        # Some Debug Logging
        self.logger.debug('PushDeer URL: {} (cert_verify={})'.format(
            notify_url, self.verify_certificate))
        self.logger.debug('PushDeer Payload: {}'.format(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                data=payload,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyPushDeer.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send PushDeer notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return False

            else:
                self.logger.info('Sent PushDeer notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending PushDeer '
                'notification.'
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
            self.push_key, self.host, self.port,
        )

    def url(self, privacy=False):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        if self.host:
            url = '{schema}://{host}{port}/{pushkey}'
        else:
            url = '{schema}://{pushkey}'

        return url.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            host=self.host,
            port='' if not self.port else ':{}'.format(self.port),
            pushkey=self.pprint(self.push_key, privacy, safe=''))

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.
        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't parse the URL
            return results

        fullpaths = NotifyPushDeer.split_path(results['fullpath'])

        if len(fullpaths) == 0:
            results['pushkey'] = results['host']
            results['host'] = None
        else:
            results['pushkey'] = fullpaths.pop()

        return results
