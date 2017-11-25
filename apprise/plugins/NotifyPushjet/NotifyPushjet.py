# -*- encoding: utf-8 -*-
#
# Pushjet Notify Wrapper
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

from .pushjet import errors
from .pushjet import pushjet

from ..NotifyBase import NotifyBase
from ..NotifyBase import NotifyFormat


class NotifyPushjet(NotifyBase):
    """
    A wrapper for Pushjet Notifications
    """

    # The default protocol
    PROTOCOL = 'pjet'

    # The default secure protocol
    SECURE_PROTOCOL = 'pjets'

    def __init__(self, **kwargs):
        """
        Initialize Pushjet Object
        """
        super(NotifyPushjet, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

    def _notify(self, title, body, notify_type):
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

        except (errors.PushjetError, ValueError) as e:
            self.logger.warning('Failed to send Pushjet notification.')
            self.logger.debug('Pushjet Exception: %s' % str(e))
            return False

        return True
