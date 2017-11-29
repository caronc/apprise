#!/usr/bin/env python
# -*- coding: utf-8 -*-
import click
import logging
import sys

from apprise import Apprise

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


@click.command()
@click.option('--title', '-t', default=None, type=str,
              help='Specify the message title.')
@click.option('--body', '-b', default=None, type=str,
              help='Specify the message body.')
@click.option('--theme', '-T', default='default', type=str,
              help='Specify the default theme.')
@click.option('--image-url', '-i', default=None, type=str,
              help='Specify the image URL.')
@click.argument('urls', nargs=-1)
def _main(title, body, urls, theme, image_url):
    """
    Notify all specified servers

    """
    if not (title and body):
        logger.error('Neither a message body or title was specified.')
        return 1

    if not urls:
        logger.error('You must specify at least one server URL')
        return 1

    # Create our object
    apprise = Apprise()

    # Load our inventory up
    for url in urls:
        apprise.add(url)

    # now print it out
    apprise.notify(title=title, body=body)

    return 0
#    """\
#    Usage: apprise [options] [URL ...]
#
#    Send notifications to a variety of different supported services.
#    See also https://github.com/caronc/apprise
#
#    URL                       The notification service URL
#
#    Options:
#
#    -h, --help                show this message
#    -t TITLE, --title TITLE   Specify a notification title.
#    -b BODY, --body BODY      Specify a notification body.
#    -i IMGURL, --image IMGURL Specify an image to send with the notification.
#                              The image should be in the format of a URL
#                              string such as file:///local/path/to/file.png or
#                              a remote site like: http://my.host/my.image.png.
#    """


if __name__ == '__main__':
    exit(_main())
