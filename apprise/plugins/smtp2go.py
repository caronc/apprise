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

# Signup @ https://smtp2go.com (free accounts available)
#
# From your dashboard, you can generate an API Key if you haven't already
# at https://app.smtp2go.com/settings/apikeys/

# The API Key from here which will look something like:
#    api-60F0DD0AB5BA11ABA421F23C91C88EF4
#
# Knowing this, you can buid your smtp2go url as follows:
#  smtp2go://{user}@{domain}/{apikey}
#  smtp2go://{user}@{domain}/{apikey}/{email}
#
# You can email as many addresses as you want as:
#  smtp2go://{user}@{domain}/{apikey}/{email1}/{email2}/{emailN}
#
#  The {user}@{domain} effectively assembles the 'from' email address
#  the email will be transmitted from.  If no email address is specified
#  then it will also become the 'to' address as well.
#
import requests
from json import dumps
from email.utils import formataddr
from .base import NotifyBase
from .. import exception
from ..common import NotifyType
from ..common import NotifyFormat
from ..utils.parse import (
    parse_emails, parse_bool, is_email, validate_regex)
from ..locale import gettext_lazy as _

SMTP2GO_HTTP_ERROR_MAP = {
    429: 'To many requests.',
}


class NotifySMTP2Go(NotifyBase):
    """
    A wrapper for SMTP2Go Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'SMTP2Go'

    # The services URL
    service_url = 'https://www.smtp2go.com/'

    # All notification requests are secure
    secure_protocol = 'smtp2go'

    # SMTP2Go advertises they allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.20

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_smtp2go'

    # Notify URL
    notify_url = 'https://api.smtp2go.com/v3/email/send'

    # Support attachments
    attachment_support = True

    # Default Notify Format
    notify_format = NotifyFormat.HTML

    # The maximum amount of emails that can reside within a single
    # batch transfer
    default_batch_size = 100

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

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('Email Header'),
            'prefix': '+',
        },
    }

    def __init__(self, apikey, targets, cc=None, bcc=None, from_name=None,
                 headers=None, batch=False, **kwargs):
        """
        Initialize SMTP2Go Object
        """
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = 'An invalid SMTP2Go API Key ' \
                  '({}) was specified.'.format(apikey)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate our username
        if not self.user:
            msg = 'No SMTP2Go username was specified.'
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

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        # Prepare Batch Mode Flag
        self.batch = batch

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

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform SMTP2Go Notification
        """

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                'There are no Email recipients to notify')
            return False

        # error tracking (used for function return)
        has_error = False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # Prepare our headers
        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }

        # Track our potential attachments
        attachments = []

        if attach and self.attachment_support:
            for no, attachment in enumerate(attach, start=1):
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access SMTP2Go attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                try:
                    # Format our attachment
                    attachments.append({
                        'filename': attachment.name
                        if attachment.name else f'file{no:03}.dat',
                        'fileblob': attachment.base64(),
                        'mimetype': attachment.mimetype,
                    })

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access SMTP2Go attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                self.logger.debug(
                    'Appending SMTP2Go attachment {}'.format(
                        attachment.url(privacy=True)))

        sender = formataddr(
            (self.from_name if self.from_name else False,
             self.from_addr), charset='utf-8')

        # Prepare our payload
        payload = {
            # API Key
            'api_key': self.apikey,

            # Base payload options
            'sender': sender,
            'subject': title,

            # our To array
            'to': [],
        }

        if attachments:
            payload['attachments'] = attachments

        if self.notify_format == NotifyFormat.HTML:
            payload['html_body'] = body

        else:
            payload['text_body'] = body

        # Create a copy of the targets list
        emails = list(self.targets)

        for index in range(0, len(emails), batch_size):
            # Initialize our cc list
            cc = (self.cc - self.bcc)

            # Initialize our bcc list
            bcc = set(self.bcc)

            # Initialize our to list
            to = list()

            for to_addr in self.targets[index:index + batch_size]:
                # Strip target out of cc list if in To
                cc = (cc - set([to_addr[1]]))

                # Strip target out of bcc list if in To
                bcc = (bcc - set([to_addr[1]]))

                # Prepare our `to`
                to.append(formataddr(to_addr, charset='utf-8'))

            # Prepare our To
            payload['to'] = to

            if cc:
                # Format our cc addresses to support the Name field
                payload['cc'] = [formataddr(
                    (self.names.get(addr, False), addr), charset='utf-8')
                    for addr in cc]

            # Format our bcc addresses to support the Name field
            if bcc:
                # set our bcc variable (convert to list first so it's
                # JSON serializable)
                payload['bcc'] = list(bcc)

            # Store our header entries if defined into the payload
            # in their payload
            if self.headers:
                payload['custom_headers'] = \
                    [{'header': k, 'value': v}
                     for k, v in self.headers.items()]

            # Some Debug Logging
            self.logger.debug('SMTP2Go POST URL: {} (cert_verify={})'.format(
                self.notify_url, self.verify_certificate))
            self.logger.debug('SMTP2Go Payload: {}' .format(payload))

            # For logging output of success and errors; we get a head count
            # of our outbound details:
            verbose_dest = ', '.join(
                [x[1] for x in self.targets[index:index + batch_size]]) \
                if len(self.targets[index:index + batch_size]) <= 3 \
                else '{} recipients'.format(
                    len(self.targets[index:index + batch_size]))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = \
                        NotifyBase.http_response_code_lookup(
                            r.status_code, SMTP2GO_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send SMTP2Go notification to {}: '
                        '{}{}error={}.'.format(
                            verbose_dest,
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
                        'Sent SMTP2Go notification to {}.'.format(
                            verbose_dest))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occurred sending SMTP2Go:%s ' % (
                        verbose_dest) + 'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

            except (OSError, IOError) as e:
                self.logger.warning(
                    'An I/O error occurred while reading attachments')
                self.logger.debug('I/O Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol, self.user, self.host, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'batch': 'yes' if self.batch else 'no',
        }

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

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

        return '{schema}://{user}@{host}/{apikey}/{targets}?{params}'.format(
            schema=self.secure_protocol,
            host=self.host,
            user=NotifySMTP2Go.quote(self.user, safe=''),
            apikey=self.pprint(self.apikey, privacy, safe=''),
            targets='' if not has_targets else '/'.join(
                [NotifySMTP2Go.quote('{}{}'.format(
                    '' if not e[0] else '{}:'.format(e[0]), e[1]),
                    safe='') for e in self.targets]),
            params=NotifySMTP2Go.urlencode(params))

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + \
                (1 if targets % batch_size else 0)

        return targets if targets > 0 else 1

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
        results['targets'] = NotifySMTP2Go.split_path(results['fullpath'])

        # Our very first entry is reserved for our api key
        try:
            results['apikey'] = results['targets'].pop(0)

        except IndexError:
            # We're done - no API Key found
            results['apikey'] = None

        if 'name' in results['qsd'] and len(results['qsd']['name']):
            # Extract from name to associate with from address
            results['from_name'] = \
                NotifySMTP2Go.unquote(results['qsd']['name'])

        # Handle 'to' email address
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'].append(results['qsd']['to'])

        # Handle Carbon Copy Addresses
        if 'cc' in results['qsd'] and len(results['qsd']['cc']):
            results['cc'] = results['qsd']['cc']

        # Handle Blind Carbon Copy Addresses
        if 'bcc' in results['qsd'] and len(results['qsd']['bcc']):
            results['bcc'] = results['qsd']['bcc']

        # Add our Meta Headers that the user can provide with their outbound
        # emails
        results['headers'] = {NotifyBase.unquote(x): NotifyBase.unquote(y)
                              for x, y in results['qsd+'].items()}

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifySMTP2Go.template_args['batch']['default']))

        return results
