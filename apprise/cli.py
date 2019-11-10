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
from os.path import isfile
from os.path import expanduser
from os.path import expandvars

from . import NotifyType
from . import Apprise
from . import AppriseAsset
from . import AppriseConfig
from .utils import parse_list
from .common import NOTIFY_TYPES
from .logger import logger

from . import __title__
from . import __version__
from . import __license__
from . import __copywrite__

# Defines our click context settings adding -h to the additional options that
# can be specified to get the help menu to come up
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

# Define our default configuration we use if nothing is otherwise specified
DEFAULT_SEARCH_PATHS = (
    '~/.apprise',
    '~/.apprise.yml',
    '~/.config/apprise',
    '~/.config/apprise.yml',
)

# Detect Windows
if platform.system() == 'Windows':
    # Default Search Path for Windows Users
    DEFAULT_SEARCH_PATHS = (
        expandvars('%APPDATA%/Apprise/apprise'),
        expandvars('%APPDATA%/Apprise/apprise.yml'),
        expandvars('%LOCALAPPDATA%/Apprise/apprise'),
        expandvars('%LOCALAPPDATA%/Apprise/apprise.yml'),
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
@click.option('--config', '-c', default=None, type=str, multiple=True,
              metavar='CONFIG_URL',
              help='Specify one or more configuration locations.')
@click.option('--attach', '-a', default=None, type=str, multiple=True,
              metavar='ATTACHMENT_URL',
              help='Specify one or more configuration locations.')
@click.option('--notification-type', '-n', default=NotifyType.INFO, type=str,
              metavar='TYPE',
              help='Specify the message type (default=info). Possible values'
              ' are "{}", and "{}".'.format(
                  '", "'.join(NOTIFY_TYPES[:-1]), NOTIFY_TYPES[-1]))
@click.option('--theme', '-T', default='default', type=str, metavar='THEME',
              help='Specify the default theme.')
@click.option('--tag', '-g', default=None, type=str, multiple=True,
              metavar='TAG', help='Specify one or more tags to filter '
              'which services to notify. Use multiple --tag (-g) entries to '
              '"OR" the tags together and comma separated to "AND" them. '
              'If no tags are specified then all services are notified.')
@click.option('--dry-run', '-d', is_flag=True,
              help='Perform a trial run but only prints the notification '
              'services to-be triggered to stdout. Notifications are never '
              'sent using this mode.')
@click.option('--verbose', '-v', count=True)
@click.option('--version', '-V', is_flag=True,
              help='Display the apprise version and exit.')
@click.argument('urls', nargs=-1,
                metavar='SERVER_URL [SERVER_URL2 [SERVER_URL3]]',)
def main(body, title, config, attach, urls, notification_type, theme, tag,
         dry_run, verbose, version):
    """
    Send a notification to all of the specified servers identified by their
    URLs the content provided within the title, body and notification-type.

    For a list of all of the supported services and information on how to
    use them, check out at https://github.com/caronc/apprise
    """
    # Note: Click ignores the return values of functions it wraps, If you
    #       want to return a specific error code, you must call sys.exit()
    #       as you will see below.

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

    if version:
        print_version_msg()
        sys.exit(0)

    # Prepare our asset
    asset = AppriseAsset(theme=theme)

    # Create our object
    a = Apprise(asset=asset)

    # Load our configuration if no URLs or specified configuration was
    # identified on the command line
    a.add(AppriseConfig(
        paths=[f for f in DEFAULT_SEARCH_PATHS if isfile(expanduser(f))]
        if not (config or urls) else config), asset=asset)

    # Load our inventory up
    for url in urls:
        a.add(url)

    if len(a) == 0:
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
        sys.exit(2)

    elif result is False:
        # At least 1 notification service failed to send
        sys.exit(1)

    # else:  We're good!
    sys.exit(0)
