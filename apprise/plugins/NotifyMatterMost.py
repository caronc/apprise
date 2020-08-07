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

import six
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool
from ..utils import parse_list
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Some Reference Locations:
# - https://docs.mattermost.com/developer/webhooks-incoming.html
# - https://docs.mattermost.com/administration/config-settings.html


class NotifyMatterMost(NotifyBase):
    """
    A wrapper for MatterMost Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'MatterMost'

    # The services URL
    service_url = 'https://mattermost.com/'

    # The default protocol
    protocol = 'mmost'

    # The default secure protocol
    secure_protocol = 'mmosts'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_mattermost'

    # The default Mattermost port
    default_port = 8065

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4000

    # Mattermost does not have a title
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{host}/{authtoken}',
        '{schema}://{host}/{authtoken}:{port}',
        '{schema}://{botname}@{host}/{authtoken}',
        '{schema}://{botname}@{host}:{port}/{authtoken}',
        '{schema}://{host}/{fullpath}/{authtoken}',
        '{schema}://{host}/{fullpath}{authtoken}:{port}',
        '{schema}://{botname}@{host}/{fullpath}/{authtoken}',
        '{schema}://{botname}@{host}:{port}/{fullpath}/{authtoken}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'authtoken': {
            'name': _('Access Key'),
            'type': 'string',
            'regex': (r'^[a-z0-9]{24,32}$', 'i'),
            'private': True,
            'required': True,
        },
        'fullpath': {
            'name': _('Path'),
            'type': 'string',
        },
        'botname': {
            'name': _('Bot Name'),
            'type': 'string',
            'map_to': 'user',
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'channels': {
            'name': _('Channels'),
            'type': 'list:string',
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
        'to': {
            'alias_of': 'channels',
        },
    })

    def __init__(self, authtoken, fullpath=None, channels=None,
                 include_image=False, **kwargs):
        """
        Initialize MatterMost Object
        """
        super(NotifyMatterMost, self).__init__(**kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        # our full path
        self.fullpath = '' if not isinstance(
            fullpath, six.string_types) else fullpath.strip()

        # Authorization Token (associated with project)
        self.authtoken = validate_regex(
            authtoken, *self.template_tokens['authtoken']['regex'])
        if not self.authtoken:
            msg = 'An invalid MatterMost Authorization Token ' \
                  '({}) was specified.'.format(authtoken)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Optional Channels
        self.channels = parse_list(channels)

        if not self.port:
            self.port = self.default_port

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform MatterMost Notification
        """

        # Create a copy of our channels, otherwise place a dummy entry
        channels = list(self.channels) if self.channels else [None, ]

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        # prepare JSON Object
        payload = {
            'text': body,
            'icon_url': None,
        }

        # Acquire our image url if configured to do so
        image_url = None if not self.include_image \
            else self.image_url(notify_type)

        if image_url:
            # Set our image configuration if told to do so
            payload['icon_url'] = image_url

        # Set our user
        payload['username'] = self.user if self.user else self.app_id

        # For error tracking
        has_error = False

        while len(channels):
            # Pop a channel off of the list
            channel = channels.pop(0)

            if channel:
                payload['channel'] = channel

            url = '{}://{}:{}{}/hooks/{}'.format(
                self.schema, self.host, self.port, self.fullpath,
                self.authtoken)

            self.logger.debug('MatterMost POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('MatterMost Payload: %s' % str(payload))

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
                        NotifyMatterMost.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send MatterMost notification{}: '
                        '{}{}error={}.'.format(
                            '' if not channel
                            else ' to channel {}'.format(channel),
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Flag our error
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent MatterMost notification{}.'.format(
                            '' if not channel
                            else ' to channel {}'.format(channel)))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending MatterMost '
                    'notification{}.'.format(
                        '' if not channel
                        else ' to channel {}'.format(channel)))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Flag our error
                has_error = True
                continue

        # Return our overall status
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

        if self.channels:
            # historically the value only accepted one channel and is
            # therefore identified as 'channel'. Channels have always been
            # optional, so that is why this setting is nested in an if block
            params['channel'] = ','.join(self.channels)

        default_port = 443 if self.secure else self.default_port
        default_schema = self.secure_protocol if self.secure else self.protocol

        # Determine if there is a botname present
        botname = ''
        if self.user:
            botname = '{botname}@'.format(
                botname=NotifyMatterMost.quote(self.user, safe=''),
            )

        return \
            '{schema}://{botname}{hostname}{port}{fullpath}{authtoken}' \
            '/?{params}'.format(
                schema=default_schema,
                botname=botname,
                # never encode hostname since we're expecting it to be a valid
                # one
                hostname=self.host,
                port='' if not self.port or self.port == default_port
                     else ':{}'.format(self.port),
                fullpath='/' if not self.fullpath else '{}/'.format(
                    NotifyMatterMost.quote(self.fullpath, safe='/')),
                authtoken=self.pprint(self.authtoken, privacy, safe=''),
                params=NotifyMatterMost.urlencode(params),
            )

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

        # Acquire our tokens; the last one will always be our authtoken
        # all entries before it will be our path
        tokens = NotifyMatterMost.split_path(results['fullpath'])

        results['authtoken'] = None if not tokens else tokens.pop()

        # Store our path
        results['fullpath'] = '' if not tokens \
            else '/{}'.format('/'.join(tokens))

        # Define our optional list of channels to notify
        results['channels'] = list()

        # Support both 'to' (for yaml configuration) and channel=
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            # Allow the user to specify the channel to post to
            results['channels'].append(
                NotifyMatterMost.parse_list(results['qsd']['to']))

        if 'channel' in results['qsd'] and len(results['qsd']['channel']):
            # Allow the user to specify the channel to post to
            results['channels'].append(
                NotifyMatterMost.parse_list(results['qsd']['channel']))

        # Image manipulation
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', False))

        return results
