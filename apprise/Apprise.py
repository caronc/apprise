# -*- coding: utf-8 -*-
#
# Apprise Core
#
# Copyright (C) 2017 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with apprise.  If not, see <http://www.gnu.org/licenses/>.

import re
import logging

from .common import NotifyType
from .common import NOTIFY_TYPES
from .utils import parse_list

from .AppriseAsset import AppriseAsset

from . import plugins

logger = logging.getLogger(__name__)

# Build a list of supported plugins
SCHEMA_MAP = {}

# Used for attempting to acquire the schema if the URL can't be parsed.
GET_SCHEMA_RE = re.compile('\s*(?P<schema>[a-z0-9]{3,9})://.*$', re.I)


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

        # Load protocol(s) if defined
        proto = getattr(plugin, 'protocol', None)
        if isinstance(proto, basestring):
            if proto not in SCHEMA_MAP:
                SCHEMA_MAP[proto] = plugin

        elif isinstance(proto, (set, list, tuple)):
            # Support iterables list types
            for p in proto:
                if p not in SCHEMA_MAP:
                    SCHEMA_MAP[p] = plugin

        # Load secure protocol(s) if defined
        protos = getattr(plugin, 'secure_protocol', None)
        if isinstance(protos, basestring):
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

    def add(self, servers, asset=None):
        """
        Adds one or more server URLs into our list.

        """

        # Initialize our return status
        return_status = True

        servers = parse_list(servers)
        for _server in servers:

            # swap hash (#) tag values with their html version
            # This is useful for accepting channels (as arguments to
            # pushbullet)
            _server = _server.replace('/#', '/%23')

            # Attempt to acquire the schema at the very least to allow
            # our plugins to determine if they can make a better
            # interpretation of a URL geared for them anyway.
            schema = GET_SCHEMA_RE.match(_server)
            if schema is None:
                logger.error(
                    '%s is an unparseable server url.' % _server,
                )
                return_status = False
                continue

            # Update the schema
            schema = schema.group('schema').lower()

            # Some basic validation
            if schema not in SCHEMA_MAP:
                logger.error(
                    '%s is not a supported server type.' % schema,
                )
                return_status = False
                continue

            # Parse our url details
            # the server object is a dictionary containing all of the
            # information parsed from our URL
            results = SCHEMA_MAP[schema].parse_url(_server)

            if not results:
                # Failed to parse the server URL
                logger.error('Could not parse URL: %s' % _server)
                return_status = False
                continue

            try:
                # Attempt to create an instance of our plugin using the parsed
                # URL information
                plugin = SCHEMA_MAP[results['schema']](**results)

            except:
                # the arguments are invalid or can not be used.
                return_status = False
                continue

            # Save our asset
            if asset:
                plugin.asset = asset

            else:
                plugin.asset = self.asset

            # Add our initialized plugin to our server listings
            self.servers.append(plugin)

        # Return our status
        return return_status

    def clear(self):
        """
        Empties our server list

        """
        self.servers[:] = []

    def notify(self, title, body, notify_type=NotifyType.SUCCESS, **kwargs):
        """
        This should be over-rided by the class that inherits this one.
        """

        # Initialize our return result
        status = len(self.servers) > 0

        if not (title or body):
            return False

        # Iterate over our loaded plugins
        for server in self.servers:
            try:
                # Send notification
                if not server.notify(title=title, body=body):

                    # Toggle our return status flag
                    status = False

            except:
                # A catch all so we don't have to abort early
                # just because one of our plugins has a bug in it.
                # TODO: print backtrace
                status = False

        return status

    def __len__(self):
        """
        Returns the number of servers loaded
        """
        return len(self.servers)
