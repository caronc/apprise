# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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

# API Information:
# - https://docs.aws.amazon.com/ses/latest/APIReference/API_SendRawEmail.html
#
# AWS Credentials (access_key and secret_access_key)
# - https://docs.aws.amazon.com/sdk-for-java/v1/developer-guide/\
#       setup-credentials.html
# - https://docs.aws.amazon.com/toolkit-for-eclipse/v1/user-guide/\
#       setup-credentials.html
#
#      Other systems write these credentials to:
#        -  ~/.aws/credentials on Linux, macOS, or Unix
#        -  C:\Users\USERNAME\.aws\credentials on Windows
#
#
#      To get A users access key ID and secret access key
#
#        1. Open the IAM console: https://console.aws.amazon.com/iam/home
#        2. On the navigation menu, choose Users.
#        3. Choose your IAM user name (not the check box).
#        4. Open the Security credentials tab, and then choose:
#             Create Access key - Programmatic access
#        5. To see the new access key, choose Show. Your credentials resemble
#           the following:
#               Access key ID: AKIAIOSFODNN7EXAMPLE
#               Secret access key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
#
#      To download the key pair, choose Download .csv file. Store the keys
#      The account requries this permssion to 'SES v2 : SendEmail' in order to
#      work
#
#      To get the root users account (if you're logged in as that) you can
#      visit: https://console.aws.amazon.com/iam/home#/\
#                 security_credentials$access_key
#
#    This information is vital to work with SES


# To use/test the service, i logged into the portal via:
#       - https://portal.aws.amazon.com
#
# Go to the dashboard of the Amazon SES (Simple Email Service)
#  1. You must have a verified identity; click on that option and create one
#     if you don't already have one. Until it's verified, you won't be able to
#     do the next step.
#  2. From here you'll be able to retrieve your ARN associated with your
#     identity you want Apprise to send emails on behalf. It might look
#     something like:
#          arn:aws:ses:us-east-2:133216123003:identity/user@example.com
#
#  This is your ARN (Amazon Record Name)
#
#

import re
import hmac
import base64
import requests
from hashlib import sha256
from datetime import datetime
from collections import OrderedDict
from xml.etree import ElementTree
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email.header import Header
try:
    # Python v3.x
    from urllib.parse import quote

except ImportError:
    # Python v2.x
    from urllib import quote

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_emails
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _
from ..utils import is_email

# Our Regin Identifier
# support us-gov-west-1 syntax as well
IS_REGION = re.compile(
    r'^\s*(?P<country>[a-z]{2})-(?P<area>[a-z-]+?)-(?P<no>[0-9]+)\s*$', re.I)

# Extend HTTP Error Messages
AWS_HTTP_ERROR_MAP = {
    403: 'Unauthorized - Invalid Access/Secret Key Combination.',
}


