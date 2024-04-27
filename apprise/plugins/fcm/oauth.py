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
#
# To generate a private key file for your service account:
#
#  1. In the Firebase console, open Settings > Service Accounts.
#  2. Click Generate New Private Key, then confirm by clicking Generate Key.
#  3. Securely store the JSON file containing the key.

import requests
import base64
import json
import calendar
from cryptography.hazmat import backends
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import asymmetric
from cryptography.exceptions import UnsupportedAlgorithm
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from json.decoder import JSONDecodeError
from urllib.parse import urlencode as _urlencode

from ...logger import logger


class GoogleOAuth:
    """
    A OAuth simplified implimentation to Google's Firebase Cloud Messaging

    """
    scopes = [
        'https://www.googleapis.com/auth/firebase.messaging',
    ]

    # 1 hour in seconds (the lifetime of our token)
    access_token_lifetime_sec = timedelta(seconds=3600)

    # The default URI to use if one is not found
    default_token_uri = 'https://oauth2.googleapis.com/token'

    # Taken right from google.auth.helpers:
    clock_skew = timedelta(seconds=10)

    def __init__(self, user_agent=None, timeout=(5, 4),
                 verify_certificate=True):
        """
        Initialize our OAuth object
        """

        # Wether or not to verify ssl
        self.verify_certificate = verify_certificate

        # Our (connect, read) timeout
        self.request_timeout = timeout

        # assign our user-agent if defined
        self.user_agent = user_agent

        # initialize our other object variables
        self.__reset()

    def __reset(self):
        """
        Reset object internal variables
        """

        # Google Keyfile Encoding
        self.encoding = 'utf-8'

        # Our retrieved JSON content (unmangled)
        self.content = None

        # Our generated key information we cache once loaded
        self.private_key = None

        # Our keys we build using the provided content
        self.__refresh_token = None
        self.__access_token = None
        self.__access_token_expiry = datetime.now(timezone.utc)

    def load(self, path):
        """
        Generate our SSL details
        """

        # Reset our objects
        self.content = None
        self.private_key = None
        self.__access_token = None
        self.__access_token_expiry = datetime.now(timezone.utc)

        try:
            with open(path, mode="r", encoding=self.encoding) as fp:
                self.content = json.loads(fp.read())

        except (OSError, IOError):
            logger.debug('FCM keyfile {} could not be accessed'.format(path))
            return False

        except JSONDecodeError as e:
            logger.debug(
                'FCM keyfile {} generated a JSONDecodeError: {}'.format(
                    path, e))
            return False

        if not isinstance(self.content, dict):
            logger.debug(
                'FCM keyfile {} is incorrectly structured'.format(path))
            self.__reset()
            return False

        # Verify we've got the correct tokens in our content to work with
        is_valid = next((False for k in (
            'client_email', 'private_key_id', 'private_key',
            'type', 'project_id') if not self.content.get(k)), True)

        if not is_valid:
            logger.debug(
                'FCM keyfile {} is missing required information'.format(path))
            self.__reset()
            return False

        # Verify our service_account type
        if self.content.get('type') != 'service_account':
            logger.debug(
                'FCM keyfile {} is not of type service_account'.format(path))
            self.__reset()
            return False

        # Prepare our private key which is in PKCS8 PEM format
        try:
            self.private_key = serialization.load_pem_private_key(
                self.content.get('private_key').encode(self.encoding),
                password=None, backend=backends.default_backend())

        except (TypeError, ValueError):
            # ValueError: If the PEM data could not be decrypted or if its
            #             structure could not be decoded successfully.
            # TypeError:  If a password was given and the private key was
            #             not encrypted. Or if the key was encrypted but
            #             no password was supplied.
            logger.error('FCM provided private key is invalid.')
            self.__reset()
            return False

        except UnsupportedAlgorithm:
            # If the serialized key is of a type that is not supported by
            # the backend.
            logger.error('FCM provided private key is not supported')
            self.__reset()
            return False

        # We've done enough validation to move on
        return True

    @property
    def access_token(self):
        """
        Returns our access token (if it hasn't expired yet)
          - if we do not have one we'll fetch one.
          - if it expired, we'll renew it
          - if a key simply can't be acquired, then we return None
        """

        if not self.private_key or not self.content:
            # invalid content (or not loaded)
            logger.error(
                'No FCM JSON keyfile content loaded to generate a access '
                'token with.')
            return None

        if self.__access_token_expiry > datetime.now(timezone.utc):
            # Return our no-expired key
            return self.__access_token

        # If we reach here we need to prepare our payload
        token_uri = self.content.get('token_uri', self.default_token_uri)
        service_email = self.content.get('client_email')
        key_identifier = self.content.get('private_key_id')

        # Generate our Assertion
        now = datetime.now(timezone.utc)
        expiry = now + self.access_token_lifetime_sec

        payload = {
            # The number of seconds since the UNIX epoch.
            "iat": calendar.timegm(now.utctimetuple()),
            "exp": calendar.timegm(expiry.utctimetuple()),
            # The issuer must be the service account email.
            "iss": service_email,
            # The audience must be the auth token endpoint's URI
            "aud": token_uri,
            # Our token scopes
            "scope": " ".join(self.scopes),
        }

        # JWT Details
        header = {
            'typ': 'JWT',
            'alg': 'RS256' if isinstance(
                self.private_key, asymmetric.rsa.RSAPrivateKey) else 'ES256',

            # Key Identifier
            'kid': key_identifier,
        }

        # Encodes base64 strings removing any padding characters.
        segments = [
            base64.urlsafe_b64encode(
                json.dumps(header).encode(self.encoding)).rstrip(b"="),
            base64.urlsafe_b64encode(
                json.dumps(payload).encode(self.encoding)).rstrip(b"="),
        ]

        signing_input = b".".join(segments)
        signature = self.private_key.sign(
            signing_input,
            asymmetric.padding.PKCS1v15(),
            hashes.SHA256(),
        )

        # Finally append our segment
        segments.append(base64.urlsafe_b64encode(signature).rstrip(b"="))
        assertion = b".".join(segments)

        http_payload = _urlencode({
            'assertion': assertion,
            'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        })

        http_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        if self.user_agent:
            http_headers['User-Agent'] = self.user_agent

        logger.info('Refreshing FCM Access Token')
        try:
            r = requests.post(
                token_uri,
                data=http_payload,
                headers=http_headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                logger.warning(
                    'Failed to update FCM Access Token error={}.'
                    .format(r.status_code))

                logger.debug(
                    'Response Details:\r\n%s', r.content)
                return None

        except requests.RequestException as e:
            logger.warning(
                'A Connection error occurred refreshing FCM '
                'Access Token.'
            )
            logger.debug('Socket Exception: %s', str(e))
            return None

        # If we get here, we made our request successfully, now we need
        # to parse out the data
        response = json.loads(r.content)
        self.__access_token = response['access_token']
        self.__refresh_token = response.get(
            'refresh_token', self.__refresh_token)

        if 'expires_in' in response:
            delta = timedelta(seconds=int(response['expires_in']))
            self.__access_token_expiry = \
                delta + datetime.now(timezone.utc) - self.clock_skew

        else:
            # Allow some grace before we expire
            self.__access_token_expiry = expiry - self.clock_skew

        logger.debug(
            'Access Token successfully acquired: %s', self.__access_token)

        # Return our token
        return self.__access_token

    @property
    def project_id(self):
        """
        Returns the project id found in the file
        """
        return None if not self.content \
            else self.content.get('project_id')
