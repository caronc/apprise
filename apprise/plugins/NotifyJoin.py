# -*- encoding: utf-8 -*-
#
# Join Notify Wrapper
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

# Join URL: http://joaoapps.com/join/
# To use this plugin, you need to first access (make sure your browser allows
#  popups): https://joinjoaomgcd.appspot.com/
#
# To register you just need to allow it to connect to your Google Profile but
# the good news is it doesn't ask for anything too personal.
#
# You can download the app for your phone here:
#   https://play.google.com/store/apps/details?id=com.joaomgcd.join

import requests
import re

from urllib import urlencode

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import HTTP_ERROR_MAP
from .NotifyBase import NotifyImageSize

# Join uses the http protocol with JSON requests
JOIN_URL = 'https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush'

# Token required as part of the API request
VALIDATE_APIKEY = re.compile(r'[A-Za-z0-9]{32}')

# Default User
JOIN_DEFAULT_USER = 'apprise'

# Extend HTTP Error Messages
JOIN_HTTP_ERROR_MAP = dict(HTTP_ERROR_MAP.items() + {
    401: 'Unauthorized - Invalid Token.',
}.items())

# Used to break path apart into list of devices
DEVICE_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')

# Used to detect a device
IS_DEVICE_RE = re.compile(r'([A-Za-z0-9]{32})')

# Used to detect a device
IS_GROUP_RE = re.compile(
    r'(group\.)?(?P<name>(all|android|chrome|windows10|phone|tablet|pc))',
    re.IGNORECASE,
)

# Image Support (72x72)
JOIN_IMAGE_XY = NotifyImageSize.XY_72


class NotifyJoin(NotifyBase):
    """
    A wrapper for Join Notifications
    """

    # The default protocol
    PROTOCOL = 'join'

    # The default secure protocol
    SECURE_PROTOCOL = 'join'

    def __init__(self, apikey, devices, **kwargs):
        """
        Initialize Join Object
        """
        super(NotifyJoin, self).__init__(
            title_maxlen=250, body_maxlen=1000,
            image_size=JOIN_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

        if not VALIDATE_APIKEY.match(apikey.strip()):
            self.logger.warning(
                'The first API Token specified (%s) is invalid.' % apikey,
            )
            raise TypeError(
                'The first API Token specified (%s) is invalid.' % apikey,
            )

        # The token associated with the account
        self.apikey = apikey.strip()

        if isinstance(devices, basestring):
            self.devices = filter(bool, DEVICE_LIST_DELIM.split(
                devices,
            ))
        elif isinstance(devices, (tuple, list)):
            self.devices = devices
        else:
            self.devices = list()

        if len(self.devices) == 0:
            self.logger.warning('No device(s) were specified.')
            raise TypeError('No device(s) were specified.')

    def _notify(self, title, body, notify_type, **kwargs):
        """
        Perform Join Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the devices list
        devices = list(self.devices)
        while len(devices):
            device = devices.pop(0)
            group_re = IS_GROUP_RE.match(device)
            if group_re:
                device = 'group.%s' % group_re.group('name').lower()

            elif not IS_DEVICE_RE.match(device):
                self.logger.warning(
                    "The specified device '%s' is invalid; skipping." % (
                        device,
                    )
                )
                continue

            url_args = {
                'apikey': self.apikey,
                'deviceId': device,
                'title': title,
                'text': body,
            }

            if self.include_image:
                image_url = self.image_url(
                    notify_type,
                )
                if image_url:
                    url_args['icon'] = image_url

            # prepare payload
            payload = {
            }

            # Prepare the URL
            url = '%s?%s' % (JOIN_URL, urlencode(url_args))

            self.logger.debug('Join POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Join Payload: %s' % str(payload))

            try:
                r = requests.post(
                    url,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    try:
                        self.logger.warning(
                            'Failed to send Join:%s '
                            'notification: %s (error=%s).' % (
                                device,
                                JOIN_HTTP_ERROR_MAP[r.status_code],
                                r.status_code))

                    except IndexError:
                        self.logger.warning(
                            'Failed to send Join:%s '
                            'notification (error=%s).' % (
                                device,
                                r.status_code))

                    # self.logger.debug('Response Details: %s' % r.raw.read())
                    # Return; we're done
                    has_error = True

            except requests.ConnectionError as e:
                self.logger.warning(
                    'A Connection error occured sending Join:%s '
                    'notification.' % device
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                has_error = True

            if len(devices):
                # Prevent thrashing requests
                self.throttle()

        return has_error
