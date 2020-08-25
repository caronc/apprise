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

  * `-a`, `--attach=`<ATTACH-URL>:
    Specify one or more file attachment locations.

  * `-n`, `--notification-type=`<TYPE>:
    Specify the message type (default=info). Possible values are "info",
    "success", "failure", and "warning".

  * `-i`, `--input-format=`<FORMAT>:
    Specify the input message format (default=text). Possible values are "text",
    "html", and "markdown".

  * `-T`, `--theme=`THEME:
    Specify the default theme.

  * `-g`, `--tag=`TAG:
    Specify one or more tags to filter which services to notify. Use multiple
    **--tag** (**-g**) entries to `OR` the tags together and comma separated
    to `AND` them. If no tags are specified then all services are notified.

  * `-d`, `--dry-run`:
    Perform a trial run but only prints the notification services to-be
    triggered to **stdout**. Notifications are never sent using this mode.

  * `-v`, `--verbose`:
    The more of these you specify, the more verbose the output is.

  * `-Da`, `--disable-async`:
    Send notifications synchronously (one after the other) instead of
    all at once.

  * `-R`, `--recursion-depth`:
    he number of recursive import entries that can be loaded from within
    Apprise configuration. By default this is set to 1. If this is set to
    zero, then import statements found in any configuration is ignored.

  * `-D`, `--debug`:
    A debug mode; useful for troubleshooting.

  * `-V`, `--version`:
    Display the apprise version and exit.

  * `--help`:
    Show this message and exit.

## EXIT STATUS

**apprise** exits with a status 0 if all notifications were sent successfully otherwise **apprise** returns a value of 1. **apprise** returns a value of 2 if
there was an error specified on the command line (such as not providing an valid
argument).

**apprise** exits with a status of 3 if there were no notifcations sent due (as a result of end user actions).  This occurs in the case where you have assigned one or more tags to all of the Apprise URLs being notified and did not match any when actually executing the **apprise** tool.  This can also occur if you specified a tag that has not been assigned to anything defined in your configuration.


## SERVICE URLS

There are to many service URL and combinations to list here. It's best to
visit the [Apprise GitHub page][serviceurls] and see what's available.

[serviceurls]: https://github.com/caronc/apprise/wiki#notification-services

## EXAMPLES

Send a notification to as many servers as you want to specify as you can
easily chain them together:

    $ apprise -vv -t 'my title' -b 'my notification body' \
       'mailto://myemail:mypass@gmail.com' \
       'pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b'

If you don't specify a **--body** (**-b**) then stdin is used allowing you to
use the tool as part of your every day administration:

    $ cat /proc/cpuinfo | apprise -vv -t 'cpu info' \
        'mailto://myemail:mypass@gmail.com'

Load in a configuration file which identifies all of your notification service
URLs and notify them all:

    $ apprise -vv -t 'my title' -b 'my notification body' \
       --config=~/apprise.yml

Load in a configuration file from a remote server that identifies all of your
notification service URLs and only notify the ones tagged as _devops_.

    $ apprise -vv -t 'my title' -b 'my notification body' \
       --config=https://localhost/my/apprise/config \
       -t devops

Include an attachment:

    $ apprise -vv -t 'School Assignment' -b 'See attached' \
       --attach=Documents/FinalReport.docx

## BUGS

If you find any bugs, please make them known at:
<https://github.com/caronc/apprise/issues>

## COPYRIGHT

Apprise is Copyright (C) 2020 Chris Caron <lead2gold@gmail.com>
