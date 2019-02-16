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

from __future__ import absolute_import
from __future__ import print_function

import re

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..utils import GET_SCHEMA_RE

# Default our global support flag
NOTIFY_DBUS_SUPPORT_ENABLED = False

# Image support is dependant on the GdkPixbuf library being available
NOTIFY_DBUS_IMAGE_SUPPORT = False

# The following are required to hook into the notifications:
NOTIFY_DBUS_INTERFACE = 'org.freedesktop.Notifications'
NOTIFY_DBUS_SETTING_LOCATION = '/org/freedesktop/Notifications'

# Initialize our mainloops
LOOP_GLIB = None
LOOP_QT = None


try:
    # dbus essentials
    from dbus import SessionBus
    from dbus import Interface
    from dbus import Byte
    from dbus import ByteArray

    #
    # now we try to determine which mainloop(s) we can access
    #

    # glib
    try:
        from dbus.mainloop.glib import DBusGMainLoop
        LOOP_GLIB = DBusGMainLoop()

    except ImportError:
        # No problem
        pass

    # qt
    try:
        from dbus.mainloop.qt import DBusQtMainLoop
        LOOP_QT = DBusQtMainLoop(set_as_default=True)

    except ImportError:
        # No problem
        pass

    # We're good as long as at least one
    NOTIFY_DBUS_SUPPORT_ENABLED = (
        LOOP_GLIB is not None or LOOP_QT is not None)

    try:
        # The following is required for Image/Icon loading only
        import gi
        gi.require_version('GdkPixbuf', '2.0')
        from gi.repository import GdkPixbuf
        NOTIFY_DBUS_IMAGE_SUPPORT = True

    except ImportError:
        # No problem; this will get caught in outer try/catch
        raise

except ImportError:
    # No problem; we just simply can't support this plugin; we could
    # be in microsoft windows, or we just don't have the python-gobject
    # library available to us (or maybe one we don't support)?
    pass

# Define our supported protocols and the loop to assign them.
# The key to value pairs are the actual supported schema's matched
# up with the Main Loop they should reference when accessed.
MAINLOOP_MAP = {
    'qt': LOOP_QT,
    'kde': LOOP_QT,
    'glib': LOOP_GLIB,
    'dbus': LOOP_QT if LOOP_QT else LOOP_GLIB,
}


# Urgencies
class DBusUrgency(object):
    LOW = 0
    NORMAL = 1
    HIGH = 2


# Define our urgency levels
DBUS_URGENCIES = (
    DBusUrgency.LOW,
    DBusUrgency.NORMAL,
    DBusUrgency.HIGH,
)


class NotifyDBus(NotifyBase):
    """
    A wrapper for local DBus/Qt Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'DBus Notification'

    # The default protocols
    # Python 3 keys() does not return a list object, it's it's own dict_keys()
    # object if we were to reference, we wouldn't be backwards compatible with
    # Python v2.  So converting the result set back into a list makes us
    # compatible

    protocol = list(MAINLOOP_MAP.keys())

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_dbus'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # The number of seconds to keep the message present for
    message_timeout_ms = 13000

    # Limit results to just the first 10 line otherwise there is just to much
    # content to display
    body_max_line_count = 10

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # This entry is a bit hacky, but it allows us to unit-test this library
    # in an environment that simply doesn't have the gnome packages
    # available to us.  It also allows us to handle situations where the
    # packages actually are present but we need to test that they aren't.
    # If anyone is seeing this had knows a better way of testing this
    # outside of what is defined in test/test_glib_plugin.py, please
    # let me know! :)
    _enabled = NOTIFY_DBUS_SUPPORT_ENABLED

    def __init__(self, urgency=None, x_axis=None, y_axis=None, **kwargs):
        """
        Initialize DBus Object
        """

        super(NotifyDBus, self).__init__(**kwargs)

        # Track our notifications
        self.registry = {}

        # Store our schema; default to dbus
        self.schema = kwargs.get('schema', 'dbus')

        if self.schema not in MAINLOOP_MAP:
            # Unsupported Schema
            self.logger.warning(
                'The schema specified ({}) is not supported.'
                .format(self.schema))
            raise TypeError(
                'The schema specified ({}) is not supported.'
                .format(self.schema))

        # The urgency of the message
        if urgency not in DBUS_URGENCIES:
            self.urgency = DBusUrgency.NORMAL

        else:
            self.urgency = urgency

        # Our x/y axis settings
        self.x_axis = x_axis
        self.y_axis = y_axis

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform DBus Notification
        """

        if not self._enabled or MAINLOOP_MAP[self.schema] is None:
            self.logger.warning(
                "{} notifications could not be loaded.".format(self.schema))
            return False

        # Acquire our session
        session = SessionBus(mainloop=MAINLOOP_MAP[self.schema])

        # acquire our dbus object
        dbus_obj = session.get_object(
            NOTIFY_DBUS_INTERFACE,
            NOTIFY_DBUS_SETTING_LOCATION,
        )

        # Acquire our dbus interface
        dbus_iface = Interface(
            dbus_obj,
            dbus_interface=NOTIFY_DBUS_INTERFACE,
        )

        # image path
        icon_path = self.image_path(notify_type, extension='.ico')

        # Our meta payload
        meta_payload = {
            "urgency": Byte(self.urgency)
        }

        if not (self.x_axis is None and self.y_axis is None):
            # Set x/y access if these were set
            meta_payload['x'] = self.x_axis
            meta_payload['y'] = self.y_axis

        if NOTIFY_DBUS_IMAGE_SUPPORT is True:
            try:
                # Use Pixbuf to create the proper image type
                image = GdkPixbuf.Pixbuf.new_from_file(icon_path)

                # Associate our image to our notification
                meta_payload['icon_data'] = (
                    image.get_width(),
                    image.get_height(),
                    image.get_rowstride(),
                    image.get_has_alpha(),
                    image.get_bits_per_sample(),
                    image.get_n_channels(),
                    ByteArray(image.get_pixels())
                )

            except Exception as e:
                self.logger.warning(
                    "Could not load Gnome notification icon ({}): {}"
                    .format(icon_path, e))

        try:
            dbus_iface.Notify(
                # Application Identifier
                self.app_id,
                # Message ID (0 = New Message)
                0,
                # Icon (str) - not used
                '',
                # Title
                str(title),
                # Body
                str(body),
                # Actions
                list(),
                # Meta
                meta_payload,
                # Message Timeout
                self.message_timeout_ms,
            )

            self.logger.info('Sent DBus notification.')

        except Exception as e:
            self.logger.warning('Failed to send DBus notification.')
            self.logger.exception('DBus Exception')
            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        return '{schema}://'.format(schema=self.schema)

    @staticmethod
    def parse_url(url):
        """
        There are no parameters nessisary for this protocol; simply having
        gnome:// is all you need.  This function just makes sure that
        is in place.

        """
        schema = GET_SCHEMA_RE.match(url)
        if schema is None:
            # Content is simply not parseable
            return None

        # return a very basic set of requirements
        return {
            'schema': schema.group('schema').lower(),
            'user': None,
            'password': None,
            'port': None,
            'host': 'localhost',
            'fullpath': None,
            'path': None,
            'url': url,
            'qsd': {},
            # screen lat/lon (in pixels) where x=0 and y=0 if you want to put
            # the notification in the top left hand side. Accept defaults if
            # set to None
            'x_axis': None,
            'y_axis': None,
            # Set the urgency to None so that we fall back to the default
            # value.
            'urgency': None,
        }
