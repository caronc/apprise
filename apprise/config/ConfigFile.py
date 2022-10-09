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
from .ConfigBase import ConfigBase
from ..common import ConfigFormat
from ..common import ContentIncludeMode
from ..AppriseLocale import gettext_lazy as _


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
        self.path = os.path.abspath(os.path.expanduser(path))

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
            path=self.quote(self.path),
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
