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

import importlib
import logging
import re
import sys
import types
from unittest.mock import Mock, call, ANY

import pytest

import apprise
from helpers import reload_plugin


# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


# Skip tests when Python environment does not provide the `dbus` package.
if 'dbus' not in sys.modules:
    pytest.skip("Skipping dbus-python based tests", allow_module_level=True)


from dbus import DBusException  # noqa E402
from apprise.plugins.NotifyDBus import DBusUrgency, NotifyDBus  # noqa E402


def setup_glib_environment():
    """
    Setup a heavily mocked Glib environment.
    """
    mock_mainloop = Mock()

    # Our module base
    gi_name = 'gi'

    # First we do an import without the gi library available to ensure
    # we can handle cases when the library simply isn't available

    if gi_name in sys.modules:
        # Test cases where the gi library exists; we want to remove it
        # for the purpose of testing and capture the handling of the
        # library when it is missing
        del sys.modules[gi_name]
        importlib.reload(sys.modules['apprise.plugins.NotifyDBus'])

    # We need to fake our dbus environment for testing purposes since
    # the gi library isn't available on CI
    gi = types.ModuleType(gi_name)
    gi.repository = types.ModuleType(gi_name + '.repository')

    mock_pixbuf = Mock()
    mock_image = Mock()
    mock_pixbuf.new_from_file.return_value = mock_image

    mock_image.get_width.return_value = 100
    mock_image.get_height.return_value = 100
    mock_image.get_rowstride.return_value = 1
    mock_image.get_has_alpha.return_value = 0
    mock_image.get_bits_per_sample.return_value = 8
    mock_image.get_n_channels.return_value = 1
    mock_image.get_pixels.return_value = ''

    gi.repository.GdkPixbuf = \
        types.ModuleType(gi_name + '.repository.GdkPixbuf')
    gi.repository.GdkPixbuf.Pixbuf = mock_pixbuf

    # Emulate require_version function:
    gi.require_version = Mock(
        name=gi_name + '.require_version')

    # Force the fake module to exist
    sys.modules[gi_name] = gi
    sys.modules[gi_name + '.repository'] = gi.repository

    # Exception Handling
    mock_mainloop.qt.DBusQtMainLoop.return_value = True
    mock_mainloop.qt.DBusQtMainLoop.side_effect = ImportError
    sys.modules['dbus.mainloop.qt'] = mock_mainloop.qt
    mock_mainloop.qt.DBusQtMainLoop.side_effect = None

    mock_mainloop.glib.NativeMainLoop.return_value = True
    mock_mainloop.glib.NativeMainLoop.side_effect = ImportError()
    sys.modules['dbus.mainloop.glib'] = mock_mainloop.glib
    mock_mainloop.glib.DBusGMainLoop.side_effect = None
    mock_mainloop.glib.NativeMainLoop.side_effect = None

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    reload_plugin('NotifyDBus')


@pytest.fixture
def dbus_environment(mocker):
    """
    Fixture to provide a mocked Dbus environment to test case functions.
    """
    interface_mock = mocker.patch('dbus.Interface', spec=True,
                                  Notify=Mock())
    mocker.patch('dbus.SessionBus', spec=True,
                 **{"get_object.return_value": interface_mock})


@pytest.fixture
def glib_environment():
    """
    Fixture to provide a mocked Glib environment to test case functions.
    """
    setup_glib_environment()


@pytest.fixture
def dbus_glib_environment(dbus_environment, glib_environment):
    """
    Fixture to provide a mocked Glib/DBus environment to test case functions.
    """
    pass


