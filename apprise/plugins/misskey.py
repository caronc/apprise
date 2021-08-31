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

# 1. visit https://misskey-hub.net/ and see what it's all about if you want.
#    Choose a service you want to create an account on from here:
#    https://misskey-hub.net/en/instances.html
#
#    - For this plugin, I tested using https://misskey.sda1.net and created an
#      account.
#
# 2. Generate an API Key:
#    - Settings > API > Generate Key
#      - Name it whatever you want
#      - Assign it 'AT LEAST':
#          a. Compose or delete chat messages
#          b. Compose or delete notes
#
#
# This plugin also supports taking the URL (as identified above) directly
# as well.

import requests
from json import dumps

from .base import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..locale import gettext_lazy as _


class MisskeyVisibility:
    """
    The visibility of any note created
    """
    # post will be public
    PUBLIC = 'public'

    HOME = 'home'

    FOLLOWERS = 'followers'

    PRIVATE = 'private'

    SPECIFIED = 'specified'


# Define the types in a list for validation purposes
MISSKEY_VISIBILITIES = (
    MisskeyVisibility.PUBLIC,
    MisskeyVisibility.HOME,
    MisskeyVisibility.FOLLOWERS,
    MisskeyVisibility.PRIVATE,
    MisskeyVisibility.SPECIFIED,
)


class NotifyMisskey(NotifyBase):
    """
    A wrapper for Misskey Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Misskey'

    # The services URL
    service_url = 'https://misskey-hub.net/'

    # The default protocol
    protocol = 'misskey'

    # The default secure protocol
    secure_protocol = 'misskeys'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_misskey'

    # The title is not used
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 512

    # Define object templates
    templates = (
        '{schema}://{project_id}/{msghook}',
    )

    # Define object templates
    templates = (
        '{schema}://{token}@{host}',
        '{schema}://{token}@{host}:{port}',
    )

    # Define our template arguments
    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'token': {
            'name': _('Access Token'),
            'type': 'string',
            'required': True,
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
        'token': {
            'alias_of': 'token',
        },
        'visibility': {
            'name': _('Visibility'),
            'type': 'choice:string',
            'values': MISSKEY_VISIBILITIES,
            'default': MisskeyVisibility.PUBLIC,
        },
    })

    def __init__(self, token=None, visibility=None, **kwargs):
        """
        Initialize Misskey Object
        """
        super().__init__(**kwargs)

        self.token = validate_regex(token)
        if not self.token:
            msg = 'An invalid Misskey Access Token was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if visibility:
            # Input is a string; attempt to get the lookup from our
            # sound mapping
            vis = 'invalid' if not isinstance(visibility, str) \
                else visibility.lower().strip()

            # This little bit of black magic allows us to match against
            # against multiple versions of the same string ... etc
            self.visibility = \
                next((v for v in MISSKEY_VISIBILITIES
                      if v.startswith(vis)), None)

            if self.visibility not in MISSKEY_VISIBILITIES:
                msg = 'The Misskey visibility specified ({}) is invalid.' \
                    .format(visibility)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.visibility = self.template_args['visibility']['default']

        # Prepare our URL
        self.schema = 'https' if self.secure else 'http'
        self.api_url = '%s://%s' % (self.schema, self.host)

        if isinstance(self.port, int):
            self.api_url += ':%d' % self.port

        return

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.token, self.host, self.port,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        params = {
            'visibility': self.visibility,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        host = self.host
        if isinstance(self.port, int):
            host += ':%d' % self.port

        return '{schema}://{token}@{host}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            host=host,
            token=self.pprint(self.token, privacy, safe=''),
            params=NotifyMisskey.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        wrapper to _send since we can alert more then one channel
        """

        # prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }

        # Prepare our payload
        payload = {
            'i': self.token,
            'text': body,
            'visibility': self.visibility,
        }

        api_url = f'{self.api_url}/api/notes/create'
        self.logger.debug('Misskey GET URL: %s (cert_verify=%r)' % (
            api_url, self.verify_certificate))
        self.logger.debug('Misskey Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                api_url,
                headers=headers,
                data=dumps(payload),
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyMisskey.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Misskey notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Misskey notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Misskey '
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
            results['token'] = NotifyMisskey.unquote(results['qsd']['token'])

        elif not results['password'] and results['user']:
            results['token'] = NotifyMisskey.unquote(results['user'])

        # Capture visibility if specified
        if 'visibility' in results['qsd'] and \
                len(results['qsd']['visibility']):
            results['visibility'] = \
                NotifyMisskey.unquote(results['qsd']['visibility'])

        return results
