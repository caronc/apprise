# -*- encoding: utf-8 -*-
#
# JSON Notify Wrapper
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

from .NotifyBase import NotifyBase
from .NotifyBase import NotifyFormat
from .NotifyBase import NotifyImageSize
from .NotifyBase import HTTP_ERROR_MAP

# Image Support (128x128)
JSON_IMAGE_XY = NotifyImageSize.XY_128


class NotifyJSON(NotifyBase):
    """
    A wrapper for JSON Notifications
    """

    # The default protocol
    PROTOCOL = 'json'

    # The default secure protocol
    SECURE_PROTOCOL = 'jsons'

    def __init__(self, **kwargs):
        """
        Initialize JSON Object
        """
        super(NotifyJSON, self).__init__(
            title_maxlen=250, body_maxlen=32768,
            image_size=JSON_IMAGE_XY,
            notify_format=NotifyFormat.TEXT,
            **kwargs)

        if self.secure:
            self.schema = 'https'

        else:
            self.schema = 'http'

        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, basestring):
            self.fullpath = '/'

        return

    def _notify(self, title, body, notify_type, **kwargs):
        """
        Perform JSON Notification
        """

        # prepare JSON Object
        payload = {
            # Version: Major.Minor,  Major is only updated if the entire
            # schema is changed. If just adding new items (or removing
            # old ones, only increment the Minor!
            'version': '1.0',
            'title': title,
            'message': body,
            'type': notify_type,
        }

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/json'
        }

        auth = None
        if self.user:
            auth = (self.user, self.password)

        url = '%s://%s' % (self.schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath

        self.logger.debug('JSON POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('JSON Payload: %s' % str(payload))
        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                auth=auth,
                verify=self.verify_certificate,
            )
            if r.status_code != requests.codes.ok:
                try:
                    self.logger.warning(
                        'Failed to send JSON notification: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send JSON notification '
                        '(error=%s).' % (
                            r.status_code))

                # Return; we're done
                return False

        except requests.ConnectionError as e:
            self.logger.warning(
                'A Connection error occured sending JSON '
                'notification to %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return; we're done
            return False

        return True
