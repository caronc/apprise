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
import pytest
import mock
import sys
import types
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

if 'dbus' not in sys.modules:
    # Environment doesn't allow for dbus
    pytest.skip("Skipping dbus-python based tests", allow_module_level=True)


@mock.patch('dbus.SessionBus')
@mock.patch('dbus.Interface')
@mock.patch('dbus.ByteArray')
@mock.patch('dbus.Byte')
@mock.patch('dbus.mainloop')
def test_dbus_plugin(mock_mainloop, mock_byte, mock_bytearray,
                     mock_interface, mock_sessionbus):
    """
    API: NotifyDBus Plugin()

    """

    # Our module base
    gi_name = 'gi'

    # First we do an import without the gi library available to ensure
    # we can handle cases when the library simply isn't available

    if gi_name in sys.modules:
        # Test cases where the gi library exists; we want to remove it
        # for the purpose of testing and capture the handling of the
        # library when it is missing
        del sys.modules[gi_name]
        reload(sys.modules['apprise.plugins.NotifyDBus'])

    # We need to fake our dbus environment for testing purposes since
    # the gi library isn't available in Travis CI
    gi = types.ModuleType(gi_name)
    gi.repository = types.ModuleType(gi_name + '.repository')

    mock_pixbuf = mock.Mock()
    mock_image = mock.Mock()
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
    gi.require_version = mock.Mock(
        name=gi_name + '.require_version')

    # Force the fake module to exist
    sys.modules[gi_name] = gi
    sys.modules[gi_name + '.repository'] = gi.repository

    # Exception Handling
    mock_mainloop.qt.DBusQtMainLoop.return_value = True
    mock_mainloop.qt.DBusQtMainLoop.side_effect = ImportError
    sys.modules['dbus.mainloop.qt'] = mock_mainloop.qt
    reload(sys.modules['apprise.plugins.NotifyDBus'])
    mock_mainloop.qt.DBusQtMainLoop.side_effect = None

    # Python v2.x
    mock_mainloop.glib.DBusGMainLoop.return_value = True
    mock_mainloop.glib.DBusGMainLoop.side_effect = ImportError()
    # Python 3.x
    mock_mainloop.glib.NativeMainLoop.return_value = True
    mock_mainloop.glib.NativeMainLoop.side_effect = ImportError()
    sys.modules['dbus.mainloop.glib'] = mock_mainloop.glib
    reload(sys.modules['apprise.plugins.NotifyDBus'])
    mock_mainloop.glib.DBusGMainLoop.side_effect = None
    mock_mainloop.glib.NativeMainLoop.side_effect = None

    # The following libraries need to be reloaded to prevent
    #  TypeError: super(type, obj): obj must be an instance or subtype of type
    #  This is better explained in this StackOverflow post:
    #     https://stackoverflow.com/questions/31363311/\
    #       any-way-to-manually-fix-operation-of-\
    #          super-after-ipython-reload-avoiding-ty
    #
    reload(sys.modules['apprise.plugins.NotifyDBus'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])

    # Create our instance (identify all supported types)
    obj = apprise.Apprise.instantiate('dbus://', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    obj = apprise.Apprise.instantiate('kde://', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    obj = apprise.Apprise.instantiate('qt://', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    obj.duration = 0

    # Check that it found our mocked environments
    assert(obj._enabled is True)

    # Test our class loading using a series of arguments
    try:
        apprise.plugins.NotifyDBus(**{'schema': 'invalid'})
        # We should not reach here as the invalid schema
        # should force an exception
        assert(False)
    except TypeError:
        # Expected behaviour
        assert(True)

    # Invalid URLs
    assert apprise.plugins.NotifyDBus.parse_url('') is None

    # Set our X and Y coordinate and try the notification
    assert(
        apprise.plugins.NotifyDBus(
            x_axis=0, y_axis=0, **{'schema': 'dbus'})
        .notify(title='', body='body',
                notify_type=apprise.NotifyType.INFO) is True)

    # test notifications
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # test notification without a title
    assert(obj.notify(title='', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # Test our arguments through the instantiate call
    obj = apprise.Apprise.instantiate(
        'dbus://_/?image=True', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    obj = apprise.Apprise.instantiate(
        'dbus://_/?image=False', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # Test priority (alias to urgency) handling
    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=invalid', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=high', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=2', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # Test urgency handling
    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=invalid', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=high', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=2', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # Test x/y
    obj = apprise.Apprise.instantiate(
        'dbus://_/?x=5&y=5', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    obj = apprise.Apprise.instantiate(
        'dbus://_/?x=invalid&y=invalid', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    assert(isinstance(obj.url(), six.string_types) is True)
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # If our underlining object throws for whatever reason, we will
    # gracefully fail
    mock_notify = mock.Mock()
    mock_interface.return_value = mock_notify
    mock_notify.Notify.side_effect = AttributeError()
    assert(obj.notify(title='', body='body',
           notify_type=apprise.NotifyType.INFO) is False)
    mock_notify.Notify.side_effect = None

    # Test our loading of our icon exception; it will still allow the
    # notification to be sent
    mock_pixbuf.new_from_file.side_effect = AttributeError()
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)
    # Undo our change
    mock_pixbuf.new_from_file.side_effect = None

    # Test our exception handling during initialization
    # Toggle our testing for when we can't send notifications because the
    # package has been made unavailable to us
    obj._enabled = False
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is False)

    # Test the setting of a the urgency
    apprise.plugins.NotifyDBus(urgency=0)

    #
    # We can still notify if the gi library is the only inaccessible
    # compontent
    #

    # Emulate require_version function:
    gi.require_version.side_effect = ImportError()

    # The following libraries need to be reloaded to prevent
    #  TypeError: super(type, obj): obj must be an instance or subtype of type
    #  This is better explained in this StackOverflow post:
    #     https://stackoverflow.com/questions/31363311/\
    #       any-way-to-manually-fix-operation-of-\
    #          super-after-ipython-reload-avoiding-ty
    #
    reload(sys.modules['apprise.plugins.NotifyDBus'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])

    # Create our instance
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    obj.duration = 0

    # Test url() call
    assert(isinstance(obj.url(), six.string_types) is True)

    # Our notification succeeds even though the gi library was not loaded
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # Verify this all works in the event a ValueError is also thronw
    # out of the call to gi.require_version()

    # Emulate require_version function:
    gi.require_version.side_effect = ValueError()

    # The following libraries need to be reloaded to prevent
    #  TypeError: super(type, obj): obj must be an instance or subtype of type
    #  This is better explained in this StackOverflow post:
    #     https://stackoverflow.com/questions/31363311/\
    #       any-way-to-manually-fix-operation-of-\
    #          super-after-ipython-reload-avoiding-ty
    #
    reload(sys.modules['apprise.plugins.NotifyDBus'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])

    # Create our instance
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    obj.duration = 0

    # Test url() call
    assert(isinstance(obj.url(), six.string_types) is True)

    # Our notification succeeds even though the gi library was not loaded
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # Force a global import error
    _session_bus = sys.modules['dbus']
    sys.modules['dbus'] = compile('raise ImportError()', 'dbus', 'exec')

    # Reload our modules
    reload(sys.modules['apprise.plugins.NotifyDBus'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])

    # Create our instance
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert(isinstance(obj, apprise.plugins.NotifyDBus) is True)
    obj.duration = 0

    # Test url() call
    assert(isinstance(obj.url(), six.string_types) is True)

    # Our notification fail because the dbus library wasn't present
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is False)

    # Since playing with the sys.modules is not such a good idea,
    # let's just put it back now :)
    sys.modules['dbus'] = _session_bus
    # Reload our modules
    reload(sys.modules['apprise.plugins.NotifyDBus'])
    reload(sys.modules['apprise.plugins'])
    reload(sys.modules['apprise.Apprise'])
    reload(sys.modules['apprise'])
