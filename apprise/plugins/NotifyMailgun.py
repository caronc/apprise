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

# Signup @ https://www.mailgun.com/
#
# Each domain will have an API key associated with it. If you sign up you'll
# get a sandbox domain to use.  Or if you set up your own, they'll have
# api keys associated with them too.  Find your API key out by visiting
#    https://app.mailgun.com/app/domains
#
# From here you can click on the domain you're interested in. You can acquire
# the API Key from here which will look something like:
#    4b4f2918c6c21ba0a26ad2af73c07f4d-dk5f51da-8f91a0df
#
# You'll also need to know the domain that is associated with your API key.
# This will be obvious with a paid account because it will be the domain name
# you've registered with them.   But if you're using a test account, it will
# be name of the sandbox you've set up such as:
#    sandbox74bda3414c06kb5acb946.mailgun.org
#
# Knowing this, you can buid your mailgun url as follows:
#  mailgun://{user}@{domain}/{apikey}
#  mailgun://{user}@{domain}/{apikey}/{email}
#
# You can email as many addresses as you want as:
#  mailgun://{user}@{domain}/{apikey}/{email1}/{email2}/{emailN}
#
#  The {user}@{domain} effectively assembles the 'from' email address
#  the email will be transmitted from.  If no email address is specified
#  then it will also become the 'to' address as well.
#
import requests
from email.utils import formataddr
from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..common import NotifyFormat
from ..utils import parse_emails
from ..utils import is_email
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Provide some known codes Mailgun uses and what they translate to:
# Based on https://documentation.mailgun.com/en/latest/api-intro.html#errors
MAILGUN_HTTP_ERROR_MAP = {
    400: 'A bad request was made to the server.',
    401: 'The provided API Key was not valid.',
    402: 'The request failed for a reason out of your control.',
    404: 'The requested API query is not valid.',
    413: 'Provided attachment is to big.',
}


# Priorities
class MailgunRegion(object):
    US = 'us'
    EU = 'eu'


# Mailgun APIs
MAILGUN_API_LOOKUP = {
    MailgunRegion.US: 'https://api.mailgun.net/v3/',
    MailgunRegion.EU: 'https://api.eu.mailgun.net/v3/',
}

# A List of our regions we can use for verification
MAILGUN_REGIONS = (
    MailgunRegion.US,
    MailgunRegion.EU,
)


