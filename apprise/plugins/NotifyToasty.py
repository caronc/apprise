# -*- encoding: utf-8 -*-
#
# (Super) Toasty Notify Wrapper
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

# Toasty uses the http protocol with JSON requests
TOASTY_URL = 'http://api.supertoasty.com/notify/'

# Image Support (128x128)
TOASTY_IMAGE_XY = NotifyImageSize.XY_128

# Used to break apart list of potential devices by their delimiter
# into a usable list.
DEVICES_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class NotifyToasty(NotifyBase):
    """
    A wrapper for Toasty Notifications
    """

    # The default protocol
    PROTOCOL = 'toasty'

    # The default secure protocol
    SECURE_PROTOCOL = 'toasty'

    def __init__(self, devices, **kwargs):
        """
        Initialize Toasty Object
        """
        super(NotifyToasty, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            image_size=TOASTY_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

        if isinstance(devices, basestring):
            self.devices = filter(bool, DEVICES_LIST_DELIM.split(
                devices,
            ))
        elif isinstance(devices, (tuple, list)):
            self.devices = devices
        else:
            raise TypeError('You must specify at least 1 device.')

        if not self.user:
            raise TypeError('You must specify a username.')

    def _notify(self, title, body, notify_type, **kwargs):
        """
        Perform Toasty Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'multipart/form-data',
        }

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the devices list
        devices = list(self.devices)
        while len(devices):
            device = devices.pop(0)

            # prepare JSON Object
            payload = {
                'sender': quote(self.user),
                'title': quote(title),
                'text': quote(body),
            }

            if self.include_image:
                image_url = self.image_url(
                    notify_type,
                )
                if image_url:
                    payload['image'] = image_url

            # URL to transmit content via
            url = '%s%s' % (TOASTY_URL, device)

            self.logger.debug('Toasty POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Toasty Payload: %s' % str(payload))
            try:
                r = requests.get(
                    url,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    try:
                        self.logger.warning(
                            'Failed to send Toasty:%s '
                            'notification: %s (error=%s).' % (
                                device,
                                HTTP_ERROR_MAP[r.status_code],
                                r.status_code))

                    except IndexError:
                        self.logger.warning(
                            'Failed to send Toasty:%s '
                            'notification (error=%s).' % (
                                device,
                                r.status_code))

                    # self.logger.debug('Response Details: %s' % r.raw.read())

                    # Return; we're done
                    has_error = True

            except requests.ConnectionError as e:
                self.logger.warning(
                    'A Connection error occured sending Toasty:%s ' % (
                        device) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                has_error = True

            if len(devices):
                # Prevent thrashing requests
                self.throttle()

        return has_error
