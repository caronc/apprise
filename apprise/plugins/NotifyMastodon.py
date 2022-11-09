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

import requests
from json import dumps
from itertools import chain

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _


class NotifyMastodon(NotifyBase):
    """
    A wrapper for Notify Mastodon Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Mastodon'

    # The services URL
    service_url = 'https://joinmastodon.org'

    # The default protocol
    protocol = 'mastodon'

    # The default secure protocol
    secure_protocol = 'mastodons'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_mastodon'

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # The title is not used
    title_maxlen = 0

    # The maximum size of the message
    body_maxlen = 500

    # Default to markdown
    notify_format = NotifyFormat.MARKDOWN

    # Define object templates
    templates = (
        '{schema}://{token}@{host}',
        '{schema}://{token}@{host}:{port}',
        '{schema}://{token}@{host}/{targets}',
        '{schema}://{token}@{host}:{port}/{targets}',
    )

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
        'user': {
            'name': _('Username'),
            'type': 'string',
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
        'token': {
            'name': _('Access Token'),
            'type': 'string',
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'token': {
            'alias_of': 'token',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, token=None, targets=None, **kwargs):
        """
        Initialize Notify Mastodon Object
        """
        super().__init__(**kwargs)

        # Set our schema
        self.schema = 'https' if self.secure else 'http'

        # Prepare our URL
        self.api_url = '%s://%s' % (self.schema, self.host)

        if isinstance(self.port, int):
            self.api_url += ':%d' % self.port

        # Initialize channels list
        self.channels = list()

        # Initialize room list
        self.rooms = list()

        # Assign our access token
        self.token = token

        # Our target users
        self.targets = parse_list(targets)
        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {}

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        default_port = 443 if self.secure else 80

        return '{schema}://{token}@{host}{port}/{targets}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            token=self.pprint(
                self.token, privacy, mode=PrivacyMode.Secret, safe=''),
            # never encode hostname since we're expecting it to be a valid one
            host=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='/'.join(
                [NotifyMastodon.quote(x, safe='') for x in chain(
                    # Users
                    ['@{}'.format(x) for x in self.targets],
                )]),
            params=NotifyMastodon.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        wrapper to _send since we can alert more then one channel
        """
        # Apply minimum headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}',
        }

        payload = {
            'status': body,
        }

        # Prepare our message
        api_url = '{}/{}'.format(self.api_url, 'api/v1/statuses')

        self.logger.debug('Mastodon POST URL: %s (cert_verify=%r)' % (
            api_url, self.verify_certificate))
        self.logger.debug('Mastodon Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                api_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyMastodon.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send Mastodon notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info(
                    'Sent Mastodon notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Mastodon '
                'notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        if 'token' in results['qsd'] and len(results['qsd']['token']):
            results['token'] = NotifyMastodon.unquote(results['qsd']['token'])

        elif not results['password'] and results['user']:
            results['token'] = NotifyMastodon.unquote(results['user'])

        # Apply our targets
        results['targets'] = NotifyMastodon.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyMastodon.parse_list(results['qsd']['to'])

        return results
