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

import sys

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool
from .base import NotifyBase

# Default our global support flag
NOTIFY_GLIB_SUPPORT_ENABLED = False

# Image support is dependant on the GdkPixbuf library being available
NOTIFY_GLIB_IMAGE_SUPPORT = False


try:
    # glib essentials
    import gi
    gi.require_version("Gio", "2.0")
    gi.require_version("GLib", "2.0")
    from gi.repository import Gio, GLib

    # We're good
    NOTIFY_GLIB_SUPPORT_ENABLED = True

    # ImportError: When using gi.repository you must not import static modules
    # like "gobject". Please change all occurrences of "import gobject" to
    # "from gi.repository import GObject".
    # See: https://bugzilla.gnome.org/show_bug.cgi?id=709183
    if "gobject" in sys.modules:  # pragma: no cover
        del sys.modules["gobject"]

    try:
        # The following is required for Image/Icon loading only
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        NOTIFY_GLIB_IMAGE_SUPPORT = True

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


# Urgencies
class GLibUrgency:
    LOW = 0
    NORMAL = 1
    HIGH = 2


GLIB_URGENCIES = {
    # Note: This also acts as a reverse lookup mapping
    GLibUrgency.LOW: "low",
    GLibUrgency.NORMAL: "normal",
    GLibUrgency.HIGH: "high",
}

GLIB_URGENCY_MAP = {
    # Maps against string 'low'
    "l": GLibUrgency.LOW,
    # Maps against string 'moderate'
    "m": GLibUrgency.LOW,
    # Maps against string 'normal'
    "n": GLibUrgency.NORMAL,
    # Maps against string 'high'
    "h": GLibUrgency.HIGH,
    # Maps against string 'emergency'
    "e": GLibUrgency.HIGH,

    # Entries to additionally support (so more like DBus's API)
    "0": GLibUrgency.LOW,
    "1": GLibUrgency.NORMAL,
    "2": GLibUrgency.HIGH,
}


