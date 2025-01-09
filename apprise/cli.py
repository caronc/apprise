# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import click
import textwrap
import logging
import platform
import sys
import os
import shutil
import re

from os.path import isfile
from os.path import exists

from . import Apprise
from . import AppriseAsset
from . import AppriseConfig
from . import PersistentStore

from .utils.parse import parse_list
from .utils.disk import dir_size, bytes_to_str, path_decode
from .common import NOTIFY_TYPES
from .common import NOTIFY_FORMATS
from .common import PERSISTENT_STORE_MODES
from .common import PersistentStoreState
from .common import ContentLocation
from .logger import logger

from . import __title__
from . import __version__
from . import __license__
from . import __copywrite__

# By default we allow looking 1 level down recursivly in Apprise configuration
# files.
DEFAULT_RECURSION_DEPTH = 1

# Default number of days to prune persistent storage
DEFAULT_STORAGE_PRUNE_DAYS = \
    int(os.environ.get('APPRISE_STORAGE_PRUNE_DAYS', 30))

# The default URL ID Length
DEFAULT_STORAGE_UID_LENGTH = \
    int(os.environ.get('APPRISE_STORAGE_UID_LENGTH', 8))

# Defines the envrionment variable to parse if defined. This is ONLY
# Referenced if:
# - No Configuration Files were found/loaded/specified
# - No URLs were provided directly into the CLI Call
DEFAULT_ENV_APPRISE_URLS = 'APPRISE_URLS'

# Defines the over-ride path for the configuration files read
DEFAULT_ENV_APPRISE_CONFIG_PATH = 'APPRISE_CONFIG_PATH'

# Defines the over-ride path for the plugins to load
DEFAULT_ENV_APPRISE_PLUGIN_PATH = 'APPRISE_PLUGIN_PATH'

# Defines the over-ride path for the persistent storage
DEFAULT_ENV_APPRISE_STORAGE_PATH = 'APPRISE_STORAGE_PATH'

# Defines our click context settings adding -h to the additional options that
# can be specified to get the help menu to come up
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

# Define our default configuration we use if nothing is otherwise specified
DEFAULT_CONFIG_PATHS = (
    # Legacy Path Support
    '~/.apprise',
    '~/.apprise.conf',
    '~/.apprise.yml',
    '~/.apprise.yaml',
    '~/.config/apprise',
    '~/.config/apprise.conf',
    '~/.config/apprise.yml',
    '~/.config/apprise.yaml',

    # Plugin Support Extended Directory Search Paths
    '~/.apprise/apprise',
    '~/.apprise/apprise.conf',
    '~/.apprise/apprise.yml',
    '~/.apprise/apprise.yaml',
    '~/.config/apprise/apprise',
    '~/.config/apprise/apprise.conf',
    '~/.config/apprise/apprise.yml',
    '~/.config/apprise/apprise.yaml',

    # Global Configuration File Support
    '/etc/apprise',
    '/etc/apprise.yml',
    '/etc/apprise.yaml',
    '/etc/apprise/apprise',
    '/etc/apprise/apprise.conf',
    '/etc/apprise/apprise.yml',
    '/etc/apprise/apprise.yaml',
)

# Define our paths to search for plugins
DEFAULT_PLUGIN_PATHS = (
    '~/.apprise/plugins',
    '~/.config/apprise/plugins',

    # Global Plugin Support
    '/var/lib/apprise/plugins',
)

#
# Persistent Storage
#
DEFAULT_STORAGE_PATH = '~/.local/share/apprise/cache'

