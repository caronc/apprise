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

import six

from . import config
from . import ConfigBase
from . import URLBase
from .AppriseAsset import AppriseAsset

from .utils import GET_SCHEMA_RE
from .utils import parse_list
from .utils import is_exclusive_match
from .logger import logger


class AppriseConfig(object):
    """
    Our Apprise Configuration File Manager

        - Supports a list of URLs defined one after another (text format)
        - Supports a destinct YAML configuration format

    """

    def __init__(self, paths=None, asset=None, cache=True, **kwargs):
        """
        Loads all of the paths specified (if any).

        The path can either be a single string identifying one explicit
        location, otherwise you can pass in a series of locations to scan
        via a list.

        If no path is specified then a default list is used.

        If cache is set to True, then after the data is loaded, it's cached
        within this object so it isn't retrieved again later.
        """

        # Initialize a server list of URLs
        self.configs = list()

        # Prepare our Asset Object
        self.asset = \
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        if paths is not None:
            # Store our path(s)
            self.add(paths)

        return

    def add(self, configs, asset=None, tag=None):
        """
        Adds one or more config URLs into our list.

        You can override the global asset if you wish by including it with the
        config(s) that you add.

        """

        # Initialize our return status
        return_status = True

        if isinstance(asset, AppriseAsset):
            # prepare default asset
            asset = self.asset

        if isinstance(configs, ConfigBase):
            # Go ahead and just add our configuration into our list
            self.configs.append(configs)
            return True

        elif isinstance(configs, six.string_types):
            # Save our path
            configs = (configs, )

        elif not isinstance(configs, (tuple, set, list)):
            logger.error(
                'An invalid configuration path (type={}) was '
                'specified.'.format(type(configs)))
            return False

        # Iterate over our
        for _config in configs:

            if isinstance(_config, ConfigBase):
                # Go ahead and just add our configuration into our list
                self.configs.append(_config)
                continue

            elif not isinstance(_config, six.string_types):
                logger.warning(
                    "An invalid configuration (type={}) was specified.".format(
                        type(_config)))
                return_status = False
                continue

            # Instantiate ourselves an object, this function throws or
            # returns None if it fails
            instance = AppriseConfig.instantiate(_config, asset=asset, tag=tag)
            if not isinstance(instance, ConfigBase):
                return_status = False
                continue

            # Add our initialized plugin to our server listings
            self.configs.append(instance)

        # Return our status
        return return_status

    def servers(self, tag=None, cache=True):
        """
        Returns all of our servers dynamically build based on parsed
        configuration.

        If a tag is specified, it applies to the configuration sources
        themselves and not the notification services inside them.

        This is for filtering the configuration files polled for
        results.

        """
        # Build our tag setup
        #   - top level entries are treated as an 'or'
        #   - second level (or more) entries are treated as 'and'
        #
        #   examples:
        #     tag="tagA, tagB"                = tagA or tagB
        #     tag=['tagA', 'tagB']            = tagA or tagB
        #     tag=[('tagA', 'tagC'), 'tagB']  = (tagA and tagC) or tagB
        #     tag=[('tagB', 'tagC')]          = tagB and tagC

        response = list()

        for entry in self.configs:

            # Apply our tag matching based on our defined logic
            if tag is not None and not is_exclusive_match(
                    logic=tag, data=entry.tags):
                continue

            # Build ourselves a list of services dynamically and return the
            # as a list
            response.extend(entry.servers(cache=cache))

        return response

    @staticmethod
    def instantiate(url, asset=None, tag=None, suppress_exceptions=True):
        """
        Returns the instance of a instantiated configuration plugin based on
        the provided Server URL.  If the url fails to be parsed, then None
        is returned.

        """
        # Attempt to acquire the schema at the very least to allow our
        # configuration based urls.
        schema = GET_SCHEMA_RE.match(url)
        if schema is None:
            # Plan B is to assume we're dealing with a file
            schema = config.ConfigFile.protocol
            url = '{}://{}'.format(schema, URLBase.quote(url))

        else:
            # Ensure our schema is always in lower case
            schema = schema.group('schema').lower()

            # Some basic validation
            if schema not in config.SCHEMA_MAP:
                logger.debug('Unsupported schema {}.'.format(schema))
                return None

        # Parse our url details of the server object as dictionary containing
        # all of the information parsed from our URL
        results = config.SCHEMA_MAP[schema].parse_url(url)

        if not results:
            # Failed to parse the server URL
            logger.debug('Unparseable URL {}.'.format(url))
            return None

        # Build a list of tags to associate with the newly added notifications
        results['tag'] = set(parse_list(tag))

        # Prepare our Asset Object
        results['asset'] = \
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        if suppress_exceptions:
            try:
                # Attempt to create an instance of our plugin using the parsed
                # URL information
                cfg_plugin = config.SCHEMA_MAP[results['schema']](**results)

            except Exception:
                # the arguments are invalid or can not be used.
                logger.debug('Could not load URL: %s' % url)
                return None

        else:
            # Attempt to create an instance of our plugin using the parsed
            # URL information but don't wrap it in a try catch
            cfg_plugin = config.SCHEMA_MAP[results['schema']](**results)

        return cfg_plugin

    def clear(self):
        """
        Empties our configuration list

        """
        self.configs[:] = []

    def server_pop(self, index):
        """
        Removes an indexed Apprise Notification from the servers
        """

        # Tracking variables
        prev_offset = -1
        offset = prev_offset

        for entry in self.configs:
            servers = entry.servers(cache=True)
            if len(servers) > 0:
                # Acquire a new maximum offset to work with
                offset = prev_offset + len(servers)

                if offset >= index:
                    # we can pop an notification from our config stack
                    return entry.pop(index if prev_offset == -1
                                     else (index - prev_offset - 1))

                # Update our old offset
                prev_offset = offset

        # If we reach here, then we indexed out of range
        raise IndexError('list index out of range')

    def pop(self, index):
        """
        Removes an indexed Apprise Configuration from the stack and
        returns it.
        """
        # Remove our entry
        return self.configs.pop(index)

    def __getitem__(self, index):
        """
        Returns the indexed config entry of a loaded apprise configuration
        """
        return self.configs[index]

    def __iter__(self):
        """
        Returns an iterator to our config list
        """
        return iter(self.configs)

    def __len__(self):
        """
        Returns the number of config entries loaded
        """
        return len(self.configs)
