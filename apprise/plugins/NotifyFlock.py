# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Hitesh Sondhi <hitesh@cropsly.com>
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

# To use this plugin, you need to first access https://dev.flock.com/webhooks
# Specifically https://dev.flock.com/webhooks/incoming
# to create a new incoming webhook for your account. You'll need to
# follow the wizard to pre-determine the channel(s) you want your
# message to broadcast to, and when you're complete, you will
# recieve a URL that looks something like this:
# https://api.flock.com/hooks/sendMessage/134b8gh0-eba0-4fa9-ab9c-257ced0e8221
#                                                             ^
#                                                             |
#  This is important <----------------------------------------^
#
#
import re
import six
import requests
from json import dumps
from time import time

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType

# Token required as part of the API request
# /134b8gh0-eba0-4fa9-ab9c-257ced0e8221
VALIDATE_TOKEN = re.compile(r'[A-Za-z0-9-]{24}')

# Extend HTTP Error Messages
FLOCK_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}

class FlockContentType(object):
    """
    Flock supports to content types
    """
    FLOCKML = 'flockml'
    TEXT = 'text'


# Define the types in a list for validation purposes
FLOCK_CONTENT_TYPES = (
    FlockContentType.FLOCKML,
    FlockContentType.TEXT,
)

class NotifyFlock(NotifyBase):
    """
    A wrapper for Flock Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Flock'

    # The services URL
    service_url = 'https://flock.com/'

    # The default secure protocol
    secure_protocol = 'flock'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_flock'

    # Flock uses the http protocol with JSON requests
    notify_url = 'https://api.flock.com/hooks/sendMessage'

    def __init__(self, token, contenttype=FlockContentType.TEXT, **kwargs):
        """
        Initialize Flock Object
        """
        super(NotifyFlock, self).__init__(**kwargs)

        if not VALIDATE_TOKEN.match(token.strip()):
            self.logger.warning(
                'The API Token specified (%s) is invalid.' % token,
            )
            raise TypeError(
                'The API Token specified (%s) is invalid.' % token,
            )

        # The token associated with the account
        self.token = token.strip()

        # Store our webhook type
        self.contenttype = contenttype

        if self.contenttype not in FLOCK_CONTENT_TYPES:
            self.logger.warning(
                'The content type specified (%s) is invalid.' % contenttype,
            )
            raise TypeError(
                'The content type specified (%s) is invalid.' % contenttype,
            )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Flock Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # error tracking (used for function return)
        has_error = False

        url = '%s/%s' % (
            self.notify_url,
            self.token
        )

        payload = {
            self.contenttype: body
        }

        self.logger.debug('Flock POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Flock Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyBase.http_response_code_lookup(
                        r.status_code, FLOCK_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Flock notification : '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                has_error = True

            else:
                self.logger.info(
                    'Sent Flock notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Flock notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            has_error = True

        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'contenttype': self.contenttype
        }

        return '{schema}://{token}/?{args}'\
            .format(
                schema=self.secure_protocol,
                token=self.quote(self.token, safe=''),
                args=self.urlencode(args),
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

        # Apply our settings now

        # The first token is stored in the hostname
        token = results['host']

        if 'contenttype' in results['qsd'] and len(results['qsd']['contenttype']):
            results['contenttype'] = results['qsd']\
                .get('contenttype', FlockContentType.TEXT).lower()

        results['token'] = token
        
        return results
