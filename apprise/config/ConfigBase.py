# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
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
import yaml
import time

from .. import plugins
from .. import common
from ..AppriseAsset import AppriseAsset
from ..URLBase import URLBase
from ..utils import GET_SCHEMA_RE
from ..utils import parse_list
from ..utils import parse_bool
from ..utils import parse_urls
from ..utils import cwe312_url

# Test whether token is valid or not
VALID_TOKEN = re.compile(
    r'(?P<token>[a-z0-9][a-z0-9_]+)', re.I)


class ConfigBase(URLBase):
    """
    This is the base class for all supported configuration sources
    """

    # The Default Encoding to use if not otherwise detected
    encoding = 'utf-8'

    # The default expected configuration format unless otherwise
    # detected by the sub-modules
    default_config_format = common.ConfigFormat.TEXT

    # This is only set if the user overrides the config format on the URL
    # this should always initialize itself as None
    config_format = None

    # Don't read any more of this amount of data into memory as there is no
    # reason we should be reading in more. This is more of a safe guard then
    # anything else. 128KB (131072B)
    max_buffer_size = 131072

    # By default all configuration is not includable using the 'include'
    # line found in configuration files.
    allow_cross_includes = common.ContentIncludeMode.NEVER

    # the config path manages the handling of relative include
    config_path = os.getcwd()

    def __init__(self, cache=True, recursion=0, insecure_includes=False,
                 **kwargs):
        """
        Initialize some general logging and common server arguments that will
        keep things consistent when working with the configurations that
        inherit this class.

        By default we cache our responses so that subsiquent calls does not
        cause the content to be retrieved again.  For local file references
        this makes no difference at all.  But for remote content, this does
        mean more then one call can be made to retrieve the (same) data.  This
        method can be somewhat inefficient if disabled.  Only disable caching
        if you understand the consequences.

        You can alternatively set the cache value to an int identifying the
        number of seconds the previously retrieved can exist for before it
        should be considered expired.

        recursion defines how deep we recursively handle entries that use the
        `include` keyword. This keyword requires us to fetch more configuration
        from another source and add it to our existing compilation. If the
        file we remotely retrieve also has an `include` reference, we will only
        advance through it if recursion is set to 2 deep.  If set to zero
        it is off.  There is no limit to how high you set this value. It would
        be recommended to keep it low if you do intend to use it.

        insecure_include by default are disabled. When set to True, all
        Apprise Config files marked to be in STRICT mode are treated as being
        in ALWAYS mode.

        Take a file:// based configuration for example, only a file:// based
        configuration can include another file:// based one. because it is set
        to STRICT mode. If an http:// based configuration file attempted to
        include a file:// one it woul fail. However this include would be
        possible if insecure_includes is set to True.

        There are cases where a self hosting apprise developer may wish to load
        configuration from memory (in a string format) that contains 'include'
        entries (even file:// based ones).  In these circumstances if you want
        these 'include' entries to be honored, this value must be set to True.
        """

        super().__init__(**kwargs)

        # Tracks the time the content was last retrieved on.  This place a role
        # for cases where we are not caching our response and are required to
        # re-retrieve our settings.
        self._cached_time = None

        # Tracks previously loaded content for speed
        self._cached_servers = None

        # Initialize our recursion value
        self.recursion = recursion

        # Initialize our insecure_includes flag
        self.insecure_includes = insecure_includes

        if 'encoding' in kwargs:
            # Store the encoding
            self.encoding = kwargs.get('encoding')

        if 'format' in kwargs \
                and isinstance(kwargs['format'], str):
            # Store the enforced config format
            self.config_format = kwargs.get('format').lower()

            if self.config_format not in common.CONFIG_FORMATS:
                # Simple error checking
                err = 'An invalid config format ({}) was specified.'.format(
                    self.config_format)
                self.logger.warning(err)
                raise TypeError(err)

        # Set our cache flag; it can be True or a (positive) integer
        try:
            self.cache = cache if isinstance(cache, bool) else int(cache)
            if self.cache < 0:
                err = 'A negative cache value ({}) was specified.'.format(
                    cache)
                self.logger.warning(err)
                raise TypeError(err)

        except (ValueError, TypeError):
            err = 'An invalid cache value ({}) was specified.'.format(cache)
            self.logger.warning(err)
            raise TypeError(err)

        return

    def servers(self, asset=None, **kwargs):
        """
        Performs reads loaded configuration and returns all of the services
        that could be parsed and loaded.

        """

        if not self.expired():
            # We already have cached results to return; use them
            return self._cached_servers

        # Our cached response object
        self._cached_servers = list()

        # read() causes the child class to do whatever it takes for the
        # config plugin to load the data source and return unparsed content
        # None is returned if there was an error or simply no data
        content = self.read(**kwargs)
        if not isinstance(content, str):
            # Set the time our content was cached at
            self._cached_time = time.time()

            # Nothing more to do; return our empty cache list
            return self._cached_servers

        # Our Configuration format uses a default if one wasn't one detected
        # or enfored.
        config_format = \
            self.default_config_format \
            if self.config_format is None else self.config_format

        # Dynamically load our parse_ function based on our config format
        fn = getattr(ConfigBase, 'config_parse_{}'.format(config_format))

        # Initialize our asset object
        asset = asset if isinstance(asset, AppriseAsset) else self.asset

        # Execute our config parse function which always returns a tuple
        # of our servers and our configuration
        servers, configs = fn(content=content, asset=asset)
        self._cached_servers.extend(servers)

        # Configuration files were detected; recursively populate them
        # If we have been configured to do so
        for url in configs:

            if self.recursion > 0:
                # Attempt to acquire the schema at the very least to allow
                # our configuration based urls.
                schema = GET_SCHEMA_RE.match(url)
                if schema is None:
                    # Plan B is to assume we're dealing with a file
                    schema = 'file'
                    if not os.path.isabs(url):
                        # We're dealing with a relative path; prepend
                        # our current config path
                        url = os.path.join(self.config_path, url)

                    url = '{}://{}'.format(schema, URLBase.quote(url))

                else:
                    # Ensure our schema is always in lower case
                    schema = schema.group('schema').lower()

                    # Some basic validation
                    if schema not in common.CONFIG_SCHEMA_MAP:
                        ConfigBase.logger.warning(
                            'Unsupported include schema {}.'.format(schema))
                        continue

                # CWE-312 (Secure Logging) Handling
                loggable_url = url if not asset.secure_logging \
                    else cwe312_url(url)

                # Parse our url details of the server object as dictionary
                # containing all of the information parsed from our URL
                results = common.CONFIG_SCHEMA_MAP[schema].parse_url(url)
                if not results:
                    # Failed to parse the server URL
                    self.logger.warning(
                        'Unparseable include URL {}'.format(loggable_url))
                    continue

                # Handle cross inclusion based on allow_cross_includes rules
                if (common.CONFIG_SCHEMA_MAP[schema].allow_cross_includes ==
                        common.ContentIncludeMode.STRICT
                        and schema not in self.schemas()
                        and not self.insecure_includes) or \
                        common.CONFIG_SCHEMA_MAP[schema] \
                        .allow_cross_includes == \
                        common.ContentIncludeMode.NEVER:

                    # Prevent the loading if insecure base protocols
                    ConfigBase.logger.warning(
                        'Including {}:// based configuration is prohibited. '
                        'Ignoring URL {}'.format(schema, loggable_url))
                    continue

                # Prepare our Asset Object
                results['asset'] = asset

                # No cache is required because we're just lumping this in
                # and associating it with the cache value we've already
                # declared (prior to our recursion)
                results['cache'] = False

                # Recursion can never be parsed from the URL; we decrement
                # it one level
                results['recursion'] = self.recursion - 1

                # Insecure Includes flag can never be parsed from the URL
                results['insecure_includes'] = self.insecure_includes

                try:
                    # Attempt to create an instance of our plugin using the
                    # parsed URL information
                    cfg_plugin = \
                        common.CONFIG_SCHEMA_MAP[results['schema']](**results)

                except Exception as e:
                    # the arguments are invalid or can not be used.
                    self.logger.warning(
                        'Could not load include URL: {}'.format(loggable_url))
                    self.logger.debug('Loading Exception: {}'.format(str(e)))
                    continue

                # if we reach here, we can now add this servers found
                # in this configuration file to our list
                self._cached_servers.extend(
                    cfg_plugin.servers(asset=asset))

                # We no longer need our configuration object
                del cfg_plugin

            else:
                # CWE-312 (Secure Logging) Handling
                loggable_url = url if not asset.secure_logging \
                    else cwe312_url(url)

                self.logger.debug(
                    'Recursion limit reached; ignoring Include URL: %s',
                    loggable_url)

        if self._cached_servers:
            self.logger.info(
                'Loaded {} entries from {}'.format(
                    len(self._cached_servers),
                    self.url(privacy=asset.secure_logging)))
        else:
            self.logger.warning(
                'Failed to load Apprise configuration from {}'.format(
                    self.url(privacy=asset.secure_logging)))

        # Set the time our content was cached at
        self._cached_time = time.time()

        return self._cached_servers

    def read(self):
        """
        This object should be implimented by the child classes

        """
        return None

    def expired(self):
        """
        Simply returns True if the configuration should be considered
        as expired or False if content should be retrieved.
        """
        if isinstance(self._cached_servers, list) and self.cache:
            # We have enough reason to look further into our cached content
            # and verify it has not expired.
            if self.cache is True:
                # we have not expired, return False
                return False

            # Verify our cache time to determine whether we will get our
            # content again.
            age_in_sec = time.time() - self._cached_time
            if age_in_sec <= self.cache:
                # We have not expired; return False
                return False

        # If we reach here our configuration should be considered
        # missing and/or expired.
        return True

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
            if results['format'] not in common.CONFIG_FORMATS:
                URLBase.logger.warning(
                    'Unsupported format specified {}'.format(
                        results['format']))
                del results['format']

        # Defines the encoding of the payload
        if 'encoding' in results['qsd']:
            results['encoding'] = results['qsd'].get('encoding')

        # Our cache value
        if 'cache' in results['qsd']:
            # First try to get it's integer value
            try:
                results['cache'] = int(results['qsd']['cache'])

            except (ValueError, TypeError):
                # No problem, it just isn't an integer; now treat it as a bool
                # instead:
                results['cache'] = parse_bool(results['qsd']['cache'])

        return results

    @staticmethod
    def detect_config_format(content, **kwargs):
        """
        Takes the specified content and attempts to detect the format type

        The function returns the actual format type if detected, otherwise
        it returns None
        """

        # Detect Format Logic:
        #  - A pound/hashtag (#) is alawys a comment character so we skip over
        #     lines matched here.
        #  - Detection begins on the first non-comment and non blank line
        #     matched.
        #  - If we find a string followed by a colon, we know we're dealing
        #     with a YAML file.
        #  - If we find a string that starts with a URL, or our tag
        #     definitions (accepting commas) followed by an equal sign we know
        #     we're dealing with a TEXT format.

        # Define what a valid line should look like
        valid_line_re = re.compile(
            r'^\s*(?P<line>([;#]+(?P<comment>.*))|'
            r'(?P<text>((?P<tag>[ \t,a-z0-9_-]+)=)?[a-z0-9]+://.*)|'
            r'((?P<yaml>[a-z0-9]+):.*))?$', re.I)

        try:
            # split our content up to read line by line
            content = re.split(r'\r*\n', content)

        except TypeError:
            # content was not expected string type
            ConfigBase.logger.error(
                'Invalid Apprise configuration specified.')
            return None

        # By default set our return value to None since we don't know
        # what the format is yet
        config_format = None

        # iterate over each line of the file to attempt to detect it
        # stop the moment a the type has been determined
        for line, entry in enumerate(content, start=1):

            result = valid_line_re.match(entry)
            if not result:
                # Invalid syntax
                ConfigBase.logger.error(
                    'Undetectable Apprise configuration found '
                    'based on line {}.'.format(line))
                # Take an early exit
                return None

            # Attempt to detect configuration
            if result.group('yaml'):
                config_format = common.ConfigFormat.YAML
                ConfigBase.logger.debug(
                    'Detected YAML configuration '
                    'based on line {}.'.format(line))
                break

            elif result.group('text'):
                config_format = common.ConfigFormat.TEXT
                ConfigBase.logger.debug(
                    'Detected TEXT configuration '
                    'based on line {}.'.format(line))
                break

            # If we reach here, we have a comment entry
            # Adjust default format to TEXT
            config_format = common.ConfigFormat.TEXT

        return config_format

    @staticmethod
    def config_parse(content, asset=None, config_format=None, **kwargs):
        """
        Takes the specified config content and loads it based on the specified
        config_format. If a format isn't specified, then it is auto detected.

        """

        if config_format is None:
            # Detect the format
            config_format = ConfigBase.detect_config_format(content)

            if not config_format:
                # We couldn't detect configuration
                ConfigBase.logger.error('Could not detect configuration')
                return (list(), list())

        if config_format not in common.CONFIG_FORMATS:
            # Invalid configuration type specified
            ConfigBase.logger.error(
                'An invalid configuration format ({}) was specified'.format(
                    config_format))
            return (list(), list())

        # Dynamically load our parse_ function based on our config format
        fn = getattr(ConfigBase, 'config_parse_{}'.format(config_format))

        # Execute our config parse function which always returns a list
        return fn(content=content, asset=asset)

    @staticmethod
    def config_parse_text(content, asset=None):
        """
        Parse the specified content as though it were a simple text file only
        containing a list of URLs.

        Return a tuple that looks like (servers, configs) where:
          - servers contains a list of loaded notification plugins
          - configs contains a list of additional configuration files
            referenced.

        You may also optionally associate an asset with the notification.

        The file syntax is:

            #
            # pound/hashtag allow for line comments
            #
            # One or more tags can be idenified using comma's (,) to separate
            # them.
            <Tag(s)>=<URL>

            # Or you can use this format (no tags associated)
            <URL>

            # you can also use the keyword 'include' and identify a
            # configuration location (like this file) which will be included
            # as additional configuration entries when loaded.
            include <ConfigURL>

        """
        # A list of loaded Notification Services
        servers = list()

        # A list of additional configuration files referenced using
        # the include keyword
        configs = list()

        # Prepare our Asset Object
        asset = asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        # Define what a valid line should look like
        valid_line_re = re.compile(
            r'^\s*(?P<line>([;#]+(?P<comment>.*))|'
            r'(\s*(?P<tags>[^=]+)=|=)?\s*'
            r'(?P<url>[a-z0-9]{2,9}://.*)|'
            r'include\s+(?P<config>.+))?\s*$', re.I)

        try:
            # split our content up to read line by line
            content = re.split(r'\r*\n', content)

        except TypeError:
            # content was not expected string type
            ConfigBase.logger.error(
                'Invalid Apprise TEXT based configuration specified.')
            return (list(), list())

        for line, entry in enumerate(content, start=1):
            result = valid_line_re.match(entry)
            if not result:
                # Invalid syntax
                ConfigBase.logger.error(
                    'Invalid Apprise TEXT configuration format found '
                    '{} on line {}.'.format(entry, line))

                # Assume this is a file we shouldn't be parsing. It's owner
                # can read the error printed to screen and take action
                # otherwise.
                return (list(), list())

            url, config = result.group('url'), result.group('config')
            if not (url or config):
                # Comment/empty line; do nothing
                continue

            if config:
                # CWE-312 (Secure Logging) Handling
                loggable_url = config if not asset.secure_logging \
                    else cwe312_url(config)

                ConfigBase.logger.debug(
                    'Include URL: {}'.format(loggable_url))

                # Store our include line
                configs.append(config.strip())
                continue

            # CWE-312 (Secure Logging) Handling
            loggable_url = url if not asset.secure_logging \
                else cwe312_url(url)

            # Acquire our url tokens
            results = plugins.url_to_dict(
                url, secure_logging=asset.secure_logging)
            if results is None:
                # Failed to parse the server URL
                ConfigBase.logger.warning(
                    'Unparseable URL {} on line {}.'.format(
                        loggable_url, line))
                continue

            # Build a list of tags to associate with the newly added
            # notifications if any were set
            results['tag'] = set(parse_list(result.group('tags')))

            # Set our Asset Object
            results['asset'] = asset

            try:
                # Attempt to create an instance of our plugin using the
                # parsed URL information
                plugin = common.NOTIFY_SCHEMA_MAP[results['schema']](**results)

                # Create log entry of loaded URL
                ConfigBase.logger.debug(
                    'Loaded URL: %s', plugin.url(privacy=asset.secure_logging))

            except Exception as e:
                # the arguments are invalid or can not be used.
                ConfigBase.logger.warning(
                    'Could not load URL {} on line {}.'.format(
                        loggable_url, line))
                ConfigBase.logger.debug('Loading Exception: %s' % str(e))
                continue

            # if we reach here, we successfully loaded our data
            servers.append(plugin)

        # Return what was loaded
        return (servers, configs)

    @staticmethod
    def config_parse_yaml(content, asset=None):
        """
        Parse the specified content as though it were a yaml file
        specifically formatted for Apprise.

        Return a tuple that looks like (servers, configs) where:
          - servers contains a list of loaded notification plugins
          - configs contains a list of additional configuration files
            referenced.

        You may optionally associate an asset with the notification.

        """

        # A list of loaded Notification Services
        servers = list()

        # A list of additional configuration files referenced using
        # the include keyword
        configs = list()

        try:
            # Load our data (safely)
            result = yaml.load(content, Loader=yaml.SafeLoader)

        except (AttributeError,
                yaml.parser.ParserError,
                yaml.error.MarkedYAMLError) as e:
            # Invalid content
            ConfigBase.logger.error(
                'Invalid Apprise YAML data specified.')
            ConfigBase.logger.debug(
                'YAML Exception:{}{}'.format(os.linesep, e))
            return (list(), list())

        if not isinstance(result, dict):
            # Invalid content
            ConfigBase.logger.error(
                'Invalid Apprise YAML based configuration specified.')
            return (list(), list())

        # YAML Version
        version = result.get('version', 1)
        if version != 1:
            # Invalid syntax
            ConfigBase.logger.error(
                'Invalid Apprise YAML version specified {}.'.format(version))
            return (list(), list())

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
                        isinstance(getattr(asset, k),
                                   (bool, str))):

                    # We can't set a function or non-string set value
                    ConfigBase.logger.warning(
                        'Invalid asset key "{}".'.format(k))
                    continue

                if v is None:
                    # Convert to an empty string
                    v = ''

                if (isinstance(v, (bool, str))
                        and isinstance(getattr(asset, k), bool)):

                    # If the object in the Asset is a boolean, then
                    # we want to convert the specified string to
                    # match that.
                    setattr(asset, k, parse_bool(v))

                elif isinstance(v, str):
                    # Set our asset object with the new value
                    setattr(asset, k, v.strip())

                else:
                    # we must set strings with a string
                    ConfigBase.logger.warning(
                        'Invalid asset value to "{}".'.format(k))
                    continue
        #
        # global tag root directive
        #
        global_tags = set()

        tags = result.get('tag', None)
        if tags and isinstance(tags, (list, tuple, str)):
            # Store any preset tags
            global_tags = set(parse_list(tags))

        #
        # include root directive
        #
        includes = result.get('include', None)
        if isinstance(includes, str):
            # Support a single inline string or multiple ones separated by a
            # comma and/or space
            includes = parse_urls(includes)

        elif not isinstance(includes, (list, tuple)):
            # Not a problem; we simply have no includes
            includes = list()

        # Iterate over each config URL
        for no, url in enumerate(includes):

            if isinstance(url, str):
                # Support a single inline string or multiple ones separated by
                # a comma and/or space
                configs.extend(parse_urls(url))

            elif isinstance(url, dict):
                # Store the url and ignore arguments associated
                configs.extend(u for u in url.keys())

        #
        # urls root directive
        #
        urls = result.get('urls', None)
        if not isinstance(urls, (list, tuple)):
            # Not a problem; we simply have no urls
            urls = list()

        # Iterate over each URL
        for no, url in enumerate(urls):

            # Our results object is what we use to instantiate our object if
            # we can. Reset it to None on each iteration
            results = list()

            # CWE-312 (Secure Logging) Handling
            loggable_url = url if not asset.secure_logging \
                else cwe312_url(url)

            if isinstance(url, str):
                # We're just a simple URL string...
                schema = GET_SCHEMA_RE.match(url)
                if schema is None:
                    # Log invalid entries so that maintainer of config
                    # config file at least has something to take action
                    # with.
                    ConfigBase.logger.warning(
                        'Invalid URL {}, entry #{}'.format(
                            loggable_url, no + 1))
                    continue

                # We found a valid schema worthy of tracking; store it's
                # details:
                _results = plugins.url_to_dict(
                    url, secure_logging=asset.secure_logging)
                if _results is None:
                    ConfigBase.logger.warning(
                        'Unparseable URL {}, entry #{}'.format(
                            loggable_url, no + 1))
                    continue

                # add our results to our global set
                results.append(_results)

            elif isinstance(url, dict):
                # We are a url string with additional unescaped options. In
                # this case we want to iterate over all of our options so we
                # can at least tell the end user what entries were ignored
                # due to errors

                it = iter(url.items())

                # Track the URL to-load
                _url = None

                # Track last acquired schema
                schema = None
                for key, tokens in it:
                    # Test our schema
                    _schema = GET_SCHEMA_RE.match(key)
                    if _schema is None:
                        # Log invalid entries so that maintainer of config
                        # config file at least has something to take action
                        # with.
                        ConfigBase.logger.warning(
                            'Ignored entry {} found under urls, entry #{}'
                            .format(key, no + 1))
                        continue

                    # Store our schema
                    schema = _schema.group('schema').lower()

                    # Store our URL and Schema Regex
                    _url = key

                if _url is None:
                    # the loop above failed to match anything
                    ConfigBase.logger.warning(
                        'Unsupported URL, entry #{}'.format(no + 1))
                    continue

                _results = plugins.url_to_dict(
                    _url, secure_logging=asset.secure_logging)
                if _results is None:
                    # Setup dictionary
                    _results = {
                        # Minimum requirements
                        'schema': schema,
                    }

                if isinstance(tokens, (list, tuple, set)):
                    # populate and/or override any results populated by
                    # parse_url()
                    for entries in tokens:
                        # Copy ourselves a template of our parsed URL as a base
                        # to work with
                        r = _results.copy()

                        # We are a url string with additional unescaped options
                        if isinstance(entries, dict):
                            _url, tokens = next(iter(url.items()))

                            # Tags you just can't over-ride
                            if 'schema' in entries:
                                del entries['schema']

                            # support our special tokens (if they're present)
                            if schema in common.NOTIFY_SCHEMA_MAP:
                                entries = ConfigBase._special_token_handler(
                                    schema, entries)

                            # Extend our dictionary with our new entries
                            r.update(entries)

                            # add our results to our global set
                            results.append(r)

                elif isinstance(tokens, dict):
                    # support our special tokens (if they're present)
                    if schema in common.NOTIFY_SCHEMA_MAP:
                        tokens = ConfigBase._special_token_handler(
                            schema, tokens)

                    # Copy ourselves a template of our parsed URL as a base to
                    # work with
                    r = _results.copy()

                    # add our result set
                    r.update(tokens)

                    # add our results to our global set
                    results.append(r)

                else:
                    # add our results to our global set
                    results.append(_results)

            else:
                # Unsupported
                ConfigBase.logger.warning(
                    'Unsupported Apprise YAML entry #{}'.format(no + 1))
                continue

            # Track our entries
            entry = 0

            while len(results):
                # Increment our entry count
                entry += 1

                # Grab our first item
                _results = results.pop(0)

                if _results['schema'] not in common.NOTIFY_SCHEMA_MAP:
                    # the arguments are invalid or can not be used.
                    ConfigBase.logger.warning(
                        'An invalid Apprise schema ({}) in YAML configuration '
                        'entry #{}, item #{}'
                        .format(_results['schema'], no + 1, entry))
                    continue

                # tag is a special keyword that is managed by Apprise object.
                # The below ensures our tags are set correctly
                if 'tag' in _results:
                    # Tidy our list up
                    _results['tag'] = \
                        set(parse_list(_results['tag'])) | global_tags

                else:
                    # Just use the global settings
                    _results['tag'] = global_tags

                for key in list(_results.keys()):
                    # Strip out any tokens we know that we can't accept and
                    # warn the user
                    match = VALID_TOKEN.match(key)
                    if not match:
                        ConfigBase.logger.warning(
                            'Ignoring invalid token ({}) found in YAML '
                            'configuration entry #{}, item #{}'
                            .format(key, no + 1, entry))
                        del _results[key]

                ConfigBase.logger.trace(
                    'URL #{}: {} unpacked as:{}{}'
                    .format(no + 1, url, os.linesep, os.linesep.join(
                        ['{}="{}"'.format(k, a)
                         for k, a in _results.items()])))

                # Prepare our Asset Object
                _results['asset'] = asset

                # Now we generate our plugin
                try:
                    # Attempt to create an instance of our plugin using the
                    # parsed URL information
                    plugin = common.\
                        NOTIFY_SCHEMA_MAP[_results['schema']](**_results)

                    # Create log entry of loaded URL
                    ConfigBase.logger.debug(
                        'Loaded URL: {}'.format(
                            plugin.url(privacy=asset.secure_logging)))

                except Exception as e:
                    # the arguments are invalid or can not be used.
                    ConfigBase.logger.warning(
                        'Could not load Apprise YAML configuration '
                        'entry #{}, item #{}'
                        .format(no + 1, entry))
                    ConfigBase.logger.debug('Loading Exception: %s' % str(e))
                    continue

                # if we reach here, we successfully loaded our data
                servers.append(plugin)

        return (servers, configs)

    def pop(self, index=-1):
        """
        Removes an indexed Notification Service from the stack and returns it.

        By default, the last element of the list is removed.
        """

        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers()

        # Pop the element off of the stack
        return self._cached_servers.pop(index)

    @staticmethod
    def _special_token_handler(schema, tokens):
        """
        This function takes a list of tokens and updates them to no longer
        include any special tokens such as +,-, and :

        - schema must be a valid schema of a supported plugin type
        - tokens must be a dictionary containing the yaml entries parsed.

        The idea here is we can post process a set of tokens provided in
        a YAML file where the user provided some of the special keywords.

        We effectivley look up what these keywords map to their appropriate
        value they're expected
        """
        # Create a copy of our dictionary
        tokens = tokens.copy()

        for kw, meta in common.NOTIFY_SCHEMA_MAP[schema]\
                .template_kwargs.items():

            # Determine our prefix:
            prefix = meta.get('prefix', '+')

            # Detect any matches
            matches = \
                {k[1:]: str(v) for k, v in tokens.items()
                 if k.startswith(prefix)}

            if not matches:
                # we're done with this entry
                continue

            if not isinstance(tokens.get(kw), dict):
                # Invalid; correct it
                tokens[kw] = dict()

            # strip out processed tokens
            tokens = {k: v for k, v in tokens.items()
                      if not k.startswith(prefix)}

            # Update our entries
            tokens[kw].update(matches)

        # Now map our tokens accordingly to the class templates defined by
        # each service.
        #
        # This is specifically used for YAML file parsing.  It allows a user to
        # define an entry such as:
        #
        # urls:
        #   - mailto://user:pass@domain:
        #       - to: user1@hotmail.com
        #       - to: user2@hotmail.com
        #
        # Under the hood, the NotifyEmail() class does not parse the `to`
        # argument. It's contents needs to be mapped to `targets`.  This is
        # defined in the class via the `template_args` and template_tokens`
        # section.
        #
        # This function here allows these mappings to take place within the
        # YAML file as independant arguments.
        class_templates = \
            plugins.details(common.NOTIFY_SCHEMA_MAP[schema])

        for key in list(tokens.keys()):

            if key not in class_templates['args']:
                # No need to handle non-arg entries
                continue

            # get our `map_to` and/or 'alias_of' value (if it exists)
            map_to = class_templates['args'][key].get(
                'alias_of', class_templates['args'][key].get('map_to', ''))

            if map_to == key:
                # We're already good as we are now
                continue

            if map_to in class_templates['tokens']:
                meta = class_templates['tokens'][map_to]

            else:
                meta = class_templates['args'].get(
                    map_to, class_templates['args'][key])

            # Perform a translation/mapping if our code reaches here
            value = tokens[key]
            del tokens[key]

            # Detect if we're dealign with a list or not
            is_list = re.search(
                r'^list:.*',
                meta.get('type'),
                re.IGNORECASE)

            if map_to not in tokens:
                tokens[map_to] = [] if is_list \
                    else meta.get('default')

            elif is_list and not isinstance(tokens.get(map_to), list):
                # Convert ourselves to a list if we aren't already
                tokens[map_to] = [tokens[map_to]]

            # Type Conversion
            if re.search(
                    r'^(choice:)?string',
                    meta.get('type'),
                    re.IGNORECASE) \
                    and not isinstance(value, str):

                # Ensure our format is as expected
                value = str(value)

            # Apply any further translations if required (absolute map)
            # This is the case when an arg maps to a token which further
            # maps to a different function arg on the class constructor
            abs_map = meta.get('map_to', map_to)

            # Set our token as how it was provided by the configuration
            if isinstance(tokens.get(map_to), list):
                tokens[abs_map].append(value)

            else:
                tokens[abs_map] = value

        # Return our tokens
        return tokens

    def __getitem__(self, index):
        """
        Returns the indexed server entry associated with the loaded
        notification servers
        """
        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers()

        return self._cached_servers[index]

    def __iter__(self):
        """
        Returns an iterator to our server list
        """
        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers()

        return iter(self._cached_servers)

    def __len__(self):
        """
        Returns the total number of servers loaded
        """
        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers()

        return len(self._cached_servers)

    def __bool__(self):
        """
        Allows the Apprise object to be wrapped in an 'if statement'.
        True is returned if our content was downloaded correctly.
        """
        if not isinstance(self._cached_servers, list):
            # Generate ourselves a list of content we can pull from
            self.servers()

        return True if self._cached_servers else False
