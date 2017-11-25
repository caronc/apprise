# -*- encoding: utf-8 -*-
#
# MatterMost Notify Wrapper
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

from json import dumps
import requests

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import NotifyImageSize
from .NotifyBase import HTTP_ERROR_MAP
from .NotifyBase import NOTIFY_APPLICATION_ID
import re

# Some Reference Locations:
# - https://docs.mattermost.com/developer/webhooks-incoming.html
# - https://docs.mattermost.com/administration/config-settings.html

# Used to validate Authorization Token
VALIDATE_AUTHTOKEN = re.compile(r'[A-Za-z0-9]{24,32}')

# Image Support (72x72)
MATTERMOST_IMAGE_XY = NotifyImageSize.XY_72

# MATTERMOST uses the http protocol with JSON requests
MATTERMOST_PORT = 8065


class NotifyMatterMost(NotifyBase):
    """
    A wrapper for MatterMost Notifications
    """

    # The default protocol
    PROTOCOL = 'mmost'

    # The default secure protocol
    SECURE_PROTOCOL = 'mmosts'

    def __init__(self, authtoken, channel=None, **kwargs):
        """
        Initialize MatterMost Object
        """
        super(NotifyMatterMost, self).__init__(
            title_maxlen=250, body_maxlen=4000,
            image_size=MATTERMOST_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

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
            self.port = MATTERMOST_PORT

        return

    def _notify(self, title, body, notify_type, **kwargs):
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
            payload['username'] = NOTIFY_APPLICATION_ID

        if self.channel:
            payload['channel'] = self.channel

        url = '%s://%s' % (self.schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

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

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending MatterMost '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True
