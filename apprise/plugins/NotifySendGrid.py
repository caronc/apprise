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
#
# You will need an API Key for this plugin to work.
# From the Settings -> API Keys you can click "Create API Key" if you don't
# have one already. The key must have at least the "Mail Send" permission
# to work.
#
# The schema to use the plugin looks like this:
#    {schema}://{apikey}:{from_email}
#
# Your {from_email} must be comprissed of your Sendgrid Authenticated
# Domain. The same domain must have 'Link Branding' turned on as well or it
# will not work. This can be seen from Settings -> Sender Authentication.

# If you're (SendGrid) verified domain is example.com, then your schema may
# look something like this:

# Simple API Reference:
#  - https://sendgrid.com/docs/API_Reference/Web_API_v3/index.html
#  - https://sendgrid.com/docs/ui/sending-email/\
#       how-to-send-an-email-with-dynamic-transactional-templates/

import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..utils import GET_EMAIL_RE
from ..AppriseLocale import gettext_lazy as _

IS_APIKEY_RE = re.compile(r'^([A-Z0-9._-]+)$', re.I)

# Extend HTTP Error Messages
SENDGRID_HTTP_ERROR_MAP = {
    401: 'Unauthorized - You do not have authorization to make the request.',
    413: 'Payload To Large - The JSON payload you have included in your '
         'request is too large.',
    429: 'Too Many Requests - The number of requests you have made exceeds '
         'SendGrid’s rate limitations.',
}