# Detect Windows
if platform.system() == 'Windows':
    # Default Config Search Path for Windows Users
    DEFAULT_CONFIG_PATHS = (
        '%APPDATA%\\Apprise\\apprise',
        '%APPDATA%\\Apprise\\apprise.conf',
        '%APPDATA%\\Apprise\\apprise.yml',
        '%APPDATA%\\Apprise\\apprise.yaml',
        '%LOCALAPPDATA%\\Apprise\\apprise',
        '%LOCALAPPDATA%\\Apprise\\apprise.conf',
        '%LOCALAPPDATA%\\Apprise\\apprise.yml',
        '%LOCALAPPDATA%\\Apprise\\apprise.yaml',

        #
        # Global Support
        #

        # C:\ProgramData\Apprise
        '%ALLUSERSPROFILE%\\Apprise\\apprise',
        '%ALLUSERSPROFILE%\\Apprise\\apprise.conf',
        '%ALLUSERSPROFILE%\\Apprise\\apprise.yml',
        '%ALLUSERSPROFILE%\\Apprise\\apprise.yaml',

        # C:\Program Files\Apprise
        '%PROGRAMFILES%\\Apprise\\apprise',
        '%PROGRAMFILES%\\Apprise\\apprise.conf',
        '%PROGRAMFILES%\\Apprise\\apprise.yml',
        '%PROGRAMFILES%\\Apprise\\apprise.yaml',

        # C:\Program Files\Common Files
        '%COMMONPROGRAMFILES%\\Apprise\\apprise',
        '%COMMONPROGRAMFILES%\\Apprise\\apprise.conf',
        '%COMMONPROGRAMFILES%\\Apprise\\apprise.yml',
        '%COMMONPROGRAMFILES%\\Apprise\\apprise.yaml',
    )

    # Default Plugin Search Path for Windows Users
    DEFAULT_PLUGIN_PATHS = (
        '%APPDATA%\\Apprise\\plugins',
        '%LOCALAPPDATA%\\Apprise\\plugins',

        #
        # Global Support
        #

        # C:\ProgramData\Apprise\plugins
        '%ALLUSERSPROFILE%\\Apprise\\plugins',
        # C:\Program Files\Apprise\plugins
        '%PROGRAMFILES%\\Apprise\\plugins',
        # C:\Program Files\Common Files
        '%COMMONPROGRAMFILES%\\Apprise\\plugins',
    )

    #
    # Persistent Storage
    #
    DEFAULT_STORAGE_PATH = '%APPDATA%/Apprise/cache'


class PersistentStorageMode:
    """
    Persistent Storage Modes
    """
    # List all detected configuration loaded
    LIST = 'list'

    # Prune persistent storage based on age
    PRUNE = 'prune'

    # Reset all (reguardless of age)
    CLEAR = 'clear'


# Define the types in a list for validation purposes
PERSISTENT_STORAGE_MODES = (
    PersistentStorageMode.LIST,
    PersistentStorageMode.PRUNE,
    PersistentStorageMode.CLEAR,
)

if os.environ.get('APPRISE_STORAGE_PATH', '').strip():
    # Over-ride Default Storage Path
    DEFAULT_STORAGE_PATH = os.environ.get('APPRISE_STORAGE_PATH')


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


class CustomHelpCommand(click.Command):
    def format_help(self, ctx, formatter):
        formatter.write_text('Usage:')
        formatter.write_text(
            '   apprise [OPTIONS] [APPRISE_URL [APPRISE_URL2 [APPRISE_URL3]]]')
        formatter.write_text(
            '   apprise storage [OPTIONS] [ACTION] [UID1 [UID2 [UID3]]]')

        # Custom help message
        formatter.write_text('')
        content = (
            'Send a notification to all of the specified servers '
            'identified by their URLs',
            'the content provided within the title, body and '
            'notification-type.',
            '',
            'For a list of all of the supported services and information on '
            'how to use ',
            'them, check out at https://github.com/caronc/apprise')

        for line in content:
            formatter.write_text(line)

        # Display options and arguments in the default format
        self.format_options(ctx, formatter)
        self.format_epilog(ctx, formatter)

        # Custom 'Actions:' section after the 'Options:'
        formatter.write_text('')
        formatter.write_text('Actions:')

        actions = [(
            'storage', 'Access the persistent storage disk administration',
            [(
                'list',
                'List all URL IDs associated with detected URL(s). '
                'This is also the default action ran if nothing is provided',
            ), (
                'prune',
                'Eliminates stale entries found based on '
                '--storage-prune-days (-SPD)',
            ), (
                'clean',
                'Removes any persistent data created by Apprise',
            )],
        )]

        #
        # Some variables
        #

        # actions are indented this many spaces
        # sub actions double this value
        action_indent = 2

        # label padding (for alignment)
        action_label_width = 10

        space = ' '
        space_re = re.compile(r'\r*\n')
        cols = 80
        indent = 10

        # Format each action and its subactions
        for action, description, sub_actions in actions:
            # Our action indent
            ai = ' ' * action_indent
            # Format the main action description
            formatted_description = space_re.split(textwrap.fill(
                description, width=(cols - indent - action_indent),
                initial_indent=space * indent,
                subsequent_indent=space * indent))
            for no, line in enumerate(formatted_description):
                if not no:
                    formatter.write_text(
                        f'{ai}{action:<{action_label_width}}{line}')

                else:  # pragma: no cover
                    # Note: no branch is set intentionally since this is not
                    #       tested since in 2025.08.13 when this was set up
                    #       it never entered this area of the code.  But we
                    #       know it works because we repeat this process with
                    #       our sub-options below
                    formatter.write_text(
                        f'{ai}{space:<{action_label_width}}{line}')

            # Format each subaction
            ai = ' ' * (action_indent * 2)
            for action, description in sub_actions:
                formatted_description = space_re.split(textwrap.fill(
                    description, width=(cols - indent - (action_indent * 3)),
                    initial_indent=space * (indent - action_indent),
                    subsequent_indent=space * (indent - action_indent)))

                for no, line in enumerate(formatted_description):
                    if not no:
                        formatter.write_text(
                            f'{ai}{action:<{action_label_width}}{line}')
                    else:
                        formatter.write_text(
                            f'{ai}{space:<{action_label_width}}{line}')

        # Include any epilog or additional text
        self.format_epilog(ctx, formatter)


