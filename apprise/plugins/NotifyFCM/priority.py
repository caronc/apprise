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

# New priorities are defined here:
# - https://firebase.google.com/docs/reference/fcm/rest/v1/\
#       projects.messages#NotificationPriority

# Legacy priorities are defined here:
# - https://firebase.google.com/docs/cloud-messaging/http-server-ref
from .common import (FCMMode, FCM_MODES)
from ...logger import logger


class NotificationPriority:
    """
    Defines the Notification Priorities as described on:
    https://firebase.google.com/docs/reference/fcm/rest/v1/\
            projects.messages#androidmessagepriority

        NORMAL:
            Default priority for data messages. Normal priority messages won't
            open network connections on a sleeping device, and their delivery
            may be delayed to conserve the battery. For less time-sensitive
            messages, such as notifications of new email or other data to sync,
            choose normal delivery priority.

        HIGH:
            Default priority for notification messages. FCM attempts to
            deliver high priority messages immediately, allowing the FCM
            service to wake a sleeping device when possible and open a network
            connection to your app server. Apps with instant messaging, chat,
            or voice call alerts, for example, generally need to open a
            network connection and make sure FCM delivers the message to the
            device without delay. Set high priority if the message is
            time-critical and requires the user's immediate interaction, but
            beware that setting your messages to high priority contributes
            more to battery drain compared with normal priority messages.
    """

    NORMAL = 'NORMAL'
    HIGH = 'HIGH'


class FCMPriority:
    """
    Defines our accepted priorites
    """
    MIN = "min"

    LOW = "low"

    NORMAL = "normal"

    HIGH = "high"

    MAX = "max"


FCM_PRIORITIES = (
    FCMPriority.MIN,
    FCMPriority.LOW,
    FCMPriority.NORMAL,
    FCMPriority.HIGH,
    FCMPriority.MAX,
)


class FCMPriorityManager:
    """
    A Simple object to make it easier to work with FCM set priorities
    """

    priority_map = {
        FCMPriority.MIN: {
            FCMMode.OAuth2: {
                'message': {
                    'android': {
                        'priority': NotificationPriority.NORMAL
                    },
                    'apns': {
                        'headers': {
                            'apns-priority': "5"
                        }
                    },
                    'webpush': {
                        'headers': {
                            'Urgency': 'very-low'
                        }
                    },
                }
            },
            FCMMode.Legacy: {
                'priority': 'normal',
            }
        },
        FCMPriority.LOW: {
            FCMMode.OAuth2: {
                'message': {
                    'android': {
                        'priority': NotificationPriority.NORMAL
                    },
                    'apns': {
                        'headers': {
                            'apns-priority': "5"
                        }
                    },
                    'webpush': {
                        'headers': {
                            'Urgency': 'low'
                        }
                    }
                }
            },
            FCMMode.Legacy: {
                'priority': 'normal',
            }
        },
        FCMPriority.NORMAL: {
            FCMMode.OAuth2: {
                'message': {
                    'android': {
                        'priority': NotificationPriority.NORMAL
                    },
                    'apns': {
                        'headers': {
                            'apns-priority': "5"
                        }
                    },
                    'webpush': {
                        'headers': {
                            'Urgency': 'normal'
                        }
                    }
                }
            },
            FCMMode.Legacy: {
                'priority': 'normal',
            }
        },
        FCMPriority.HIGH: {
            FCMMode.OAuth2: {
                'message': {
                    'android': {
                        'priority': NotificationPriority.HIGH
                    },
                    'apns': {
                        'headers': {
                            'apns-priority': "10"
                        }
                    },
                    'webpush': {
                        'headers': {
                            'Urgency': 'high'
                        }
                    }
                }
            },
            FCMMode.Legacy: {
                'priority': 'high',
            }
        },
        FCMPriority.MAX: {
            FCMMode.OAuth2: {
                'message': {
                    'android': {
                        'priority': NotificationPriority.HIGH
                    },
                    'apns': {
                        'headers': {
                            'apns-priority': "10"
                        }
                    },
                    'webpush': {
                        'headers': {
                            'Urgency': 'high'
                        }
                    }
                }
            },
            FCMMode.Legacy: {
                'priority': 'high',
            }
        }
    }

    def __init__(self, mode, priority=None):
        """
        Takes a FCMMode and Priority
        """

        self.mode = mode
        if self.mode not in FCM_MODES:
            msg = 'The FCM mode specified ({}) is invalid.'.format(mode)
            logger.warning(msg)
            raise TypeError(msg)

        self.priority = None
        if priority:
            self.priority = \
                next((p for p in FCM_PRIORITIES
                      if p.startswith(priority[:2].lower())), None)
            if not self.priority:
                msg = 'An invalid FCM Priority ' \
                      '({}) was specified.'.format(priority)
                logger.warning(msg)
                raise TypeError(msg)

    def payload(self):
        """
        Returns our payload depending on our mode
        """
        return self.priority_map[self.priority][self.mode] \
            if self.priority else {}

    def __str__(self):
        """
        our priority representation
        """
        return self.priority if self.priority else ''

    def __bool__(self):
        """
        Allows this object to be wrapped in an 'if statement'.
        True is returned if a priority was loaded
        """
        return True if self.priority else False
