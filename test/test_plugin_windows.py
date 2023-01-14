# -*- coding: utf-8 -*-
#
# Apprise - Push Notification Library.
# Copyright (C) 2023  Chris Caron <lead2gold@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor,
# Boston, MA  02110-1301, USA.

import sys
import types
import pytest
from importlib import reload
from unittest import mock

import apprise

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)


@pytest.mark.skipif((
    'win32api' in sys.modules or
    'win32con' in sys.modules or
    'win32gui' in sys.modules), reason="Requires non-windows platform")
def test_plugin_windows_mocked():
    """
    NotifyWindows() General Checks (via non-Windows platform)

    """

    # We need to fake our windows environment for testing purposes
    win32api_name = 'win32api'
    win32api = types.ModuleType(win32api_name)
    sys.modules[win32api_name] = win32api
    win32api.GetModuleHandle = mock.Mock(
        name=win32api_name + '.GetModuleHandle')
    win32api.PostQuitMessage = mock.Mock(
        name=win32api_name + '.PostQuitMessage')

    win32con_name = 'win32con'
    win32con = types.ModuleType(win32con_name)
    sys.modules[win32con_name] = win32con
    win32con.CW_USEDEFAULT = mock.Mock(name=win32con_name + '.CW_USEDEFAULT')
    win32con.IDI_APPLICATION = mock.Mock(
        name=win32con_name + '.IDI_APPLICATION')
    win32con.IMAGE_ICON = mock.Mock(name=win32con_name + '.IMAGE_ICON')
    win32con.LR_DEFAULTSIZE = 1
    win32con.LR_LOADFROMFILE = 2
    win32con.WM_DESTROY = mock.Mock(name=win32con_name + '.WM_DESTROY')
    win32con.WM_USER = 0
    win32con.WS_OVERLAPPED = 1
    win32con.WS_SYSMENU = 2

    win32gui_name = 'win32gui'
    win32gui = types.ModuleType(win32gui_name)
    sys.modules[win32gui_name] = win32gui
    win32gui.CreateWindow = mock.Mock(name=win32gui_name + '.CreateWindow')
    win32gui.DestroyWindow = mock.Mock(name=win32gui_name + '.DestroyWindow')
    win32gui.LoadIcon = mock.Mock(name=win32gui_name + '.LoadIcon')
    win32gui.LoadImage = mock.Mock(name=win32gui_name + '.LoadImage')
    win32gui.NIF_ICON = 1
    win32gui.NIF_INFO = mock.Mock(name=win32gui_name + '.NIF_INFO')
    win32gui.NIF_MESSAGE = 2
    win32gui.NIF_TIP = 4
    win32gui.NIM_ADD = mock.Mock(name=win32gui_name + '.NIM_ADD')
    win32gui.NIM_DELETE = mock.Mock(name=win32gui_name + '.NIM_DELETE')
    win32gui.NIM_MODIFY = mock.Mock(name=win32gui_name + '.NIM_MODIFY')
    win32gui.RegisterClass = mock.Mock(name=win32gui_name + '.RegisterClass')
    win32gui.UnregisterClass = mock.Mock(
        name=win32gui_name + '.UnregisterClass')
    win32gui.Shell_NotifyIcon = mock.Mock(
        name=win32gui_name + '.Shell_NotifyIcon')
    win32gui.UpdateWindow = mock.Mock(name=win32gui_name + '.UpdateWindow')
    win32gui.WNDCLASS = mock.Mock(name=win32gui_name + '.WNDCLASS')

    # The following allows our mocked content to kick in. In python 3.x keys()
    # returns an iterator, therefore we need to convert the keys() back into
    # a list object to prevent from getting the error:
    #    "RuntimeError: dictionary changed size during iteration"
    #
    for mod in list(sys.modules.keys()):
        if mod.startswith('apprise.'):
            del sys.modules[mod]
    reload(apprise)

    # Create our instance
    obj = apprise.Apprise.instantiate('windows://', suppress_exceptions=False)
    obj.duration = 0

    # Test URL functionality
    assert isinstance(obj.url(), str) is True

    # Check that it found our mocked environments
    assert obj.enabled is True

    # _on_destroy check
    obj._on_destroy(0, '', 0, 0)

    # test notifications
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'windows://_/?image=True', suppress_exceptions=False)
    obj.duration = 0
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'windows://_/?image=False', suppress_exceptions=False)
    obj.duration = 0
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'windows://_/?duration=1', suppress_exceptions=False)
    assert isinstance(obj.url(), str) is True
    # loads okay
    assert obj.duration == 1
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'windows://_/?duration=invalid', suppress_exceptions=False)
    # Falls back to default
    assert obj.duration == obj.default_popup_duration_sec

    obj = apprise.Apprise.instantiate(
        'windows://_/?duration=-1', suppress_exceptions=False)
    # Falls back to default
    assert obj.duration == obj.default_popup_duration_sec

    obj = apprise.Apprise.instantiate(
        'windows://_/?duration=0', suppress_exceptions=False)
    # Falls back to default
    assert obj.duration == obj.default_popup_duration_sec

    # To avoid slowdowns (for testing), turn it to zero for now
    obj.duration = 0

    # Test our loading of our icon exception; it will still allow the
    # notification to be sent
    win32gui.LoadImage.side_effect = AttributeError
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True
    # Undo our change
    win32gui.LoadImage.side_effect = None

    # Test our global exception handling
    win32gui.UpdateWindow.side_effect = AttributeError
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False
    # Undo our change
    win32gui.UpdateWindow.side_effect = None

    # Toggle our testing for when we can't send notifications because the
    # package has been made unavailable to us
    obj.enabled = False
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False


