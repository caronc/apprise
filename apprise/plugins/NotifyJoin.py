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

# Join URL: http://joaoapps.com/join/
# To use this plugin, you need to first access (make sure your browser allows
#  popups): https://joinjoaomgcd.appspot.com/
#
# To register you just need to allow it to connect to your Google Profile but
# the good news is it doesn't ask for anything too personal.
#
# You can download the app for your phone here:
#   https://play.google.com/store/apps/details?id=com.joaomgcd.join

import re
import requests

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize
from ..utils import compat_is_basestring

# Token required as part of the API request
VALIDATE_APIKEY = re.compile(r'[A-Za-z0-9]{32}')

# Extend HTTP Error Messages
JOIN_HTTP_ERROR_MAP = HTTP_ERROR_MAP.copy()
JOIN_HTTP_ERROR_MAP.update({
    401: 'Unauthorized - Invalid Token.',
})

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

    # The default descriptive name associated with the Notification
    service_name = 'Join'

    # The services URL
    service_url = 'https://joaoapps.com/join/'

    # The default protocol
    secure_protocol = 'join'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_join'

    # Join uses the http protocol with JSON requests
    notify_url = \
        'https://joinjoaomgcd.appspot.com/_ah/api/messaging/v1/sendPush'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    def __init__(self, apikey, devices, **kwargs):
        """
        Initialize Join Object
        """
        super(NotifyJoin, self).__init__(**kwargs)

        if not VALIDATE_APIKEY.match(apikey.strip()):
            self.logger.warning(
                'The first API Token specified (%s) is invalid.' % apikey,
            )

            raise TypeError(
                'The first API Token specified (%s) is invalid.' % apikey,
            )

        # The token associated with the account
        self.apikey = apikey.strip()

        if compat_is_basestring(devices):
            self.devices = [x for x in filter(bool, DEVICE_LIST_DELIM.split(
                devices,
            ))]

        elif isinstance(devices, (set, tuple, list)):
            self.devices = devices

        else:
            self.devices = list()

        if len(self.devices) == 0:
            # Default to everyone
            self.devices.append('group.all')

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Join Notification
        """

        try:
            # Limit results to just the first 2 line otherwise
            # there is just to much content to display
            body = re.split('[\r\n]+', body)
            body[0] = body[0].strip('#').strip()
            body = '\r\n'.join(body[0:2])

        except (AttributeError, TypeError):
            # body was None or not of a type string
            body = ''

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        # error tracking (used for function return)
        return_status = True

        # Create a copy of the devices list
        devices = list(self.devices)
        while len(devices):
            device = devices.pop(0)
            group_re = IS_GROUP_RE.match(device)
            if group_re:
                device = 'group.%s' % group_re.group('name').lower()

            elif not IS_DEVICE_RE.match(device):
                self.logger.warning(
                    "The specified device/group '%s' is invalid; skipping." % (
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

            image_url = self.image_url(notify_type)
            if image_url:
                url_args['icon'] = image_url

            # prepare payload
            payload = {}

            # Prepare the URL
            url = '%s?%s' % (self.notify_url, NotifyBase.urlencode(url_args))

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

                    except KeyError:
                        self.logger.warning(
                            'Failed to send Join:%s '
                            'notification (error=%s).' % (
                                device,
                                r.status_code))

                    # self.logger.debug('Response Details: %s' % r.raw.read())

                    return_status = False

                else:
                    self.logger.info('Sent Join notification to %s.' % device)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending Join:%s '
                    'notification.' % device
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                return_status = False

            if len(devices):
                # Prevent thrashing requests
                self.throttle()

        return return_status

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
        }

        return '{schema}://{apikey}/{devices}/?{args}'.format(
            schema=self.secure_protocol,
            apikey=self.quote(self.apikey, safe=''),
            devices='/'.join([self.quote(x) for x in self.devices]),
            args=self.urlencode(args))

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
        devices = ' '.join(
            filter(bool, NotifyBase.split_path(results['fullpath'])))

        results['apikey'] = results['host']
        results['devices'] = devices

        return results
