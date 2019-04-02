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

import re
import six
import smtplib
from email.mime.text import MIMEText
from socket import error as SocketError
from datetime import datetime

from .NotifyBase import NotifyBase
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import is_email
from ..utils import parse_list
from ..AppriseLocale import gettext_lazy as _


class WebBaseLogin(object):
    """
    This class is just used in conjunction of the default emailers
    to best formulate a login to it using the data detected
    """
    # User Login must be Email Based
    EMAIL = 'Email'

    # User Login must UserID Based
    USERID = 'UserID'


# Secure Email Modes
class SecureMailMode(object):
    SSL = "ssl"
    STARTTLS = "starttls"


# Define all of the secure modes (used during validation)
SECURE_MODES = (
    SecureMailMode.SSL,
    SecureMailMode.STARTTLS,
)

# To attempt to make this script stupid proof, if we detect an email address
# that is part of the this table, we can pre-use a lot more defaults if they
# aren't otherwise specified on the users input.
EMAIL_TEMPLATES = (
    # Google GMail
    (
        'Google Mail',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>gmail\.com)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp.gmail.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Pronto Mail
    (
        'Pronto Mail',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>prontomail\.com)$', re.I),
        {
            'port': 465,
            'smtp_host': 'secure.emailsrvr.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Microsoft Hotmail
    (
        'Microsoft Hotmail',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>(hotmail|live)\.com)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp.live.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Yahoo Mail
    (
        'Yahoo Mail',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>yahoo\.(ca|com))$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.mail.yahoo.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Fast Mail (Series 1)
    (
        'Fast Mail',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>fastmail\.(com|cn|co\.uk|com\.au|de|es|fm|fr|im|'
            r'in|jp|mx|net|nl|org|se|to|tw|uk|us))$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.fastmail.com',
            'secure': True,
            'secure_mode': SecureMailMode.SSL,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Fast Mail (Series 2)
    (
        'Fast Mail Extended Addresses',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>123mail\.org|airpost\.net|eml\.cc|fmail\.co\.uk|'
            r'fmgirl\.com|fmguy\.com|mailbolt\.com|mailcan\.com|'
            r'mailhaven\.com|mailmight\.com|ml1\.net|mm\.st|myfastmail\.com|'
            r'proinbox\.com|promessage\.com|rushpost\.com|sent\.(as|at|com)|'
            r'speedymail\.org|warpmail\.net|xsmail\.com|150mail\.com|'
            r'150ml\.com|16mail\.com|2-mail\.com|4email\.net|50mail\.com|'
            r'allmail\.net|bestmail\.us|cluemail\.com|elitemail\.org|'
            r'emailcorner\.net|emailengine\.(net|org)|emailgroups\.net|'
            r'emailplus\.org|emailuser\.net|f-m\.fm|fast-email\.com|'
            r'fast-mail\.org|fastem\.com|fastemail\.us|fastemailer\.com|'
            r'fastest\.cc|fastimap\.com|fastmailbox\.net|fastmessaging\.com|'
            r'fea\.st|fmailbox\.com|ftml\.net|h-mail\.us|hailmail\.net|'
            r'imap-mail\.com|imap\.cc|imapmail\.org|inoutbox\.com|'
            r'internet-e-mail\.com|internet-mail\.org|internetemails\.net|'
            r'internetmailing\.net|jetemail\.net|justemail\.net|'
            r'letterboxes\.org|mail-central\.com|mail-page\.com|'
            r'mailandftp\.com|mailas\.com|mailc\.net|mailforce\.net|'
            r'mailftp\.com|mailingaddress\.org|mailite\.com|mailnew\.com|'
            r'mailsent\.net|mailservice\.ms|mailup\.net|mailworks\.org|'
            r'mymacmail\.com|nospammail\.net|ownmail\.net|petml\.com|'
            r'postinbox\.com|postpro\.net|realemail\.net|reallyfast\.biz|'
            r'reallyfast\.info|speedpost\.net|ssl-mail\.com|swift-mail\.com|'
            r'the-fastest\.net|the-quickest\.com|theinternetemail\.com|'
            r'veryfast\.biz|veryspeedy\.net|yepmail\.net)$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.fastmail.com',
            'secure': True,
            'secure_mode': SecureMailMode.SSL,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Zoho Mail
    (
        'Zoho Mail',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>zoho\.com)$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.zoho.com',
            'secure': True,
            'secure_mode': SecureMailMode.SSL,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Catch All
    (
        'Custom',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>.+)$', re.I),
        {
            # Setting smtp_host to None is a way of
            # auto-detecting it based on other parameters
            # specified.  There is no reason to ever modify
            # this Catch All
            'smtp_host': None,
        },
    ),
)


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

    # Default Notify Format
    notify_format = NotifyFormat.HTML

    # Default Non-Encryption Port
    default_port = 25

    # Default Secure Port
    default_secure_port = 587

    # Default Secure Mode
    default_secure_mode = SecureMailMode.STARTTLS

    # Default SMTP Timeout (in seconds)
    connect_timeout = 15

    # Define object templates
    templates = (
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
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
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
        'targets': {
            'name': _('Target Emails'),
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
            'map_to': 'from_name',
        },
        'smtp_host': {
            'name': _('SMTP Server'),
            'type': 'string',
        },
        'mode': {
            'name': _('Secure Mode'),
            'type': 'choice:string',
            'values': SECURE_MODES,
            'default': SecureMailMode.STARTTLS,
            'map_to': 'secure_mode',
        },
        'timeout': {
            'name': _('Server Timeout'),
            'type': 'int',
            'default': 15,
            'min': 5,
        },
    })

    def __init__(self, timeout=15, smtp_host=None, from_name=None,
                 from_addr=None, secure_mode=None, targets=None, **kwargs):
        """
        Initialize Email Object

        The smtp_host and secure_mode can be automatically detected depending
        on how the URL was built
        """
        super(NotifyEmail, self).__init__(**kwargs)

        # Handle SMTP vs SMTPS (Secure vs UnSecure)
        if not self.port:
            if self.secure:
                self.port = self.default_secure_port

            else:
                self.port = self.default_port

        # Email SMTP Server Timeout
        try:
            self.timeout = int(timeout)

        except (ValueError, TypeError):
            self.timeout = self.connect_timeout

        # Acquire targets
        self.targets = parse_list(targets)

        # Now we want to construct the To and From email
        # addresses from the URL provided
        self.from_name = from_name
        self.from_addr = from_addr

        if not self.from_addr:
            # detect our email address
            self.from_addr = '{}@{}'.format(
                re.split(r'[\s@]+', self.user)[0],
                self.host,
            )

        if not is_email(self.from_addr):
            # Parse Source domain based on from_addr
            msg = 'Invalid ~From~ email specified: {}'.format(self.from_addr)
            self.logger.warning(msg)
            raise TypeError(msg)

        # If our target email list is empty we want to add ourselves to it
        if len(self.targets) == 0:
            self.targets.append(self.from_addr)

        # Now detect the SMTP Server
        self.smtp_host = \
            smtp_host if isinstance(smtp_host, six.string_types) else ''

        # Now detect secure mode
        self.secure_mode = self.default_secure_mode \
            if not isinstance(secure_mode, six.string_types) \
            else secure_mode.lower()
        if self.secure_mode not in SECURE_MODES:
            msg = 'The secure mode specified ({}) is invalid.'\
                  .format(secure_mode)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Apply any defaults based on certain known configurations
        self.NotifyEmailDefaults()

        return

    def NotifyEmailDefaults(self):
        """
        A function that prefills defaults based on the email
        it was provided.
        """

        if self.smtp_host:
            # SMTP Server was explicitly specified, therefore it is assumed
            # the caller knows what he's doing and is intentionally
            # over-riding any smarts to be applied
            return

        for i in range(len(EMAIL_TEMPLATES)):  # pragma: no branch
            self.logger.debug('Scanning %s against %s' % (
                self.from_addr, EMAIL_TEMPLATES[i][0]
            ))
            match = EMAIL_TEMPLATES[i][1].match(self.from_addr)
            if match:
                self.logger.info(
                    'Applying %s Defaults' %
                    EMAIL_TEMPLATES[i][0],
                )
                self.port = EMAIL_TEMPLATES[i][2]\
                    .get('port', self.port)
                self.secure = EMAIL_TEMPLATES[i][2]\
                    .get('secure', self.secure)
                self.secure_mode = EMAIL_TEMPLATES[i][2]\
                    .get('secure_mode', self.secure_mode)
                self.smtp_host = EMAIL_TEMPLATES[i][2]\
                    .get('smtp_host', self.smtp_host)

                if self.smtp_host is None:
                    # default to our host
                    self.smtp_host = self.host

                # Adjust email login based on the defined usertype. If no entry
                # was specified, then we default to having them all set (which
                # basically implies that there are no restrictions and use use
                # whatever was specified)
                login_type = EMAIL_TEMPLATES[i][2]\
                    .get('login_type', [])

                if login_type:
                    # only apply additional logic to our user if a login_type
                    # was specified.
                    if is_email(self.user) and \
                       WebBaseLogin.EMAIL not in login_type:
                        # Email specified but login type
                        # not supported; switch it to user id
                        self.user = match.group('id')

                    elif WebBaseLogin.USERID not in login_type:
                        # user specified but login type
                        # not supported; switch it to email
                        self.user = '{}@{}'.format(self.user, self.host)

                break

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Email Notification
        """

        from_name = self.from_name
        if not from_name:
            from_name = self.app_desc

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the targets list
        emails = list(self.targets)
        while len(emails):
            # Get our email to notify
            to_addr = emails.pop(0)

            if not is_email(to_addr):
                self.logger.warning(
                    'Invalid ~To~ email specified: {}'.format(to_addr))
                has_error = True
                continue

            self.logger.debug(
                'Email From: {} <{}>'.format(from_name, self.from_addr))
            self.logger.debug('Email To: {}'.format(to_addr))
            self.logger.debug('Login ID: {}'.format(self.user))
            self.logger.debug(
                'Delivery: {}:{}'.format(self.smtp_host, self.port))

            # Prepare Email Message
            if self.notify_format == NotifyFormat.HTML:
                email = MIMEText(body, 'html')

            else:
                email = MIMEText(body, 'plain')

            email['Subject'] = title
            email['From'] = '{} <{}>'.format(from_name, self.from_addr)
            email['To'] = to_addr
            email['Date'] = \
                datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
            email['X-Application'] = self.app_id

            # bind the socket variable to the current namespace
            socket = None

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                self.logger.debug('Connecting to remote SMTP server...')
                socket_func = smtplib.SMTP
                if self.secure and self.secure_mode == SecureMailMode.SSL:
                    self.logger.debug('Securing connection with SSL...')
                    socket_func = smtplib.SMTP_SSL

                socket = socket_func(
                    self.smtp_host,
                    self.port,
                    None,
                    timeout=self.timeout,
                )

                if self.secure and self.secure_mode == SecureMailMode.STARTTLS:
                    # Handle Secure Connections
                    self.logger.debug('Securing connection with STARTTLS...')
                    socket.starttls()

                if self.user and self.password:
                    # Apply Login credetials
                    self.logger.debug('Applying user credentials...')
                    socket.login(self.user, self.password)

                # Send the email
                socket.sendmail(
                    self.from_addr, to_addr, email.as_string())

                self.logger.info(
                    'Sent Email notification to "{}".'.format(to_addr))

            except (SocketError, smtplib.SMTPException, RuntimeError) as e:
                self.logger.warning(
                    'A Connection error occured sending Email '
                    'notification to {}.'.format(self.smtp_host))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True

            finally:
                # Gracefully terminate the connection with the server
                if socket is not None:  # pragma: no branch
                    socket.quit()

        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'from': self.from_addr,
            'name': self.from_name,
            'mode': self.secure_mode,
            'smtp': self.smtp_host,
            'timeout': self.timeout,
            'user': self.user,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        # pull email suffix from username (if present)
        user = self.user.split('@')[0]

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=NotifyEmail.quote(user, safe=''),
                password=NotifyEmail.quote(self.password, safe=''),
            )
        else:
            # user url
            auth = '{user}@'.format(
                user=NotifyEmail.quote(user, safe=''),
            )

        # Default Port setup
        default_port = \
            self.default_secure_port if self.secure else self.default_port

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1 and self.targets[0] == self.from_addr)

        return '{schema}://{auth}{hostname}{port}/{targets}?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=NotifyEmail.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            targets='' if has_targets else '/'.join(
                [NotifyEmail.quote(x, safe='') for x in self.targets]),
            args=NotifyEmail.urlencode(args),
        )

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

        # The From address is a must; either through the use of templates
        # from= entry and/or merging the user and hostname together, this
        # must be calculated or parse_url will fail.
        from_addr = ''

        # The server we connect to to send our mail to
        smtp_host = ''

        # Get our potential email targets; if none our found we'll just
        # add one to ourselves
        results['targets'] = NotifyEmail.split_path(results['fullpath'])

        # Attempt to detect 'from' email address
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            from_addr = NotifyEmail.unquote(results['qsd']['from'])

        # Attempt to detect 'to' email address
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyEmail.parse_list(results['qsd']['to'])

        if 'name' in results['qsd'] and len(results['qsd']['name']):
            # Extract from name to associate with from address
            results['from_name'] = NotifyEmail.unquote(results['qsd']['name'])

        if 'timeout' in results['qsd'] and len(results['qsd']['timeout']):
            # Extract the timeout to associate with smtp server
            results['timeout'] = results['qsd']['timeout']

        # Store SMTP Host if specified
        if 'smtp' in results['qsd'] and len(results['qsd']['smtp']):
            # Extract the smtp server
            smtp_host = NotifyEmail.unquote(results['qsd']['smtp'])

        if 'mode' in results['qsd'] and len(results['qsd']['mode']):
            # Extract the secure mode to over-ride the default
            results['secure_mode'] = results['qsd']['mode'].lower()

        results['from_addr'] = from_addr
        results['smtp_host'] = smtp_host

        return results
