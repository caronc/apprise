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

import syslog

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _


class SyslogFacility:
    """
    All of the supported facilities
    """
    KERN = 'kern'
    USER = 'user'
    MAIL = 'mail'
    DAEMON = 'daemon'
    AUTH = 'auth'
    SYSLOG = 'syslog'
    LPR = 'lpr'
    NEWS = 'news'
    UUCP = 'uucp'
    CRON = 'cron'
    LOCAL0 = 'local0'
    LOCAL1 = 'local1'
    LOCAL2 = 'local2'
    LOCAL3 = 'local3'
    LOCAL4 = 'local4'
    LOCAL5 = 'local5'
    LOCAL6 = 'local6'
    LOCAL7 = 'local7'


SYSLOG_FACILITY_MAP = {
    SyslogFacility.KERN: syslog.LOG_KERN,
    SyslogFacility.USER: syslog.LOG_USER,
    SyslogFacility.MAIL: syslog.LOG_MAIL,
    SyslogFacility.DAEMON: syslog.LOG_DAEMON,
    SyslogFacility.AUTH: syslog.LOG_AUTH,
    SyslogFacility.SYSLOG: syslog.LOG_SYSLOG,
    SyslogFacility.LPR: syslog.LOG_LPR,
    SyslogFacility.NEWS: syslog.LOG_NEWS,
    SyslogFacility.UUCP: syslog.LOG_UUCP,
    SyslogFacility.CRON: syslog.LOG_CRON,
    SyslogFacility.LOCAL0: syslog.LOG_LOCAL0,
    SyslogFacility.LOCAL1: syslog.LOG_LOCAL1,
    SyslogFacility.LOCAL2: syslog.LOG_LOCAL2,
    SyslogFacility.LOCAL3: syslog.LOG_LOCAL3,
    SyslogFacility.LOCAL4: syslog.LOG_LOCAL4,
    SyslogFacility.LOCAL5: syslog.LOG_LOCAL5,
    SyslogFacility.LOCAL6: syslog.LOG_LOCAL6,
    SyslogFacility.LOCAL7: syslog.LOG_LOCAL7,
}

SYSLOG_FACILITY_RMAP = {
    syslog.LOG_KERN: SyslogFacility.KERN,
    syslog.LOG_USER: SyslogFacility.USER,
    syslog.LOG_MAIL: SyslogFacility.MAIL,
    syslog.LOG_DAEMON: SyslogFacility.DAEMON,
    syslog.LOG_AUTH: SyslogFacility.AUTH,
    syslog.LOG_SYSLOG: SyslogFacility.SYSLOG,
    syslog.LOG_LPR: SyslogFacility.LPR,
    syslog.LOG_NEWS: SyslogFacility.NEWS,
    syslog.LOG_UUCP: SyslogFacility.UUCP,
    syslog.LOG_CRON: SyslogFacility.CRON,
    syslog.LOG_LOCAL0: SyslogFacility.LOCAL0,
    syslog.LOG_LOCAL1: SyslogFacility.LOCAL1,
    syslog.LOG_LOCAL2: SyslogFacility.LOCAL2,
    syslog.LOG_LOCAL3: SyslogFacility.LOCAL3,
    syslog.LOG_LOCAL4: SyslogFacility.LOCAL4,
    syslog.LOG_LOCAL5: SyslogFacility.LOCAL5,
    syslog.LOG_LOCAL6: SyslogFacility.LOCAL6,
    syslog.LOG_LOCAL7: SyslogFacility.LOCAL7,
}


class NotifySyslog(NotifyBase):
    """
    A wrapper for Syslog Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Syslog'

    # The services URL
    service_url = 'https://tools.ietf.org/html/rfc5424'

    # The default secure protocol
    secure_protocol = 'syslog'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_syslog'

    # Disable throttle rate for Syslog requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Title to be added to body if present
    title_maxlen = 0

    # Define object templates
    templates = (
        '{schema}://_/',
    )

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'facility': {
            'name': _('Facility'),
            'type': 'choice:int',
            'values': [k for k in SYSLOG_FACILITY_MAP.keys()],
            'default': SyslogFacility.USER,
        },
        'logpid': {
            'name': _('Log PID'),
            'type': 'bool',
            'default': True,
            'map_to': 'log_pid',
        },
        'logperror': {
            'name': _('Log to STDERR'),
            'type': 'bool',
            'default': False,
            'map_to': 'log_perror',
        },
    })

    def __init__(self, facility=None, log_pid=True, log_perror=False,
                 **kwargs):
        """
        Initialize Syslog Object
        """
        super(NotifySyslog, self).__init__(**kwargs)

        if facility:
            try:
                self.facility = SYSLOG_FACILITY_MAP[facility]

            except KeyError:
                msg = 'An invalid syslog facility ' \
                      '({}) was specified.'.format(facility)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.facility = \
                SYSLOG_FACILITY_MAP[
                    self.template_args['facility']['default']]

        # Logging Options
        self.logoptions = 0

        # Include PID with each message.
        # This may not appear evident if using journalctl since the pid
        # will always display itself; however it will appear visible
        # for log_perror combinations
        self.log_pid = log_pid

        # Print to stderr as well.
        self.log_perror = log_perror

        if log_pid:
            self.logoptions |= syslog.LOG_PID

        if log_perror:
            self.logoptions |= syslog.LOG_PERROR

        # Initialize our loggig
        syslog.openlog(
            self.app_id, logoption=self.logoptions, facility=self.facility)
        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Syslog Notification
        """

        _pmap = {
            NotifyType.INFO: syslog.LOG_INFO,
            NotifyType.SUCCESS: syslog.LOG_NOTICE,
            NotifyType.FAILURE: syslog.LOG_CRIT,
            NotifyType.WARNING: syslog.LOG_WARNING,
        }

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            syslog.syslog(_pmap[notify_type], body)

        except KeyError:
            # An invalid notification type was specified
            self.logger.warning(
                'An invalid notification type '
                '({}) was specified.'.format(notify_type))
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'logperror': 'yes' if self.log_perror else 'no',
            'logpid': 'yes' if self.log_pid else 'no',
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'facility': 'info' if self.facility not in SYSLOG_FACILITY_RMAP
                        else SYSLOG_FACILITY_RMAP[self.facility],
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://_/?{args}'.format(
            schema=self.secure_protocol,
            args=NotifySyslog.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        if 'facility' in results['qsd'] and len(results['qsd']['facility']):
            key = results['qsd']['facility'].lower()

            # Find first match; if no match is found we set the result
            # to the matching key.  This allows us to throw a TypeError
            # during the __init__() call. The benifit of doing this
            # check here is if we do have a valid match, we can support
            # short form matches like 'u' which will match against user
            results['facility'] = \
                next((f for f in SYSLOG_FACILITY_MAP.keys()
                      if f.startswith(key)), key)

        # Include PID as part of the message logged
        results['log_pid'] = \
            parse_bool(results['qsd'].get('logpid', True))

        # Print to stderr as well.
        results['log_perror'] = \
            parse_bool(results['qsd'].get('logperror', False))

        return results
