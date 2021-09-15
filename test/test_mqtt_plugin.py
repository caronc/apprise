# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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

import mock
import re
import sys
import ssl
import six
import os
import pytest

# Rebuild our Apprise environment
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


@pytest.mark.skipif('paho' not in sys.modules, reason="requires paho-mqtt")
def test_paho_mqtt_plugin_import_error(tmpdir):
    """
    API: NotifyMQTT Plugin() Import Error

    """
    # This is a really confusing test case; it can probably be done better,
    # but this was all I could come up with.  Effectively Apprise is will
    # still work flawlessly without the paho dependancy.  Since
    # paho is actually required to be installed to run these unit tests
    # we need to do some hacky tricks into fooling our test cases that the
    # package isn't available.

    # So we create a temporary directory called paho (simulating the
    # library itself) and writing an __init__.py in it that does nothing
    # but throw an ImportError exception (simulating that the library
    # isn't found).
    suite = tmpdir.mkdir("paho")
    suite.join("__init__.py").write('')
    module_name = 'paho'
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

    # The following libraries need to be reloaded to prevent
    #  TypeError: super(type, obj): obj must be an instance or subtype of type
    #  This is better explained in this StackOverflow post:
    #     https://stackoverflow.com/questions/31363311/\
    #       any-way-to-manually-fix-operation-of-\
    #          super-after-ipython-reload-avoiding-ty
    #
    reload(sys.modules['apprise.plugins.NotifyMQTT'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])

    # This tests that Apprise still works without sleekxmpp.
    # XMPP objects can still be instantiated in these cases.
    obj = apprise.Apprise.instantiate('mqtt://user:pass@localhost/my/topic')
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    # We can still retrieve our url back to us
    assert obj.url().startswith('mqtt://user:pass@localhost/my/topic')
    # Notifications are not possible
    assert obj.notify(body="test") is False

    # Tidy-up / restore things to how they were
    # Remove our garbage library
    os.unlink(str(suite.join("{}.py".format(module_name))))

    # Remove our custom entry into the path
    sys.path.remove(str(suite))

    # Reload the libraries we care about
    reload(sys.modules['apprise.plugins.NotifyMQTT'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])


@pytest.mark.skipif(
    'paho' not in sys.modules, reason="requires paho-mqtt")
