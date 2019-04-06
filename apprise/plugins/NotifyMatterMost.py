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
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool
from ..utils import parse_list

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

    # Mattermost does not have a title
    title_maxlen = 0

    def __init__(self, authtoken, channels=None, include_image=True,
                 **kwargs):
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
            msg = 'Missing MatterMost Authorization Token.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_AUTHTOKEN.match(authtoken):
            msg = 'Invalid MatterMost Authorization Token Specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Optional Channels
        self.channels = parse_list(channels)

        if not self.port:
            self.port = self.default_port

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform MatterMost Notification
        """

        # Create a copy of our channels, otherwise place a dummy entry
        channels = list(self.channels) if self.channels else [None, ]

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # prepare JSON Object
        payload = {
            'text': body,
            'icon_url': None,
        }

        # Acquire our image url if configured to do so
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if image_url:
            # Set our image configuration if told to do so
            payload['icon_url'] = image_url

        # Set our user
        payload['username'] = self.user if self.user else self.app_id

        # For error tracking
        has_error = False

        while len(channels):
            # Pop a channel off of the list
            channel = channels.pop(0)

            if channel:
                payload['channel'] = channel

            url = '%s://%s:%d' % (self.schema, self.host, self.port)
            url += '/hooks/%s' % self.authtoken

            self.logger.debug('MatterMost POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('MatterMost Payload: %s' % str(payload))

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
                        NotifyMatterMost.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send MatterMost notification{}: '
                        '{}{}error={}.'.format(
                            '' if not channel
                            else ' to channel {}'.format(channel),
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Flag our error
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent MatterMost notification{}.'.format(
                            '' if not channel
                            else ' to channel {}'.format(channel)))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending MatterMost '
                    'notification{}.'.format(
                        '' if not channel
                        else ' to channel {}'.format(channel)))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Flag our error
                has_error = True
                continue

        # Return our overall status
        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'image': 'yes' if self.include_image else 'no',
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        if self.channels:
            # historically the value only accepted one channel and is
            # therefore identified as 'channel'. Channels have always been
            # optional, so that is why this setting is nested in an if block
            args['channel'] = ','.join(self.channels)

        default_port = 443 if self.secure else self.default_port
        default_schema = self.secure_protocol if self.secure else self.protocol

        return '{schema}://{hostname}{port}/{authtoken}/?{args}'.format(
            schema=default_schema,
            hostname=NotifyMatterMost.quote(self.host, safe=''),
            port='' if not self.port or self.port == default_port
                 else ':{}'.format(self.port),
            authtoken=NotifyMatterMost.quote(self.authtoken, safe=''),
            args=NotifyMatterMost.urlencode(args),
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

        try:
            # Apply our settings now
            results['authtoken'] = \
                NotifyMatterMost.split_path(results['fullpath'])[0]

        except IndexError:
            # There was no Authorization Token specified
            results['authtoken'] = None

        # Define our optional list of channels to notify
        results['channels'] = list()

        # Support both 'to' (for yaml configuration) and channel=
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            # Allow the user to specify the channel to post to
            results['channels'].append(
                NotifyMatterMost.parse_list(results['qsd']['to']))

        if 'channel' in results['qsd'] and len(results['qsd']['channel']):
            # Allow the user to specify the channel to post to
            results['channels'].append(
                NotifyMatterMost.parse_list(results['qsd']['channel']))

        # Image manipulation
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', False))

        return results