@click.command(context_settings=CONTEXT_SETTINGS, cls=CustomHelpCommand)
@click.option('--body', '-b', default=None, type=str,
              help='Specify the message body. If no body is specified then '
              'content is read from <stdin>.')
@click.option('--title', '-t', default=None, type=str,
              help='Specify the message title. This field is complete '
              'optional.')
@click.option('--plugin-path', '-P', default=None, type=str, multiple=True,
              metavar='PATH',
              help='Specify one or more plugin paths to scan.')
@click.option('--storage-path', '-S', default=DEFAULT_STORAGE_PATH, type=str,
              metavar='PATH',
              help='Specify the path to the persistent storage location '
              '(default={}).'.format(DEFAULT_STORAGE_PATH))
@click.option('--storage-prune-days', '-SPD',
              default=DEFAULT_STORAGE_PRUNE_DAYS, type=int,
              help='Define the number of days the storage prune '
              'should run using. Setting this to zero (0) will eliminate '
              'all accumulated content. By default this value is {} days.'
              .format(DEFAULT_STORAGE_PRUNE_DAYS))
@click.option('--storage-uid-length', '-SUL',
              default=DEFAULT_STORAGE_UID_LENGTH, type=int,
              help='Define the number of unique characters to store persistent'
              'cache in. By default this value is {} characters.'
              .format(DEFAULT_STORAGE_UID_LENGTH))
@click.option('--storage-mode', '-SM', default=PERSISTENT_STORE_MODES[0],
              type=str, metavar='MODE',
              help='Specify the persistent storage operational mode '
              '(default={}). Possible values are "{}", and "{}".'.format(
                  PERSISTENT_STORE_MODES[0], '", "'.join(
                      PERSISTENT_STORE_MODES[:-1]),
                  PERSISTENT_STORE_MODES[-1]))
@click.option('--config', '-c', default=None, type=str, multiple=True,
              metavar='CONFIG_URL',
              help='Specify one or more configuration locations.')
@click.option('--attach', '-a', default=None, type=str, multiple=True,
              metavar='ATTACHMENT_URL',
              help='Specify one or more attachment.')
@click.option('--notification-type', '-n', default=NOTIFY_TYPES[0], type=str,
              metavar='TYPE',
              help='Specify the message type (default={}). '
              'Possible values are "{}", and "{}".'.format(
                  NOTIFY_TYPES[0], '", "'.join(NOTIFY_TYPES[:-1]),
                  NOTIFY_TYPES[-1]))
