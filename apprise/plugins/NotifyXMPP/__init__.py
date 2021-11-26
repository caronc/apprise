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

from ..NotifyBase import NotifyBase
from ...URLBase import PrivacyMode
from ...common import NotifyType
from ...utils import parse_list
from ...AppriseLocale import gettext_lazy as _
from .SliXmppAdapter import SliXmppAdapter

# xep string parser
XEP_PARSE_RE = re.compile('^[^1-9]*(?P<xep>[1-9][0-9]{0,3})$')


class NotifyXMPP(NotifyBase):
    """
    A wrapper for XMPP Notifications
    """
    # Set our global enabled flag
    enabled = SliXmppAdapter._enabled

    requirements = {
        # Define our required packaging in order to work
        'packages_required': [
            "slixmpp; python_version >= '3.7'",
        ]
    }

    # The default descriptive name associated with the Notification
    service_name = 'XMPP'

    # The services URL
    service_url = 'https://xmpp.org/'

    # The default protocol
    protocol = 'xmpp'

    # The default secure protocol
    secure_protocol = 'xmpps'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_xmpp'

    # Lower throttle rate for XMPP
    request_rate_per_sec = 0.5

    # Our XMPP Adapter we use to communicate through
    _adapter = SliXmppAdapter if SliXmppAdapter._enabled else None

    # Define object templates
    templates = (
        '{schema}://{user}:{password}@{host}',
        '{schema}://{user}:{password}@{host}:{port}',
        '{schema}://{user}:{password}@{host}/{targets}',
        '{schema}://{user}:{password}@{host}:{port}/{targets}',
    )

    # Define our tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
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
        },
        'user': {
            'name': _('Username'),
            'type': 'string',
            'required': True,
        },
        'password': {
            'name': _('Password'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'target_jid': {
            'name': _('Target JID'),
            'type': 'string',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'to': {
            'alias_of': 'targets',
        },
        'xep': {
            'name': _('XEP'),
            'type': 'list:string',
            'prefix': 'xep-',
            'regex': (r'^[1-9][0-9]{0,3}$', 'i'),
        },
        'jid': {
            'name': _('Source JID'),
            'type': 'string',
        },
    })

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
                    self.logger.debug('Loaded XMPP {}'.format(xep))

                else:
                    self.logger.warning(
                        "Could not load XMPP {}".format(xep))

        # By default we send ourselves a message
        if targets:
            self.targets = parse_list(targets)
            self.targets[0] = self.targets[0][1:]

        else:
            self.targets = list()

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform XMPP Notification
        """

        # Detect our JID if it isn't otherwise specified
        jid = self.jid
        password = self.password
        if not jid:
            jid = '{}@{}'.format(self.user, self.host)

        try:
            # Communicate with XMPP.
            xmpp_adapter = self._adapter(
                host=self.host, port=self.port, secure=self.secure,
                verify_certificate=self.verify_certificate, xep=self.xep,
                jid=jid, password=password, body=body, subject=title,
                targets=self.targets, before_message=self.throttle,
                logger=self.logger)

        except ValueError:
            # We failed
            return False

        # Initialize XMPP machinery and begin processing the XML stream.
        outcome = xmpp_adapter.process()

        return outcome

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.jid:
            params['jid'] = self.jid

        if self.xep:
            # xep are integers, so we need to just iterate over a list and
            # switch them to a string
            params['xep'] = ','.join([str(xep) for xep in self.xep])

        # Target JID(s) can clash with our existing paths, so we just use comma
        # and/or space as a delimiters - %20 = space
        jids = '%20'.join([NotifyXMPP.quote(x, safe='') for x in self.targets])

        default_schema = self.secure_protocol if self.secure else self.protocol

        auth = '{user}:{password}'.format(
            user=NotifyXMPP.quote(self.user, safe=''),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=''))

        return '{schema}://{auth}@{hostname}{port}/{jids}?{params}'.format(
            auth=auth,
            schema=default_schema,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port='' if not self.port
                 else ':{}'.format(self.port),
            jids=jids,
            params=NotifyXMPP.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

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