class NotifyGLib(NotifyBase):
    """
    A wrapper for local GLib/Gio Notifications
    """

    # Set our global enabled flag
    enabled = NOTIFY_GLIB_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        "details": _("libdbus-1.so.x or libdbus-2.so.x must be installed.")
    }

    # The default descriptive name associated with the Notification
    service_name = _("DBus Notification")

    # The services URL
    service_url = \
        "https://lazka.github.io/pgi-docs/Gio-2.0/classes/DBusProxy.html"

    # The default protocols
    protocol = ("glib", "gio")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_glib"

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
    glib_interface = "org.freedesktop.Notifications"
    glib_setting_location = "/org/freedesktop/Notifications"

    # Define object templates
    templates = (
        "{schema}://",
    )

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        "urgency": {
            "name": _("Urgency"),
            "type": "choice:int",
            "values": GLIB_URGENCIES,
            "default": GLibUrgency.NORMAL,
        },
        "priority": {
            # Apprise uses 'priority' everywhere; it's just a nice consistent
            # feel to be able to use it here as well. Just map the
            # value back to 'priority'
            "alias_of": "urgency",
        },
        "x": {
            "name": _("X-Axis"),
            "type": "int",
            "min": 0,
            "map_to": "x_axis",
        },
        "y": {
            "name": _("Y-Axis"),
            "type": "int",
            "min": 0,
            "map_to": "y_axis",
        },
        "image": {
            "name": _("Include Image"),
            "type": "bool",
            "default": True,
            "map_to": "include_image",
        },
    })

    def __init__(self, urgency=None, x_axis=None, y_axis=None,
                 include_image=True, **kwargs):
        """
        Initialize DBus Object
        """

        super().__init__(**kwargs)

        # Track our notifications
        self.registry = {}

        # The urgency of the message
        self.urgency = int(
            NotifyGLib.template_args["urgency"]["default"]
            if urgency is None else
            next((
                v for k, v in GLIB_URGENCY_MAP.items()
                if str(urgency).lower().startswith(k)),
                NotifyGLib.template_args["urgency"]["default"]))

        # Our x/y axis settings
        if x_axis or y_axis:
            try:
                self.x_axis = int(x_axis)
                self.y_axis = int(y_axis)

            except (TypeError, ValueError):
                # Invalid x/y values specified
                msg = "The x,y coordinates specified ({},{}) are invalid."\
                    .format(x_axis, y_axis)
                self.logger.warning(msg)
                raise TypeError(msg) from None
        else:
            self.x_axis = None
            self.y_axis = None

        # Track whether we want to add an image to the notification.
        self.include_image = include_image

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """
        Perform GLib/Gio Notification
        """
        # Acquire our gio interface
        try:
            gio_iface = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                self.glib_interface,
                self.glib_setting_location,
                self.glib_interface,
                None,
            )

        except GLib.Error as e:
            # Handle exception
            self.logger.warning("Failed to send GLib/Gio notification.")
            self.logger.debug(f"GLib/Gio Exception: {e}")
            return False

        # If there is no title, but there is a body, swap the two to get rid
        # of the weird whitespace
        if not title:
            title = body
            body = ""

        # image path
        icon_path = None if not self.include_image \
            else self.image_path(notify_type, extension=".ico")

        # Our meta payload
        meta_payload = {
            "urgency": GLib.Variant("y", self.urgency),
        }

        if not (self.x_axis is None and self.y_axis is None):
            # Set x/y access if these were set
            meta_payload["x"] = GLib.Variant("i", self.x_axis)
            meta_payload["y"] = GLib.Variant("i", self.y_axis)

        if NOTIFY_GLIB_IMAGE_SUPPORT and icon_path:
            try:
                # Use Pixbuf to create the proper image type
                image = GdkPixbuf.Pixbuf.new_from_file(icon_path)

                # Associate our image to our notification
                meta_payload["icon_data"] = GLib.Variant(
                    "(iiibiiay)",
                    (
                        image.get_width(),
                        image.get_height(),
                        image.get_rowstride(),
                        image.get_has_alpha(),
                        image.get_bits_per_sample(),
                        image.get_n_channels(),
                        image.get_pixels(),
                    ),
                )

            except Exception as e:
                self.logger.warning(
                    "Could not load notification icon (%s).", icon_path)
                self.logger.debug(f"GLib/Gio Exception: {e}")

        try:
            # Always call throttle() before any remote execution is made
            self.throttle()

            gio_iface.Notify(
                "(susssasa{sv}i)",
                # Application Identifier
                self.app_id,
                # Message ID (0 = New Message)
                0,
                # Icon (str) - not used
                "",
                # Title
                str(title),
                # Body
                str(body),
                # Actions
                [],
                # Meta
                meta_payload,
                # Message Timeout
                self.message_timeout_ms,
            )

            self.logger.info("Sent GLib/Gio notification.")

        except Exception as e:
            self.logger.warning("Failed to send GLib/Gio notification.")
            self.logger.debug(f"GLib/Gio Exception: {e}")
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
            "urgency":
                GLIB_URGENCIES[self.template_args["urgency"]["default"]]
                if self.urgency not in GLIB_URGENCIES
                else GLIB_URGENCIES[self.urgency],
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # x in (x,y) screen coordinates
        if self.x_axis:
            params["x"] = str(self.x_axis)

        # y in (x,y) screen coordinates
        if self.y_axis:
            params["y"] = str(self.y_axis)

        schema = self.protocol[0]
        return f"{schema}://_/?{NotifyGLib.urlencode(params)}"

    @staticmethod
    def parse_url(url):
        """
        There are no parameters necessary for this protocol; simply having
        gnome:// is all you need.  This function just makes sure that
        is in place.

        """

        results = NotifyBase.parse_url(url, verify_host=False)

        # Include images with our message
        results["include_image"] = \
            parse_bool(results["qsd"].get("image", True))

        # GLib/Gio supports urgency, but we we also support the keyword
        # priority so that it is consistent with some of the other plugins
        if "priority" in results["qsd"] and len(results["qsd"]["priority"]):
            # We intentionally store the priority in the urgency section
            results["urgency"] = \
                NotifyGLib.unquote(results["qsd"]["priority"])

        if "urgency" in results["qsd"] and len(results["qsd"]["urgency"]):
            results["urgency"] = \
                NotifyGLib.unquote(results["qsd"]["urgency"])

        # handle x,y coordinates
        if "x" in results["qsd"] and len(results["qsd"]["x"]):
            results["x_axis"] = NotifyGLib.unquote(results["qsd"].get("x"))

        if "y" in results["qsd"] and len(results["qsd"]["y"]):
            results["y_axis"] = NotifyGLib.unquote(results["qsd"].get("y"))

        return results
