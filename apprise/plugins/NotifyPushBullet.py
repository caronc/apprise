# -*- coding: utf-8 -*-
#
# PushBullet Notify Wrapper
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
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
import requests
from json import dumps
from urllib import unquote

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from .NotifyBase import IS_EMAIL_RE

# Flag used as a placeholder to sending to all devices
PUSHBULLET_SEND_TO_ALL = 'ALL_DEVICES'

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
    protocol = 'pbul'

    # The default secure protocol
    secure_protocol = 'pbul'

    # PushBullet uses the http protocol with JSON requests
    notify_url = 'https://api.pushbullet.com/v2/pushes'

    def __init__(self, accesstoken, recipients=None, **kwargs):
        """
        Initialize PushBullet Object
        """
        super(NotifyPushBullet, self).__init__(
            title_maxlen=250, body_maxlen=32768, **kwargs)

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

    def notify(self, title, body, **kwargs):
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
                self.notify_url, self.verify_certificate,
            ))
            self.logger.debug('PushBullet Payload: %s' % str(payload))
            try:
                r = requests.post(
                    self.notify_url,
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
        try:
            recipients = unquote(results['fullpath'])

        except AttributeError:
            recipients = ''

        results['accesstoken'] = results['host']
        results['recipients'] = recipients

        return results
