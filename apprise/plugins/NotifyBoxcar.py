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

from json import dumps
import requests
import re
from time import time
import hmac
from hashlib import sha1
from itertools import chain
try:
    from urlparse import urlparse

except ImportError:
    from urllib.parse import urlparse

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP

from ..common import NotifyImageSize
from ..utils import compat_is_basestring

# Default to sending to all devices if nothing is specified
DEFAULT_TAG = '@all'

# The tags value is an structure containing an array of strings defining the
# list of tagged devices that the notification need to be send to, and a
# boolean operator (‘and’ / ‘or’) that defines the criteria to match devices
# against those tags.
IS_TAG = re.compile(r'^[@](?P<name>[A-Z0-9]{1,63})$', re.I)

# Device tokens are only referenced when developing.
# it's not likely you'll send a message directly to a device, but
# if you do; this plugin supports it.
IS_DEVICETOKEN = re.compile(r'^[A-Z0-9]{64}$', re.I)

# Both an access key and seret key are created and assigned to each project
# you create on the boxcar website
VALIDATE_ACCESS = re.compile(r'[A-Z0-9_-]{64}', re.I)
VALIDATE_SECRET = re.compile(r'[A-Z0-9_-]{64}', re.I)

# Used to break apart list of potential tags by their delimiter
# into a usable list.
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

    def __init__(self, access, secret, recipients=None, **kwargs):
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
            self.logger.warning(
                'The specified access key specified is invalid.',
            )
            raise TypeError(
                'The specified access key specified is invalid.',
            )

        try:
            # Secret Key (associated with project)
            self.secret = secret.strip()

        except AttributeError:
            self.logger.warning(
                'The specified secret key specified is invalid.',
            )
            raise TypeError(
                'The specified secret key specified is invalid.',
            )

        if not VALIDATE_ACCESS.match(self.access):
            self.logger.warning(
                'The access key specified (%s) is invalid.' % self.access,
            )
            raise TypeError(
                'The access key specified (%s) is invalid.' % self.access,
            )

        if not VALIDATE_SECRET.match(self.secret):
            self.logger.warning(
                'The secret key specified (%s) is invalid.' % self.secret,
            )
            raise TypeError(
                'The secret key specified (%s) is invalid.' % self.secret,
            )

        if not recipients:
            self.tags.append(DEFAULT_TAG)
            recipients = []

        elif compat_is_basestring(recipients):
            recipients = [x for x in filter(bool, TAGS_LIST_DELIM.split(
                recipients,
            ))]

        # Validate recipients and drop bad ones:
        for recipient in recipients:
            if IS_TAG.match(recipient):
                # store valid tag/alias
                self.tags.append(IS_TAG.match(recipient).group('name'))

            elif IS_DEVICETOKEN.match(recipient):
                # store valid device
                self.device_tokens.append(recipient)

            else:
                self.logger.warning(
                    'Dropped invalid tag/alias/device_token '
                    '(%s) specified.' % recipient,
                )

    def notify(self, title, body, notify_type, **kwargs):
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
        image_url = self.image_url(notify_type)
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

        params = self.urlencode({
            "publishkey": self.access,
            "signature": h.hexdigest(),
        })

        notify_url = '%s?%s' % (self.notify_url, params)
        self.logger.debug('Boxcar POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('Boxcar Payload: %s' % str(payload))

        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )

            # Boxcar returns 201 (Created) when successful
            if r.status_code != requests.codes.created:
                try:
                    self.logger.warning(
                        'Failed to send Boxcar notification: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send Boxcar notification '
                        '(error=%s).' % (
                            r.status_code))

                # self.logger.debug('Response Details: %s' % r.raw.read())

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
            'format': self.notify_format
        }

        return '{schema}://{access}/{secret}/{recipients}/?{args}'.format(
            schema=self.secure_protocol,
            access=self.quote(self.access),
            secret=self.quote(self.secret),
            recipients='/'.join([
                self.quote(x) for x in chain(
                    self.tags, self.device_tokens) if x != DEFAULT_TAG]),
            args=self.urlencode(args),
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
        access = results['host']

        # Now fetch the remaining tokens
        secret = NotifyBase.split_path(results['fullpath'])[0]

        # Our recipients
        recipients = ','.join(
            NotifyBase.split_path(results['fullpath'])[1:])

        if not (access and secret):
            # If we did not recive an access and/or secret code
            # then we're done
            return None

        # Store our required content
        results['recipients'] = recipients if recipients else None
        results['access'] = access
        results['secret'] = secret

        return results
