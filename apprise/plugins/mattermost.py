# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# Create an incoming webhook; the website will provide you with something like:
#  http://localhost:8065/hooks/yobjmukpaw3r3urc5h6i369yima
#                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
#                              |-- this is the webhook --|
#
# You can effectively turn the url above to read this:
# mmost://localhost:8065/yobjmukpaw3r3urc5h6i369yima
#  - swap http with mmost
#  - drop /hooks/ reference

import requests
from json import dumps

from .base import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool
from ..utils import parse_list
from ..utils import validate_regex
from ..locale import gettext_lazy as _

# Some Reference Locations:
# - https://docs.mattermost.com/developer/webhooks-incoming.html
# - https://docs.mattermost.com/administration/config-settings.html


class NotifyMattermost(NotifyBase):
    """
    A wrapper for Mattermost Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Mattermost'

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
        '{schema}://{host}/{token}',
        '{schema}://{host}:{port}/{token}',
        '{schema}://{host}/{fullpath}/{token}',
        '{schema}://{host}:{port}/{fullpath}/{token}',
        '{schema}://{botname}@{host}/{token}',
        '{schema}://{botname}@{host}:{port}/{token}',
        '{schema}://{botname}@{host}/{fullpath}/{token}',
        '{schema}://{botname}@{host}:{port}/{fullpath}/{token}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'token': {
            'name': _('Webhook Token'),
            'type': 'string',
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
        'channel': {
            'alias_of': 'channels',
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

    def __init__(self, token, fullpath=None, channels=None,
                 include_image=False, **kwargs):
        """
        Initialize Mattermost Object
        """
        super().__init__(**kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        # our full path
        self.fullpath = '' if not isinstance(
            fullpath, str) else fullpath.strip()

        # Authorization Token (associated with project)
        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Mattermost Authorization Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Optional Channels (strip off any channel prefix entries if present)
        self.channels = [x.lstrip('#') for x in parse_list(channels)]

        if not self.port:
            self.port = self.default_port

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Mattermost Notification
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
                self.schema, self.host, self.port,
                self.fullpath.rstrip('/'), self.token)

            self.logger.debug('Mattermost POST URL: %s (cert_verify=%r)' % (
                url, self.verify_certificate,
            ))
            self.logger.debug('Mattermost Payload: %s' % str(payload))

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
                        NotifyMattermost.http_response_code_lookup(
                            r.status_code)

                    self.logger.warning(
                        'Failed to send Mattermost notification{}: '
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
                        'Sent Mattermost notification{}.'.format(
                            '' if not channel
                            else ' to channel {}'.format(channel)))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Mattermost '
                    'notification{}.'.format(
                        '' if not channel
                        else ' to channel {}'.format(channel)))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Flag our error
                has_error = True
                continue

        # Return our overall status
        return not has_error

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.token, self.host, self.port, self.fullpath,
        )

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
            params['channel'] = ','.join(
                [NotifyMattermost.quote(x, safe='') for x in self.channels])

        default_port = 443 if self.secure else self.default_port
        default_schema = self.secure_protocol if self.secure else self.protocol

        # Determine if there is a botname present
        botname = ''
        if self.user:
            botname = '{botname}@'.format(
                botname=NotifyMattermost.quote(self.user, safe=''),
            )

        return \
            '{schema}://{botname}{hostname}{port}{fullpath}{token}' \
            '/?{params}'.format(
                schema=default_schema,
                botname=botname,
                # never encode hostname since we're expecting it to be a valid
                # one
                hostname=self.host,
                port='' if not self.port or self.port == default_port
                     else ':{}'.format(self.port),
                fullpath='/' if not self.fullpath else '{}/'.format(
                    NotifyMattermost.quote(self.fullpath, safe='/')),
                token=self.pprint(self.token, privacy, safe=''),
                params=NotifyMattermost.urlencode(params),
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

        # Acquire our tokens; the last one will always be our token
        # all entries before it will be our path
        tokens = NotifyMattermost.split_path(results['fullpath'])

        results['token'] = None if not tokens else tokens.pop()

        # Store our path
        results['fullpath'] = '' if not tokens \
            else '/{}'.format('/'.join(tokens))

        # Define our optional list of channels to notify
        results['channels'] = list()

        # Support both 'to' (for yaml configuration) and channel=
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            # Allow the user to specify the channel to post to
            results['channels'].extend(
                NotifyMattermost.parse_list(results['qsd']['to']))

        if 'channel' in results['qsd'] and len(results['qsd']['channel']):
            # Allow the user to specify the channel to post to
            results['channels'].extend(
                NotifyMattermost.parse_list(results['qsd']['channel']))

        if 'channels' in results['qsd'] and len(results['qsd']['channels']):
            # Allow the user to specify the channel to post to
            results['channels'].extend(
                NotifyMattermost.parse_list(results['qsd']['channels']))

        # Image manipulation
        results['include_image'] = parse_bool(results['qsd'].get(
            'image', NotifyMattermost.template_args['image']['default']))

        return results
