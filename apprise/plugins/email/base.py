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

import re
import smtplib
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import formataddr, make_msgid
from email.header import Header

from socket import error as SocketError
from datetime import datetime
from datetime import timezone

from ..base import NotifyBase
from ...url import PrivacyMode
from ...common import NotifyFormat, NotifyType
from ...conversion import convert_between
from ...utils import pgp as _pgp
from ...utils.parse import (
    is_ipaddr, is_email, parse_emails, is_hostname, parse_bool)
from ...locale import gettext_lazy as _
from ...logger import logger
from .common import (
    AppriseEmailException, EmailMessage, SecureMailMode, SECURE_MODES,
    WebBaseLogin)
from . import templates


class NotifyEmail(NotifyBase):
    """
    A wrapper to Email Notifications

    """

    # The default descriptive name associated with the Notification
    service_name = 'E-Mail'

    # The default simple (insecure) protocol
    protocol = 'mailto'

    # The default secure protocol
    secure_protocol = 'mailtos'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_email'

    # Support attachments
    attachment_support = True

    # Default Notify Format
    notify_format = NotifyFormat.HTML

    # Default SMTP Timeout (in seconds)
    socket_connect_timeout = 15

    # Define object templates
    templates = (
        '{schema}://{host}',
        '{schema}://{host}:{port}',
        '{schema}://{host}/{targets}',
        '{schema}://{host}:{port}/{targets}',
        '{schema}://{user}@{host}',
        '{schema}://{user}@{host}:{port}',
        '{schema}://{user}@{host}/{targets}',
        '{schema}://{user}@{host}:{port}/{targets}',
        '{schema}://{user}:{password}@{host}',
        '{schema}://{user}:{password}@{host}:{port}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'user': {
            'name': _('User Name'),
            'type': 'string',
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
        },
        'host': {
            'name': _('Domain'),
            'type': 'string',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
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

    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'name': _('To Email'),
            'type': 'string',
            'map_to': 'targets',
        },
        'from': {
            'name': _('From Email'),
            'type': 'string',
            'map_to': 'from_addr',
        },
        'name': {
            'name': _('From Name'),
            'type': 'string',
            'map_to': 'from_addr',
        },
        'cc': {
            'name': _('Carbon Copy'),
            'type': 'list:string',
        },
        'bcc': {
            'name': _('Blind Carbon Copy'),
            'type': 'list:string',
        },
        'smtp': {
            'name': _('SMTP Server'),
            'type': 'string',
            'map_to': 'smtp_host',
        },
        'mode': {
            'name': _('Secure Mode'),
            'type': 'choice:string',
            'values': SECURE_MODES,
            'default': SecureMailMode.STARTTLS,
            'map_to': 'secure_mode',
        },
        'reply': {
            'name': _('Reply To'),
            'type': 'list:string',
            'map_to': 'reply_to',
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
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('Email Header'),
            'prefix': '+',
        },
    }

    def __init__(self, smtp_host=None, from_addr=None, secure_mode=None,
                 targets=None, cc=None, bcc=None, reply_to=None, headers=None,
                 use_pgp=None, pgp_key=None, **kwargs):
        """
        Initialize Email Object

        The smtp_host and secure_mode can be automatically detected depending
        on how the URL was built
        """
        super().__init__(**kwargs)

        # Acquire Email 'To'
        self.targets = list()

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Acquire Reply To
        self.reply_to = set()

        # For tracking our email -> name lookups
        self.names = {}

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        # Now we want to construct the To and From email
        # addresses from the URL provided
        self.from_addr = [False, '']

        # Now detect the SMTP Server
        self.smtp_host = \
            smtp_host if isinstance(smtp_host, str) else ''

        # Now detect secure mode
        if secure_mode:
            self.secure_mode = None \
                if not isinstance(secure_mode, str) \
                else secure_mode.lower()
        else:
            self.secure_mode = SecureMailMode.INSECURE \
                if not self.secure else self.template_args['mode']['default']

        if self.secure_mode not in SECURE_MODES:
            msg = 'The secure mode specified ({}) is invalid.'\
                  .format(secure_mode)
            self.logger.warning(msg)
            raise TypeError(msg)

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

        # Apply any defaults based on certain known configurations
        self.apply_email_defaults(secure_mode=secure_mode, **kwargs)

        if self.user:
            if self.host:
                # Prepare the bases of our email
                self.from_addr = [self.app_id, '{}@{}'.format(
                    re.split(r'[\s@]+', self.user)[0],
                    self.host,
                )]

            else:
                result = is_email(self.user)
                if result:
                    # Prepare the bases of our email and include domain
                    self.host = result['domain']
                    self.from_addr = [self.app_id, self.user]

        if from_addr:
            result = is_email(from_addr)
            if result:
                self.from_addr = (
                    result['name'] if result['name'] else False,
                    result['full_email'])
            else:
                # Only update the string but use the already detected info
                self.from_addr[0] = from_addr

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
            self.targets.append((False, self.from_addr[1]))

        if not self.secure and self.secure_mode != SecureMailMode.INSECURE:
            # Enable Secure mode if not otherwise set
            self.secure = True

        if not self.port:
            # Assign our port based on our secure_mode if not otherwise
            # detected
            self.port = SECURE_MODES[self.secure_mode]['default_port']

        # if there is still no smtp_host then we fall back to the hostname
        if not self.smtp_host:
            self.smtp_host = self.host

        # Prepare our Pretty Good Privacy Object
        self.pgp = _pgp.ApprisePGPController(
            path=self.store.path, pub_keyfile=pgp_key,
            email=self.from_addr[1], asset=self.asset)

        # We store so we can generate a URL later on
        self.pgp_key = pgp_key

        self.use_pgp = use_pgp if not None \
            else self.template_args['pgp']['default']

        if self.use_pgp and not _pgp.PGP_SUPPORT:
            self.logger.warning(
                'PGP Support is not available on this installation; '
                'ask admin to install PGPy')

        return

    def apply_email_defaults(self, secure_mode=None, port=None, **kwargs):
        """
        A function that prefills defaults based on the email
        it was provided.
        """

        if self.smtp_host or not self.user:
            # SMTP Server was explicitly specified, therefore it is assumed
            # the caller knows what he's doing and is intentionally
            # over-riding any smarts to be applied. We also can not apply
            # any default if there was no user specified.
            return

        # detect our email address using our user/host combo
        from_addr = '{}@{}'.format(
            re.split(r'[\s@]+', self.user)[0],
            self.host,
        )

        for i in range(len(templates.EMAIL_TEMPLATES)):  # pragma: no branch
            self.logger.trace('Scanning %s against %s' % (
                from_addr, templates.EMAIL_TEMPLATES[i][0]
            ))
            match = templates.EMAIL_TEMPLATES[i][1].match(from_addr)
            if match:
                self.logger.info(
                    'Applying %s Defaults' %
                    templates.EMAIL_TEMPLATES[i][0],
                )
                # the secure flag can not be altered if defined in the template
                self.secure = templates.EMAIL_TEMPLATES[i][2]\
                    .get('secure', self.secure)

                # The SMTP Host check is already done above; if it was
                # specified we wouldn't even reach this part of the code.
                self.smtp_host = templates.EMAIL_TEMPLATES[i][2]\
                    .get('smtp_host', self.smtp_host)

                # The following can be over-ridden if defined manually in the
                # Apprise URL.  Otherwise they take on the template value
                if not port:
                    self.port = templates.EMAIL_TEMPLATES[i][2]\
                        .get('port', self.port)
                if not secure_mode:
                    self.secure_mode = templates.EMAIL_TEMPLATES[i][2]\
                        .get('secure_mode', self.secure_mode)

                # Adjust email login based on the defined usertype. If no entry
                # was specified, then we default to having them all set (which
                # basically implies that there are no restrictions and use use
                # whatever was specified)
                login_type = \
                    templates.EMAIL_TEMPLATES[i][2].get('login_type', [])
                if login_type:
                    # only apply additional logic to our user if a login_type
                    # was specified.
                    if is_email(self.user):
                        if WebBaseLogin.EMAIL not in login_type:
                            # Email specified but login type
                            # not supported; switch it to user id
                            self.user = match.group('id')

                        else:
                            # Enforce our host information
                            self.host = self.user.split('@')[1]

                    elif WebBaseLogin.USERID not in login_type:
                        # user specified but login type
                        # not supported; switch it to email
                        self.user = '{}@{}'.format(self.user, self.host)

                break

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):

        if not self.targets:
            # There is no one to email; we're done
            logger.warning('There are no Email recipients to notify')
            return False

        # error tracking (used for function return)
        has_error = False

        # bind the socket variable to the current namespace
        socket = None

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            self.logger.debug('Connecting to remote SMTP server...')
            socket_func = smtplib.SMTP
            if self.secure_mode == SecureMailMode.SSL:
                self.logger.debug('Securing connection with SSL...')
                socket_func = smtplib.SMTP_SSL

            socket = socket_func(
                self.smtp_host,
                self.port,
                None,
                timeout=self.socket_connect_timeout,
            )

            if self.secure_mode == SecureMailMode.STARTTLS:
                # Handle Secure Connections
                self.logger.debug('Securing connection with STARTTLS...')
                socket.starttls()

            self.logger.trace('Login ID: {}'.format(self.user))
            if self.user and self.password:
                # Apply Login credetials
                self.logger.debug('Applying user credentials...')
                socket.login(self.user, self.password)

            # Prepare our headers
            headers = {
                'X-Application': self.app_id,
            }
            headers.update(self.headers)

            # Iterate over our email messages we can generate and then
            # send them off.
            for message in NotifyEmail.prepare_emails(
                    subject=title, body=body, notify_format=self.notify_format,
                    from_addr=self.from_addr, to=self.targets,
                    cc=self.cc, bcc=self.bcc, reply_to=self.reply_to,
                    smtp_host=self.smtp_host,
                    attach=attach, headers=headers, names=self.names,
                    pgp=self.pgp if self.use_pgp else None):
                try:
                    socket.sendmail(
                        self.from_addr[1],
                        message.to_addrs,
                        message.body)

                    self.logger.info('Sent Email to %s', message.recipient)

                except (SocketError, smtplib.SMTPException, RuntimeError) as e:
                    self.logger.warning(
                        'Sending email to "%s" failed.', message.recipient)
                    self.logger.debug(f'Socket Exception: {e}')

                    # Mark as failure
                    has_error = True

        except (SocketError, smtplib.SMTPException, RuntimeError) as e:
            self.logger.warning(
                'Connection error while submitting email to "%s"',
                self.smtp_host)
            self.logger.debug(f'Socket Exception: {e}')

            # Mark as failure
            has_error = True

        except AppriseEmailException as e:
            self.logger.debug(f'Socket Exception: {e}')

            # Mark as failure
            has_error = True

        finally:
            # Gracefully terminate the connection with the server
            if socket is not None:
                socket.quit()

        # Reduce our dictionary (eliminate expired keys if any)
        self.pgp.prune()

        return not has_error

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
            params['pgp_key'] = NotifyEmail.quote(self.pgp_key, safe=':\\/')

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        from_addr = None
        if len(self.targets) == 1 and self.targets[0][1] != self.from_addr[1]:
            # A custom email was provided
            from_addr = self.from_addr[1]

        if self.smtp_host != self.host:
            # Apply our SMTP Host only if it differs from the provided hostname
            params['smtp'] = self.smtp_host

        if self.secure:
            # Mode is only requried if we're dealing with a secure connection
            params['mode'] = self.secure_mode

        if self.from_addr[0] and self.from_addr[0] != self.app_id:
            # A custom name was provided
            params['from'] = self.from_addr[0] if not from_addr else \
                formataddr((self.from_addr[0], from_addr), charset='utf-8')

        elif from_addr:
            params['from'] = formataddr((False, from_addr), charset='utf-8')

        elif not self.user:
            params['from'] = \
                formataddr((False, self.from_addr[1]), charset='utf-8')

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

        # pull email suffix from username (if present)
        user = None if not self.user else self.user.split('@')[0]

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyEmail.quote(user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif user:
            # user url
            auth = '{user}@'.format(
                user=NotifyEmail.quote(user, safe=''),
            )

        # Default Port setup
        default_port = SECURE_MODES[self.secure_mode]['default_port']

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1
                 and self.targets[0][1] == self.from_addr[1])

        return '{schema}://{auth}{hostname}{port}/{targets}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='' if not has_targets else '/'.join(
                [NotifyEmail.quote('{}{}'.format(
                    '' if not e[0] else '{}:'.format(e[0]), e[1]),
                    safe='') for e in self.targets]),
            params=NotifyEmail.urlencode(params),
        )

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user, self.password, self.host, self.smtp_host,
            self.port if self.port
            else SECURE_MODES[self.secure_mode]['default_port'],
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return len(self.targets) if self.targets else 1

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

        # Prepare our target lists
        results['targets'] = []

        if is_ipaddr(results['host']):
            # Silently move on and do not disrupt any configuration
            pass

        elif not is_hostname(results['host'], ipv4=False, ipv6=False,
                             underscore=False):

            if is_email(NotifyEmail.unquote(results['host'])):
                # Don't lose defined email addresses
                results['targets'].append(NotifyEmail.unquote(results['host']))

            # Detect if we have a valid hostname or not; be sure to reset it's
            # value if invalid; we'll attempt to figure this out later on
            results['host'] = ''

        # Get PGP Flag
        results['use_pgp'] = \
            parse_bool(results['qsd'].get(
                'pgp', NotifyEmail.template_args['pgp']['default']))

        # Get PGP Public Key Override
        if 'pgpkey' in results['qsd'] and results['qsd']['pgpkey']:
            results['pgp_key'] = \
                NotifyEmail.unquote(results['qsd']['pgpkey'])

        # The From address is a must; either through the use of templates
        # from= entry and/or merging the user and hostname together, this
        # must be calculated or parse_url will fail.
        from_addr = ''

        # The server we connect to to send our mail to
        smtp_host = ''

        # Get our potential email targets; if none our found we'll just
        # add one to ourselves
        results['targets'] += NotifyEmail.split_path(results['fullpath'])

        # Attempt to detect 'to' email address
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'].append(results['qsd']['to'])

        # Attempt to detect 'from' email address
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            from_addr = NotifyEmail.unquote(results['qsd']['from'])

            if 'name' in results['qsd'] and len(results['qsd']['name']):
                from_addr = formataddr(
                    (NotifyEmail.unquote(results['qsd']['name']), from_addr),
                    charset='utf-8')

        elif 'name' in results['qsd'] and len(results['qsd']['name']):
            # Extract from name to associate with from address
            from_addr = NotifyEmail.unquote(results['qsd']['name'])

        # Store SMTP Host if specified
        if 'smtp' in results['qsd'] and len(results['qsd']['smtp']):
            # Extract the smtp server
            smtp_host = NotifyEmail.unquote(results['qsd']['smtp'])

        if 'mode' in results['qsd'] and len(results['qsd']['mode']):
            # Extract the secure mode to over-ride the default
            results['secure_mode'] = results['qsd']['mode'].lower()

        # Handle Carbon Copy Addresses
        if 'cc' in results['qsd'] and len(results['qsd']['cc']):
            results['cc'] = results['qsd']['cc']

        # Handle Blind Carbon Copy Addresses
        if 'bcc' in results['qsd'] and len(results['qsd']['bcc']):
            results['bcc'] = results['qsd']['bcc']

        # Handle Reply To Addresses
        if 'reply' in results['qsd'] and len(results['qsd']['reply']):
            results['reply_to'] = results['qsd']['reply']

        results['from_addr'] = from_addr
        results['smtp_host'] = smtp_host

        # Add our Meta Headers that the user can provide with their outbound
        # emails
        results['headers'] = {NotifyBase.unquote(x): NotifyBase.unquote(y)
                              for x, y in results['qsd+'].items()}

        return results

    @staticmethod
    def _get_charset(input_string):
        """
        Get utf-8 charset if non ascii string only

        Encode an ascii string to utf-8 is bad for email deliverability
        because some anti-spam gives a bad score for that
        like SUBJ_EXCESS_QP flag on Rspamd
        """
        if not input_string:
            return None
        return 'utf-8' if not all(ord(c) < 128 for c in input_string) else None

    @staticmethod
    def prepare_emails(subject, body, from_addr, to,
                       cc=set(), bcc=set(), reply_to=set(),
                       # Providing an SMTP Host helps improve Email Message-ID
                       # and avoids getting flagged as spam
                       smtp_host=None,
                       # Can be either 'html' or 'text'
                       notify_format=NotifyFormat.HTML,
                       attach=None, headers=dict(),
                       # Names can be a dictionary
                       names=None,
                       # Pretty Good Privacy Support; Pass in an
                       # ApprisePGPController if you wish to use it
                       pgp=None):
        """
        Generator for emails
            from_addr: must be in format: (from_name, from_addr)
            to: must be in the format:
                 [(to_name, to_addr), (to_name, to_addr)), ...]
            cc: must be a set of email addresses
            bcc: must be a set of email addresses
            reply_to: must be either None, or an email address
            smtp_host: This is used to generate the email's Message-ID. Set
                       this correctly to avoid getting flagged as Spam
            notify_format: can be either 'text' or 'html'
            attach: must be of class AppriseAttachment
            headers: Optionally provide a dictionary of additional headers you
                     would like to include in the email payload
            names: This is a dictionary of email addresses as keys and the
                   Names to associate with them when sending the email.
                   This is cross referenced for the cc and bcc lists
            pgp:   Encrypting the message using Pretty Good Privacy support
                   This requires that the pgp_path provided exists and
                   keys can be referenced here to perform the encryption
                   with. If a key isn't found, one will be generated.

                   pgp support requires the 'PGPy' Python library to be
                   available.

                   Pass in an ApprisePGPController() if you wish to use this
        """

        if not to:
            # There is no one to email; we're done
            msg = 'There are no Email recipients to notify'
            logger.warning(msg)
            raise AppriseEmailException(msg)

        elif pgp and not _pgp.PGP_SUPPORT:
            msg = 'PGP Support unavailable; install PGPy library'
            logger.warning(msg)
            raise AppriseEmailException(msg)

        if not names:
            # Prepare a empty dictionary to prevent errors/warnings
            names = {}

        if not smtp_host:
            # Generate a host identifier (used for Message-ID Creation)
            smtp_host = from_addr[1].split('@')[1]

        logger.debug('SMTP Host: {smtp_host}')

        # Create a copy of the targets list
        emails = list(to)
        while len(emails):
            # Get our email to notify
            to_name, to_addr = emails.pop(0)

            # Strip target out of cc list if in To or Bcc
            _cc = (cc - bcc - set([to_addr]))

            # Strip target out of bcc list if in To
            _bcc = (bcc - set([to_addr]))

            # Strip target out of reply_to list if in To
            _reply_to = (reply_to - set([to_addr]))

            # Format our cc addresses to support the Name field
            _cc = [formataddr(
                (names.get(addr, False), addr), charset='utf-8')
                for addr in _cc]

            # Format our bcc addresses to support the Name field
            _bcc = [formataddr(
                (names.get(addr, False), addr), charset='utf-8')
                for addr in _bcc]

            if reply_to:
                # Format our reply-to addresses to support the Name field
                reply_to = [formataddr(
                    (names.get(addr, False), addr), charset='utf-8')
                    for addr in reply_to]

            logger.debug(
                'Email From: {}'.format(
                    formataddr(from_addr, charset='utf-8')))

            logger.debug('Email To: {}'.format(to_addr))
            if _cc:
                logger.debug('Email Cc: {}'.format(', '.join(_cc)))
            if _bcc:
                logger.debug('Email Bcc: {}'.format(', '.join(_bcc)))
            if _reply_to:
                logger.debug(
                    'Email Reply-To: {}'.format(', '.join(_reply_to))
                )

            # Prepare Email Message
            if notify_format == NotifyFormat.HTML:
                base = MIMEMultipart("alternative")
                base.attach(MIMEText(
                    convert_between(
                        NotifyFormat.HTML, NotifyFormat.TEXT, body),
                    'plain', 'utf-8')
                )
                base.attach(MIMEText(body, 'html', 'utf-8'))
            else:
                base = MIMEText(body, 'plain', 'utf-8')

            if attach:
                mixed = MIMEMultipart("mixed")
                mixed.attach(base)
                # Now store our attachments
                for no, attachment in enumerate(attach, start=1):
                    if not attachment:
                        # We could not load the attachment; take an early
                        # exit since this isn't what the end user wanted

                        # We could not access the attachment
                        msg = 'Could not access attachment {}.'.format(
                            attachment.url(privacy=True))
                        logger.warning(msg)
                        raise AppriseEmailException(msg)

                    logger.debug(
                        'Preparing Email attachment {}'.format(
                            attachment.url(privacy=True)))

                    with open(attachment.path, "rb") as abody:
                        app = MIMEApplication(abody.read())
                        app.set_type(attachment.mimetype)

                        # Prepare our attachment name
                        filename = attachment.name \
                            if attachment.name else f'file{no:03}.dat'

                        app.add_header(
                            'Content-Disposition',
                            'attachment; filename="{}"'.format(
                                Header(filename, 'utf-8')),
                        )
                        mixed.attach(app)
                base = mixed

            if pgp:
                logger.debug("Securing Email with PGP Encryption")
                # Set our header information to include in the encryption
                base['From'] = formataddr(
                    (None, from_addr[1]), charset='utf-8')
                base['To'] = formataddr((None, to_addr), charset='utf-8')
                base['Subject'] = \
                    Header(subject, NotifyEmail._get_charset(subject))

                # Apply our encryption
                encrypted_content = \
                    pgp.encrypt(base.as_string(), to_addr)

                if not encrypted_content:
                    # Unable to send notification
                    msg = 'Unable to encrypt email via PGP'
                    logger.warning(msg)
                    raise AppriseEmailException(msg)

                # prepare our messsage
                base = MIMEMultipart(
                    "encrypted", protocol="application/pgp-encrypted")

                # Store Autocrypt header (DeltaChat Support)
                base.add_header(
                    "Autocrypt",
                    "addr=%s; prefer-encrypt=mutual" % formataddr(
                        (False, to_addr), charset='utf-8'))

                # Set Encryption Info Part
                enc_payload = MIMEText("Version: 1", "plain")
                enc_payload.set_type("application/pgp-encrypted")
                base.attach(enc_payload)

                enc_payload = MIMEBase("application", "octet-stream")
                enc_payload.set_payload(encrypted_content)
                base.attach(enc_payload)

            # Apply any provided custom headers
            for k, v in headers.items():
                base[k] = Header(v, NotifyEmail._get_charset(v))

            base['Subject'] = \
                Header(subject, NotifyEmail._get_charset(subject))
            base['From'] = formataddr(from_addr, charset='utf-8')
            base['To'] = formataddr((to_name, to_addr), charset='utf-8')
            base['Message-ID'] = make_msgid(domain=smtp_host)
            base['Date'] = \
                datetime.now(timezone.utc)\
                .strftime("%a, %d %b %Y %H:%M:%S +0000")

            if cc:
                base['Cc'] = ','.join(_cc)

            if reply_to:
                base['Reply-To'] = ','.join(_reply_to)

            yield EmailMessage(
                recipient=to_addr,
                to_addrs=[to_addr] + list(_cc) + list(_bcc),
                body=base.as_string())
