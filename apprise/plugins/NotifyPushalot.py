# -*- encoding: utf-8 -*-
#
# Pushalot Notify Wrapper
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
import re

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import NotifyImageSize
from .NotifyBase import HTTP_ERROR_MAP

# Pushalot uses the http protocol with JSON requests
PUSHALOT_URL = 'https://pushalot.com/api/sendmessage'

# Image Support (72x72)
PUSHALOT_IMAGE_XY = NotifyImageSize.XY_72

# Extend HTTP Error Messages
PUSHALOT_HTTP_ERROR_MAP = dict(HTTP_ERROR_MAP.items() + {
    406: 'Message throttle limit hit.',
    410: 'AuthorizedToken is no longer valid.',
}.items())

# Used to validate Authorization Token
VALIDATE_AUTHTOKEN = re.compile(r'[A-Za-z0-9]{32}')


class NotifyPushalot(NotifyBase):
    """
    A wrapper for Pushalot Notifications
    """

    # The default protocol
    PROTOCOL = 'palot'

    # The default secure protocol
    SECURE_PROTOCOL = 'palot'

    def __init__(self, authtoken, is_important=False, **kwargs):
        """
        Initialize Pushalot Object
        """
        super(NotifyPushalot, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            image_size=PUSHALOT_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

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

    def _notify(self, title, body, notify_type, **kwargs):
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

        if self.include_image:
            image_url = self.image_url(
                notify_type,
            )
            if image_url:
                payload['Image'] = image_url

        self.logger.debug('Pushalot POST URL: %s (cert_verify=%r)' % (
            PUSHALOT_URL, self.verify_certificate,
        ))
        self.logger.debug('Pushalot Payload: %s' % str(payload))
        try:
            r = requests.post(
                PUSHALOT_URL,
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

                except IndexError:
                    self.logger.warning(
                        'Failed to send Pushalot notification '
                        '(error=%s).' % r.status_code)

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Pushalot notification.')

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending Pushalot notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True
