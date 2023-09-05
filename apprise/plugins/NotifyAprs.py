# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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

# To use this plugin, you need to be a licensed ham radio operator

#
# You're done at this point, you only need to know your user/pass that
# you signed up with.

#  The following URLs would be accepted by Apprise:
#   - aprs://{user}:{password}@{callsign}
#   - aprs://{user}:{password}@{callsign1}/{callsign2}

# Optional parameters:
#   - server --> APRS-IS target server to connect with
#                Default: 'euro.aprs2.net'
#                Details: https://www.aprs2.net/

#
# APRS message format specification:
# http://www.aprs.org/doc/APRS101.PDF
#

from json import dumps

import socket
import sys
from .NotifyBase import NotifyBase
from ..AppriseLocale import gettext_lazy as _
from ..URLBase import PrivacyMode
from ..common import NotifyType
from ..utils import is_call_sign
from ..utils import parse_call_sign
from ..utils import parse_list
from ..utils import parse_bool
from .. import __version__

# fixed APRS-IS server locales
# default is "EURO"
APRS_LOCALES = {
    "NOAM": 'noam.aprs2.net',
    "SOAM": 'soam.aprs2.net',
    "EURO": 'euro.aprs2.net',
    "ASIA": 'asia.aprs2.net',
    "AUNZ": 'aunz.aprs2.net',
}


