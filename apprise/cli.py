# -*- coding: utf-8 -*-

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

import click
import logging
import platform
import sys
import os
import re

from os.path import isfile
from os.path import exists
from os.path import expanduser
from os.path import expandvars

from . import NotifyType
from . import NotifyFormat
from . import Apprise
from . import AppriseAsset
from . import AppriseConfig

from .utils import parse_list
from .common import NOTIFY_TYPES
from .common import NOTIFY_FORMATS
from .common import ContentLocation
from .logger import logger

from . import __title__
from . import __version__
from . import __license__
from . import __copywrite__

# By default we allow looking 1 level down recursivly in Apprise configuration
# files.
DEFAULT_RECURSION_DEPTH = 1

# Defines our click context settings adding -h to the additional options that
# can be specified to get the help menu to come up
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

# Define our default configuration we use if nothing is otherwise specified
DEFAULT_CONFIG_PATHS = (
    # Legacy Path Support
    '~/.apprise',
    '~/.apprise.yml',
    '~/.config/apprise',
    '~/.config/apprise.yml',

    # Plugin Support Extended Directory Search Paths
    '~/.apprise/apprise',
    '~/.apprise/apprise.yml',
    '~/.config/apprise/apprise',
    '~/.config/apprise/apprise.yml',
)

# Define our paths to search for plugins
DEFAULT_PLUGIN_PATHS = (
    '~/.apprise/plugins',
    '~/.config/apprise/plugins',
)

# Detect Windows
if platform.system() == 'Windows':
    # Default Config Search Path for Windows Users
    DEFAULT_CONFIG_PATHS = (
        expandvars('%APPDATA%/Apprise/apprise'),
        expandvars('%APPDATA%/Apprise/apprise.yml'),
        expandvars('%LOCALAPPDATA%/Apprise/apprise'),
        expandvars('%LOCALAPPDATA%/Apprise/apprise.yml'),
    )

    # Default Plugin Search Path for Windows Users
    DEFAULT_PLUGIN_PATHS = (
        expandvars('%APPDATA%/Apprise/plugins'),
        expandvars('%LOCALAPPDATA%/Apprise/plugins'),
    )


def print_help_msg(command):
    """
    Prints help message when -h or --help is specified.

    """
    with click.Context(command) as ctx:
        click.echo(command.get_help(ctx))


def print_version_msg():
    """
    Prints version message when -V or --version is specified.

    """
    result = list()
    result.append('{} v{}'.format(__title__, __version__))
    result.append(__copywrite__)
    result.append(
        'This code is licensed under the {} License.'.format(__license__))
    click.echo('\n'.join(result))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--body', '-b', default=None, type=str,
              help='Specify the message body. If no body is specified then '
              'content is read from <stdin>.')
@click.option('--title', '-t', default=None, type=str,
              help='Specify the message title. This field is complete '
              'optional.')
@click.option('--plugin-path', '-P', default=None, type=str, multiple=True,
              metavar='PLUGIN_PATH',
              help='Specify one or more plugin paths to scan.')
@click.option('--config', '-c', default=None, type=str, multiple=True,
              metavar='CONFIG_URL',
              help='Specify one or more configuration locations.')
@click.option('--attach', '-a', default=None, type=str, multiple=True,
              metavar='ATTACHMENT_URL',
              help='Specify one or more attachment.')
@click.option('--notification-type', '-n', default=NotifyType.INFO, type=str,
              metavar='TYPE',
              help='Specify the message type (default={}). '
              'Possible values are "{}", and "{}".'.format(
                  NotifyType.INFO, '", "'.join(NOTIFY_TYPES[:-1]),
                  NOTIFY_TYPES[-1]))
@click.option('--input-format', '-i', default=NotifyFormat.TEXT, type=str,
              metavar='FORMAT',
              help='Specify the message input format (default={}). '
              'Possible values are "{}", and "{}".'.format(
                  NotifyFormat.TEXT, '", "'.join(NOTIFY_FORMATS[:-1]),
                  NOTIFY_FORMATS[-1]))
@click.option('--theme', '-T', default='default', type=str, metavar='THEME',
              help='Specify the default theme.')
@click.option('--tag', '-g', default=None, type=str, multiple=True,
              metavar='TAG', help='Specify one or more tags to filter '
              'which services to notify. Use multiple --tag (-g) entries to '
              '"OR" the tags together and comma separated to "AND" them. '
              'If no tags are specified then all services are notified.')
@click.option('--disable-async', '-Da', is_flag=True,
              help='Send all notifications sequentially')
@click.option('--dry-run', '-d', is_flag=True,
              help='Perform a trial run but only prints the notification '
              'services to-be triggered to stdout. Notifications are never '
              'sent using this mode.')
@click.option('--details', '-l', is_flag=True,
              help='Prints details about the current services supported by '
              'Apprise.')
