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

import os
import re
import six
import yaml

from .. import plugins
from ..AppriseAsset import AppriseAsset
from ..URLBase import URLBase
from ..common import ConfigFormat
from ..common import CONFIG_FORMATS
from ..utils import GET_SCHEMA_RE
from ..utils import parse_list


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

        if len(self._cached_servers):
            self.logger.info('Loaded {} entries from {}'.format(
                len(self._cached_servers), self.url()))
        else:
            self.logger.warning('Failed to load configuration from {}'.format(
                self.url()))

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

        The file syntax is:

            #
            # pound/hashtag allow for line comments
            #
            # One or more tags can be idenified using comma's (,) to separate
            # them.
            <Tag(s)>=<URL>

            # Or you can use this format (no tags associated)
            <URL>

        """
        # For logging, track the line number
        line = 0

        response = list()

        # Define what a valid line should look like
        valid_line_re = re.compile(
            r'^\s*(?P<line>([;#]+(?P<comment>.*))|'
            r'(\s*(?P<tags>[^=]+)=|=)?\s*'
            r'(?P<url>[a-z0-9]{2,9}://.*))?$', re.I)

        try:
            # split our content up to read line by line
            content = re.split(r'\r*\n', content)

        except TypeError:
            # content was not expected string type
            ConfigBase.logger.error('Invalid apprise text data specified')
            return list()

        for entry in content:
            # Increment our line count
            line += 1

            result = valid_line_re.match(entry)
            if not result:
                # Invalid syntax
                ConfigBase.logger.error(
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
                ConfigBase.logger.warning(
                    'Unsupported schema {} on line {}.'.format(
                        schema, line))
                continue

            # Parse our url details of the server object as dictionary
            # containing all of the information parsed from our URL
            results = plugins.SCHEMA_MAP[schema].parse_url(_url)

            if results is None:
                # Failed to parse the server URL
                ConfigBase.logger.warning(
                    'Unparseable URL {} on line {}.'.format(url, line))
                continue

            # Build a list of tags to associate with the newly added
            # notifications if any were set
            results['tag'] = set(parse_list(result.group('tags')))

            ConfigBase.logger.trace(
                'URL {} unpacked as:{}{}'.format(
                    url, os.linesep, os.linesep.join(
                        ['{}="{}"'.format(k, v) for k, v in results.items()])))

            # Prepare our Asset Object
            results['asset'] = \
                asset if isinstance(asset, AppriseAsset) else AppriseAsset()

            try:
                # Attempt to create an instance of our plugin using the
                # parsed URL information
                plugin = plugins.SCHEMA_MAP[results['schema']](**results)

                # Create log entry of loaded URL
                ConfigBase.logger.debug('Loaded URL: {}'.format(plugin.url()))

            except Exception as e:
                # the arguments are invalid or can not be used.
                ConfigBase.logger.warning(
                    'Could not load URL {} on line {}.'.format(
                        url, line))
                ConfigBase.logger.debug('Loading Exception: %s' % str(e))
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

        try:
            # Load our data (safely)
            result = yaml.load(content, Loader=yaml.SafeLoader)

        except (AttributeError, yaml.error.MarkedYAMLError) as e:
            # Invalid content
            ConfigBase.logger.error(
                'Invalid apprise yaml data specified.')
            ConfigBase.logger.debug(
                'YAML Exception:{}{}'.format(os.linesep, e))
            return list()

        if not isinstance(result, dict):
            # Invalid content
            ConfigBase.logger.error('Invalid apprise yaml structure specified')
            return list()

        # YAML Version
        version = result.get('version', 1)
        if version != 1:
            # Invalid syntax
            ConfigBase.logger.error(
                'Invalid apprise yaml version specified {}.'.format(version))
            return list()

        #
        # global asset object
        #
        asset = asset if isinstance(asset, AppriseAsset) else AppriseAsset()
        tokens = result.get('asset', None)
        if tokens and isinstance(tokens, dict):
            for k, v in tokens.items():

                if k.startswith('_') or k.endswith('_'):
                    # Entries are considered reserved if they start or end
                    # with an underscore
                    ConfigBase.logger.warning(
                        'Ignored asset key "{}".'.format(k))
                    continue

                if not (hasattr(asset, k) and
                        isinstance(getattr(asset, k), six.string_types)):
                    # We can't set a function or non-string set value
                    ConfigBase.logger.warning(
                        'Invalid asset key "{}".'.format(k))
                    continue

                if v is None:
                    # Convert to an empty string
                    v = ''

                if not isinstance(v, six.string_types):
                    # we must set strings with a string
                    ConfigBase.logger.warning(
                        'Invalid asset value to "{}".'.format(k))
                    continue

                # Set our asset object with the new value
                setattr(asset, k, v.strip())

        #
        # global tag root directive
        #
        global_tags = set()

        tags = result.get('tag', None)
        if tags and isinstance(tags, (list, tuple, six.string_types)):
            # Store any preset tags
            global_tags = set(parse_list(tags))

        #
        # urls root directive
        #
        urls = result.get('urls', None)
        if not isinstance(urls, (list, tuple)):
            # Unsupported
            ConfigBase.logger.error(
                'Missing "urls" directive in apprise yaml.')
            return list()

        # Iterate over each URL
        for no, url in enumerate(urls):

            # Our results object is what we use to instantiate our object if
            # we can. Reset it to None on each iteration
            results = list()

            if isinstance(url, six.string_types):
                # We're just a simple URL string

                # swap hash (#) tag values with their html version
                _url = url.replace('/#', '/%23')

                # Attempt to acquire the schema at the very least to allow our
                # plugins to determine if they can make a better
                # interpretation of a URL geared for them
                schema = GET_SCHEMA_RE.match(_url)
                if schema is None:
                    ConfigBase.logger.warning(
                        'Unsupported schema in urls entry #{}'.format(no))
                    continue

                # Ensure our schema is always in lower case
                schema = schema.group('schema').lower()

                # Some basic validation
                if schema not in plugins.SCHEMA_MAP:
                    ConfigBase.logger.warning(
                        'Unsupported schema {} in urls entry #{}'.format(
                            schema, no))
                    continue

                # Parse our url details of the server object as dictionary
                # containing all of the information parsed from our URL
                _results = plugins.SCHEMA_MAP[schema].parse_url(_url)
                if _results is None:
                    ConfigBase.logger.warning(
                        'Unparseable {} based url; entry #{}'.format(
                            schema, no))
                    continue

                # add our results to our global set
                results.append(_results)

            elif isinstance(url, dict):
                # We are a url string with additional unescaped options
                if six.PY2:
                    _url, tokens = next(url.iteritems())
                else:  # six.PY3
                    _url, tokens = next(iter(url.items()))

                # swap hash (#) tag values with their html version
                _url = _url.replace('/#', '/%23')

                # Get our schema
                schema = GET_SCHEMA_RE.match(_url)
                if schema is None:
                    ConfigBase.logger.warning(
                        'Unsupported schema in urls entry #{}'.format(no))
                    continue

                # Ensure our schema is always in lower case
                schema = schema.group('schema').lower()

                # Some basic validation
                if schema not in plugins.SCHEMA_MAP:
                    ConfigBase.logger.warning(
                        'Unsupported schema {} in urls entry #{}'.format(
                            schema, no))
                    continue

                # Parse our url details of the server object as dictionary
                # containing all of the information parsed from our URL
                _results = plugins.SCHEMA_MAP[schema].parse_url(_url)
                if _results is None:
                    # Setup dictionary
                    _results = {
                        # Minimum requirements
                        'schema': schema,
                    }

                if tokens is not None:
                    # populate and/or override any results populated by
                    # parse_url()
                    for entries in tokens:
                        # Copy ourselves a template of our parsed URL as a base
                        # to work with
                        r = _results.copy()

                        # We are a url string with additional unescaped options
                        if isinstance(entries, dict):
                            if six.PY2:
                                _url, tokens = next(url.iteritems())
                            else:  # six.PY3
                                _url, tokens = next(iter(url.items()))

                            # Tags you just can't over-ride
                            if 'schema' in entries:
                                del entries['schema']

                            # Extend our dictionary with our new entries
                            r.update(entries)

                            # add our results to our global set
                            results.append(r)

                else:
                    # add our results to our global set
                    results.append(_results)

            else:
                # Unsupported
                ConfigBase.logger.warning(
                    'Unsupported apprise yaml entry #{}'.format(no))
                continue

            # Track our entries
            entry = 0

            while len(results):
                # Increment our entry count
                entry += 1

                # Grab our first item
                _results = results.pop(0)

                # tag is a special keyword that is managed by apprise object.
                # The below ensures our tags are set correctly
                if 'tag' in _results:
                    # Tidy our list up
                    _results['tag'] = \
                        set(parse_list(_results['tag'])) | global_tags

                else:
                    # Just use the global settings
                    _results['tag'] = global_tags

                ConfigBase.logger.trace(
                    'URL no.{} {} unpacked as:{}{}'
                    .format(os.linesep, no, url, os.linesep.join(
                        ['{}="{}"'.format(k, a)
                         for k, a in _results.items()])))

                # Prepare our Asset Object
                _results['asset'] = asset

                try:
                    # Attempt to create an instance of our plugin using the
                    # parsed URL information
                    plugin = plugins.SCHEMA_MAP[_results['schema']](**_results)

                    # Create log entry of loaded URL
                    ConfigBase.logger.debug(
                        'Loaded URL: {}'.format(plugin.url()))

                except Exception:
                    # the arguments are invalid or can not be used.
                    ConfigBase.logger.warning(
                        'Could not load apprise yaml entry #{}, item #{}'
                        .format(no, entry))
                    continue

                # if we reach here, we successfully loaded our data
                response.append(plugin)

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
