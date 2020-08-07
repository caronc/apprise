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

# To use this plugin, you need to first access https://dev.flock.com/webhooks
# Specifically https://dev.flock.com/webhooks/incoming
#
# To create a new incoming webhook for your account. You'll need to
# follow the wizard to pre-determine the channel(s) you want your
# message to broadcast to. When you've completed this, you will
# recieve a URL that looks something like this:
# https://api.flock.com/hooks/sendMessage/134b8gh0-eba0-4fa9-ab9c-257ced0e8221
#                                                             ^
#                                                             |
#  This is important <----------------------------------------^
#
#  It becomes your 'token' that you will pass into this class
#
import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..common import NotifyFormat
from ..common import NotifyImageSize
from ..utils import parse_list
from ..utils import parse_bool
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


# Extend HTTP Error Messages
FLOCK_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}

# Used to detect a channel/user
IS_CHANNEL_RE = re.compile(r'^(#|g:)(?P<id>[A-Z0-9_]+)$', re.I)
IS_USER_RE = re.compile(r'^(@|u:)?(?P<id>[A-Z0-9_]+)$', re.I)


class NotifyFlock(NotifyBase):
    """
    A wrapper for Flock Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Flock'

    # The services URL
    service_url = 'https://flock.com/'

    # The default secure protocol
    secure_protocol = 'flock'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_flock'

    # Flock uses the http protocol with JSON requests
    notify_url = 'https://api.flock.com/hooks/sendMessage'

    # API Wrapper
    notify_api = 'https://api.flock.co/v1/chat.sendMessage'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # Define object templates
    templates = (
        '{schema}://{token}',
        '{schema}://{user}@{token}',
        '{schema}://{user}@{token}/{targets}',
        '{schema}://{token}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'token': {
            'name': _('Access Key'),
            'type': 'string',
            'regex': (r'^[a-z0-9-]+$', 'i'),
            'private': True,
            'required': True,
        },
        'user': {
            'name': _('Bot Name'),
            'type': 'string',
        },
        'to_user': {
            'name': _('To User ID'),
            'type': 'string',
            'prefix': '@',
            'regex': (r'^[A-Z0-9_]+$', 'i'),
            'map_to': 'targets',
        },
        'to_channel': {
            'name': _('To Channel ID'),
            'type': 'string',
            'prefix': '#',
            'regex': (r'^[A-Z0-9_]+$', 'i'),
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

    def __init__(self, token, targets=None, include_image=True, **kwargs):
        """
        Initialize Flock Object
        """
        super(NotifyFlock, self).__init__(**kwargs)

        # Build ourselves a target list
        self.targets = list()

        self.token = validate_regex(
            token, *self.template_tokens['token']['regex'])
        if not self.token:
            msg = 'An invalid Flock Access Key ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

        # Track any issues
        has_error = False

        # Tidy our targets
        targets = parse_list(targets)

        for target in targets:
            result = IS_USER_RE.match(target)
            if result:
                self.targets.append('u:' + result.group('id'))
                continue

            result = IS_CHANNEL_RE.match(target)
            if result:
                self.targets.append('g:' + result.group('id'))
                continue

            has_error = True
            self.logger.warning(
                'Ignoring invalid target ({}) specified.'.format(target))

        if has_error and not self.targets:
            # We have a bot token and no target(s) to message
            msg = 'No Flock targets to notify.'
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Flock Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # error tracking (used for function return)
        has_error = False

        if self.notify_format == NotifyFormat.HTML:
            body = '<flockml>{}</flockml>'.format(body)

        else:
            title = NotifyFlock.escape_html(title, whitespace=False)
            body = NotifyFlock.escape_html(body, whitespace=False)

            body = '<flockml>{}{}</flockml>'.format(
                '' if not title else '<b>{}</b><br/>'.format(title), body)

        payload = {
            'token': self.token,
            'flockml': body,
            'sendAs': {
                'name': self.app_id if not self.user else self.user,
                # A Profile Image is only configured if we're configured to
                # allow it
                'profileImage': None if not self.include_image
                else self.image_url(notify_type),
            }
        }

        if len(self.targets):
            # Create a copy of our targets
            targets = list(self.targets)

            while len(targets) > 0:
                # Get our first item
                target = targets.pop(0)

                # Copy and update our payload
                _payload = payload.copy()
                _payload['to'] = target

                if not self._post(self.notify_api, headers, _payload):
                    has_error = True

        else:
            # Webhook
            url = '{}/{}'.format(self.notify_url, self.token)
            if not self._post(url, headers, payload):
                has_error = True

        return not has_error

    def _post(self, url, headers, payload):
        """
        A wrapper to the requests object
        """

        # error tracking (used for function return)
        has_error = False

        self.logger.debug('Flock POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate))
        self.logger.debug('Flock Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyFlock.http_response_code_lookup(
                        r.status_code, FLOCK_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Flock notification : '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                has_error = True

            else:
                self.logger.info('Sent Flock notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Flock notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            has_error = True

        return not has_error

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

        return '{schema}://{token}/{targets}?{params}'\
            .format(
                schema=self.secure_protocol,
                token=self.pprint(self.token, privacy, safe=''),
                targets='/'.join(
                    [NotifyFlock.quote(target, safe='')
                     for target in self.targets]),
                params=NotifyFlock.urlencode(params),
            )

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
        results['targets'] = NotifyFlock.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += NotifyFlock.parse_list(results['qsd']['to'])

        # The first token is stored in the hostname
        results['token'] = NotifyFlock.unquote(results['host'])

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://api.flock.com/hooks/sendMessage/TOKEN
        """

        result = re.match(
            r'^https?://api\.flock\.com/hooks/sendMessage/'
            r'(?P<token>[a-z0-9-]{24})/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            return NotifyFlock.parse_url(
                '{schema}://{token}/{params}'.format(
                    schema=NotifyFlock.secure_protocol,
                    token=result.group('token'),
                    params='' if not result.group('params')
                    else result.group('params')))

        return None
