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
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from email.header import Header
from email import charset

from socket import error as SocketError
from datetime import datetime

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import is_email
from ..utils import parse_emails
from ..AppriseLocale import gettext_lazy as _

# Globally Default encoding mode set to Quoted Printable.
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')


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

    # Yandex
    (
        'Yandex',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>yandex\.(com|ru|ua|by|kz|uz|tr|fr))$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.yandex.ru',
            'secure': True,
            'secure_mode': SecureMailMode.SSL,
            'login_type': (WebBaseLogin.USERID, )
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
            'smtp_host': 'smtp-mail.outlook.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Microsoft Office 365 (Email Server)
    # You must specify an authenticated sender address in the from= settings
    # and a valid email in the to= to deliver your emails to
    (
        'Microsoft Office 365',
        re.compile(
            r'^[^@]+@(?P<domain>(smtp\.)?office365\.com)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp.office365.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
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

    # Zoho Mail (Free)
    (
        'Zoho Mail',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>zoho(mail)?\.com)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp.zoho.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # SendGrid (Email Server)
    # You must specify an authenticated sender address in the from= settings
    # and a valid email in the to= to deliver your emails to
    (
        'SendGrid',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>(\.smtp)?sendgrid\.(com|net))$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.sendgrid.net',
            'secure': True,
            'secure_mode': SecureMailMode.SSL,
            'login_type': (WebBaseLogin.USERID, )
        },
    ),

    # 163.com
    (
        '163.com',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>163\.com)$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.163.com',
            'secure': True,
            'secure_mode': SecureMailMode.SSL,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Foxmail.com
    (
        'Foxmail.com',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>(foxmail|qq)\.com)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp.qq.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
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
    })

    # Define any kwargs we're using
    template_kwargs = {
        'headers': {
            'name': _('Email Header'),
            'prefix': '+',
        },
    }

    def __init__(self, smtp_host=None, from_name=None,
                 from_addr=None, secure_mode=None, targets=None, cc=None,
                 bcc=None, headers=None, **kwargs):
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

        # Now we want to construct the To and From email
        # addresses from the URL provided
        self.from_addr = from_addr

        if self.user and not self.from_addr:
            # detect our email address
            self.from_addr = '{}@{}'.format(
                re.split(r'[\s@]+', self.user)[0],
                self.host,
            )

        result = is_email(self.from_addr)
        if not result:
            # Parse Source domain based on from_addr
            msg = 'Invalid ~From~ email specified: {}'.format(self.from_addr)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our email address
        self.from_addr = result['full_email']

        # Set our from name
        self.from_name = from_name if from_name else result['name']

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

        # Apply any defaults based on certain known configurations
        self.NotifyEmailDefaults()

        # if there is still no smtp_host then we fall back to the hostname
        if not self.smtp_host:
            self.smtp_host = self.host

        return

    def NotifyEmailDefaults(self):
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

        for i in range(len(EMAIL_TEMPLATES)):  # pragma: no branch
            self.logger.trace('Scanning %s against %s' % (
                from_addr, EMAIL_TEMPLATES[i][0]
            ))
            match = EMAIL_TEMPLATES[i][1].match(from_addr)
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

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform Email Notification
        """

        # Initialize our default from name
        from_name = self.from_name if self.from_name else self.app_desc

        # error tracking (used for function return)
        has_error = False

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                'There are no Email recipients to notify')
            return False

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

            self.logger.debug(
                'Email From: {} <{}>'.format(from_name, self.from_addr))
            self.logger.debug('Email To: {}'.format(to_addr))
            if cc:
                self.logger.debug('Email Cc: {}'.format(', '.join(cc)))
            if bcc:
                self.logger.debug('Email Bcc: {}'.format(', '.join(bcc)))
            self.logger.debug('Login ID: {}'.format(self.user))
            self.logger.debug(
                'Delivery: {}:{}'.format(self.smtp_host, self.port))

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
                        app = MIMEApplication(abody.read())
                        app.set_type(attachment.mimetype)

                        app.add_header(
                            'Content-Disposition',
                            'attachment; filename="{}"'.format(
                                Header(attachment.name, 'utf-8')),
                        )

                        base.attach(app)

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
                    timeout=self.socket_connect_timeout,
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
                    self.from_addr,
                    [to_addr] + list(cc) + list(bcc),
                    base.as_string())

                self.logger.info(
                    'Sent Email notification to "{}".'.format(to_addr))

            except (SocketError, smtplib.SMTPException, RuntimeError) as e:
                self.logger.warning(
                    'A Connection error occurred sending Email '
                    'notification to {}.'.format(self.smtp_host))
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True

            finally:
                # Gracefully terminate the connection with the server
                if socket is not None:  # pragma: no branch
                    socket.quit()

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define an URL parameters
        params = {
            'from': self.from_addr,
            'mode': self.secure_mode,
            'smtp': self.smtp_host,
            'user': self.user,
        }

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.from_name:
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
        default_port = \
            self.default_secure_port if self.secure else self.default_port

        # a simple boolean check as to whether we display our target emails
        # or not
        has_targets = \
            not (len(self.targets) == 1
                 and self.targets[0][1] == self.from_addr)

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
            results['targets'].append(results['qsd']['to'])

        if 'name' in results['qsd'] and len(results['qsd']['name']):
            # Extract from name to associate with from address
            results['from_name'] = NotifyEmail.unquote(results['qsd']['name'])

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

        results['from_addr'] = from_addr
        results['smtp_host'] = smtp_host

        # Add our Meta Headers that the user can provide with their outbound
        # emails
        results['headers'] = {NotifyBase.unquote(x): NotifyBase.unquote(y)
                              for x, y in results['qsd+'].items()}

        return results
