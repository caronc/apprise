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
from os import urandom
from json import loads
import requests

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

from base64 import urlsafe_b64encode
import hashlib

try:
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher
    from cryptography.hazmat.primitives.ciphers import algorithms
    from cryptography.hazmat.primitives.ciphers import modes
    from cryptography.hazmat.backends import default_backend

    # We're good to go!
    NOTIFY_SIMPLEPUSH_ENABLED = True

except ImportError:
    # cryptography is required in order for this package to work
    NOTIFY_SIMPLEPUSH_ENABLED = False


class NotifySimplePush(NotifyBase):
    """
    A wrapper for SimplePush Notifications
    """

    # Set our global enabled flag
    enabled = NOTIFY_SIMPLEPUSH_ENABLED

    requirements = {
        # Define our required packaging in order to work
        'packages_required': 'cryptography'
    }

    # The default descriptive name associated with the Notification
    service_name = 'SimplePush'

    # The services URL
    service_url = 'https://simplepush.io/'

    # The default secure protocol
    secure_protocol = 'spush'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_simplepush'

    # SimplePush uses the http protocol with SimplePush requests
    notify_url = 'https://api.simplepush.io/send'

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 10000

    # Defines the maximum allowable characters in the title
    title_maxlen = 1024

    # Define object templates
    templates = (
        '{schema}://{apikey}',
        '{schema}://{salt}:{password}@{apikey}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },

        # Used for encrypted logins
        'password': {
            'name': _('Encrypted Password'),
            'type': 'string',
            'private': True,
        },
        'salt': {
            'name': _('Encrypted Salt'),
            'type': 'string',
            'private': True,
            'map_to': 'user',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'event': {
            'name': _('Event'),
            'type': 'string',
        },
    })

    def __init__(self, apikey, event=None, **kwargs):
        """
        Initialize SimplePush Object
        """
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid SimplePush API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        if event:
            # Event Name (associated with project)
            self.event = validate_regex(event)
            if not self.event:
                msg = 'An invalid SimplePush Event Name ' \
                      '({}) was specified.'.format(event)
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            # Default Event Name
            self.event = None

        # Used/cached in _encrypt() function
        self._iv = None
        self._iv_hex = None
        self._key = None

    def _encrypt(self, content):
        """
        Encrypts message for use with SimplePush
        """

        if self._iv is None:
            # initialization vector and cache it
            self._iv = urandom(algorithms.AES.block_size // 8)

            # convert vector into hex string (used in payload)
            self._iv_hex = ''.join(["{:02x}".format(ord(self._iv[idx:idx + 1]))
                                    for idx in range(len(self._iv))]).upper()

            # encrypted key and cache it
            self._key = bytes(bytearray.fromhex(
                hashlib.sha1('{}{}'.format(self.password, self.user)
                             .encode('utf-8')).hexdigest()[0:32]))

        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        content = padder.update(content.encode()) + padder.finalize()

        encryptor = Cipher(
            algorithms.AES(self._key),
            modes.CBC(self._iv),
            default_backend()).encryptor()

        return urlsafe_b64encode(
            encryptor.update(content) + encryptor.finalize())

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform SimplePush Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-type': "application/x-www-form-urlencoded",
        }

        # Prepare our payload
        payload = {
            'key': self.apikey,
        }

        if self.password and self.user:
            body = self._encrypt(body)
            title = self._encrypt(title)
            payload.update({
                'encrypted': 'true',
                'iv': self._iv_hex,
            })

        # prepare SimplePush Object
        payload.update({
            'msg': body,
            'title': title,
        })

        if self.event:
            # Store Event
            payload['event'] = self.event

        self.logger.debug('SimplePush POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('SimplePush Payload: %s' % str(payload))

        # We need to rely on the status string returned in the SimplePush
        # response
        status_str = None
        status = None

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            # Get our SimplePush response (if it's possible)
            try:
                json_response = loads(r.content)
                status_str = json_response.get('message')
                status = json_response.get('status')

            except (TypeError, ValueError, AttributeError):
                # TypeError = r.content is not a String
                # ValueError = r.content is Unparsable
                # AttributeError = r.content is None
                pass

            if r.status_code != requests.codes.ok or status != 'OK':
                # We had a problem
                status_str = status_str if status_str else\
                    NotifyBase.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send SimplePush notification:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent SimplePush notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending SimplePush notification.')
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.event:
            params['event'] = self.event

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{salt}:{password}@'.format(
                salt=self.pprint(
                    self.user, privacy, mode=PrivacyMode.Secret, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )

        return '{schema}://{auth}{apikey}/?{params}'.format(
            schema=self.secure_protocol,
            auth=auth,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            params=NotifySimplePush.urlencode(params),
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

        # Set the API Key
        results['apikey'] = NotifySimplePush.unquote(results['host'])

        # Event
        if 'event' in results['qsd'] and len(results['qsd']['event']):
            # Extract the account sid from an argument
            results['event'] = \
                NotifySimplePush.unquote(results['qsd']['event'])

        return results
