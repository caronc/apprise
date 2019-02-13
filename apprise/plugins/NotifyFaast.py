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
# OUT OF OR IN CON

import requests

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize


class NotifyFaast(NotifyBase):
    """
    A wrapper for Faast Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Faast'

    # The services URL
    service_url = 'http://www.faast.io/'

    # The default protocol (this is secure for faast)
    protocol = 'faast'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_faast'

    # Faast uses the http protocol with JSON requests
    notify_url = 'https://www.appnotifications.com/account/notifications.json'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    def __init__(self, authtoken, **kwargs):
        """
        Initialize Faast Object
        """
        super(NotifyFaast, self).__init__(**kwargs)

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

        image_url = self.image_url(notify_type)
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

                except KeyError:
                    self.logger.warning(
                        'Failed to send Faast notification '
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Faast notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Faast notification.',
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

        return '{schema}://{authtoken}/?{args}'.format(
            schema=self.protocol,
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

        # Store our authtoken using the host
        results['authtoken'] = results['host']

        return results
