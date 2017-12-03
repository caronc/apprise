# -*- coding: utf-8 -*-
#
# Pushalot Notify Wrapper
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize

# Image Support (72x72)
PUSHALOT_IMAGE_XY = NotifyImageSize.XY_72

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

    # The default protocol
    protocol = 'palot'

    # The default secure protocol
    secure_protocol = 'palot'

    # Pushalot uses the http protocol with JSON requests
    notify_url = 'https://pushalot.com/api/sendmessage'

    def __init__(self, authtoken, is_important=False, **kwargs):
        """
        Initialize Pushalot Object
        """
        super(NotifyPushalot, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            image_size=PUSHALOT_IMAGE_XY, **kwargs)

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

        if self.include_image:
            image_url = self.image_url(
                notify_type,
            )
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
