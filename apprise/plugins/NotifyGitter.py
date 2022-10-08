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

# Once you visit: https://developer.gitter.im/apps you'll get a personal
# access token that will look something like this:
#    b5647881d563fm846dfbb2c27d1fe8f669b8f026

# Don't worry about generating an app; this token is all you need to form
# you're URL with. The syntax is as follows:
#  gitter://{token}/{channel}

# Hence a URL might look like the following:
#    gitter://b5647881d563fm846dfbb2c27d1fe8f669b8f026/apprise

# Note: You must have joined the channel to send a message to it!

# Official API reference: https://developer.gitter.im/docs/user-resource

import re
import requests
from json import loads
from json import dumps
from datetime import datetime

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# API Gitter URL
GITTER_API_URL = 'https://api.gitter.im/v1'

# Used to break path apart into list of targets
TARGET_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')


class NotifyGitter(NotifyBase):
    """
    A wrapper for Gitter Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Gitter'

    # The services URL
    service_url = 'https://gitter.im/'

    # All notification requests are secure
    secure_protocol = 'gitter'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_gitter'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_32

    # Gitter does not support a title
    title_maxlen = 0

    # Gitter is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # X-RateLimit-Reset: The epoc time (in seconds) we can expect our
    #                    rate-limit to be reset.
    # X-RateLimit-Remaining: an integer identifying how many requests we're
    #                        still allow to make.
    request_rate_per_sec = 0

    # For Tracking Purposes
    ratelimit_reset = datetime.utcnow()

    # Default to 1
    ratelimit_remaining = 1

    # Default Notification Format
    notify_format = NotifyFormat.MARKDOWN

    # Define object templates
    templates = (
        '{schema}://{token}/{targets}/',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'token': {
            'name': _('Token'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[a-z0-9]{40}$', 'i'),
        },
        'targets': {
            'name': _('Rooms'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, token, targets, include_image=False, **kwargs):
        """
        Initialize Gitter Object
        """
        super().__init__(**kwargs)

        # Secret Key (associated with project)
        self.token = validate_regex(
            token, *self.template_tokens['token']['regex'])
        if not self.token:
            msg = 'An invalid Gitter API Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse our targets
        self.targets = parse_list(targets)
        if not self.targets:
            msg = 'There are no valid Gitter targets to notify.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Used to track maping of rooms to their numeric id lookup for
        # messaging
        self._room_mapping = None

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Gitter Notification
        """

        # error tracking (used for function return)
        has_error = False

        # Set up our image for display if configured to do so
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if image_url:
            body = '![alt]({})\n{}'.format(image_url, body)

        if self._room_mapping is None:
            # Populate our room mapping
            self._room_mapping = {}
            postokay, response = self._fetch(url='rooms')
            if not postokay:
                return False

            # Response generally looks like this:
            # [
            #   {
            #     noindex: False,
            #     oneToOne: False,
            #     avatarUrl: 'https://path/to/avatar/url',
            #     url: '/apprise-notifications/community',
            #     public: True,
            #     tags: [],
            #     lurk: False,
            #     uri: 'apprise-notifications/community',
            #     lastAccessTime: '2019-03-25T00:12:28.144Z',
            #     topic: '',
            #     roomMember: True,
            #     groupId: '5c981cecd73408ce4fbbad2f',
            #     githubType: 'REPO_CHANNEL',
            #     unreadItems: 0,
            #     mentions: 0,
            #     security: 'PUBLIC',
            #     userCount: 1,
            #     id: '5c981cecd73408ce4fbbad31',
            #     name: 'apprise/community'
            #   }
            # ]
            for entry in response:
                self._room_mapping[entry['name'].lower().split('/')[0]] = {
                    # The ID of the room
                    'id': entry['id'],

                    # A descriptive name (useful for logging)
                    'uri': entry['uri'],
                }

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0).lower()

            if target not in self._room_mapping:
                self.logger.warning(
                    'Failed to locate Gitter room {}'.format(target))

                # Flag our error
                has_error = True
                continue

            # prepare our payload
            payload = {
                'text': body,
            }

            # Our Notification URL
            notify_url = 'rooms/{}/chatMessages'.format(
                self._room_mapping[target]['id'])

            # Perform our query
            postokay, response = self._fetch(
                notify_url, payload=dumps(payload), method='POST')

            if not postokay:
                # Flag our error
                has_error = True

        return not has_error

    def _fetch(self, url, payload=None, method='GET'):
        """
        Wrapper to request object

        """

        # Prepare our headers:
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
            'Authorization': 'Bearer ' + self.token,
        }
        if payload:
            # Only set our header payload if it's defined
            headers['Content-Type'] = 'application/json'

        # Default content response object
        content = {}

        # Update our URL
        url = '{}/{}'.format(GITTER_API_URL, url)

        # Some Debug Logging
        self.logger.debug('Gitter {} URL: {} (cert_verify={})'.format(
            method,
            url, self.verify_certificate))
        if payload:
            self.logger.debug('Gitter Payload: {}' .format(payload))

        # By default set wait to None
        wait = None

        if self.ratelimit_remaining <= 0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Gitter server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.utcnow()
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                # We add 0.5 seconds to the end just to allow a grace
                # period.
                wait = (self.ratelimit_reset - now).total_seconds() + 0.5

        # Always call throttle before any remote server i/o is made
        self.throttle(wait=wait)

        # fetch function
        fn = requests.post if method == 'POST' else requests.get
        try:
            r = fn(
                url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyGitter.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Gitter {} to {}: '
                    '{}error={}.'.format(
                        method,
                        url,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            try:
                self.ratelimit_remaining = \
                    int(r.headers.get('X-RateLimit-Remaining'))
                self.ratelimit_reset = datetime.utcfromtimestamp(
                    int(r.headers.get('X-RateLimit-Reset')))

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this information
                # gracefully accept this state and move on
                pass

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending Gitter {} to {}: '.
                format(method, url))
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return (False, content)

        return (True, content)

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

        return '{schema}://{token}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=''),
            targets='/'.join(
                [NotifyGitter.quote(x, safe='') for x in self.targets]),
            params=NotifyGitter.urlencode(params))

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

        results['token'] = NotifyGitter.unquote(results['host'])

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifyGitter.split_path(results['fullpath'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += NotifyGitter.parse_list(results['qsd']['to'])

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', False))

        return results
