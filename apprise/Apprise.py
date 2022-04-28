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
import six
from itertools import chain
from .common import NotifyType
from .common import MATCH_ALL_TAG
from .common import MATCH_ALWAYS_TAG
from .conversion import convert_between
from .utils import is_exclusive_match
from .utils import parse_list
from .utils import parse_urls
from .utils import cwe312_url
from .logger import logger

from .AppriseAsset import AppriseAsset
from .AppriseConfig import AppriseConfig
from .AppriseAttachment import AppriseAttachment
from .AppriseLocale import AppriseLocale
from .config.ConfigBase import ConfigBase
from .plugins.NotifyBase import NotifyBase


from . import plugins
from . import __version__

# Python v3+ support code made importable so it can remain backwards
# compatible with Python v2
from . import py3compat
ASYNCIO_SUPPORT = not six.PY2


class Apprise(object):
    """
    Our Notification Manager

    """

    def __init__(self, servers=None, asset=None, location=None, debug=False):
        """
        Loads a set of server urls while applying the Asset() module to each
        if specified.

        If no asset is provided, then the default asset is used.

        Optionally specify a global ContentLocation for a more strict means
        of handling Attachments.
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

        # Set our debug flag
        self.debug = debug

        # Store our hosting location for optional strict rule handling
        # of Attachments.  Setting this to None removes any attachment
        # restrictions.
        self.location = location

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

        # Prepare our Asset Object
        asset = asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        if isinstance(url, six.string_types):
            # Acquire our url tokens
            results = plugins.url_to_dict(
                url, secure_logging=asset.secure_logging)

            if results is None:
                # Failed to parse the server URL; detailed logging handled
                # inside url_to_dict - nothing to report here.
                return None

        elif isinstance(url, dict):
            # We already have our result set
            results = url

            if results.get('schema') not in plugins.SCHEMA_MAP:
                # schema is a mandatory dictionary item as it is the only way
                # we can index into our loaded plugins
                logger.error('Dictionary does not include a "schema" entry.')
                logger.trace(
                    'Invalid dictionary unpacked as:{}{}'.format(
                        os.linesep, os.linesep.join(
                            ['{}="{}"'.format(k, v)
                             for k, v in results.items()])))
                return None

            logger.trace(
                'Dictionary unpacked as:{}{}'.format(
                    os.linesep, os.linesep.join(
                        ['{}="{}"'.format(k, v) for k, v in results.items()])))

        # Otherwise we handle the invalid input specified
        else:
            logger.error(
                'An invalid URL type (%s) was specified for instantiation',
                type(url))
            return None

        if not plugins.SCHEMA_MAP[results['schema']].enabled:
            #
            # First Plugin Enable Check (Pre Initialization)
            #

            # Plugin has been disabled at a global level
            logger.error(
                '%s:// is disabled on this system.', results['schema'])
            return None

        # Build a list of tags to associate with the newly added notifications
        results['tag'] = set(parse_list(tag))

        # Set our Asset Object
        results['asset'] = asset

        if suppress_exceptions:
            try:
                # Attempt to create an instance of our plugin using the parsed
                # URL information
                plugin = plugins.SCHEMA_MAP[results['schema']](**results)

                # Create log entry of loaded URL
                logger.debug(
                    'Loaded {} URL: {}'.format(
                        plugins.SCHEMA_MAP[results['schema']].service_name,
                        plugin.url(privacy=asset.secure_logging)))

            except Exception:
                # CWE-312 (Secure Logging) Handling
                loggable_url = url if not asset.secure_logging \
                    else cwe312_url(url)

                # the arguments are invalid or can not be used.
                logger.error(
                    'Could not load {} URL: {}'.format(
                        plugins.SCHEMA_MAP[results['schema']].service_name,
                        loggable_url))
                return None

        else:
            # Attempt to create an instance of our plugin using the parsed
            # URL information but don't wrap it in a try catch
            plugin = plugins.SCHEMA_MAP[results['schema']](**results)

        if not plugin.enabled:
            #
            # Second Plugin Enable Check (Post Initialization)
            #

            # Service/Plugin is disabled (on a more local level).  This is a
            # case where the plugin was initially enabled but then after the
            # __init__() was called under the hood something pre-determined
            # that it could no longer be used.

            # The only downside to doing it this way is services are
            # initialized prior to returning the details() if 3rd party tools
            # are polling what is available. These services that become
            # disabled thereafter are shown initially that they can be used.
            logger.error(
                '%s:// has become disabled on this system.', results['schema'])
            return None

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
            servers = parse_urls(servers)
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
                # No logging is required as instantiate() handles failure
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

    def find(self, tag=MATCH_ALL_TAG, match_always=True):
        """
        Returns an list of all servers matching against the tag specified.

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

        # A match_always flag allows us to pick up on our 'any' keyword
        # and notify these services under all circumstances
        match_always = MATCH_ALWAYS_TAG if match_always else None

        # Iterate over our loaded plugins
        for entry in self.servers:

            if isinstance(entry, (ConfigBase, AppriseConfig)):
                # load our servers
                servers = entry.servers()

            else:
                servers = [entry, ]

            for server in servers:
                # Apply our tag matching based on our defined logic
                if is_exclusive_match(
                        logic=tag, data=server.tags, match_all=MATCH_ALL_TAG,
                        match_always=match_always):
                    yield server
        return

    def notify(self, body, title='', notify_type=NotifyType.INFO,
               body_format=None, tag=MATCH_ALL_TAG, match_always=True,
               attach=None, interpret_escapes=None):
        """
        Send a notification to all of the plugins previously loaded.

        If the body_format specified is NotifyFormat.MARKDOWN, it will
        be converted to HTML if the Notification type expects this.

        if the tag is specified (either a string or a set/list/tuple
        of strings), then only the notifications flagged with that
        tagged value are notified.  By default all added services
        are notified (tag=MATCH_ALL_TAG)

        This function returns True if all notifications were successfully
        sent, False if even just one of them fails, and None if no
        notifications were sent at all as a result of tag filtering and/or
        simply having empty configuration files that were read.

        Attach can contain a list of attachment URLs.  attach can also be
        represented by a an AttachBase() (or list of) object(s). This
        identifies the products you wish to notify

        Set interpret_escapes to True if you want to pre-escape a string
        such as turning a \n into an actual new line, etc.
        """

        if ASYNCIO_SUPPORT:
            return py3compat.asyncio.tosync(
                self.async_notify(
                    body, title,
                    notify_type=notify_type, body_format=body_format,
                    tag=tag, match_always=match_always, attach=attach,
                    interpret_escapes=interpret_escapes,
                ),
                debug=self.debug
            )

        else:
            try:
                results = list(
                    self._notifyall(
                        Apprise._notifyhandler,
                        body, title,
                        notify_type=notify_type, body_format=body_format,
                        tag=tag, attach=attach,
                        interpret_escapes=interpret_escapes,
                    )
                )

            except TypeError:
                # No notifications sent, and there was an internal error.
                return False

            else:
                if len(results) > 0:
                    # All notifications sent, return False if any failed.
                    return all(results)

                else:
                    # No notifications sent.
                    return None

    def async_notify(self, *args, **kwargs):
        """
        Send a notification to all of the plugins previously loaded, for
        asynchronous callers. This method is an async method that should be
        awaited on, even if it is missing the async keyword in its signature.
        (This is omitted to preserve syntax compatibility with Python 2.)

        The arguments are identical to those of Apprise.notify(). This method
        is not available in Python 2.
        """

        try:
            coroutines = list(
                self._notifyall(
                    Apprise._notifyhandlerasync, *args, **kwargs))

        except TypeError:
            # No notifications sent, and there was an internal error.
            return py3compat.asyncio.toasyncwrap(False)

        else:
            if len(coroutines) > 0:
                # All notifications sent, return False if any failed.
                return py3compat.asyncio.notify(coroutines)

            else:
                # No notifications sent.
                return py3compat.asyncio.toasyncwrap(None)

    @staticmethod
    def _notifyhandler(server, **kwargs):
        """
        The synchronous notification sender. Returns True if the notification
        sent successfully.
        """

        try:
            # Send notification
            return server.notify(**kwargs)

        except TypeError:
            # These our our internally thrown notifications
            return False

        except Exception:
            # A catch all so we don't have to abort early
            # just because one of our plugins has a bug in it.
            logger.exception("Unhandled Notification Exception")
            return False

    @staticmethod
    def _notifyhandlerasync(server, **kwargs):
        """
        The asynchronous notification sender. Returns a coroutine that yields
        True if the notification sent successfully.
        """

        if server.asset.async_mode:
            return server.async_notify(**kwargs)

        else:
            # Send the notification immediately, and wrap the result in a
            # coroutine.
            status = Apprise._notifyhandler(server, **kwargs)
            return py3compat.asyncio.toasyncwrap(status)

    def _notifyall(self, handler, body, title='', notify_type=NotifyType.INFO,
                   body_format=None, tag=MATCH_ALL_TAG, match_always=True,
                   attach=None, interpret_escapes=None):
        """
        Creates notifications for all of the plugins loaded.

        Returns a generator that calls handler for each notification. The first
        and only argument supplied to handler is the server, and the keyword
        arguments are exactly as they would be passed to server.notify().
        """

        if len(self) == 0:
            # Nothing to notify
            msg = "There are service(s) to notify"
            logger.error(msg)
            raise TypeError(msg)

        if not (title or body):
            msg = "No message content specified to deliver"
            logger.error(msg)
            raise TypeError(msg)

        try:
            if six.PY2:
                # Python 2.7 encoding support isn't the greatest, so we try
                # to ensure that we're ALWAYS dealing with unicode characters
                # prior to entrying the next part.  This is especially required
                # for Markdown support
                if title and isinstance(title, str):  # noqa: F821
                    title = title.decode(self.asset.encoding)

                if body and isinstance(body, str):  # noqa: F821
                    body = body.decode(self.asset.encoding)

            else:  # Python 3+
                if title and isinstance(title, bytes):  # noqa: F821
                    title = title.decode(self.asset.encoding)

                if body and isinstance(body, bytes):  # noqa: F821
                    body = body.decode(self.asset.encoding)

        except UnicodeDecodeError:
            msg = 'The content passed into Apprise was not of encoding ' \
                  'type: {}'.format(self.asset.encoding)
            logger.error(msg)
            raise TypeError(msg)

        # Tracks conversions
        conversion_body_map = dict()
        conversion_title_map = dict()

        # Prepare attachments if required
        if attach is not None and not isinstance(attach, AppriseAttachment):
            attach = AppriseAttachment(
                attach, asset=self.asset, location=self.location)

        # Allow Asset default value
        body_format = self.asset.body_format \
            if body_format is None else body_format

        # Allow Asset default value
        interpret_escapes = self.asset.interpret_escapes \
            if interpret_escapes is None else interpret_escapes

        # Iterate over our loaded plugins
        for server in self.find(tag, match_always=match_always):
            # If our code reaches here, we either did not define a tag (it
            # was set to None), or we did define a tag and the logic above
            # determined we need to notify the service it's associated with
            if server.notify_format not in conversion_body_map:
                # Perform Conversion
                conversion_body_map[server.notify_format] = \
                    convert_between(
                        body_format, server.notify_format, content=body)

                # Prepare our title
                conversion_title_map[server.notify_format] = \
                    '' if not title else title

                # Tidy Title IF required (hence it will become part of the
                # body)
                if server.title_maxlen <= 0 and \
                        conversion_title_map[server.notify_format]:

                    conversion_title_map[server.notify_format] = \
                        convert_between(
                            body_format, server.notify_format,
                            content=conversion_title_map[server.notify_format])

                if interpret_escapes:
                    #
                    # Escape our content
                    #

                    try:
                        # Added overhead required due to Python 3 Encoding Bug
                        # identified here: https://bugs.python.org/issue21331
                        conversion_body_map[server.notify_format] = \
                            conversion_body_map[server.notify_format]\
                            .encode('ascii', 'backslashreplace')\
                            .decode('unicode-escape')

                        conversion_title_map[server.notify_format] = \
                            conversion_title_map[server.notify_format]\
                            .encode('ascii', 'backslashreplace')\
                            .decode('unicode-escape')

                    except UnicodeDecodeError:  # pragma: no cover
                        # This occurs using a very old verion of Python 2.7
                        # such as the one that ships with CentOS/RedHat 7.x
                        # (v2.7.5).
                        conversion_body_map[server.notify_format] = \
                            conversion_body_map[server.notify_format] \
                            .decode('string_escape')

                        conversion_title_map[server.notify_format] = \
                            conversion_title_map[server.notify_format] \
                            .decode('string_escape')

                    except AttributeError:
                        # Must be of string type
                        msg = 'Failed to escape message body'
                        logger.error(msg)
                        raise TypeError(msg)

                if six.PY2:
                    # Python 2.7 strings must be encoded as utf-8 for
                    # consistency across all platforms
                    if conversion_body_map[server.notify_format] and \
                            isinstance(
                                conversion_body_map[server.notify_format],
                                unicode):  # noqa: F821
                        conversion_body_map[server.notify_format] = \
                            conversion_body_map[server.notify_format]\
                            .encode('utf-8')

                    if conversion_title_map[server.notify_format] and \
                            isinstance(
                                conversion_title_map[server.notify_format],
                                unicode):  # noqa: F821
                        conversion_title_map[server.notify_format] = \
                            conversion_title_map[server.notify_format]\
                            .encode('utf-8')

            yield handler(
                server,
                body=conversion_body_map[server.notify_format],
                title=conversion_title_map[server.notify_format],
                notify_type=notify_type,
                attach=attach,
                body_format=body_format,
            )

    def details(self, lang=None, show_requirements=False, show_disabled=False):
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

        for plugin in set(plugins.SCHEMA_MAP.values()):
            # Iterate over our hashed plugins and dynamically build details on
            # their status:

            content = {
                'service_name': getattr(plugin, 'service_name', None),
                'service_url': getattr(plugin, 'service_url', None),
                'setup_url': getattr(plugin, 'setup_url', None),
                # Placeholder - populated below
                'details': None
            }

            # Standard protocol(s) should be None or a tuple
            enabled = getattr(plugin, 'enabled', True)
            if not show_disabled and not enabled:
                # Do not show inactive plugins
                continue

            elif show_disabled:
                # Add current state to response
                content['enabled'] = enabled

            # Standard protocol(s) should be None or a tuple
            protocols = getattr(plugin, 'protocol', None)
            if isinstance(protocols, six.string_types):
                protocols = (protocols, )

            # Secure protocol(s) should be None or a tuple
            secure_protocols = getattr(plugin, 'secure_protocol', None)
            if isinstance(secure_protocols, six.string_types):
                secure_protocols = (secure_protocols, )

            # Add our protocol details to our content
            content.update({
                'protocols': protocols,
                'secure_protocols': secure_protocols,
            })

            if not lang:
                # Simply return our results
                content['details'] = plugins.details(plugin)
                if show_requirements:
                    content['requirements'] = plugins.requirements(plugin)

            else:
                # Emulate the specified language when returning our results
                with self.locale.lang_at(lang):
                    content['details'] = plugins.details(plugin)
                    if show_requirements:
                        content['requirements'] = plugins.requirements(plugin)

            # Build our response object
            response['schemas'].append(content)

        return response

    def urls(self, privacy=False):
        """
        Returns all of the loaded URLs defined in this apprise object.
        """
        return [x.url(privacy=privacy) for x in self.servers]

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

    def __bool__(self):
        """
        Allows the Apprise object to be wrapped in an Python 3.x based 'if
        statement'.  True is returned if at least one service has been loaded.
        """
        return len(self) > 0

    def __nonzero__(self):
        """
        Allows the Apprise object to be wrapped in an Python 2.x based 'if
        statement'.  True is returned if at least one service has been loaded.
        """
        return len(self) > 0

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


if six.PY2:
    del Apprise.async_notify
