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

# To use this plugin, you must have a Kumulos account set up. Add a client
# and link it with your phone using the phone app (using your Companion App
# option in the profile menu area):
#    Android: https://play.google.com/store/apps/\
#                     details?id=com.kumulos.companion
#    iOS: https://apps.apple.com/us/app/kumulos/id1463947782
#
# The API reference used to build this plugin was documented here:
#  https://docs.kumulos.com/messaging/api/#sending-in-app-messages
#
import requests
from json import dumps

from .base import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..locale import gettext_lazy as _

# Extend HTTP Error Messages
KUMULOS_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid API and/or Server Key.',
    422: 'Unprocessable Entity - The request was unparsable.',
    400: 'Bad Request - Targeted users do not exist or have unsubscribed.',
}


class NotifyKumulos(NotifyBase):
    """
    A wrapper for Kumulos Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Kumulos'

    # The services URL
    service_url = 'https://kumulos.com/'

    # The default secure protocol
    secure_protocol = 'kumulos'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_kumulos'

    # Kumulos uses the http protocol with JSON requests
    notify_url = 'https://messages.kumulos.com/v2/notifications'

    # The maximum allowable characters allowed in the title per message
    title_maxlen = 64

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 240

    # Define object templates
    templates = (
        '{schema}://{apikey}/{serverkey}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
            # UUID4
            'regex': (r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-'
                      r'[89ab][0-9a-f]{3}-[0-9a-f]{12}$', 'i')
        },
        'serverkey': {
            'name': _('Server Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Z0-9+]{36}$', 'i'),
        },
    })

    def __init__(self, apikey, serverkey, **kwargs):
        """
        Initialize Kumulos Object
        """
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Kumulos API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Server Key (associated with project)
        self.serverkey = validate_regex(
            serverkey, *self.template_tokens['serverkey']['regex'])
        if not self.serverkey:
            msg = 'An invalid Kumulos Server Key ' \
                  '({}) was specified.'.format(serverkey)
            self.logger.warning(msg)
            raise TypeError(msg)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Kumulos Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        # prepare JSON Object
        payload = {
            'target': {
                'broadcast': True,
            },
            'content': {
                'title': title,
                'message': body,
            },
        }

        # Determine Authentication
        auth = (self.apikey, self.serverkey)

        self.logger.debug('Kumulos POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Kumulos Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyKumulos.http_response_code_lookup(
                        r.status_code, KUMULOS_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Kumulos notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False

            else:
                self.logger.info('Sent Kumulos notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Kumulos '
                'notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            return False
        return True

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.apikey, self.serverkey)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{apikey}/{serverkey}/?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            serverkey=self.pprint(self.serverkey, privacy, safe=''),
            params=NotifyKumulos.urlencode(params),
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

        # The first token is stored in the hostname
        results['apikey'] = NotifyKumulos.unquote(results['host'])

        # Now fetch the remaining tokens
        try:
            results['serverkey'] = \
                NotifyKumulos.split_path(results['fullpath'])[0]

        except IndexError:
            # no token
            results['serverkey'] = None

        return results
