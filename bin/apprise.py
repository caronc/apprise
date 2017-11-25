#!/usr/bin/env python


def _main():
    """\
    Usage: apprise [options] [URL ...]

    Send notifications to a variety of different supported services.
    See also https://github.com/caronc/apprise

    URL                       The notification service URL

    Options:

    -h, --help                show this message
    -t TITLE, --title TITLE   Specify a notification title.
    -b BODY, --body BODY      Specify a notification body.
    -i IMGURL, --image IMGURL Specify an image to send with the notification.
                              The image should be in the format of a URL
                              string such as file:///local/path/to/file.png or
                              a remote site like: http://my.host/my.image.png.
    """


if __name__ == '__main__':
    _main()
