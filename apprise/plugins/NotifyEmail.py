# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import dataclasses
import re
import smtplib
import typing as t
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, make_msgid
from email.header import Header
from email import charset

from socket import error as SocketError
from datetime import datetime
from datetime import timezone

from .NotifyBase import NotifyBase
from ..URLBase import PrivacyMode
from ..common import NotifyFormat, NotifyType
from ..conversion import convert_between
from ..utils import is_email, parse_emails, is_hostname
from ..AppriseLocale import gettext_lazy as _
from ..logger import logger

# Globally Default encoding mode set to Quoted Printable.
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')


class WebBaseLogin:
    """
    This class is just used in conjunction of the default emailers
    to best formulate a login to it using the data detected
    """
    # User Login must be Email Based
    EMAIL = 'Email'

    # User Login must UserID Based
    USERID = 'UserID'


# Secure Email Modes
class SecureMailMode:
    INSECURE = "insecure"
    SSL = "ssl"
    STARTTLS = "starttls"


# Define all of the secure modes (used during validation)
SECURE_MODES = {
    SecureMailMode.STARTTLS: {
        'default_port': 587,
    },
    SecureMailMode.SSL: {
        'default_port': 465,
    },
    SecureMailMode.INSECURE: {
        'default_port': 25,
    },
}

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
            r'(?P<domain>(hotmail|live)\.com(\.au)?)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp-mail.outlook.com',
            'secure': True,
            'secure_mode': SecureMailMode.STARTTLS,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Microsoft Outlook
    (
        'Microsoft Outlook',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>(smtp\.)?outlook\.com(\.au)?)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp.outlook.com',
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

    # Comcast.net
    (
        'Comcast.net',
        re.compile(
            r'^((?P<label>[^+]+)\+)?(?P<id>[^@]+)@'
            r'(?P<domain>(comcast)\.net)$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.comcast.net',
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


@dataclasses.dataclass
class EmailMessage:
    recipient: str
    to_addrs: t.List[str]
    body: str


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
                 **kwargs):
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
        self.NotifyEmailDefaults(secure_mode=secure_mode, **kwargs)

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

        return

    def NotifyEmailDefaults(self, secure_mode=None, port=None, **kwargs):
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
                # the secure flag can not be altered if defined in the template
                self.secure = EMAIL_TEMPLATES[i][2]\
                    .get('secure', self.secure)

                # The SMTP Host check is already done above; if it was
                # specified we wouldn't even reach this part of the code.
                self.smtp_host = EMAIL_TEMPLATES[i][2]\
                    .get('smtp_host', self.smtp_host)

                # The following can be over-ridden if defined manually in the
                # Apprise URL.  Otherwise they take on the template value
                if not port:
                    self.port = EMAIL_TEMPLATES[i][2]\
                        .get('port', self.port)
                if not secure_mode:
                    self.secure_mode = EMAIL_TEMPLATES[i][2]\
                        .get('secure_mode', self.secure_mode)

                # Adjust email login based on the defined usertype. If no entry
                # was specified, then we default to having them all set (which
                # basically implies that there are no restrictions and use use
                # whatever was specified)
                login_type = EMAIL_TEMPLATES[i][2].get('login_type', [])
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

    def _get_charset(self, input_string):
        """
        Get utf-8 charset if non ascii string only

        Encode an ascii string to utf-8 is bad for email deliverability
        because some anti-spam gives a bad score for that
        like SUBJ_EXCESS_QP flag on Rspamd
        """
        if not input_string:
            return None
        return 'utf-8' if not all(ord(c) < 128 for c in input_string) else None

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform Email Notification
        """

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                'There are no Email recipients to notify')
            return False

        messages: t.List[EmailMessage] = []

        # Create a copy of the targets list
        emails = list(self.targets)
        while len(emails):
            # Get our email to notify
            to_name, to_addr = emails.pop(0)

            # Strip target out of cc list if in To or Bcc
            cc = (self.cc - self.bcc - set([to_addr]))

            # Strip target out of bcc list if in To
            bcc = (self.bcc - set([to_addr]))

            # Strip target out of reply_to list if in To
            reply_to = (self.reply_to - set([to_addr]))

            # Format our cc addresses to support the Name field
            cc = [formataddr(
                (self.names.get(addr, False), addr), charset='utf-8')
                for addr in cc]

            # Format our bcc addresses to support the Name field
            bcc = [formataddr(
                (self.names.get(addr, False), addr), charset='utf-8')
                for addr in bcc]

            if reply_to:
                # Format our reply-to addresses to support the Name field
                reply_to = [formataddr(
                    (self.names.get(addr, False), addr), charset='utf-8')
                    for addr in reply_to]

            self.logger.debug(
                'Email From: {}'.format(
                    formataddr(self.from_addr, charset='utf-8')))

            self.logger.debug('Email To: {}'.format(to_addr))
            if cc:
                self.logger.debug('Email Cc: {}'.format(', '.join(cc)))
            if bcc:
                self.logger.debug('Email Bcc: {}'.format(', '.join(bcc)))
            if reply_to:
                self.logger.debug(
                    'Email Reply-To: {}'.format(', '.join(reply_to))
                )
            self.logger.debug('Login ID: {}'.format(self.user))
            self.logger.debug(
                'Delivery: {}:{}'.format(self.smtp_host, self.port))

            # Prepare Email Message
            if self.notify_format == NotifyFormat.HTML:
                base = MIMEMultipart("alternative")
                base.attach(MIMEText(
                    convert_between(
                        NotifyFormat.HTML, NotifyFormat.TEXT, body),
                    'plain', 'utf-8')
                )
                base.attach(MIMEText(body, 'html', 'utf-8'))
            else:
                base = MIMEText(body, 'plain', 'utf-8')

            if attach and self.attachment_support:
                mixed = MIMEMultipart("mixed")
                mixed.attach(base)
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
                        mixed.attach(app)
                base = mixed

            # Apply any provided custom headers
            for k, v in self.headers.items():
                base[k] = Header(v, self._get_charset(v))

            base['Subject'] = Header(title, self._get_charset(title))
            base['From'] = formataddr(self.from_addr, charset='utf-8')
            base['To'] = formataddr((to_name, to_addr), charset='utf-8')
            base['Message-ID'] = make_msgid(domain=self.smtp_host)
            base['Date'] = \
                datetime.now(timezone.utc)\
                .strftime("%a, %d %b %Y %H:%M:%S +0000")
            base['X-Application'] = self.app_id

            if cc:
                base['Cc'] = ','.join(cc)

            if reply_to:
                base['Reply-To'] = ','.join(reply_to)

            message = EmailMessage(
                recipient=to_addr,
                to_addrs=[to_addr] + list(cc) + list(bcc),
                body=base.as_string())
            messages.append(message)

        return self.submit(messages)

    def submit(self, messages: t.List[EmailMessage]):

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

            if self.user and self.password:
                # Apply Login credetials
                self.logger.debug('Applying user credentials...')
                socket.login(self.user, self.password)

            # Send the emails
            for message in messages:
                try:
                    socket.sendmail(
                        self.from_addr[1],
                        message.to_addrs,
                        message.body)

                    self.logger.info(
                        f'Sent Email notification to "{message.recipient}".')
                except (SocketError, smtplib.SMTPException, RuntimeError) as e:
                    self.logger.warning(
                        f'Sending email to "{message.recipient}" failed. '
                        f'Reason: {e}')

                    # Mark as failure
                    has_error = True

        except (SocketError, smtplib.SMTPException, RuntimeError) as e:
            self.logger.warning(
                f'Connection error while submitting email to {self.smtp_host}.'
                f' Reason: {e}')

            # Mark as failure
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
        params = {}

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

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            params['cc'] = ','.join([
                formataddr(
                    (self.names[e] if e in self.names else False, e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset='utf-8').replace(',', '%2C')
                for e in self.cc])

        if len(self.bcc) > 0:
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

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
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

        # Prepare our target lists
        results['targets'] = []

        if not is_hostname(results['host'], ipv4=False, ipv6=False,
                           underscore=False):

            if is_email(NotifyEmail.unquote(results['host'])):
                # Don't lose defined email addresses
                results['targets'].append(NotifyEmail.unquote(results['host']))

            # Detect if we have a valid hostname or not; be sure to reset it's
            # value if invalid; we'll attempt to figure this out later on
            results['host'] = ''

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
                # Depricate use of both `from=` and `name=` in the same url as
                # they will be synomomus of one another in the future.
                from_addr = formataddr(
                    (NotifyEmail.unquote(results['qsd']['name']), from_addr),
                    charset='utf-8')
                logger.warning(
                    'Email name= and from= are synonymous; '
                    'use one or the other.')

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
