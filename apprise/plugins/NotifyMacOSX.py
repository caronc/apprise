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

from __future__ import absolute_import
from __future__ import print_function

import platform
import subprocess
import os

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..utils import parse_bool
from ..AppriseLocale import gettext_lazy as _

# Default our global support flag
NOTIFY_MACOSX_SUPPORT_ENABLED = False


# TODO: The module will be easier to test without module-level code.
if platform.system() == 'Darwin':
    # Check this is Mac OS X 10.8, or higher
    major, minor = platform.mac_ver()[0].split('.')[:2]

    # Toggle our enabled flag, if version is correct and executable
    # found. This is done in such a way to provide verbosity to the
    # end user, so they know why it may or may not work for them.
    NOTIFY_MACOSX_SUPPORT_ENABLED = \
        (int(major) > 10 or (int(major) == 10 and int(minor) >= 8))


class NotifyMacOSX(NotifyBase):
    """
    A wrapper for the MacOS X terminal-notifier tool

    Source: https://github.com/julienXX/terminal-notifier
    """

    # Set our global enabled flag
    enabled = NOTIFY_MACOSX_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        'details': _(
            'Only works with Mac OS X 10.8 and higher. Additionally '
            ' requires that /usr/local/bin/terminal-notifier is locally '
            'accessible.')
    }

    # The default descriptive name associated with the Notification
    service_name = _('MacOSX Notification')

    # The services URL
    service_url = 'https://github.com/julienXX/terminal-notifier'

    # The default protocol
    protocol = 'macosx'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_macosx'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for MacOSX requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Limit results to just the first 10 line otherwise there is just to much
    # content to display
    body_max_line_count = 10

    # The possible paths to the terminal-notifier
    notify_paths = (
        '/opt/homebrew/bin/terminal-notifier',
        '/usr/local/bin/terminal-notifier',
        '/usr/bin/terminal-notifier',
        '/bin/terminal-notifier',
    )

    # Define object templates
    templates = (
        '{schema}://',
    )

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
        # Play the NAME sound when the notification appears.
        # Sound names are listed in Sound Preferences.
        # Use 'default' for the default sound.
        'sound': {
            'name': _('Sound'),
            'type': 'string',
        },
        'click': {
            'name': _('Open/Click URL'),
            'type': 'string',
        },
    })

    def __init__(self, sound=None, include_image=True, click=None, **kwargs):
        """
        Initialize MacOSX Object
        """

        super().__init__(**kwargs)

        # Track whether we want to add an image to the notification.
        self.include_image = include_image

        # Acquire the path to the `terminal-notifier` program.
        self.notify_path = next(  # pragma: no branch
            (p for p in self.notify_paths if os.access(p, os.X_OK)), None)

        # Click URL
        # Allow user to provide the `--open` argument on the notify wrapper
        self.click = click

        # Set sound object (no q/a for now)
        self.sound = sound

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform MacOSX Notification
        """

        if not (self.notify_path and os.access(self.notify_path, os.X_OK)):
            self.logger.warning(
                "MacOSX Notifications requires one of the following to "
                "be in place: '{}'.".format(
                    '\', \''.join(self.notify_paths)))
            return False

        # Start with our notification path
        cmd = [
            self.notify_path,
            '-message', body,
        ]

        # Title is an optional switch
        if title:
            cmd.extend(['-title', title])

        if self.click:
            cmd.extend(['-open', self.click])

        # The sound to play
        if self.sound:
            cmd.extend(['-sound', self.sound])

        # Support any defined images if set
        image_path = None if not self.include_image \
            else self.image_url(notify_type)
        if image_path:
            cmd.extend(['-appIcon', image_path])

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Capture some output for helpful debugging later on
        self.logger.debug('MacOSX CMD: {}'.format(' '.join(cmd)))

        # Send our notification
        output = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Wait for process to complete
        output.wait()

        if output.returncode:
            self.logger.warning('Failed to send MacOSX notification.')
            self.logger.exception('MacOSX Exception')
            return False

        self.logger.info('Sent MacOSX notification.')
        return True

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parametrs
        params = {
            'image': 'yes' if self.include_image else 'no',
        }

        if self.click:
            params['click'] = self.click

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.sound:
            # Store our sound
            params['sound'] = self.sound

        return '{schema}://_/?{params}'.format(
            schema=self.protocol,
            params=NotifyMacOSX.urlencode(params),
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

        # Support 'click'
        if 'click' in results['qsd'] and len(results['qsd']['click']):
            results['click'] = NotifyMacOSX.unquote(results['qsd']['click'])

        # Support 'sound'
        if 'sound' in results['qsd'] and len(results['qsd']['sound']):
            results['sound'] = NotifyMacOSX.unquote(results['qsd']['sound'])

        return results
