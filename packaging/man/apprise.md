apprise(1) -- Push Notifications that work with just about every platform!
==========================================================================

## SYNOPSIS

`apprise` [<options>...] <service-url>...<br>

## DESCRIPTION

**Apprise** allows you to send a notification to _almost all_ of the most
popular notification services available to us today such as: Discord,
Telegram, Pushbullet, Slack, Twitter, etc.

  * One notification library to rule them all.
  * A common and intuitive notification syntax.
  * Supports the handling of images (to the notification services that will
    accept them).

## OPTIONS

The Apprise options are as follows:

  * `-b`, `--body=`<TEXT>:
    Specify the message body. If no body is specified then content is read from
    <stdin>.

  * `-t`, `--title=`<TEXT>:
    Specify the message title. This field is complete optional.

  * `-c`, `--config=`<CONFIG-URL>:
    Specify one or more configuration locations.

  * `-n`, `--notification-type=`<TYPE>:
    Specify the message type (default=info). Possible values are "info",
    "success", "failure", and "warning".

  * `-T`, `--theme=`THEME:
    Specify the default theme.

  * `-g`, `--tag=`TAG:
    Specify one or more tags to filter which services to notify. Use multiple
    **--tag** (**-g**) entries to `OR` the tags together and comma separated
    to `AND` them. If no tags are specified then all services are notified.

  * `-v`, `--verbose`:
    The more of these you specify, the more verbose the output is.

  * `-V`, `--version`:
    Display the apprise version and exit.

  * `--help`:
    Show this message and exit.

## SERVICE URLS

There are to many service URL and combinations to list here. It's best to
visit the [Apprise GitHub page][serviceurls] and see what's available.

[serviceurls]: https://github.com/caronc/apprise

## EXAMPLES

Send a notification to as many servers as you want to specify as you can
easily chain them together:

    $ apprise -t 'my title' -b 'my notification body' \
       'mailto://myemail:mypass@gmail.com' \
       'pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b'

If you don't specify a **--body** (**-b**) then stdin is used allowing you to
use the tool as part of your every day administration:

    $ cat /proc/cpuinfo | apprise -t 'cpu info' \
        'mailto://myemail:mypass@gmail.com'

Load in a configuration file which identifies all of your notification service
URLs and notify them all:

    $ apprise -t 'my title' -b 'my notification body' \
       --config=~/apprise.yml

Load in a configuration file from a remote server that identifies all of your
notification service URLs and only notify the ones tagged as _devops_.

    $ apprise -t 'my title' -b 'my notification body' \
       --config=https://localhost/my/apprise/config \
       -t devops

## BUGS

**Apprise** is written in Python with 100% test coverage; but it still makes
it far from perfect since the notification services it talks to change
all the time. If you find any bugs, please make them known at:
<https://github.com/caronc/apprise/issues>

## COPYRIGHT

Apprise is Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