def test_plugin_dbus_general_success(mocker, dbus_glib_environment):
    """
    NotifyDBus() general tests

    Test class loading using different arguments, provided via URL.
    """

    # Create our instance (identify all supported types)
    obj = apprise.Apprise.instantiate('dbus://', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('dbus://_/')
    obj = apprise.Apprise.instantiate('kde://', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('kde://_/')
    obj = apprise.Apprise.instantiate('qt://', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('qt://_/')
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('glib://_/')
    obj.duration = 0

    # Set our X and Y coordinate and try the notification
    assert NotifyDBus(
        x_axis=0, y_axis=0, **{'schema': 'dbus'})\
        .notify(title='', body='body',
                notify_type=apprise.NotifyType.INFO) is True

    # test notifications
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # test notification without a title
    assert obj.notify(
        title='', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Test our arguments through the instantiate call
    obj = apprise.Apprise.instantiate(
        'dbus://_/?image=True', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('dbus://_/')
    assert re.search('image=yes', obj.url())

    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?image=False', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('dbus://_/')
    assert re.search('image=no', obj.url())

    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Test priority (alias to urgency) handling
    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=invalid', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=high', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=2', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Test urgency handling
    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=invalid', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=high', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=2', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Test x/y
    obj = apprise.Apprise.instantiate(
        'dbus://_/?x=5&y=5', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True


def test_plugin_dbus_general_failure(dbus_glib_environment):
    """
    Verify a few failure conditions.
    """

    with pytest.raises(TypeError):
        NotifyDBus(**{'schema': 'invalid'})

    with pytest.raises(TypeError):
        apprise.Apprise.instantiate('dbus://_/?x=invalid&y=invalid',
                                    suppress_exceptions=False)


def test_plugin_dbus_parse_configuration(dbus_glib_environment):

    # Test configuration parsing
    content = """
    urls:
      - dbus://:
          - priority: 0
            tag: dbus_int low
          - priority: "0"
            tag: dbus_str_int low
          - priority: low
            tag: dbus_str low
          - urgency: 0
            tag: dbus_int low
          - urgency: "0"
            tag: dbus_str_int low
          - urgency: low
            tag: dbus_str low

          # These will take on normal (default) urgency
          - priority: invalid
            tag: dbus_invalid
          - urgency: invalid
            tag: dbus_invalid

      - dbus://:
          - priority: 2
            tag: dbus_int high
          - priority: "2"
            tag: dbus_str_int high
          - priority: high
            tag: dbus_str high
          - urgency: 2
            tag: dbus_int high
          - urgency: "2"
            tag: dbus_str_int high
          - urgency: high
            tag: dbus_str high
    """

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 14 servers from that
    # 6x low
    # 6x high
    # 2x invalid (so takes on normal urgency)
    assert len(ac.servers()) == 14
    assert len(aobj) == 14
    assert len([x for x in aobj.find(tag='low')]) == 6
    for s in aobj.find(tag='low'):
        assert s.urgency == DBusUrgency.LOW

    assert len([x for x in aobj.find(tag='high')]) == 6
    for s in aobj.find(tag='high'):
        assert s.urgency == DBusUrgency.HIGH

    assert len([x for x in aobj.find(tag='dbus_str')]) == 4
    assert len([x for x in aobj.find(tag='dbus_str_int')]) == 4
    assert len([x for x in aobj.find(tag='dbus_int')]) == 4

    assert len([x for x in aobj.find(tag='dbus_invalid')]) == 2
    for s in aobj.find(tag='dbus_invalid'):
        assert s.urgency == DBusUrgency.NORMAL


def test_plugin_dbus_missing_icon(mocker, dbus_glib_environment):
    """
    Test exception when loading icon; the notification will still be sent.
    """

    # Inject error when loading icon.
    gi = importlib.import_module("gi")
    gi.repository.GdkPixbuf.Pixbuf.new_from_file.side_effect = \
        AttributeError("Something failed")

    obj = apprise.Apprise.instantiate('dbus://', suppress_exceptions=False)
    logger: Mock = mocker.spy(obj, "logger")
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True
    assert logger.mock_calls == [
        call.warning('Could not load notification icon (%s).', ANY),
        call.debug('DBus Exception: Something failed'),
        call.info('Sent DBus notification.'),
    ]


def test_plugin_dbus_disabled_plugin(dbus_glib_environment):
    """
    Verify notification will not be submitted if plugin is disabled.
    """
    obj = apprise.Apprise.instantiate('dbus://', suppress_exceptions=False)

    obj.enabled = False

    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False


def test_plugin_dbus_set_urgency():
    """
    Test the setting of an urgency.
    """
    NotifyDBus(urgency=0)


def test_plugin_dbus_gi_missing(dbus_glib_environment):
    """
    Verify notification succeeds even if the `gi` package is not available.
    """

    # Make `require_version` function raise an ImportError.
    gi = importlib.import_module("gi")
    gi.require_version.side_effect = ImportError()

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    reload_plugin('NotifyDBus')

    # Create the instance.
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    obj.duration = 0

    # Test url() call.
    assert isinstance(obj.url(), str) is True

    # The notification succeeds even though the gi library was not loaded.
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True


def test_plugin_dbus_gi_require_version_error(dbus_glib_environment):
    """
    Verify notification succeeds even if `gi.require_version()` croaks.
    """

    # Make `require_version` function raise a ValueError.
    gi = importlib.import_module("gi")
    gi.require_version.side_effect = ValueError("Something failed")

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    reload_plugin('NotifyDBus')

    # Create instance.
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    obj.duration = 0

    # Test url() call.
    assert isinstance(obj.url(), str) is True

    # The notification succeeds even though the gi library was not loaded.
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True


def test_plugin_dbus_module_croaks(mocker, dbus_glib_environment):
    """
    Verify plugin is not available when `dbus` module is missing.
    """

    # Make importing `dbus` raise an ImportError.
    mocker.patch.dict(
        sys.modules, {'dbus': compile('raise ImportError()', 'dbus', 'exec')})

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    reload_plugin('NotifyDBus')

    # Verify plugin is not available.
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert obj is None


def test_plugin_dbus_session_croaks(mocker, dbus_glib_environment):
    """
    Verify notification fails if DBus croaks.
    """

    mocker.patch('dbus.SessionBus', side_effect=DBusException('test'))
    setup_glib_environment()

    obj = apprise.Apprise.instantiate('dbus://', suppress_exceptions=False)

    # Emulate DBus session initialization error.
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False


def test_plugin_dbus_interface_notify_croaks(mocker):
    """
    Fail gracefully if underlying object croaks for whatever reason.
    """

    # Inject an error when invoking `dbus.Interface().Notify()`.
    mocker.patch('dbus.SessionBus', spec=True)
    mocker.patch('dbus.Interface', spec=True,
                 Notify=Mock(side_effect=AttributeError("Something failed")))
    setup_glib_environment()

    obj = apprise.Apprise.instantiate('dbus://', suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True

    logger: Mock = mocker.spy(obj, "logger")
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False
    assert [
        call.warning('Failed to send DBus notification.'),
        call.debug('DBus Exception: Something failed'),
    ] in logger.mock_calls
