# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

# To use this service you will need a Spontit account from their website
# at https://spontit.com/
#
# After you have an account created:
#   - Visit your profile at https://spontit.com/profile and take note of your
#     {username}.  It might look something like: user12345678901
#   - Next generate an API key at https://spontit.com/secret_keys. This will
#     generate a very long alpha-numeric string we'll refer to as the
#     {apikey}

# The Spontit Syntax is as follows:
# spontit://{username}@{apikey}

import re
import requests
from json import loads

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Syntax suggests you use a hashtag '#' to help distinguish we're dealing
# with a channel.
# Secondly we extract the user information only if it's
# specified.  If not, we use the user of the person sending the notification
# Finally the channel identifier is detected
CHANNEL_REGEX = re.compile(
    r'^\s*(\#|\%23)?((\@|\%40)?(?P<user>[a-z0-9_]+)([/\\]|\%2F))?'
    r'(?P<channel>[a-z0-9_-]+)\s*$', re.I)


class NotifySpontit(NotifyBase):
    """
    A wrapper for Spontit Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Spontit'

    # The services URL
    service_url = 'https://spontit.com/'

    # All notification requests are secure
    secure_protocol = 'spontit'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_spontit'

    # Spontit single notification URL
    notify_url = 'https://api.spontit.com/v3/push'

    # The maximum length of the body
    body_maxlen = 5000

    # The maximum length of the title
    title_maxlen = 100

    # If we don't have the specified min length, then we don't bother using
    # the body directive
    spontit_body_minlen = 100

    # Subtitle support; this is the maximum allowed characters defined by
    # the API page
    spontit_subtitle_maxlen = 20

    # Define object templates
    templates = (
        '{schema}://{user}@{apikey}',
        '{schema}://{user}@{apikey}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('User ID'),
            'type': 'string',
            'required': True,
            'regex': (r'^[a-z0-9_-]+$', 'i'),
        },
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9]+$', 'i'),
        },
        # Target Channel ID's
        # If a slash is used; you must escape it
        # If no slash is used; channel is presumed to be your own
        'target_channel': {
            'name': _('Target Channel ID'),
            'type': 'string',
            'prefix': '#',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'subtitle': {
            # Subtitle is available for MacOS users
            'name': _('Subtitle'),
            'type': 'string',
        },
    })

    def __init__(self, apikey, targets=None, subtitle=None, **kwargs):
        """
        Initialize Spontit Object
        """
        super().__init__(**kwargs)

        # User ID (associated with project)
        user = validate_regex(
            self.user, *self.template_tokens['user']['regex'])
        if not user:
            msg = 'An invalid Spontit User ID ' \
                  '({}) was specified.'.format(self.user)
            self.logger.warning(msg)
            raise TypeError(msg)
        # use cleaned up version
        self.user = user

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Spontit API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Save our subtitle information
        self.subtitle = subtitle

        # Parse our targets
        self.targets = list()

        for target in parse_list(targets):
            # Validate targets and drop bad ones:
            result = CHANNEL_REGEX.match(target)
            if result:
                # Just extract the channel
                self.targets.append(
                    '{}'.format(result.group('channel')))
                continue

            self.logger.warning(
                'Dropped invalid channel/user ({}) specified.'.format(target))

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Sends Message
        """

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'X-Authorization': self.apikey,
            'X-UserId': self.user,
        }

        # use the list directly
        targets = list(self.targets)

        if not len(targets):
            # The user did not specify a channel and therefore wants to notify
            # the main account only.  We just set a substitute marker of
            # None so that our while loop below can still process one iteration
            targets = [None, ]

        while len(targets):
            # Get our target(s) to notify
            target = targets.pop(0)

            # Prepare our payload
            payload = {
                'message': body,
            }

            # Use our body directive if we exceed the minimum message
            # limitation
            if len(body) > self.spontit_body_minlen:
                payload['message'] = '{}...'.format(
                    body[:self.spontit_body_minlen - 3])
                payload['body'] = body

            if self.subtitle:
                # Set title if specified
                payload['subtitle'] = \
                    self.subtitle[:self.spontit_subtitle_maxlen]

            elif self.app_desc:
                # fall back to app description
                payload['subtitle'] = \
                    self.app_desc[:self.spontit_subtitle_maxlen]

            elif self.app_id:
                # fall back to app id
                payload['subtitle'] = \
                    self.app_id[:self.spontit_subtitle_maxlen]

            if title:
                # Set title if specified
                payload['pushTitle'] = title

            if target is not None:
                payload['channelName'] = target

            # Some Debug Logging
            self.logger.debug(
                'Spontit POST URL: {} (cert_verify={})'.format(
                    self.notify_url, self.verify_certificate))
            self.logger.debug('Spontit Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    params=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in (
                        requests.codes.created, requests.codes.ok):
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code)

                    try:
                        # Update our status response if we can
                        json_response = loads(r.content)
                        status_str = json_response.get('message', status_str)

                    except (AttributeError, TypeError, ValueError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None

                        # We could not parse JSON response.
                        # We will just use the status we already have.
                        pass

                    self.logger.warning(
                        'Failed to send Spontit notification to {}: '
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

                # If we reach here; the message was sent
                self.logger.info(
                    'Sent Spontit notification to {}.'.format(target))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Spontit:%s ' % (
                        ', '.join(self.targets)) + 'notification.'
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

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.subtitle:
            params['subtitle'] = self.subtitle

        return '{schema}://{userid}@{apikey}/{targets}?{params}'.format(
            schema=self.secure_protocol,
            userid=self.user,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='/'.join(
                [NotifySpontit.quote(x, safe='') for x in self.targets]),
            params=NotifySpontit.urlencode(params))

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifySpontit.split_path(results['fullpath'])

        # The hostname is our authentication key
        results['apikey'] = NotifySpontit.unquote(results['host'])

        # Support MacOS subtitle option
        if 'subtitle' in results['qsd'] and len(results['qsd']['subtitle']):
            results['subtitle'] = \
                NotifySpontit.unquote(results['qsd']['subtitle'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifySpontit.parse_list(results['qsd']['to'])

        return results