@click.option('--recursion-depth', '-R', default=DEFAULT_RECURSION_DEPTH,
              type=int,
              help='The number of recursive import entries that can be '
              'loaded from within Apprise configuration. By default '
              'this is set to {}.'.format(DEFAULT_RECURSION_DEPTH))
@click.option('--verbose', '-v', count=True,
              help='Makes the operation more talkative. Use multiple v to '
              'increase the verbosity. I.e.: -vvvv')
@click.option('--interpret-escapes', '-e', is_flag=True,
              help='Enable interpretation of backslash escapes')
@click.option('--debug', '-D', is_flag=True, help='Debug mode')
@click.option('--version', '-V', is_flag=True,
              help='Display the apprise version and exit.')
@click.argument('urls', nargs=-1,
                metavar='SERVER_URL [SERVER_URL2 [SERVER_URL3]]',)
def main(body, title, config, attach, urls, notification_type, theme, tag,
         input_format, dry_run, recursion_depth, verbose, disable_async,
         details, interpret_escapes, plugin_path, debug, version):
    """
    Send a notification to all of the specified servers identified by their
    URLs the content provided within the title, body and notification-type.

    For a list of all of the supported services and information on how to
    use them, check out at https://github.com/caronc/apprise
    """
    # Note: Click ignores the return values of functions it wraps, If you
    #       want to return a specific error code, you must call sys.exit()
    #       as you will see below.

    debug = True if debug else False
    if debug:
        # Verbosity must be a minimum of 3
        verbose = 3 if verbose < 3 else verbose

    # Logging
    ch = logging.StreamHandler(sys.stdout)
    if verbose > 3:
        # -vvvv: Most Verbose Debug Logging
        logger.setLevel(logging.TRACE)

    elif verbose > 2:
        # -vvv: Debug Logging
        logger.setLevel(logging.DEBUG)

    elif verbose > 1:
        # -vv: INFO Messages
        logger.setLevel(logging.INFO)

    elif verbose > 0:
        # -v: WARNING Messages
        logger.setLevel(logging.WARNING)

    else:
        # No verbosity means we display ERRORS only AND any deprecation
        # warnings
        logger.setLevel(logging.ERROR)

    # Format our logger
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Update our asyncio logger
    asyncio_logger = logging.getLogger('asyncio')
    for handler in logger.handlers:
        asyncio_logger.addHandler(handler)
    asyncio_logger.setLevel(logger.level)

    if version:
        print_version_msg()
        sys.exit(0)

    # Simple Error Checking
    notification_type = notification_type.strip().lower()
    if notification_type not in NOTIFY_TYPES:
        logger.error(
            'The --notification-type (-n) value of {} is not supported.'
            .format(notification_type))
        # 2 is the same exit code returned by Click if there is a parameter
        # issue.  For consistency, we also return a 2
        sys.exit(2)

    input_format = input_format.strip().lower()
    if input_format not in NOTIFY_FORMATS:
        logger.error(
            'The --input-format (-i) value of {} is not supported.'
            .format(input_format))
        # 2 is the same exit code returned by Click if there is a parameter
        # issue.  For consistency, we also return a 2
        sys.exit(2)

    if not plugin_path:
        # Prepare a default set of plugin path
        plugin_path = \
            next((path for path in DEFAULT_PLUGIN_PATHS
                 if exists(expanduser(path))), None)

    # Prepare our asset
    asset = AppriseAsset(
        # Our body format
        body_format=input_format,

        # Interpret Escapes
        interpret_escapes=interpret_escapes,

        # Set the theme
        theme=theme,

        # Async mode allows a user to send all of their notifications
        # asynchronously. This was made an option incase there are problems
        # in the future where it is better that everything runs sequentially/
        # synchronously instead.
        async_mode=disable_async is not True,

        # Load our plugins
        plugin_paths=plugin_path,
    )

    # Create our Apprise object
    a = Apprise(asset=asset, debug=debug, location=ContentLocation.LOCAL)

    if details:
        # Print details and exit
        results = a.details(show_requirements=True, show_disabled=True)

        # Sort our results:
        plugins = sorted(
            results['schemas'], key=lambda i: str(i['service_name']))
        for entry in plugins:
            protocols = [] if not entry['protocols'] else \
                [p for p in entry['protocols']
                 if isinstance(p, str)]
            protocols.extend(
                [] if not entry['secure_protocols'] else
                [p for p in entry['secure_protocols']
                 if isinstance(p, str)])

            if len(protocols) == 1:
                # Simplify view by swapping {schema} with the single
                # protocol value

                # Convert tuple to list
                entry['details']['templates'] = \
                    list(entry['details']['templates'])

                for x in range(len(entry['details']['templates'])):
                    entry['details']['templates'][x] = \
                        re.sub(
                            r'^[^}]+}://',
                            '{}://'.format(protocols[0]),
                            entry['details']['templates'][x])

            fg = "green" if entry['enabled'] else "red"
            if entry['category'] == 'custom':
                # Identify these differently
                fg = "cyan"
                # Flip the enable switch so it forces the requirements
                # to be displayed
                entry['enabled'] = False

            click.echo(click.style(
                '{} {:<30} '.format(
                    '+' if entry['enabled'] else '-',
                    str(entry['service_name'])), fg=fg, bold=True),
                nl=(not entry['enabled'] or len(protocols) == 1))

            if not entry['enabled']:
                if entry['requirements']['details']:
                    click.echo(
                        '   ' + str(entry['requirements']['details']))

                if entry['requirements']['packages_required']:
                    click.echo('   Python Packages Required:')
                    for req in entry['requirements']['packages_required']:
                        click.echo('     - ' + req)

                if entry['requirements']['packages_recommended']:
                    click.echo('   Python Packages Recommended:')
                    for req in entry['requirements']['packages_recommended']:
                        click.echo('     - ' + req)

                # new line padding between entries
                if entry['category'] == 'native':
                    click.echo()
                    continue

            if len(protocols) > 1:
                click.echo('| Schema(s): {}'.format(
                    ', '.join(protocols),
                ))

            prefix = '   - '
            click.echo('{}{}'.format(
                prefix,
                '\n{}'.format(prefix).join(entry['details']['templates'])))

            # new line padding between entries
            click.echo()

        sys.exit(0)
        # end if details()

    # The priorities of what is accepted are parsed in order below:
    #    1. URLs by command line
    #    2. Configuration by command line
    #    3. URLs by environment variable: APPRISE_URLS
    #    4. Configuration by environment variable: APPRISE_CONFIG
    #    5. Default Configuration File(s) (if found)
    #
    if urls:
        if tag:
            # Ignore any tags specified
            logger.warning(
                '--tag (-g) entries are ignored when using specified URLs')
            tag = None

        # Load our URLs (if any defined)
        for url in urls:
            a.add(url)

        if config:
            # Provide a warning to the end user if they specified both
            logger.warning(
                'You defined both URLs and a --config (-c) entry; '
                'Only the URLs will be referenced.')

    elif config:
        # We load our configuration file(s) now only if no URLs were specified
        # Specified config entries trump all
        a.add(AppriseConfig(
            paths=config, asset=asset, recursion=recursion_depth))

    elif os.environ.get('APPRISE_URLS', '').strip():
        logger.debug('Loading provided APPRISE_URLS environment variable')
        if tag:
            # Ignore any tags specified
            logger.warning(
                '--tag (-g) entries are ignored when using specified URLs')
            tag = None

        # Attempt to use our APPRISE_URLS environment variable (if populated)
        a.add(os.environ['APPRISE_URLS'].strip())

    elif os.environ.get('APPRISE_CONFIG', '').strip():
        logger.debug('Loading provided APPRISE_CONFIG environment variable')
        # Fall back to config environment variable (if populated)
        a.add(AppriseConfig(
            paths=os.environ['APPRISE_CONFIG'].strip(),
            asset=asset, recursion=recursion_depth))

    else:
        # Load default configuration
        a.add(AppriseConfig(
            paths=[f for f in DEFAULT_CONFIG_PATHS if isfile(expanduser(f))],
            asset=asset, recursion=recursion_depth))

    if len(a) == 0 and not urls:
        logger.error(
            'You must specify at least one server URL or populated '
            'configuration file.')
        print_help_msg(main)
        sys.exit(1)

    # each --tag entry comprises of a comma separated 'and' list
    # we or each of of the --tag and sets specified.
    tags = None if not tag else [parse_list(t) for t in tag]

    if not dry_run:
        if body is None:
            logger.trace('No --body (-b) specified; reading from stdin')
            # if no body was specified, then read from STDIN
            body = click.get_text_stream('stdin').read()

        # now print it out
        result = a.notify(
            body=body, title=title, notify_type=notification_type, tag=tags,
            attach=attach)
    else:
        # Number of rows to assume in the terminal.  In future, maybe this can
        # be detected and made dynamic. The actual row count is 80, but 5
        # characters are already reserved for the counter on the left
        rows = 75

        # Initialize our URL response;  This is populated within the for/loop
        # below; but plays a factor at the end when we need to determine if
        # we iterated at least once in the loop.
        url = None

        for idx, server in enumerate(a.find(tag=tags)):
            url = server.url(privacy=True)
            click.echo("{: 3d}. {}".format(
                idx + 1,
                url if len(url) <= rows else '{}...'.format(url[:rows - 3])))
            if server.tags:
                click.echo("{} - {}".format(' ' * 5, ', '.join(server.tags)))

        # Initialize a default response of nothing matched, otherwise
        # if we matched at least one entry, we can return True
        result = None if url is None else True

    if result is None:
        # There were no notifications set.  This is a result of just having
        # empty configuration files and/or being to restrictive when filtering
        # by specific tag(s)

        # Exit code 3 is used since Click uses exit code 2 if there is an
        # error with the parameters specified
        sys.exit(3)

    elif result is False:
        # At least 1 notification service failed to send
        sys.exit(1)

    # else:  We're good!
    sys.exit(0)
