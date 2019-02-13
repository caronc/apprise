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

# Some Reference Locations:
# - https://docs.mattermost.com/developer/webhooks-incoming.html
# - https://docs.mattermost.com/administration/config-settings.html

# Used to validate Authorization Token
VALIDATE_AUTHTOKEN = re.compile(r'[A-Za-z0-9]{24,32}')


class NotifyMatterMost(NotifyBase):
    """
    A wrapper for MatterMost Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'MatterMost'

    # The services URL
    service_url = 'https://mattermost.com/'

    # The default protocol
    protocol = 'mmost'

    # The default secure protocol
    secure_protocol = 'mmosts'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_mattermost'

    # The default Mattermost port
    default_port = 8065

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4000

    def __init__(self, authtoken, channel=None, **kwargs):
        """
        Initialize MatterMost Object
        """
        super(NotifyMatterMost, self).__init__(**kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        # Our API Key
        self.authtoken = authtoken

        # Validate authtoken
        if not authtoken:
            self.logger.warning(
                'Missing MatterMost Authorization Token.'
            )
            raise TypeError(
                'Missing MatterMost Authorization Token.'
            )

        if not VALIDATE_AUTHTOKEN.match(authtoken):
            self.logger.warning(
                'Invalid MatterMost Authorization Token Specified.'
            )
            raise TypeError(
                'Invalid MatterMost Authorization Token Specified.'
            )

        # A Channel (optional)
        self.channel = channel

        if not self.port:
            self.port = self.default_port

        return

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform MatterMost Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # prepare JSON Object
        payload = {
            'text': '###### %s\n%s' % (title, body),
            'icon_url': self.image_url(notify_type),
        }

        if self.user:
            payload['username'] = self.user

        else:
            payload['username'] = self.app_id

        if self.channel:
            payload['channel'] = self.channel

        url = '%s://%s:%d' % (self.schema, self.host, self.port)
        url += '/hooks/%s' % self.authtoken

        self.logger.debug('MatterMost POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('MatterMost Payload: %s' % str(payload))
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
                        'Failed to send MatterMost notification:'
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send MatterMost notification '
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False
            else:
                self.logger.info('Sent MatterMost notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending MatterMost '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
        }

        default_port = 443 if self.secure else self.default_port
        default_schema = self.secure_protocol if self.secure else self.protocol

        return '{schema}://{hostname}{port}/{authtoken}/?{args}'.format(
            schema=default_schema,
            hostname=self.host,
            port='' if not self.port or self.port == default_port
                 else ':{}'.format(self.port),
            authtoken=self.quote(self.authtoken, safe=''),
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
        authtoken = NotifyBase.split_path(results['fullpath'])[0]

        channel = None
        if 'channel' in results['qsd'] and len(results['qsd']['channel']):
            # Allow the user to specify the channel to post to
            channel = NotifyBase.unquote(results['qsd']['channel']).strip()

        results['authtoken'] = authtoken
        results['channel'] = channel

        return results
