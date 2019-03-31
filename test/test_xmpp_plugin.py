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
import mock
import sys
import ssl

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

    # Our module base
    sleekxmpp_name = 'sleekxmpp'

    # First we do an import without the sleekxmpp library available to ensure
    # we can handle cases when the library simply isn't available

    if sleekxmpp_name in sys.modules:
        # Test cases where the sleekxmpp library exists; we want to remove it
        # for the purpose of testing and capture the handling of the
        # library when it is missing
        del sys.modules[sleekxmpp_name]
        reload(sys.modules['apprise.plugins.NotifyXMPP'])

    # We need to fake our gnome environment for testing purposes since
    # the sleekxmpp library isn't available in Travis CI
    sys.modules[sleekxmpp_name] = mock.MagicMock()

    xmpp = mock.Mock()
    xmpp.register_plugin.return_value = True
    xmpp.send_message.return_value = True
    xmpp.connect.return_value = True
    xmpp.disconnect.return_value = True
    xmpp.send_presence.return_value = True
    xmpp.get_roster.return_value = True
    xmpp.ssl_version = None

    class IqError(Exception):
        iq = {'error': {'condition': 'test'}}
        pass

    class IqTimeout(Exception):
        pass

    # Setup our Exceptions
    sys.modules[sleekxmpp_name].exceptions.IqError = IqError
    sys.modules[sleekxmpp_name].exceptions.IqTimeout = IqTimeout

    sys.modules[sleekxmpp_name].ClientXMPP.return_value = xmpp

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

    # An empty CA list
    sys.modules['apprise.plugins.NotifyXMPP']\
        .CA_CERTIFICATE_FILE_LOCATIONS = []

    # Disable Throttling to speed testing
    apprise.plugins.NotifyBase.NotifyBase.request_rate_per_sec = 0

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
        url = 'xmpps://user:pass@example.com'
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
        url = 'xmpps://user:pass@example.com'
        obj = apprise.Apprise.instantiate(url, suppress_exceptions=False)
        # Test we loaded
        assert isinstance(obj, apprise.plugins.NotifyXMPP) is True
        assert obj.notify(
            title='title', body='body',
            notify_type=apprise.NotifyType.INFO) is True

        # Restore settings as they were
        del ssl.PROTOCOL_TLS

    # Try Different Variations of our URL
    for url in (
            'xmpps://user:pass@example.com',
            'xmpps://user:pass@example.com?xep=30,199,garbage,xep_99999999',
            'xmpps://user:pass@example.com?xep=ignored',
            'xmpps://pass@example.com/user@test.com, user2@test.com/resource',
            'xmpps://pass@example.com:5226?jid=user@test.com',
            'xmpps://pass@example.com?jid=user@test.com&verify=False',
            'xmpps://user:pass@example.com?verify=False',
            'xmpp://user:pass@example.com?to=user@test.com'):

        obj = apprise.Apprise.instantiate(url, suppress_exceptions=False)

        # Test we loaded
        assert isinstance(obj, apprise.plugins.NotifyXMPP) is True

        # Check that it found our mocked environments
        assert obj._enabled is True

        # Test url() call
        assert isinstance(obj.url(), six.string_types) is True

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
        'xmpps://pass@example.com/user@test.com',
        suppress_exceptions=False)

    # Our notification now should be able to get a ca_cert to reference
    assert obj.notify(
        title='', body='body', notify_type=apprise.NotifyType.INFO) is True

    # Test Connect Failures
    xmpp.connect.return_value = False
    assert obj.notify(
        title='', body='body', notify_type=apprise.NotifyType.INFO) is False

    # Return our object value so we don't obstruct other tests
    xmpp.connect.return_value = True

    # Test Exceptions
    xmpp.get_roster.side_effect = \
        sys.modules[sleekxmpp_name].exceptions.IqTimeout()

    assert obj.notify(
        title='', body='body', notify_type=apprise.NotifyType.INFO) is False
    xmpp.get_roster.side_effect = None

    xmpp.get_roster.side_effect = \
        sys.modules[sleekxmpp_name].exceptions.IqError()
    assert obj.notify(
        title='', body='body', notify_type=apprise.NotifyType.INFO) is False
    xmpp.get_roster.side_effect = None
