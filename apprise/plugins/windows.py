# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

from time import sleep

from .base import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils.parse import parse_bool
from ..locale import gettext_lazy as _

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
    # either using Linux, or simply do not have pywin32 installed.
    pass


class NotifyWindows(NotifyBase):
    """
    A wrapper for local Windows Notifications
    """
    # Set our global enabled flag
    enabled = NOTIFY_WINDOWS_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        'details': _('A local Microsoft Windows environment is required.')
    }

    # The default descriptive name associated with the Notification
    service_name = 'Windows Notification'

    # The default protocol
    protocol = 'windows'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_windows'

    # Disable throttle rate for Windows requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Limit results to just the first 2 line otherwise there is just to much
    # content to display
    body_max_line_count = 2

    # The number of seconds to display the popup for
    default_popup_duration_sec = 12

    # No URL Identifier will be defined for this service as there simply isn't
    # enough details to uniquely identify one dbus:// from another.
    url_identifier = False

    # Define object templates
    templates = (
        '{schema}://',
    )

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'duration': {
            'name': _('Duration'),
            'type': 'int',
            'min': 1,
            'default': 12,
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
    })

    def __init__(self, include_image=True, duration=None, **kwargs):
        """
        Initialize Windows Object
        """

        super().__init__(**kwargs)

        # Number of seconds to display notification for
        self.duration = self.default_popup_duration_sec \
            if not (isinstance(duration, int) and duration > 0) else duration

        # Define our handler
        self.hwnd = None

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        """
        Destroy callback function
        """

        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32api.PostQuitMessage(0)

        return 0

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Windows Notification
        """

        # Always call throttle before any remote server i/o is made
        self.throttle()

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

            # image path (if configured to acquire)
            icon_path = None if not self.include_image \
                else self.image_path(notify_type, extension='.ico')

            if icon_path:
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
            else:
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
            self.logger.debug('Windows Exception: {}', str(e))
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
            'duration': str(self.duration),
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://?{params}'.format(
            schema=self.protocol,
            params=NotifyWindows.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        There are no parameters nessisary for this protocol; simply having
        windows:// is all you need.  This function just makes sure that
        is in place.

        """

        results = NotifyBase.parse_url(url, verify_host=False)

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        # Set duration
        try:
            results['duration'] = int(results['qsd'].get('duration'))

        except (TypeError, ValueError):
            # Not a valid integer; ignore entry
            pass

        # return results
        return results
