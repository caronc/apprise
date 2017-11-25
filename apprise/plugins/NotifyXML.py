# -*- encoding: utf-8 -*-
#
# XML Notify Wrapper
#
# Copyright (C) 2014-2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# apprise is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# apprise is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with apprise. If not, see <http://www.gnu.org/licenses/>.

from urllib import quote
import requests
import re

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import NotifyImageSize
from .NotifyBase import HTTP_ERROR_MAP

# Image Support (128x128)
XML_IMAGE_XY = NotifyImageSize.XY_128


class NotifyXML(NotifyBase):
    """
    A wrapper for XML Notifications
    """

    # The default protocol
    PROTOCOL = 'xml'

    # The default secure protocol
    SECURE_PROTOCOL = 'xmls'

    def __init__(self, **kwargs):
        """
        Initialize XML Object
        """
        super(NotifyXML, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            image_size=XML_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

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

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, basestring):
            self.fullpath = '/'

        return

    def _notify(self, title, body, notify_type, **kwargs):
        """
        Perform XML Notification
        """

        # prepare XML Object
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/xml'
        }

        re_map = {
            '{MESSAGE_TYPE}': quote(notify_type),
            '{SUBJECT}': quote(title),
            '{MESSAGE}': quote(body),
        }

        # Iterate over above list and store content accordingly
        re_table = re.compile(
            r'(' + '|'.join(re_map.keys()) + r')',
            re.IGNORECASE,
        )

        auth = None
        if self.user:
            auth = (self.user, self.password)

        url = '%s://%s' % (self.schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath
        payload = re_table.sub(lambda x: re_map[x.group()], self.payload)

        self.logger.debug('XML POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('XML Payload: %s' % str(payload))
        try:
            r = requests.post(
                url,
                data=payload,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                try:
                    self.logger.warning(
                        'Failed to send XML notification: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send XML notification '
                        '(error=%s).' % r.status_code)

                # Return; we're done
                return False

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending XML '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True
