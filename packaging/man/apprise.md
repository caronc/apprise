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

  `-b`, `--body=`<TEXT>:
  Specify the message body. If no body is specified then content is read from
  <stdin>.

  `-t`, `--title=`<TEXT>:
  Specify the message title. This field is complete optional.

  `-c`, `--config=`<CONFIG-URL>:
  Specify one or more configuration locations.

  `-a`, `--attach=`<ATTACH-URL>:
  Specify one or more file attachment locations.

  `-P`, `--plugin-path=`<PLUGIN-PATH>:
  Specify a path to scan for custom notification plugin support.
  You can create your own notification by simply creating a Python file
  that contains the `@notify("schema")` decorator.

  You can optioanly chose to specify more then one **--plugin-path** (**-P**)
  to increase the modules included.

  `-n`, `--notification-type=`<TYPE>:
  Specify the message type (default=info). Possible values are "info",
  "success", "failure", and "warning".

  `-i`, `--input-format=`<FORMAT>:
  Specify the input message format (default=text). Possible values are "text",
  "html", and "markdown".

  `-T`, `--theme=`THEME:
  Specify the default theme.

  `-g`, `--tag=`TAG:
  Specify one or more tags to filter which services to notify. Use multiple
  **--tag** (**-g**) entries to `OR` the tags together and comma separated
  to `AND` them. If no tags are specified then all services are notified.

  `-Da`, `--disable-async`:
  Send notifications synchronously (one after the other) instead of
  all at once.

  `-R`, `--recursion-depth`:
  he number of recursive import entries that can be loaded from within
  Apprise configuration. By default this is set to 1. If this is set to
  zero, then import statements found in any configuration is ignored.

  `-e`, `--interpret-escapes`
  Enable interpretation of backslash escapes. For example, this would convert
  sequences such as \n and \r to their respected ascii new-line and carriage

  `-d`, `--dry-run`:
  Perform a trial run but only prints the notification services to-be
  triggered to **stdout**. Notifications are never sent using this mode.

  return characters prior to the delivery of the notification.

  `-l`, `--details`
  Prints details about the current services supported by Apprise.

  `-v`, `--verbose`:
  The more of these you specify, the more verbose the output is. e.g: -vvvv

  `-D`, `--debug`:
  A debug mode; useful for troubleshooting.

  `-V`, `--version`:
  Display the apprise version and exit.

  `-h`, `--help`:
  Show this message and exit.

## EXIT STATUS

**apprise** exits with a status of:

* **0** if all of the notifications were sent successfully.
* **1** if one or more notifications could not be sent.
* **2** if there was an error specified on the command line such as not
  providing an valid argument.
* **3** if there was one or more Apprise Service URLs successfully
  loaded but none could be notified due to user filtering (via tags).

## SERVICE URLS

There are to many service URL and combinations to list here. It's best to
visit the [Apprise GitHub page][serviceurls] and see what's available.

[serviceurls]: https://github.com/caronc/apprise/wiki#notification-services

## EXAMPLES

Send a notification to as many servers as you want to specify as you can
easily chain them together:

    $ apprise -vv -t "my title" -b "my notification body" \
       "mailto://myemail:mypass@gmail.com" \
       "pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b"

If you don't specify a **--body** (**-b**) then stdin is used allowing you to
use the tool as part of your every day administration:

    $ cat /proc/cpuinfo | apprise -vv -t "cpu info" \
        "mailto://myemail:mypass@gmail.com"

Load in a configuration file which identifies all of your notification service
URLs and notify them all:

    $ apprise -vv -t "my title" -b "my notification body" \
       --config=~/apprise.yml

Load in a configuration file from a remote server that identifies all of your
notification service URLs and only notify the ones tagged as _devops_.

    $ apprise -vv -t "my title" -b "my notification body" \
       --config=https://localhost/my/apprise/config \
       -t devops

Include an attachment:

    $ apprise -vv -t "School Assignment" -b "See attached" \
       --attach=Documents/FinalReport.docx

## CUSTOM PLUGIN/NOTIFICATIONS
Apprise can additionally allow you to define your own custom **schema://**
entries that you can trigger on and call services you've defined.

By default **apprise** looks in the following local locations for custom plugin
files and loads them:

    ~/.apprise/plugins
    ~/.config/apprise/plugins

Simply create your own python file with the following bare minimum content in
it:
    from apprise.decorators import notify

    # This example assumes you want your function to trigger on foobar://
    # references:
    @notify(on="foobar", name="My Custom Notification")
    def my_wrapper(body, title, notify_type, *args, **kwargs):
    
         <define your custom code here>
   
    		# Returning True/False is a way to relay your status back to Apprise.
    		# Returning nothing (None by default) is always interpreted as a Success
         return True

## CONFIGURATION

A configuration file can be in the format of either **TEXT** or **YAML** where
[TEXT][textconfig] is the easiest and most ideal solution for most users.  However
[YAML][yamlconfig] configuration files grants the user a bit more leverage and access
to some of the internal features of Apprise. Reguardless of which format you choose,
both provide the users the ability to leverage **tagging** which adds a more rich and
powerful notification environment.

Configuration files can be directly referenced via **apprise** when referencing
the `--config=` (`-c`) CLI directive.  You can identify as many as you like on the
command line and all of them will be loaded.  You can also point your configuration to
a cloud location (by referencing `http://` or `https://`. By default **apprise** looks
in the following local locations for configuration files and loads them:

    ~/.apprise
    ~/.apprise.yml
    ~/.config/apprise
    ~/.config/apprise.yml

    ~/.apprise/apprise
    ~/.apprise/apprise.yaml
    ~/.config/apprise/apprise
    ~/.config/apprise/apprise.yaml

If a default configuration file is referenced in any way by the **apprise**
tool, you no longer need to provide it a Service URL.  Usage of the **apprise**
tool simplifies to:

    $ apprise -vv -t "my title" -b "my notification body"

If you leveraged [tagging][tagging], you can define all of Apprise Service URLs in your
configuration that you want and only specifically notify a subset of them:

    $ apprise -vv -t "Will Be Late" -b "Go ahead and make dinner without me" \
              --tag=family

[yamlconfig]: https://github.com/caronc/apprise/wiki/config_yaml
[tagging]: https://github.com/caronc/apprise/wiki/CLI_Usage#label-leverage-tagging


## BUGS

If you find any bugs, please make them known at:
<https://github.com/caronc/apprise/issues>

## COPYRIGHT

Apprise is Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
