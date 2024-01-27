# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _

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

except (ImportError, ValueError, AttributeError):
    # No problem; we just simply can't support this plugin; we could
    # be in microsoft windows, or we just don't have the python-gobject
    # library available to us (or maybe one we don't support)?

    # Alternatively, a `ValueError` will get raised upon calling
    # gi.require_version() if the requested Notify namespace isn't available.
    pass


# Urgencies
class GnomeUrgency:
    LOW = 0
    NORMAL = 1
    HIGH = 2


GNOME_URGENCIES = {
    GnomeUrgency.LOW: 'low',
    GnomeUrgency.NORMAL: 'normal',
    GnomeUrgency.HIGH: 'high',
}


GNOME_URGENCY_MAP = {
    # Maps against string 'low'
    'l': GnomeUrgency.LOW,
    # Maps against string 'moderate'
    'm': GnomeUrgency.LOW,
    # Maps against string 'normal'
    'n': GnomeUrgency.NORMAL,
    # Maps against string 'high'
    'h': GnomeUrgency.HIGH,
    # Maps against string 'emergency'
    'e': GnomeUrgency.HIGH,

    # Entries to additionally support (so more like Gnome's API)
    '0': GnomeUrgency.LOW,
    '1': GnomeUrgency.NORMAL,
    '2': GnomeUrgency.HIGH,
}


class NotifyGnome(NotifyBase):
    """
    A wrapper for local Gnome Notifications
    """

    # Set our global enabled flag
    enabled = NOTIFY_GNOME_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        'details': _('A local Gnome environment is required.')
    }

    # The default descriptive name associated with the Notification
    service_name = _('Gnome Notification')

    # The service URL
    service_url = 'https://www.gnome.org/'

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

    # Define object templates
    templates = (
        '{schema}://',
    )

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'urgency': {
            'name': _('Urgency'),
            'type': 'choice:int',
            'values': GNOME_URGENCIES,
            'default': GnomeUrgency.NORMAL,
        },
        'priority': {
            # Apprise uses 'priority' everywhere; it's just a nice consistent
            # feel to be able to use it here as well. Just map the
            # value back to 'priority'
            'alias_of': 'urgency',
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
    })

    def __init__(self, urgency=None, include_image=True, **kwargs):
        """
        Initialize Gnome Object
        """

        super().__init__(**kwargs)

        # The urgency of the message
        self.urgency = int(
            NotifyGnome.template_args['urgency']['default']
            if urgency is None else
            next((
                v for k, v in GNOME_URGENCY_MAP.items()
                if str(urgency).lower().startswith(k)),
                NotifyGnome.template_args['urgency']['default']))

        # Track whether we want to add an image to the notification.
        self.include_image = include_image

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Gnome Notification
        """

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
                        "Could not load notification icon (%s).", icon_path)
                    self.logger.debug(f'Gnome Exception: {e}')

            notification.show()
            self.logger.info('Sent Gnome notification.')

        except Exception as e:
            self.logger.warning('Failed to send Gnome notification.')
            self.logger.debug(f'Gnome Exception: {e}')
            return False

        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
            'urgency':
                GNOME_URGENCIES[self.template_args['urgency']['default']]
                if self.urgency not in GNOME_URGENCIES
                else GNOME_URGENCIES[self.urgency],
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return '{schema}://?{params}'.format(
            schema=self.protocol,
            params=NotifyGnome.urlencode(params),
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

        # Gnome supports urgency, but we we also support the keyword priority
        # so that it is consistent with some of the other plugins
        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            # We intentionally store the priority in the urgency section
            results['urgency'] = \
                NotifyGnome.unquote(results['qsd']['priority'])

        if 'urgency' in results['qsd'] and len(results['qsd']['urgency']):
            results['urgency'] = \
                NotifyGnome.unquote(results['qsd']['urgency'])

        return results
