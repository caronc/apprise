# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <xuzheliang135@qq.com>
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
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import re
import requests

from ..common import NotifyType
from .NotifyBase import NotifyBase
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


# Register at https://sct.ftqq.com/
#   - do as the page describe and you will get the token

# Syntax:
#  schan://{access_token}/


class NotifyServerChan(NotifyBase):
    """
    A wrapper for ServerChan Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'ServerChan'

    # The services URL
    service_url = 'https://sct.ftqq.com/'

    # All notification requests are secure
    secure_protocol = 'schan'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_serverchan'

    # ServerChan API
    notify_url = 'https://sctapi.ftqq.com/{token}.send'

    # Define object templates
    templates = (
        '{schema}://{token}/',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'token': {
            'name': _('Token'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
        },
    })

    def __init__(self, token, **kwargs):
        """
        Initialize ServerChan Object
        """
        super(NotifyServerChan, self).__init__(**kwargs)

        # Token (associated with project)
        self.token = validate_regex(
            token, *self.template_tokens['token']['regex'])
        if not self.token:
            msg = 'An invalid ServerChan API Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform ServerChan Notification
        """
        payload = {
            'title': title,
            'desp': body,
        }

        # Our Notification URL
        notify_url = self.notify_url.format(token=self.token)

        # Some Debug Logging
        self.logger.debug('ServerChan URL: {} (cert_verify={})'.format(
            notify_url, self.verify_certificate))
        self.logger.debug('ServerChan Payload: {}'.format(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                data=payload,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyServerChan.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send ServerChan notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return False

            else:
                self.logger.info('Sent ServerChan notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending ServerChan '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    def url(self, privacy=False):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        return '{schema}://{token}'.format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=''))

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

        pattern = 'schan://([a-zA-Z0-9]+)/' + \
                  ('?' if not url.endswith('/') else '')
        result = re.match(pattern, url)
        results['token'] = result.group(1) if result else ''
        return results
