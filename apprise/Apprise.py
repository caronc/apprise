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
import logging
from markdown import markdown

from .common import NotifyType
from .common import NotifyFormat
from .utils import parse_list
from .utils import compat_is_basestring
from .utils import GET_SCHEMA_RE

from .AppriseAsset import AppriseAsset

from . import NotifyBase
from . import plugins
from . import __version__

logger = logging.getLogger(__name__)

# Build a list of supported plugins
SCHEMA_MAP = {}


# Load our Lookup Matrix
def __load_matrix():
    """
    Dynamically load our schema map; this allows us to gracefully
    skip over plugins we simply don't have the dependecies for.

    """
    # to add it's mapping to our hash table
    for entry in dir(plugins):

        # Get our plugin
        plugin = getattr(plugins, entry)
        if not hasattr(plugin, 'app_id'):  # pragma: no branch
            # Filter out non-notification modules
            continue

        # Load protocol(s) if defined
        proto = getattr(plugin, 'protocol', None)
        if compat_is_basestring(proto):
            if proto not in SCHEMA_MAP:
                SCHEMA_MAP[proto] = plugin

        elif isinstance(proto, (set, list, tuple)):
            # Support iterables list types
            for p in proto:
                if p not in SCHEMA_MAP:
                    SCHEMA_MAP[p] = plugin

        # Load secure protocol(s) if defined
        protos = getattr(plugin, 'secure_protocol', None)
        if compat_is_basestring(protos):
            if protos not in SCHEMA_MAP:
                SCHEMA_MAP[protos] = plugin

        if isinstance(protos, (set, list, tuple)):
            # Support iterables list types
            for p in protos:
                if p not in SCHEMA_MAP:
                    SCHEMA_MAP[p] = plugin


