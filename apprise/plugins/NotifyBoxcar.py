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
from ..URLBase import PrivacyMode
from ..utils import parse_bool
from ..utils import validate_regex
from ..common import NotifyType
from ..common import NotifyImageSize
from ..AppriseLocale import gettext_lazy as _

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

    # Define object templates
    templates = (
        '{schema}://{access_key}/{secret_key}/',
        '{schema}://{access_key}/{secret_key}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'access_key': {
            'name': _('Access Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Z0-9_-]{64}$', 'i'),
            'map_to': 'access',
        },
        'secret_key': {
            'name': _('Secret Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Z0-9_-]{64}$', 'i'),
            'map_to': 'secret',
        },
        'target_tag': {
            'name': _('Target Tag ID'),
            'type': 'string',
            'prefix': '@',
            'regex': (r'^[A-Z0-9]{1,63}$', 'i'),
            'map_to': 'targets',
        },
        'target_device': {
            'name': _('Target Device ID'),
            'type': 'string',
            'regex': (r'^[A-Z0-9]{64}$', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

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

        # Access Key (associated with project)
        self.access = validate_regex(
            access, *self.template_tokens['access_key']['regex'])
        if not self.access:
            msg = 'An invalid Boxcar Access Key ' \
                  '({}) was specified.'.format(access)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Secret Key (associated with project)
        self.secret = validate_regex(
            secret, *self.template_tokens['secret_key']['regex'])
        if not self.secret:
            msg = 'An invalid Boxcar Secret Key ' \
                  '({}) was specified.'.format(secret)
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
                timeout=self.request_timeout,
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
                'A Connection error occurred sending Boxcar '
                'notification to %s.' % (host))

            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{access}/{secret}/{targets}?{params}'.format(
            schema=self.secure_protocol,
            access=self.pprint(self.access, privacy, safe=''),
            secret=self.pprint(
                self.secret, privacy, mode=PrivacyMode.Secret, safe=''),
            targets='/'.join([
                NotifyBoxcar.quote(x, safe='') for x in chain(
                    self.tags, self.device_tokens) if x != DEFAULT_TAG]),
            params=NotifyBoxcar.urlencode(params),
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

        # Now fetch the remaining tokens
        results['secret'] = entries.pop(0) if entries else None

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
