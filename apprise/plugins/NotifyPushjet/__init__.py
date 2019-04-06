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

import re
from . import pushjet

from ..NotifyBase import NotifyBase
from ...common import NotifyType

PUBLIC_KEY_RE = re.compile(
    r'^[a-z0-9]{4}-[a-z0-9]{6}-[a-z0-9]{12}-[a-z0-9]{5}-[a-z0-9]{9}$', re.I)

SECRET_KEY_RE = re.compile(r'^[a-z0-9]{32}$', re.I)


class NotifyPushjet(NotifyBase):
    """
    A wrapper for Pushjet Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushjet'

    # The default protocol
    protocol = 'pjet'

    # The default secure protocol
    secure_protocol = 'pjets'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushjet'

    # Disable throttle rate for Pushjet requests since they are normally
    # local anyway (the remote/online service is no more)
    request_rate_per_sec = 0

    def __init__(self, secret_key, **kwargs):
        """
        Initialize Pushjet Object
        """
        super(NotifyPushjet, self).__init__(**kwargs)

        if not secret_key:
            # You must provide a Pushjet key to work with
            msg = 'You must specify a Pushjet Secret Key.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # store our key
        self.secret_key = secret_key

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Pushjet Notification
        """
        # Always call throttle before any remote server i/o is made
        self.throttle()

        server = "https://" if self.secure else "http://"

        server += self.host
        if self.port:
            server += ":" + str(self.port)

        try:
            api = pushjet.pushjet.Api(server)
            service = api.Service(secret_key=self.secret_key)

            service.send(body, title)
            self.logger.info('Sent Pushjet notification.')

        except (pushjet.errors.PushjetError, ValueError) as e:
            self.logger.warning('Failed to send Pushjet notification.')
            self.logger.debug('Pushjet Exception: %s' % str(e))
            return False

        return True

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

        default_port = 443 if self.secure else 80

        return '{schema}://{secret_key}@{hostname}{port}/?{args}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            secret_key=NotifyPushjet.quote(self.secret_key, safe=''),
            hostname=NotifyPushjet.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            args=NotifyPushjet.urlencode(args),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        Syntax:
           pjet://secret_key@hostname
           pjet://secret_key@hostname:port
           pjets://secret_key@hostname
           pjets://secret_key@hostname:port

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store it as it's value
        results['secret_key'] = \
            NotifyPushjet.unquote(results.get('user'))

        return results
