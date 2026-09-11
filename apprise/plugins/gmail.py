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
import base64
import json
import time
from datetime import datetime
from datetime import timedelta
from .base import NotifyBase
from .. import exception
from email.utils import formataddr
from ..url import PrivacyMode
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils.parse import is_email, parse_emails, validate_regex
from ..locale import gettext_lazy as _
from ..common import PersistentStoreMode
from . import email as _email


class NotifyGMail(NotifyBase):
    """
    A wrapper for GMail Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'GMail'

    # The services URL
    service_url = 'https://mail.google.com/'

    # The default protocol
    secure_protocol = 'gmail'

    # GMail SMTP Host (used for generating a Message-ID)
    google_smtp_host = 'smtp.gmail.com'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_gmail'

    # Google OAuth2 URLs
    device_url = "https://oauth2.googleapis.com/device/code"
    token_url = "https://oauth2.googleapis.com/token"
    send_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

    # The maximum number of seconds we will wait for our token to be acquired
    token_acquisition_timeout = 14.0

    # Required Scope
    scope = "https://www.googleapis.com/auth/gmail.send"

    # Support attachments
    attachment_support = True

    # Our default is to no not use persistent storage beyond in-memory
    # reference
    storage_mode = PersistentStoreMode.AUTO

    # Default Notify Format
    notify_format = NotifyFormat.HTML

    # Define object templates
    templates = (
        '{schema}://{user}@{client_id}/{secret}',
        '{schema}://{user}@{client_id}/{secret}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('Username'),
            'type': 'string',
            'required': True,
        },
        'client_id': {
            'name': _('Client ID'),
            'type': 'string',
            'required': True,
            'private': True,
            # Generally looks like:
            # 12345012-xxxxxxxxxxxxxxxxxxxxxxxxxxxx.apps.googleusercontent.com
            'regex': (r'^[a-z0-9-.]+$', 'i'),
        },
        'secret': {
            'name': _('Client Secret'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_email': {
            'name': _('Target Email'),
            'type': 'string',
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
        'cc': {
            'name': _('Carbon Copy'),
            'type': 'list:string',
        },
        'bcc': {
            'name': _('Blind Carbon Copy'),
            'type': 'list:string',
        },
        'client_id': {
            'alias_of': 'client_id',
        },
        'secret': {
            'alias_of': 'secret',
        },
        'from': {
            'name': _('From Email'),
            'type': 'string',
            'map_to': 'from_addr',
        },
        'pgp': {
            'name': _('PGP Encryption'),
            'type': 'bool',
            'map_to': 'use_pgp',
            'default': False,
        },
        'pgpkey': {
            'name': _('PGP Public Key Path'),
            'type': 'string',
            'private': True,
            # By default persistent storage is referenced
            'default': '',
            'map_to': 'pgp_key',
        },
        'reply': {
            'name': _('Reply To'),
            'type': 'list:string',
            'map_to': 'reply_to',
        },
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('Email Header'),
            'prefix': '+',
        },
    }

    def __init__(self, client_id, secret, targets=None, from_addr=None,
                 cc=None, bcc=None, reply_to=None, headers=None,
                 use_pgp=None, pgp_key=None, **kwargs):
        """
        Initialize GMail Object
        """
        super().__init__(**kwargs)

        # Client Key (associated with generated OAuth2 Login)
        if not self.user:
            msg = 'An invalid GMail User ' \
                  '({}) was specified.'.format(self.user)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Client Key (associated with generated OAuth2 Login)
        self.client_id = validate_regex(
            client_id, *self.template_tokens['client_id']['regex'])
        if not self.client_id:
            msg = 'An invalid GMail Client OAuth2 ID ' \
                  '({}) was specified.'.format(client_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Client Secret (associated with generated OAuth2 Login)
        self.secret = validate_regex(secret)
        if not self.secret:
            msg = 'An invalid GMail Client OAuth2 Secret ' \
                  '({}) was specified.'.format(secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # For tracking our email -> name lookups
        self.names = {}

        # Save our headers
        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Acquire Reply To
        self.reply_to = set()

        # Parse our targets
        self.targets = list()

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_emails(cc):
            email = is_email(recipient)
            if email:
                self.cc.add(email['full_email'])

                # Index our name (if one exists)
                self.names[email['full_email']] = \
                    email['name'] if email['name'] else False
                continue

            self.logger.warning(
                'Dropped invalid Carbon Copy email '
                '({}) specified.'.format(recipient),
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_emails(bcc):
            email = is_email(recipient)
            if email:
                self.bcc.add(email['full_email'])

                # Index our name (if one exists)
                self.names[email['full_email']] = \
                    email['name'] if email['name'] else False
                continue

            self.logger.warning(
                'Dropped invalid Blind Carbon Copy email '
                '({}) specified.'.format(recipient),
            )

        # Validate recipients (reply-to:) and drop bad ones:
        for recipient in parse_emails(reply_to):
            email = is_email(recipient)
            if email:
                self.reply_to.add(email['full_email'])

                # Index our name (if one exists)
                self.names[email['full_email']] = \
                    email['name'] if email['name'] else False
                continue

            self.logger.warning(
                'Dropped invalid Reply To email '
                '({}) specified.'.format(recipient),
            )

        # Our token is acquired upon a successful login
        self.token = None
        self.refresh = None

        # Presume that our token has expired 'now'
        self.token_expiry = datetime.now()

        # Now we want to construct the To and From email
        # addresses from the URL provided
        self.from_addr = [False, '']

        if from_addr:
            result = is_email(from_addr)
            if result:
                self.from_addr = (
                    result['name'] if result['name'] else False,
                    result['full_email'])
            else:
                # Only update the string but use the already detected info
                self.from_addr[0] = from_addr

        else:  # Send email to ourselves by default
            self.from_addr[1] = f'{self.user}@gmail.com'

        result = is_email(self.from_addr[1])
        if not result:
            # Parse Source domain based on from_addr
            msg = 'Invalid ~From~ email specified: {}'.format(
                '{} <{}>'.format(self.from_addr[0], self.from_addr[1])
                if self.from_addr[0] else '{}'.format(self.from_addr[1]))
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our lookup
        self.names[self.from_addr[1]] = self.from_addr[0]

        if targets:
            for recipient in parse_emails(targets):
                # Validate recipients (to:) and drop bad ones:
                result = is_email(recipient)
                if result:
                    # Add our email to our target list
                    self.targets.append(
                        (result['name'] if result['name'] else False,
                            result['full_email']))
                    continue

                self.logger.warning(
                    'Dropped invalid To email ({}) specified.'
                    .format(recipient))
        else:
            self.targets.append((False, self.from_addr[1]))

        # Prepare our Pretty Good Privacy Object
        self.pgp = _email.pgp.ApprisePGPController(
            path=self.store.path, pub_keyfile=pgp_key,
            email=self.from_addr[1], asset=self.asset)

        # We store so we can generate a URL later on
        self.pgp_key = pgp_key

        self.use_pgp = use_pgp if not None \
            else self.template_args['pgp']['default']

        if self.use_pgp and not email.pgp.PGP_SUPPORT:
            self.logger.warning(
                'PGP Support is not available on this installation; '
                'ask admin to install PGPy')

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform GMail Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                'There are no Email recipients to notify')
            return False

        if not self.authenticate():
            self.logger.warning('Could not authenticate with the GMail')
            return False

        # Prepare our headers
        headers = {
            'X-Application': self.app_id,
        }
        headers.update(self.headers)

        try:
            for message in _email.NotifyEmail.prepare_emails(
                    subject=title, body=body, notify_format=self.notify_format,
                    from_addr=self.from_addr, to=self.targets,
                    cc=self.cc, bcc=self.bcc, reply_to=self.reply_to,
                    smtp_host=self.google_smtp_host,
                    attach=attach, headers=headers, names=self.names,
                    pgp=self.pgp):

                # Encode the message in base64
                payload = {
                    "raw": base64.urlsafe_b64encode(
                        message.body.encode()).decode()
                }

                # Perform upstream post
                postokay, response = self._fetch(
                    url=self.send_url, payload=payload)
                if not postokay:
                    has_error = True

        except exception.AppriseException as e:
            self.logger.debug(f'Socket Exception: {e}')

            # Mark as failure
            has_error = True

        return not has_error

    # def authenticate(self):
    #     """
    #     JWT Authentication
    #     """

    #     iat = time.time()
    #     exp = iat + 3600  # Token valid for 1 hour

    #     payload = {
    #         # Issuer (service account email)
    #         "iss": self.from_addr[1],
    #         # Scopes for Gmail API
    #         "scope": self.scope,
    #         # Audience (token endpoint)
    #         "aud": self.token_url,
    #         # Expiration time
    #         "exp": exp,
    #         # Issued at time
    #         "iat": iat
    #     }

    def authenticate(self, timeout=None, long_poll=5.0, short_poll=2.0):
        """
        Logs into and acquires us an authentication token to work with
        """

        if self.token and self.token_expiry > datetime.now():
            # If we're already authenticated and our token is still valid
            self.logger.debug(
                'Already authenticate with token {}'.format(self.token))
            return True

        if not timeout:
            # Save our default timeout
            timeout = self.token_acquisition_timeout

        def token_store(response, save=True):
            """
            Stores token data
            """
            try:
                # Extract our time from our response and subtrace 10
                # seconds from it to give us some wiggle/grace people to
                # re-authenticate if we need to
                self.token_expiry = datetime.now() + \
                    timedelta(seconds=int(response.get('expires_in')) - 10)

            except (ValueError, AttributeError, TypeError):
                # ValueError: expires_in wasn't an integer
                # TypeError: expires_in was None
                # AttributeError: we could not extract anything from our
                #                 response object.
                return False

            if save:
                # store our content to disk
                self.store.write(
                    json.dumps(response).encode('utf-8'), key='tokens')

            # Store our other tokens for fast access
            self.token = response.get("access_token")
            self.refresh = response.get("refresh_token")
            return True

        # Read our content to see if it exists
        try:
            response = json.loads(
                self.store.read(key='tokens').decode('utf-8'))

        except AttributeError:
            # NoneType returned; nothing to decode.
            response = None

        if response and token_store(response, save=False) and self.refresh:
            if self.token_expiry > (datetime.now() - timedelta(days=20)):
                #
                # We have to refresh our token
                #
                payload = {
                    "client_id": self.client_id,
                    "client_secret": self.secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                }

                postokay, response = self._fetch(
                    url=self.token_url, payload=payload)
                if postokay and token_store(response):
                    # We were successful
                    return True

            elif self.token:
                # we're good with the information we have
                return True

        #
        # If we reach here, we've either expired, or we need to authenticate
        # for the first time.
        #
        # Reset our token
        self.token = None
        self.refresh = None

        # Reset our token cache file
        self.store.delete('tokens')

        # Prepare our payload
        payload = {
            "client_id": self.client_id,
            "scope": self.scope,
        }

        postokay, response = self._fetch(
            url=self.device_url, payload=payload,
            content_type=None)
        if not postokay:
            return False

        # A device token is required to get our token
        device_code = None

        # Go ahead and store our token if it's available
        device_code = response.get('device_code')

        payload = {
            "client_id": self.client_id,
            "client_secret": self.secret,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }

        self.logger.debug(
            'Blocking until GMail token can be acquired ...')

        reference = datetime.now()

        while True:
            postokay, response = self._fetch(
                url=self.token_url, payload=payload)

            if postokay and token_store(response):
                # We were successful
                break

            if response and response.get("error") in (
                    "authorization_pending", "slow_down"):

                # Our own throttle so we can abort eventually....
                elapsed = (datetime.now() - reference).total_seconds()
                remaining = \
                    0.0 if (timeout - elapsed) < 0.0 else (timeout - elapsed)
                self.logger.action_required(
                    f"Visit \"{response['verification_url']}\" "
                    f"and enter code: {response['user_code']} "
                    f"- [remaining={remaining:.2f}sec]")

                if elapsed >= timeout:
                    self.logger.warning('GMail token could not be acquired')
                    break

                # Throttle
                time.sleep(
                    short_poll if response.get("error") != "slow_down"
                    else long_poll)

                # Loop and see if we were successful
                continue

            # We failed
            break

        # Return our success (if we were at all)
        return True if self.token else False

    def _fetch(self, url, payload=None, headers=None,
               content_type='application/json'):
        """
        Wrapper to request object

        """

        # Prepare our headers:
        if not headers:
            headers = {
                'User-Agent': self.app_id,
            }

        if content_type:
            headers.update({
                'Content-Type': content_type,
            })

        if self.token:
            # Are we authenticated?
            headers['Authorization'] = 'Bearer ' + self.token

        # Default content response object
        content = {}

        # Some Debug Logging
        self.logger.debug('GMail URL: {} (cert_verify={})'.format(
            url, self.verify_certificate))
        self.logger.debug('GMail Payload: {}' .format(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=json.dumps(payload)
                if content_type and content_type.endswith('/json')
                else payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            try:
                content = json.loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            if r.status_code not in (
                    requests.codes.ok, requests.codes.created,
                    requests.codes.accepted):

                self.logger.warning(
                    'Failed to send GMail to %s [error=%d]',
                    url, r.status_code)

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending GMail to {}: '.
                format(url))
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
        return (self.secure_protocol, self.user, self.client_id,
                self.secret)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define an URL parameters
        params = {
            'pgp': 'yes' if self.use_pgp else 'no',
        }

        # Store our public key back into your URL
        if self.pgp_key is not None:
            params['pgp_key'] = NotifyGMail.quote(self.pgp_key, safe=':\\/')

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.cc:
            # Handle our Carbon Copy Addresses
            params['cc'] = ','.join([
                formataddr(
                    (self.names[e] if e in self.names else False, e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset='utf-8').replace(',', '%2C')
                for e in self.cc])

        if self.bcc:
            # Handle our Blind Carbon Copy Addresses
            params['bcc'] = ','.join([
                formataddr(
                    (self.names[e] if e in self.names else False, e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset='utf-8').replace(',', '%2C')
                for e in self.bcc])

        if self.reply_to:
            # Handle our Reply-To Addresses
            params['reply'] = ','.join([
                formataddr(
                    (self.names[e] if e in self.names else False, e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset='utf-8').replace(',', '%2C')
                for e in self.reply_to])

        return '{schema}://{user}@{client_id}/{secret}' \
            '/{targets}/?{params}'.format(
                schema=self.secure_protocol,
                user=self.user,
                client_id=self.pprint(self.client_id, privacy, safe=''),
                secret=self.pprint(
                    self.secret, privacy, mode=PrivacyMode.Secret,
                    safe=''),
                targets='/'.join(
                    [NotifyGMail.quote('{}{}'.format(
                        '' if not e[0] else '{}:'.format(e[0]), e[1]),
                        safe='@') for e in self.targets]),
                params=NotifyGMail.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return len(self.targets)

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

        # Now make a list of all our path entries
        # We need to read each entry back one at a time in reverse order
        # where each email found we mark as a target. Once we run out
        # of targets, the presume the remainder of the entries are part
        # of the secret key (since it can contain slashes in it)
        entries = NotifyGMail.split_path(results['fullpath'])
        entries.insert(0, NotifyGMail.unquote(results['host']))

        # Initialize our email
        results['email'] = None

        # From Email
        if 'from' in results['qsd'] and \
                len(results['qsd']['from']):
            # Extract the sending account's information
            results['source'] = \
                NotifyGMail.unquote(results['qsd']['from'])

        # OAuth2 ID
        if 'client_id' in results['qsd'] and len(results['qsd']['client_id']):
            # Extract the API Key from an argument
            results['client_id'] = \
                NotifyGMail.unquote(results['qsd']['client_id'])

        elif entries:
            # Get our client_id is the first entry on the path
            results['client_id'] = NotifyGMail.unquote(entries.pop(0))

        # OAuth2 Secret
        if 'secret' in results['qsd'] and len(results['qsd']['secret']):
            # Extract the API Key from an argument
            results['secret'] = \
                NotifyGMail.unquote(results['qsd']['secret'])

        elif entries:
            # Get our secret is the next entry on the path
            results['secret'] = NotifyGMail.unquote(entries.pop(0))

        #
        # Prepare our target listing
        #
        results['targets'] = list()
        while entries:
            # Pop our remaining entries
            entry = NotifyGMail.unquote(entries.pop())

            if is_email(entry):
                # Store our email and move on
                results['targets'].append(entry)
                continue

            # If we reach here, the entry we just popped is part of the secret
            # key, so put it back
            entries.append(NotifyGMail.quote(entry, safe=''))

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyGMail.parse_list(results['qsd']['to'])

        # Handle Carbon Copy Addresses
        if 'cc' in results['qsd'] and len(results['qsd']['cc']):
            results['cc'] = results['qsd']['cc']

        # Handle Blind Carbon Copy Addresses
        if 'bcc' in results['qsd'] and len(results['qsd']['bcc']):
            results['bcc'] = results['qsd']['bcc']

        # Handle Reply To Addresses
        if 'reply' in results['qsd'] and len(results['qsd']['reply']):
            results['reply_to'] = results['qsd']['reply']

        # Add our Meta Headers that the user can provide with their outbound
        # emails
        results['headers'] = {NotifyBase.unquote(x): NotifyBase.unquote(y)
                              for x, y in results['qsd+'].items()}

        return results
