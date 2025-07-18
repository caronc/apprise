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

import os
import socket

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool
from .base import NotifyBase


class syslog:
    """Extrapoloated information from the syslog library so that this plugin
    would not be dependent on it."""

    # Notification Categories
    LOG_KERN = 0
    LOG_USER = 8
    LOG_MAIL = 16
    LOG_DAEMON = 24
    LOG_AUTH = 32
    LOG_SYSLOG = 40
    LOG_LPR = 48
    LOG_NEWS = 56
    LOG_UUCP = 64
    LOG_CRON = 72
    LOG_LOCAL0 = 128
    LOG_LOCAL1 = 136
    LOG_LOCAL2 = 144
    LOG_LOCAL3 = 152
    LOG_LOCAL4 = 160
    LOG_LOCAL5 = 168
    LOG_LOCAL6 = 176
    LOG_LOCAL7 = 184

    # Notification Types
    LOG_INFO = 6
    LOG_NOTICE = 5
    LOG_WARNING = 4
    LOG_CRIT = 2


class SyslogFacility:
    """All of the supported facilities."""

    KERN = "kern"
    USER = "user"
    MAIL = "mail"
    DAEMON = "daemon"
    AUTH = "auth"
    SYSLOG = "syslog"
    LPR = "lpr"
    NEWS = "news"
    UUCP = "uucp"
    CRON = "cron"
    LOCAL0 = "local0"
    LOCAL1 = "local1"
    LOCAL2 = "local2"
    LOCAL3 = "local3"
    LOCAL4 = "local4"
    LOCAL5 = "local5"
    LOCAL6 = "local6"
    LOCAL7 = "local7"


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

# Used as a lookup when handling the Apprise -> Syslog Mapping
SYSLOG_PUBLISH_MAP = {
    NotifyType.INFO: syslog.LOG_INFO,
    NotifyType.SUCCESS: syslog.LOG_NOTICE,
    NotifyType.FAILURE: syslog.LOG_CRIT,
    NotifyType.WARNING: syslog.LOG_WARNING,
}


class NotifyRSyslog(NotifyBase):
    """A wrapper for Remote Syslog Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Remote Syslog"

    # The services URL
    service_url = "https://tools.ietf.org/html/rfc5424"

    # The default protocol
    protocol = "rsyslog"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_rsyslog"

    # Disable throttle rate for RSyslog requests
    request_rate_per_sec = 0

    # Define object templates
    templates = (
        "{schema}://{host}",
        "{schema}://{host}:{port}",
        "{schema}://{host}/{facility}",
        "{schema}://{host}:{port}/{facility}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "facility": {
                "name": _("Facility"),
                "type": "choice:string",
                "values": list(SYSLOG_FACILITY_MAP),
                "default": SyslogFacility.USER,
                "required": True,
            },
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
                "default": 514,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "facility": {
                # We map back to the same element defined in template_tokens
                "alias_of": "facility",
            },
            "logpid": {
                "name": _("Log PID"),
                "type": "bool",
                "default": True,
                "map_to": "log_pid",
            },
        },
    )

    def __init__(self, facility=None, log_pid=True, **kwargs):
        """Initialize RSyslog Object."""
        super().__init__(**kwargs)

        if facility:
            try:
                self.facility = SYSLOG_FACILITY_MAP[facility]

            except KeyError:
                msg = f"An invalid syslog facility ({facility}) was specified."
                self.logger.warning(msg)
                raise TypeError(msg) from None

        else:
            self.facility = SYSLOG_FACILITY_MAP[
                self.template_tokens["facility"]["default"]
            ]

        # Include PID with each message.
        self.log_pid = log_pid

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform RSyslog Notification."""

        if title:
            # Format title
            body = f"{title}: {body}"

        # Always call throttle before any remote server i/o is made
        self.throttle()
        host = self.host
        port = (
            self.port if self.port else self.template_tokens["port"]["default"]
        )

        priority = SYSLOG_PUBLISH_MAP[notify_type] + self.facility * 8
        payload = f"<{priority}>- {os.getpid()} {body}" \
            if self.log_pid else f"<{priority}>- {body}"

        # send UDP packet to upstream server
        self.logger.debug(
            "RSyslog Host: %s:%d/%s",
            host,
            port,
            SYSLOG_FACILITY_RMAP[self.facility],
        )
        self.logger.debug(f"RSyslog Payload: {payload!s}")

        # our sent bytes
        sent = 0

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.socket_connect_timeout)
            sent = sock.sendto(payload.encode("utf-8"), (host, port))
            sock.close()

        except socket.gaierror as e:
            self.logger.warning(
                "A connection error occurred sending RSyslog "
                "notification to %s:%d/%s",
                host,
                port,
                SYSLOG_FACILITY_RMAP[self.facility],
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        except socket.timeout as e:
            self.logger.warning(
                "A connection timeout occurred sending RSyslog "
                "notification to %s:%d/%s",
                host,
                port,
                SYSLOG_FACILITY_RMAP[self.facility],
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        if sent < len(payload):
            self.logger.warning(
                "RSyslog sent %d byte(s) but intended to send %d byte(s)",
                sent,
                len(payload),
            )
            return False

        self.logger.info("Sent RSyslog notification.")

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.protocol,
            self.host,
            (
                self.port
                if self.port
                else self.template_tokens["port"]["default"]
            ),
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "logpid": "yes" if self.log_pid else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{hostname}{port}/{facility}/?{params}".format(
            schema=self.protocol,
            hostname=NotifyRSyslog.quote(self.host, safe=""),
            port=(
                ""
                if self.port is None
                or self.port == self.template_tokens["port"]["default"]
                else f":{self.port}"
            ),
            facility=(
                self.template_tokens["facility"]["default"]
                if self.facility not in SYSLOG_FACILITY_RMAP
                else SYSLOG_FACILITY_RMAP[self.facility]
            ),
            params=NotifyRSyslog.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        tokens = []

        # Get our path values
        tokens.extend(NotifyRSyslog.split_path(results["fullpath"]))

        # Initialization
        facility = None

        if tokens:
            # Store the last entry as the facility
            facility = tokens[-1].lower()

        # However if specified on the URL, that will over-ride what was
        # identified
        if "facility" in results["qsd"] and len(results["qsd"]["facility"]):
            facility = results["qsd"]["facility"].lower()

        if facility and facility not in SYSLOG_FACILITY_MAP:
            # Find first match; if no match is found we set the result
            # to the matching key.  This allows us to throw a TypeError
            # during the __init__() call. The benifit of doing this
            # check here is if we do have a valid match, we can support
            # short form matches like 'u' which will match against user
            facility = next(
                (f for f in SYSLOG_FACILITY_MAP if f.startswith(facility)),
                facility,
            )

        # Save facility if set
        if facility:
            results["facility"] = facility

        # Include PID as part of the message logged
        results["log_pid"] = parse_bool(
            results["qsd"].get(
                "logpid", NotifyRSyslog.template_args["logpid"]["default"]
            )
        )

        return results