class NotifyMailgun(NotifyBase):
    """
    A wrapper for Mailgun Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Mailgun'

    # The services URL
    service_url = 'https://www.mailgun.com/'

    # All notification requests are secure
    secure_protocol = 'mailgun'

    # Mailgun advertises they allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_mailgun'

    # Default Notify Format
    notify_format = NotifyFormat.HTML

    # The default region to use if one isn't otherwise specified
    mailgun_default_region = MailgunRegion.US

    # Define object templates
    templates = (
        '{schema}://{user}@{host}:{apikey}/',
        '{schema}://{user}@{host}:{apikey}/{targets}',
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
        'apikey': {
            'name': _('API Key'),
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
        'name': {
            'name': _('From Name'),
            'type': 'string',
            'map_to': 'from_name',
        },
        'region': {
            'name': _('Region Name'),
            'type': 'choice:string',
            'values': MAILGUN_REGIONS,
            'default': MailgunRegion.US,
            'map_to': 'region_name',
        },
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

    def __init__(self, apikey, targets, cc=None, bcc=None, from_name=None,
                 region_name=None, **kwargs):
        """
        Initialize Mailgun Object
        """
        super(NotifyMailgun, self).__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid Mailgun API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate our username
        if not self.user:
            msg = 'No Mailgun username was specified.'
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

        # Store our region
        try:
            self.region_name = self.mailgun_default_region \
                if region_name is None else region_name.lower()

            if self.region_name not in MAILGUN_REGIONS:
                # allow the outer except to handle this common response
                raise
        except:
            # Invalid region specified
            msg = 'The Mailgun region specified ({}) is invalid.' \
                  .format(region_name)
            self.logger.warning(msg)
            raise TypeError(msg)

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

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Mailgun Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                'There are no Email recipients to notify')
            return False

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
        }

        try:
            from_addr = formataddr(
                (self.from_name if self.from_name else False,
                 self.from_addr), charset='utf-8')

        except TypeError:
            # Python v2.x Support (no charset keyword)
            # Format our cc addresses to support the Name field
            from_addr = formataddr(
                (self.from_name if self.from_name else False,
                 self.from_addr))

        # Prepare our payload
        payload = {
            'from': from_addr,
            'subject': title,
        }

        if self.notify_format == NotifyFormat.HTML:
            payload['html'] = body

        else:
            payload['text'] = body

        # Prepare our URL as it's based on our hostname
        url = '{}{}/messages'.format(
            MAILGUN_API_LOOKUP[self.region_name], self.host)

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
                # Prepare our to
                payload['to'] = formataddr((to_name, to_addr), charset='utf-8')

                # Format our cc addresses to support the Name field
                if cc:
                    payload['cc'] = [formataddr(
                        (self.names.get(addr, False), addr), charset='utf-8')
                        for addr in cc]

                # Format our bcc addresses to support the Name field
                if bcc:
                    payload['bcc'] = [formataddr(
                        (self.names.get(addr, False), addr), charset='utf-8')
                        for addr in bcc]

            except TypeError:
                # Python v2.x Support (no charset keyword)
                # Format our cc addresses to support the Name field

                # Prepare our to
                payload['to'] = formataddr((to_name, to_addr))

                if cc:
                    payload['cc'] = [formataddr(
                        (self.names.get(addr, False), addr)) for addr in cc]

                # Format our bcc addresses to support the Name field
                if bcc:
                    payload['bcc'] = [formataddr(
                        (self.names.get(addr, False), addr)) for addr in bcc]

            # Some Debug Logging
            self.logger.debug('Mailgun POST URL: {} (cert_verify={})'.format(
                url, self.verify_certificate))
            self.logger.debug('Mailgun Payload: {}' .format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    auth=("api", self.apikey),
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code, MAILGUN_API_LOOKUP)

                    self.logger.warning(
                        'Failed to send Mailgun notification to {}: '
                        '{}{}error={}.'.format(
                            to_addr,
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
                        'Sent Mailgun notification to {}.'.format(to_addr))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending Mailgun:%s ' % (
                        to_addr) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'region': self.region_name,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.from_name is not None:
            # from_name specified; pass it back on the url
            params['name'] = self.from_name

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            params['cc'] = ','.join(
                ['{}{}'.format(
                    '' if not e not in self.names
                    else '{}:'.format(self.names[e]), e) for e in self.cc])

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params['bcc'] = ','.join(
                ['{}{}'.format(
                    '' if not e not in self.names
                    else '{}:'.format(self.names[e]), e) for e in self.bcc])

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1
                 and self.targets[0][1] == self.from_addr)

        return '{schema}://{user}@{host}/{apikey}/{targets}/?{params}'.format(
            schema=self.secure_protocol,
            host=self.host,
            user=NotifyMailgun.quote(self.user, safe=''),
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='' if not has_targets else '/'.join(
                [NotifyMailgun.quote('{}{}'.format(
                    '' if not e[0] else '{}:'.format(e[0]), e[1]),
                    safe='') for e in self.targets]),
            params=NotifyMailgun.urlencode(params))

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
        results['targets'] = NotifyMailgun.split_path(results['fullpath'])

        # Our very first entry is reserved for our api key
        try:
            results['apikey'] = results['targets'].pop(0)

        except IndexError:
            # We're done - no API Key found
            results['apikey'] = None

        if 'name' in results['qsd'] and len(results['qsd']['name']):
            # Extract from name to associate with from address
            results['from_name'] = \
                NotifyMailgun.unquote(results['qsd']['name'])

        if 'region' in results['qsd'] and len(results['qsd']['region']):
            # Extract from name to associate with from address
            results['region_name'] = \
                NotifyMailgun.unquote(results['qsd']['region'])

        # Handle 'to' email address
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'].append(results['qsd']['to'])

        # Handle Carbon Copy Addresses
        if 'cc' in results['qsd'] and len(results['qsd']['cc']):
            results['cc'] = results['qsd']['cc']

        # Handle Blind Carbon Copy Addresses
        if 'bcc' in results['qsd'] and len(results['qsd']['bcc']):
            results['bcc'] = results['qsd']['bcc']

        return results
