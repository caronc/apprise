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

# API Details:
# https://docs.microsoft.com/en-us/previous-versions/office/\
#        office-365-api/?redirectedfrom=MSDN

# Information on sending an email:
# https://docs.microsoft.com/en-us/graph/api/user-sendmail\
#       ?view=graph-rest-1.0&tabs=http
#
# Note: One must set up Application Permissions (not Delegated Permissions)
#       - Scopes required: Mail.Send
#       - For Large Attachments: Mail.ReadWrite
#       - For Email Lookups: User.Read.All
#
import requests
import json
from uuid import uuid4
from datetime import datetime
from datetime import timedelta
from .base import NotifyBase
from .. import exception
from ..url import PrivacyMode
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils.parse import is_email, parse_emails, validate_regex
from ..locale import gettext_lazy as _
from ..common import PersistentStoreMode


class NotifyOffice365(NotifyBase):
    """
    A wrapper for Office 365 Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Office 365'

    # The services URL
    service_url = 'https://office.com/'

    # The default protocol
    secure_protocol = ('azure', 'o365')

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_office365'

    # URL to Microsoft Graph Server
    graph_url = 'https://graph.microsoft.com'

    # Authentication URL
    auth_url = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'

    # Support attachments
    attachment_support = True

    # Our default is to no not use persistent storage beyond in-memory
    # reference
    storage_mode = PersistentStoreMode.AUTO

    # the maximum size an attachment can be for it to be allowed to be
    # uploaded inline with the current email going out (one http post)
    # Anything larger than this and a second PUT request is required to
    # the outlook server to post the content through reference.
    # Currently (as of 2025.10.06) this was documented to be 3MB
    outlook_attachment_inline_max = 3145728

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
        # Send as user (only supported method)
        '{schema}://{source}/{tenant}/{client_id}/{secret}',
        '{schema}://{source}/{tenant}/{client_id}/{secret}/{targets}',
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
        'source': {
            'name': _('Account Email or Object ID'),
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
        'oauth_id': {
            'alias_of': 'client_id',
        },
        'oauth_secret': {
            'alias_of': 'secret',
        },
    })

    def __init__(self, tenant, client_id, secret, source=None,
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

        # Store our email/ObjectID Source
        self.source = source

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
            result = is_email(self.source)
            if not result:
                self.logger.warning('No Target Office 365 Email Detected')

            else:
                # If our target email list is empty we want to add ourselves to
                # it
                self.targets.append((False, self.source))

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

        # Our email source; we detect this if the source is an ObjectID
        # If it is unknown we set this to None
        # User is the email associated with the account
        self.from_email = self.store.get('from')
        result = is_email(self.source)
        if result:
            self.from_email = result['full_email']
            self.from_name = \
                result['name'] or self.store.get('name')

        else:
            self.from_name = self.store.get('name')

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
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

        if self.from_email is None:
            if not self.authenticate():
                # We could not authenticate ourselves; we're done
                return False

            # Acquire our from_email
            url = "https://graph.microsoft.com/v1.0/users/{}".format(
                self.source)
            postokay, response = self._fetch(url=url, method='GET')
            if not postokay:
                self.logger.warning(
                    'Could not acquire From email address; ensure '
                    '"User.Read.All" Application scope is set!')

            else:  # Acquire our from_email (if possible)
                from_email = \
                    response.get("mail") or response.get("userPrincipalName")
                result = is_email(from_email)
                if not result:
                    self.logger.warning(
                        'Could not get From email from the Azure endpoint.')

                    # Prevent re-occuring upstream fetches for info that isn't
                    # there
                    self.from_email = False

                else:
                    # Store our email for future reference
                    self.from_email = result['full_email']
                    self.store.set('from', result['full_email'])

                    self.from_name = response.get("displayName")
                    if self.from_name:
                        self.store.set('name', self.from_name)

        # Setup our Content Type
        content_type = \
            'HTML' if self.notify_format == NotifyFormat.HTML else 'Text'

        # Prepare our payload
        payload = {
            'message': {
                'subject': title,
                'body': {
                    'contentType': content_type,
                    'content': body,
                },
            },
            # Below takes a string (not bool) of either 'true' or 'false'
            'saveToSentItems': 'true'
        }

        if self.from_email:
            # Apply from email if it is known
            payload['message'].update({
                'from': {
                    "emailAddress": {
                        "address": self.from_email,
                        "name": self.from_name or self.app_id,
                    }
                },
            })

        # Create a copy of the email list
        emails = list(self.targets)

        # Define our URL to post to
        url = '{graph_url}/v1.0/users/{userid}/sendMail'.format(
            graph_url=self.graph_url,
            userid=self.source,
        )

        # Prepare our Draft URL
        draft_url = \
            '{graph_url}/v1.0/users/{userid}/messages' \
            .format(
                graph_url=self.graph_url,
                userid=self.source,
            )

        small_attachments = []
        large_attachments = []

        # draft emails
        drafts = []

        if attach and self.attachment_support:
            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access Office 365 attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                if len(attachment) > self.outlook_attachment_inline_max:
                    # Messages larger then xMB need to be uploaded after; a
                    # draft email must be prepared; below is our session
                    large_attachments.append({
                        'obj': attachment,
                        'name': attachment.name
                        if attachment.name else f'file{no:03}.dat',
                    })
                    continue

                try:
                    # Prepare our Attachment in Base64
                    small_attachments.append({
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        # Name of the attachment (as it should appear in email)
                        "name": attachment.name
                        if attachment.name else f'file{no:03}.dat',
                        # MIME type of the attachment
                        "contentType": "attachment.mimetype",
                        # Base64 Content
                        "contentBytes": attachment.base64(),

                    })

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access Office 365 attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                self.logger.debug(
                    'Appending Office 365 attachment {}'.format(
                        attachment.url(privacy=True)))

        if small_attachments:
            # Store Attachments
            payload['message']['attachments'] = small_attachments

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
            payload['message']['toRecipients'] = [{
                'emailAddress': {
                    'address': to_addr
                }
            }]
            if to_name:
                # Apply our To Name
                payload['message']['toRecipients'][0]['emailAddress']['name'] \
                    = to_name

            self.logger.debug('{}Email To: {}'.format(
                'Draft' if large_attachments else '', to_addr))

            if cc:
                # Prepare our CC list
                payload['message']['ccRecipients'] = []
                for addr in cc:
                    _payload = {'address': addr}
                    if self.names.get(addr):
                        _payload['name'] = self.names[addr]

                    # Store our address in our payload
                    payload['message']['ccRecipients']\
                        .append({'emailAddress': _payload})

                self.logger.debug('{}Email Cc: {}'.format(
                    'Draft' if large_attachments else '', ', '.join(
                        ['{}{}'.format(
                            '' if self.names.get(e)
                            else '{}: '.format(
                                self.names[e]), e) for e in cc])))

            if bcc:
                # Prepare our CC list
                payload['message']['bccRecipients'] = []
                for addr in bcc:
                    _payload = {'address': addr}
                    if self.names.get(addr):
                        _payload['name'] = self.names[addr]

                    # Store our address in our payload
                    payload['message']['bccRecipients']\
                        .append({'emailAddress': _payload})

                self.logger.debug('{}Email Bcc: {}'.format(
                    'Draft' if large_attachments else '', ', '.join(
                        ['{}{}'.format(
                            '' if self.names.get(e)
                            else '{}: '.format(
                                self.names[e]), e) for e in bcc])))

            # Perform upstream post
            postokay, response = self._fetch(
                url=url if not large_attachments
                else draft_url, payload=payload)

            # Test if we were okay
            if not postokay:
                has_error = True

            elif large_attachments:
                # We have large attachments now to upload and associate with
                # our message. We need to prepare a draft message; acquire
                # the message-id associated with it and then attach the file
                # via this means.

                # Acquire our Draft ID to work with
                message_id = response.get("id")
                if not message_id:
                    self.logger.warning(
                        'Email Draft ID could not be retrieved')
                    has_error = True
                    continue

                self.logger.debug('Email Draft ID: {}'.format(message_id))
                # In future, the below could probably be called via async
                has_attach_error = False
                for attachment in large_attachments:
                    if not self.upload_attachment(
                            attachment['obj'], message_id, attachment['name']):
                        self.logger.warning(
                            'Could not prepare attachment session for %s',
                            attachment['name'])

                        has_error = True
                        has_attach_error = True
                        # Take early exit
                        break

                if has_attach_error:
                    continue

                # Send off our draft
                attach_url = \
                    "https://graph.microsoft.com/v1.0/users/" \
                    "{}/messages/{}/send"

                attach_url = attach_url.format(
                    self.source,
                    message_id,
                )

                # Trigger our send
                postokay, response = self._fetch(url=url)
                if not postokay:
                    self.logger.warning(
                        'Could not send drafted email id: {} ', message_id)
                    has_error = True
                    continue

        # Memory management
        del small_attachments
        del large_attachments
        del drafts

        return not has_error

    def upload_attachment(self, attachment, message_id, name=None):
        """
        Uploads an attachment to a session
        """

        # Perform some simple error checking
        if not attachment:
            # We could not access the attachment
            self.logger.error(
                'Could not access Office 365 attachment {}.'.format(
                    attachment.url(privacy=True)))
            return False

        # Our Session URL
        url = \
            '{graph_url}/v1.0/users/{userid}/message/{message_id}' \
            .format(
                graph_url=self.graph_url,
                userid=self.source,
                message_id=message_id,
            ) + '/attachments/createUploadSession'

        file_size = len(attachment)

        payload = {
            "AttachmentItem": {
                "attachmentType": "file",
                "name": name if name else (
                    attachment.name
                    if attachment.name else '{}.dat'.format(str(uuid4()))),
                # MIME type of the attachment
                "contentType": attachment.mimetype,
                "size": file_size,
            }
        }

        if not self.authenticate():
            # We could not authenticate ourselves; we're done
            return False

        # Get our Upload URL
        postokay, response = self._fetch(url, payload)
        if not postokay:
            return False

        upload_url = response.get('uploadUrl')
        if not upload_url:
            return False

        start_byte = 0
        postokay = False
        response = None

        for chunk in attachment.chunk():
            end_byte = start_byte + len(chunk) - 1

            # Define headers for this chunk
            headers = {
                'User-Agent': self.app_id,
                'Content-Length': str(len(chunk)),
                'Content-Range':
                f'bytes {start_byte}-{end_byte}/{file_size}'
            }

            # Upload the chunk
            postokay, response = self._fetch(
                upload_url, chunk, headers=headers, content_type=None,
                method='PUT')
            if not postokay:
                return False

        # Return our Upload URL
        return postokay

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
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.secret,
            'scope': '{graph_url}/{scope}'.format(
                graph_url=self.graph_url,
                scope=self.scope),
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

        postokay, response = self._fetch(
            url=url, payload=payload,
            content_type='application/x-www-form-urlencoded')
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

    def _fetch(self, url, payload=None, headers=None,
               content_type='application/json', method='POST'):
        """
        Wrapper to request object

        """

        # Prepare our headers:
        if not headers:
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
        self.logger.debug('Office 365 %s URL: {} (cert_verify={})'.format(
            url, self.verify_certificate), method)
        self.logger.debug('Office 365 Payload: {}' .format(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # fetch function
        req = requests.post if method == 'POST' else (
            requests.put if method == 'PUT' else requests.get)

        try:
            r = req(
                url,
                data=json.dumps(payload)
                if content_type and content_type.endswith('/json')
                else payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code not in (
                    requests.codes.ok, requests.codes.created,
                    requests.codes.accepted):

                # We had a problem
                status_str = \
                    NotifyOffice365.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Office 365 %s to {}: '
                    '{}error={}.'.format(
                        url,
                        ', ' if status_str else '',
                        r.status_code), method)

                # A Response could look like this if a Scope element was not
                # found:
                # {
                #  "error": {
                #     "code": "MissingClaimType",
                #     "message":"The token is missing the claim type \'oid\'.",
                #     "innerError": {
                #       "oAuthEventOperationId":" 7abe20-339f-4659-9381-38f52",
                #       "oAuthEventcV": "xsOSpAHSHVm3Tp4SNH5oIA.1.1",
                #       "errorUrl": "https://url",
                #       "requestId": "2328ea-ec9e-43a8-80f4-164c",
                #       "date":"2024-12-01T02:03:13"
                #  }}
                # }

                # Error 403; the below is returned if he User.Read.All
                #           Application scope is not set and a lookup is
                #           attempted.
                # {
                #   "error": {
                #     "code": "Authorization_RequestDenied",
                #     "message":
                #        "Insufficient privileges to complete the operation.",
                #     "innerError": {
                #       "date": "2024-12-06T00:15:57",
                #       "request-id":
                #         "48fdb3e7-2f1a-4f45-a5a0-99b8b851278b",
                #         "client-request-id": "48f-2f1a-4f45-a5a0-99b8"
                #     }
                #   }
                # }

                # Another response type (error 415):
                # {
                #  "error": {
                #    "code": "RequestBodyRead",
                #    "message": "A missing or empty content type header was \
                #        found when trying to read a message. The content \
                #        type header is required.",
                #  }
                # }

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))

                # Mark our failure
                return (False, content)

            try:
                content = json.loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

        except requests.RequestException as e:
            self.logger.warning(
                'Exception received when sending Office 365 %s to {}: '.
                format(url), method)
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
            self.secure_protocol[0], self.source, self.tenant, self.client_id,
            self.secret,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Extend our parameters
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

        return '{schema}://{source}/{tenant}/{client_id}/{secret}' \
            '/{targets}/?{params}'.format(
                schema=self.secure_protocol[0],
                tenant=self.pprint(self.tenant, privacy, safe=''),
                # email does not need to be escaped because it should
                # already be a valid host and username at this point
                source=self.source,
                client_id=self.pprint(self.client_id, privacy, safe=''),
                secret=self.pprint(
                    self.secret, privacy, mode=PrivacyMode.Secret,
                    safe=''),
                targets='/'.join(
                    [NotifyOffice365.quote('{}{}'.format(
                        '' if not e[0] else '{}:'.format(e[0]), e[1]),
                        safe='@') for e in self.targets]),
                params=NotifyOffice365.urlencode(params))

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
        entries = NotifyOffice365.split_path(results['fullpath'])

        # Initialize our tenant
        results['tenant'] = None

        # Initialize our email
        results['email'] = None

        # From Email
        if 'from' in results['qsd'] and \
                len(results['qsd']['from']):
            # Extract the sending account's information
            results['source'] = \
                NotifyOffice365.unquote(results['qsd']['from'])

        # If tenant is occupied, then the user defined makes up our source
        elif results['user']:
            results['source'] = '{}@{}'.format(
                NotifyOffice365.unquote(results['user']),
                NotifyOffice365.unquote(results['host']),
            )

        else:
            # Object ID instead of email
            results['source'] = NotifyOffice365.unquote(results['host'])

        # Tenant
        if 'tenant' in results['qsd'] and len(results['qsd']['tenant']):
            # Extract the Tenant from the argument
            results['tenant'] = \
                NotifyOffice365.unquote(results['qsd']['tenant'])

        elif entries:
            results['tenant'] = NotifyOffice365.unquote(entries.pop(0))

        # OAuth2 ID
        if 'oauth_id' in results['qsd'] and len(results['qsd']['oauth_id']):
            # Extract the API Key from an argument
            results['client_id'] = \
                NotifyOffice365.unquote(results['qsd']['oauth_id'])

        elif entries:
            # Get our client_id is the first entry on the path
            results['client_id'] = NotifyOffice365.unquote(entries.pop(0))

        #
        # Prepare our target listing
        #
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

        # OAuth2 Secret
        if 'oauth_secret' in results['qsd'] and \
                len(results['qsd']['oauth_secret']):
            # Extract the API Secret from an argument
            results['secret'] = \
                NotifyOffice365.unquote(results['qsd']['oauth_secret'])

        else:
            # Assemble our secret key which is a combination of the host
            # followed by all entries in the full path that follow up until
            # the first email
            results['secret'] = '/'.join(
                [NotifyOffice365.unquote(x) for x in entries])

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