class NotifyAprs(NotifyBase):
    """
    A wrapper for APRS Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Aprs'

    # The services URL
    service_url = 'https://www.aprs2.net/'

    # The default secure protocol
    secure_protocol = 'aprs'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_aprs'

    # APRS default server
    notify_url = 'euro.aprs2.net'

    # Our (future) socket sobject
    sock = None

    # APRS default port, supported by all core servers
    # Details: https://www.aprs-is.net/Connecting.aspx
    notify_port = 10152

    # The maximum length of the body
    body_maxlen = 67

    # socket timeout in seconds
    socket_timeout = 15

    # A title can not be used for APRS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The maximum amount of emails that can reside within a single transmission
    default_batch_size = 50

    # Define object templates
    templates = ('{schema}://{user}:{password}@{targets}',)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
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
            'target_callsign': {
                'name': _('Target Callsign'),
                'type': 'string',
                'regex': (
                    r'^[a-z0-9]{2,5}(-[a-z0-9]{1,2})?$', 'i',
                ),
                'map_to': 'targets',
            },
            'targets': {
                'name': _('Targets'),
                'type': 'list:string',
                'required': True,
            },
        }
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            'to': {
                'name': _('Target Callsign'),
                'type': 'string',
                'map_to': 'targets',
            },
            'locale': {
                'name': _('Locale'),
                'type': 'choice:string',
                'values': APRS_LOCALES,
                'default': 'EURO',
            },
            'batch': {
                'name': _('Batch Mode'),
                'type': 'bool',
                'default': False,
            },
        }
    )

    def __init__(self, targets=None, locale=None,
                 batch=False, **kwargs):
        """
        Initialize APRS Object
        """
        super().__init__(**kwargs)

        # Parse our targets
        self.targets = list()

        """
        Check if the user has provided credentials
        """
        if not (self.user and self.password):
            msg = 'An APRS user/pass was not provided.'
            self.logger.warning(msg)
            raise TypeError(msg)

        """
        Check if the user tries to use a read-only access
        to APRS-IS. We need to send content, meaning that
        read-only access will not work
        """
        if self.password == "-1":
            msg = 'APRS read-only passwords are not supported.'
            self.logger.warning(msg)
            raise TypeError(msg)

        """
        Check if the password is numeric
        """
        if not self.password.isnumeric():
            msg = 'Invalid APRS-IS password'
            self.logger.warning(msg)
            raise TypeError(msg)

        """
        Check if the user has provided a locale for the 
        APRS-IS-server and validate it, if necessary
        """
        if locale:
            locale = locale.upper()
            if locale not in APRS_LOCALES:
                msg = 'Unsupported APRS-IS locale. Valid:({}).'.format(APRS_LOCALES.keys())
                self.logger.warning(msg)
                raise TypeError(msg)

        # Set the transmitter group
        self.locale = NotifyAprs.template_args['locale']['default'] if not locale else locale

        # Prepare Batch Mode Flag
        self.batch = batch

        for target in parse_call_sign(targets):
            # Validate targets and drop bad ones
            # We just need to know if the call sign (including SSID, if
            # provided) is valid and can then process the input as is
            result = is_call_sign(target)
            if not result:
                self.logger.warning(
                    'Dropping invalid Amateur radio call sign ({}).'.format(
                        target),
                )
                continue

            # Convert the call sign to upper case and
            # try to add it to our list of targets
            target_upper = target.upper()

            # Store call sign as is and ignore duplicates
            if target_upper not in self.targets:
                self.targets.append(target_upper)

        return

    def socket_close(self):
        """
        Closes the socket connection whereas present
        """
        if self.sock:
            try:
                self.sock.close()

            except socket.gaierror as e:
                self.logger.debug('Socket Exception: %s' % str(e))
                self.sock = None
                return False

            except socket.timeout as e:
                self.logger.debug('Socket Timeout Exception: %s' % str(e))
                self.sock = None
                return False

            except Exception as e:
                self.logger.debug('General Exception: %s' % str(e))
                self.sock = None
                return False

        self.sock = None

    def socket_open(self):
        """
        Establishes the connection to the APRS-IS
        socket server
        """
        self.logger.info(
            'Creating socket connection with APRS-IS')

        try:
            self.sock = socket.create_connection((APRS_LOCALES[self.locale],
                                                  self.notify_port),
                                                 self.socket_timeout)

        except ConnectionError as e:
            self.logger.debug('Socket Exception: %s' % str(e))
            self.sock = None
            return False

        except socket.gaierror as e:
            self.logger.debug('Socket Exception: %s' % str(e))
            self.sock = None
            return False

        except socket.timeout as e:
            self.logger.debug('Socket Timeout Exception: %s' % str(e))
            self.sock = None
            return False

        except Exception as e:
            self.logger.debug('General Exception: %s' % str(e))
            self.sock = None
            return False

        # We are connected.
        # Get the physical host/port of the server
        host, port = self.sock.getpeername()

        # and create debug info
        self.logger.info(
                'Connected to {}:{}'.format(host, port))

        # Return success
        return True

    def aprsis_login(self):
        """
        Generate the APRS-IS login string, send it to the server
        and parse the response

        Returns True/False wrt whether the login was successful
        """

        # Check if we are connected
        if not self.sock:
            self.logger.info(
                'Not connected to APRS-IS')
            return False

        # APRS-IS login string, see https://www.aprs-is.net/Connecting.aspx
        login_str = "user {0} pass {1} vers apprise {2}\r\n"\
            .format(self.user,self.password, __version__)

        self.logger.info(
            'Sending login information to APRS-IS')

        # Send the data & abort in case of error
        if not self.socket_send(login_str):
            self.logger.debug(
                'Login to APRS-IS unsuccessful, exception occurred')
            self.socket_close()
            return False

        rx_buf = self.socket_receive(len(login_str)+100)
        # Abort the remaining process in case an error has occurred
        if not rx_buf:
            self.logger.debug(
                'Login to APRS-IS unsuccessful, exception occurred')
            self.socket_close()
            return False

            rx_lines = rb_buf.splitlines()
            if len(rx_lines) < 1:
                self.logger.debug(
                    'Incorrect APRS-IS rx header?')
                self.socket_close()
                return False

            # We need the content from the 2nd line
            # of the server's response
            _, _, callsign, status, _ = rx_lines[1].split(' ', 4)

            # check if we were able to log in
            if callsign == "":
                self.logger.debug('Did not receive call sign from APRS-IS')
                self.socket_close()
                return False

            if callsign != self.user:
                self.logger.debug('call signs differ: %s' % callsign)
                self.socket_close()
                return False

            if status == "unverified,":
                self.logger.debug('invalid APRS-IS password for given call sign')
                self.socket_close()
                return False

            # all validations are successful; we are connected
            return True

    def socket_send(self, tx_data):
        """
        Generic "Send data to a socket"
        """

        # Check if we are connected
        if not self.sock:
            self.logger.info(
                'Not connected to APRS-IS')
            return False

        self.logger.debug(
            'Sending data to APRS-IS')

        payload = tx_data.encode('utf-8') if sys.version_info[0] >= 3 else tx_data

        try:
            self.sock.sendall(payload)

        except socket.gaierror as e:
            self.logger.debug('Socket Exception: %s' % str(e))
            self.sock = None
            return False

        except socket.timeout as e:
            self.logger.debug('Socket Timeout Exception: %s' % str(e))
            self.sock = None
            return False

        except Exception as e:
            self.logger.debug('General Exception: %s' % str(e))
            self.sock = None
            return False

        return True

    def socket_receive(self, rx_len):
        """
        Generic "Receive data from a socket"
        """

        # Check if we are connected
        if not self.sock:
            self.logger.info(
                'Not connected to APRS-IS')
            return False

        self.logger.debug(
            'Receiving data from APRS-IS')

        # Receive content from the socket
        try:
            rx_buf = self.sock.recv(rx_len)

        except ConnectionError as e:
            self.logger.debug('Socket Exception: %s' % str(e))
            self.sock = None
            return None

        except socket.gaierror as e:
            self.logger.debug('Socket Exception: %s' % str(e))
            self.sock = None
            return None

        except socket.timeout as e:
            self.logger.debug('Socket Timeout Exception: %s' % str(e))
            self.sock = None
            return None

        except Exception as e:
            self.logger.debug('General Exception: %s' % str(e))
            self.sock = None
            return None

        rx_buf = rx_buf.decode('latin-1') if sys.version_info[0] >= 3 else rx_buf

        return rx_buf.rstrip()


    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform APRS Notification
        """

        if not self.targets:
            # There is no one to notify; we're done
            self.logger.warning(
                'There are no amateur radio call signs to notify')
            return False

        # prepare payload
        if title:
            # Format title
            payload = '{}: {}'.format(title, body)
        else:
            payload = body

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Create the connection
        self.logger.info(
            'Connecting to APRS-IS')

        # Try to open the socket
        # sock object is "None" if we were unable to establish a connection
        # In case of errors, the error message has already been sent
        # to the logger object
        if not self.socket_open():
            return False

        # test
        self.sock.setblocking(1)

        # We have established a successful connection
        # to the socket server. Now send the login information
        if not self.aprsis_login():
            return False

        # Login & authorization confirmed

        self.socket_close()
        self.logger.info('Sent APRS-IS notification.')

        return True


    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'locale':
                APRS_LOCALES[self.template_args['locale']['default']]
                if self.locale not in APRS_LOCALES
                else APRS_LOCALES[self.locale],
            'batch': 'yes' if self.batch else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Setup Authentication
        auth = '{user}:{password}@'.format(
            user=NotifyAprs.quote(self.user, safe=""),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''
            ),
        )

        return '{schema}://{auth}{targets}?{params}'.format(
            schema=self.secure_protocol,
            auth=auth,
            targets='/'.join([self.pprint(x, privacy, safe='')
                              for x in self.targets]),
            params=NotifyAprs.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + \
                (1 if targets % batch_size else 0)

        return targets

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
        results['targets'] = [NotifyAprs.unquote(results['host'])]

        # All entries after the hostname are additional targets
        results['targets'].extend(NotifyAprs.split_path(results['fullpath']))

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyAprs.parse_list(results['qsd']['to'])

        # Set our priority
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            results['priority'] = \
                NotifyAprs.unquote(results['qsd']['priority'])

        # Check for one or multiple transmitter groups (comma separated)
        # and split them up, when necessary
        if 'txgroups' in results['qsd']:
            results['txgroups'] = \
                [x.lower() for x in
                 NotifyAprs.parse_list(results['qsd']['txgroups'])]

        # Get Batch Mode Flag
        results['batch'] = \
            parse_bool(results['qsd'].get(
                'batch', NotifyAprs.template_args['batch']['default']))

        return results
