# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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

# API Details:
# https://docs.microsoft.com/en-us/previous-versions/office/\
#        office-365-api/?redirectedfrom=MSDN

# Information on sending an email:
# https://docs.microsoft.com/en-us/graph/api/user-sendmail\
#       ?view=graph-rest-1.0&tabs=http

# Steps to get your Microsoft Client ID, Client Secret, and Tenant ID:
# 1. You should have valid Microsoft personal account. Go to Azure Portal
# 2. Go to -> Microsoft Active Directory --> App Registrations
# 3. Click new -> give any name (your choice) in Name field -> select
#     personal Microsoft accounts only --> Register
# 4.  Now you have your client_id & Tenant id.
# 5. To create client_secret , go to active directory ->
#          Certificate & Tokens -> New client secret
#               **This is auto-generated string which may have '@' and '?'
#                 characters in it. You should encode these to prevent
#                 from having any issues.**
# 6. Now need to set permission Active directory -> API permissions ->
#         Add permission (search mail) , add relevant permission.
# 7. Set the redirect uri (Web) to:
#        https://login.microsoftonline.com/common/oauth2/nativeclient
#
#     ...and click register.
#
#     This needs to be inserted into the "Redirect URI" text box as simply
#     checking the check box next to this link seems to be insufficient.
#     This is the default redirect uri used by this library, but you can use
#     any other if you want.
#
# 8. Now you're good to go

import requests
from datetime import datetime
from datetime import timedelta
from json import loads
from json import dumps
from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import is_email
from ..utils import parse_emails
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


