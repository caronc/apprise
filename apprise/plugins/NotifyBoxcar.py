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
import six
import requests
import hmac
from json import dumps
from time import time
from hashlib import sha1
from itertools import chain
try:
    from urlparse import urlparse

except ImportError:
    from urllib.parse import urlparse

from .NotifyBase import NotifyBase
from ..utils import parse_bool
from ..common import NotifyType
from ..common import NotifyImageSize

# Default to sending to all devices if nothing is specified
DEFAULT_TAG = '@all'

# The tags value is an structure containing an array of strings defining the
# list of tagged devices that the notification need to be send to, and a
# boolean operator (‘and’ / ‘or’) that defines the criteria to match devices
# against those tags.
IS_TAG = re.compile(r'^[@](?P<name>[A-Z0-9]{1,63})$', re.I)

# Device tokens are only referenced when developing.
# It's not likely you'll send a message directly to a device, but if you do;
# this plugin supports it.
IS_DEVICETOKEN = re.compile(r'^[A-Z0-9]{64}$', re.I)

# Both an access key and seret key are created and assigned to each project
# you create on the boxcar website
VALIDATE_ACCESS = re.compile(r'[A-Z0-9_-]{64}', re.I)
VALIDATE_SECRET = re.compile(r'[A-Z0-9_-]{64}', re.I)

# Used to break apart list of potential tags by their delimiter into a useable
# list.
TAGS_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class NotifyBoxcar(NotifyBase):
    """
    A wrapper for Boxcar Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Boxcar'

    # The services URL
    service_url = 'https://boxcar.io/'

    # All boxcar notifications are secure
    secure_protocol = 'boxcar'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_boxcar'

    # Boxcar URL
    notify_url = 'https://boxcar-api.io/api/push/'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 10000

    def __init__(self, access, secret, targets=None, include_image=True,
                 **kwargs):
        """
        Initialize Boxcar Object
        """
        super(NotifyBoxcar, self).__init__(**kwargs)

        # Initialize tag list
        self.tags = list()

        # Initialize device_token list
        self.device_tokens = list()

        try:
            # Access Key (associated with project)
            self.access = access.strip()

        except AttributeError:
            msg = 'The specified access key is invalid.'
            self.logger.warning(msg)
            raise TypeError(msg)

        try:
            # Secret Key (associated with project)
            self.secret = secret.strip()

        except AttributeError:
            msg = 'The specified secret key is invalid.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_ACCESS.match(self.access):
            msg = 'The access key specified ({}) is invalid.'\
                .format(self.access)
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_SECRET.match(self.secret):
            msg = 'The secret key specified ({}) is invalid.'\
                .format(self.secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        if not targets:
            self.tags.append(DEFAULT_TAG)
            targets = []

        elif isinstance(targets, six.string_types):
            targets = [x for x in filter(bool, TAGS_LIST_DELIM.split(
                targets,
            ))]

        # Validate targets and drop bad ones:
        for target in targets:
            if IS_TAG.match(target):
                # store valid tag/alias
                self.tags.append(IS_TAG.match(target).group('name'))

            elif IS_DEVICETOKEN.match(target):
                # store valid device
                self.device_tokens.append(target)

            else:
                self.logger.warning(
                    'Dropped invalid tag/alias/device_token '
                    '({}) specified.'.format(target),
                )

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Boxcar Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # prepare Boxcar Object
        payload = {
            'aps': {
                'badge': 'auto',
                'alert': '',
            },
            'expires': str(int(time() + 30)),
        }

        if title:
            payload['aps']['@title'] = title

        if body:
            payload['aps']['alert'] = body

        if self.tags:
            payload['tags'] = {'or': self.tags}

        if self.device_tokens:
            payload['device_tokens'] = self.device_tokens

        # Source picture should be <= 450 DP wide, ~2:1 aspect.
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if image_url:
            # Set our image
            payload['@img'] = image_url

        # Acquire our hostname
        host = urlparse(self.notify_url).hostname

        # Calculate signature.
        str_to_sign = "%s\n%s\n%s\n%s" % (
            "POST", host, "/api/push", dumps(payload))

        h = hmac.new(
            bytearray(self.secret, 'utf-8'),
            bytearray(str_to_sign, 'utf-8'),
            sha1,
        )

        params = NotifyBoxcar.urlencode({
            "publishkey": self.access,
            "signature": h.hexdigest(),
        })

        notify_url = '%s?%s' % (self.notify_url, params)
        self.logger.debug('Boxcar POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('Boxcar Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )

            # Boxcar returns 201 (Created) when successful
            if r.status_code != requests.codes.created:
                # We had a problem
                status_str = \
                    NotifyBoxcar.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Boxcar notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Boxcar notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Boxcar '
                'notification to %s.' % (host))

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
            'overflow': self.overflow_mode,
            'image': 'yes' if self.include_image else 'no',
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://{access}/{secret}/{targets}/?{args}'.format(
            schema=self.secure_protocol,
            access=NotifyBoxcar.quote(self.access, safe=''),
            secret=NotifyBoxcar.quote(self.secret, safe=''),
            targets='/'.join([
                NotifyBoxcar.quote(x, safe='') for x in chain(
                    self.tags, self.device_tokens) if x != DEFAULT_TAG]),
            args=NotifyBoxcar.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns it broken apart into a dictionary.

        """
        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early
            return None

        # The first token is stored in the hostname
        results['access'] = NotifyBoxcar.unquote(results['host'])

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        entries = NotifyBoxcar.split_path(results['fullpath'])

        try:
            # Now fetch the remaining tokens
            results['secret'] = entries.pop(0)

        except IndexError:
            # secret wasn't specified
            results['secret'] = None

        # Our recipients make up the remaining entries of our array
        results['targets'] = entries

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyBoxcar.parse_list(results['qsd'].get('to'))

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results
