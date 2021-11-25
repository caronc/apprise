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

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _

# Default our global support flag
NOTIFY_DBUS_SUPPORT_ENABLED = False

# Image support is dependant on the GdkPixbuf library being available
NOTIFY_DBUS_IMAGE_SUPPORT = False

# Initialize our mainloops
LOOP_GLIB = None
LOOP_QT = None


try:
    # dbus essentials
    from dbus import SessionBus
    from dbus import Interface
    from dbus import Byte
    from dbus import ByteArray
    from dbus import DBusException

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

    except (ImportError, ValueError, AttributeError):
        # No problem; this will get caught in outer try/catch

        # A ValueError will get thrown upon calling gi.require_version() if
        # GDK/GTK isn't installed on the system but gi is.
        pass

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

    # Set our global enabled flag
    enabled = NOTIFY_DBUS_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        'details': _('libdbus-1.so.x must be installed.')
    }

    # The default descriptive name associated with the Notification
    service_name = _('DBus Notification')

    # The services URL
    service_url = 'http://www.freedesktop.org/Software/dbus/'

    # The default protocols
    # Python 3 keys() does not return a list object, it's it's own dict_keys()
    # object if we were to reference, we wouldn't be backwards compatible with
    # Python v2.  So converting the result set back into a list makes us
    # compatible
    protocol = list(MAINLOOP_MAP.keys())

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_dbus'

    # No throttling required for DBus queries
    request_rate_per_sec = 0

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # The number of milliseconds to keep the message present for
    message_timeout_ms = 13000

    # Limit results to just the first 10 line otherwise there is just to much
    # content to display
    body_max_line_count = 10

    # The following are required to hook into the notifications:
    dbus_interface = 'org.freedesktop.Notifications'
    dbus_setting_location = '/org/freedesktop/Notifications'

    # Define object templates
    templates = (
        '{schema}://',
    )

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'urgency': {
            'name': _('Urgency'),
            'type': 'choice:int',
            'values': DBUS_URGENCIES,
            'default': DBusUrgency.NORMAL,
        },
        'x': {
            'name': _('X-Axis'),
            'type': 'int',
            'min': 0,
            'map_to': 'x_axis',
        },
        'y': {
            'name': _('Y-Axis'),
            'type': 'int',
            'min': 0,
            'map_to': 'y_axis',
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
    })

    def __init__(self, urgency=None, x_axis=None, y_axis=None,
                 include_image=True, **kwargs):
        """
        Initialize DBus Object
        """

        super(NotifyDBus, self).__init__(**kwargs)

        # Track our notifications
        self.registry = {}

        # Store our schema; default to dbus
        self.schema = kwargs.get('schema', 'dbus')

        if self.schema not in MAINLOOP_MAP:
            msg = 'The schema specified ({}) is not supported.' \
                .format(self.schema)
            self.logger.warning(msg)
            raise TypeError(msg)

        # The urgency of the message
        if urgency not in DBUS_URGENCIES:
            self.urgency = DBusUrgency.NORMAL

        else:
            self.urgency = urgency

        # Our x/y axis settings
        self.x_axis = x_axis if isinstance(x_axis, int) else None
        self.y_axis = y_axis if isinstance(y_axis, int) else None

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform DBus Notification
        """
        # Acquire our session
        try:
            session = SessionBus(mainloop=MAINLOOP_MAP[self.schema])

        except DBusException:
            # Handle exception
            self.logger.warning('Failed to send DBus notification.')
            self.logger.exception('DBus Exception')
            return False

        # If there is no title, but there is a body, swap the two to get rid
        # of the weird whitespace
        if not title:
            title = body
            body = ''

        # acquire our dbus object
        dbus_obj = session.get_object(
            self.dbus_interface,
            self.dbus_setting_location,
        )

        # Acquire our dbus interface
        dbus_iface = Interface(
            dbus_obj,
            dbus_interface=self.dbus_interface,
        )

        # image path
        icon_path = None if not self.include_image \
            else self.image_path(notify_type, extension='.ico')

        # Our meta payload
        meta_payload = {
            "urgency": Byte(self.urgency)
        }

        if not (self.x_axis is None and self.y_axis is None):
            # Set x/y access if these were set
            meta_payload['x'] = self.x_axis
            meta_payload['y'] = self.y_axis

        if NOTIFY_DBUS_IMAGE_SUPPORT and icon_path:
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
            # Always call throttle() before any remote execution is made
            self.throttle()

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

        except Exception:
            self.logger.warning('Failed to send DBus notification.')
            self.logger.exception('DBus Exception')
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        _map = {
            DBusUrgency.LOW: 'low',
            DBusUrgency.NORMAL: 'normal',
            DBusUrgency.HIGH: 'high',
        }

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
            'urgency': 'normal' if self.urgency not in _map
                       else _map[self.urgency],
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # x in (x,y) screen coordinates
        if self.x_axis:
            params['x'] = str(self.x_axis)

        # y in (x,y) screen coordinates
        if self.y_axis:
            params['y'] = str(self.y_axis)

        return '{schema}://_/?{params}'.format(
            schema=self.schema,
            params=NotifyDBus.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        There are no parameters nessisary for this protocol; simply having
        gnome:// is all you need.  This function just makes sure that
        is in place.

        """

        results = NotifyBase.parse_url(url, verify_host=False)

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        # DBus supports urgency, but we we also support the keyword priority
        # so that it is consistent with some of the other plugins
        urgency = results['qsd'].get('urgency', results['qsd'].get('priority'))
        if urgency and len(urgency):
            _map = {
                '0': DBusUrgency.LOW,
                'l': DBusUrgency.LOW,
                'n': DBusUrgency.NORMAL,
                '1': DBusUrgency.NORMAL,
                'h': DBusUrgency.HIGH,
                '2': DBusUrgency.HIGH,
            }

            try:
                # Attempt to index/retrieve our urgency
                results['urgency'] = _map[urgency[0].lower()]

            except KeyError:
                # No priority was set
                pass

        # handle x,y coordinates
        try:
            results['x_axis'] = int(results['qsd'].get('x'))

        except (TypeError, ValueError):
            # No x was set
            pass

        try:
            results['y_axis'] = int(results['qsd'].get('y'))

        except (TypeError, ValueError):
            # No y was set
            pass

        return results
