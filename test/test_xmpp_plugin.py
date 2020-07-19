# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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
import os
import sys
import ssl
import mock
import pytest
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


@pytest.mark.skipif(
    'sleekxmpp' not in sys.modules, reason="requires sleekxmpp")
def test_xmpp_plugin_import_error(tmpdir):
    """
    API: NotifyXMPP Plugin() Import Error

    """
    # This is a really confusing test case; it can probably be done better,
    # but this was all I could come up with.  Effectively Apprise is will
    # still work flawlessly without the sleekxmpp dependancy.  Since
    # sleekxmpp is actually required to be installed to run these unit tests
    # we need to do some hacky tricks into fooling our test cases that the
    # package isn't available.

    # So we create a temporary directory called sleekxmpp (simulating the
    # library itself) and writing an __init__.py in it that does nothing
    # but throw an ImportError exception (simulating that the library
    # isn't found).
    suite = tmpdir.mkdir("sleekxmpp")
    suite.join("__init__.py").write('')
    module_name = 'sleekxmpp'
    suite.join("{}.py".format(module_name)).write('raise ImportError()')

    # The second part of the test is to update our PYTHON_PATH to look
    # into this new directory first (before looking where the actual
    # valid paths are).  This will allow us to override 'JUST' the sleekxmpp
    # path.

    # Update our path to point to our new test suite
    sys.path.insert(0, str(suite))

    # We need to remove the sleekxmpp modules that have already been loaded
    # in memory otherwise they'll just be used instead. Python is smart and
    # won't go try and reload everything again if it doesn't have to.
    for name in list(sys.modules.keys()):
        if name.startswith('{}.'.format(module_name)):
            del sys.modules[name]
    del sys.modules[module_name]
    del sys.modules['apprise.plugins.NotifyXMPP.SleekXmppAdapter']

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

    # This tests that Apprise still works without sleekxmpp.
    # XMPP objects can still be instantiated in these cases.
    obj = apprise.Apprise.instantiate('xmpp://user:pass@localhost')
    assert obj is not None

    # Tidy-up / restore things to how they were
    # Remove our garbage library
    os.unlink(str(suite.join("{}.py".format(module_name))))

    # Remove our custom entry into the path
    sys.path.remove(str(suite))

    # Reload the libraries we care about
    reload(sys.modules['apprise.plugins.NotifyXMPP.SleekXmppAdapter'])
    reload(sys.modules['apprise.plugins.NotifyXMPP'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])


@pytest.mark.skipif(
    'sleekxmpp' not in sys.modules, reason="requires sleekxmpp")
