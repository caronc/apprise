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

import re
import ssl
from os.path import isfile

from .NotifyBase import NotifyBase
from ..common import NotifyType
from ..utils import parse_list

# xep string parser
XEP_PARSE_RE = re.compile('^[^1-9]*(?P<xep>[1-9][0-9]{0,3})$')

# Default our global support flag
NOTIFY_XMPP_SUPPORT_ENABLED = False

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

try:
    # Import sleekxmpp if available
    import sleekxmpp

    NOTIFY_XMPP_SUPPORT_ENABLED = True

except ImportError:
    # No problem; we just simply can't support this plugin because we're
    # either using Linux, or simply do not have sleekxmpp installed.
    pass


class NotifyXMPP(NotifyBase):
    """
    A wrapper for XMPP Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'XMPP'

    # The default protocol
    protocol = 'xmpp'

    # The default secure protocol
    secure_protocol = 'xmpps'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_xmpp'

    # The default XMPP port
    default_unsecure_port = 5222

    # The default XMPP secure port
    default_secure_port = 5223

    # XMPP does not support a title
    title_maxlen = 0

    # This entry is a bit hacky, but it allows us to unit-test this library
    # in an environment that simply doesn't have the sleekxmpp package
    # available to us.
    #
    # If anyone is seeing this had knows a better way of testing this
    # outside of what is defined in test/test_xmpp_plugin.py, please
    # let me know! :)
    _enabled = NOTIFY_XMPP_SUPPORT_ENABLED

    def __init__(self, targets=None, jid=None, xep=None, **kwargs):
        """
        Initialize XMPP Object
        """
        super(NotifyXMPP, self).__init__(**kwargs)

        # JID Details:
        #  - JID's normally have an @ symbol in them, but it is not required
        #  - Each allowable portion of a JID MUST NOT be more than 1023 bytes
        #    in length.
        #  - JID's can identify resource paths at the end separated by slashes
        #     hence the following is valid: user@example.com/resource/path

        # Since JID's can clash with URLs offered by aprise (specifically the
        # resource paths we need to allow users an alternative character to
        # represent the slashes. The grammer is defined here:
        # https://xmpp.org/extensions/xep-0029.html as follows:
        #
        #     <JID> ::= [<node>"@"]<domain>["/"<resource>]
        #     <node> ::= <conforming-char>[<conforming-char>]*
        #     <domain> ::= <hname>["."<hname>]*
        #     <resource> ::= <any-char>[<any-char>]*
        #     <hname> ::= <let>|<dig>[[<let>|<dig>|"-"]*<let>|<dig>]
        #     <let> ::= [a-z] | [A-Z]
        #     <dig> ::= [0-9]
        #     <conforming-char> ::= #x21 | [#x23-#x25] | [#x28-#x2E] |
        #                           [#x30-#x39] | #x3B | #x3D | #x3F |
        #                           [#x41-#x7E] | [#x80-#xD7FF] |
        #                           [#xE000-#xFFFD] | [#x10000-#x10FFFF]
        #     <any-char> ::= [#x20-#xD7FF] | [#xE000-#xFFFD] |
        #                    [#x10000-#x10FFFF]

        # The best way to do this is to choose characters that aren't allowed
        # in this case we will use comma and/or space.

        # Assemble our jid using the information available to us:
        self.jid = jid

        if not (self.user or self.password):
            # you must provide a jid/pass for this to work; if no password
            # is specified then the user field acts as the password instead
            # so we know that if there is no user specified, our url was
            # really busted up.
            msg = 'You must specify a XMPP password'
            self.logger.warning(msg)
            raise TypeError(msg)

        # See https://xmpp.org/extensions/ for details on xep values
        if xep is None:
            # Default xep setting
            self.xep = [
                # xep_0030: Service Discovery
                30,
                # xep_0199: XMPP Ping
                199,
            ]

        else:
            # Prepare the list
            _xep = parse_list(xep)
            self.xep = []

            for xep in _xep:
                result = XEP_PARSE_RE.match(xep)
                if result is not None:
                    self.xep.append(int(result.group('xep')))

                else:
                    self.logger.warning(
                        "Could not load XMPP xep {}".format(xep))

        # By default we send ourselves a message
        if targets:
            self.targets = parse_list(targets)

        else:
            self.targets = list()

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform XMPP Notification
        """

        if not self._enabled:
            self.logger.warning(
                'XMPP Notifications are not supported by this system '
                '- install sleekxmpp.')
            return False

        # Detect our JID if it isn't otherwise specified
        jid = self.jid
        password = self.password
        if not jid:
            if self.user and self.password:
                # xmpp://user:password@hostname
                jid = '{}@{}'.format(self.user, self.host)

            else:
                # xmpp://password@hostname
                jid = self.host
                password = self.password if self.password else self.user

        # Prepare our object
        xmpp = sleekxmpp.ClientXMPP(jid, password)

        for xep in self.xep:
            # Load xep entries
            xmpp.register_plugin('xep_{0:04d}'.format(xep))

        if self.secure:
            xmpp.ssl_version = ssl.PROTOCOL_TLSv1
            # If the python version supports it, use highest TLS version
            # automatically
            if hasattr(ssl, "PROTOCOL_TLS"):
                # Use the best version of TLS available to us
                xmpp.ssl_version = ssl.PROTOCOL_TLS

            xmpp.ca_certs = None
            if self.verify_certificate:
                # Set the ca_certs variable for certificate verification
                xmpp.ca_certs = next(
                    (cert for cert in CA_CERTIFICATE_FILE_LOCATIONS
                     if isfile(cert)), None)

                if xmpp.ca_certs is None:
                    self.logger.warning(
                        'XMPP Secure comunication can not be verified; '
                        'no CA certificate found')

        # Acquire our port number
        if not self.port:
            port = self.default_secure_port \
                if self.secure else self.default_unsecure_port

        else:
            port = self.port

        # Establish our connection
        if not xmpp.connect((self.host, port)):
            return False

        xmpp.send_presence()

        try:
            xmpp.get_roster()

        except sleekxmpp.exceptions.IqError as e:
            self.logger.warning('There was an error getting the XMPP roster.')
            self.logger.debug(e.iq['error']['condition'])
            xmpp.disconnect()
            return False

        except sleekxmpp.exceptions.IqTimeout:
            self.logger.warning('XMPP Server is taking too long to respond.')
            xmpp.disconnect()
            return False

        targets = list(self.targets)
        if not targets:
            # We always default to notifying ourselves
            targets.append(jid)

        while len(targets) > 0:

            # Get next target (via JID)
            target = targets.pop(0)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            # The message we wish to send, and the JID that
            # will receive it.
            xmpp.send_message(mto=target, mbody=body, mtype='chat')

        # Using wait=True ensures that the send queue will be
        # emptied before ending the session.
        xmpp.disconnect(wait=True)

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        if self.jid:
            args['jid'] = self.jid

        if self.xep:
            # xep are integers, so we need to just iterate over a list and
            # switch them to a string
            args['xep'] = ','.join([str(xep) for xep in self.xep])

        # Target JID(s) can clash with our existing paths, so we just use comma
        # and/or space as a delimiters - %20 = space
        jids = '%20'.join([NotifyXMPP.quote(x, safe='') for x in self.targets])

        default_port = self.default_secure_port \
            if self.secure else self.default_unsecure_port

        default_schema = self.secure_protocol if self.secure else self.protocol

        if self.user and self.password:
            auth = '{}:{}'.format(
                NotifyXMPP.quote(self.user, safe=''),
                NotifyXMPP.quote(self.password, safe=''))

        else:
            auth = self.password if self.password else self.user

        return '{schema}://{auth}@{hostname}{port}/{jids}?{args}'.format(
            auth=auth,
            schema=default_schema,
            hostname=NotifyXMPP.quote(self.host, safe=''),
            port='' if not self.port or self.port == default_port
                 else ':{}'.format(self.port),
            jids=jids,
            args=NotifyXMPP.urlencode(args),
        )

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

        # Get our targets; we ignore path slashes since they identify
        # our resources
        results['targets'] = NotifyXMPP.parse_list(results['fullpath'])

        # Over-ride the xep plugins
        if 'xep' in results['qsd'] and len(results['qsd']['xep']):
            results['xep'] = \
                NotifyXMPP.parse_list(results['qsd']['xep'])

        # Over-ride the default (and detected) jid
        if 'jid' in results['qsd'] and len(results['qsd']['jid']):
            results['jid'] = NotifyXMPP.unquote(results['qsd']['jid'])

        # Over-ride the default (and detected) jid
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyXMPP.parse_list(results['qsd']['to'])

        return results
