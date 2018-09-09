# -*- coding: utf-8 -*-
#
# Windows Notify Wrapper
#
# Copyright (C) 2017-2018 Chris Caron <lead2gold@gmail.com>
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
from __future__ import absolute_import
from __future__ import print_function

import re
from time import sleep

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize

# Default our global support flag
NOTIFY_WINDOWS_SUPPORT_ENABLED = False

try:
    # 3rd party modules (Windows Only)
    import win32api
    import win32con
    import win32gui

    # We're good to go!
    NOTIFY_WINDOWS_SUPPORT_ENABLED = True

except ImportError:
    # No problem; we just simply can't support this plugin because we're
    # either using Linux, or simply do not have pypiwin32 installed.
    pass


class NotifyWindows(NotifyBase):
    """
    A wrapper for local Windows Notifications
    """

    # The default protocol
    protocol = 'windows'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # This entry is a bit hacky, but it allows us to unit-test this library
    # in an environment that simply doesn't have the windows packages
    # available to us.  It also allows us to handle situations where the
    # packages actually are present but we need to test that they aren't.
    # If anyone is seeing this had knows a better way of testing this
    # outside of what is defined in test/test_windows_plugin.py, please
    # let me know! :)
    _enabled = NOTIFY_WINDOWS_SUPPORT_ENABLED

    def __init__(self, **kwargs):
        """
        Initialize Windows Object
        """

        # Number of seconds to display notification for
        self.duration = 12

        # Define our handler
        self.hwnd = None

        super(NotifyWindows, self).__init__(**kwargs)

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        """
        Destroy callback function
        """

        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32api.PostQuitMessage(0)

        return None

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Windows Notification
        """

        if not self._enabled:
            self.logger.warning(
                "Windows Notifications are not supported by this system.")
            return False

        # Limit results to just the first 2 line otherwise
        # there is just to much content to display
        body = re.split('[\r\n]+', body)
        body[0] = body[0].strip('#').strip()
        body = '\r\n'.join(body[0:2])

        try:
            # Register destruction callback
            message_map = {win32con.WM_DESTROY: self._on_destroy, }

            # Register the window class.
            self.wc = win32gui.WNDCLASS()
            self.hinst = self.wc.hInstance = win32api.GetModuleHandle(None)
            self.wc.lpszClassName = str("PythonTaskbar")
            self.wc.lpfnWndProc = message_map
            self.classAtom = win32gui.RegisterClass(self.wc)

            # Styling and window type
            style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
            self.hwnd = win32gui.CreateWindow(
                self.classAtom, "Taskbar", style, 0, 0,
                win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT, 0, 0,
                self.hinst, None)
            win32gui.UpdateWindow(self.hwnd)

            # image path
            icon_path = self.image_path(notify_type, extension='.ico')
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE

            try:
                hicon = win32gui.LoadImage(
                    self.hinst, icon_path, win32con.IMAGE_ICON, 0, 0,
                    icon_flags)

            except Exception as e:
                self.logger.warning(
                    "Could not load windows notification icon ({}): {}"
                    .format(icon_path, e))

                # disable icon
                hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

            # Taskbar icon
            flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
            nid = (self.hwnd, 0, flags, win32con.WM_USER + 20, hicon,
                   "Tooltip")
            win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, nid)
            win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, (
                self.hwnd, 0, win32gui.NIF_INFO, win32con.WM_USER + 20, hicon,
                "Balloon Tooltip", body, 200, title))

            # take a rest then destroy
            sleep(self.duration)
            win32gui.DestroyWindow(self.hwnd)
            win32gui.UnregisterClass(self.wc.lpszClassName, None)

            self.logger.info('Sent Windows notification.')

        except Exception as e:
            self.logger.warning('Failed to send Windows notification.')
            self.logger.exception('Windows Exception')
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        There are no parameters nessisary for this protocol; simply having
        windows:// is all you need.  This function just makes sure that
        is in place.

        """

        # return a very basic set of requirements
        return {
            'schema': NotifyWindows.protocol,
            'user': None,
            'password': None,
            'port': None,
            'host': 'localhost',
            'fullpath': None,
            'path': None,
            'url': url,
            'qsd': {},
        }
