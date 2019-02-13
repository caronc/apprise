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

import re
import requests
from json import dumps
from time import time

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP

# Token required as part of the API request
VALIDATE_TOKEN = re.compile(r'[A-Za-z0-9]{64}')

# Default User
MATRIX_DEFAULT_USER = 'apprise'

# Extend HTTP Error Messages
MATRIX_HTTP_ERROR_MAP = HTTP_ERROR_MAP.copy()
MATRIX_HTTP_ERROR_MAP.update({
    403: 'Unauthorized - Invalid Token.',
})


class MatrixNotificationMode(object):
    SLACK = "slack"
    MATRIX = "matrix"


MATRIX_NOTIFICATION_MODES = (
    MatrixNotificationMode.SLACK,
    MatrixNotificationMode.MATRIX,
)


class NotifyMatrix(NotifyBase):
    """
    A wrapper for Matrix Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Matrix'

    # The services URL
    service_url = 'https://matrix.org/'

    # The default protocol
    protocol = 'matrix'

    # The default secure protocol
    secure_protocol = 'matrixs'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_matrix'

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    def __init__(self, token, mode=MatrixNotificationMode.MATRIX, **kwargs):
        """
        Initialize Matrix Object
        """
        super(NotifyMatrix, self).__init__(**kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        if not isinstance(self.port, int):
            self.notify_url = '%s://%s/api/v1/matrix/hook' % (
                self.schema, self.host)

        else:
            self.notify_url = '%s://%s:%d/api/v1/matrix/hook' % (
                self.schema, self.host, self.port)

        if not VALIDATE_TOKEN.match(token.strip()):
            self.logger.warning(
                'The API token specified (%s) is invalid.' % token,
            )
            raise TypeError(
                'The API token specified (%s) is invalid.' % token,
            )

        # The token associated with the webhook
        self.token = token.strip()

        if not self.user:
            self.logger.warning(
                'No user was specified; using %s.' % MATRIX_DEFAULT_USER)

        if mode not in MATRIX_NOTIFICATION_MODES:
            self.logger.warning('The mode specified (%s) is invalid.' % mode)
            raise TypeError('The mode specified (%s) is invalid.' % mode)

        self.mode = mode

        self._re_formatting_map = {
            # New lines must become the string version
            r'\r\*\n': '\\n',
            # Escape other special characters
            r'&': '&amp;',
            r'<': '&lt;',
            r'>': '&gt;',
        }

        # Iterate over above list and store content accordingly
        self._re_formatting_rules = re.compile(
            r'(' + '|'.join(self._re_formatting_map.keys()) + r')',
            re.IGNORECASE,
        )

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Matrix Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # error tracking (used for function return)
        notify_okay = True

        # Perform Formatting
        title = self._re_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_formatting_map[x.group()], title,
        )
        body = self._re_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_formatting_map[x.group()], body,
        )
        url = '%s/%s' % (
            self.notify_url,
            self.token,
        )

        if self.mode == MatrixNotificationMode.MATRIX:
            payload = self.__matrix_mode_payload(title, body, notify_type)

        else:
            payload = self.__slack_mode_payload(title, body, notify_type)

        self.logger.debug('Matrix POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Matrix Payload: %s' % str(payload))
        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Matrix '
                        'notification: %s (error=%s).' % (
                            MATRIX_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send Matrix '
                        'notification (error=%s).' % r.status_code)

                # Return; we're done
                notify_okay = False

            else:
                self.logger.info('Sent Matrix notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Matrix notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            notify_okay = False

        return notify_okay

    def __slack_mode_payload(self, title, body, notify_type):
        # prepare JSON Object
        payload = {
            'username': self.user if self.user else MATRIX_DEFAULT_USER,
            # Use Markdown language
            'mrkdwn': True,
            'attachments': [{
                'title': title,
                'text': body,
                'color': self.color(notify_type),
                'ts': time(),
                'footer': self.app_id,
            }],
        }

        return payload

    def __matrix_mode_payload(self, title, body, notify_type):
        title = NotifyBase.escape_html(title)
        body = NotifyBase.escape_html(body)

        msg = '<h4>%s</h4>%s<br/>' % (title, body)

        payload = {
            'displayName': self.user if self.user else MATRIX_DEFAULT_USER,
            'format': 'html',
            'text': msg,
        }

        return payload

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'mode': self.mode,
        }

        # Determine Authentication
        auth = ''
        if self.user:
            auth = '{user}@'.format(
                user=self.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{host}/{token}{port}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            host=self.host,
            auth=auth,
            token=self.token,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
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
        results['token'] = NotifyBase.unquote(results['query'])

        if 'mode' in results['qsd'] and len(results['qsd']['mode']):
            results['mode'] = results['qsd']\
                .get('mode', MatrixNotificationMode.MATRIX).lower()

        return results
