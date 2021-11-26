# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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

# New priorities are defined here:
# - https://firebase.google.com/docs/reference/fcm/rest/v1/\
#       projects.messages#NotificationPriority

# Legacy priorities are defined here:
# - https://firebase.google.com/docs/cloud-messaging/http-server-ref
from .common import (FCMMode, FCM_MODES)
from ...logger import logger


class NotificationPriority(object):
    """
    Defines the Notification Priorities as described on:
    https://firebase.google.com/docs/reference/fcm/rest/v1/\
            projects.messages#notificationpriority

        0 - PRIORITY_UNSPECIFIED:
            If priority is unspecified, notification priority is set to
            PRIORITY_DEFAULT. <- not used here

        1 - PRIORITY_MIN:
            Lowest notification priority. Notifications with this PRIORITY_MIN
            might not be shown to the user except under special circumstances,
            such as detailed notification logs.

        2 - PRIORITY_LOW:
            Lower notification priority. The UI may choose to show the
            notifications smaller, or at a different position in the list,
            compared with notifications with PRIORITY_DEFAULT.

        3 - PRIORITY_DEFAULT:
            Default notification priority. If the application does not
            prioritize its own notifications, use this value for all
            notifications.

        4 - PRIORITY_HIGH:
            Higher notification priority. Use this for more important
            notifications or alerts. The UI may choose to show these
            notifications larger, or at a different position in the
            notification lists, compared with notifications with
            PRIORITY_DEFAULT.

        5 - PRIORITY_MAX:
            Highest notification priority. Use this for the application's most
            important items that require the user's prompt attention or input.
    """

    PRIORITY_MIN = 'PRIORITY_MIN'
    PRIORITY_LOW = 'PRIORITY_LOW'
    PRIORITY_DEFAULT = 'PRIORITY_DEFAULT'
    PRIORITY_HIGH = 'PRIORITY_HIGH'
    PRIORITY_MAX = 'PRIORITY_MAX'


class FCMPriority(object):
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


class FCMPriorityManager(object):
    """
    A Simple object to make it easier to work with FCM set priorities
    """

    priority_map = {
        FCMPriority.MIN: {
            FCMMode.OAuth2: {
                'message': {
                    'android': {
                        'priority': 'normal'
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
                    'notification': {
                        'notification_priority':
                        NotificationPriority.PRIORITY_MIN,
                    }
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
                        'priority': 'normal'
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
                    },
                    'notification': {
                        'notification_priority':
                        NotificationPriority.PRIORITY_LOW,
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
                        'priority': 'normal'
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
                    },
                    'notification': {
                        'notification_priority':
                        NotificationPriority.PRIORITY_DEFAULT,
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
                        'priority': 'high'
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
                    },
                    'notification': {
                        'notification_priority':
                        NotificationPriority.PRIORITY_HIGH,
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
                        'priority': 'high'
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
                    },
                    'notification': {
                        'notification_priority':
                        NotificationPriority.PRIORITY_MAX,
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
        Allows this object to be wrapped in an Python 3.x based 'if
        statement'.  True is returned if a priority was loaded
        """
        return True if self.priority else False

    def __nonzero__(self):
        """
        Allows this object to be wrapped in an Python 2.x based 'if
        statement'.  True is returned if a priority was loaded
        """
        return True if self.priority else False
