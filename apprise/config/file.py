# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
from .base import ConfigBase
from ..utils.disk import path_decode
from ..common import ConfigFormat
from ..common import ContentIncludeMode
from ..locale import gettext_lazy as _


class ConfigFile(ConfigBase):
    """
    A wrapper for File based configuration sources
    """

    # The default descriptive name associated with the service
    service_name = _('Local File')

    # The default protocol
    protocol = 'file'

    # Configuration file inclusion can only be of the same type
    allow_cross_includes = ContentIncludeMode.STRICT

    def __init__(self, path, **kwargs):
        """
        Initialize File Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with

        """
        super().__init__(**kwargs)

        # Store our file path as it was set
        self.path = path_decode(path)

        # Track the file as it was saved
        self.__original_path = os.path.normpath(path)

        # Update the config path to be relative to our file we just loaded
        self.config_path = os.path.dirname(self.path)

        return

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Prepare our cache value
        if isinstance(self.cache, bool) or not self.cache:
            cache = 'yes' if self.cache else 'no'

        else:
            cache = int(self.cache)

        # Define any URL parameters
        params = {
            'encoding': self.encoding,
            'cache': cache,
        }

        if self.config_format:
            # A format was enforced; make sure it's passed back with the url
            params['format'] = self.config_format

        return 'file://{path}{params}'.format(
            path=self.quote(self.__original_path),
            params='?{}'.format(self.urlencode(params)) if params else '',
        )

    def read(self, **kwargs):
        """
        Perform retrieval of the configuration based on the specified request
        """

        response = None

        try:
            if self.max_buffer_size > 0 and \
                    os.path.getsize(self.path) > self.max_buffer_size:

                # Content exceeds maximum buffer size
                self.logger.error(
                    'File size exceeds maximum allowable buffer length'
                    ' ({}KB).'.format(int(self.max_buffer_size / 1024)))
                return None

        except OSError:
            # getsize() can throw this acception if the file is missing
            # and or simply isn't accessible
            self.logger.error(
                'File is not accessible: {}'.format(self.path))
            return None

        # Always call throttle before any server i/o is made
        self.throttle()

        try:
            with open(self.path, "rt", encoding=self.encoding) as f:
                # Store our content for parsing
                response = f.read()

        except (ValueError, UnicodeDecodeError):
            # A result of our strict encoding check; if we receive this
            # then the file we're opening is not something we can
            # understand the encoding of..

            self.logger.error(
                'File not using expected encoding ({}) : {}'.format(
                    self.encoding, self.path))
            return None

        except (IOError, OSError):
            # IOError is present for backwards compatibility with Python
            # versions older then 3.3.  >= 3.3 throw OSError now.

            # Could not open and/or read the file; this is not a problem since
            # we scan a lot of default paths.
            self.logger.error(
                'File can not be opened for read: {}'.format(self.path))
            return None

        # Detect config format based on file extension if it isn't already
        # enforced
        if self.config_format is None and \
                re.match(r'^.*\.ya?ml\s*$', self.path, re.I) is not None:

            # YAML Filename Detected
            self.default_config_format = ConfigFormat.YAML

        # Return our response object
        return response

    @staticmethod
    def parse_url(url):
        """
        Parses the URL so that we can handle all different file paths
        and return it as our path object

        """

        results = ConfigBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early; it's not a good URL
            return results

        match = re.match(r'[a-z0-9]+://(?P<path>[^?]+)(\?.*)?', url, re.I)
        if not match:
            return None

        results['path'] = ConfigFile.unquote(match.group('path'))
        return results