@mock.patch('paho.mqtt.client.Client')
def test_mqtt_plugin(mock_client):
    """
    API: NotifyMQTT Plugin()

    """
    # Speed up request rate for testing
    apprise.plugins.NotifyBase.request_rate_per_sec = 0

    # our call to publish() response object
    publish_result = mock.Mock()
    publish_result.rc = 0
    publish_result.is_published.return_value = True

    # Our mqtt.Client() object
    _mock_client = mock.Mock()
    _mock_client.connect.return_value = 0
    _mock_client.reconnect.return_value = 0
    _mock_client.is_connected.return_value = True
    _mock_client.publish.return_value = publish_result
    mock_client.return_value = _mock_client

    # Instantiate our object
    obj = apprise.Apprise.instantiate(
        'mqtt://localhost:1234/my/topic', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.url().startswith('mqtt://localhost:1234/my/topic')
    # Detect our defaults
    assert re.search(r'qos=0', obj.url())
    assert re.search(r'version=v3.1.1', obj.url())
    # Send a good notification
    assert obj.notify(body="test=test") is True

    # leverage the to= argument to identify our topic
    obj = apprise.Apprise.instantiate(
        'mqtt://localhost?to=my/topic', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.url().startswith('mqtt://localhost/my/topic')
    # Detect our defaults
    assert re.search(r'qos=0', obj.url())
    assert re.search(r'version=v3.1.1', obj.url())
    # Send a good notification
    assert obj.notify(body="test=test") is True

    # Send a notification in a situation where our publish failed
    publish_result.rc = 2
    assert obj.notify(body="test=test") is False
    # Toggle our response object back to what it should be
    publish_result.rc = 0

    # Test case where we provide an invalid/unsupported mqtt version
    with pytest.raises(TypeError):
        obj = apprise.Apprise.instantiate(
            'mqtt://localhost?version=v1.0.0.0', suppress_exceptions=False)

    # Test case where we provide an invalid/unsupported qos
    with pytest.raises(TypeError):
        obj = apprise.Apprise.instantiate(
            'mqtt://localhost?qos=123', suppress_exceptions=False)
    with pytest.raises(TypeError):
        obj = apprise.Apprise.instantiate(
            'mqtt://localhost?qos=invalid', suppress_exceptions=False)

    # Test a bad URL
    obj = apprise.Apprise.instantiate('mqtt://', suppress_exceptions=False)
    assert obj is None

    # Instantiate our object without any topics
    # we also test that we can set our qos and version if we want from
    # the URL
    obj = apprise.Apprise.instantiate(
        'mqtt://localhost?qos=1&version=v3.1', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.url().startswith('mqtt://localhost')
    assert re.search(r'qos=1', obj.url())
    assert re.search(r'version=v3.1', obj.url())
    assert re.search(r'session=no', obj.url())
    assert re.search(r'client_id=', obj.url()) is None

    # Our notification will fail because we have no topics to notify
    assert obj.notify(body="test=test") is False

    # A Secure URL
    obj = apprise.Apprise.instantiate(
        'mqtts://user:pass@localhost/my/topic', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.url().startswith('mqtts://user:pass@localhost/my/topic')
    assert obj.notify(body="test=test") is True

    # Clear CA Certificates
    ca_certs_backup = \
        list(apprise.plugins.NotifyMQTT.CA_CERTIFICATE_FILE_LOCATIONS)
    apprise.plugins.NotifyMQTT.CA_CERTIFICATE_FILE_LOCATIONS = []
    obj = apprise.Apprise.instantiate(
        'mqtts://user:pass@localhost/my/topic', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.url().startswith('mqtts://user:pass@localhost/my/topic')

    # A notification is not possible now (without ca_certs)
    assert obj.notify(body="test=test") is False

    # Restore our certificates (for future tests)
    apprise.plugins.NotifyMQTT.CA_CERTIFICATE_FILE_LOCATIONS = ca_certs_backup

    # A single user (not password) + no verifying of host
    obj = apprise.Apprise.instantiate(
        'mqtts://user@localhost/my/topic,my/other/topic?verify=False',
        suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.url().startswith('mqtts://user@localhost')
    assert re.search(r'my/other/topic', obj.url())
    assert re.search(r'my/topic', obj.url())
    assert obj.notify(body="test=test") is True

    # Session and client_id handling
    obj = apprise.Apprise.instantiate(
        'mqtts://user@localhost/my/topic?session=yes&client_id=apprise',
        suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.url().startswith('mqtts://user@localhost')
    assert re.search(r'my/topic', obj.url())
    assert re.search(r'client_id=apprise', obj.url())
    assert re.search(r'session=yes', obj.url())
    assert obj.notify(body="test=test") is True

    # handle case where we fail to connect
    _mock_client.connect.return_value = 2
    obj = apprise.Apprise.instantiate(
        'mqtt://localhost/my/topic', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.notify(body="test=test") is False
    # Restore our values
    _mock_client.connect.return_value = 0

    # handle case where we fail to reconnect
    _mock_client.reconnect.return_value = 2
    _mock_client.is_connected.return_value = False
    obj = apprise.Apprise.instantiate(
        'mqtt://localhost/my/topic', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.notify(body="test=test") is False
    # Restore our values
    _mock_client.reconnect.return_value = 0
    _mock_client.is_connected.return_value = True

    # handle case where we fail to publish()
    publish_result.rc = 2
    obj = apprise.Apprise.instantiate(
        'mqtt://localhost/my/topic', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    assert obj.notify(body="test=test") is False
    # Restore our values
    publish_result.rc = 0
    # Set another means of failing publish()
    publish_result.is_published.return_value = False
    assert obj.notify(body="test=test") is False
    # Restore our values
    publish_result.is_published.return_value = True
    # Verify that was all we had to do
    assert obj.notify(body="test=test") is True
    # A slight variation on the same failure (but with recovery)
    publish_result.is_published.return_value = None
    publish_result.is_published.side_effect = (False, True)
    # Our notification is still sent okay
    assert obj.notify(body="test=test") is True

    # Exception handling
    obj = apprise.Apprise.instantiate(
        'mqtt://localhost/my/topic', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyMQTT)
    _mock_client.connect.return_value = None

    if six.PY2:
        # Python v2.7 does not support the ConnectionError exception
        for side_effect in (ValueError, ssl.CertificateError):
            _mock_client.connect.side_effect = side_effect
            assert obj.notify(body="test=test") is False

    else:
        for side_effect in (
                ValueError,
                # Python 2.7 doesn't recognize ConnectionError so for that
                # reason we stick a noqa entry here...
                ConnectionError,  # noqa: F821
                ssl.CertificateError):
            _mock_client.connect.side_effect = side_effect
            assert obj.notify(body="test=test") is False

    # Restore our values
    _mock_client.connect.side_effect = None
    _mock_client.connect.return_value = 0
