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
import six
from markdown import markdown
from itertools import chain
from .common import NotifyType
from .common import NotifyFormat
from .utils import is_exclusive_match
from .utils import parse_list
from .utils import split_urls
from .utils import GET_SCHEMA_RE
from .logger import logger

from .AppriseAsset import AppriseAsset
from .AppriseConfig import AppriseConfig
from .AppriseLocale import AppriseLocale
from .config.ConfigBase import ConfigBase
from .plugins.NotifyBase import NotifyBase

from . import plugins
from . import __version__


class Apprise(object):
    """
    Our Notification Manager

    """
    def __init__(self, servers=None, asset=None):
        """
        Loads a set of server urls while applying the Asset() module to each
        if specified.

        If no asset is provided, then the default asset is used.

        """

        # Initialize a server list of URLs
        self.servers = list()

        # Assigns an central asset object that will be later passed into each
        # notification plugin.  Assets contain information such as the local
        # directory images can be found in. It can also identify remote
        # URL paths that contain the images you want to present to the end
        # user. If no asset is specified, then the default one is used.
        self.asset = \
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        if servers:
            self.add(servers)

        # Initialize our locale object
        self.locale = AppriseLocale()

    @staticmethod
    def instantiate(url, asset=None, tag=None, suppress_exceptions=True):
        """
        Returns the instance of a instantiated plugin based on the provided
        Server URL.  If the url fails to be parsed, then None is returned.

        The specified url can be either a string (the URL itself) or a
        dictionary containing all of the components needed to istantiate
        the notification service.  If identifying a dictionary, at the bare
        minimum, one must specify the schema.

        An example of a url dictionary object might look like:
          {
            schema: 'mailto',
            host: 'google.com',
            user: 'myuser',
            password: 'mypassword',
          }

        Alternatively the string is much easier to specify:
          mailto://user:mypassword@google.com

        The dictionary works well for people who are calling details() to
        extract the components they need to build the URL manually.
        """

        # Initialize our result set
        results = None

        if isinstance(url, six.string_types):
            # swap hash (#) tag values with their html version
            _url = url.replace('/#', '/%23')

            # Attempt to acquire the schema at the very least to allow our
            # plugins to determine if they can make a better interpretation of
            # a URL geared for them
            schema = GET_SCHEMA_RE.match(_url)
            if schema is None:
                logger.error(
                    'Unparseable schema:// found in URL {}.'.format(url))
                return None

            # Ensure our schema is always in lower case
            schema = schema.group('schema').lower()

            # Some basic validation
            if schema not in plugins.SCHEMA_MAP:
                # Give the user the benefit of the doubt that the user may be
                # using one of the URLs provided to them by their notification
                # service. Before we fail for good, just scan all the plugins
                # that support he native_url() parse function
                results = \
                    next((r['plugin'].parse_native_url(_url)
                          for r in plugins.MODULE_MAP.values()
                          if r['plugin'].parse_native_url(_url) is not None),
                         None)

            else:
                # Parse our url details of the server object as dictionary
                # containing all of the information parsed from our URL
                results = plugins.SCHEMA_MAP[schema].parse_url(_url)

            if results is None:
                # Failed to parse the server URL
                logger.error('Unparseable URL {}.'.format(url))
                return None

            logger.trace('URL {} unpacked as:{}{}'.format(
                url, os.linesep, os.linesep.join(
                    ['{}="{}"'.format(k, v) for k, v in results.items()])))

        elif isinstance(url, dict):
            # We already have our result set
            results = url

            if results.get('schema') not in plugins.SCHEMA_MAP:
                # schema is a mandatory dictionary item as it is the only way
                # we can index into our loaded plugins
                logger.error('Dictionary does not include a "schema" entry.')
                logger.trace('Invalid dictionary unpacked as:{}{}'.format(
                    os.linesep, os.linesep.join(
                        ['{}="{}"'.format(k, v) for k, v in results.items()])))
                return None

            logger.trace('Dictionary unpacked as:{}{}'.format(
                os.linesep, os.linesep.join(
                    ['{}="{}"'.format(k, v) for k, v in results.items()])))

        else:
            logger.error('Invalid URL specified: {}'.format(url))
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
                plugin = plugins.SCHEMA_MAP[results['schema']](**results)

                # Create log entry of loaded URL
                logger.debug('Loaded URL: {}'.format(plugin.url()))

            except Exception:
                # the arguments are invalid or can not be used.
                logger.error('Could not load URL: %s' % url)
                return None

        else:
            # Attempt to create an instance of our plugin using the parsed
            # URL information but don't wrap it in a try catch
            plugin = plugins.SCHEMA_MAP[results['schema']](**results)

        return plugin

    def add(self, servers, asset=None, tag=None):
        """
        Adds one or more server URLs into our list.

        You can override the global asset if you wish by including it with the
        server(s) that you add.

        The tag allows you to associate 1 or more tag values to the server(s)
        being added. tagging a service allows you to exclusively access them
        when calling the notify() function.
        """

        # Initialize our return status
        return_status = True

        if asset is None:
            # prepare default asset
            asset = self.asset

        if isinstance(servers, six.string_types):
            # build our server list
            servers = split_urls(servers)
            if len(servers) == 0:
                return False

        elif isinstance(servers, dict):
            # no problem, we support kwargs, convert it to a list
            servers = [servers]

        elif isinstance(servers, (ConfigBase, NotifyBase, AppriseConfig)):
            # Go ahead and just add our plugin into our list
            self.servers.append(servers)
            return True

        elif not isinstance(servers, (tuple, set, list)):
            logger.error(
                "An invalid notification (type={}) was specified.".format(
                    type(servers)))
            return False

        for _server in servers:

            if isinstance(_server, (ConfigBase, NotifyBase, AppriseConfig)):
                # Go ahead and just add our plugin into our list
                self.servers.append(_server)
                continue

            elif not isinstance(_server, (six.string_types, dict)):
                logger.error(
                    "An invalid notification (type={}) was specified.".format(
                        type(_server)))
                return_status = False
                continue

            # Instantiate ourselves an object, this function throws or
            # returns None if it fails
            instance = Apprise.instantiate(_server, asset=asset, tag=tag)
            if not isinstance(instance, NotifyBase):
                # No logging is requird as instantiate() handles failure
                # and/or success reasons for us
                return_status = False
                continue

            # Add our initialized plugin to our server listings
            self.servers.append(instance)

        # Return our status
        return return_status

    def clear(self):
        """
        Empties our server list

        """
        self.servers[:] = []

    def notify(self, body, title='', notify_type=NotifyType.INFO,
               body_format=None, tag=None):
        """
        Send a notification to all of the plugins previously loaded.

        If the body_format specified is NotifyFormat.MARKDOWN, it will
        be converted to HTML if the Notification type expects this.

        if the tag is specified (either a string or a set/list/tuple
        of strings), then only the notifications flagged with that
        tagged value are notified.  By default all added services
        are notified (tag=None)

        """

        # Initialize our return result
        status = len(self) > 0

        if not (title or body):
            return False

        # Tracks conversions
        conversion_map = dict()

        # Build our tag setup
        #   - top level entries are treated as an 'or'
        #   - second level (or more) entries are treated as 'and'
        #
        #   examples:
        #     tag="tagA, tagB"                = tagA or tagB
        #     tag=['tagA', 'tagB']            = tagA or tagB
        #     tag=[('tagA', 'tagC'), 'tagB']  = (tagA and tagC) or tagB
        #     tag=[('tagB', 'tagC')]          = tagB and tagC

        # Iterate over our loaded plugins
        for entry in self.servers:

            if isinstance(entry, (ConfigBase, AppriseConfig)):
                # load our servers
                servers = entry.servers()

            else:
                servers = [entry, ]

            for server in servers:
                # Apply our tag matching based on our defined logic
                if tag is not None and not is_exclusive_match(
                        logic=tag, data=server.tags):
                    continue

                # If our code reaches here, we either did not define a tag (it
                # was set to None), or we did define a tag and the logic above
                # determined we need to notify the service it's associated with
                if server.notify_format not in conversion_map:
                    if body_format == NotifyFormat.MARKDOWN and \
                            server.notify_format == NotifyFormat.HTML:

                        # Apply Markdown
                        conversion_map[server.notify_format] = markdown(body)

                    elif body_format == NotifyFormat.TEXT and \
                            server.notify_format == NotifyFormat.HTML:

                        # Basic TEXT to HTML format map; supports keys only
                        re_map = {
                            # Support Ampersand
                            r'&': '&amp;',

                            # Spaces to &nbsp; for formatting purposes since
                            # multiple spaces are treated as one an this may
                            # not be the callers intention
                            r' ': '&nbsp;',

                            # Tab support
                            r'\t': '&nbsp;&nbsp;&nbsp;',

                            # Greater than and Less than Characters
                            r'>': '&gt;',
                            r'<': '&lt;',
                        }

                        # Compile our map
                        re_table = re.compile(
                            r'(' + '|'.join(
                                map(re.escape, re_map.keys())) + r')',
                            re.IGNORECASE,
                        )

                        # Execute our map against our body in addition to
                        # swapping out new lines and replacing them with <br/>
                        conversion_map[server.notify_format] = \
                            re.sub(r'\r*\n', '<br/>\r\n',
                                   re_table.sub(
                                       lambda x: re_map[x.group()], body))

                    else:
                        # Store entry directly
                        conversion_map[server.notify_format] = body

                try:
                    # Send notification
                    if not server.notify(
                            body=conversion_map[server.notify_format],
                            title=title,
                            notify_type=notify_type):

                        # Toggle our return status flag
                        status = False

                except TypeError:
                    # These our our internally thrown notifications
                    status = False

                except Exception:
                    # A catch all so we don't have to abort early
                    # just because one of our plugins has a bug in it.
                    logger.exception("Notification Exception")
                    status = False

        return status

    def details(self, lang=None):
        """
        Returns the details associated with the Apprise object

        """

        # general object returned
        response = {
            # Defines the current version of Apprise
            'version': __version__,
            # Lists all of the currently supported Notifications
            'schemas': [],
            # Includes the configured asset details
            'asset': self.asset.details(),
        }

        # to add it's mapping to our hash table
        for plugin in set(plugins.SCHEMA_MAP.values()):

            # Standard protocol(s) should be None or a tuple
            protocols = getattr(plugin, 'protocol', None)
            if isinstance(protocols, six.string_types):
                protocols = (protocols, )

            # Secure protocol(s) should be None or a tuple
            secure_protocols = getattr(plugin, 'secure_protocol', None)
            if isinstance(secure_protocols, six.string_types):
                secure_protocols = (secure_protocols, )

            if not lang:
                # Simply return our results
                details = plugins.details(plugin)
            else:
                # Emulate the specified language when returning our results
                with self.locale.lang_at(lang):
                    details = plugins.details(plugin)

            # Build our response object
            response['schemas'].append({
                'service_name': getattr(plugin, 'service_name', None),
                'service_url': getattr(plugin, 'service_url', None),
                'setup_url': getattr(plugin, 'setup_url', None),
                'protocols': protocols,
                'secure_protocols': secure_protocols,
                'details': details,
            })

        return response

    def urls(self):
        """
        Returns all of the loaded URLs defined in this apprise object.
        """
        return [x.url() for x in self.servers]

    def pop(self, index):
        """
        Removes an indexed Notification Service from the stack and returns it.

        The thing is we can never pop AppriseConfig() entries, only what was
        loaded within them. So pop needs to carefully iterate over our list
        and only track actual entries.
        """

        # Tracking variables
        prev_offset = -1
        offset = prev_offset

        for idx, s in enumerate(self.servers):
            if isinstance(s, (ConfigBase, AppriseConfig)):
                servers = s.servers()
                if len(servers) > 0:
                    # Acquire a new maximum offset to work with
                    offset = prev_offset + len(servers)

                    if offset >= index:
                        # we can pop an element from our config stack
                        fn = s.pop if isinstance(s, ConfigBase) \
                            else s.server_pop

                        return fn(index if prev_offset == -1
                                  else (index - prev_offset - 1))

            else:
                offset = prev_offset + 1
                if offset == index:
                    return self.servers.pop(idx)

            # Update our old offset
            prev_offset = offset

        # If we reach here, then we indexed out of range
        raise IndexError('list index out of range')

    def __getitem__(self, index):
        """
        Returns the indexed server entry of a loaded notification server
        """
        # Tracking variables
        prev_offset = -1
        offset = prev_offset

        for idx, s in enumerate(self.servers):
            if isinstance(s, (ConfigBase, AppriseConfig)):
                # Get our list of servers associate with our config object
                servers = s.servers()
                if len(servers) > 0:
                    # Acquire a new maximum offset to work with
                    offset = prev_offset + len(servers)

                    if offset >= index:
                        return servers[index if prev_offset == -1
                                       else (index - prev_offset - 1)]

            else:
                offset = prev_offset + 1
                if offset == index:
                    return self.servers[idx]

            # Update our old offset
            prev_offset = offset

        # If we reach here, then we indexed out of range
        raise IndexError('list index out of range')

    def __iter__(self):
        """
        Returns an iterator to each of our servers loaded. This includes those
        found inside configuration.
        """
        return chain(*[[s] if not isinstance(s, (ConfigBase, AppriseConfig))
                       else iter(s.servers()) for s in self.servers])

    def __len__(self):
        """
        Returns the number of servers loaded; this includes those found within
        loaded configuration. This funtion nnever actually counts the
        Config entry themselves (if they exist), only what they contain.
        """
        return sum([1 if not isinstance(s, (ConfigBase, AppriseConfig))
                    else len(s.servers()) for s in self.servers])