def test_xmpp_plugin(tmpdir):
    """
    API: NotifyXMPP Plugin()
    """

    # Set success flag
    apprise.plugins.SleekXmppAdapter.success = True

    # Create a restore point
    ca_backup = apprise.plugins.SleekXmppAdapter\
        .CA_CERTIFICATE_FILE_LOCATIONS

    # Clear CA Certificates
    apprise.plugins.SleekXmppAdapter.CA_CERTIFICATE_FILE_LOCATIONS = []

    # Disable Throttling to speed testing
    apprise.plugins.NotifyBase.request_rate_per_sec = 0

    # Create our instance
    obj = apprise.Apprise.instantiate('xmpp://', suppress_exceptions=False)

    # Not possible because no password or host was specified
    assert obj is None

    with pytest.raises(TypeError):
        apprise.Apprise.instantiate(
            'xmpp://hostname', suppress_exceptions=False)

    # SSL Flags
    if hasattr(ssl, "PROTOCOL_TLS"):
        # Test cases where PROTOCOL_TLS simply isn't available
        ssl_temp_swap = ssl.PROTOCOL_TLS
        del ssl.PROTOCOL_TLS

        # Test our URL
        url = 'xmpps://user:pass@127.0.0.1'
        obj = apprise.Apprise.instantiate(url, suppress_exceptions=False)

        # Test we loaded
        assert isinstance(obj, apprise.plugins.NotifyXMPP) is True

        # Check that it found our mocked environments
        assert obj._enabled is True

        with mock.patch('sleekxmpp.ClientXMPP') as mock_stream:
            client_stream = mock.Mock()
            client_stream.connect.return_value = True
            mock_stream.return_value = client_stream

            # We fail because we could not verify the host
            assert obj.notify(
                title='title', body='body',
                notify_type=apprise.NotifyType.INFO) is False

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

        # Check that it found our mocked environments
        assert obj._enabled is True

        with mock.patch('sleekxmpp.ClientXMPP') as mock_stream:
            client_stream = mock.Mock()
            client_stream.connect.return_value = True
            mock_stream.return_value = client_stream

            assert obj.notify(
                title='title', body='body',
                notify_type=apprise.NotifyType.INFO) is True

        # Restore settings as they were
        del ssl.PROTOCOL_TLS

    urls = (
        {
            'u': 'xmpp://user:pass@localhost',
            'p': 'xmpp://user:****@localhost',
        }, {
            'u': 'xmpp://user:pass@localhost?'
                 'xep=30,199,garbage,xep_99999999',
            'p': 'xmpp://user:****@localhost',
        }, {
            'u': 'xmpps://user:pass@localhost?xep=ignored&verify=no',
            'p': 'xmpps://user:****@localhost',
        }, {
            'u': 'xmpps://pass@localhost/?verify=false'
                 'user@test.com, user2@test.com/resource',
            'p': 'xmpps://****@localhost',
        }, {
            'u': 'xmpps://pass@localhost:5226?jid=user@test.com&verify=no',
            'p': 'xmpps://****@localhost:5226',
        }, {
            'u': 'xmpps://pass@localhost?jid=user@test.com&verify=False',
            'p': 'xmpps://****@localhost',
        }, {
            'u': 'xmpps://user:pass@localhost?verify=False',
            'p': 'xmpps://user:****@localhost',
        }, {
            'u': 'xmpp://user:pass@localhost?to=user@test.com&verify=no',
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

        with mock.patch('sleekxmpp.ClientXMPP') as mock_stream:
            client_stream = mock.Mock()
            client_stream.connect.return_value = True
            mock_stream.return_value = client_stream

            # test notifications
            assert obj.notify(
                title='title', body='body',
                notify_type=apprise.NotifyType.INFO) is True

            # test notification without a title
            assert obj.notify(
                title='', body='body',
                notify_type=apprise.NotifyType.INFO) is True

        # Test Connection Failure
        with mock.patch('sleekxmpp.ClientXMPP') as mock_stream:
            client_stream = mock.Mock()
            client_stream.connect.return_value = False
            mock_stream.return_value = client_stream

            # test notifications
            assert obj.notify(
                title='title', body='body',
                notify_type=apprise.NotifyType.INFO) is False

    # Toggle our _enabled flag
    obj._enabled = False

    with mock.patch('sleekxmpp.ClientXMPP') as mock_client:
        # Allow a connection to succeed
        mock_client.connect.return_value = True

        # Verify that we can't send content now
        assert obj.notify(
            title='', body='body',
            notify_type=apprise.NotifyType.INFO) is False

    # Toggle it back so it doesn't disrupt other testing
    obj._enabled = True

    # create an empty file for now
    ca_cert = tmpdir.mkdir("apprise_xmpp_test").join('ca_cert')
    ca_cert.write('')

    # Update our path
    apprise.plugins.SleekXmppAdapter.CA_CERTIFICATE_FILE_LOCATIONS = \
        [str(ca_cert), ]

    obj = apprise.Apprise.instantiate(
        'xmpps://pass@localhost/user@test.com?verify=yes',
        suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyXMPP) is True

    with mock.patch('sleekxmpp.ClientXMPP') as mock_client:
        # Allow a connection to succeed
        mock_client.connect.return_value = True
        # Our notification now should be able to get a ca_cert to reference
        assert obj.notify(
            title='', body='body', notify_type=apprise.NotifyType.INFO) is True

    # Restore our CA Certificates from backup
    apprise.plugins.SleekXmppAdapter.CA_CERTIFICATE_FILE_LOCATIONS = \
        ca_backup


@pytest.mark.skipif(
    'sleekxmpp' not in sys.modules, reason="requires sleekxmpp")
def test_sleekxmpp_callbacks():
    """
    API: NotifyXMPP Plugin() Sleekxmpp callback tests

    The tests identified here just test the basic callbacks defined for
    sleekxmpp.  Emulating a full xmpp server in order to test this plugin
    proved to be difficult so just here are some basic tests to make sure code
    doesn't produce any exceptions. This is a perfect solution to get 100%
    test coverage of the NotifyXMPP plugin, but it's better than nothing at
    all.
    """
    def dummy_before_message():
        # Just a dummy function for testing purposes
        return

    kwargs = {
        'host': 'localhost',
        'port': 5555,
        'secure': False,
        'verify_certificate': False,
        'xep': [
            # xep_0030: Service Discovery
            30,
            # xep_0199: XMPP Ping
            199,
        ],
        'jid': 'user@localhost',
        'password': 'secret!',
        'body': 'my message to delivery!',
        'targets': ['user2@localhost'],
        'before_message': dummy_before_message,
        'logger': None,
    }

    # Set success flag
    apprise.plugins.SleekXmppAdapter.success = False

    with mock.patch('sleekxmpp.ClientXMPP') as mock_stream:
        client_stream = mock.Mock()
        client_stream.send_message.return_value = True
        mock_stream.return_value = client_stream

        adapter = apprise.plugins.SleekXmppAdapter(**kwargs)
        assert isinstance(adapter, apprise.plugins.SleekXmppAdapter)

        # Ensure we are initialized in a failure state; our return flag after
        # we actually attempt to send the notification(s). This get's toggled
        # to true only after a session_start() call is done successfully
        assert adapter.success is False
        adapter.session_start()
        assert adapter.success is True

    # Now we'll do a test with no one to notify
    kwargs['targets'] = []
    adapter = apprise.plugins.SleekXmppAdapter(**kwargs)
    assert isinstance(adapter, apprise.plugins.SleekXmppAdapter)

    # success flag should be back to a False state
    assert adapter.success is False

    with mock.patch('sleekxmpp.ClientXMPP') as mock_stream:
        client_stream = mock.Mock()
        client_stream.send_message.return_value = True
        mock_stream.return_value = client_stream
        adapter.session_start()
        # success flag changes to True
        assert adapter.success is True

    # Restore our target, but set up invalid xep codes
    kwargs['targets'] = ['user2@localhost']
    kwargs['xep'] = [1, 999]
    with pytest.raises(ValueError):
        apprise.plugins.SleekXmppAdapter(**kwargs)
