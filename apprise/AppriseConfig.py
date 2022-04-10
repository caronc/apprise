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
from . import CONFIG_FORMATS
from . import URLBase
from .AppriseAsset import AppriseAsset

from .common import MATCH_ALL_TAG
from .common import MATCH_ALWAYS_TAG
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

    def __init__(self, paths=None, asset=None, cache=True, recursion=0,
                 insecure_includes=False, **kwargs):
        """
        Loads all of the paths specified (if any).

        The path can either be a single string identifying one explicit
        location, otherwise you can pass in a series of locations to scan
        via a list.

        If no path is specified then a default list is used.

        By default we cache our responses so that subsiquent calls does not
        cause the content to be retrieved again. Setting this to False does
        mean more then one call can be made to retrieve the (same) data.  This
        method can be somewhat inefficient if disabled and you're set up to
        make remote calls.  Only disable caching if you understand the
        consequences.

        You can alternatively set the cache value to an int identifying the
        number of seconds the previously retrieved can exist for before it
        should be considered expired.

        It's also worth nothing that the cache value is only set to elements
        that are not already of subclass ConfigBase()

        recursion defines how deep we recursively handle entries that use the
        `import` keyword. This keyword requires us to fetch more configuration
        from another source and add it to our existing compilation. If the
        file we remotely retrieve also has an `import` reference, we will only
        advance through it if recursion is set to 2 deep.  If set to zero
        it is off.  There is no limit to how high you set this value. It would
        be recommended to keep it low if you do intend to use it.

        insecure includes by default are disabled. When set to True, all
        Apprise Config files marked to be in STRICT mode are treated as being
        in ALWAYS mode.

        Take a file:// based configuration for example, only a file:// based
        configuration can import another file:// based one. because it is set
        to STRICT mode. If an http:// based configuration file attempted to
        import a file:// one it woul fail. However this import would be
        possible if insecure_includes is set to True.

        There are cases where a self hosting apprise developer may wish to load
        configuration from memory (in a string format) that contains import
        entries (even file:// based ones).  In these circumstances if you want
        these includes to be honored, this value must be set to True.
        """

        # Initialize a server list of URLs
        self.configs = list()

        # Prepare our Asset Object
        self.asset = \
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        # Set our cache flag
        self.cache = cache

        # Initialize our recursion value
        self.recursion = recursion

        # Initialize our insecure_includes flag
        self.insecure_includes = insecure_includes

        if paths is not None:
            # Store our path(s)
            self.add(paths)

        return

    def add(self, configs, asset=None, tag=None, cache=True, recursion=None,
            insecure_includes=None):
        """
        Adds one or more config URLs into our list.

        You can override the global asset if you wish by including it with the
        config(s) that you add.

        By default we cache our responses so that subsiquent calls does not
        cause the content to be retrieved again. Setting this to False does
        mean more then one call can be made to retrieve the (same) data.  This
        method can be somewhat inefficient if disabled and you're set up to
        make remote calls.  Only disable caching if you understand the
        consequences.

        You can alternatively set the cache value to an int identifying the
        number of seconds the previously retrieved can exist for before it
        should be considered expired.

        It's also worth nothing that the cache value is only set to elements
        that are not already of subclass ConfigBase()

        Optionally override the default recursion value.

        Optionally override the insecure_includes flag.
        if insecure_includes is set to True then all plugins that are
        set to a STRICT mode will be a treated as ALWAYS.
        """

        # Initialize our return status
        return_status = True

        # Initialize our default cache value
        cache = cache if cache is not None else self.cache

        # Initialize our default recursion value
        recursion = recursion if recursion is not None else self.recursion

        # Initialize our default insecure_includes value
        insecure_includes = \
            insecure_includes if insecure_includes is not None \
            else self.insecure_includes

        if asset is None:
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

        # Iterate over our configuration
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

            logger.debug("Loading configuration: {}".format(_config))

            # Instantiate ourselves an object, this function throws or
            # returns None if it fails
            instance = AppriseConfig.instantiate(
                _config, asset=asset, tag=tag, cache=cache,
                recursion=recursion, insecure_includes=insecure_includes)
            if not isinstance(instance, ConfigBase):
                return_status = False
                continue

            # Add our initialized plugin to our server listings
            self.configs.append(instance)

        # Return our status
        return return_status

    def add_config(self, content, asset=None, tag=None, format=None,
                   recursion=None, insecure_includes=None):
        """
        Adds one configuration file in it's raw format. Content gets loaded as
        a memory based object and only exists for the life of this
        AppriseConfig object it was loaded into.

        If you know the format ('yaml' or 'text') you can specify
        it for slightly less overhead during this call.  Otherwise the
        configuration is auto-detected.

        Optionally override the default recursion value.

        Optionally override the insecure_includes flag.
        if insecure_includes is set to True then all plugins that are
        set to a STRICT mode will be a treated as ALWAYS.
        """

        # Initialize our default recursion value
        recursion = recursion if recursion is not None else self.recursion

        # Initialize our default insecure_includes value
        insecure_includes = \
            insecure_includes if insecure_includes is not None \
            else self.insecure_includes

        if asset is None:
            # prepare default asset
            asset = self.asset

        if not isinstance(content, six.string_types):
            logger.warning(
                "An invalid configuration (type={}) was specified.".format(
                    type(content)))
            return False

        logger.debug("Loading raw configuration: {}".format(content))

        # Create ourselves a ConfigMemory Object to store our configuration
        instance = config.ConfigMemory(
            content=content, format=format, asset=asset, tag=tag,
            recursion=recursion, insecure_includes=insecure_includes)

        if instance.config_format not in CONFIG_FORMATS:
            logger.warning(
                "The format of the configuration could not be deteced.")
            return False

        # Add our initialized plugin to our server listings
        self.configs.append(instance)

        # Return our status
        return True

    def servers(self, tag=MATCH_ALL_TAG, match_always=True, *args, **kwargs):
        """
        Returns all of our servers dynamically build based on parsed
        configuration.

        If a tag is specified, it applies to the configuration sources
        themselves and not the notification services inside them.

        This is for filtering the configuration files polled for
        results.

        If the anytag is set, then any notification that is found
        set with that tag are included in the response.

        """

        # A match_always flag allows us to pick up on our 'any' keyword
        # and notify these services under all circumstances
        match_always = MATCH_ALWAYS_TAG if match_always else None

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
            if is_exclusive_match(
                    logic=tag, data=entry.tags, match_all=MATCH_ALL_TAG,
                    match_always=match_always):
                # Build ourselves a list of services dynamically and return the
                # as a list
                response.extend(entry.servers())

        return response

    @staticmethod
    def instantiate(url, asset=None, tag=None, cache=None,
                    recursion=0, insecure_includes=False,
                    suppress_exceptions=True):
        """
        Returns the instance of a instantiated configuration plugin based on
        the provided Config URL.  If the url fails to be parsed, then None
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
                logger.warning('Unsupported schema {}.'.format(schema))
                return None

        # Parse our url details of the server object as dictionary containing
        # all of the information parsed from our URL
        results = config.SCHEMA_MAP[schema].parse_url(url)

        if not results:
            # Failed to parse the server URL
            logger.warning('Unparseable URL {}.'.format(url))
            return None

        # Build a list of tags to associate with the newly added notifications
        results['tag'] = set(parse_list(tag))

        # Prepare our Asset Object
        results['asset'] = \
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        if cache is not None:
            # Force an over-ride of the cache value to what we have specified
            results['cache'] = cache

        # Recursion can never be parsed from the URL
        results['recursion'] = recursion

        # Insecure includes flag can never be parsed from the URL
        results['insecure_includes'] = insecure_includes

        if suppress_exceptions:
            try:
                # Attempt to create an instance of our plugin using the parsed
                # URL information
                cfg_plugin = config.SCHEMA_MAP[results['schema']](**results)

            except Exception:
                # the arguments are invalid or can not be used.
                logger.warning('Could not load URL: %s' % url)
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

    def pop(self, index=-1):
        """
        Removes an indexed Apprise Configuration from the stack and returns it.

        By default, the last element is removed from the list
        """
        # Remove our entry
        return self.configs.pop(index)

    def __getitem__(self, index):
        """
        Returns the indexed config entry of a loaded apprise configuration
        """
        return self.configs[index]

    def __bool__(self):
        """
        Allows the Apprise object to be wrapped in an Python 3.x based 'if
        statement'.  True is returned if at least one service has been loaded.
        """
        return True if self.configs else False

    def __nonzero__(self):
        """
        Allows the Apprise object to be wrapped in an Python 2.x based 'if
        statement'.  True is returned if at least one service has been loaded.
        """
        return True if self.configs else False

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
