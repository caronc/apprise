# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import re
import os
import io
import base64
from .base import AttachBase
from .. import exception
from ..common import ContentLocation
from ..locale import gettext_lazy as _
import uuid


class AttachMemory(AttachBase):
    """
    A wrapper for Memory based attachment sources
    """

    # The default descriptive name associated with the service
    service_name = _('Memory')

    # The default protocol
    protocol = 'memory'

    # Content is local to the same location as the apprise instance
    # being called (server-side)
    location = ContentLocation.LOCAL

    def __init__(self, content=None, name=None, mimetype=None,
                 encoding='utf-8', **kwargs):
        """
        Initialize Memory Based Attachment Object

        """
        # Create our BytesIO object
        self._data = io.BytesIO()

        if content is None:
            # Empty; do nothing
            pass

        elif isinstance(content, str):
            content = content.encode(encoding)
            if mimetype is None:
                mimetype = 'text/plain'

            if not name:
                # Generate a unique filename
                name = str(uuid.uuid4()) + '.txt'

        elif not isinstance(content, bytes):
            raise TypeError(
                'Provided content for memory attachment is invalid')

        # Store our content
        if content:
            self._data.write(content)

        if mimetype is None:
            # Default mimetype
            mimetype = 'application/octet-stream'

        if not name:
            # Generate a unique filename
            name = str(uuid.uuid4()) + '.dat'

        # Initialize our base object
        super().__init__(name=name, mimetype=mimetype, **kwargs)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'mime': self._mimetype,
        }

        return 'memory://{name}?{params}'.format(
            name=self.quote(self._name),
            params=self.urlencode(params, safe='/')
        )

    def open(self, *args, **kwargs):
        """
        return our memory object
        """
        # Return our object
        self._data.seek(0, 0)
        return self._data

    def __enter__(self):
        """
        support with clause
        """
        # Return our object
        self._data.seek(0, 0)
        return self._data

    def download(self, **kwargs):
        """
        Handle memory download() call
        """

        if self.location == ContentLocation.INACCESSIBLE:
            # our content is inaccessible
            return False

        if self.max_file_size > 0 and len(self) > self.max_file_size:
            # The content to attach is to large
            self.logger.error(
                'Content exceeds allowable maximum memory size '
                '({}KB): {}'.format(
                    int(self.max_file_size / 1024), self.url(privacy=True)))

            # Return False (signifying a failure)
            return False

        return True

    def base64(self, encoding='ascii'):
        """
        We need to over-ride this since the base64 sub-library seems to close
        our file descriptor making it no longer referencable.
        """

        if not self:
            # We could not access the attachment
            self.logger.error(
                'Could not access attachment {}.'.format(
                    self.url(privacy=True)))
            raise exception.AppriseFileNotFound("Attachment Missing")
        self._data.seek(0, 0)

        return base64.b64encode(self._data.read()).decode(encoding) \
            if encoding else base64.b64encode(self._data.read())

    def invalidate(self):
        """
        Removes data
        """
        self._data.truncate(0)
        return

    def exists(self):
        """
        over-ride exists() call
        """
        size = len(self)
        return True if self.location != ContentLocation.INACCESSIBLE \
            and size > 0 and (
                self.max_file_size <= 0 or
                (self.max_file_size > 0 and size <= self.max_file_size)) \
            else False

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

        if 'name' not in results:
            # Allow fall-back to be from URL
            match = re.match(r'memory://(?P<path>[^?]+)(\?.*)?', url, re.I)
            if match:
                # Store our filename only (ignore any defined paths)
                results['name'] = \
                    os.path.basename(AttachMemory.unquote(match.group('path')))
        return results

    @property
    def path(self):
        """
        return the filename
        """
        if not self.exists():
            # we could not obtain our path
            return None

        return self._name

    def __len__(self):
        """
        Returns the size of he memory attachment

        """
        return self._data.getbuffer().nbytes

    def __bool__(self):
        """
        Allows the Apprise object to be wrapped in an based 'if statement'.
        True is returned if our content was downloaded correctly.
        """

        return self.exists()
