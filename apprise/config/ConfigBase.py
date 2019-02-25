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
import six
import logging

from .. import plugins
from ..AppriseAsset import AppriseAsset
from ..URLBase import URLBase
from ..common import ConfigFormat
from ..common import CONFIG_FORMATS
from ..utils import GET_SCHEMA_RE
from ..utils import parse_list

logger = logging.getLogger(__name__)


class ConfigBase(URLBase):
    """
    This is the base class for all supported configuration sources
    """

    # The Default Encoding to use if not otherwise detected
    encoding = 'utf-8'

    # The default expected configuration format unless otherwise
    # detected by the sub-modules
    default_config_format = ConfigFormat.TEXT

    # This is only set if the user overrides the config format on the URL
    # this should always initialize itself as None
    config_format = None

    # Don't read any more of this amount of data into memory as there is no
    # reason we should be reading in more. This is more of a safe guard then
    # anything else. 128KB (131072B)
    max_buffer_size = 131072

    # Logging
    logger = logging.getLogger(__name__)

    def __init__(self, **kwargs):
        """
        Initialize some general logging and common server arguments that will
        keep things consistent when working with the configurations that
        inherit this class.

        """

        super(ConfigBase, self).__init__(**kwargs)

        # Tracks previously loaded content for speed
        self._cached_servers = None

        if 'encoding' in kwargs:
            # Store the encoding
            self.encoding = kwargs.get('encoding')

        if 'format' in kwargs:
            # Store the enforced config format
            self.config_format = kwargs.get('format').lower()

            if self.config_format not in CONFIG_FORMATS:
                # Simple error checking
                err = 'An invalid config format ({}) was specified.'.format(
                    self.config_format)
                self.logger.warning(err)
                raise TypeError(err)

        return

    def servers(self, asset=None, cache=True, **kwargs):
        """
        Performs reads loaded configuration and returns all of the services
        that could be parsed and loaded.

        """

        if cache is True and isinstance(self._cached_servers, list):
            # We already have cached results to return; use them
            return self._cached_servers

        # Our response object
        self._cached_servers = list()

        # read() causes the child class to do whatever it takes for the
        # config plugin to load the data source and return unparsed content
        # None is returned if there was an error or simply no data
        content = self.read(**kwargs)
        if not isinstance(content, six.string_types):
            # Nothing more to do
            return list()

        # Our Configuration format uses a default if one wasn't one detected
        # or enfored.
        config_format = \
            self.default_config_format \
            if self.config_format is None else self.config_format

        # Dynamically load our parse_ function based on our config format
        fn = getattr(ConfigBase, 'config_parse_{}'.format(config_format))

        # Execute our config parse function which always returns a list
        self._cached_servers.extend(fn(content=content, asset=asset))

        return self._cached_servers

    def read(self):
        """
        This object should be implimented by the child classes

        """
        return None

    @staticmethod
    def parse_url(url, verify_host=True):
        """Parses the URL and returns it broken apart into a dictionary.

        This is very specific and customized for Apprise.


        Args:
            url (str): The URL you want to fully parse.
            verify_host (:obj:`bool`, optional): a flag kept with the parsed
                 URL which some child classes will later use to verify SSL
                 keys (if SSL transactions take place).  Unless under very
                 specific circumstances, it is strongly recomended that
                 you leave this default value set to True.

        Returns:
            A dictionary is returned containing the URL fully parsed if
            successful, otherwise None is returned.
        """

        results = URLBase.parse_url(url, verify_host=verify_host)

        if not results:
            # We're done; we failed to parse our url
            return results

        # Allow overriding the default config format
        if 'format' in results['qsd']:
            results['format'] = results['qsd'].get('format')
            if results['format'] not in CONFIG_FORMATS:
                URLBase.logger.warning(
                    'Unsupported format specified {}'.format(
                        results['format']))
                del results['format']

        # Defines the encoding of the payload
        if 'encoding' in results['qsd']:
            results['encoding'] = results['qsd'].get('encoding')

        return results

    @staticmethod
    def config_parse_text(content, asset=None):
        """
        Parse the specified content as though it were a simple text file only
        containing a list of URLs. Return a list of loaded notification plugins

        Optionally associate an asset with the notification.

        """
        # For logging, track the line number
        line = 0

        response = list()

        # Define what a valid line should look like
        valid_line_re = re.compile(
            r'^\s*(?P<line>([;#]+(?P<comment>.*))|'
            r'(\s*(?P<tags>[^=]+)=|=)?\s*'
            r'(?P<url>[a-z0-9]{2,9}://.*))?$', re.I)

        # split our content up to read line by line
        content = re.split(r'\r*\n', content)

        for entry in content:
            # Increment our line count
            line += 1

            result = valid_line_re.match(entry)
            if not result:
                # Invalid syntax
                logger.error(
                    'Invalid apprise text format found '
                    '{} on line {}.'.format(entry, line))

                # Assume this is a file we shouldn't be parsing. It's owner
                # can read the error printed to screen and take action
                # otherwise.
                return list()

            if result.group('comment') or not result.group('line'):
                # Comment/empty line; do nothing
                continue

            # Store our url read in
            url = result.group('url')

            # swap hash (#) tag values with their html version
            _url = url.replace('/#', '/%23')

            # Attempt to acquire the schema at the very least to allow our
            # plugins to determine if they can make a better
            # interpretation of a URL geared for them
            schema = GET_SCHEMA_RE.match(_url)

            # Ensure our schema is always in lower case
            schema = schema.group('schema').lower()

            # Some basic validation
            if schema not in plugins.SCHEMA_MAP:
                logger.warning(
                    'Unsupported schema {} on line {}.'.format(
                        schema, line))
                continue

            # Parse our url details of the server object as dictionary
            # containing all of the information parsed from our URL
            results = plugins.SCHEMA_MAP[schema].parse_url(_url)

            if not results:
                # Failed to parse the server URL
                logger.warning(
                    'Unparseable URL {} on line {}.'.format(url, line))
                continue

            # Build a list of tags to associate with the newly added
            # notifications if any were set
            results['tag'] = set(parse_list(result.group('tags')))

            # Prepare our Asset Object
            results['asset'] = \
                asset if isinstance(asset, AppriseAsset) else AppriseAsset()

            try:
                # Attempt to create an instance of our plugin using the
                # parsed URL information
                plugin = plugins.SCHEMA_MAP[results['schema']](**results)

            except Exception:
                # the arguments are invalid or can not be used.
                logger.warning(
                    'Could not load URL {} on line {}.'.format(
                        url, line))
                continue

            # if we reach here, we successfully loaded our data
            response.append(plugin)

        # Return what was loaded
        return response

    @staticmethod
    def config_parse_yaml(content, asset=None):
        """
        Parse the specified content as though it were a yaml file
        specifically formatted for apprise. Return a list of loaded
        notification plugins.

        Optionally associate an asset with the notification.

        """
        response = list()

        # TODO

        return response

    def pop(self, index):
        """
        Removes an indexed Notification Service from the stack and
        returns it.
        """

        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers(cache=True)

        # Pop the element off of the stack
        return self._cached_servers.pop(index)

    def __getitem__(self, index):
        """
        Returns the indexed server entry associated with the loaded
        notification servers
        """
        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers(cache=True)

        return self._cached_servers[index]

    def __iter__(self):
        """
        Returns an iterator to our server list
        """
        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers(cache=True)

        return iter(self._cached_servers)

    def __len__(self):
        """
        Returns the total number of servers loaded
        """
        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers(cache=True)

        return len(self._cached_servers)
