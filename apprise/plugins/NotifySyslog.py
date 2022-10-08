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
import os
import syslog
import socket

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_bool
from ..utils import is_hostname
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


class SyslogMode:
    # A local query
    LOCAL = "local"

    # A remote query
    REMOTE = "remote"


# webhook modes are placed ito this list for validation purposes
SYSLOG_MODES = (
    SyslogMode.LOCAL,
    SyslogMode.REMOTE,
)


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

    # Define object templates
    templates = (
        '{schema}://',
        '{schema}://{facility}',
        '{schema}://{host}',
        '{schema}://{host}:{port}',
        '{schema}://{host}/{facility}',
        '{schema}://{host}:{port}/{facility}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'facility': {
            'name': _('Facility'),
            'type': 'choice:string',
            'values': [k for k in SYSLOG_FACILITY_MAP.keys()],
            'default': SyslogFacility.USER,
        },
        'host': {
            'name': _('Hostname'),
            'type': 'string',
            'required': True,
        },
        'port': {
            'name': _('Port'),
            'type': 'int',
            'min': 1,
            'max': 65535,
            'default': 514,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'facility': {
            # We map back to the same element defined in template_tokens
            'alias_of': 'facility',
        },
        'mode': {
            'name': _('Syslog Mode'),
            'type': 'choice:string',
            'values': SYSLOG_MODES,
            'default': SyslogMode.LOCAL,
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

    def __init__(self, facility=None, mode=None, log_pid=True,
                 log_perror=False, **kwargs):
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
                    self.template_tokens['facility']['default']]

        self.mode = self.template_args['mode']['default'] \
            if not isinstance(mode, str) else mode.lower()

        if self.mode not in SYSLOG_MODES:
            msg = 'The mode specified ({}) is invalid.'.format(mode)
            self.logger.warning(msg)
            raise TypeError(msg)

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

        if title:
            # Format title
            body = '{}: {}'.format(title, body)

        # Always call throttle before any remote server i/o is made
        self.throttle()
        if self.mode == SyslogMode.LOCAL:
            try:
                syslog.syslog(_pmap[notify_type], body)

            except KeyError:
                # An invalid notification type was specified
                self.logger.warning(
                    'An invalid notification type '
                    '({}) was specified.'.format(notify_type))
                return False

        else:  # SyslogMode.REMOTE

            host = self.host
            port = self.port if self.port \
                else self.template_tokens['port']['default']
            if self.log_pid:
                payload = '<%d>- %d - %s' % (
                    _pmap[notify_type] + self.facility * 8, os.getpid(), body)

            else:
                payload = '<%d>- %s' % (
                    _pmap[notify_type] + self.facility * 8, body)

            # send UDP packet to upstream server
            self.logger.debug(
                'Syslog Host: %s:%d/%s',
                host, port, SYSLOG_FACILITY_RMAP[self.facility])
            self.logger.debug('Syslog Payload: %s' % str(payload))

            # our sent bytes
            sent = 0

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(self.socket_connect_timeout)
                sent = sock.sendto(payload.encode('utf-8'), (host, port))
                sock.close()

            except socket.gaierror as e:
                self.logger.warning(
                    'A connection error occurred sending Syslog '
                    'notification to %s:%d/%s', host, port,
                    SYSLOG_FACILITY_RMAP[self.facility]
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                return False

            except socket.timeout as e:
                self.logger.warning(
                    'A connection timeout occurred sending Syslog '
                    'notification to %s:%d/%s', host, port,
                    SYSLOG_FACILITY_RMAP[self.facility]
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                return False

            if sent < len(payload):
                self.logger.warning(
                    'Syslog sent %d byte(s) but intended to send %d byte(s)',
                    sent, len(payload))
                return False

        self.logger.info('Sent Syslog (%s) notification.', self.mode)

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'logperror': 'yes' if self.log_perror else 'no',
            'logpid': 'yes' if self.log_pid else 'no',
            'mode': self.mode,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.mode == SyslogMode.LOCAL:
            return '{schema}://{facility}/?{params}'.format(
                facility=self.template_tokens['facility']['default']
                if self.facility not in SYSLOG_FACILITY_RMAP
                else SYSLOG_FACILITY_RMAP[self.facility],
                schema=self.secure_protocol,
                params=NotifySyslog.urlencode(params),
            )

        # Remote mode:
        return '{schema}://{hostname}{port}/{facility}/?{params}'.format(
            schema=self.secure_protocol,
            hostname=NotifySyslog.quote(self.host, safe=''),
            port='' if self.port is None
            or self.port == self.template_tokens['port']['default']
            else ':{}'.format(self.port),
            facility=self.template_tokens['facility']['default']
            if self.facility not in SYSLOG_FACILITY_RMAP
            else SYSLOG_FACILITY_RMAP[self.facility],
            params=NotifySyslog.urlencode(params),
        )

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

        tokens = []
        if results['host']:
            tokens.append(NotifySyslog.unquote(results['host']))

        # Get our path values
        tokens.extend(NotifySyslog.split_path(results['fullpath']))

        facility = None
        if len(tokens) > 1 and is_hostname(tokens[0]):
            # syslog://hostname/facility
            results['mode'] = SyslogMode.REMOTE

            # Store our facility as the first path entry
            facility = tokens[-1]

        elif tokens:
            # This is a bit ambigious... it could be either:
            # syslog://facility -or- syslog://hostname

            # First lets test it as a facility; we'll correct this
            # later on if nessisary
            facility = tokens[-1]

        # However if specified on the URL, that will over-ride what was
        # identified
        if 'facility' in results['qsd'] and len(results['qsd']['facility']):
            facility = results['qsd']['facility'].lower()

        if facility and facility not in SYSLOG_FACILITY_MAP:
            # Find first match; if no match is found we set the result
            # to the matching key.  This allows us to throw a TypeError
            # during the __init__() call. The benifit of doing this
            # check here is if we do have a valid match, we can support
            # short form matches like 'u' which will match against user
            facility = next((f for f in SYSLOG_FACILITY_MAP.keys()
                             if f.startswith(facility)), facility)

        # Attempt to solve our ambiguity
        if len(tokens) == 1 and is_hostname(tokens[0]) and (
                results['port'] or facility not in SYSLOG_FACILITY_MAP):

            # facility is likely hostname; update our guessed mode
            results['mode'] = SyslogMode.REMOTE

            # Reset our facility value
            facility = None

        # Set mode if not otherwise set
        if 'mode' in results['qsd'] and len(results['qsd']['mode']):
            results['mode'] = NotifySyslog.unquote(results['qsd']['mode'])

        # Save facility if set
        if facility:
            results['facility'] = facility

        # Include PID as part of the message logged
        results['log_pid'] = parse_bool(
            results['qsd'].get(
                'logpid',
                NotifySyslog.template_args['logpid']['default']))

        # Print to stderr as well.
        results['log_perror'] = parse_bool(
            results['qsd'].get(
                'logperror',
                NotifySyslog.template_args['logperror']['default']))

        return results
