# -*- coding: utf-8 -*-

import re
import logging

from . import plugins
from .Utils import parse_url
from .Utils import parse_list
from .Utils import parse_bool

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

        proto = getattr(plugin, 'PROTOCOL', None)
        protos = getattr(plugin, 'SECURE_PROTOCOL', None)
        if not proto:
            # Must have at least PROTOCOL defined
            continue

        if proto not in SCHEMA_MAP:
            SCHEMA_MAP[proto] = plugin

        if protos and protos not in SCHEMA_MAP:
            SCHEMA_MAP[protos] = plugin


# Dynamically build our module
__load_matrix()


class Apprise(object):
    """
    Our Notification Manager

    """
    def __init__(self, servers=None):
        """
        Loads a set of server urls

        """

        # Initialize a server list of URLs
        self.servers = list()

        if servers:
            self.add(servers)

    def add(self, servers, include_image=True, image_url=None,
            image_path=None):
        """
        Adds one or more server URLs into our list.

        """

        servers = parse_list(servers)
        for _server in servers:

            # swap hash (#) tag values with their html version
            # This is useful for accepting channels (as arguments to
            # pushbullet)
            _server = _server.replace('/#', '/%23')

            # Parse our url details
            # the server object is a dictionary containing all of the
            # information parsed from our URL
            server = parse_url(_server, default_schema='unknown')

            # Initialize our return status
            return_status = True

            if not server:
                # This is a dirty hack; but it's the only work around to
                # tgram:// messages since the bot_token has a colon in it.
                # It invalidates an normal URL.

                # This hack searches for this bogus URL and corrects it
                # so we can properly load it further down. The other
                # alternative is to ask users to actually change the colon
                # into a slash (which will work too), but it's more likely
                # to cause confusion... So this is the next best thing
                tgram = re.match(
                    r'(?P<protocol>%s://)(bot)?(?P<prefix>([a-z0-9_-]+)'
                    r'(:[a-z0-9_-]+)?@)?(?P<btoken_a>[0-9]+):+'
                    r'(?P<remaining>.*)$' % 'tgram',
                    _server, re.I)

                if tgram:
                    if tgram.group('prefix'):
                        server = self.parse_url('%s%s%s/%s' % (
                                tgram.group('protocol'),
                                tgram.group('prefix'),
                                tgram.group('btoken_a'),
                                tgram.group('remaining'),
                            ),
                            default_schema='unknown',
                        )

                    else:
                        server = self.parse_url('%s%s/%s' % (
                                tgram.group('protocol'),
                                tgram.group('btoken_a'),
                                tgram.group('remaining'),
                            ),
                            default_schema='unknown',
                        )

            if not server:
                # Failed to parse te server
                self.logger.error('Could not parse URL: %s' % server)
                return_status = False
                continue

            # Some basic validation
            if server['schema'] not in SCHEMA_MAP:
                self.logger.error(
                    '%s is not a supported server type.' %
                    server['schema'].upper(),
                )
                return_status = False
                continue

            notify_args = server.copy().items() + {
                # Logger Details
                'logger': self.logger,
                # Base
                'include_image': include_image,
                'secure': (server['schema'][-1] == 's'),
                # Support SSL Certificate 'verify' keyword
                # Default to being enabled (True)
                'verify': parse_bool(server['qsd'].get('verify', True)),
                # Overrides
                'override_image_url': image_url,
                'override_image_path': image_path,
            }.items()

            # Grant our plugin access to manipulate the dictionary
            if not SCHEMA_MAP[server['schema']].pre_parse(notify_args):
                # the arguments are invalid or can not be used.
                return_status = False
                continue

            # Add our entry to our list as it can be actioned at this point
            self.servers.add(notify_args)

            # Return our status
            return return_status

    def clear(self, urls):
        """
        Empties our server list

        """
        self.servers.clear()

    def notify(self, title='', body=''):
        """
        Notifies all loaded servers using the content provided.

        """
        # TODO: iterate over server entries and execute notification
