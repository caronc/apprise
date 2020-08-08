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
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Extend HTTP Error Messages
JOIN_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}

# Used to detect a device
IS_DEVICE_RE = re.compile(r'^[a-z0-9]{32}$', re.I)

# Used to detect a device
IS_GROUP_RE = re.compile(
    r'(group\.)?(?P<name>(all|android|chrome|windows10|phone|tablet|pc))',
    re.IGNORECASE,
)

# Image Support (72x72)
JOIN_IMAGE_XY = NotifyImageSize.XY_72


# Priorities
class JoinPriority(object):
    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


JOIN_PRIORITIES = (
    JoinPriority.LOW,
    JoinPriority.MODERATE,
    JoinPriority.NORMAL,
    JoinPriority.HIGH,
    JoinPriority.EMERGENCY,
)


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

    # The default group to use if none is specified
    default_join_group = 'group.all'

    # Define object templates
    templates = (
        '{schema}://{apikey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'regex': (r'^[a-z0-9]{32}$', 'i'),
            'private': True,
            'required': True,
        },
        'device': {
            'name': _('Device ID'),
            'type': 'string',
            'regex': (r'^[a-z0-9]{32}$', 'i'),
            'map_to': 'targets',
        },
        'device_name': {
            'name': _('Device Name'),
            'type': 'string',
            'map_to': 'targets',
        },
        'group': {
            'name': _('Group'),
            'type': 'choice:string',
            'values': (
                'all', 'android', 'chrome', 'windows10', 'phone', 'tablet',
                'pc'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
            'required': True,
        },
    })

    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
        'priority': {
            'name': _('Priority'),
            'type': 'choice:int',
            'values': JOIN_PRIORITIES,
            'default': JoinPriority.NORMAL,
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, apikey, targets=None, include_image=True, priority=None,
                 **kwargs):
        """
        Initialize Join Object
        """
        super(NotifyJoin, self).__init__(**kwargs)

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Join API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Priority of the message
        if priority not in JOIN_PRIORITIES:
            self.priority = self.template_args['priority']['default']

        else:
            self.priority = priority

        # Prepare a list of targets to store entries into
        self.targets = list()

        # Prepare a parsed list of targets
        targets = parse_list(targets)
        if len(targets) == 0:
            # Default to everyone if our list was empty
            self.targets.append(self.default_join_group)
            return

        # If we reach here we have some targets to parse
        while len(targets):
            # Parse our targets
            target = targets.pop(0)
            group_re = IS_GROUP_RE.match(target)
            if group_re:
                self.targets.append(
                    'group.{}'.format(group_re.group('name').lower()))
                continue

            self.targets.append(target)

        return

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

        # Capture a list of our targets to notify
        targets = list(self.targets)

        while len(targets):
            # Pop the first element off of our list
            target = targets.pop(0)

            url_args = {
                'apikey': self.apikey,
                'priority': str(self.priority),
                'title': title,
                'text': body,
            }

            if IS_GROUP_RE.match(target) or IS_DEVICE_RE.match(target):
                url_args['deviceId'] = target

            else:
                # Support Device Names
                url_args['deviceNames'] = target

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
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyJoin.http_response_code_lookup(
                            r.status_code, JOIN_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send Join notification to {}: '
                        '{}{}error={}.'.format(
                            target,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info('Sent Join notification to %s.' % target)

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Join:%s '
                    'notification.' % target
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """
        _map = {
            JoinPriority.LOW: 'low',
            JoinPriority.MODERATE: 'moderate',
            JoinPriority.NORMAL: 'normal',
            JoinPriority.HIGH: 'high',
            JoinPriority.EMERGENCY: 'emergency',
        }

        # Define any URL parameters
        params = {
            'priority':
                _map[self.template_args['priority']['default']]
                if self.priority not in _map else _map[self.priority],
            'image': 'yes' if self.include_image else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{apikey}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='/'.join([NotifyJoin.quote(x, safe='')
                              for x in self.targets]),
            params=NotifyJoin.urlencode(params))

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our API Key is the hostname if no user is specified
        results['apikey'] = \
            results['user'] if results['user'] else results['host']

        # Unquote our API Key
        results['apikey'] = NotifyJoin.unquote(results['apikey'])

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            _map = {
                'l': JoinPriority.LOW,
                'm': JoinPriority.MODERATE,
                'n': JoinPriority.NORMAL,
                'h': JoinPriority.HIGH,
                'e': JoinPriority.EMERGENCY,
            }
            try:
                results['priority'] = \
                    _map[results['qsd']['priority'][0].lower()]

            except KeyError:
                # No priority was set
                pass

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
