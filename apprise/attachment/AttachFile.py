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
        super(AttachFile, self).__init__(**kwargs)

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