class NotifySES(NotifyBase):
    """
    A wrapper for AWS SES (Amazon Simple Email Service)
    """

    # The default descriptive name associated with the Notification
    service_name = 'AWS Simple Email Service (SES)'

    # The services URL
    service_url = 'https://aws.amazon.com/ses/'

    # The default secure protocol
    secure_protocol = 'ses'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_ses'

    # AWS is pretty good for handling data load so request limits
    # can occur in much shorter bursts
    request_rate_per_sec = 2.5

    # Default Notify Format
    notify_format = NotifyFormat.HTML

    # Define object templates
    templates = (
        '{schema}://{from_email}/{access_key_id}/{secret_access_key}/'
        '{region}/{targets}',
        '{schema}://{from_email}/{access_key_id}/{secret_access_key}/'
        '{region}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'from_email': {
            'name': _('From Email'),
            'type': 'string',
            'map_to': 'from_addr',
        },
        'access_key_id': {
            'name': _('Access Key ID'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'secret_access_key': {
            'name': _('Secret Access Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'region': {
            'name': _('Region'),
            'type': 'string',
            'regex': (r'^[a-z]{2}-[a-z-]+?-[0-9]+$', 'i'),
            'map_to': 'region_name',
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
        'from': {
            'alias_of': 'from_email',
        },
        'reply': {
            'name': _('Reply To Email'),
            'type': 'string',
            'map_to': 'reply_to',
        },
        'name': {
            'name': _('From Name'),
            'type': 'string',
            'map_to': 'from_name',
        },
        'cc': {
            'name': _('Carbon Copy'),
            'type': 'list:string',
        },
        'bcc': {
            'name': _('Blind Carbon Copy'),
            'type': 'list:string',
        },
        'access': {
            'alias_of': 'access_key_id',
        },
        'secret': {
            'alias_of': 'secret_access_key',
        },
        'region': {
            'alias_of': 'region',
        },
    })

    def __init__(self, access_key_id, secret_access_key, region_name,
                 reply_to=None, from_addr=None, from_name=None, targets=None,
                 cc=None, bcc=None, **kwargs):
        """
        Initialize Notify AWS SES Object
        """
        super(NotifySES, self).__init__(**kwargs)

        # Store our AWS API Access Key
        self.aws_access_key_id = validate_regex(access_key_id)
        if not self.aws_access_key_id:
            msg = 'An invalid AWS Access Key ID was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our AWS API Secret Access key
        self.aws_secret_access_key = validate_regex(secret_access_key)
        if not self.aws_secret_access_key:
            msg = 'An invalid AWS Secret Access Key ' \
                  '({}) was specified.'.format(secret_access_key)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Acquire our AWS Region Name:
        # eg. us-east-1, cn-north-1, us-west-2, ...
        self.aws_region_name = validate_regex(
            region_name, *self.template_tokens['region']['regex'])
        if not self.aws_region_name:
            msg = 'An invalid AWS Region ({}) was specified.'.format(
                region_name)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Acquire Email 'To'
        self.targets = list()

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # For tracking our email -> name lookups
        self.names = {}

        # Set our notify_url based on our region
        self.notify_url = 'https://email.{}.amazonaws.com'\
            .format(self.aws_region_name)

        # AWS Service Details
        self.aws_service_name = 'ses'
        self.aws_canonical_uri = '/'

        # AWS Authentication Details
        self.aws_auth_version = 'AWS4'
        self.aws_auth_algorithm = 'AWS4-HMAC-SHA256'
        self.aws_auth_request = 'aws4_request'

        # Get our From username (if specified)
        self.from_name = from_name

        if from_addr:
            self.from_addr = from_addr

        else:
            # Get our from email address
            self.from_addr = '{user}@{host}'.format(
                user=self.user, host=self.host) if self.user else None

        if not (self.from_addr and is_email(self.from_addr)):
            msg = 'An invalid AWS From ({}) was specified.'.format(
                '{user}@{host}'.format(user=self.user, host=self.host))
            self.logger.warning(msg)
            raise TypeError(msg)

        self.reply_to = None
        if reply_to:
            result = is_email(reply_to)
            if not result:
                msg = 'An invalid AWS Reply To ({}) was specified.'.format(
                    '{user}@{host}'.format(user=self.user, host=self.host))
                self.logger.warning(msg)
                raise TypeError(msg)

            self.reply_to = (
                result['name'] if result['name'] else False,
                result['full_email'])

        if targets:
            # Validate recipients (to:) and drop bad ones:
            for recipient in parse_emails(targets):
                result = is_email(recipient)
                if result:
                    self.targets.append(
                        (result['name'] if result['name'] else False,
                            result['full_email']))
                    continue

                self.logger.warning(
                    'Dropped invalid To email '
                    '({}) specified.'.format(recipient),
                )

        else:
            # If our target email list is empty we want to add ourselves to it
            self.targets.append(
                (self.from_name if self.from_name else False, self.from_addr))

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

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        wrapper to send_notification since we can alert more then one channel
        """

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                'There are no SES email recipients to notify')
            return False

        # error tracking (used for function return)
        has_error = False

        # Initialize our default from name
        from_name = self.from_name if self.from_name \
            else self.reply_to[0] if self.reply_to and \
            self.reply_to[0] else self.app_desc

        reply_to = (
            from_name, self.from_addr
            if not self.reply_to else self.reply_to[1])

        # Create a copy of the targets list
        emails = list(self.targets)
        while len(emails):
            # Get our email to notify
            to_name, to_addr = emails.pop(0)

            # Strip target out of cc list if in To or Bcc
            cc = (self.cc - self.bcc - set([to_addr]))

            # Strip target out of bcc list if in To
            bcc = (self.bcc - set([to_addr]))

            try:
                # Format our cc addresses to support the Name field
                cc = [formataddr(
                    (self.names.get(addr, False), addr), charset='utf-8')
                    for addr in cc]

                # Format our bcc addresses to support the Name field
                bcc = [formataddr(
                    (self.names.get(addr, False), addr), charset='utf-8')
                    for addr in bcc]

            except TypeError:
                # Python v2.x Support (no charset keyword)
                # Format our cc addresses to support the Name field
                cc = [formataddr(  # pragma: no branch
                    (self.names.get(addr, False), addr)) for addr in cc]

                # Format our bcc addresses to support the Name field
                bcc = [formataddr(  # pragma: no branch
                    (self.names.get(addr, False), addr)) for addr in bcc]

            self.logger.debug('Email From: {} <{}>'.format(
                quote(reply_to[0], ' '),
                quote(reply_to[1], '@ ')))

            self.logger.debug('Email To: {}'.format(to_addr))
            if cc:
                self.logger.debug('Email Cc: {}'.format(', '.join(cc)))
            if bcc:
                self.logger.debug('Email Bcc: {}'.format(', '.join(bcc)))

            # Prepare Email Message
            if self.notify_format == NotifyFormat.HTML:
                content = MIMEText(body, 'html', 'utf-8')

            else:
                content = MIMEText(body, 'plain', 'utf-8')

            # Create a Multipart container if there is an attachment
            base = MIMEMultipart() if attach else content

            base['Subject'] = Header(title, 'utf-8')
            try:
                base['From'] = formataddr(
                    (from_name if from_name else False, self.from_addr),
                    charset='utf-8')
                base['To'] = formataddr((to_name, to_addr), charset='utf-8')
                if reply_to[1] != self.from_addr:
                    base['Reply-To'] = formataddr(reply_to, charset='utf-8')

            except TypeError:
                # Python v2.x Support (no charset keyword)
                base['From'] = formataddr(
                    (from_name if from_name else False, self.from_addr))
                base['To'] = formataddr((to_name, to_addr))
                if reply_to[1] != self.from_addr:
                    base['Reply-To'] = formataddr(reply_to)

            base['Cc'] = ','.join(cc)
            base['Date'] = \
                datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
            base['X-Application'] = self.app_id

            if attach:
                # First attach our body to our content as the first element
                base.attach(content)

                # Now store our attachments
                for attachment in attach:
                    if not attachment:
                        # We could not load the attachment; take an early
                        # exit since this isn't what the end user wanted

                        # We could not access the attachment
                        self.logger.error(
                            'Could not access attachment {}.'.format(
                                attachment.url(privacy=True)))

                        return False

                    self.logger.debug(
                        'Preparing Email attachment {}'.format(
                            attachment.url(privacy=True)))

                    with open(attachment.path, "rb") as abody:
                        app = MIMEApplication(abody.read())
                        app.set_type(attachment.mimetype)

                        app.add_header(
                            'Content-Disposition',
                            'attachment; filename="{}"'.format(
                                Header(attachment.name, 'utf-8')),
                        )

                        base.attach(app)

            # Prepare our payload object
            payload = {
                'Action': 'SendRawEmail',
                'Version': '2010-12-01',
                'RawMessage.Data': base64.b64encode(
                    base.as_string().encode('utf-8')).decode('utf-8')
            }

            for no, email in enumerate(([to_addr] + bcc + cc), start=1):
                payload['Destinations.member.{}'.format(no)] = email

            # Specify from address
            payload['Source'] = '{} <{}>'.format(
                quote(from_name, ' '),
                quote(self.from_addr, '@ '))

            (result, response) = self._post(payload=payload, to=to_addr)
            if not result:
                # Mark our failure
                has_error = True
                continue

        return not has_error

    def _post(self, payload, to):
        """
        Wrapper to request.post() to manage it's response better and make
        the send() function cleaner and easier to maintain.

        This function returns True if the _post was successful and False
        if it wasn't.
        """

        # Always call throttle before any remote server i/o is made; for AWS
        # time plays a huge factor in the headers being sent with the payload.
        # So for AWS (SES) requests we must throttle before they're generated
        # and not directly before the i/o call like other notification
        # services do.
        self.throttle()

        # Convert our payload from a dict() into a urlencoded string
        payload = NotifySES.urlencode(payload)

        # Prepare our Notification URL
        # Prepare our AWS Headers based on our payload
        headers = self.aws_prepare_request(payload)

        self.logger.debug('AWS SES POST URL: %s (cert_verify=%r)' % (
            self.notify_url, self.verify_certificate,
        ))
        self.logger.debug('AWS SES Payload (%d bytes)', len(payload))

        try:
            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifySES.http_response_code_lookup(
                        r.status_code, AWS_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send AWS SES notification to {}: '
                    '{}{}error={}.'.format(
                        to,
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                return (False, NotifySES.aws_response_to_dict(r.text))

            else:
                self.logger.info(
                    'Sent AWS SES notification to "%s".' % (to))

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred sending AWS SES '
                'notification to "%s".' % (to),
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            return (False, NotifySES.aws_response_to_dict(None))

        return (True, NotifySES.aws_response_to_dict(r.text))

    def aws_prepare_request(self, payload, reference=None):
        """
        Takes the intended payload and returns the headers for it.

        The payload is presumed to have been already urlencoded()

        """

        # Define our AWS SES header
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',

            # Populated below
            'Content-Length': 0,
            'Authorization': None,
            'X-Amz-Date': None,
        }

        # Get a reference time (used for header construction)
        reference = datetime.utcnow()

        # Provide Content-Length
        headers['Content-Length'] = str(len(payload))

        # Amazon Date Format
        amzdate = reference.strftime('%Y%m%dT%H%M%SZ')
        headers['X-Amz-Date'] = amzdate

        # Credential Scope
        scope = '{date}/{region}/{service}/{request}'.format(
            date=reference.strftime('%Y%m%d'),
            region=self.aws_region_name,
            service=self.aws_service_name,
            request=self.aws_auth_request,
        )

        # Similar to headers; but a subset.  keys must be lowercase
        signed_headers = OrderedDict([
            ('content-type', headers['Content-Type']),
            ('host', 'email.{region}.amazonaws.com'.format(
                region=self.aws_region_name)),
            ('x-amz-date', headers['X-Amz-Date']),
        ])

        #
        # Build Canonical Request Object
        #
        canonical_request = '\n'.join([
            # Method
            u'POST',

            # URL
            self.aws_canonical_uri,

            # Query String (none set for POST)
            '',

            # Header Content (must include \n at end!)
            # All entries except characters in amazon date must be
            # lowercase
            '\n'.join(['%s:%s' % (k, v)
                      for k, v in signed_headers.items()]) + '\n',

            # Header Entries (in same order identified above)
            ';'.join(signed_headers.keys()),

            # Payload
            sha256(payload.encode('utf-8')).hexdigest(),
        ])

        # Prepare Unsigned Signature
        to_sign = '\n'.join([
            self.aws_auth_algorithm,
            amzdate,
            scope,
            sha256(canonical_request.encode('utf-8')).hexdigest(),
        ])

        # Our Authorization header
        headers['Authorization'] = ', '.join([
            '{algorithm} Credential={key}/{scope}'.format(
                algorithm=self.aws_auth_algorithm,
                key=self.aws_access_key_id,
                scope=scope,
            ),
            'SignedHeaders={signed_headers}'.format(
                signed_headers=';'.join(signed_headers.keys()),
            ),
            'Signature={signature}'.format(
                signature=self.aws_auth_signature(to_sign, reference)
            ),
        ])

        return headers

    def aws_auth_signature(self, to_sign, reference):
        """
        Generates a AWS v4 signature based on provided payload
        which should be in the form of a string.
        """

        def _sign(key, msg, to_hex=False):
            """
            Perform AWS Signing
            """
            if to_hex:
                return hmac.new(key, msg.encode('utf-8'), sha256).hexdigest()
            return hmac.new(key, msg.encode('utf-8'), sha256).digest()

        _date = _sign((
            self.aws_auth_version +
            self.aws_secret_access_key).encode('utf-8'),
            reference.strftime('%Y%m%d'))

        _region = _sign(_date, self.aws_region_name)
        _service = _sign(_region, self.aws_service_name)
        _signed = _sign(_service, self.aws_auth_request)
        return _sign(_signed, to_sign, to_hex=True)

    @staticmethod
    def aws_response_to_dict(aws_response):
        """
        Takes an AWS Response object as input and returns it as a dictionary
        but not befor extracting out what is useful to us first.

        eg:
          IN:

            <SendRawEmailResponse
                 xmlns="http://ses.amazonaws.com/doc/2010-12-01/">
              <SendRawEmailResult>
                <MessageId>
                   010f017d87656ee2-a2ea291f-79ea-
                   44f3-9d25-00d041de3007-000000</MessageId>
              </SendRawEmailResult>
              <ResponseMetadata>
                <RequestId>7abb454e-904b-4e46-a23c-2f4d2fc127a6</RequestId>
              </ResponseMetadata>
            </SendRawEmailResponse>

          OUT:
           {
             'type': 'SendRawEmailResponse',
              'message_id': '010f017d87656ee2-a2ea291f-79ea-
                             44f3-9d25-00d041de3007-000000',
              'request_id': '7abb454e-904b-4e46-a23c-2f4d2fc127a6',
           }
        """

        # Define ourselves a set of directives we want to keep if found and
        # then identify the value we want to map them to in our response
        # object
        aws_keep_map = {
            'RequestId': 'request_id',
            'MessageId': 'message_id',

            # Error Message Handling
            'Type': 'error_type',
            'Code': 'error_code',
            'Message': 'error_message',
        }

        # A default response object that we'll manipulate as we pull more data
        # from our AWS Response object
        response = {
            'type': None,
            'request_id': None,
            'message_id': None,
        }

        try:
            # we build our tree, but not before first eliminating any
            # reference to namespacing (if present) as it makes parsing
            # the tree so much easier.
            root = ElementTree.fromstring(
                re.sub(' xmlns="[^"]+"', '', aws_response, count=1))

            # Store our response tag object name
            response['type'] = str(root.tag)

            def _xml_iter(root, response):
                if len(root) > 0:
                    for child in root:
                        # use recursion to parse everything
                        _xml_iter(child, response)

                elif root.tag in aws_keep_map.keys():
                    response[aws_keep_map[root.tag]] = (root.text).strip()

            # Recursivly iterate over our AWS Response to extract the
            # fields we're interested in in efforts to populate our response
            # object.
            _xml_iter(root, response)

        except (ElementTree.ParseError, TypeError):
            # bad data just causes us to generate a bad response
            pass

        return response

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Acquire any global URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.from_name is not None:
            # from_name specified; pass it back on the url
            params['name'] = self.from_name

        if self.cc:
            # Handle our Carbon Copy Addresses
            params['cc'] = ','.join(
                ['{}{}'.format(
                    '' if not e not in self.names
                    else '{}:'.format(self.names[e]), e) for e in self.cc])

        if self.bcc:
            # Handle our Blind Carbon Copy Addresses
            params['bcc'] = ','.join(self.bcc)

        if self.reply_to:
            # Handle our reply to address
            params['reply'] = '{} <{}>'.format(*self.reply_to) \
                if self.reply_to[0] else self.reply_to[1]

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1
                 and self.targets[0][1] == self.from_addr)

        return '{schema}://{from_addr}/{key_id}/{key_secret}/{region}/' \
            '{targets}/?{params}'.format(
                schema=self.secure_protocol,
                from_addr=NotifySES.quote(self.from_addr, safe='@'),
                key_id=self.pprint(self.aws_access_key_id, privacy, safe=''),
                key_secret=self.pprint(
                    self.aws_secret_access_key, privacy,
                    mode=PrivacyMode.Secret, safe=''),
                region=NotifySES.quote(self.aws_region_name, safe=''),
                targets='' if not has_targets else '/'.join(
                    [NotifySES.quote('{}{}'.format(
                        '' if not e[0] else '{}:'.format(e[0]), e[1]),
                        safe='') for e in self.targets]),
                params=NotifySES.urlencode(params),
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

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        entries = NotifySES.split_path(results['fullpath'])

        # The AWS Access Key ID is stored in the first entry
        access_key_id = entries.pop(0) if entries else None

        # Our AWS Access Key Secret contains slashes in it which unfortunately
        # means it is of variable length after the hostname.  Since we require
        # that the user provides the region code, we intentionally use this
        # as our delimiter to detect where our Secret is.
        secret_access_key = None
        region_name = None

        # We need to iterate over each entry in the fullpath and find our
        # region. Once we get there we stop and build our secret from our
        # accumulated data.
        secret_access_key_parts = list()

        # Section 1: Get Region and Access Secret
        index = 0
        for index, entry in enumerate(entries, start=1):

            # Are we at the region yet?
            result = IS_REGION.match(entry)
            if result:
                # Ensure region is nicely formatted
                region_name = "{country}-{area}-{no}".format(
                    country=result.group('country').lower(),
                    area=result.group('area').lower(),
                    no=result.group('no'),
                )

                # We're done with Section 1 of our url (the credentials)
                break

            elif is_email(entry):
                # We're done with Section 1 of our url (the credentials)
                index -= 1
                break

            # Store our secret parts
            secret_access_key_parts.append(entry)

        # Prepare our Secret Access Key
        secret_access_key = '/'.join(secret_access_key_parts) \
            if secret_access_key_parts else None

        # Section 2: Get our Recipients (basically all remaining entries)
        results['targets'] = entries[index:]

        if 'name' in results['qsd'] and len(results['qsd']['name']):
            # Extract from name to associate with from address
            results['from_name'] = \
                NotifySES.unquote(results['qsd']['name'])

        # Handle 'to' email address
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'].append(results['qsd']['to'])

        # Handle Carbon Copy Addresses
        if 'cc' in results['qsd'] and len(results['qsd']['cc']):
            results['cc'] = NotifySES.parse_list(results['qsd']['cc'])

        # Handle Blind Carbon Copy Addresses
        if 'bcc' in results['qsd'] and len(results['qsd']['bcc']):
            results['bcc'] = NotifySES.parse_list(results['qsd']['bcc'])

        # Handle From Address handling
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            results['from_addr'] = \
                NotifySES.unquote(results['qsd']['from'])

        # Handle Reply To Address
        if 'reply' in results['qsd'] and len(results['qsd']['reply']):
            results['reply_to'] = \
                NotifySES.unquote(results['qsd']['reply'])

        # Handle secret_access_key over-ride
        if 'secret' in results['qsd'] and len(results['qsd']['secret']):
            results['secret_access_key'] = \
                NotifySES.unquote(results['qsd']['secret'])
        else:
            results['secret_access_key'] = secret_access_key

        # Handle access key id over-ride
        if 'access' in results['qsd'] and len(results['qsd']['access']):
            results['access_key_id'] = \
                NotifySES.unquote(results['qsd']['access'])
        else:
            results['access_key_id'] = access_key_id

        # Handle region name id over-ride
        if 'region' in results['qsd'] and len(results['qsd']['region']):
            results['region_name'] = \
                NotifySES.unquote(results['qsd']['region'])
        else:
            results['region_name'] = region_name

        # Return our result set
        return results
