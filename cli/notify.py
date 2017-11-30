#!/usr/bin/env python
# -*- coding: utf-8 -*-
import click
import logging
import sys

from apprise import Apprise
from apprise import AppriseAsset
from apprise import NotifyType

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Defines our click context settings adding -h to the additional options that
# can be specified to get the help menu to come up
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


def print_help_msg(command):
    """
    Prints help message when -h or --help is specified.

    """
    with click.Context(command) as ctx:
        click.echo(command.get_help(ctx))


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--title', '-t', default=None, type=str,
              help='Specify the message title.')
@click.option('--body', '-b', default=None, type=str,
              help='Specify the message body.')
@click.option('--notification-type', '-t', default=NotifyType.INFO, type=str,
              metavar='TYPE', help='Specify the message type (default=info).')
@click.option('--theme', '-T', default='default', type=str,
              help='Specify the default theme.')
@click.argument('urls', nargs=-1,
                metavar='SERVER_URL [SERVER_URL2 [SERVER_URL3]]',)
def _main(title, body, urls, notification_type, theme):
    """
    Send a notification to all of the specified servers identified by their
    URLs the content provided within the title, body and notification-type.

    """
    if not urls:
        logger.error('You must specify at least one server URL.')
        print_help_msg(_main)
        return 1

    # Prepare our asset
    asset = AppriseAsset(theme=theme)

    # Create our object
    apprise = Apprise(asset=asset)

    # Load our inventory up
    for url in urls:
        apprise.add(url)

    if body is None:
        # if no body was specified, then read from STDIN
        body = click.get_text_stream('stdin').read()

    # now print it out
    apprise.notify(title=title, body=body, notify_type=notification_type)

    return 0


if __name__ == '__main__':
    exit(_main())
