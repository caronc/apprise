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

# To use this plugin, you need to download the app
# - Apple: https://itunes.apple.com/us/app/\
#              push-by-techulus/id1444391917?ls=1&mt=8
# - Android: https://play.google.com/store/apps/\
#              details?id=com.techulus.push
#
# You have to sign up through the account via your mobile device.
#
# Once you've got your account, you can get your API key from here:
#   https://push.techulus.com/login.html
#
# You can also just get the {apikey} right out of the phone app that is
# installed.
#
# your {apikey} will look something like:
#   b444a40f-3db9-4224-b489-9a514c41c009
#
# You will need to assemble all of your URLs for this plugin to work as:
#   push://{apikey}
#
# Resources
# - https://push.techulus.com/ - Main Website
# - https://pushtechulus.docs.apiary.io - API Documentation

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Token required as part of the API request
# Used to prepare our UUID regex matching
UUID4_RE = \
    r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'


class NotifyTechulusPush(NotifyBase):
    """
    A wrapper for Techulus Push Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Techulus Push'

    # The services URL
    service_url = 'https://push.techulus.com'

    # The default secure protocol
    secure_protocol = 'push'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_techulus'

    # Techulus Push uses the http protocol with JSON requests
    notify_url = 'https://push.techulus.com/api/v1/notify'

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Define object templates
    templates = (
        '{schema}://{apikey}',
    )

    # Define our template apikeys
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^{}$'.format(UUID4_RE), 'i'),
        },
    })

    def __init__(self, apikey, **kwargs):
        """
        Initialize Techulus Push Object
        """
        super().__init__(**kwargs)

        # The apikey associated with the account
        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Techulus Push API key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Techulus Push Notification
        """

        # Setup our headers
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'x-api-key': self.apikey,
        }

        payload = {
            'title': title,
            'body': body,
        }

        self.logger.debug('Techulus Push POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('Techulus Push Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                self.notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):
                # We had a problem
                status_str = \
                    NotifyTechulusPush.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send Techulus Push notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                return False

            else:
                self.logger.info(
                    'Sent Techulus Push notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending Techulus Push '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return '{schema}://{apikey}/?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            params=NotifyTechulusPush.urlencode(params),
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

        # The first apikey is stored in the hostname
        results['apikey'] = NotifyTechulusPush.unquote(results['host'])

        return results
