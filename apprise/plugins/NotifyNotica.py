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

# 1. Simply visit https://notica.us
# 2. You'll be provided a new variation of the website which will look
#    something like: https://notica.us/?abc123.
#                                         ^
#                                         |
#                                       token
#
#    Your token is actually abc123 (do not include/grab the question mark)
#    You can use that URL as is directly in Apprise, or you can follow
#    the next step which shows you how to assemble the Apprise URL:
#
# 3. With respect to the above, your apprise URL would be:
#       notica://abc123
#
import re
import requests

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotifyNotica(NotifyBase):
    """
    A wrapper for Notica Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Notica'

    # The services URL
    service_url = 'https://notica.us/'

    # The default protocol (this is secure for notica)
    secure_protocol = 'notica'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_notica'

    # Notica URL
    notify_url = 'https://notica.us/?{token}'

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
            'regex': r'^\?*(?P<token>[^/]+)\s*$'
        },
    })

    def __init__(self, token, **kwargs):
        """
        Initialize Notica Object
        """
        super(NotifyNotica, self).__init__(**kwargs)

        # Token (associated with project)
        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Notica Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Notica Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # Prepare our payload
        payload = 'd:{}'.format(body)

        # prepare our notify url
        notify_url = self.notify_url.format(token=self.token)

        self.logger.debug('Notica POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('Notica Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url.format(token=self.token),
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyNotica.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Notica notification:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Notica notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Notica notification.',
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

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

        return '{schema}://{token}/?{args}'.format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=''),
            args=NotifyNotica.urlencode(args),
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

        # Store our token using the host
        results['token'] = NotifyNotica.unquote(results['host'])

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://notica.us/?abc123
        """

        result = re.match(
            r'^https?://notica\.us/?'
            r'\??(?P<token>[^/&=]+)$', url, re.I)

        if result:
            return NotifyNotica.parse_url(
                '{schema}://{token}'.format(
                    schema=NotifyNotica.secure_protocol,
                    token=result.group('token')))

        return None
