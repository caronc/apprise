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

import six
import sys
import ssl
import mock

import apprise

try:
    # Python v3.4+
    from importlib import reload
except ImportError:
    try:
        # Python v3.0-v3.3
        from imp import reload
    except ImportError:
        # Python v2.7
        pass

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


def test_xmpp_plugin(tmpdir):
    """
    API: NotifyXMPP Plugin()
    """

    # Mock the sleekxmpp module completely.
    sys.modules['sleekxmpp'] = mock.MagicMock()

    # The following libraries need to be reloaded to prevent
    #  TypeError: super(type, obj): obj must be an instance or subtype of type
    #  This is better explained in this StackOverflow post:
    #     https://stackoverflow.com/questions/31363311/\
    #       any-way-to-manually-fix-operation-of-\
    #          super-after-ipython-reload-avoiding-ty
    #
    reload(sys.modules['apprise.plugins.NotifyXMPP'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])

    # Mock the XMPP adapter to override "self.success".
    # This will signal a successful message delivery.
    from apprise.plugins.NotifyXMPP import SleekXmppAdapter
    class MockedSleekXmppAdapter(SleekXmppAdapter):

        def __init__(self, *args, **kwargs):
            super(MockedSleekXmppAdapter, self).__init__(*args, **kwargs)
            self.success = True

    NotifyXMPP = sys.modules['apprise.plugins.NotifyXMPP']
    NotifyXMPP.SleekXmppAdapter = MockedSleekXmppAdapter

    # Disable Throttling to speed testing
    apprise.plugins.NotifyBase.request_rate_per_sec = 0

    # Create our instance
    obj = apprise.Apprise.instantiate('xmpp://', suppress_exceptions=False)

    # Not possible because no password or host was specified
    assert obj is None

    try:
        obj = apprise.Apprise.instantiate(
            'xmpp://hostname', suppress_exceptions=False)
        # We should not reach here; we should have thrown an exception
        assert False

    except TypeError:
        # we're good
        assert True

    # Not possible because no password was specified
    assert obj is None

    # SSL Flags
    if hasattr(ssl, "PROTOCOL_TLS"):
        # Test cases where PROTOCOL_TLS simply isn't available
        ssl_temp_swap = ssl.PROTOCOL_TLS
        del ssl.PROTOCOL_TLS

        # Test our URL
        url = 'xmpps://user:pass@localhost'
        obj = apprise.Apprise.instantiate(url, suppress_exceptions=False)
        # Test we loaded
        assert isinstance(obj, apprise.plugins.NotifyXMPP) is True
        assert obj.notify(
            title='title', body='body',
            notify_type=apprise.NotifyType.INFO) is True

        # Restore the variable for remaining tests
        setattr(ssl, 'PROTOCOL_TLS', ssl_temp_swap)

    else:
        # Handle case where it is not missing
        setattr(ssl, 'PROTOCOL_TLS', ssl.PROTOCOL_TLSv1)
        # Test our URL
        url = 'xmpps://user:pass@localhost'
        obj = apprise.Apprise.instantiate(url, suppress_exceptions=False)
        # Test we loaded
        assert isinstance(obj, apprise.plugins.NotifyXMPP) is True
        assert obj.notify(
            title='title', body='body',
            notify_type=apprise.NotifyType.INFO) is True

        # Restore settings as they were
        del ssl.PROTOCOL_TLS

    urls = (
        {
            'u': 'xmpps://user:pass@localhost',
            'p': 'xmpps://user:****@localhost',
        }, {
            'u': 'xmpps://user:pass@localhost?'
                 'xep=30,199,garbage,xep_99999999',
            'p': 'xmpps://user:****@localhost',
        }, {
            'u': 'xmpps://user:pass@localhost?xep=ignored',
            'p': 'xmpps://user:****@localhost',
        }, {
            'u': 'xmpps://pass@localhost/'
                 'user@test.com, user2@test.com/resource',
            'p': 'xmpps://****@localhost',
        }, {
            'u': 'xmpps://pass@localhost:5226?jid=user@test.com',
            'p': 'xmpps://****@localhost:5226',
        }, {
            'u': 'xmpps://pass@localhost?jid=user@test.com&verify=False',
            'p': 'xmpps://****@localhost',
        }, {
            'u': 'xmpps://user:pass@localhost?verify=False',
            'p': 'xmpps://user:****@localhost',
        }, {
            'u': 'xmpp://user:pass@localhost?to=user@test.com',
            'p': 'xmpp://user:****@localhost',
        }
    )

    # Try Different Variations of our URL
    for entry in urls:

        url = entry['u']
        privacy_url = entry['p']

        obj = apprise.Apprise.instantiate(url, suppress_exceptions=False)

        # Test we loaded
        assert isinstance(obj, apprise.plugins.NotifyXMPP) is True

        # Check that it found our mocked environments
        assert obj._enabled is True

        # Test url() call
        assert isinstance(obj.url(), six.string_types) is True

        # Test url(privacy=True) call
        assert isinstance(obj.url(privacy=True), six.string_types) is True

        assert obj.url(privacy=True).startswith(privacy_url)

        # test notifications
        assert obj.notify(
            title='title', body='body',
            notify_type=apprise.NotifyType.INFO) is True

        # test notification without a title
        assert obj.notify(
            title='', body='body', notify_type=apprise.NotifyType.INFO) is True

    # Toggle our _enabled flag
    obj._enabled = False

    # Verify that we can't send content now
    assert obj.notify(
        title='', body='body', notify_type=apprise.NotifyType.INFO) is False

    # Toggle it back so it doesn't disrupt other testing
    obj._enabled = True

    # create an empty file for now
    ca_cert = tmpdir.mkdir("apprise_xmpp_test").join('ca_cert')
    ca_cert.write('')
    # Update our path
    sys.modules['apprise.plugins.NotifyXMPP']\
        .CA_CERTIFICATE_FILE_LOCATIONS = [str(ca_cert), ]

    obj = apprise.Apprise.instantiate(
        'xmpps://pass@localhost/user@test.com',
        suppress_exceptions=False)

    # Our notification now should be able to get a ca_cert to reference
    assert obj.notify(
        title='', body='body', notify_type=apprise.NotifyType.INFO) is True
