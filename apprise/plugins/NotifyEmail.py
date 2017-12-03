# -*- coding: utf-8 -*-
#
# Email Notify Wrapper
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

import re

from datetime import datetime
from smtplib import SMTP
from smtplib import SMTPException
from socket import error as SocketError

from email.mime.text import MIMEText

from ..utils import compat_is_basestring
from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat


class WebBaseLogin(object):
    """
    This class is just used in conjunction of the default emailers
    to best formulate a login to it using the data detected
    """
    # User Login must be Email Based
    EMAIL = 'Email'

    # User Login must UserID Based
    USERID = 'UserID'


# To attempt to make this script stupid proof, if we detect an email address
# that is part of the this table, we can pre-use a lot more defaults if they
# aren't otherwise specified on the users input.
WEBBASE_LOOKUP_TABLE = (
    # Google GMail
    (
        'Google Mail',
        re.compile('^(?P<id>[^@]+)@(?P<domain>gmail\.com)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp.gmail.com',
            'secure': True,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Pronto Mail
    (
        'Pronto Mail',
        re.compile('^(?P<id>[^@]+)@(?P<domain>prontomail\.com)$', re.I),
        {
            'port': 465,
            'smtp_host': 'secure.emailsrvr.com',
            'secure': True,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Microsoft Hotmail
    (
        'Microsoft Hotmail',
        re.compile('^(?P<id>[^@]+)@(?P<domain>(hotmail|live)\.com)$', re.I),
        {
            'port': 587,
            'smtp_host': 'smtp.live.com',
            'secure': True,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Yahoo Mail
    (
        'Yahoo Mail',
        re.compile('^(?P<id>[^@]+)@(?P<domain>yahoo\.(ca|com))$', re.I),
        {
            'port': 465,
            'smtp_host': 'smtp.mail.yahoo.com',
            'secure': True,
            'login_type': (WebBaseLogin.EMAIL, )
        },
    ),

    # Catch All
    (
        'Custom',
        re.compile('^(?P<id>[^@]+)@(?P<domain>.+)$', re.I),
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

    # The default simple (insecure) protocol
    protocol = 'mailto'

    # The default secure protocol
    secure_protocol = 'mailtos'

    # Default Non-Encryption Port
    default_port = 25

    # Default Secure Port
    default_secure_port = 587

    # Default SMTP Timeout (in seconds)
    connect_timeout = 15

    def __init__(self, to, notify_format, **kwargs):
        """
        Initialize Email Object
        """
        super(NotifyEmail, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            notify_format=notify_format,
            **kwargs)

        # Store To Addr
        self.to_addr = to

        # Handle SMTP vs SMTPS (Secure vs UnSecure)
        if not self.port:
            if self.secure:
                self.port = self.default_secure_port

            else:
                self.port = self.default_port

        # Email SMTP Server Timeout
        try:
            self.timeout = int(kwargs.get('timeout', self.connect_timeout))

        except (ValueError, TypeError):
            self.timeout = self.connect_timeout

        # Now we want to construct the To and From email
        # addresses from the URL provided
        self.from_name = kwargs.get('name', 'NZB Notification')
        self.from_addr = kwargs.get('from', None)
        if not self.from_addr:
            # Keep trying to be clever and make it equal to the to address
            self.from_addr = self.to_addr

        if not compat_is_basestring(self.to_addr):
            raise TypeError('No valid ~To~ email address specified.')

        if not NotifyBase.is_email(self.to_addr):
            raise TypeError('Invalid ~To~ email format: %s' % self.to_addr)

        if not compat_is_basestring(self.from_addr):
            raise TypeError('No valid ~From~ email address specified.')

        match = NotifyBase.is_email(self.from_addr)
        if not match:
            # Parse Source domain based on from_addr
            raise TypeError('Invalid ~From~ email format: %s' % self.to_addr)

        # Now detect the SMTP Server
        self.smtp_host = kwargs.get('smtp_host', None)

        # Apply any defaults based on certain known configurations
        self.NotifyEmailDefaults()

        # Using the match, we want to extract the user id and domain
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

        for i in range(len(WEBBASE_LOOKUP_TABLE)):
            self.logger.debug('Scanning %s against %s' % (
                self.to_addr, WEBBASE_LOOKUP_TABLE[i][0]
            ))
            match = WEBBASE_LOOKUP_TABLE[i][1].match(self.to_addr)
            if match:
                self.logger.info(
                    'Applying %s Defaults' %
                    WEBBASE_LOOKUP_TABLE[i][0],
                )
                self.port = WEBBASE_LOOKUP_TABLE[i][2]\
                    .get('port', self.port)
                self.secure = WEBBASE_LOOKUP_TABLE[i][2]\
                    .get('secure', self.secure)

                self.smtp_host = WEBBASE_LOOKUP_TABLE[i][2]\
                    .get('smtp_host', self.smtp_host)

                if self.smtp_host is None:
                    # Detect Server if possible
                    self.smtp_host = re.split('[\s@]+', self.from_addr)[-1]

                # Adjust email login based on the defined
                # usertype
                login_type = WEBBASE_LOOKUP_TABLE[i][2]\
                    .get('login_type', [])

                if NotifyBase.is_email(self.user) and \
                   WebBaseLogin.EMAIL not in login_type:
                    # Email specified but login type
                    # not supported; switch it to user id
                    self.user = match.group('id')

                elif WebBaseLogin.USERID not in login_type:
                    # user specified but login type
                    # not supported; switch it to email
                    self.user = '%s@%s' % (self.user, self.host)

                break

    def notify(self, title, body, **kwargs):
        """
        Perform Email Notification
        """

        self.logger.debug('Email From: %s <%s>' % (
            self.from_addr, self.from_name))
        self.logger.debug('Email To: %s' % (self.to_addr))
        self.logger.debug('Login ID: %s' % (self.user))
        self.logger.debug('Delivery: %s:%d' % (self.smtp_host, self.port))

        # Prepare Email Message
        if self.notify_format == NotifyFormat.HTML:
            email = MIMEText(body, 'html')
            email['Content-Type'] = 'text/html'

        else:
            email = MIMEText(body, 'text')
            email['Content-Type'] = 'text/plain'

        email['Subject'] = title
        email['From'] = '%s <%s>' % (self.from_name, self.from_addr)
        email['To'] = self.to_addr
        email['Date'] = datetime.utcnow()\
                                .strftime("%a, %d %b %Y %H:%M:%S +0000")
        email['X-Application'] = self.app_id

        try:
            self.logger.debug('Connecting to remote SMTP server...')
            socket = SMTP(
                self.smtp_host,
                self.port,
                None,
                timeout=self.timeout,
            )

            if self.secure:
                # Handle Secure Connections
                self.logger.debug('Securing connection with TLS...')
                socket.starttls()

            if self.user and self.password:
                # Apply Login credetials
                self.logger.debug('Applying user credentials...')
                socket.login(self.user, self.password)

            # Send the email
            socket.sendmail(self.from_addr, self.to_addr, email.as_string())

            self.logger.info('Sent Email notification to "%s".' % (
                self.to_addr,
            ))

        except (SocketError, SMTPException) as e:
            self.logger.warning(
                'A Connection error occured sending Email '
                'notification to %s.' % self.smtp_host)
            self.logger.debug('Socket Exception: %s' % str(e))
            # Return; we're done
            return False

        try:
            socket.quit()

        except:
            # no problem
            pass

        return True

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

        # Apply our settings now

        # Default Format is HTML
        results['notify_format'] = NotifyFormat.HTML

        to_addr = ''
        from_addr = ''
        smtp_host = ''

        if 'format' in results['qsd'] and len(results['qsd']['format']):
            # Extract email format (Text/Html)
            try:
                format = NotifyBase.unquote(results['qsd']['format']).lower()
                if len(format) > 0 and format[0] == 't':
                    results['notify_format'] = NotifyFormat.TEXT

            except AttributeError:
                pass

        # get 'To' email address
        try:
            to_addr = filter(bool, NotifyBase.split_path(results['host']))[0]

        except (AttributeError, IndexError):
            # No problem, we have other ways of getting
            # the To address
            pass

        if not NotifyBase.is_email(to_addr):
            if results['user']:
                # Try to be clever and build a potential
                # email address based on what we've been provided
                to_addr = '%s@%s' % (
                    re.split('[\s@]+', results['user'])[0],
                    re.split('[\s@]+', to_addr)[-1],
                )

                if not NotifyBase.is_email(to_addr):
                    NotifyBase.logger.error(
                        '%s does not contain a recipient email.' %
                        NotifyBase.unquote(results['url'].lstrip('/')),
                    )
                    return None

        # Attempt to detect 'from' email address
        from_addr = to_addr
        try:
            if 'from' in results['qsd'] and len(results['qsd']['from']):
                from_addr = results['qsd']['from']
                if not NotifyBase.is_email(results['qsd']['from']):
                    # Lets be clever and attempt to make the from
                    # address email
                    from_addr = '%s@%s' % (
                        re.split('[\s@]+', from_addr)[0],
                        re.split('[\s@]+', to_addr)[-1],
                    )

                if not NotifyBase.is_email(from_addr):
                    NotifyBase.logger.error(
                        '%s does not contain a from address.' %
                        NotifyBase.unquote(results['url'].lstrip('/')),
                    )
                    return None

        except AttributeError:
            pass

        try:
            if 'name' in results['qsd'] and len(results['qsd']['name']):
                # Extract from name to associate with from address
                results['name'] = NotifyBase.unquote(results['qsd']['name'])

        except AttributeError:
            pass

        try:
            if 'timeout' in results['qsd'] and len(results['qsd']['timeout']):
                # Extract the timeout to associate with smtp server
                results['timeout'] = NotifyBase.unquote(
                    results['qsd']['timeout'])

        except AttributeError:
            pass

        # Store SMTP Host if specified
        try:
            # Extract from password to associate with smtp server
            if 'smtp' in results['qsd'] and len(results['qsd']['smtp']):
                smtp_host = NotifyBase.unquote(results['qsd']['smtp'])

        except AttributeError:
            pass

        results['to'] = to_addr
        results['from'] = from_addr
        results['smtp_host'] = smtp_host

        return results
