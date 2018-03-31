# -*- coding: utf-8 -*-
#
# Growl Notify Wrapper
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

import re

from .gntp import notifier
from .gntp import errors
from ..NotifyBase import NotifyBase
from ...common import NotifyImageSize


# Priorities
class GrowlPriority(object):
    LOW = -2
    MODERATE = -1
    NORMAL = 0
    HIGH = 1
    EMERGENCY = 2


GROWL_PRIORITIES = (
    GrowlPriority.LOW,
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
    protocol = 'growl'

    # Default Growl Port
    default_port = 23053

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    def __init__(self, priority=None, version=2, **kwargs):
        """
        Initialize Growl Object
        """
        super(NotifyGrowl, self).__init__(**kwargs)

        if not self.port:
            self.port = self.default_port

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
        self.growl = notifier.GrowlNotifier(**payload)

        try:
            self.growl.register()
            self.logger.debug(
                'Growl server registration completed successfully.'
            )

        except errors.NetworkError:
            self.logger.warning(
                'A network error occured sending Growl '
                'notification to %s.' % self.host)
            raise TypeError(
                'A network error occured sending Growl '
                'notification to %s.' % self.host)

        except errors.AuthError:
            self.logger.warning(
                'An authentication error occured sending Growl '
                'notification to %s.' % self.host)
            raise TypeError(
                'An authentication error occured sending Growl '
                'notification to %s.' % self.host)

        except errors.UnsupportedError:
            self.logger.warning(
                'An unsupported error occured sending Growl '
                'notification to %s.' % self.host)
            raise TypeError(
                'An unsupported error occured sending Growl '
                'notification to %s.' % self.host)

        return

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Growl Notification
        """

        # Limit results to just the first 2 line otherwise there is just to
        # much content to display
        body = re.split('[\r\n]+', body)
        body[0] = body[0].strip('#').strip()
        body = '\r\n'.join(body[0:2])

        icon = None
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

        # Update icon of payload to be raw data; this is intentionally done
        # here after we spit the debug message above (so we don't try to
        # print the binary contents of an image
        payload['icon'] = icon

        try:
            response = self.growl.notify(**payload)
            if not isinstance(response, bool):
                self.logger.warning(
                    'Growl notification failed to send with response: %s' %
                    str(response),
                )

            else:
                self.logger.info('Sent Growl notification.')

        except errors.BaseError as e:
            # Since Growl servers listen for UDP broadcasts, it's possible
            # that you will never get to this part of the code since there is
            # no acknowledgement as to whether it accepted what was sent to it
            # or not.

            # However, if the host/server is unavailable, you will get to this
            # point of the code.
            self.logger.warning(
                'A Connection error occured sending Growl '
                'notification to %s.' % self.host)
            self.logger.debug('Growl Exception: %s' % str(e))

            # Return; we're done
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Apply our settings now
        version = None
        if 'version' in results['qsd'] and len(results['qsd']['version']):
            # Allow the user to specify the version of the protocol to use.
            try:
                version = int(
                    NotifyBase.unquote(
                        results['qsd']['version']).strip().split('.')[0])

            except (AttributeError, IndexError, TypeError, ValueError):
                NotifyBase.logger.warning(
                    'An invalid Growl version of "%s" was specified and will '
                    'be ignored.' % results['qsd']['version']
                )
                pass

        if 'priority' in results['qsd'] and len(results['qsd']['priority']):
            _map = {
                'l': GrowlPriority.LOW,
                '-2': GrowlPriority.LOW,
                'm': GrowlPriority.MODERATE,
                '-1': GrowlPriority.MODERATE,
                'n': GrowlPriority.NORMAL,
                '0': GrowlPriority.NORMAL,
                'h': GrowlPriority.HIGH,
                '1': GrowlPriority.HIGH,
                'e': GrowlPriority.EMERGENCY,
                '2': GrowlPriority.EMERGENCY,
            }
            try:
                results['priority'] = \
                    _map[results['qsd']['priority'][0].lower()]

            except KeyError:
                # No priority was set
                pass

        # Because of the URL formatting, the password is actually where the
        # username field is. For this reason, we just preform this small hack
        # to make it (the URL) conform correctly. The following strips out the
        # existing password entry (if exists) so that it can be swapped with
        # the new one we specify.
        if results.get('password', None) is None:
            results['password'] = results.get('user', None)

        if version:
            results['version'] = version

        return results
