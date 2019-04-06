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
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_list
from ..utils import parse_bool

# Token required as part of the API request
VALIDATE_APIKEY = re.compile(r'[A-Za-z0-9]{32}')

# Extend HTTP Error Messages
JOIN_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}

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

    # Limit results to just the first 2 line otherwise there is just to much
    # content to display
    body_max_line_count = 2

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # The default group to use if none is specified
    default_join_group = 'group.all'

    def __init__(self, apikey, targets, include_image=True, **kwargs):
        """
        Initialize Join Object
        """
        super(NotifyJoin, self).__init__(**kwargs)

        if not VALIDATE_APIKEY.match(apikey.strip()):
            msg = 'The JOIN API Token specified ({}) is invalid.'\
                .format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The token associated with the account
        self.apikey = apikey.strip()

        # Parse devices specified
        self.devices = parse_list(targets)

        if len(self.devices) == 0:
            # Default to everyone
            self.devices.append(self.default_join_group)

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
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
                device = 'group.{}'.format(group_re.group('name').lower())

            elif not IS_DEVICE_RE.match(device):
                self.logger.warning(
                    'Skipping specified invalid device/group "{}"'
                    .format(device)
                )
                # Mark our failure
                has_error = True
                continue

            url_args = {
                'apikey': self.apikey,
                'deviceId': device,
                'title': title,
                'text': body,
            }

            # prepare our image for display if configured to do so
            image_url = None if not self.include_image \
                else self.image_url(notify_type)

            if image_url:
                url_args['icon'] = image_url

            # prepare payload
            payload = {}

            # Prepare the URL
            url = '%s?%s' % (self.notify_url, NotifyJoin.urlencode(url_args))

            self.logger.debug('Join POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Join Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    url,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyJoin.http_response_code_lookup(
                            r.status_code, JOIN_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send Join notification to {}: '
                        '{}{}error={}.'.format(
                            device,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info('Sent Join notification to %s.' % device)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending Join:%s '
                    'notification.' % device
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

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

        return '{schema}://{apikey}/{devices}/?{args}'.format(
            schema=self.secure_protocol,
            apikey=NotifyJoin.quote(self.apikey, safe=''),
            devices='/'.join([NotifyJoin.quote(x, safe='')
                              for x in self.devices]),
            args=NotifyJoin.urlencode(args))

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

        # Our API Key is the hostname if no user is specified
        results['apikey'] = \
            results['user'] if results['user'] else results['host']

        # Unquote our API Key
        results['apikey'] = NotifyJoin.unquote(results['apikey'])

        # Our Devices
        results['targets'] = list()
        if results['user']:
            # If a user was defined, then the hostname is actually a target
            # too
            results['targets'].append(NotifyJoin.unquote(results['host']))

        # Now fetch the remaining tokens
        results['targets'].extend(
            NotifyJoin.split_path(results['fullpath']))

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += NotifyJoin.parse_list(results['qsd']['to'])

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results
