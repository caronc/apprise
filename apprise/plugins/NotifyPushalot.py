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

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize

# Extend HTTP Error Messages
PUSHALOT_HTTP_ERROR_MAP = HTTP_ERROR_MAP.copy()
PUSHALOT_HTTP_ERROR_MAP.update({
    406: 'Message throttle limit hit.',
    410: 'AuthorizedToken is no longer valid.',
})

# Used to validate Authorization Token
VALIDATE_AUTHTOKEN = re.compile(r'[A-Za-z0-9]{32}')


class NotifyPushalot(NotifyBase):
    """
    A wrapper for Pushalot Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushalot'

    # The services URL
    service_url = 'https://pushalot.com/'

    # The default protocol is always secured
    secure_protocol = 'palot'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushalot'

    # Pushalot uses the http protocol with JSON requests
    notify_url = 'https://pushalot.com/api/sendmessage'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    def __init__(self, authtoken, is_important=False, **kwargs):
        """
        Initialize Pushalot Object
        """
        super(NotifyPushalot, self).__init__(**kwargs)

        # Is Important Flag
        self.is_important = is_important

        self.authtoken = authtoken
        # Validate authtoken
        if not VALIDATE_AUTHTOKEN.match(authtoken):
            self.logger.warning(
                'Invalid Pushalot Authorization Token Specified.'
            )
            raise TypeError(
                'Invalid Pushalot Authorization Token Specified.'
            )

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Pushalot Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # prepare JSON Object
        payload = {
            'AuthorizationToken': self.authtoken,
            'IsImportant': self.is_important,
            'Title': title,
            'Body': body,
            'Source': self.app_id,
        }

        image_url = self.image_url(notify_type)
        if image_url:
            payload['Image'] = image_url

        self.logger.debug('Pushalot POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Pushalot Payload: %s' % str(payload))
        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Pushalot notification: '
                        '%s (error=%s).' % (
                            PUSHALOT_HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send Pushalot notification '
                        '(error=%s).' % r.status_code)

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Pushalot notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Pushalot notification.')
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

        # Apply our settings now
        results['authtoken'] = results['host']

        return results