@pytest.mark.skipif(
    'win32api' not in sys.modules and
    'win32con' not in sys.modules and
    'win32gui' not in sys.modules,
    reason="Requires win32api, win32con, and win32gui")
@mock.patch('win32gui.UpdateWindow')
@mock.patch('win32gui.Shell_NotifyIcon')
@mock.patch('win32gui.LoadImage')
def test_plugin_windows_native(mock_loadimage,
                               mock_notify,
                               mock_update_window):
    """
    NotifyWindows() General Checks (via Windows platform)

    """

    # Create our instance
    obj = apprise.Apprise.instantiate('windows://', suppress_exceptions=False)
    obj.duration = 0

    # Test URL functionality
    assert isinstance(obj.url(), str) is True

    # Check that it found our mocked environments
    assert obj.enabled is True

    # _on_destroy check
    obj._on_destroy(0, '', 0, 0)

    # test notifications
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'windows://_/?image=True', suppress_exceptions=False)
    obj.duration = 0
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'windows://_/?image=False', suppress_exceptions=False)
    obj.duration = 0
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True

    obj = apprise.Apprise.instantiate(
        'windows://_/?duration=1', suppress_exceptions=False)
    assert isinstance(obj.url(), str) is True
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True
    # loads okay
    assert obj.duration == 1

    obj = apprise.Apprise.instantiate(
        'windows://_/?duration=invalid', suppress_exceptions=False)
    # Falls back to default
    assert obj.duration == obj.default_popup_duration_sec

    obj = apprise.Apprise.instantiate(
        'windows://_/?duration=-1', suppress_exceptions=False)
    # Falls back to default
    assert obj.duration == obj.default_popup_duration_sec

    obj = apprise.Apprise.instantiate(
        'windows://_/?duration=0', suppress_exceptions=False)
    # Falls back to default
    assert obj.duration == obj.default_popup_duration_sec

    # To avoid slowdowns (for testing), turn it to zero for now
    obj = apprise.Apprise.instantiate('windows://', suppress_exceptions=False)
    obj.duration = 0

    # Test our loading of our icon exception; it will still allow the
    # notification to be sent
    mock_loadimage.side_effect = AttributeError
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is True
    # Undo our change
    mock_loadimage.side_effect = None

    # Test our global exception handling
    mock_update_window.side_effect = AttributeError
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False
    # Undo our change
    mock_update_window.side_effect = None

    # Toggle our testing for when we can't send notifications because the
    # package has been made unavailable to us
    obj.enabled = False
    assert obj.notify(
        title='title', body='body',
        notify_type=apprise.NotifyType.INFO) is False
