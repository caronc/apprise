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
import pytest
from unittest import mock

import sys
import types
import apprise
from helpers import module_reload
from importlib import reload


# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

if 'dbus' not in sys.modules:
    # Environment doesn't allow for dbus
    pytest.skip("Skipping dbus-python based tests", allow_module_level=True)

from dbus import DBusException  # noqa E402
from apprise.plugins.NotifyDBus import DBusUrgency  # noqa E402


@mock.patch('dbus.SessionBus')
@mock.patch('dbus.Interface')
@mock.patch('dbus.ByteArray')
@mock.patch('dbus.Byte')
@mock.patch('dbus.mainloop')
def test_plugin_dbus_general(mock_mainloop, mock_byte, mock_bytearray,
                             mock_interface, mock_sessionbus):
    """
    NotifyDBus() General Tests
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

    mock_mainloop.glib.NativeMainLoop.return_value = True
    mock_mainloop.glib.NativeMainLoop.side_effect = ImportError()
    sys.modules['dbus.mainloop.glib'] = mock_mainloop.glib
    reload(sys.modules['apprise.plugins.NotifyDBus'])
    mock_mainloop.glib.DBusGMainLoop.side_effect = None
    mock_mainloop.glib.NativeMainLoop.side_effect = None

    module_reload('NotifyDBus')

    # Create our instance (identify all supported types)
    obj = apprise.Apprise.instantiate('dbus://', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('dbus://_/')
    obj = apprise.Apprise.instantiate('kde://', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('kde://_/')
    obj = apprise.Apprise.instantiate('qt://', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('qt://_/')
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('glib://_/')
    obj.duration = 0

    # Test our class loading using a series of arguments
    with pytest.raises(TypeError):
        apprise.plugins.NotifyDBus(**{'schema': 'invalid'})

    # Set our X and Y coordinate and try the notification
    assert apprise.plugins.NotifyDBus(
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
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('dbus://_/')
    assert re.search('image=yes', obj.url())

    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?image=False', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.url().startswith('dbus://_/')
    assert re.search('image=no', obj.url())

    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Test priority (alias to urgency) handling
    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=invalid', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=high', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?priority=2', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Test urgency handling
    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=invalid', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=high', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=2', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'dbus://_/?urgency=', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Test x/y
    obj = apprise.Apprise.instantiate(
        'dbus://_/?x=5&y=5', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    with pytest.raises(TypeError):
        obj = apprise.Apprise.instantiate(
            'dbus://_/?x=invalid&y=invalid', suppress_exceptions=False)

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

    # If our underlining object throws for whatever rea on, we will
    # gracefully fail
    mock_notify = mock.Mock()
    mock_interface.return_value = mock_notify
    mock_notify.Notify.side_effect = AttributeError()
    assert obj.notify(
        title='', body='body',
        notify_type=apprise.NotifyType.INFO) is False
    mock_notify.Notify.side_effect = None

    # Test our loading of our icon exception; it will still allow the
    # notification to be sent
    mock_pixbuf.new_from_file.side_effect = AttributeError()
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True
    # Undo our change
    mock_pixbuf.new_from_file.side_effect = None

    # Test our exception handling during initialization
    # Toggle our testing for when we can't send notifications because the
    # package has been made unavailable to us
    obj.enabled = False
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False

    # Test the setting of a the urgency
    apprise.plugins.NotifyDBus(urgency=0)

    #
    # We can still notify if the gi library is the only inaccessible
    # compontent
    #

    # Emulate require_version function:
    gi.require_version.side_effect = ImportError()
    module_reload('NotifyDBus')

    # Create our instance
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    obj.duration = 0

    # Test url() call
    assert isinstance(obj.url(), str) is True

    # Our notification succeeds even though the gi library was not loaded
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Verify this all works in the event a ValueError is also thronw
    # out of the call to gi.require_version()

    mock_sessionbus.side_effect = DBusException('test')
    # Handle Dbus Session Initialization error
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False

    # Return side effect to normal
    mock_sessionbus.side_effect = None

    # Emulate require_version function:
    gi.require_version.side_effect = ValueError()
    module_reload('NotifyDBus')

    # Create our instance
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert isinstance(obj, apprise.plugins.NotifyDBus) is True
    obj.duration = 0

    # Test url() call
    assert isinstance(obj.url(), str) is True

    # Our notification succeeds even though the gi library was not loaded
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    # Force a global import error
    _session_bus = sys.modules['dbus']
    sys.modules['dbus'] = compile('raise ImportError()', 'dbus', 'exec')

    # Reload our modules
    module_reload('NotifyDBus')

    # We can no longer instantiate an instance because dbus has been
    # officialy marked unavailable and thus the module is marked
    # as such
    obj = apprise.Apprise.instantiate('glib://', suppress_exceptions=False)
    assert obj is None

    # Since playing with the sys.modules is not such a good idea,
    # let's just put our old configuration back:
    sys.modules['dbus'] = _session_bus
    # Reload our modules
    module_reload('NotifyDBus')
