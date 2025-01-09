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
import requests
from .base import ConfigBase
from ..common import ConfigFormat
from ..common import ContentIncludeMode
from ..url import PrivacyMode
from ..locale import gettext_lazy as _

# Support YAML formats
# text/yaml
# text/x-yaml
# application/yaml
# application/x-yaml
MIME_IS_YAML = re.compile('(text|application)/(x-)?yaml', re.I)

# Support TEXT formats
# text/plain
# text/html
MIME_IS_TEXT = re.compile('text/(plain|html)', re.I)


class ConfigHTTP(ConfigBase):
    """
    A wrapper for HTTP based configuration sources
    """

    # The default descriptive name associated with the service
    service_name = _('Web Based')

    # The default protocol
    protocol = 'http'

    # The default secure protocol
    secure_protocol = 'https'

    # If an HTTP error occurs, define the number of characters you still want
    # to read back.  This is useful for debugging purposes, but nothing else.
    # The idea behind enforcing this kind of restriction is to prevent abuse
    # from queries to services that may be untrusted.
    max_error_buffer_size = 2048

    # Configuration file inclusion can always include this type
    allow_cross_includes = ContentIncludeMode.ALWAYS

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

        # Define any arguments set
        params = {
            'encoding': self.encoding,
            'cache': cache,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.config_format:
            # A format was enforced; make sure it's passed back with the url
            params['format'] = self.config_format

        # Append our headers into our args
        params.update({'+{}'.format(k): v for k, v in self.headers.items()})

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

        return '{schema}://{auth}{hostname}{port}{fullpath}/?{params}'.format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            hostname=self.quote(self.host, safe=''),
            port='' if self.port is None or self.port == default_port
                 else ':{}'.format(self.port),
            fullpath=self.quote(self.fullpath, safe='/'),
            params=self.urlencode(params),
        )

    def read(self, **kwargs):
        """
        Perform retrieval of the configuration based on the specified request
        """

        # prepare XML Object
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

        # Prepare our response object
        response = None

        # Where our request object will temporarily live.
        r = None

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            # Make our request
            with requests.post(
                    url,
                    headers=headers,
                    auth=auth,
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

                # Store our response
                if self.max_buffer_size > 0 \
                        and file_size > self.max_buffer_size:

                    # Provide warning of data truncation
                    self.logger.error(
                        'HTTP config response exceeds maximum buffer length '
                        '({}KB);'.format(int(self.max_buffer_size / 1024)))

                    # Return None - buffer execeeded
                    return None

                # Store our result (but no more than our buffer length)
                response = r.text[:self.max_buffer_size + 1]

                # Verify that our content did not exceed the buffer size:
                if len(response) > self.max_buffer_size:
                    # Provide warning of data truncation
                    self.logger.error(
                        'HTTP config response exceeds maximum buffer length '
                        '({}KB);'.format(int(self.max_buffer_size / 1024)))

                    # Return None - buffer execeeded
                    return None

                # Detect config format based on mime if the format isn't
                # already enforced
                content_type = r.headers.get(
                    'Content-Type', 'application/octet-stream')
                if self.config_format is None and content_type:
                    if MIME_IS_YAML.match(content_type) is not None:

                        # YAML data detected based on header content
                        self.default_config_format = ConfigFormat.YAML

                    elif MIME_IS_TEXT.match(content_type) is not None:

                        # TEXT data detected based on header content
                        self.default_config_format = ConfigFormat.TEXT

        except requests.RequestException as e:
            self.logger.error(
                'A Connection error occurred retrieving HTTP '
                'configuration from %s.' % self.host)
            self.logger.debug('Socket Exception: %s' % str(e))

            # Return None (signifying a failure)
            return None

        # Return our response object
        return response

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = ConfigBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set
        results['headers'] = results['qsd-']
        results['headers'].update(results['qsd+'])

        return results
