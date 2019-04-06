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
import six
import requests

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType


class NotifyXML(NotifyBase):
    """
    A wrapper for XML Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'XML'

    # The default protocol
    protocol = 'xml'

    # The default secure protocol
    secure_protocol = 'xmls'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_Custom_XML'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for JSON requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    def __init__(self, headers=None, **kwargs):
        """
        Initialize XML Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with

        """
        super(NotifyXML, self).__init__(**kwargs)

        self.payload = """<?xml version='1.0' encoding='utf-8'?>
<soapenv:Envelope
    xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <soapenv:Body>
        <Notification xmlns:xsi="http://nuxref.com/apprise/NotifyXML-1.0.xsd">
            <Version>1.0</Version>
            <Subject>{SUBJECT}</Subject>
            <MessageType>{MESSAGE_TYPE}</MessageType>
            <Message>{MESSAGE}</Message>
       </Notification>
    </soapenv:Body>
</soapenv:Envelope>"""

        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, six.string_types):
            self.fullpath = '/'

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

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

        # Append our headers into our args
        args.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyXML.quote(self.user, safe=''),
                password=NotifyXML.quote(self.password, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifyXML.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyXML.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            args=NotifyXML.urlencode(args),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform XML Notification
        """

        # prepare XML Object
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/xml'
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        re_map = {
            '{MESSAGE_TYPE}': NotifyXML.escape_html(
                notify_type, whitespace=False),
            '{SUBJECT}': NotifyXML.escape_html(title, whitespace=False),
            '{MESSAGE}': NotifyXML.escape_html(body, whitespace=False),
        }

        # Iterate over above list and store content accordingly
        re_table = re.compile(
            r'(' + '|'.join(re_map.keys()) + r')',
            re.IGNORECASE,
        )

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath
        payload = re_table.sub(lambda x: re_map[x.group()], self.payload)

        self.logger.debug('XML POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('XML Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=payload,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyXML.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send XML notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent XML notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending XML '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

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

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set
        results['headers'] = results['qsd-']
        results['headers'].update(results['qsd+'])

        # Tidy our header entries by unquoting them
        results['headers'] = {NotifyXML.unquote(x): NotifyXML.unquote(y)
                              for x, y in results['headers'].items()}

        return results
