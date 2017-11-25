# -*- encoding: utf-8 -*-
#
# PushBullet Notify Wrapper
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

from json import dumps
import requests
import re

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import HTTP_ERROR_MAP
from .NotifyBase import IS_EMAIL_RE

# Flag used as a placeholder to sending to all devices
PUSHBULLET_SEND_TO_ALL = 'ALL_DEVICES'

# PushBullet uses the http protocol with JSON requests
PUSHBULLET_URL = 'https://api.pushbullet.com/v2/pushes'

# Used to break apart list of potential recipients by their delimiter
# into a usable list.
RECIPIENTS_LIST_DELIM = re.compile(r'[ \t\r\n,\\/]+')

# Extend HTTP Error Messages
PUSHBULLET_HTTP_ERROR_MAP = dict(HTTP_ERROR_MAP.items() + {
    401: 'Unauthorized - Invalid Token.',
}.items())


class NotifyPushBullet(NotifyBase):
    """
    A wrapper for PushBullet Notifications
    """

    # The default protocol
    PROTOCOL = 'pbul'

    # The default secure protocol
    SECURE_PROTOCOL = 'pbul'

    def __init__(self, accesstoken, recipients=None, **kwargs):
        """
        Initialize PushBullet Object
        """
        super(NotifyPushBullet, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

        self.accesstoken = accesstoken
        if isinstance(recipients, basestring):
            self.recipients = filter(bool, RECIPIENTS_LIST_DELIM.split(
                recipients,
            ))
        elif isinstance(recipients, (tuple, list)):
            self.recipients = recipients
        else:
            self.recipients = list()

        if len(self.recipients) == 0:
            self.recipients = (PUSHBULLET_SEND_TO_ALL, )

    def _notify(self, title, body, **kwargs):
        """
        Perform PushBullet Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }
        auth = (self.accesstoken, '')

        # error tracking (used for function return)
        has_error = False

        # Create a copy of the recipients list
        recipients = list(self.recipients)
        while len(recipients):
            recipient = recipients.pop(0)

            # prepare JSON Object
            payload = {
                'type': 'note',
                'title': title,
                'body': body,
            }

            if recipient is PUSHBULLET_SEND_TO_ALL:
                # Send to all
                pass

            elif IS_EMAIL_RE.match(recipient):
                payload['email'] = recipient
                self.logger.debug(
                    "Recipient '%s' is an email address" % recipient)

            elif recipient[0] == '#':
                payload['channel_tag'] = recipient[1:]
                self.logger.debug("Recipient '%s' is a channel" % recipient)

            else:
                payload['device_iden'] = recipient
                self.logger.debug(
                    "Recipient '%s' is a device" % recipient)

            self.logger.debug('PushBullet POST URL: %s (cert_verify=%r)' % (
                PUSHBULLET_URL, self.verify_certificate,
            ))
            self.logger.debug('PushBullet Payload: %s' % str(payload))
            try:
                r = requests.post(
                    PUSHBULLET_URL,
                    data=dumps(payload),
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    try:
                        self.logger.warning(
                            'Failed to send PushBullet notification: '
                            '%s (error=%s).' % (
                                PUSHBULLET_HTTP_ERROR_MAP[r.status_code],
                                r.status_code))

                    except IndexError:
                        self.logger.warning(
                            'Failed to send PushBullet notification '
                            '(error=%s).' % r.status_code)

                    # self.logger.debug('Response Details: %s' % r.raw.read())

                    # Return; we're done
                    has_error = True

            except requests.ConnectionError as e:
                self.logger.warning(
                    'A Connection error occured sending PushBullet '
                    'notification.'
                )
                self.logger.debug('Socket Exception: %s' % str(e))
                has_error = True

            if len(recipients):
                # Prevent thrashing requests
                self.throttle()

        return not has_error
