# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Chris Caron <lead2gold@gmail.com>
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

import ssl
from os.path import isfile
import logging


# Default our global support flag
SLIXMPP_SUPPORT_AVAILABLE = False

try:
    # Import slixmpp if available
    import slixmpp
    import asyncio

    SLIXMPP_SUPPORT_AVAILABLE = True

except ImportError:
    # No problem; we just simply can't support this plugin because we're
    # either using Linux, or simply do not have slixmpp installed.
    pass


class SliXmppAdapter(object):
    """
    Wrapper to slixmpp

    """

    # Reference to XMPP client.
    xmpp = None

    # Whether everything succeeded
    success = False

    # The default protocol
    protocol = 'xmpp'

    # The default secure protocol
    secure_protocol = 'xmpps'

    # Taken from https://golang.org/src/crypto/x509/root_linux.go
    CA_CERTIFICATE_FILE_LOCATIONS = [
        # Debian/Ubuntu/Gentoo etc.
        "/etc/ssl/certs/ca-certificates.crt",
        # Fedora/RHEL 6
        "/etc/pki/tls/certs/ca-bundle.crt",
        # OpenSUSE
        "/etc/ssl/ca-bundle.pem",
        # OpenELEC
        "/etc/pki/tls/cacert.pem",
        # CentOS/RHEL 7
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
    ]

    # This entry is a bit hacky, but it allows us to unit-test this library
    # in an environment that simply doesn't have the slixmpp package
    # available to us.
    #
    # If anyone is seeing this had knows a better way of testing this
    # outside of what is defined in test/test_xmpp_plugin.py, please
    # let me know! :)
    _enabled = SLIXMPP_SUPPORT_AVAILABLE

    def __init__(self, host=None, port=None, secure=False,
                 verify_certificate=True, xep=None, jid=None, password=None,
                 body=None, subject=None, targets=None, before_message=None,
                 logger=None):
        """
        Initialize our SliXmppAdapter object
        """

        self.host = host
        self.port = port
        self.secure = secure
        self.verify_certificate = verify_certificate

        self.xep = xep
        self.jid = jid
        self.password = password

        self.body = body
        self.subject = subject
        self.targets = targets
        self.before_message = before_message

        self.logger = logger or logging.getLogger(__name__)

        # Use the Apprise log handlers for configuring the slixmpp logger.
        apprise_logger = logging.getLogger('apprise')
        sli_logger = logging.getLogger('slixmpp')
        for handler in apprise_logger.handlers:
            sli_logger.addHandler(handler)
        sli_logger.setLevel(apprise_logger.level)

        if not self.load():
            raise ValueError("Invalid XMPP Configuration")

    def load(self):

        try:
            asyncio.get_event_loop()

        except RuntimeError:
            # slixmpp can not handle not having an event_loop
            # see: https://lab.louiz.org/poezio/slixmpp/-/issues/3456
            # This is a work-around to this problem
            asyncio.set_event_loop(asyncio.new_event_loop())

        # Prepare our object
        self.xmpp = slixmpp.ClientXMPP(self.jid, self.password)

        # Register our session
        self.xmpp.add_event_handler("session_start", self.session_start)

        for xep in self.xep:
            # Load xep entries
            try:
                self.xmpp.register_plugin('xep_{0:04d}'.format(xep))

            except slixmpp.plugins.base.PluginNotFound:
                self.logger.warning(
                    'Could not register plugin {}'.format(
                        'xep_{0:04d}'.format(xep)))
                return False

        if self.secure:
            # Don't even try to use the outdated ssl.PROTOCOL_SSLx
            self.xmpp.ssl_version = ssl.PROTOCOL_TLSv1

            # If the python version supports it, use highest TLS version
            # automatically
            if hasattr(ssl, "PROTOCOL_TLS"):
                # Use the best version of TLS available to us
                self.xmpp.ssl_version = ssl.PROTOCOL_TLS

            self.xmpp.ca_certs = None
            if self.verify_certificate:
                # Set the ca_certs variable for certificate verification
                self.xmpp.ca_certs = next(
                    (cert for cert in self.CA_CERTIFICATE_FILE_LOCATIONS
                     if isfile(cert)), None)

                if self.xmpp.ca_certs is None:
                    self.logger.warning(
                        'XMPP Secure comunication can not be verified; '
                        'no local CA certificate file')
                    return False

        # If the user specified a port, skip SRV resolving, otherwise it is a
        # lot easier to let slixmpp handle DNS instead of the user.
        self.override_connection = \
            None if not self.port else (self.host, self.port)

        # We're good
        return True

    def process(self):
        """
        Thread that handles the server/client i/o

        """

        # Instruct slixmpp to connect to the XMPP service.
        if not self.xmpp.connect(
                self.override_connection, use_ssl=self.secure):
            return False

        # Run the asyncio event loop, and return once disconnected,
        # for any reason.
        self.xmpp.process(forever=False)

        return self.success

    def session_start(self, *args, **kwargs):
        """
        Session Manager
        """

        targets = list(self.targets)
        if not targets:
            # We always default to notifying ourselves
            targets.append(self.jid)

        while len(targets) > 0:

            # Get next target (via JID)
            target = targets.pop(0)

            # Invoke "before_message" event hook.
            self.before_message()

            # The message we wish to send, and the JID that will receive it.
            self.xmpp.send_message(
                mto=target, msubject=self.subject,
                mbody=self.body, mtype='chat')

        # Using wait=True ensures that the send queue will be
        # emptied before ending the session.
        self.xmpp.disconnect(wait=True)

        # Toggle our success flag
        self.success = True
