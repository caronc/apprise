# -*- coding: utf-8 -*-
# BSD 3-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2023, Chris Caron <lead2gold@gmail.com>
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
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
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
import requests
from tempfile import NamedTemporaryFile
from .AttachBase import AttachBase
from ..common import ContentLocation
from ..URLBase import PrivacyMode
from ..AppriseLocale import gettext_lazy as _


class AttachHTTP(AttachBase):
    """
    A wrapper for HTTP based attachment sources
    """

    # The default descriptive name associated with the service
    service_name = _('Web Based')

    # The default protocol
    protocol = 'http'

    # The default secure protocol
    secure_protocol = 'https'

    # The number of bytes in memory to read from the remote source at a time
    chunk_size = 8192

    # Web based requests are remote/external to our current location
    location = ContentLocation.HOSTED

    def __init__(self, headers=None, **kwargs):
        """
        Initialize HTTP Object

        headers can be a dictionary of key/value pairs that you want to
        additionally include as part of the server headers to post with

        """
        super().__init__(**kwargs)

        self.schema = 'https' if self.secure else 'http'

        self.fullpath = kwargs.get('fullpath')
        if not isinstance(self.fullpath, str):
            self.fullpath = '/'

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        # Where our content is written to upon a call to download.
        self._temp_file = None

        # Our Query String Dictionary; we use this to track arguments
        # specified that aren't otherwise part of this class
        self.qsd = {k: v for k, v in kwargs.get('qsd', {}).items()
                    if k not in self.template_args}

        return

    def download(self, **kwargs):
        """
        Perform retrieval of the configuration based on the specified request
        """

        if self.location == ContentLocation.INACCESSIBLE:
            # our content is inaccessible
            return False

        # Ensure any existing content set has been invalidated
        self.invalidate()

        # prepare header
        headers = {
            'User-Agent': self.app_id,
        }

        # Apply any/all header over-rides defined
        headers.update(self.headers)

        auth = None
        if self.user:
            auth = (self.user, self.password)

        url = '%s://%s' % (self.schema, self.host)
        if isinstance(self.port, int):
            url += ':%d' % self.port

        url += self.fullpath

        self.logger.debug('HTTP POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))

        # Where our request object will temporarily live.
        r = None

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            # Make our request
            with requests.get(
                    url,
                    headers=headers,
                    auth=auth,
                    params=self.qsd,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    stream=True) as r:

                # Handle Errors
                r.raise_for_status()

                # Get our file-size (if known)
                try:
                    file_size = int(r.headers.get('Content-Length', '0'))
                except (TypeError, ValueError):
                    # Handle edge case where Content-Length is a bad value
                    file_size = 0

                # Perform a little Q/A on file limitations and restrictions
                if self.max_file_size > 0 and file_size > self.max_file_size:

                    # The content retrieved is to large
                    self.logger.error(
                        'HTTP response exceeds allowable maximum file length '
                        '({}KB): {}'.format(
                            int(self.max_file_size / 1024),
                            self.url(privacy=True)))

                    # Return False (signifying a failure)
                    return False

                # Detect config format based on mime if the format isn't
                # already enforced
                self.detected_mimetype = r.headers.get('Content-Type')

                d = r.headers.get('Content-Disposition', '')
                result = re.search(
                    "filename=['\"]?(?P<name>[^'\"]+)['\"]?", d, re.I)
                if result:
                    self.detected_name = result.group('name').strip()

                # Create a temporary file to work with
                self._temp_file = NamedTemporaryFile()

                # Get our chunk size
                chunk_size = self.chunk_size

                # Track all bytes written to disk
                bytes_written = 0

                # If we get here, we can now safely write our content to disk
                for chunk in r.iter_content(chunk_size=chunk_size):
                    # filter out keep-alive chunks
                    if chunk:
                        self._temp_file.write(chunk)
                        bytes_written = self._temp_file.tell()

                        # Prevent a case where Content-Length isn't provided
                        # we don't want to fetch beyond our limits
                        if self.max_file_size > 0:
                            if bytes_written > self.max_file_size:
                                # The content retrieved is to large
                                self.logger.error(
                                    'HTTP response exceeds allowable maximum '
                                    'file length ({}KB): {}'.format(
                                        int(self.max_file_size / 1024),
                                        self.url(privacy=True)))

                                # Invalidate any variables previously set
                                self.invalidate()

                                # Return False (signifying a failure)
                                return False

                            elif bytes_written + chunk_size \
                                    > self.max_file_size:
                                # Adjust out next read to accomodate up to our
                                # limit +1. This will prevent us from readig
                                # to much into our memory buffer
                                self.max_file_size - bytes_written + 1

                # Ensure our content is flushed to disk for post-processing
                self._temp_file.flush()

            # Set our minimum requirements for a successful download() call
            self.download_path = self._temp_file.name
            if not self.detected_name:
                self.detected_name = os.path.basename(self.fullpath)

        except requests.RequestException as e:
            self.logger.error(
                'A Connection error occurred retrieving HTTP '
                'configuration from %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Invalidate any variables previously set
            self.invalidate()

            # Return False (signifying a failure)
            return False

        except (IOError, OSError):
            # IOError is present for backwards compatibility with Python
            # versions older then 3.3.  >= 3.3 throw OSError now.

            # Could not open and/or write the temporary file
            self.logger.error(
                'Could not write attachment to disk: {}'.format(
                    self.url(privacy=True)))

            # Invalidate any variables previously set
            self.invalidate()

            # Return False (signifying a failure)
            return False

        # Return our success
        return True

    def invalidate(self):
        """
        Close our temporary file
        """
        if self._temp_file:
            self._temp_file.close()
            self._temp_file = None

        super().invalidate()

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Prepare our cache value
        if self.cache is not None:
            if isinstance(self.cache, bool) or not self.cache:
                cache = 'yes' if self.cache else 'no'
            else:
                cache = int(self.cache)

            # Set our cache value
            params['cache'] = cache

        if self._mimetype:
            # A format was enforced
            params['mime'] = self._mimetype

        if self._name:
            # A name was enforced
            params['name'] = self._name

        # Append our headers into our parameters
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

        # Apply any remaining entries to our URL
        params.update(self.qsd)

        # Determine Authentication
        auth = ''
        if self.user and self.password:
            auth = '{user}:{password}@'.format(
                user=self.quote(self.user, safe=''),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=''),
            )
        elif self.user:
            auth = '{user}@'.format(
                user=self.quote(self.user, safe=''),
            )

        default_port = 443 if self.secure else 80

        return '{schema}://{auth}{hostname}{port}{fullpath}?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=self.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            fullpath=self.quote(self.fullpath, safe='/'),
            params=self.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = AttachBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set
        results['headers'] = results['qsd-']
        results['headers'].update(results['qsd+'])

        return results
