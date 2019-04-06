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

# Default our global support flag
NOTIFY_GNOME_SUPPORT_ENABLED = False

try:
    # 3rd party modules (Gnome Only)
    import gi

    # require_version() call is required otherwise we generate a warning
    gi.require_version("Notify", "0.7")

    # We can import the actual libraries we care about now:
    from gi.repository import Notify
    from gi.repository import GdkPixbuf

    # We're good to go!
    NOTIFY_GNOME_SUPPORT_ENABLED = True

except (ImportError, ValueError):
    # No problem; we just simply can't support this plugin; we could
    # be in microsoft windows, or we just don't have the python-gobject
    # library available to us (or maybe one we don't support)?

    # Alternativey A ValueError will get thrown upon calling
    # gi.require_version() if the requested Notify namespace isn't available
    pass


# Urgencies
class GnomeUrgency(object):
    LOW = 0
    NORMAL = 1
    HIGH = 2


GNOME_URGENCIES = (
    GnomeUrgency.LOW,
    GnomeUrgency.NORMAL,
    GnomeUrgency.HIGH,
)


class NotifyGnome(NotifyBase):
    """
    A wrapper for local Gnome Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Gnome Notification'

    # The default protocol
    protocol = 'gnome'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_gnome'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for Gnome requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Limit results to just the first 10 line otherwise there is just to much
    # content to display
    body_max_line_count = 10

    # A title can not be used for Gnome Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # This entry is a bit hacky, but it allows us to unit-test this library
    # in an environment that simply doesn't have the gnome packages
    # available to us.  It also allows us to handle situations where the
    # packages actually are present but we need to test that they aren't.
    # If anyone is seeing this had knows a better way of testing this
    # outside of what is defined in test/test_gnome_plugin.py, please
    # let me know! :)
    _enabled = NOTIFY_GNOME_SUPPORT_ENABLED

    def __init__(self, urgency=None, include_image=True, **kwargs):
        """
        Initialize Gnome Object
        """

        super(NotifyGnome, self).__init__(**kwargs)

        # The urgency of the message
        if urgency not in GNOME_URGENCIES:
            self.urgency = GnomeUrgency.NORMAL

        else:
            self.urgency = urgency

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Gnome Notification
        """

        if not self._enabled:
            self.logger.warning(
                "Gnome Notifications are not supported by this system.")
            return False

        try:
            # App initialization
            Notify.init(self.app_id)

            # image path
            icon_path = None if not self.include_image \
                else self.image_path(notify_type, extension='.ico')

            # Build message body
            notification = Notify.Notification.new(body)

            # Assign urgency
            notification.set_urgency(self.urgency)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            if icon_path:
                try:
                    # Use Pixbuf to create the proper image type
                    image = GdkPixbuf.Pixbuf.new_from_file(icon_path)

                    # Associate our image to our notification
                    notification.set_icon_from_pixbuf(image)
                    notification.set_image_from_pixbuf(image)

                except Exception as e:
                    self.logger.warning(
                        "Could not load Gnome notification icon ({}): {}"
                        .format(icon_path, e))

            notification.show()
            self.logger.info('Sent Gnome notification.')

        except Exception:
            self.logger.warning('Failed to send Gnome notification.')
            self.logger.exception('Gnome Exception')
            return False

        return True

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        _map = {
            GnomeUrgency.LOW: 'low',
            GnomeUrgency.NORMAL: 'normal',
            GnomeUrgency.HIGH: 'high',
        }

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'image': 'yes' if self.include_image else 'no',
            'urgency': 'normal' if self.urgency not in _map
                       else _map[self.urgency],
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://_/?{args}'.format(
            schema=self.protocol,
            args=NotifyGnome.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        There are no parameters nessisary for this protocol; simply having
        gnome:// is all you need.  This function just makes sure that
        is in place.

        """

        results = NotifyBase.parse_url(url)
        if not results:
            results = {
                'schema': NotifyGnome.protocol,
                'user': None,
                'password': None,
                'port': None,
                'host': '_',
                'fullpath': None,
                'path': None,
                'url': url,
                'qsd': {},
            }

        # Include images with our message
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        # Gnome supports urgency, but we we also support the keyword priority
        # so that it is consistent with some of the other plugins
        urgency = results['qsd'].get('urgency', results['qsd'].get('priority'))
        if urgency and len(urgency):
            _map = {
                '0': GnomeUrgency.LOW,
                'l': GnomeUrgency.LOW,
                'n': GnomeUrgency.NORMAL,
                '1': GnomeUrgency.NORMAL,
                'h': GnomeUrgency.HIGH,
                '2': GnomeUrgency.HIGH,
            }

            try:
                # Attempt to index/retrieve our urgency
                results['urgency'] = _map[urgency[0].lower()]

            except KeyError:
                # No priority was set
                pass

        return results