class NotifyOffice365(NotifyBase):
    """
    A wrapper for Office 365 Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Office 365'

    # The services URL
    service_url = 'https://office.com/'

    # The default protocol
    secure_protocol = 'o365'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_office365'

    # URL to Microsoft Graph Server
    graph_url = 'https://graph.microsoft.com'

    # Authentication URL
    auth_url = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'

    # Use all the direct application permissions you have configured for your
    # app. The endpoint should issue a token for the ones associated with the
    # resource you want to use.
    # see https://docs.microsoft.com/en-us/azure/active-directory/develop/\
    #       v2-permissions-and-consent#the-default-scope
    scope = '.default'

    # Default Notify Format
    notify_format = NotifyFormat.HTML

    # Define object templates
    templates = (
        '{schema}://{tenant}:{email}/{client_id}/{secret}',
        '{schema}://{tenant}:{email}/{client_id}/{secret}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'tenant': {
            'name': _('Tenant Domain'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9-]+$', 'i'),
        },
        'email': {
            'name': _('Account Email'),
            'type': 'string',
            'required': True,
        },
        'client_id': {
            'name': _('Client ID'),
            'type': 'string',
            'required': True,
            'private': True,
            'regex': (r'^[a-z0-9-]+$', 'i'),
        },
        'secret': {
            'name': _('Client Secret'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'targets': {
            'name': _('Target Emails'),
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
        'oauth_id': {
            'alias_of': 'client_id',
        },
        'oauth_secret': {
            'alias_of': 'secret',
        },
    })

    def __init__(self, tenant, email, client_id, secret,
                 targets=None, cc=None, bcc=None, **kwargs):
        """
        Initialize Office 365 Object
        """
        super().__init__(**kwargs)

        # Tenant identifier
        self.tenant = validate_regex(
            tenant, *self.template_tokens['tenant']['regex'])
        if not self.tenant:
            msg = 'An invalid Office 365 Tenant' \
                  '({}) was specified.'.format(tenant)
            self.logger.warning(msg)
            raise TypeError(msg)

        result = is_email(email)
        if not result:
            msg = 'An invalid Office 365 Email Account ID' \
                  '({}) was specified.'.format(email)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Otherwise store our the email address
        self.email = result['full_email']

        # Client Key (associated with generated OAuth2 Login)
        self.client_id = validate_regex(
            client_id, *self.template_tokens['client_id']['regex'])
        if not self.client_id:
            msg = 'An invalid Office 365 Client OAuth2 ID ' \
                  '({}) was specified.'.format(client_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Client Secret (associated with generated OAuth2 Login)
        self.secret = validate_regex(secret)
        if not self.secret:
            msg = 'An invalid Office 365 Client OAuth2 Secret ' \
                  '({}) was specified.'.format(secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # For tracking our email -> name lookups
        self.names = {}

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Parse our targets
        self.targets = list()

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
            # If our target email list is empty we want to add ourselves to it
            self.targets.append((False, self.email))

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

        # Our token is acquired upon a successful login
        self.token = None

        # Presume that our token has expired 'now'
        self.token_expiry = datetime.now()

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Office 365 Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                'There are no Email recipients to notify')
            return False

        # Setup our Content Type
        content_type = \
            'HTML' if self.notify_format == NotifyFormat.HTML else 'Text'

        # Prepare our payload
        payload = {
            'Message': {
                'Subject': title,
                'Body': {
                    'ContentType': content_type,
                    'Content': body,
                },
            },
            'SaveToSentItems': 'false'
        }

        # Create a copy of the email list
        emails = list(self.targets)

        # Define our URL to post to
        url = '{graph_url}/v1.0/users/{email}/sendmail'.format(
            email=self.email,
            graph_url=self.graph_url,
        )

        while len(emails):
            # authenticate ourselves if we aren't already; but this function
            # also tracks if our token we have is still valid and will
            # re-authenticate ourselves if nessisary.
            if not self.authenticate():
                # We could not authenticate ourselves; we're done
                return False

            # Get our email to notify
            to_name, to_addr = emails.pop(0)

            # Strip target out of cc list if in To or Bcc
            cc = (self.cc - self.bcc - set([to_addr]))

            # Strip target out of bcc list if in To
            bcc = (self.bcc - set([to_addr]))

            # Prepare our email
            payload['Message']['ToRecipients'] = [{
                'EmailAddress': {
                    'Address': to_addr
                }
            }]
            if to_name:
                # Apply our To Name
                payload['Message']['ToRecipients'][0]['EmailAddress']['Name'] \
                    = to_name

            self.logger.debug('Email To: {}'.format(to_addr))

            if cc:
                # Prepare our CC list
                payload['Message']['CcRecipients'] = []
                for addr in cc:
                    _payload = {'Address': addr}
                    if self.names.get(addr):
                        _payload['Name'] = self.names[addr]

                    # Store our address in our payload
                    payload['Message']['CcRecipients']\
                        .append({'EmailAddress': _payload})

                self.logger.debug('Email Cc: {}'.format(', '.join(
                    ['{}{}'.format(
                        '' if self.names.get(e)
                        else '{}: '.format(self.names[e]), e) for e in cc])))

            if bcc:
                # Prepare our CC list
                payload['Message']['BccRecipients'] = []
                for addr in bcc:
                    _payload = {'Address': addr}
                    if self.names.get(addr):
                        _payload['Name'] = self.names[addr]

                    # Store our address in our payload
                    payload['Message']['BccRecipients']\
                        .append({'EmailAddress': _payload})

                self.logger.debug('Email Bcc: {}'.format(', '.join(
                    ['{}{}'.format(
                        '' if self.names.get(e)
                        else '{}: '.format(self.names[e]), e) for e in bcc])))

            # Perform upstream fetch
            postokay, response = self._fetch(
                url=url, payload=dumps(payload),
                content_type='application/json')

            # Test if we were okay
            if not postokay:
                has_error = True

        return not has_error

    def authenticate(self):
        """
        Logs into and acquires us an authentication token to work with
        """

        if self.token and self.token_expiry > datetime.now():
            # If we're already authenticated and our token is still valid
            self.logger.debug(
                'Already authenticate with token {}'.format(self.token))
            return True

        # If we reach here, we've either expired, or we need to authenticate
        # for the first time.

        # Prepare our payload
        payload = {
            'client_id': self.client_id,
            'client_secret': self.secret,
            'scope': '{graph_url}/{scope}'.format(
                graph_url=self.graph_url,
                scope=self.scope),
            'grant_type': 'client_credentials',
        }

        # Prepare our URL
        url = self.auth_url.format(tenant=self.tenant)

        # A response looks like the following:
        #    {
        #       "token_type": "Bearer",
        #       "expires_in": 3599,
        #       "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSzI1NiIsInNBXBP..."
        #    }
        #
        # Where expires_in defines the number of seconds the key is valid for
        # before it must be renewed.

        # Alternatively, this could happen too...
        #    {
        #      "error": "invalid_scope",
        #      "error_description": "AADSTS70011: Blah... Blah Blah... Blah",
        #      "error_codes": [
        #        70011
        #      ],
        #      "timestamp": "2020-01-09 02:02:12Z",
        #      "trace_id": "255d1aef-8c98-452f-ac51-23d051240864",
        #      "correlation_id": "fb3d2015-bc17-4bb9-bb85-30c5cf1aaaa7"
        #    }

        postokay, response = self._fetch(url=url, payload=payload)
        if not postokay:
            return False

        # Reset our token
        self.token = None

        try:
            # Extract our time from our response and subtrace 10 seconds from
            # it to give us some wiggle/grace people to re-authenticate if we
            # need to
            self.token_expiry = datetime.now() + \
                timedelta(seconds=int(response.get('expires_in')) - 10)

        except (ValueError, AttributeError, TypeError):
            # ValueError: expires_in wasn't an integer
            # TypeError: expires_in was None
            # AttributeError: we could not extract anything from our response
            #                object.
            return False

        # Go ahead and store our token if it's available
        self.token = response.get('access_token')

        # We're authenticated
        return True if self.token else False

    def _fetch(self, url, payload,
               content_type='application/x-www-form-urlencoded'):
        """
        Wrapper to request object

        """

        # Prepare our headers:
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': content_type,
        }

        if self.token:
            # Are we authenticated?
            headers['Authorization'] = 'Bearer ' + self.token

        # Default content response object
        content = {}

        # Some Debug Logging
        self.logger.debug('Office 365 POST URL: {} (cert_verify={})'.format(
            url, self.verify_certificate))
        self.logger.debug('Office 365 Payload: {}' .format(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # fetch function
        try:
            r = requests.post(
                url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code not in (
                    requests.codes.ok, requests.codes.accepted):

                # We had a problem
                status_str = \
                    NotifyOffice365.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Office 365 POST to {}: '
                    '{}error={}.'.format(
                        url,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending Office 365 POST to {}: '.
                format(url))
            self.logger.debug('Socket Exception: %s' % str(e))

            # Mark our failure
            return (False, content)

        return (True, content)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.cc:
            # Handle our Carbon Copy Addresses
            params['cc'] = ','.join(
                ['{}{}'.format(
                    '' if not self.names.get(e)
                    else '{}:'.format(self.names[e]), e) for e in self.cc])

        if self.bcc:
            # Handle our Blind Carbon Copy Addresses
            params['bcc'] = ','.join(
                ['{}{}'.format(
                    '' if not self.names.get(e)
                    else '{}:'.format(self.names[e]), e) for e in self.bcc])

        return '{schema}://{tenant}:{email}/{client_id}/{secret}' \
            '/{targets}/?{params}'.format(
                schema=self.secure_protocol,
                tenant=self.pprint(self.tenant, privacy, safe=''),
                # email does not need to be escaped because it should
                # already be a valid host and username at this point
                email=self.email,
                client_id=self.pprint(self.client_id, privacy, safe=''),
                secret=self.pprint(
                    self.secret, privacy, mode=PrivacyMode.Secret,
                    safe=''),
                targets='/'.join(
                    [NotifyOffice365.quote('{}{}'.format(
                        '' if not e[0] else '{}:'.format(e[0]), e[1]),
                        safe='') for e in self.targets]),
                params=NotifyOffice365.urlencode(params))

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
        entries = NotifyOffice365.split_path(results['fullpath'])

        try:
            # Get our client_id is the first entry on the path
            results['client_id'] = NotifyOffice365.unquote(entries.pop(0))

        except IndexError:
            # no problem, we may get the client_id another way through
            # arguments...
            pass

        # Prepare our target listing
        results['targets'] = list()
        while entries:
            # Pop the last entry
            entry = NotifyOffice365.unquote(entries.pop(-1))

            if is_email(entry):
                # Store our email and move on
                results['targets'].append(entry)
                continue

            # If we reach here, the entry we just popped is part of the secret
            # key, so put it back
            entries.append(NotifyOffice365.quote(entry, safe=''))

            # We're done
            break

        # Initialize our tenant
        results['tenant'] = None

        # Assemble our secret key which is a combination of the host followed
        # by all entries in the full path that follow up until the first email
        results['secret'] = '/'.join(
            [NotifyOffice365.unquote(x) for x in entries])

        # Assemble our client id from the user@hostname
        if results['password']:
            results['email'] = '{}@{}'.format(
                NotifyOffice365.unquote(results['password']),
                NotifyOffice365.unquote(results['host']),
            )
            # Update our tenant
            results['tenant'] = NotifyOffice365.unquote(results['user'])

        else:
            # No tenant specified..
            results['email'] = '{}@{}'.format(
                NotifyOffice365.unquote(results['user']),
                NotifyOffice365.unquote(results['host']),
            )

        # OAuth2 ID
        if 'oauth_id' in results['qsd'] and len(results['qsd']['oauth_id']):
            # Extract the API Key from an argument
            results['client_id'] = \
                NotifyOffice365.unquote(results['qsd']['oauth_id'])

        # OAuth2 Secret
        if 'oauth_secret' in results['qsd'] and \
                len(results['qsd']['oauth_secret']):
            # Extract the API Secret from an argument
            results['secret'] = \
                NotifyOffice365.unquote(results['qsd']['oauth_secret'])

        # Tenant
        if 'from' in results['qsd'] and \
                len(results['qsd']['from']):
            # Extract the sending account's information
            results['email'] = \
                NotifyOffice365.unquote(results['qsd']['from'])

        # Tenant
        if 'tenant' in results['qsd'] and \
                len(results['qsd']['tenant']):
            # Extract the Tenant from the argument
            results['tenant'] = \
                NotifyOffice365.unquote(results['qsd']['tenant'])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyOffice365.parse_list(results['qsd']['to'])

        # Handle Carbon Copy Addresses
        if 'cc' in results['qsd'] and len(results['qsd']['cc']):
            results['cc'] = results['qsd']['cc']

        # Handle Blind Carbon Copy Addresses
        if 'bcc' in results['qsd'] and len(results['qsd']['bcc']):
            results['bcc'] = results['qsd']['bcc']

        return results
