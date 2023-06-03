# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

# Sign-up with https://ringcentral.com
#
# Create an app using the developer API
#   - https://dashboard.ringcentral.com/
#
import requests

import base64
from json import dumps, loads
from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_phone_no
from ..utils import parse_phone_no
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _
from time import time


class RingCentralAuthMethod:
    BASIC = 'basic'
    JWT = 'jwt'


RINGCENTRAL_AUTH_METHODS = (
    RingCentralAuthMethod.BASIC,
    RingCentralAuthMethod.JWT,
)


class RingCentralEnvironment:
    DEVELOPMENT = 'dev'
    SANDBOX = 'sandbox'
    PRODUCTION = 'prod'


RINGCENTRAL_ENVIRONMENTS = {
    RingCentralEnvironment.PRODUCTION: '',
    RingCentralEnvironment.DEVELOPMENT: '.devtest',
    # Alias for Development
    RingCentralEnvironment.SANDBOX: '.devtest',
}


class RingCentralExtension:
    SMS = 'sms'
    MMS = 'mms'


RINGCENTRAL_EXTENSIONS = {
    RingCentralExtension.SMS: 'sms',
    RingCentralExtension.MMS: 'mms',
}


class NotifyRingCentral(NotifyBase):
    """
    A wrapper for RingCentral Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'RingCentral'

    # The services URL
    service_url = 'https://ringcentral.com/'

    # The default protocols
    secure_protocol = 'ringc'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_ringcentral'

    # RingCentral uses the http protocol with JSON requests
    notify_url = 'https://platform{environment}.ringcentral.com/' \
        'restapi/v1.0/account/~/extension/~/{extension}'

    # Oauth Token
    access_token_url = 'https://platform{environment}.ringcentral.com/' \
        'restapi/oauth/token'

    # Logout / Token Revoked
    revoke_token_url = 'https://platform{environment}.ringcentral.com/' \
        'restapi/oauth/revoke'

    # Authorize Endpoint
    auth_token_url = 'https://platform{environment}.ringcentral.com/' \
        'restapi/oauth/authorize'

    # 60 minutes
    access_token_ttl = 3600

    # 1 week
    refresh_token_ttl = 604800

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        # Auth
        '{schema}://{from_phone}:{password}@{client_id}/{secret}/',
        '{schema}://{from_phone}:{password}@{client_id}/{secret}/{targets}',
        '{schema}://{password}@{client_id}/{secret}/{from_phone}',
        '{schema}://{password}@{client_id}/{secret}/{from_phone}/{targets}',

        # JWT
        '{schema}://{from_phone}:{token}@{client_id}/{secret}/',
        '{schema}://{from_phone}:{token}@{client_id}/{secret}/{targets}',
        '{schema}://{token}@{client_id}/{secret}/{from_phone}',
        '{schema}://{token}@{client_id}/{secret}/{from_phone}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'token': {
            'name': _('Access Token'),
            'type': 'string',
            'required': True,
            'regex': (r'^[a-z0-9._-]+$', 'i'),
            'private': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'required': True,
            'private': True,
        },
        'client_id': {
            'name': _('Client ID'),
            'type': 'string',
            'required': True,
            'regex': (r'^[a-z0-9_-]+$', 'i'),
            'private': True,
        },
        'secret': {
            'name': _('Client Secret'),
            'type': 'string',
            'required': True,
            'regex': (r'^[a-z0-9_-]+$', 'i'),
            'private': True,
            'map_to': 'client_secret',
        },
        'from_phone': {
            'name': _('From Phone No'),
            'type': 'string',
            'required': True,
            'regex': (r'^\+?[0-9\s)(+-]+$', 'i'),
            'map_to': 'source',
        },
        'target_phone': {
            'name': _('Target Phone No'),
            'type': 'string',
            'prefix': '+',
            'regex': (r'^[0-9\s)(+-]+$', 'i'),
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
        'from': {
            'alias_of': 'from_phone',
        },
        'env': {
            'name': _('Environment'),
            'type': 'choice:string',
            'values': RINGCENTRAL_ENVIRONMENTS,
            'default': RingCentralEnvironment.PRODUCTION,
            'map_to': 'environment',
        },
        'ext': {
            'name': _('Extensions'),
            'type': 'choice:string',
            'values': RINGCENTRAL_EXTENSIONS,
            'default': RingCentralExtension.SMS,
            'map_to': 'extension',
        },
        'token': {
            'alias_of': 'token',
        },
        'id': {
            'alias_of': 'token',
        },
        'secret': {
            'alias_of': 'secret',
        },
        'mode': {
            # This is automatically detected
            'name': _('Authentication Mode'),
            'type': 'choice:string',
            'values': RINGCENTRAL_AUTH_METHODS,
        },
    })

    def __init__(self, source, targets=None, environment=None,
                 token=None, client_id=None, client_secret=None,
                 extension=None, mode=None, **kwargs):
        """
        Initialize RingCentral Object
        """
        super().__init__(**kwargs)

        # Authenticatio Tracking
        self._access_token = None
        self._expire_time = 0.0
        self._scope = None
        self._owner = None
        self._endpoint_id = None

        #
        # Auth Mode
        #
        self.token = None
        if isinstance(mode, str):
            _mode = mode.lower().strip()
            match = next((a for a in RINGCENTRAL_AUTH_METHODS
                         if a.startswith(_mode)), None) \
                if _mode else None

            # Now test to see if we got a match
            if not match:
                msg = 'An invalid RingCentral Authentication Mode ' \
                      '({}) was specified.'.format(mode)
                self.logger.warning(msg)
                raise TypeError(msg)

            # Otherwise store our extension
            self.mode = match
        else:
            # Default
            self.mode = RingCentralAuthMethod.BASIC

        if self.mode == RingCentralAuthMethod.JWT:
            # Access Token (associated with app)
            self.token = validate_regex(
                token, *self.template_tokens['token']['regex'])
            if not self.token:
                msg = 'An invalid RingCentral JWT Token ' \
                      '({}) was specified.'.format(token)
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            # Store token as regular password
            self.token = token

        self.client_id = None
        self.client_secret = None

        # Client ID
        self.client_id = validate_regex(
            client_id, *self.template_tokens['client_id']['regex'])
        if not self.client_id:
            msg = 'An invalid RingCentral Client ID ' \
                  '({}) was specified.'.format(client_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Client Secret
        self.client_secret = validate_regex(
            client_secret, *self.template_tokens['secret']['regex'])

        if not self.client_secret:
            msg = 'An invalid RingCentral Client Secret ' \
                  '({}) was specified.'.format(client_secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Source Phone #
        self.source = source

        result = is_phone_no(source)
        if not result:
            msg = 'The Account (From) Phone # specified ' \
                  '({}) is invalid.'.format(source)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our parsed value
        self.source = result['full']

        #
        # Environment
        #
        _environment = environment.lower().strip() \
            if isinstance(environment, str) else \
            NotifyRingCentral.template_args['env']['default']

        match = next((env for env in RINGCENTRAL_ENVIRONMENTS.keys()
                     if env.startswith(_environment)), None) \
            if _environment else None

        # Now test to see if we got a match
        if not match:
            msg = 'An invalid RingCentral environment ' \
                  '({}) was specified.'.format(environment)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Otherwise store our environment
        self.environment = match

        #
        # Extension
        #
        _extension = extension.lower().strip() \
            if isinstance(extension, str) else \
            NotifyRingCentral.template_args['ext']['default']

        match = next((ext for ext in RINGCENTRAL_EXTENSIONS.keys()
                     if ext.startswith(_extension)), None) \
            if _extension else None

        # Now test to see if we got a match
        if not match:
            msg = 'An invalid RingCentral extension ' \
                  '({}) was specified.'.format(extension)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Otherwise store our extension
        self.extension = match

        # Parse our targets
        self.targets = list()

        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    'Dropped invalid phone # '
                    '({}) specified.'.format(target),
                )
                continue

            # store valid phone number
            self.targets.append(result['full'])

        return

    def login(self):
        """
        Authenticates with the RingCentral server
        """

        if self._expire_time >= time():
            # Nothing further to do
            return True

        status = True
        url = self.access_token_url.format(
            environment=RINGCENTRAL_ENVIRONMENTS[self.environment],
        )
        payload = {}

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic {}'.format(
                str(base64.b64encode(
                    bytes(self.client_id + ':' + self.client_secret, 'utf8')),
                    'utf8'))
        }

        self._access_token = None
        self._scope = None
        self._owner = None
        self._endpoint_id = None

        if self.mode == RingCentralAuthMethod.BASIC:
            payload = {
                'grant_type': 'password',
                'username': '+' + self.source,
                'password': self.token,
                'access_token_ttl': self.access_token_ttl,
                'refresh_token_ttl': self.refresh_token_ttl,
            }

            status, response = self._send(
                url, payload, headers, name='auth.login', throttle=False)

        else:  # RingCentralAuthMethod.JWT
            payload = {
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': self.token,
            }

            status, response = self._send(
                url, payload, headers, name='auth.login', throttle=False)

        if status:
            self._access_token = response.get('access_token')
            self._expire_time = time() + response.get('expires_in')
            self._scope = response.get('scope')
            self._owner = response.get('owner')
            self._endpoint_id = response.get('endpoint_id')

        return status

    def logout(self):
        """
        Unauthenticates with the RingCentral server
        """
        if self._expire_time < time():
            # We're done
            return

        url = self.revoke_token_url.format(
            environment=RINGCENTRAL_ENVIRONMENTS[self.environment],
        )

        # Prepare our headers
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Basic {}'.format(
                str(base64.b64encode(
                    bytes(self.client_id + ':' + self.client_secret, 'utf8')),
                    'utf8'))
        }

        payload = {
            'token': self._access_token,
        }

        status, response = self._send(
            url, payload, headers, name='auth.logout', throttle=False)

        self._access_token = None
        self._expire_time = 0.0
        self._scope = None
        self._owner = None
        self._endpoint_id = None

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform RingCentral Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not self.login():
            self.logger.warning(
                'RingCentral %s Authentication Failed', self.mode)
            return False

        # Prepare our headers
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self._access_token)
        }

        # Prepare our URL
        notify_url = self.notify_url.format(
            environment=RINGCENTRAL_ENVIRONMENTS[self.environment],
            extension=RINGCENTRAL_EXTENSIONS[self.extension],
        )

        # Prepare our SMS payload
        # https://developers.ringcentral.com/api-reference/SMS/createSMSMessage
        payload = {
            'from': {
                'phoneNumber': '+' + self.source,
            },
            'to': [],
            'text': body,
        }

        # Create a copy of the targets list
        targets = list(self.targets)

        if len(targets) == 0:
            # No sources specified, use our own phone no
            targets.append(self.source)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload['to'].append({
                # The to gets populated in the loop below
                'phoneNumber': '+' + target
            })

            # Some Debug Logging
            status, response = self._send(notify_url, dumps(payload), headers)
            if status:
                self.logger.info(
                    'Sent RingCentral notification to %s.', target)

            else:
                # Mark our failure
                has_error = True
                continue

        return not has_error

    def _send(self, url, payload, headers, name='notification', throttle=True):
        """
        Since RingCentral has several connections it needs to make at times
        for authentication purposes, we move the posting to here.
        """
        headers.update({
            # Prepare our headers (minimum settings)
            'User-Agent': self.app_id,
            'Accept': 'application/json',
        })

        # Some Debug Logging
        self.logger.debug(
            'RingCentral POST URL: {} (cert_verify={})'.format(
                url, self.verify_certificate))
        self.logger.debug('RingCentral Payload: {}' .format(payload))

        if throttle:
            # Throttling is controlled since we don't want to throttle during
            # authentication calls
            self.throttle()

        content = None
        try:
            r = requests.post(
                url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            self.logger.trace('RingCentral Response: %s', r.content)

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifyRingCentral.http_response_code_lookup(
                        r.status_code)

                self.logger.warning(
                    'Failed to send RingCentral {}: '
                    '{}{}error={}.'.format(
                        name,
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
            else:
                # We were successful
                return (True, content)

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending RingCentral %s',
                name,
            )
            self.logger.debug('Socket Exception: %s' % str(e))

        return (False, content)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'env': str(self.environment),
            'ext': str(self.extension),
            'mode': str(self.mode),
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://{source}:{token}@{client_id}/{client_secret}/' \
            '{targets}/?{params}'.format(
                schema=self.secure_protocol,
                source=NotifyRingCentral.quote(self.source, safe=''),
                token=self.pprint(
                    self.token, privacy,
                    mode=PrivacyMode.Secret
                    if self.mode == RingCentralAuthMethod.BASIC
                    else PrivacyMode.Outer, safe=''),
                client_id=self.pprint(self.client_id, privacy, safe=''),
                client_secret=self.pprint(
                    self.client_secret, privacy, mode=PrivacyMode.Secret,
                    safe=''),
                targets='/'.join(
                    [NotifyRingCentral.quote(x, safe='')
                     for x in self.targets]),
                params=NotifyRingCentral.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
        return targets if targets > 0 else 1

    def __del__(self):
        """
        Deconstructor
        """
        # Log out if we aren't already
        try:
            self.logout()

        except Exception:
            # No worries... we tried
            pass

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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results['targets'] = NotifyRingCentral.split_path(results['fullpath'])

        results['client_id'] = \
            NotifyRingCentral.unquote(results['host'])

        results['client_secret'] = \
            results['targets'].pop(0) if results['targets'] else None

        # The next element is the source phone
        if not results.get('password'):
            # user is the source phone no
            # ringc://pass@client_id/secret/user
            results['source'] = \
                results['targets'].pop(0) if results['targets'] else None

            # Our Token can be a JWT code, or it can be our password to
            # authenticate with.
            results['token'] = NotifyRingCentral.unquote(results['user'])
        else:
            # user is the source phone no
            # ringc://user:pass@client_id/secret
            results['source'] = NotifyRingCentral.unquote(results['user'])
            # Our Token can be a JWT code, or it can be our password to
            # authenticate with.
            results['token'] = NotifyRingCentral.unquote(results['password'])

        # Environment
        if 'env' in results['qsd'] and len(results['qsd']['env']):
            # Extract the environment from an argument
            results['environment'] = \
                NotifyRingCentral.unquote(results['qsd']['env'])

        # Extension
        if 'ext' in results['qsd'] and len(results['qsd']['ext']):
            # Extract the extension from an argument
            results['extension'] = \
                NotifyRingCentral.unquote(results['qsd']['ext'])

        # Authorization mode
        if 'mode' in results['qsd'] and len(results['qsd']['mode']):
            # Extract the auth mode from an argument
            results['mode'] = \
                NotifyRingCentral.unquote(results['qsd']['mode'])

        elif len(results['token']) > 60:
            results['mode'] = RingCentralAuthMethod.JWT

        else:
            # Default
            results['mode'] = RingCentralAuthMethod.BASIC

        # Access Token
        if 'token' in results['qsd'] and len(results['qsd']['token']):
            # Extract the Access Token from an argument
            results['token'] = \
                NotifyRingCentral.unquote(results['qsd']['token'])

        # Client ID
        if 'id' in results['qsd'] and len(results['qsd']['id']):
            # Extract the Client ID from an argument
            results['token'] = \
                NotifyRingCentral.unquote(results['qsd']['id'])

        # Client Secret
        if 'secret' in results['qsd'] and len(results['qsd']['secret']):
            # Extract the Client ID from an argument
            results['client_secret'] = \
                NotifyRingCentral.unquote(results['qsd']['secret'])

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['source'] = \
                NotifyRingCentral.unquote(results['qsd']['from'])
        if 'source' in results['qsd'] and len(results['qsd']['source']):
            results['source'] = \
                NotifyRingCentral.unquote(results['qsd']['source'])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyRingCentral.parse_phone_no(results['qsd']['to'])

        return results