# Dynamically build our module
__load_matrix()


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
        self.asset = asset
        if asset is None:
            # Load our default configuration
            self.asset = AppriseAsset()

        if servers:
            self.add(servers)

    @staticmethod
    def instantiate(url, asset=None, tag=None, suppress_exceptions=True):
        """
        Returns the instance of a instantiated plugin based on the provided
        Server URL.  If the url fails to be parsed, then None is returned.

        """
        # swap hash (#) tag values with their html version
        # This is useful for accepting channels (as arguments to pushbullet)
        _url = url.replace('/#', '/%23')

        # Attempt to acquire the schema at the very least to allow our plugins
        # to determine if they can make a better interpretation of a URL
        # geared for them anyway.
        schema = GET_SCHEMA_RE.match(_url)
        if schema is None:
            logger.error('%s is an unparseable server url.' % url)
            return None

        # Update the schema
        schema = schema.group('schema').lower()

        # Some basic validation
        if schema not in SCHEMA_MAP:
            logger.error(
                '{0} is not a supported server type (url={1}).'.format(
                    schema,
                    _url,
                )
            )
            return None

        # Parse our url details
        # the server object is a dictionary containing all of the information
        # parsed from our URL
        results = SCHEMA_MAP[schema].parse_url(_url)

        if not results:
            # Failed to parse the server URL
            logger.error('Could not parse URL: %s' % url)
            return None

        # Build a list of tags to associate with the newly added notifications
        results['tag'] = set(parse_list(tag))

        if suppress_exceptions:
            try:
                # Attempt to create an instance of our plugin using the parsed
                # URL information
                plugin = SCHEMA_MAP[results['schema']](**results)

            except Exception:
                # the arguments are invalid or can not be used.
                logger.error('Could not load URL: %s' % url)
                return None

        else:
            # Attempt to create an instance of our plugin using the parsed
            # URL information but don't wrap it in a try catch
            plugin = SCHEMA_MAP[results['schema']](**results)

        # Save our asset
        if asset:
            plugin.asset = asset

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

        if isinstance(servers, NotifyBase):
            # Go ahead and just add our plugin into our list
            self.servers.append(servers)
            return True

        # build our server listings
        servers = parse_list(servers)
        for _server in servers:

            # Instantiate ourselves an object, this function throws or
            # returns None if it fails
            instance = Apprise.instantiate(_server, asset=asset, tag=tag)
            if not instance:
                return_status = False
                logging.error(
                    "Failed to load notification url: {}".format(_server),
                )
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

    def notify(self, title, body, notify_type=NotifyType.INFO,
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
        status = len(self.servers) > 0

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
        for server in self.servers:

            if tag is not None:

                if isinstance(tag, (list, tuple, set)):
                    # using the tags detected; determine if we'll allow the
                    # notification to be sent or not
                    matched = False

                    # Every entry here will be or'ed with the next
                    for entry in tag:
                        if isinstance(entry, (list, tuple, set)):

                            # treat these entries as though all elements found
                            # must exist in the notification service
                            tags = set(parse_list(entry))

                            if len(tags.intersection(
                                   server.tags)) == len(tags):
                                # our set contains all of the entries found
                                # in our notification server object
                                matched = True
                                break

                        elif entry in server:
                            # our entr(ies) match what was found in our server
                            # object.
                            matched = True
                            break

                        # else: keep looking

                    if not matched:
                        # We did not meet any of our and'ed criteria
                        continue

                elif tag not in server:
                    # one or more tags were defined and they didn't match the
                    # entry in the current service; move along...
                    continue

                # else: our content was found inside the server, so we're good

            # If our code reaches here, we either did not define a tag (it was
            # set to None), or we did define a tag and the logic above
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
                        # multiple spaces are treated as one an this may not
                        # be the callers intention
                        r' ': '&nbsp;',

                        # Tab support
                        r'\t': '&nbsp;&nbsp;&nbsp;',

                        # Greater than and Less than Characters
                        r'>': '&gt;',
                        r'<': '&lt;',
                    }

                    # Compile our map
                    re_table = re.compile(
                        r'(' + '|'.join(map(re.escape, re_map.keys())) + r')',
                        re.IGNORECASE,
                    )

                    # Execute our map against our body in addition to swapping
                    # out new lines and replacing them with <br/>
                    conversion_map[server.notify_format] = \
                        re.sub(r'\r*\n', '<br/>\r\n',
                               re_table.sub(lambda x: re_map[x.group()], body))

                else:
                    # Store entry directly
                    conversion_map[server.notify_format] = body

            try:
                # Send notification
                if not server.notify(
                        title=title,
                        body=conversion_map[server.notify_format],
                        notify_type=notify_type):

                    # Toggle our return status flag
                    status = False

            except TypeError:
                # These our our internally thrown notifications
                # TODO: Change this to a custom one such as AppriseNotifyError
                status = False

            except Exception:
                # A catch all so we don't have to abort early
                # just because one of our plugins has a bug in it.
                logging.exception("Notification Exception")
                status = False

        return status

    def details(self):
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
        for entry in sorted(dir(plugins)):

            # Get our plugin
            plugin = getattr(plugins, entry)
            if not hasattr(plugin, 'app_id'):  # pragma: no branch
                # Filter out non-notification modules
                continue

            # Standard protocol(s) should be None or a tuple
            protocols = getattr(plugin, 'protocol', None)
            if compat_is_basestring(protocols):
                protocols = (protocols, )

            # Secure protocol(s) should be None or a tuple
            secure_protocols = getattr(plugin, 'secure_protocol', None)
            if compat_is_basestring(secure_protocols):
                secure_protocols = (secure_protocols, )

            # Build our response object
            response['schemas'].append({
                'service_name': getattr(plugin, 'service_name', None),
                'service_url': getattr(plugin, 'service_url', None),
                'setup_url': getattr(plugin, 'setup_url', None),
                'protocols': protocols,
                'secure_protocols': secure_protocols,
            })

        return response

    def urls(self):
        """
        Returns all of the loaded URLs defined in this apprise object.
        """
        return [x.url() for x in self.servers]

    def pop(self, index):
        """
        Removes an indexed Notification Service from the stack and
        returns it.
        """

        # Remove our entry
        return self.servers.pop(index)

    def __getitem__(self, index):
        """
        Returns the indexed server entry of a loaded notification server
        """
        return self.servers[index]

    def __iter__(self):
        """
        Returns an iterator to our server list
        """
        return iter(self.servers)

    def __len__(self):
        """
        Returns the number of servers loaded
        """
        return len(self.servers)
