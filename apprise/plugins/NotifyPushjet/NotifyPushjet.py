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
from .pushjet import errors
from .pushjet import pushjet

from ..NotifyBase import NotifyBase

PUBLIC_KEY_RE = re.compile(
    r'^[a-z0-9]{4}-[a-z0-9]{6}-[a-z0-9]{12}-[a-z0-9]{5}-[a-z0-9]{9}$', re.I)

SECRET_KEY_RE = re.compile(r'^[a-z0-9]{32}$', re.I)


class NotifyPushjet(NotifyBase):
    """
    A wrapper for Pushjet Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Pushjet'

    # The services URL
    service_url = 'https://pushjet.io/'

    # The default protocol
    protocol = 'pjet'

    # The default secure protocol
    secure_protocol = 'pjets'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_pushjet'

    def __init__(self, **kwargs):
        """
        Initialize Pushjet Object
        """
        super(NotifyPushjet, self).__init__(**kwargs)

    def notify(self, title, body, notify_type):
        """
        Perform Pushjet Notification
        """
        try:
            if self.user and self.host:
                server = "http://"
                if self.secure:
                    server = "https://"

                server += self.host
                if self.port:
                    server += ":" + str(self.port)

                api = pushjet.Api(server)
                service = api.Service(secret_key=self.user)

            else:
                api = pushjet.Api(pushjet.DEFAULT_API_URL)
                service = api.Service(secret_key=self.host)

            service.send(body, title)
            self.logger.info('Sent Pushjet notification.')

        except (errors.PushjetError, ValueError) as e:
            self.logger.warning('Failed to send Pushjet notification.')
            self.logger.debug('Pushjet Exception: %s' % str(e))
            return False

        return True