@click.option('--input-format', '-i', default=NOTIFY_FORMATS[0], type=str,
              metavar='FORMAT',
              help='Specify the message input format (default={}). '
              'Possible values are "{}", and "{}".'.format(
                  NOTIFY_FORMATS[0], '", "'.join(NOTIFY_FORMATS[:-1]),
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
@click.option('--interpret-emojis', '-j', is_flag=True,
              help='Enable interpretation of :emoji: definitions')
@click.option('--debug', '-D', is_flag=True, help='Debug mode')
@click.option('--version', '-V', is_flag=True,
              help='Display the apprise version and exit.')
@click.argument('urls', nargs=-1,
                metavar='SERVER_URL [SERVER_URL2 [SERVER_URL3]]',)
@click.pass_context
def main(ctx, body, title, config, attach, urls, notification_type, theme, tag,
         input_format, dry_run, recursion_depth, verbose, disable_async,
         details, interpret_escapes, interpret_emojis, plugin_path,
         storage_path, storage_mode, storage_prune_days, storage_uid_length,
         debug, version):
    """
    Send a notification to all of the specified servers identified by their
    URLs the content provided within the title, body and notification-type.

    For a list of all of the supported services and information on how to
    use them, check out at https://github.com/caronc/apprise
    """
    # Note: Click ignores the return values of functions it wraps, If you
    #       want to return a specific error code, you must call ctx.exit()
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
        ctx.exit(0)

    # Simple Error Checking
    notification_type = notification_type.strip().lower()
    if notification_type not in NOTIFY_TYPES:
        click.echo(
            'The --notification-type (-n) value of {} is not supported.'
            .format(notification_type))
        click.echo("Try 'apprise --help' for more information.")
        # 2 is the same exit code returned by Click if there is a parameter
        # issue.  For consistency, we also return a 2
        ctx.exit(2)

    input_format = input_format.strip().lower()
    if input_format not in NOTIFY_FORMATS:
        click.echo(
            'The --input-format (-i) value of {} is not supported.'
            .format(input_format))
        click.echo("Try 'apprise --help' for more information.")
        # 2 is the same exit code returned by Click if there is a parameter
        # issue.  For consistency, we also return a 2
        ctx.exit(2)

    storage_mode = storage_mode.strip().lower()
    if storage_mode not in PERSISTENT_STORE_MODES:
        click.echo(
            'The --storage-mode (-SM) value of {} is not supported.'
            .format(storage_mode))
        click.echo("Try 'apprise --help' for more information.")
        # 2 is the same exit code returned by Click if there is a parameter
        # issue.  For consistency, we also return a 2
        ctx.exit(2)

    #
    # Apply Environment Over-rides if defined
    #
    _config_paths = DEFAULT_CONFIG_PATHS
    if 'APPRISE_CONFIG' in os.environ:
        # Deprecate (this was from previous versions of Apprise <= 1.9.1)
        logger.deprecate(
            'APPRISE_CONFIG environment variable has been changed to '
            f'{DEFAULT_ENV_APPRISE_CONFIG_PATH}')
        logger.debug(
            'Loading provided APPRISE_CONFIG (deprecated) environment '
            'variable')
        _config_paths = (os.environ.get('APPRISE_CONFIG', '').strip(), )

    elif DEFAULT_ENV_APPRISE_CONFIG_PATH in os.environ:
        logger.debug(
            f'Loading provided {DEFAULT_ENV_APPRISE_CONFIG_PATH} '
            'environment variable')
        _config_paths = re.split(
            r'[\r\n;]+', os.environ.get(
                DEFAULT_ENV_APPRISE_CONFIG_PATH).strip())

    _plugin_paths = DEFAULT_PLUGIN_PATHS
    if DEFAULT_ENV_APPRISE_PLUGIN_PATH in os.environ:
        logger.debug(
            f'Loading provided {DEFAULT_ENV_APPRISE_PLUGIN_PATH} environment '
            'variable')
        _plugin_paths = re.split(
            r'[\r\n;]+', os.environ.get(
                DEFAULT_ENV_APPRISE_PLUGIN_PATH).strip())

    if DEFAULT_ENV_APPRISE_STORAGE_PATH in os.environ:
        logger.debug(
            f'Loading provided {DEFAULT_ENV_APPRISE_STORAGE_PATH} environment '
            'variable')
        storage_path = \
            os.environ.get(DEFAULT_ENV_APPRISE_STORAGE_PATH).strip()

    #
    # Continue with initialization process
    #

    # Prepare a default set of plugin paths to scan; anything specified
    # on the CLI always trumps
    plugin_paths = \
        [path for path in _plugin_paths if exists(path_decode(path))] \
        if not plugin_path else plugin_path

    if storage_uid_length < 2:
        click.echo(
            'The --storage-uid-length (-SUL) value can not be lower '
            'then two (2).')
        click.echo("Try 'apprise --help' for more information.")

        # 2 is the same exit code returned by Click if there is a
        # parameter issue.  For consistency, we also return a 2
        ctx.exit(2)

    # Prepare our asset
    asset = AppriseAsset(
        # Our body format
        body_format=input_format,

        # Interpret Escapes
        interpret_escapes=interpret_escapes,

        # Interpret Emojis
        interpret_emojis=None if not interpret_emojis else True,

        # Set the theme
        theme=theme,

        # Async mode allows a user to send all of their notifications
        # asynchronously. This was made an option incase there are problems
        # in the future where it is better that everything runs sequentially/
        # synchronously instead.
        async_mode=disable_async is not True,

        # Load our plugins
        plugin_paths=plugin_paths,

        # Load our persistent storage path
        storage_path=path_decode(storage_path),

        # Our storage URL ID Length
        storage_idlen=storage_uid_length,

        # Define if we flush to disk as soon as possible or not when required
        storage_mode=storage_mode
    )

    # Create our Apprise object
    a = Apprise(asset=asset, debug=debug, location=ContentLocation.LOCAL)

    # Track if we are performing a storage action
    storage_action = True if urls and 'storage'.startswith(urls[0]) else False

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

        ctx.exit(0)
        # end if details()

    # The priorities of what is accepted are parsed in order below:
    #    1. URLs by command line
    #    2. Configuration by command line
    #    3. URLs by environment variable: APPRISE_URLS
    #    4. Default Configuration File(s)
    #
    elif urls and not storage_action:
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

    elif os.environ.get(DEFAULT_ENV_APPRISE_URLS, '').strip():
        logger.debug(
            f'Loading provided {DEFAULT_ENV_APPRISE_URLS} environment '
            'variable')
        if tag:
            # Ignore any tags specified
            logger.warning(
                '--tag (-g) entries are ignored when using specified URLs')
            tag = None

        # Attempt to use our APPRISE_URLS environment variable (if populated)
        a.add(os.environ[DEFAULT_ENV_APPRISE_URLS].strip())

    else:
        # Load default configuration
        a.add(AppriseConfig(
            paths=[f for f in _config_paths if isfile(path_decode(f))],
            asset=asset, recursion=recursion_depth))

    if not dry_run and not (a or storage_action):
        click.echo(
            'You must specify at least one server URL or populated '
            'configuration file.')
        click.echo("Try 'apprise --help' for more information.")
        ctx.exit(1)

    # each --tag entry comprises of a comma separated 'and' list
    # we or each of of the --tag and sets specified.
    tags = None if not tag else [parse_list(t) for t in tag]

    # Determine if we're dealing with URLs or url_ids based on the first
    # entry provided.
    if storage_action:
        #
        # Storage Mode
        #  - urls are now to be interpreted as best matching namespaces
        #
        if storage_prune_days < 0:
            click.echo(
                'The --storage-prune-days (-SPD) value can not be lower '
                'then zero (0).')
            click.echo("Try 'apprise --help' for more information.")

            # 2 is the same exit code returned by Click if there is a
            # parameter issue.  For consistency, we also return a 2
            ctx.exit(2)

        # Number of columns to assume in the terminal.  In future, maybe this
        # can be detected and made dynamic. The actual column count is 80, but
        # 5 characters are already reserved for the counter on the left
        (columns, _) = shutil.get_terminal_size(fallback=(80, 24))

        # Pop 'storage' off of the head of our list
        filter_uids = urls[1:]

        action = PERSISTENT_STORAGE_MODES[0]
        if filter_uids:
            _action = next(  # pragma: no branch
                (a for a in PERSISTENT_STORAGE_MODES
                 if a.startswith(filter_uids[0])), None)

            if _action:
                # pop 'action' off the head of our list
                filter_uids = filter_uids[1:]
                action = _action

        # Get our detected URL IDs
        uids = {}
        for plugin in (a if not tags else a.find(tag=tags)):
            _id = plugin.url_id()
            if not _id:
                continue

            if filter_uids and next(
                    (False for n in filter_uids if _id.startswith(n)), True):
                continue

            if _id not in uids:
                uids[_id] = {
                    'plugins': [plugin],
                    'state': PersistentStoreState.UNUSED,
                    'size': 0,
                }

            else:
                # It's possible to have more then one URL point to the same
                # location (thus match against the same url id more then once
                uids[_id]['plugins'].append(plugin)

        if action == PersistentStorageMode.LIST:
            detected_uid = PersistentStore.disk_scan(
                # Use our asset path as it has already been properly parsed
                path=asset.storage_path,

                # Provide filter if specified
                namespace=filter_uids,
            )
            for _id in detected_uid:
                size, _ = dir_size(os.path.join(asset.storage_path, _id))
                if _id in uids:
                    uids[_id]['state'] = PersistentStoreState.ACTIVE
                    uids[_id]['size'] = size

                elif not tags:
                    uids[_id] = {
                        'plugins': [],
                        # No cross reference (wasted space?)
                        'state': PersistentStoreState.STALE,
                        # Acquire disk space
                        'size': size,
                    }

            for idx, (uid, meta) in enumerate(uids.items()):
                fg = "green" \
                    if meta['state'] == PersistentStoreState.ACTIVE else (
                        "red"
                        if meta['state'] == PersistentStoreState.STALE else
                        "white")

                if idx > 0:
                    # New line
                    click.echo()
                click.echo("{: 4d}. ".format(idx + 1), nl=False)
                click.echo(click.style("{:<52} {:<8} {}".format(
                    uid, bytes_to_str(meta['size']), meta['state']),
                    fg=fg, bold=True))

                for entry in meta['plugins']:
                    url = entry.url(privacy=True)
                    click.echo("{:>7} {}".format(
                        '-',
                        url if len(url) <= (columns - 8) else '{}...'.format(
                            url[:columns - 11])))

                    if entry.tags:
                        click.echo("{:>10}: {}".format(
                            'tags', ', '.join(entry.tags)))

        else:  # PersistentStorageMode.PRUNE or PersistentStorageMode.CLEAR
            if action == PersistentStorageMode.CLEAR:
                storage_prune_days = 0

            # clean up storage
            results = PersistentStore.disk_prune(
                # Use our asset path as it has already been properly parsed
                path=asset.storage_path,
                # Provide our namespaces if they exist
                namespace=None if not filter_uids else filter_uids,
                # Convert expiry from days to seconds
                expires=storage_prune_days * 60 * 60 * 24,
                action=not dry_run)

            ctx.exit(0)
            # end if disk_prune()

        ctx.exit(0)
        # end if storage()

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
        # Number of columns to assume in the terminal.  In future, maybe this
        # can be detected and made dynamic. The actual column count is 80, but
        # 5 characters are already reserved for the counter on the left
        (columns, _) = shutil.get_terminal_size(fallback=(80, 24))

        # Initialize our URL response;  This is populated within the for/loop
        # below; but plays a factor at the end when we need to determine if
        # we iterated at least once in the loop.
        url = None

        for idx, server in enumerate(a.find(tag=tags)):
            url = server.url(privacy=True)
            click.echo("{: 4d}. {}".format(
                idx + 1,
                url if len(url) <= (columns - 8) else '{}...'.format(
                    url[:columns - 9])))

            # Share our URL ID
            click.echo("{:>10}: {}".format(
                'uid', '- n/a -' if not server.url_id()
                else server.url_id()))

            if server.tags:
                click.echo("{:>10}: {}".format('tags', ', '.join(server.tags)))

        # Initialize a default response of nothing matched, otherwise
        # if we matched at least one entry, we can return True
        result = None if url is None else True

    if result is None:
        # There were no notifications set.  This is a result of just having
        # empty configuration files and/or being to restrictive when filtering
        # by specific tag(s)

        # Exit code 3 is used since Click uses exit code 2 if there is an
        # error with the parameters specified
        ctx.exit(3)

    elif result is False:
        # At least 1 notification service failed to send
        ctx.exit(1)

    # else:  We're good!
    ctx.exit(0)
