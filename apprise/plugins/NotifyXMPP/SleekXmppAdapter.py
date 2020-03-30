# -*- coding: utf-8 -*-

import ssl
from os.path import isfile
import logging


# Default our global support flag
SLEEKXMPP_SUPPORT_AVAILABLE = False

try:
    # Import sleekxmpp if available
    import sleekxmpp

    SLEEKXMPP_SUPPORT_AVAILABLE = True

except ImportError:
    # No problem; we just simply can't support this plugin because we're
    # either using Linux, or simply do not have sleekxmpp installed.
    pass


class SleekXmppAdapter(object):
    """
    Wrapper to sleekxmpp

    """

    # Reference to XMPP client.
    xmpp = None

    # Whether everything succeeded
    success = False

    # The default protocol
    protocol = 'xmpp'

    # The default secure protocol
    secure_protocol = 'xmpps'

    # The default XMPP port
    default_unsecure_port = 5222

    # The default XMPP secure port
    default_secure_port = 5223

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
    # in an environment that simply doesn't have the sleekxmpp package
    # available to us.
    #
    # If anyone is seeing this had knows a better way of testing this
    # outside of what is defined in test/test_xmpp_plugin.py, please
    # let me know! :)
    _enabled = SLEEKXMPP_SUPPORT_AVAILABLE

    def __init__(self, host=None, port=None, secure=False,
                 verify_certificate=True, xep=None, jid=None, password=None,
                 body=None, targets=None, before_message=None, logger=None):
        """
        Initialize our SleekXmppAdapter object
        """

        self.host = host
        self.port = port
        self.secure = secure
        self.verify_certificate = verify_certificate

        self.xep = xep
        self.jid = jid
        self.password = password

        self.body = body
        self.targets = targets
        self.before_message = before_message

        self.logger = logger or logging.getLogger(__name__)

        # Use the Apprise log handlers for configuring the sleekxmpp logger.
        apprise_logger = logging.getLogger('apprise')
        sleek_logger = logging.getLogger('sleekxmpp')
        for handler in apprise_logger.handlers:
            sleek_logger.addHandler(handler)
        sleek_logger.setLevel(apprise_logger.level)

        if not self.load():
            raise ValueError("Invalid XMPP Configuration")

    def load(self):

        # Prepare our object
        self.xmpp = sleekxmpp.ClientXMPP(self.jid, self.password)

        # Register our session
        self.xmpp.add_event_handler("session_start", self.session_start)

        for xep in self.xep:
            # Load xep entries
            try:
                self.xmpp.register_plugin('xep_{0:04d}'.format(xep))

            except sleekxmpp.plugins.base.PluginNotFound:
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

        # We're good
        return True

    def process(self):
        """
        Thread that handles the server/client i/o

        """

        # Establish connection to XMPP server.
        # To speed up sending messages, don't use the "reattempt" feature,
        # it will add a nasty delay even before connecting to XMPP server.
        if not self.xmpp.connect((self.host, self.port),
                                 use_ssl=self.secure, reattempt=False):

            default_port = self.default_secure_port \
                if self.secure else self.default_unsecure_port

            default_schema = self.secure_protocol \
                if self.secure else self.protocol

            # Log connection issue
            self.logger.warning(
                'Failed to authenticate {jid} with: {schema}://{host}{port}'
                .format(
                    jid=self.jid,
                    schema=default_schema,
                    host=self.host,
                    port='' if not self.port or self.port == default_port
                         else ':{}'.format(self.port),
                ))
            return False

        # Process XMPP communication.
        self.xmpp.process(block=True)

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
            self.xmpp.send_message(mto=target, mbody=self.body, mtype='chat')

        # Using wait=True ensures that the send queue will be
        # emptied before ending the session.
        self.xmpp.disconnect(wait=True)

        # Toggle our success flag
        self.success = True
