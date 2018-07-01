# -*- coding: utf-8 -*-
#
# NotifyWindows - Unit Tests
#
# Copyright (C) 2018 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

import mock
import sys
import types

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


def test_windows_plugin():
    """
    API: NotifyWindows Plugin()

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
            del(sys.modules[mod])
    reload(apprise)

    # Create our instance
    obj = apprise.Apprise.instantiate('windows://', suppress_exceptions=False)
    obj.duration = 0

    # Check that it found our mocked environments
    assert(obj._enabled is True)

    # _on_destroy check
    obj._on_destroy(0, '', 0, 0)

    # test notifications
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)

    # Test our loading of our icon exception; it will still allow the
    # notification to be sent
    win32gui.LoadImage.side_effect = AttributeError
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is True)
    # Undo our change
    win32gui.LoadImage.side_effect = None

    # Test our global exception handling
    win32gui.UpdateWindow.side_effect = AttributeError
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is False)
    # Undo our change
    win32gui.UpdateWindow.side_effect = None

    # Toggle our testing for when we can't send notifications because the
    # package has been made unavailable to us
    obj._enabled = False
    assert(obj.notify(title='title', body='body',
           notify_type=apprise.NotifyType.INFO) is False)
