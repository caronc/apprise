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
from ..common import NotifyFormat
from ..utils import validate_regex
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _


class NotifyPushMe(NotifyBase):
    """
    A wrapper for PushMe Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'PushMe'

    # The services URL
    service_url = 'https://push.i-i.me/'

    # Insecure protocol (for those self hosted requests)
    protocol = 'pushme'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushme'

    # PushMe URL
    notify_url = 'https://push.i-i.me/'

    # Define object templates
    templates = (
        '{schema}://{token}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'token': {
            'name': _('Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'token': {
            'alias_of': 'token',
        },
        'push_key': {
            'alias_of': 'token',
        },
        'status': {
            'name': _('Show Status'),
            'type': 'bool',
            'default': True,
        },
    })

    def __init__(self, token, status=None, **kwargs):
        """
        Initialize PushMe Object
        """
        super().__init__(**kwargs)

        # Token (associated with project)
        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid PushMe Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Set Status type
        self.status = status

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform PushMe Notification
        """

        headers = {
            'User-Agent': self.app_id,
        }

        # Prepare our payload
        params = {
            'push_key': self.token,
            'title': title if not self.status
            else '{} {}'.format(self.asset.ascii(notify_type), title),
            'content': body,
            'type': 'markdown'
            if self.notify_format == NotifyFormat.MARKDOWN else 'text'
        }

        self.logger.debug('PushMe POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('PushMe Payload: %s' % str(params))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                params=params,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyPushMe.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send PushMe notification:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent PushMe notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending PushMe notification.',
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'status': 'yes' if self.status else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Official URLs are easy to assemble
        return '{schema}://{token}/?{params}'.format(
            schema=self.protocol,
            token=self.pprint(self.token, privacy, safe=''),
            params=NotifyPushMe.urlencode(params),
        )

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

        # Store our token using the host
        results['token'] = NotifyPushMe.unquote(results['host'])

        # The 'token' makes it easier to use yaml configuration
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            results['token'] = NotifyPushMe.unquote(results['qsd']['token'])

        elif 'push_key' in results['qsd'] and len(results['qsd']['push_key']):
            # Support 'push_key' if specified
            results['token'] = NotifyPushMe.unquote(results['qsd']['push_key'])

        # Get status switch
        results['status'] = \
            parse_bool(results['qsd'].get('status', True))

        return results
