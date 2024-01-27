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

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _

# For API Details see:
# https://kb.synology.com/en-au/DSM/help/Chat/chat_integration


class NotifySynology(NotifyBase):
    """
    A wrapper for Synology Chat Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Synology Chat'

    # The services URL
    service_url = 'https://www.synology.com/'

    # The default protocol
    protocol = 'synology'

    # The default secure protocol
    secure_protocol = 'synologys'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_synology_chat'

    # Title is to be part of body
    title_maxlen = 0

    # Disable throttle rate for Synology requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Define object templates
    templates = (
        '{schema}://{host}/{token}',
        '{schema}://{host}:{port}/{token}',
        '{schema}://{user}@{host}/{token}',
        '{schema}://{user}@{host}:{port}/{token}',
        '{schema}://{user}:{password}@{host}/{token}',
        '{schema}://{user}:{password}@{host}:{port}/{token}',
    )

    # Define our tokens; these are the minimum tokens required required to
    # be passed into this function (as arguments). The syntax appends any
    # previously defined in the base package and builds onto them
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
            'name': _('Token'),
            'type': 'string',
            'required': True,
            'private': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'file_url': {
            'name': _('Upload'),
            'type': 'string',
        },
        'token': {
            'alias_of': 'token',
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('HTTP Header'),
            'prefix': '+',
        },
    }

    def __init__(self, token=None, headers=None, file_url=None, **kwargs):
        """
        Initialize Synology Chat Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with

        """
        super().__init__(**kwargs)

        self.token = token
        if not self.token:
            msg = 'An invalid Synology Token ' \
                  '({}) was specified.'.format(token)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.fullpath = kwargs.get('fullpath')

        # A URL to an attachment you want to upload (must be less then 32MB
        # Acording to API details (at the time of writing plugin)
        self.file_url = file_url

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {}

        if self.file_url:
            params['file_url'] = self.file_url

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifySynology.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=NotifySynology.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}/{token}' \
            '{fullpath}?{params}'.format(
                schema=self.secure_protocol if self.secure else self.protocol,
                auth=auth,
                # never encode hostname since we're expecting it to be a valid
                # one
                hostname=self.host,
                port='' if self.port is None or self.port == default_port
                     else ':{}'.format(self.port),
                token=self.pprint(self.token, privacy, safe=''),
                fullpath=NotifySynology.quote(self.fullpath, safe='/')
                if self.fullpath else '/',
                params=NotifySynology.urlencode(params),
            )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Synology Chat Notification
        """

        # Prepare HTTP Headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': '*/*',
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        # prepare Synology Object
        payload = {
            'text': body,
        }

        if self.file_url:
            payload['file_url'] = self.file_url

        # Prepare our parameters
        params = {
            'api': 'SYNO.Chat.External',
            'method': 'incoming',
            'version': 2,
            'token': self.token,
        }

        auth = None
        if self.user:
            auth = (self.user, self.password)

        # Set our schema
        schema = 'https' if self.secure else 'http'

        url = '%s://%s' % (schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        # Prepare our Synology API URL
        url += self.fullpath + '/webapi/entry.cgi'

        self.logger.debug('Synology Chat POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Synology Chat Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=f"payload={dumps(payload)}",
                params=params,
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code < 200 or r.status_code >= 300:
                # We had a problem
                status_str = \
                    NotifySynology.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Synology Chat %s notification: '
                    '%serror=%s.',
                    status_str,
                    ', ' if status_str else '',
                    str(r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Synology Chat notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Synology '
                'Chat notification to %s.' % self.host)
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

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results['headers'] = {
            NotifySynology.unquote(x): NotifySynology.unquote(y)
            for x, y in results['qsd+'].items()}

        # Set our token if found as an argument
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            results['token'] = NotifySynology.unquote(results['qsd']['token'])

        else:
            # Get unquoted entries
            entries = NotifySynology.split_path(results['fullpath'])
            if entries:
                # Pop the first element
                results['token'] = entries.pop(0)

                # Update our fullpath to not include our token
                results['fullpath'] = \
                    results['fullpath'][len(results['token']) + 1:]

        # Set upload/file_url if not otherwise set
        if 'file_url' in results['qsd'] and len(results['qsd']['file_url']):
            results['file_url'] = \
                NotifySynology.unquote(results['qsd']['file_url'])

        return results
