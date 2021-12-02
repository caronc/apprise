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

# API Information:
# - https://docs.aws.amazon.com/ses/latest/APIReference-V2/API_SendEmail.html
#
import re
import hmac
import requests
from hashlib import sha256
from datetime import datetime
from collections import OrderedDict
from xml.etree import ElementTree
from itertools import chain
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email.header import Header

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_emails
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _
from ..utils import is_email

# Because our AWS Access Key Secret contains slashes, we actually use the
# region as a delimiter. This is a bit hacky; but it's much easier than having
# users of this product search though this Access Key Secret and escape all
# of the forward slashes!
IS_REGION = re.compile(
    r'^\s*(?P<country>[a-z]{2})-(?P<area>[a-z]+)-(?P<no>[0-9]+)\s*$', re.I)

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

    # A batch size for bulk email handling
    default_batch_size = 2000

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://{user}@{host}/{access_key_id}/{secret_access_key}{region}/{targets}',
        #           ^^^^^^^^^^^^
        # Amazon requires that the sender email be validated
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('User Name'),
            'type': 'string',
            'required': True,
        },
        'host': {
            'name': _('Domain'),
            'type': 'string',
            'required': True,
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
            'required': True,
            'regex': (r'^[a-z]{2}-[a-z]+-[0-9]+$', 'i'),
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
        'cc': {
            'name': _('Carbon Copy'),
            'type': 'list:string',
        },
        'bcc': {
            'name': _('Blind Carbon Copy'),
            'type': 'list:string',
        },
        'batch': {
            'name': _('Batch Mode'),
            'type': 'bool',
            'default': False,
        },
    })

    def __init__(self, access_key_id, secret_access_key, region_name,
                 from_name=None, targets=None, cc=None, bcc=None, batch=False,
                 **kwargs):
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

        # Prepare Batch Mode Flag
        self.batch = batch

        # Acquire Email 'To'
        self.targets = list()

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Set our notify_url based on our region
        self.notify_url = 'https://email.{}.amazonaws.com/'\
            .format(self.aws_region_name)

        # AWS Service Details
        self.aws_service_name = 'ses'
        self.aws_canonical_uri = '/v2/email/outbound-emails'

        # AWS Authentication Details
        self.aws_auth_version = 'AWS4'
        self.aws_auth_algorithm = 'AWS4-HMAC-SHA256'
        self.aws_auth_request = 'aws4_request'

        # Get our From username (if specified)
        self.from_name = from_name

        # Get our from email address
        self.from_addr = '{user}@{host}'.format(user=self.user, host=self.host)

        if not is_email(self.from_addr):
            # Parse Source domain based on from_addr
            msg = 'Invalid ~From~ email format: {}'.format(self.from_addr)
            self.logger.warning(msg)
            raise TypeError(msg)

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

        try:
            reply_to = formataddr(
                (self.from_name if self.from_name else False,
                 self.from_addr), charset='utf-8')

        except TypeError:
            # Python v2.x Support (no charset keyword)
            # Format our cc addresses to support the Name field
            reply_to = formataddr(
                (self.from_name if self.from_name else False,
                 self.from_addr))

        # Initialize our default from name
        from_name = self.from_name if self.from_name else self.app_desc

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

            self.logger.debug(
                'Email From: {} <{}>'.format(from_name, self.from_addr))
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

            base = MIMEMultipart() if attach else content

            # Apply any provided custom headers
            for k, v in self.headers.items():
                base[k] = Header(v, 'utf-8')

            base['Subject'] = Header(title, 'utf-8')
            try:
                base['From'] = formataddr(
                    (from_name if from_name else False, self.from_addr),
                    charset='utf-8')
                base['To'] = formataddr((to_name, to_addr), charset='utf-8')

            except TypeError:
                # Python v2.x Support (no charset keyword)
                base['From'] = formataddr(
                    (from_name if from_name else False, self.from_addr))
                base['To'] = formataddr((to_name, to_addr))

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
                        app = MIMEApplication(
                            abody.read(), attachment.mimetype)

                        app.add_header(
                            'Content-Disposition',
                            'attachment; filename="{}"'.format(
                                Header(attachment.name, 'utf-8')),
                        )

                        base.attach(app)

            # Prepare our payload object
            payload = {
                'Content': {
                    'Raw': {
                        'Data': base.as_string()
                    },
                }
                'Destination': {
                    'BccAddresses': list(bcc),
                    'CcAddresses': list(Cc),
                    'ToAddresses': to_addr,
                },
                'FromEmailAddress': self.from_addr,
            }

            (result, response) = self._post(payload=payload, to=topic)
            if not result:
                # Mark our failure
                has_error = True
                continue

            self.logger.info(
                'Sent Email notification to "{}".'.format(to_addr))

        return not has_error

        # Prepare our payload
        # payload = {
        #     'Body': {},
        #     'Subject': {
        #         'Charset': 'utf-8',
        #         'Data': title if title else 'Apprise Notification',
        #     }
        # }

        # if self.notify_format == NotifyFormat.HTML:
        #     payload['Body']['Html'] = {
        #         'Charset': 'utf-8',
        #         'Data': body,
        #     }

        # else:
        #     payload['Body']['Text'] = {
        #         'Charset': 'utf-8',
        #         'Data': body,
        #     }

        # # Create a copy of the targets list
        # emails = list(self.targets)

        # for index in range(0, len(emails), batch_size):
        #     # Initialize our cc list
        #     cc = (self.cc - self.bcc)

        #     # Initialize our bcc list
        #     bcc = set(self.bcc)

        #     # Initialize our to list
        #     to = list()

        # while len(phone) > 0:

        #     # Get Phone No
        #     no = phone.pop(0)

        #     # Prepare SES Message Payload
        #     payload = {
        #         'Action': u'Publish',
        #         'Message': body,
        #         'Version': u'2010-03-31',
        #         'PhoneNumber': no,
        #     }

        #     (result, _) = self._post(payload=payload, to=no)
        #     if not result:
        #         error_count += 1

        # # Send all our defined topic id's
        # while len(topics):

        #     # Get Topic
        #     topic = topics.pop(0)

        #     # First ensure our topic exists, if it doesn't, it gets created
        #     payload = {
        #         'Action': u'CreateTopic',
        #         'Version': u'2010-03-31',
        #         'Name': topic,
        #     }

        #     (result, response) = self._post(payload=payload, to=topic)
        #     if not result:
        #         error_count += 1
        #         continue

        #     # Get the Amazon Resource Name
        #     topic_arn = response.get('topic_arn')
        #     if not topic_arn:
        #         # Could not acquire our topic; we're done
        #         error_count += 1
        #         continue

        #     # Build our payload now that we know our topic_arn
        #     payload = {
        #         'Action': u'Publish',
        #         'Version': u'2010-03-31',
        #         'TopicArn': topic_arn,
        #         'Message': body,
        #     }

        #     # Send our payload to AWS
        #     (result, _) = self._post(payload=payload, to=topic)
        #     if not result:
        #         error_count += 1

        # return error_count == 0

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

        notify_url = '{}/{}'.format(self.notify_url, self.aws_canonical_uri)
        self.logger.debug('AWS SES POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('AWS SES Payload: %s' % str(payload))

        try:
            r = requests.post(
                notify_url,
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
            ('host', '{service}.{region}.amazonaws.com'.format(
                service=self.aws_service_name,
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

             TODO

          OUT:
           {
              type: 'CreateTopicResponse',
              request_id: '604bef0f-369c-50c5-a7a4-bbd474c83d6a',
              topic_arn: 'arn:aws:sns:us-east-1:000000000000:abcd',
           }
        """

        # Define ourselves a set of directives we want to keep if found and
        # then identify the value we want to map them to in our response
        # object
        aws_keep_map = {
            'RequestId': 'request_id',
            'TopicArn': 'topic_arn',
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

        # Define any URL parameters
        params = {
            'batch': 'yes' if self.batch else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

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

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1
                 and self.targets[0][1] == self.from_addr)

        return '{schema}://{user}@{host}/{key_id}/{key_secret}/{region}/'
            '{targets}/?{params}'.format(
                schema=self.secure_protocol,
                host=self.host,
                user=NotifySES.quote(self.user, safe=''),
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
        results = NotifySES.parse_url(url, verify_host=False)
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
        for i, entry in enumerate(entries):

            # Are we at the region yet?
            result = IS_REGION.match(entry)
            if result:
                # We found our Region; Rebuild our access key secret based on
                # all entries we found prior to this:
                secret_access_key = '/'.join(secret_access_key_parts)

                # Ensure region is nicely formatted
                region_name = "{country}-{area}-{no}".format(
                    country=result.group('country').lower(),
                    area=result.group('area').lower(),
                    no=result.group('no'),
                )

                # Track our index as we'll use this to grab the remaining
                # content in the next Section
                index = i + 1

                # We're done with Section 1
                break

            # Store our secret parts
            secret_access_key_parts.append(entry)

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
            results['cc'] = results['qsd']['cc']

        # Handle Blind Carbon Copy Addresses
        if 'bcc' in results['qsd'] and len(results['qsd']['bcc']):
            results['bcc'] = results['qsd']['bcc']

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifySES.template_args['batch']['default']))

        # Store our other detected data (if at all)
        results['region_name'] = region_name
        results['access_key_id'] = access_key_id
        results['secret_access_key'] = secret_access_key

        # Return our result set
        return results
