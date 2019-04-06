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

import requests
from json import dumps

from .NotifyBase import NotifyBase
from ..utils import GET_EMAIL_RE
from ..common import NotifyType
from ..utils import parse_list

# Flag used as a placeholder to sending to all devices
PUSHBULLET_SEND_TO_ALL = 'ALL_DEVICES'

# Provide some known codes Pushbullet uses and what they translate to:
PUSHBULLET_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}


class NotifyPushBullet(NotifyBase):
    """
    A wrapper for PushBullet Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushbullet'

    # The services URL
    service_url = 'https://www.pushbullet.com/'

    # The default secure protocol
    secure_protocol = 'pbul'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushbullet'

    # PushBullet uses the http protocol with JSON requests
    notify_url = 'https://api.pushbullet.com/v2/pushes'

    def __init__(self, accesstoken, targets=None, **kwargs):
        """
        Initialize PushBullet Object
        """
        super(NotifyPushBullet, self).__init__(**kwargs)

        self.accesstoken = accesstoken

        self.targets = parse_list(targets)
        if len(self.targets) == 0:
            self.targets = (PUSHBULLET_SEND_TO_ALL, )

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
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

        # Create a copy of the targets list
        targets = list(self.targets)
        while len(targets):
            recipient = targets.pop(0)

            # prepare JSON Object
            payload = {
                'type': 'note',
                'title': title,
                'body': body,
            }

            if recipient is PUSHBULLET_SEND_TO_ALL:
                # Send to all
                pass

            elif GET_EMAIL_RE.match(recipient):
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

            # Always call throttle before any remote server i/o is made
            self.throttle()

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
                    status_str = \
                        NotifyPushBullet.http_response_code_lookup(
                            r.status_code, PUSHBULLET_HTTP_ERROR_MAP)

                    self.logger.warning(
                        'Failed to send PushBullet notification to {}:'
                        '{}{}error={}.'.format(
                            recipient,
                            status_str,
                            ', ' if status_str else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        'Sent PushBullet notification to "%s".' % (recipient))

            except requests.RequestException as e:
                self.logger.warning(
                    'A Connection error occured sending PushBullet '
                    'notification to "%s".' % (recipient),
                )
                self.logger.debug('Socket Exception: %s' % str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        targets = '/'.join([NotifyPushBullet.quote(x) for x in self.targets])
        if targets == PUSHBULLET_SEND_TO_ALL:
            # keyword is reserved for internal usage only; it's safe to remove
            # it from the recipients list
            targets = ''

        return '{schema}://{accesstoken}/{targets}/?{args}'.format(
            schema=self.secure_protocol,
            accesstoken=NotifyPushBullet.quote(self.accesstoken, safe=''),
            targets=targets,
            args=NotifyPushBullet.urlencode(args))

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

        # Fetch our targets
        results['targets'] = \
            NotifyPushBullet.split_path(results['fullpath'])

        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += \
                NotifyPushBullet.parse_list(results['qsd']['to'])

        # Setup the token; we store it in Access Token for global
        # plugin consistency with naming conventions
        results['accesstoken'] = NotifyPushBullet.unquote(results['host'])

        return results