class NotifySendGrid(NotifyBase):
    """
    A wrapper for Notify SendGrid Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'SendGrid'

    # The services URL
    service_url = 'https://sendgrid.com'

    # The default secure protocol
    secure_protocol = 'sendgrid'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_sendgrid'

    # Default to markdown
    notify_format = NotifyFormat.HTML

    # The default Email API URL to use
    notify_url = 'https://api.sendgrid.com/v3/mail/send'

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.2

    # The default subject to use if one isn't specified.
    default_empty_subject = '<no subject>'

    # Define object templates
    templates = (
        '{schema}://{apikey}:{from_email}',
        '{schema}://{apikey}:{from_email}/{targets}',
    )

    # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'from_email': {
            'name': _('Source Email'),
            'type': 'string',
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
        'template': {
            # Template ID
            # The template ID is 64 characters with one dash (d-uuid)
            'name': _('Template'),
            'type': 'string',
        },
    })

    # Support Template Dynamic Variables (Substitutions)
    template_kwargs = {
        'template_data': {
            'name': _('Template Data'),
            'prefix': '+',
        },
    }

    def __init__(self, apikey, from_email, targets=None, cc=None,
                 bcc=None, template=None, template_data=None, **kwargs):
        """
        Initialize Notify SendGrid Object
        """
        super(NotifySendGrid, self).__init__(**kwargs)

        # The API Key needed to perform all SendMail API i/o
        self.apikey = apikey
        try:
            result = IS_APIKEY_RE.match(self.apikey)
            if not result:
                # let outer exception handle this
                raise TypeError

        except (TypeError, AttributeError):
            msg = 'Invalid API Key specified: {}'.format(self.apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.from_email = from_email
        try:
            result = GET_EMAIL_RE.match(self.from_email)
            if not result:
                # let outer exception handle this
                raise TypeError

        except (TypeError, AttributeError):
            msg = 'Invalid ~From~ email specified: {}'.format(self.from_email)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Acquire Targets (To Emails)
        self.targets = list()

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Now our dynamic template (if defined)
        self.template = template

        # Now our dynamic template data (if defined)
        self.template_data = template_data \
            if isinstance(template_data, dict) else {}

        # Validate recipients (to:) and drop bad ones:
        for recipient in parse_list(targets):

            if GET_EMAIL_RE.match(recipient):
                self.targets.append(recipient)
                continue

            self.logger.warning(
                'Dropped invalid email '
                '({}) specified.'.format(recipient),
            )

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_list(cc):

            if GET_EMAIL_RE.match(recipient):
                self.cc.add(recipient)
                continue

            self.logger.warning(
                'Dropped invalid Carbon Copy email '
                '({}) specified.'.format(recipient),
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_list(bcc):

            if GET_EMAIL_RE.match(recipient):
                self.bcc.add(recipient)
                continue

            self.logger.warning(
                'Dropped invalid Blind Carbon Copy email '
                '({}) specified.'.format(recipient),
            )

        if len(self.targets) == 0:
            # Notify ourselves
            self.targets.append(self.from_email)

        return

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            args['cc'] = ','.join(self.cc)

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            args['bcc'] = ','.join(self.bcc)

        if self.template:
            # Handle our Template ID if if was specified
            args['template'] = self.template

        # Append our template_data into our args
        args.update({'+{}'.format(k): v
                    for k, v in self.template_data.items()})

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1 and self.targets[0] == self.from_email)

        return '{schema}://{apikey}:{from_email}/{targets}?{args}'.format(
            schema=self.secure_protocol,
            apikey=self.quote(self.apikey, safe=''),
            from_email=self.quote(self.from_email, safe='@'),
            targets='' if not has_targets else '/'.join(
                [NotifySendGrid.quote(x, safe='') for x in self.targets]),
            args=NotifySendGrid.urlencode(args),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform SendGrid Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.apikey),
        }

        # error tracking (used for function return)
        has_error = False

        # A Simple Email Payload Template
        _payload = {
            'personalizations': [{
                # Placeholder
                'to': [{'email': None}],
            }],
            'from': {
                'email': self.from_email,
            },
            # A subject is a requirement, so if none is specified we must
            # set a default with at least 1 character or SendGrid will deny
            # our request
            'subject': title if title else self.default_empty_subject,
            'content': [{
                'type': 'text/plain'
                if self.notify_format == NotifyFormat.TEXT else 'text/html',
                'value': body,
            }],
        }

        if self.template:
            _payload['template_id'] = self.template

            if self.template_data:
                _payload['personalizations'][0]['dynamic_template_data'] = \
                    {k: v for k, v in self.template_data.items()}

        targets = list(self.targets)
        while len(targets) > 0:
            target = targets.pop(0)

            # Create a copy of our template
            payload = _payload.copy()

            # the cc, bcc, to field must be unique or SendMail will fail, the
            # below code prepares this by ensuring the target isn't in the cc
            # list or bcc list. It also makes sure the cc list does not contain
            # any of the bcc entries
            cc = (self.cc - self.bcc - set([target]))
            bcc = (self.bcc - set([target]))

            # Set our target
            payload['personalizations'][0]['to'][0]['email'] = target

            if len(cc):
                payload['personalizations'][0]['cc'] = \
                    [{'email': email} for email in cc]

            if len(bcc):
                payload['personalizations'][0]['bcc'] = \
                    [{'email': email} for email in bcc]

            self.logger.debug('SendGrid POST URL: %s (cert_verify=%r)' % (
                self.notify_url, self.verify_certificate,
            ))
            self.logger.debug('SendGrid Payload: %s' % str(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                )
                if r.status_code not in (
                        requests.codes.ok, requests.codes.accepted):
                    # We had a problem
                    status_str = \
                        NotifySendGrid.http_response_code_lookup(
                            r.status_code, SENDGRID_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send SendGrid notification to {}: '
                        '{}{}error={}.'.format(
                            target,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent SendGrid notification to {}.'.format(target))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending SendGrid '
                    'notification to {}.'.format(target))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our URL looks like this:
        #    {schema}://{apikey}:{from_email}/{targets}
        #
        # which actually equates to:
        #    {schema}://{user}:{password}@{host}/{email1}/{email2}/etc..
        #                 ^       ^         ^
        #                 |       |         |
        #              apikey     -from addr-

        if not results.get('user'):
            # An API Key as not properly specified
            return None

        if not results.get('password'):
            # A From Email was not correctly specified
            return None

        # Prepare our API Key
        results['apikey'] = NotifySendGrid.unquote(results['user'])

        # Prepare our From Email Address
        results['from_email'] = '{}@{}'.format(
            NotifySendGrid.unquote(results['password']),
            NotifySendGrid.unquote(results['host']),
        )

        # Acquire our targets
        results['targets'] = NotifySendGrid.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifySendGrid.parse_list(results['qsd']['to'])

        # Handle Carbon Copy Addresses
        if 'cc' in results['qsd'] and len(results['qsd']['cc']):
            results['cc'] = \
                NotifySendGrid.parse_list(results['qsd']['cc'])

        # Handle Blind Carbon Copy Addresses
        if 'bcc' in results['qsd'] and len(results['qsd']['bcc']):
            results['bcc'] = \
                NotifySendGrid.parse_list(results['qsd']['bcc'])

        # Handle Blind Carbon Copy Addresses
        if 'template' in results['qsd'] and len(results['qsd']['template']):
            results['template'] = \
                NotifySendGrid.unquote(results['qsd']['template'])

        # Add any template substitutions
        results['template_data'] = results['qsd+']

        return results
