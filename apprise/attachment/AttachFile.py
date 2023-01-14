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

import re
import os
from .AttachBase import AttachBase
from ..common import ContentLocation
from ..AppriseLocale import gettext_lazy as _


class AttachFile(AttachBase):
    """
    A wrapper for File based attachment sources
    """

    # The default descriptive name associated with the service
    service_name = _('Local File')

    # The default protocol
    protocol = 'file'

    # Content is local to the same location as the apprise instance
    # being called (server-side)
    location = ContentLocation.LOCAL

    def __init__(self, path, **kwargs):
        """
        Initialize Local File Attachment Object

        """
        super().__init__(**kwargs)

        # Store path but mark it dirty since we have not performed any
        # verification at this point.
        self.dirty_path = os.path.expanduser(path)
        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {}

        if self._mimetype:
            # A mime-type was enforced
            params['mime'] = self._mimetype

        if self._name:
            # A name was enforced
            params['name'] = self._name

        return 'file://{path}{params}'.format(
            path=self.quote(self.dirty_path),
            params='?{}'.format(self.urlencode(params)) if params else '',
        )

    def download(self, **kwargs):
        """
        Perform retrieval of our data.

        For file base attachments, our data already exists, so we only need to
        validate it.
        """

        if self.location == ContentLocation.INACCESSIBLE:
            # our content is inaccessible
            return False

        # Ensure any existing content set has been invalidated
        self.invalidate()

        if not os.path.isfile(self.dirty_path):
            return False

        if self.max_file_size > 0 and \
                os.path.getsize(self.dirty_path) > self.max_file_size:

            # The content to attach is to large
            self.logger.error(
                'Content exceeds allowable maximum file length '
                '({}KB): {}'.format(
                    int(self.max_file_size / 1024), self.url(privacy=True)))

            # Return False (signifying a failure)
            return False

        # We're good to go if we get here. Set our minimum requirements of
        # a call do download() before returning a success
        self.download_path = self.dirty_path
        self.detected_name = os.path.basename(self.download_path)

        # We don't need to set our self.detected_mimetype as it can be
        # pulled at the time it's needed based on the detected_name
        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL so that we can handle all different file paths
        and return it as our path object

        """

        results = AttachBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early; it's not a good URL
            return results

        match = re.match(r'file://(?P<path>[^?]+)(\?.*)?', url, re.I)
        if not match:
            return None

        results['path'] = AttachFile.unquote(match.group('path'))
        return results
