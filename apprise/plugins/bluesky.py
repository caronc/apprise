# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

# 1. Create a BlueSky account
# 2. Access Settings -> Privacy and Security
# 3. Generate an App Password.  Optionally grant yourself access to Direct
#    Messages if you want to be able to send them
# 4. Assemble your Apprise URL like:
#       bluesky://you-token-here
#
import re
import requests
import json
from datetime import (datetime, timezone, timedelta)
from apprise.exception import AppriseException
from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils.parse import parse_list
from ..locale import gettext_lazy as _

# For parsing handles
HANDLE_HOST_PARSE_RE = re.compile(r'(?P<handle>[^.]+)\.+(?P<host>.+)')

IS_USER = re.compile(r'^\s*@?(?P<user>[A-Z0-9_]+)(\.+(?P<host>.+))?$', re.I)


class BlueSkyDMUnsupported(AppriseException):
    """
    Thrown when an disk i/o error occurs
    """
    def __init__(self, message, error_code=-1):
        super().__init__(message, error_code=error_code)


class NotifyBlueSky(NotifyBase):
    """
    A wrapper for BlueSky Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'BlueSky'

    # The services URL
    service_url = 'https://bluesky.us/'

    # Protocol
    secure_protocol = ('bsky', 'bluesky')

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_bluesky'

    # XRPC Suffix URLs; Structured as:
    #  https://host/{suffix}

    # Taken right from google.auth.helpers:
    clock_skew = timedelta(seconds=10)

    # 1 hour in seconds (the lifetime of our token)
    access_token_lifetime_sec = timedelta(seconds=3600)

    # Detect your Decentralized Identitifer (DID), then you can get your Auth
    # Token.
    xrpc_suffix_did = "/xrpc/com.atproto.identity.resolveHandle"
    xrpc_suffix_session = "/xrpc/com.atproto.server.createSession"
    xrpc_suffix_record = "/xrpc/com.atproto.repo.createRecord"

    # Bluesky
    xrpc_suffix_lsconvo = "/xrpc/chat.bsky.convo.listConversations"
    xrpc_suffix_sendmsg = "/xrpc/chat.bsky.convo.sendMessage"

    # The default BlueSky host to use if one isn't specified
    bluesky_default_host = 'bsky.social'

    # Do not set body_maxlen as it is set in a property value below
    # since the length varies depending if we are doing a direct message
    # or a public post
    # body_maxlen = see below @propery defined

    # BlueSky does not support a title
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{user}@{password}',
        '{schema}://{user}@{password}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('Username'),
            'type': 'string',
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
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
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, targets=None, **kwargs):
        """
        Initialize BlueSky Object
        """
        super().__init__(**kwargs)

        # Our access token
        self.__access_token = self.store.get('access_token')
        self.__refresh_token = None
        self.__access_token_expiry = datetime.now(timezone.utc)

        if not self.user:
            msg = 'A BlueSky UserID/Handle must be specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Set our default host
        self.host = self.bluesky_default_host

        # Identify our targets
        results = HANDLE_HOST_PARSE_RE.match(self.user)
        if results:
            self.user = results.group('handle')
            self.host = results.group('host')

        has_error = False
        self.targets = []
        for target in parse_list(targets):
            match = IS_USER.match(target)
            if match and match.group('user'):
                self.targets.append(
                    '{}.{}'.format(
                        match.group('user'), match.group('host').lower()
                        if match.group('host') else self.host))
                continue

            has_error = True
            self.logger.warning(
                'Dropped invalid BlueSky user ({}) specified.'.format(target),
            )

        if has_error and not self.targets:
            # We have specified that we want to notify one or more individual
            # and we failed to load any of them.  Since it's also valid to
            # notify no one at all (which means we notify ourselves), it's
            # important we don't switch from the users original intentions
            self.targets = None

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform BlueSky Notification
        """

        if self.targets is None:
            # Users were specified, but were invalid
            self.logger.warning('No valid BlueSky targets to notify.')
            return False

        if not self.__access_token and not self.login():
            # We failed to authenticate - we're done

            return False

        if not self.targets:  # Public Message
            url = f'https://{self.host}{self.xrpc_suffix_record}'
            now = datetime.now(tz=timezone.utc)

            payload = {
                "collection": "app.bsky.feed.post",
                "repo": self.get_identifier(),
                "record": {
                    "text": body,
                    # 'YYYY-mm-ddTHH:MM:SSZ'
                    "createdAt": now.strftime('%FT%XZ'),
                    "$type": "app.bsky.feed.post"
                }
            }

            # Send Login Information
            postokay, response = self._fetch(
                url,
                payload=json.dumps(payload),
                # We set this boolean so internal recursion doesn't take place.
                login=True,
            )
            if not postokay:
                # We failed
                # Bad responses look like:
                # {
                #   'error': 'InvalidRequest',
                #   'message': 'reason'
                # }
                return False
            return True

        # If we get here, we're creating Private Message
        url = f'https://{self.host}{self.xrpc_suffix_sendmsg}'
        for target in self.targets:
            try:
                cid = self.get_conversation(target)
                if not cid:
                    pass

            except BlueSkyDMUnsupported:
                return False

            now = datetime.now(tz=timezone.utc)
            payload = {
                "convoId": cid,
                "message": {
                    "createdAt": now.strftime('%FT%XZ'),
                    "text": body,
                }
            }

            # Send Login Information
            postokay, response = self._fetch(
                url,
                payload=json.dumps(payload),
                # We set this boolean so internal recursion doesn't take place.
                login=True,
            )
            if not postokay:
                # We failed
                # Bad responses look like:
                # {
                #   'error': 'InvalidRequest',
                #   'message': 'reason'
                # }
                return False

        return True

    def get_conversation(self, user):
        """
        Provided a user, a conversation is searched; you can not
        start a brand new conversation (as it is unsupported)
        """

        # First get our identifier
        did = self.get_identifier(user)
        if not did:
            # Not possible to get conversation
            return False

        url = f'https://{self.host}{self.xrpc_suffix_lsconvo}'

        # Track our retrievals (if more than one in a pagination response)
        cursor = None

        while True:
            params = {}
            if cursor:
                params["cursor"] = cursor

            # Send Login Information
            postokay, response = self._fetch(
                url,
                params=params,
                method='GET',
            )
            if not postokay:
                # We had web request issues
                if response.get('error') == 'MethodNotImplemented':
                    raise BlueSkyDMUnsupported()
                return False

            # Store our cursor (if defined)
            cursor = response.get("cursor")

            participant_dids = \
                {p["did"] for p in response["conversation"]["participants"]}
            if len(participant_dids) == 1:
                # We do not want to post in collective groups involving
                # this person, only an exclusive private message
                return response['conversation']["id"]

            if not cursor:
                # Prevent looping forever
                break

    def get_identifier(self, user=None, login=False):
        """
        Performs a Decentralized User Lookup and returns the identifier
        """

        if user is None:
            user = self.user

        user = f'{user}.{self.host}' if '.' not in user else f'{user}'
        key = f'did.{user}'
        did = self.store.get(key)
        if did:
            return did

        url = f'https://{self.host}{self.xrpc_suffix_did}'
        params = {'handle': user}

        # Send Login Information
        postokay, response = self._fetch(
            url,
            params=params,
            method='GET',
            # We set this boolean so internal recursion doesn't take place.
            login=login,
        )

        if not postokay or not response or 'did' not in response:
            # We failed
            return False

        # Acquire our Decentralized Identitifer
        did = response.get('did')
        self.store.set(key, did)
        return did

    def login(self):
        """
        A simple wrapper to authenticate with the BlueSky Server
        """

        # Acquire our Decentralized Identitifer
        did = self.get_identifier(self.user, login=True)
        if not did:
            return False

        url = f'https://{self.host}{self.xrpc_suffix_session}'

        payload = {
            "identifier": did,
            "password": self.password,
        }

        # Send Login Information
        postokay, response = self._fetch(
            url,
            payload=json.dumps(payload),
            # We set this boolean so internal recursion doesn't take place.
            login=True,
        )

        # Our response object looks like this (content has been altered for
        # presentation purposes):
        # {
        #  'did': 'did:plc:ruk414jakghak402j1jqekj2',
        #  'didDoc': {
        #    '@context': [
        #      'https://www.w3.org/ns/did/v1',
        #      'https://w3id.org/security/multikey/v1',
        #      'https://w3id.org/security/suites/secp256k1-2019/v1'
        #    ],
        #    'id': 'did:plc:ruk414jakghak402j1jqekj2',
        #    'alsoKnownAs': ['at://apprise.bsky.social'],
        #    'verificationMethod': [
        #      {
        #        'id': 'did:plc:ruk414jakghak402j1jqekj2#atproto',
        #        'type': 'Multikey',
        #        'controller': 'did:plc:ruk414jakghak402j1jqekj2',
        #        'publicKeyMultibase' 'redacted'
        #      }
        #    ],
        #  'service': [
        #      {
        #        'id': '#atproto_pds',
        #        'type': 'AtprotoPersonalDataServer',
        #        'serviceEndpoint':
        #           'https://woodtuft.us-west.host.bsky.network'
        #      }
        #    ]
        #  },
        #  'handle': 'apprise.bsky.social',
        #  'email': 'whoami@gmail.com',
        #  'emailConfirmed': True,
        #  'emailAuthFactor': False,
        #  'accessJwt': 'redacted',
        #  'refreshJwt': 'redacted',
        #  'active': True,
        # }

        if not postokay or not response:
            # We failed
            return False

        # Acquire our Token
        self.__access_token = response.get('accessJwt')

        # Handle other optional arguments we can use
        self.__access_token_expiry = self.access_token_lifetime_sec + \
            datetime.now(timezone.utc) - self.clock_skew

        # The Refresh Token
        self.__refresh_token = response.get('refreshJwt', self.__refresh_token)
        self.store.set(
            'access_token', self.__access_token, self.__access_token_expiry)
        self.store.set(
            'refresh_token', self.__refresh_token, self.__access_token_expiry)

        self.logger.info('Authenticated to BlueSky as {}.{}'.format(
            self.user, self.host))
        return True

    def _fetch(self, url, payload=None, params=None, method='POST',
               login=False):
        """
        Wrapper to BlueSky API requests object
        """

        # use what was specified, otherwise build headers dynamically
        headers = {
            'User-Agent': self.app_id,
            'Content-Type':
            'application/x-www-form-urlencoded; charset=utf-8'
            if method == 'GET' else 'application/json'
        }

        if self.__access_token:
            # Set our token
            headers['Authorization'] = 'Bearer {}'.format(self.__access_token)

        # Some Debug Logging
        self.logger.debug('BlueSky {} URL: {} (cert_verify={})'.format(
            method, url, self.verify_certificate))
        self.logger.debug('BlueSky Payload: %s' % str(payload))

        # Always call throttle before any remote server i/o is made;
        self.throttle()

        # Initialize a default value for our content value
        content = {}

        # acquire our request mode
        fn = requests.post if method == 'POST' else requests.get
        try:
            r = fn(
                url,
                data=payload,
                params=params,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            # Get our JSON content if it's possible
            try:
                content = json.loads(r.content)

            except (TypeError, ValueError, AttributeError):
                # TypeError = r.content is not a String
                # ValueError = r.content is Unparsable
                # AttributeError = r.content is None
                content = {}

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyBlueSky.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send BlueSky {} to {}: '
                    '{}error={}.'.format(
                        method,
                        url,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending BlueSky {} to {}: '.
                format(method, url))
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return (False, content)

        return (True, content)

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol[0],
            self.user, self.password,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Apply our other parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # our URL
        return '{schema}://{user}@{password}/{targets}?{params}'.format(
            schema=self.protocol,
            user=NotifyBlueSky.quote(self.user, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            targets='/'.join(
                [NotifyBlueSky.quote('@{}'.format(target), safe='@')
                 for target in self.targets]) if self.targets else '',
            params=NotifyBlueSky.urlencode(params),
        )

    @property
    def body_maxlen(self):
        """
        The maximum allowable characters allowed in the body per message
        This is used during a Private DM Message Size (not Public Posts
        which are limited to 280 characters)
        """
        return 10000 if self.targets else 280

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
        return targets if targets > 0 else 1

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

        if not results.get('password') and results['host']:
            results['password'] = NotifyBlueSky.unquote(results['host'])
            results['targets'] = []

        else:
            # Get targets (if any)
            results['targets'] = [NotifyBlueSky.unquote(results['host'])]

        results['targets'] += NotifyBlueSky.split_path(results['fullpath'])

        # Do not use host field
        results['host'] = None
        return results
