# -*- coding: utf-8 -*-
#
# Email Notify Wrapper
#
# Copyright (C) 2017-2018 Chris Caron <lead2gold@gmail.com>
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
import smtplib
from socket import error as SocketError

from email.mime.text import MIMEText

from .NotifyBase import NotifyBase
from ..common import NotifyFormat


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
        re.compile(r'^(?P<id>[^@]+)@(?P<domain>gmail\.com)$', re.I),
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
        re.compile(r'^(?P<id>[^@]+)@(?P<domain>prontomail\.com)$', re.I),
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
        re.compile(r'^(?P<id>[^@]+)@(?P<domain>(hotmail|live)\.com)$', re.I),
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
        re.compile(r'^(?P<id>[^@]+)@(?P<domain>yahoo\.(ca|com))$', re.I),
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
        re.compile(r'^(?P<id>[^@]+)@(?P<domain>.+)$', re.I),
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

    def __init__(self, **kwargs):
        """
        Initialize Email Object
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
            self.timeout = int(kwargs.get('timeout', self.connect_timeout))

        except (ValueError, TypeError):
            self.timeout = self.connect_timeout

        # Now we want to construct the To and From email
        # addresses from the URL provided
        self.from_name = kwargs.get('name', None)
        self.from_addr = kwargs.get('from', None)
        self.to_addr = kwargs.get('to', self.from_addr)

        if not NotifyBase.is_email(self.from_addr):
            # Parse Source domain based on from_addr
            raise TypeError('Invalid ~From~ email format: %s' % self.from_addr)

        if not NotifyBase.is_email(self.to_addr):
            raise TypeError('Invalid ~To~ email format: %s' % self.to_addr)

        # Now detect the SMTP Server
        self.smtp_host = kwargs.get('smtp_host', '')

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

        for i in range(len(WEBBASE_LOOKUP_TABLE)):  # pragma: no branch
            self.logger.debug('Scanning %s against %s' % (
                self.to_addr, WEBBASE_LOOKUP_TABLE[i][0]
            ))
            match = WEBBASE_LOOKUP_TABLE[i][1].match(self.from_addr)
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

        from_name = self.from_name
        if not from_name:
            from_name = self.app_desc

        self.logger.debug('Email From: %s <%s>' % (
            self.from_addr, from_name))
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
        email['From'] = '%s <%s>' % (from_name, self.from_addr)
        email['To'] = self.to_addr
        email['Date'] = datetime.utcnow()\
                                .strftime("%a, %d %b %Y %H:%M:%S +0000")
        email['X-Application'] = self.app_id

        try:
            self.logger.debug('Connecting to remote SMTP server...')
            socket = smtplib.SMTP(
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

        except (SocketError, smtplib.SMTPException, RuntimeError) as e:
            self.logger.warning(
                'A Connection error occured sending Email '
                'notification to %s.' % self.smtp_host)
            self.logger.debug('Socket Exception: %s' % str(e))
            # Return; we're done
            return False

        finally:
            # Gracefully terminate the connection with the server
            socket.quit()

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
            format = NotifyBase.unquote(results['qsd']['format']).lower()
            if len(format) > 0 and format[0] == 't':
                results['notify_format'] = NotifyFormat.TEXT

        # Attempt to detect 'from' email address
        if 'from' in results['qsd'] and len(results['qsd']['from']):
            from_addr = NotifyBase.unquote(results['qsd']['from'])

        else:
            # get 'To' email address
            from_addr = '%s@%s' % (
                re.split(
                    '[\s@]+', NotifyBase.unquote(results['user']))[0],
                results.get('host', '')
            )
            # Lets be clever and attempt to make the from
            # address an email based on the to address
            from_addr = '%s@%s' % (
                re.split('[\s@]+', from_addr)[0],
                re.split('[\s@]+', from_addr)[-1],
            )

        # Attempt to detect 'to' email address
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            to_addr = NotifyBase.unquote(results['qsd']['to']).strip()

        if not to_addr:
            # Send to ourselves if not otherwise specified to do so
            to_addr = from_addr

        if 'name' in results['qsd'] and len(results['qsd']['name']):
            # Extract from name to associate with from address
            results['name'] = NotifyBase.unquote(results['qsd']['name'])

        if 'timeout' in results['qsd'] and len(results['qsd']['timeout']):
            # Extract the timeout to associate with smtp server
            results['timeout'] = results['qsd']['timeout']

        # Store SMTP Host if specified
        if 'smtp' in results['qsd'] and len(results['qsd']['smtp']):
            # Extract the smtp server
            smtp_host = NotifyBase.unquote(results['qsd']['smtp'])

        results['to'] = to_addr
        results['from'] = from_addr
        results['smtp_host'] = smtp_host

        return results
