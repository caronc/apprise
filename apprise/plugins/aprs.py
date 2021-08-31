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
#
# To use this plugin, you need to be a licensed ham radio operator
#
# Plugin constraints:
#
# - message length = 67 chars max.
# - message content = ASCII 7 bit
# - APRS messages will be sent without msg ID, meaning that
#   ham radio operators cannot acknowledge them
# - Bring your own APRS-IS passcode. If you don't know what
#   this is or how to get it, then this plugin is not for you
# - Do NOT change the Device/ToCall ID setting UNLESS this
#   module is used outside of Apprise. This identifier helps
#   the ham radio community with determining the software behind
#   a given APRS message.
# - With great (ham radio) power comes great responsibility; do
#   not use this plugin for spamming other ham radio operators

#
# In order to digest text input which is not in plain English,
# users can install the optional 'unidecode' package as part
# of their venv environment. Details: see plugin description
#

#
# You're done at this point, you only need to know your user/pass that
# you signed up with.

#  The following URLs would be accepted by Apprise:
#   - aprs://{user}:{password}@{callsign}
#   - aprs://{user}:{password}@{callsign1}/{callsign2}

# Optional parameters:
#   - locale --> APRS-IS target server to connect with
#                Default: EURO --> 'euro.aprs2.net'
#                Details: https://www.aprs2.net/

#
# APRS message format specification:
# http://www.aprs.org/doc/APRS101.PDF
#

import socket
import sys
from itertools import chain
from .base import NotifyBase
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..common import NotifyType
from ..utils import is_call_sign
from ..utils import parse_call_sign
from .. import __version__
import re

# Fixed APRS-IS server locales
# Default is 'EURO'
# See https://www.aprs2.net/ for details
# Select the rotating server in case you
# don"t care about a specific locale
APRS_LOCALES = {
    "NOAM": "noam.aprs2.net",
    "SOAM": "soam.aprs2.net",
    "EURO": "euro.aprs2.net",
    "ASIA": "asia.aprs2.net",
    "AUNZ": "aunz.aprs2.net",
    "ROTA": "rotate.aprs2.net",
}

# Identify all unsupported characters
APRS_BAD_CHARMAP = {
    r"Ä": "Ae",
    r"Ö": "Oe",
    r"Ü": "Ue",
    r"ä": "ae",
    r"ö": "oe",
    r"ü": "ue",
    r"ß": "ss",
}

# Our compiled mapping of bad characters
APRS_COMPILED_MAP = re.compile(
    r'(' + '|'.join(APRS_BAD_CHARMAP.keys()) + r')')


