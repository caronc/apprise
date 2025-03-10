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
#       bluesky://handle@you-token-here
#
import re
import requests
import json
from datetime import (datetime, timezone, timedelta)
from ..attachment.base import AttachBase
from .base import NotifyBase
from ..url import PrivacyMode
from ..common import NotifyType
from ..locale import gettext_lazy as _

# For parsing handles
HANDLE_HOST_PARSE_RE = re.compile(r'(?P<handle>[^.]+)\.+(?P<host>.+)$')

IS_USER = re.compile(r'^\s*@?(?P<user>[A-Z0-9_]+)(\.+(?P<host>.+))?$', re.I)


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

    # Support attachments
    attachment_support = True

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
    xrpc_suffix_blob = "/xrpc/com.atproto.repo.uploadBlob"

    # BlueSky is kind enough to return how many more requests we're allowed to
    # continue to make within it's header response as:
    # RateLimit-Reset: The epoc time (in seconds) we can expect our
    #                   rate-limit to be reset.
    # RateLimit-Remaining: an integer identifying how many requests we're
    #                      still allow to make.
    request_rate_per_sec = 0

    # For Tracking Purposes
    ratelimit_reset = datetime.now(timezone.utc).replace(tzinfo=None)

    # Remaining messages
    ratelimit_remaining = 1

    # The default BlueSky host to use if one isn't specified
    bluesky_default_host = 'bsky.social'

    # Our message body size
    body_maxlen = 280

    # BlueSky does not support a title
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{user}@{password}',
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
    })

    def __init__(self, **kwargs):
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

        # Identify our Handle (if define)
        results = HANDLE_HOST_PARSE_RE.match(self.user)
        if results:
            self.user = results.group('handle').strip()
            self.host = results.group('host').strip()

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform BlueSky Notification
        """

        if not self.__access_token and not self.login():
            # We failed to authenticate - we're done
            return False

        # Track our returning blob IDs as they're stored on the BlueSky server
        blobs = []

        if attach and self.attachment_support:
            url = f'https://{self.host}{self.xrpc_suffix_blob}'
            # We need to upload our payload first so that we can source it
            # in remaining messages
            for no, attachment in enumerate(attach, start=1):

                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                if not re.match(r'^image/.*', attachment.mimetype, re.I):
                    # Only support images at this time
                    self.logger.warning(
                        'Ignoring unsupported BlueSky attachment {}.'.format(
                            attachment.url(privacy=True)))
                    continue

                self.logger.debug(
                    'Preparing BlueSky attachment {}'.format(
                        attachment.url(privacy=True)))

                # Upload our image and get our blob associated with it
                postokay, response = self._fetch(
                    url,
                    payload=attachment,
                )

                if not postokay:
                    # We can't post our attachment
                    return False

                # Prepare our filename
                filename = attachment.name \
                    if attachment.name else f'file{no:03}.dat'

                if not (isinstance(response, dict)
                        and response.get('blob')):
                    self.logger.debug(
                        'Could not attach the file to BlueSky: %s (mime=%s)',
                        filename, attachment.mimetype)
                    continue

                blobs.append((response.get('blob'), filename))

        # Prepare our URL
        url = f'https://{self.host}{self.xrpc_suffix_record}'

        # prepare our batch of payloads to create
        payloads = []

        payload = {
            "collection": "app.bsky.feed.post",
            "repo": self.get_identifier(),
            "record": {
                "text": body,
                # 'YYYY-mm-ddTHH:MM:SSZ'
                "createdAt": datetime.now(
                    tz=timezone.utc).strftime('%FT%XZ'),
                "$type": "app.bsky.feed.post"
            }
        }

        if blobs:
            for no, blob in enumerate(blobs, start=1):
                _payload = payload.copy()
                if no > 1:
                    #
                    # multiple instances
                    #
                    # 1. update createdAt time
                    # 2. Change text to identify image no
                    _payload['record']['createdAt'] = \
                        datetime.now(tz=timezone.utc).strftime('%FT%XZ')
                    _payload['record']['text'] = \
                        '{:02d}/{:02d}'.format(no, len(blobs))

                _payload['record']['embed'] = {
                    "images": [
                        {
                            "image": blob[0],
                            "alt": blob[1],
                        }
                    ],
                    "$type": "app.bsky.embed.images"
                }
                payloads.append(_payload)
        else:
            payloads.append(payload)

        for payload in payloads:
            # Send Login Information
            postokay, response = self._fetch(
                url,
                payload=json.dumps(payload),
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
               content_type=None, login=False):
        """
        Wrapper to BlueSky API requests object
        """

        # use what was specified, otherwise build headers dynamically
        headers = {
            'User-Agent': self.app_id,
            'Content-Type':
            payload.mimetype if isinstance(payload, AttachBase) else (
                'application/x-www-form-urlencoded; charset=utf-8'
                if method == 'GET' else 'application/json')
        }

        if self.__access_token:
            # Set our token
            headers['Authorization'] = 'Bearer {}'.format(self.__access_token)

        # Some Debug Logging
        self.logger.debug('BlueSky {} URL: {} (cert_verify={})'.format(
            method, url, self.verify_certificate))
        self.logger.debug(
            'BlueSky Payload: %s', str(payload)
            if not isinstance(payload, AttachBase)
            else 'attach: ' + payload.name)

        # By default set wait to None
        wait = None

        if self.ratelimit_remaining == 0:
            # Determine how long we should wait for or if we should wait at
            # all. This isn't fool-proof because we can't be sure the client
            # time (calling this script) is completely synced up with the
            # Twitter server.  One would hope we're on NTP and our clocks are
            # the same allowing this to role smoothly:

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if now < self.ratelimit_reset:
                # We need to throttle for the difference in seconds
                # We add 0.3 seconds to the end just to allow a grace
                # period.
                wait = (self.ratelimit_reset - now).total_seconds() + 0.3

        # Always call throttle before any remote server i/o is made;
        self.throttle(wait=wait)

        # Initialize a default value for our content value
        content = {}

        # acquire our request mode
        fn = requests.post if method == 'POST' else requests.get
        try:
            r = fn(
                url,
                data=payload if not isinstance(payload, AttachBase)
                else payload.open(),
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

            # Rate limit handling... our header objects at this point are:
            # 'RateLimit-Limit': '10',     # Total # of requests per hour
            # 'RateLimit-Remaining': '9',  # Requests remaining
            # 'RateLimit-Reset': '1741631362',  # Epoch Time
            # 'RateLimit-Policy': '10;w=86400' # NoEntries;w=<window>
            try:
                # Capture rate limiting if possible
                self.ratelimit_remaining = \
                    int(r.headers.get('ratelimit-remaining'))
                self.ratelimit_reset = datetime.fromtimestamp(
                    int(r.headers.get('ratelimit-reset')), timezone.utc
                ).replace(tzinfo=None)

            except (TypeError, ValueError):
                # This is returned if we could not retrieve this information
                # gracefully accept this state and move on
                pass

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

        except (OSError, IOError) as e:
            self.logger.warning(
                'An I/O error occurred while handling {}.'.format(
                    payload.name if isinstance(payload, AttachBase)
                    else payload))
            self.logger.debug('I/O Exception: %s' % str(e))
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

        user = self.user
        if self.host != self.bluesky_default_host:
            user += f'.{self.host}'

        # our URL
        return '{schema}://{user}@{password}?{params}'.format(
            schema=self.secure_protocol[0],
            user=NotifyBlueSky.quote(user, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            params=NotifyBlueSky.urlencode(params),
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

        if not results.get('password') and results['host']:
            results['password'] = NotifyBlueSky.unquote(results['host'])

        # Do not use host field
        results['host'] = None
        return results
