# -*- encoding: utf-8 -*-
#
# Growl Notify Wrapper
#
# Copyright (C) 2014-2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# apprise is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# apprise is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with apprise. If not, see <http://www.gnu.org/licenses/>.

from ..NotifyBase import NotifyBase
from ..NotifyBase import NotifyFormat
from ..NotifyBase import NotifyImageSize

from .gntp.notifier import GrowlNotifier
from .gntp.errors import NetworkError as GrowlNetworkError
from .gntp.errors import AuthError as GrowlAuthenticationError

# Default Growl Port
GROWL_UDP_PORT = 23053

# Image Support (72x72)
GROWL_IMAGE_XY = NotifyImageSize.XY_72


# Priorities
class GrowlPriority(object):
    VERY_LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


GROWL_PRIORITIES = (
    GrowlPriority.VERY_LOW,
    GrowlPriority.MODERATE,
    GrowlPriority.NORMAL,
    GrowlPriority.HIGH,
    GrowlPriority.EMERGENCY,
)

GROWL_NOTIFICATION_TYPE = "New Messages"


class NotifyGrowl(NotifyBase):
    """
    A wrapper to Growl Notifications

    """

    # The default protocol
    PROTOCOL = 'growl'

    # The default secure protocol
    SECURE_PROTOCOL = 'growl'

    def __init__(self, priority=GrowlPriority.NORMAL, version=2, **kwargs):
        """
        Initialize Growl Object
        """
        super(NotifyGrowl, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            image_size=GROWL_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

        # A Global flag that tracks registration
        self.is_registered = False

        if not self.port:
            self.port = GROWL_UDP_PORT

        # The Priority of the message
        if priority not in GROWL_PRIORITIES:
            self.priority = GrowlPriority.NORMAL
        else:
            self.priority = priority

        # Always default the sticky flag to False
        self.sticky = False

        # Store Version
        self.version = version

        payload = {
            'applicationName': self.app_id,
            'notifications': [GROWL_NOTIFICATION_TYPE, ],
            'defaultNotifications': [GROWL_NOTIFICATION_TYPE, ],
            'hostname': self.host,
            'port': self.port,
        }

        if self.password is not None:
            payload['password'] = self.password

        self.logger.debug('Growl Registration Payload: %s' % str(payload))
        self.growl = GrowlNotifier(**payload)

        try:
            self.growl.register()
            # Toggle our flag
            self.is_registered = True
            self.logger.debug(
                'Growl server registration completed successfully.'
            )

        except GrowlNetworkError:
            self.logger.warning(
                'A network error occured sending Growl '
                'notification to %s.' % self.host)
            return

        except GrowlAuthenticationError:
            self.logger.warning(
                'An authentication error occured sending Growl '
                'notification to %s.' % self.host)
            return

        return

    def _notify(self, title, body, notify_type, **kwargs):
        """
        Perform Growl Notification
        """

        if not self.is_registered:
            # We can't do anything
            return None

        icon = None
        if self.include_image:
            if self.version >= 2:
                # URL Based
                icon = self.image_url(notify_type)
            else:
                # Raw
                icon = self.image_raw(notify_type)

        payload = {
            'noteType': GROWL_NOTIFICATION_TYPE,
            'title': title,
            'description': body,
            'icon': icon is not None,
            'sticky': False,
            'priority': self.priority,
        }
        self.logger.debug('Growl Payload: %s' % str(payload))

        # Update icon of payload to be raw data
        payload['icon'] = icon

        try:
            response = self.growl.notify(**payload)
            if not isinstance(response, bool):
                self.logger.warning(
                    'Growl notification failed to send with response: %s' %
                    str(response),
                )

            else:
                self.logger.debug(
                    'Growl notification sent successfully.'
                )

        except GrowlNetworkError as e:
            # Since Growl servers listen for UDP broadcasts,
            # it's possible that you will never get to this part
            # of the code since there is no acknowledgement as to
            # whether it accepted what was sent to it or not.

            # however, if the host/server is unavailable, you will
            # get to this point of the code.
            self.logger.warning(
                'A Connection error occured sending Growl '
                'notification to %s.' % self.host)
            self.logger.debug('Growl Exception: %s' % str(e))

            # Return; we're done
            return False

        return True
