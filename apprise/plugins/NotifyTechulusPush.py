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

import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..AppriseLocale import gettext_lazy as _

# Token required as part of the API request
# Used to prepare our UUID regex matching
UUID4_RE = \
    r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'

# API Key
VALIDATE_APIKEY = re.compile(UUID4_RE, re.I)


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
            'regex': (UUID4_RE, 'i'),
        },
    })

    def __init__(self, apikey, **kwargs):
        """
        Initialize Techulus Push Object
        """
        super(NotifyTechulusPush, self).__init__(**kwargs)

        if not apikey:
            msg = 'The Techulus Push apikey is not specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not VALIDATE_APIKEY.match(apikey.strip()):
            msg = 'The Techulus Push apikey specified ({}) is invalid.'\
                .format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The apikey associated with the account
        self.apikey = apikey.strip()

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
                'A Connection error occured sending Techulus Push '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))

            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://{apikey}/?{args}'.format(
            schema=self.secure_protocol,
            apikey=NotifyTechulusPush.quote(self.apikey, safe=''),
            args=NotifyTechulusPush.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # The first apikey is stored in the hostname
        results['apikey'] = NotifyTechulusPush.unquote(results['host'])

        return results
