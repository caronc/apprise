# -*- coding: utf-8 -*-
#
# Faast Notify Wrapper
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

import requests

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize

# Image Support (72x72)
FAAST_IMAGE_XY = NotifyImageSize.XY_72


class NotifyFaast(NotifyBase):
    """
    A wrapper for Faast Notifications
    """

    # The default protocol (this is secure for faast)
    protocol = 'faast'

    # Faast uses the http protocol with JSON requests
    notify_url = 'https://www.appnotifications.com/account/notifications.json'

    def __init__(self, authtoken, **kwargs):
        """
        Initialize Faast Object
        """
        super(NotifyFaast, self).__init__(
            title_maxlen=250, body_maxlen=32768, image_size=FAAST_IMAGE_XY,
            **kwargs)

        self.authtoken = authtoken

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Faast Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'multipart/form-data'
        }

        # prepare JSON Object
        payload = {
            'user_credentials': self.authtoken,
            'title': title,
            'message': body,
        }

        if self.include_image:
            image_url = self.image_url(
                notify_type,
            )
            if image_url:
                payload['icon_url'] = image_url

        self.logger.debug('Faast POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Faast Payload: %s' % str(payload))
        try:
            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Faast notification: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except IndexError:
                    self.logger.warning(
                        'Failed to send Faast notification '
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False
            else:
                self.logger.info('Sent Faast notification.')

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending Faast notification.',
            )
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

        # Store our authtoken using the host
        results['authtoken'] = results['host']

        return results
