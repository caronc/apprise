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
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# To use this plugin, you must have a Kumulos account set up. Add a client
# and link it with your phone using the phone app (using your Companion App
# option in the profile menu area):
#    Android: https://play.google.com/store/apps/\
#                     details?id=com.kumulos.companion
#    iOS: https://apps.apple.com/us/app/kumulos/id1463947782
#
# The API reference used to build this plugin was documented here:
#  https://docs.kumulos.com/messaging/api/#sending-in-app-messages
#
import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _

#
# API Key is a UUID; below is the regex matching
UUID4_RE = \
    r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'

# Secret Key Regex Mapping
SERVER_KEY_RE = r'[A-Z0-9+]{36}'

# API Key
VALIDATE_APIKEY = re.compile(UUID4_RE, re.I)

VALIDATE_SERVER_KEY = re.compile(SERVER_KEY_RE, re.I)

# Extend HTTP Error Messages
KUMULOS_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid API and/or Server Key.',
    422: 'Unprocessable Entity - The request was unparsable.',
    400: 'Bad Request - Targeted users do not exist or have unsubscribed.',
}

# Used to break path apart into list of channels
TARGET_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')


class NotifyKumulos(NotifyBase):
    """
    A wrapper for Kumulos Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Kumulos'

    # The services URL
    service_url = 'https://kumulos.com/'

    # The default secure protocol
    secure_protocol = 'kumulos'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_kumulos'

    # Kumulos uses the http protocol with JSON requests
    notify_url = 'https://messages.kumulos.com/v2/notifications'

    # The maximum allowable characters allowed in the title per message
    title_maxlen = 64

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 240

    # Define object templates
    templates = (
        '{schema}://{apikey}/{serverkey}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (UUID4_RE, 'i'),
        },
        'serverkey': {
            'name': _('Server Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (SERVER_KEY_RE, 'i'),
        },
    })

    def __init__(self, apikey, serverkey, **kwargs):
        """
        Initialize Kumulos Object
        """
        super(NotifyKumulos, self).__init__(**kwargs)

        if not apikey:
            msg = 'The Kumulos API Key is not specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        self.apikey = apikey.strip()
        if not VALIDATE_APIKEY.match(self.apikey):
            msg = 'The Kumulos API Key specified ({}) is invalid.'\
                .format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        if not serverkey:
            msg = 'The Kumulos Server Key is not specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        self.serverkey = serverkey.strip()
        if not VALIDATE_SERVER_KEY.match(self.serverkey):
            msg = 'The Kumulos Server Key specified ({}) is invalid.'\
                .format(serverkey)
            self.logger.warning(msg)
            raise TypeError(msg)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Kumulos Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # prepare JSON Object
        payload = {
            'target': {
                'broadcast': True,
            },
            'content': {
                'title': title,
                'message': body,
            },
        }

        # Determine Authentication
        auth = (self.apikey, self.serverkey)

        self.logger.debug('Kumulos POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Kumulos Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyKumulos.http_response_code_lookup(
                        r.status_code, KUMULOS_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Kumulos notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False

            else:
                self.logger.info('Sent Kumulos notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Kumulos '
                'notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            return False
        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://{apikey}/{serverkey}/?{args}'.format(
            schema=self.secure_protocol,
            apikey=NotifyKumulos.quote(self.apikey, safe=''),
            serverkey=NotifyKumulos.quote(self.serverkey, safe=''),
            args=NotifyKumulos.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # The first token is stored in the hostname
        results['apikey'] = NotifyKumulos.unquote(results['host'])

        # Now fetch the remaining tokens
        try:
            results['serverkey'] = \
                NotifyKumulos.split_path(results['fullpath'])[0]

        except IndexError:
            # no token
            results['serverkey'] = None

        return results