class NotifyAprs(NotifyBase):
    """
    A wrapper for APRS Notifications via APRS-IS
    """

    # The default descriptive name associated with the Notification
    service_name = "Aprs"

    # The services URL
    service_url = "https://www.aprs2.net/"

    # The default secure protocol
    secure_protocol = "aprs"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_aprs"

    # APRS default port, supported by all core servers
    # Details: https://www.aprs-is.net/Connecting.aspx
    notify_port = 10152

    # The maximum length of the APRS message body
    body_maxlen = 67

    # Apprise APRS Device ID / TOCALL ID
    # This is a FIXED value which is associated with this plugin.
    # Its value MUST NOT be changed. If you use this APRS plugin
    # code OUTSIDE of Apprise, please request your own TOCALL ID.
    # Details: see https://github.com/aprsorg/aprs-deviceid
    #
    # Do NOT use the generic "APRS" TOCALL ID !!!!!
    #
    device_id = "APPRIS"

    # A title can not be used for APRS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Helps to reduce the number of login-related errors where the
    # APRS-IS server "isn't ready yet". If we try to receive the rx buffer
    # without this grace perid in place, we may receive "incomplete" responses
    # where the login response lacks information. In case you receive too many
    # "Rx: APRS-IS msg is too short - needs to have at least two lines" error
    # messages, you might want to increase this value to a larger time span
    # Per previous experience, do not use values lower than 0.5 (seconds)
    request_rate_per_sec = 0.8

    # Encoding of retrieved content
    aprs_encoding = 'latin-1'

    # Define object templates
    templates = ("{schema}://{user}:{password}@{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("User Name"),
                "type": "string",
                "required": True,
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_callsign": {
                "name": _("Target Callsign"),
                "type": "string",
                "regex": (
                    r"^[a-z0-9]{2,5}(-[a-z0-9]{1,2})?$",
                    "i",
                ),
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
                "required": True,
            },
        }
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "to": {
                "name": _("Target Callsign"),
                "type": "string",
                "map_to": "targets",
            },
            "delay": {
                "name": _("Resend Delay"),
                "type": "float",
                "min": 0.0,
                "max": 5.0,
                "default": 0.0,
            },
            "locale": {
                "name": _("Locale"),
                "type": "choice:string",
                "values": APRS_LOCALES,
                "default": "EURO",
            },
        }
    )

    def __init__(self, targets=None, locale=None, delay=None, **kwargs):
        """
        Initialize APRS Object
        """
        super().__init__(**kwargs)

        # Our (future) socket sobject
        self.sock = None

        # Parse our targets
        self.targets = list()

        """
        Check if the user has provided credentials
        """
        if not (self.user and self.password):
            msg = "An APRS user/pass was not provided."
            self.logger.warning(msg)
            raise TypeError(msg)

        """
        Check if the user tries to use a read-only access
        to APRS-IS. We need to send content, meaning that
        read-only access will not work
        """
        if self.password == "-1":
            msg = "APRS read-only passwords are not supported."
            self.logger.warning(msg)
            raise TypeError(msg)

        """
        Check if the password is numeric
        """
        if not self.password.isnumeric():
            msg = "Invalid APRS-IS password"
            self.logger.warning(msg)
            raise TypeError(msg)

        """
        Convert given user name (FROM callsign) and
        device ID to to uppercase
        """
        self.user = self.user.upper()
        self.device_id = self.device_id.upper()

        """
        Check if the user has provided a locale for the
        APRS-IS-server and validate it, if necessary
        """
        if locale:
            if locale.upper() not in APRS_LOCALES:
                msg = (
                    "Unsupported APRS-IS server locale. "
                    "Received: {}. Valid: {}".format(
                        locale, ", ".join(str(x) for x in APRS_LOCALES.keys())
                    )
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        # Update our delay
        if delay is None:
            self.delay = NotifyAprs.template_args["delay"]["default"]

        else:
            try:
                self.delay = float(delay)
                if self.delay < NotifyAprs.template_args["delay"]["min"]:
                    raise ValueError()

                elif self.delay >= NotifyAprs.template_args["delay"]["max"]:
                    raise ValueError()

            except (TypeError, ValueError):
                msg = "Unsupported APRS-IS delay ({}) specified. ".format(
                    delay)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Bump up our request_rate
        self.request_rate_per_sec += self.delay

        # Set the transmitter group
        self.locale = \
            NotifyAprs.template_args["locale"]["default"] \
            if not locale else locale.upper()

        # Used for URL generation afterwards only
        self.invalid_targets = list()

        for target in parse_call_sign(targets):
            # Validate targets and drop bad ones
            # We just need to know if the call sign (including SSID, if
            # provided) is valid and can then process the input as is
            result = is_call_sign(target)
            if not result:
                self.logger.warning(
                    "Dropping invalid Amateur radio call sign ({}).".format(
                        target
                    ),
                )
                self.invalid_targets.append(target.upper())
                continue

            # Store entry
            self.targets.append(target.upper())

        return

    def socket_close(self):
        """
        Closes the socket connection whereas present
        """
        if self.sock:
            try:
                self.sock.close()

            except Exception:
                # No worries if socket exception thrown on close()
                pass

            self.sock = None

    def socket_open(self):
        """
        Establishes the connection to the APRS-IS
        socket server
        """
        self.logger.debug(
            "Creating socket connection with APRS-IS {}:{}".format(
                APRS_LOCALES[self.locale], self.notify_port
            )
        )

        try:
            self.sock = socket.create_connection(
                (APRS_LOCALES[self.locale], self.notify_port),
                self.socket_connect_timeout,
            )

        except ConnectionError as e:
            self.logger.debug("Socket Exception socket_open: %s", str(e))
            self.sock = None
            return False

        except socket.gaierror as e:
            self.logger.debug("Socket Exception socket_open: %s", str(e))
            self.sock = None
            return False

        except socket.timeout as e:
            self.logger.debug(
                "Socket Timeout Exception socket_open: %s", str(e))
            self.sock = None
            return False

        except Exception as e:
            self.logger.debug("General Exception socket_open: %s", str(e))
            self.sock = None
            return False

        # We are connected.
        # getpeername() is not supported by every OS. Therefore,
        # we MAY receive an exception even though we are
        # connected successfully.
        try:
            # Get the physical host/port of the server
            host, port = self.sock.getpeername()
            # and create debug info
            self.logger.debug("Connected to {}:{}".format(host, port))

        except ValueError:
            # Seens as if we are running on an operating
            # system that does not support getpeername()
            # Create a minimal log file entry
            self.logger.debug("Connected to APRS-IS")

        # Return success
        return True

    def aprsis_login(self):
        """
        Generate the APRS-IS login string, send it to the server
        and parse the response

        Returns True/False wrt whether the login was successful
        """
        self.logger.debug("socket_login: init")

        # Check if we are connected
        if not self.sock:
            self.logger.warning("socket_login: Not connected to APRS-IS")
            return False

        # APRS-IS login string, see https://www.aprs-is.net/Connecting.aspx
        login_str = "user {0} pass {1} vers apprise {2}\r\n".format(
            self.user, self.password, __version__
        )

        # Send the data & abort in case of error
        if not self.socket_send(login_str):
            self.logger.warning(
                "socket_login: Login to APRS-IS unsuccessful,"
                " exception occurred"
            )
            self.socket_close()
            return False

        rx_buf = self.socket_receive(len(login_str) + 100)
        # Abort the remaining process in case an error has occurred
        if not rx_buf:
            self.logger.warning(
                "socket_login: Login to APRS-IS "
                "unsuccessful, exception occurred"
            )
            self.socket_close()
            return False

        # APRS-IS sends at least two lines of data
        # The data that we need is in line #2 so
        # let's split the  content and see what we have
        rx_lines = rx_buf.splitlines()
        if len(rx_lines) < 2:
            self.logger.warning(
                "socket_login: APRS-IS msg is too short"
                " - needs to have at least two lines"
            )
            self.socket_close()
            return False

        # Now split the 2nd line's content and extract
        # both call sign and login status
        try:
            _, _, callsign, status, _ = rx_lines[1].split(" ", 4)

        except ValueError:
            # ValueError is returned if there were not enough elements to
            # populate the response
            self.logger.warning(
                "socket_login: " "received invalid response from APRS-IS"
            )
            self.socket_close()
            return False

        if callsign != self.user:
            self.logger.warning(
                "socket_login: " "call signs differ: %s" % callsign
            )
            self.socket_close()
            return False

        if status.startswith("unverified"):
            self.logger.warning(
                "socket_login: "
                "invalid APRS-IS password for given call sign"
            )
            self.socket_close()
            return False

        # all validations are successful; we are connected
        return True

    def socket_send(self, tx_data):
        """
        Generic "Send data to a socket"
        """
        self.logger.debug("socket_send: init")

        # Check if we are connected
        if not self.sock:
            self.logger.warning("socket_send: Not connected to APRS-IS")
            return False

        # Encode our data if we are on Python3 or later
        payload = (
            tx_data.encode("utf-8") if sys.version_info[0] >= 3 else tx_data
        )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Try to open the socket
        # Send the content to APRS-IS
        try:
            self.sock.setblocking(True)
            self.sock.settimeout(self.socket_connect_timeout)
            self.sock.sendall(payload)

        except socket.gaierror as e:
            self.logger.warning("Socket Exception socket_send: %s" % str(e))
            self.sock = None
            return False

        except socket.timeout as e:
            self.logger.warning(
                "Socket Timeout Exception " "socket_send: %s" % str(e)
            )
            self.sock = None
            return False

        except Exception as e:
            self.logger.warning(
                "General Exception " "socket_send: %s" % str(e)
            )
            self.sock = None
            return False

        self.logger.debug("socket_send: successful")

        # mandatory on several APRS-IS servers
        # helps to reduce the number of errors where
        # the server only returns an abbreviated message
        return True

    def socket_reset(self):
        """
        Resets the socket's buffer
        """
        self.logger.debug("socket_reset: init")
        _ = self.socket_receive(0)
        self.logger.debug("socket_reset: successful")
        return True

    def socket_receive(self, rx_len):
        """
        Generic "Receive data from a socket"
        """
        self.logger.debug("socket_receive: init")

        # Check if we are connected
        if not self.sock:
            self.logger.warning("socket_receive: not connected to APRS-IS")
            return False

        # len is zero in case we intend to
        # reset the socket
        if rx_len > 0:
            self.logger.debug("socket_receive: Receiving data from APRS-IS")

        # Receive content from the socket
        try:
            self.sock.setblocking(False)
            self.sock.settimeout(self.socket_connect_timeout)
            rx_buf = self.sock.recv(rx_len)

        except socket.gaierror as e:
            self.logger.warning(
                "Socket Exception socket_receive: %s" % str(e)
            )
            self.sock = None
            return False

        except socket.timeout as e:
            self.logger.warning(
                "Socket Timeout Exception " "socket_receive: %s" % str(e)
            )
            self.sock = None
            return False

        except Exception as e:
            self.logger.warning(
                "General Exception " "socket_receive: %s" % str(e)
            )
            self.sock = None
            return False

        rx_buf = (
            rx_buf.decode(self.aprs_encoding)
            if sys.version_info[0] >= 3 else rx_buf
        )

        # There will be no data in case we reset the socket
        if rx_len > 0:
            self.logger.debug("Received content: {}".format(rx_buf))

        self.logger.debug("socket_receive: successful")

        return rx_buf.rstrip()

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """
        Perform APRS Notification
        """

        if not self.targets:
            # There is no one to notify; we're done
            self.logger.warning(
                "There are no amateur radio call signs to notify"
            )
            return False

        # prepare payload
        payload = body

        # sock object is "None" if we were unable to establish a connection
        # In case of errors, the error message has already been sent
        # to the logger object
        if not self.socket_open():
            return False

        # We have established a successful connection
        # to the socket server. Now send the login information
        if not self.aprsis_login():
            return False

        # Login & authorization confirmed
        # reset what is in our buffer
        self.socket_reset()

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the targets list
        targets = list(self.targets)

        self.logger.debug("Starting Payload setup")

        # Prepare the outgoing message
        # Due to APRS's contraints, we need to do
        # a lot of filtering before we can send
        # the actual message
        #
        # First remove all characters from the
        # payload that would break APRS
        # see https://www.aprs.org/doc/APRS101.PDF pg. 71
        payload = re.sub("[{}|~]+", "", payload)

        payload = (  # pragma: no branch
            APRS_COMPILED_MAP.sub(
                lambda x: APRS_BAD_CHARMAP[x.group()], payload)
        )

        # Finally, constrain output string to 67 characters as
        # APRS messages are limited in length
        payload = payload[:67]

        # Our outgoing message MUST end with a CRLF so
        # let's amend our payload respectively
        payload = payload.rstrip("\r\n") + "\r\n"

        self.logger.debug("Payload setup complete: {}".format(payload))

        # send the message to our target call sign(s)
        for index in range(0, len(targets)):
            # prepare the output string
            # Format:
            # Device ID/TOCALL - our call sign - target call sign - body
            buffer = "{}>{}::{:9}:{}".format(
                self.user, self.device_id, targets[index], payload
            )

            # and send the content to the socket
            # Note that there will be no response from APRS and
            # that all exceptions are handled within the 'send' method
            self.logger.debug("Sending APRS message: {}".format(buffer))

            # send the content
            if not self.socket_send(buffer):
                has_error = True
                break

            # Finally, reset our socket buffer
            # we DO NOT read from the socket as we
            # would simply listen to the default APRS-IS stream
            self.socket_reset()

        self.logger.debug("Closing socket.")
        self.socket_close()
        self.logger.info(
            "Sent %d/%d APRS-IS notification(s)", index + 1, len(targets))
        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {}

        if self.locale != NotifyAprs.template_args["locale"]["default"]:
            # Store our locale if not default
            params['locale'] = self.locale

        if self.delay != NotifyAprs.template_args["delay"]["default"]:
            # Store our locale if not default
            params['delay'] = "{:.2f}".format(self.delay)

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Setup Authentication
        auth = "{user}:{password}@".format(
            user=NotifyAprs.quote(self.user, safe=""),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=""
            ),
        )

        return "{schema}://{auth}{targets}?{params}".format(
            schema=self.secure_protocol,
            auth=auth,
            targets="/".join(chain(
                [self.pprint(x, privacy, safe="") for x in self.targets],
                [self.pprint(x, privacy, safe="")
                 for x in self.invalid_targets],
            )),
            params=NotifyAprs.urlencode(params),
        )

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.user, self.password, self.locale)

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        targets = len(self.targets)
        return targets if targets > 0 else 1

    def __del__(self):
        """
        Ensure we close any lingering connections
        """
        self.socket_close()

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

        # All elements are targets
        results["targets"] = [NotifyAprs.unquote(results["host"])]

        # All entries after the hostname are additional targets
        results["targets"].extend(NotifyAprs.split_path(results["fullpath"]))

        # Get Delay (if set)
        if 'delay' in results['qsd'] and len(results['qsd']['delay']):
            results['delay'] = NotifyAprs.unquote(results['qsd']['delay'])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyAprs.parse_list(results["qsd"]["to"])

        # Set our APRS-IS server locale's key value and convert it to uppercase
        if "locale" in results["qsd"] and len(results["qsd"]["locale"]):
            results["locale"] = NotifyAprs.unquote(
                results["qsd"]["locale"]
            ).upper()

        return results
