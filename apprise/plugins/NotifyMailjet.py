# -*- coding: utf-8 -*-
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
# You will need an API Key & associated Secret Key for this plugin to work.
# From the Account Settings -> Master API Key & Sub API Key management you 
# create keys if you do not # have one already. 
#
# The schema to use the plugin looks like this:
#    {schema}://{apikey}:{secretKey}:{from_email}
#
# Your {from_email} must be a validated email address or domain.
#
# API Reference:
#  - https://dev.mailjet.com/email/guides/
#  - https://dev.mailjet.com/email/guides/send-api-v31/
#  

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_list
from ..utils import is_email
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Mailjet HTTP Error Messages
MAILJET_HTTP_ERROR_MAP = {
    200: 'OK',
    201: 'Created - The POST request was successfully executed',
    204: 'No Content',
    304: 'Not Modified - The PUT request did not affect any record',
    400: 'Bad Request - One or more parameters are missing or misspelled',
    401: 'Unauthorized - You have specified an incorrect API Key / API Secret Key pair',
    403: 'Forbidden - You are not authorized to access this resource',
    404: 'Not Found - The resource with the specified ID does not exist',
    405: 'Method Not Allowed - The method requested on the resource does not exist',
    429: 'Too Many Requests - You have reached the maximum number of calls allowed per minute',
    500: 'Internal Server Error'
}

class NotifyMailjet(NotifyBase):
    """
    A wrapper for Notify Mailjet Emails
    """

    # The default descriptive name associated with the Notification
    service_name = 'mailjet'

    # The services URL
    service_url = 'https://www.mailjet.com'

    # The default secure protocol
    secure_protocol = 'mailjet'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = ""

    # Default format is HTML
    notify_format = NotifyFormat.HTML

    # The default API URL to use
    notify_url = "https://api.mailjet.com/v3.1/send"

    # The default empty subject
    default_empty_subject = '<no subject>'

    # Object templates
    templates = (
        '{schema}://{from_email}/{apikey}/{secretkey}',
        #'{schema}://{apikey}:{secretkey}:{from_email}/{target_email}'
        '{schema}://{from_email}/{apikey}/{secretkey}/{targets}'
    )

        # Define our template arguments
    template_tokens = dict(NotifyBase.template_tokens, **{
        'apikey': {
            'name': _('API Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Z0-9._-]+$', 'i'),
        },
        'secretkey': {
            'name': _('Secret API Key'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Z0-9._-]+$', 'i'),
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
    })

    def __init__(self, apikey, secretkey, from_email, targets=None, cc=None
        , bcc=None, **kwargs):
        """
        Initialize Notify Mailjet object
        """
        super(NotifyMailjet, self).__init__(**kwargs)

        self.apikey = validate_regex(
            apikey, *self.template_tokens['apikey']['regex'])
        if not self.apikey:
            msg = 'An invalid Mailjet API key ' \
                '({}) was specified'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.secretkey = validate_regex(
            secretkey, *self.template_tokens['secretkey']['regex'])
        if not self.secretkey:
            msg = 'An invalid Mailjet API secret key ' \
                '({}) was specified'.format(secretkey)
            self.logger.warning(msg)
            raise TypeError(msg)

        result = is_email(from_email)
        if not result:
            msg = 'Invalid From email specified: {}'.format(from_email)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store email address
        self.from_email = result['full_email']

        self.from_name = None
        if 'from_name' in kwargs:
            self.from_name = kwargs['from_name']

        # Parse Targets (To Emails)
        self.targets = list()

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Validate recipients (to:) and drop bad ones:
        for recipient in parse_list(targets):

            result = is_email(recipient)
            if result:
                self.targets.append(result['full_email'])
                continue

            self.logger.warning(
                'Dropped invalid email '
                '({}) specified.'.format(recipient),
            )

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_list(cc):

            result = is_email(recipient)
            if result:
                self.cc.add(result['full_email'])
                continue

            self.logger.warning(
                'Dropped invalid Carbon Copy email '
                '({}) specified.'.format(recipient),
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_list(bcc):

            result = is_email(recipient)
            if result:
                self.bcc.add(result['full_email'])
                continue

            self.logger.warning(
                'Dropped invalid Blind Carbon Copy email '
                '({}) specified.'.format(recipient),
            )

        if len(self.targets) == 0:
            # Notify ourselves
            self.targets.append(self.from_email)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments
        """
        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            params['cc'] = ','.join(self.cc)

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params['bcc'] = ','.join(self.bcc)

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1 and self.targets[0] == self.from_email)

        return '{schema}://{from_email}/{apikey}/{secretkey}/{targets}?{params}'.format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=''),
            secretkey=self.pprint(self.secretkey, privacy, safe=''),
            # never encode email since it plays a huge role in our hostname
            from_email=self.from_email,
            targets='' if not has_targets else '/'.join(
                [NotifyMailjet.quote(x, safe='') for x in self.targets]),
            params=NotifyMailjet.urlencode(params),
        )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Mailjet Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json',
        }


        # Basic Auth with apikey:secretkey always required
        auth = (self.apikey, self.secretkey)

        # error tracking (used for function return)
        has_error = False

        # A Simple Email Payload Template
        _payload = {
            'Messages' : [
                {
                    'From': {
                        'Email': self.from_email,
                        'Name': self.from_name
                    },
                    'Subject': title if title else self.default_empty_subject,
                    'HtmlPart': body
                }
            ]
        }

        targets = list(self.targets)
        cc = self.cc - self.bcc - set(targets)
        bcc = self.bcc - set(targets)

        payload = _payload.copy()
        payload['Messages'][0]['To'] = [{'Email': target} for target in targets]

        if len(cc):
            payload['Messages'][0]['Cc'] = [{'Email': target} for target in cc]

        if len(bcc):
            payload['Messages'][0]['Bcc'] = [{'Email': target} for target in bcc]

        self.logger.debug('Mailjet POST URL: %s (cert_verify=%r)' % (self.notify_url, self.verify_certificate))
        self.logger.debug('Mailjet Payload: %s' % str(payload))

        self.throttle()
        try:
            r = requests.post(
                self.notify_url,
                auth=auth,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            print(r)
        except requests.RequestException as e:
            self.logger.warning(
                'A connection error occurred sending Mailjet '
                'notification to {}.'.format(**targets)
            )
            has_error = True
            

        return not has_error

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our URL looks like this:
        #    {schema}://{from_email}/{apikey}/{secretkey}/{targets}
        #
        # which actually equates to:
        #    {schema}://{user}@{host}/{apikey}/{secretkey}/{email1}/{email2}/etc..
        #                 ^       ^         
        #                 |       |         
        #                -from addr-

        results['from_email'] = '{}@{}'.format(
            NotifyMailjet.unquote(results['user']),
            NotifyMailjet.unquote(results['host']),
        )

        entries = NotifyMailjet.split_path(results['fullpath'])
        # Now fetch the remaining tokens
        try:
            # the first two are api_key & secret_key
            results['apikey'] = entries.pop(0)
            results['secretkey'] = entries.pop(0)

        except IndexError:
            # Force some bad values that will get caught
            # in parsing later
            api_key = None
            secret_key = None
        
        if 'name' in results['qsd'] and len(results['qsd']['name']):
            # Extract from name to associate with from address
            results['from_name'] = NotifyMailjet.unquote(results['qsd']['name'])

        # The remaining tokens are the targets
        results['targets'] = entries

        return results
    

    