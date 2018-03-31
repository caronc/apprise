# -*- coding: utf-8 -*-
#
# Pushjet Notify Wrapper
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

    # The default protocol
    protocol = 'pjet'

    # The default secure protocol
    secure_protocol = 'pjets'

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
