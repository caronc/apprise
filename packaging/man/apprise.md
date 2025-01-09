apprise(1) -- Push Notifications that work with just about every platform!
==========================================================================

## SYNOPSIS

`apprise` [<options>...] <service-url>...<br>
`apprise` storage [<options>...] [<action>] <url-id>...<br>

## DESCRIPTION

**Apprise** allows you to send a notification to _almost all_ of the most
popular notification services available to us today such as: Discord,
Telegram, Pushbullet, Slack, Twitter, etc.

  * One notification library to rule them all.
  * A common and intuitive notification syntax.
  * Supports the handling of images (to the notification services that will
    accept them).
  * It's incredibly lightweight.
  * Amazing response times because all messages sent asynchronously.

## OPTIONS

The Apprise options are as follows:

  `-b`, `--body=`<VALUE>:
  Specify the message body. If no body is specified then content is read from
  <stdin>.

  `-t`, `--title=`<VALUE>:
  Specify the message title. This field is complete optional.

  `-c`, `--config=`<CONFIG-URL>:
  Specify one or more configuration locations.

  `-a`, `--attach=`<ATTACH-URL>:
  Specify one or more file attachment locations.

  `-P`, `--plugin-path=`<PATH>:
  Specify a path to scan for custom notification plugin support.
  You can create your own notification by simply creating a Python file
  that contains the `@notify("schema")` decorator.

  You can optioanly chose to specify more then one **--plugin-path** (**-P**)
  to increase the modules included.

  `-n`, `--notification-type=`<VALUE>:
  Specify the message type (default=info). Possible values are "info",
  "success", "failure", and "warning".

  `-i`, `--input-format=`<VALUE>:
  Specify the input message format (default=text). Possible values are "text",
  "html", and "markdown".

  `-T`, `--theme=`<VALUE>:
  Specify the default theme.

  `-g`, `--tag=`<VALUE>:
  Specify one or more tags to filter which services to notify. Use multiple
  **--tag** (**-g**) entries to `OR` the tags together and comma separated
  to `AND` them. If no tags are specified then all services are notified.

  `-Da`, `--disable-async`:
  Send notifications synchronously (one after the other) instead of
  all at once.

  `-R`, `--recursion-depth`<INTEGER>:
  he number of recursive import entries that can be loaded from within
  Apprise configuration. By default this is set to 1. If this is set to
  zero, then import statements found in any configuration is ignored.

  `-e`, `--interpret-escapes`
  Enable interpretation of backslash escapes. For example, this would convert
  sequences such as \n and \r to their respected ascii new-line and carriage

  `-j`, `--interpret-emojis`
  Enable interpretation of emoji strings. For example, this would convert
  sequences such as :smile: or :grin: to their respected unicode emoji
  character.

  `-S`, `--storage-path=`<PATH>:
  Specify the path to the persistent storage caching location

  `-SM`, `--storage-mode=`<MODE>:
  Specify the persistent storage operational mode. Possible values are "auto",
  "flush", and "memory". The default is "auto" not not specified.

  `-SPD`, `--storage-prune-days=`<INTEGER>:
  Define the number of days the storage prune should run using.
  Setting this to zero (0) will eliminate all accumulated content. By
  default this value is 30 (days).

  `-SUL`, `--storage-uid-length=`<INTEGER>:
  Define the number of unique characters to store persistent cache in.
  By default this value is 8 (characters).

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

## PERSISTENT STORAGE

Persistent storage by default writes to the following location unless the environment variable `APPRISE_STORAGE_PATH` over-rides it and/or `--storage-path` (`-SP`) is specified to over-ride it:

    ~/.local/share/apprise/cache

To utilize the [persistent storage][pstorage] element associated with Apprise, simply
specify the keyword **storage**

    $ apprise storage

The **storage** action has the following sub actions:

  `list`:
  List all of the detected persistent storage elements and their state
  (**stale**, **active**, or **unused**).  This is the default action if
  nothing further is identified.

  `prune`:
  Removes all persistent storage that has not been referenced for more then 30
  days. You can optionally set the `--storage-prune-days` to alter this
  default value.

  `clean`:
  Removes all persistent storage reguardless of age.

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

The **environment variable** of `APPRISE_URLS` (comma/space delimited) can be specified to
provide the default set of URLs you wish to notify if none are otherwise specified.

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

List all of the notifications loaded:

    $ apprise --dry-run --tag=all

List all of the details around the current persistent storage setup:

    $ apprise storage list

Prune all persistent storage that has not been referenced for at least 10 days or more

    $ apprise storage prune --storage-prune-days=10

## CUSTOM PLUGIN/NOTIFICATIONS
Apprise can additionally allow you to define your own custom **schema://**
entries that you can trigger on and call services you've defined.

By default **apprise** looks in the following local locations for custom plugin
files and loads them:

    ~/.apprise/plugins
    ~/.config/apprise/plugins
    /var/lib/apprise/plugins

The **environment variable** of `APPRISE_PLUGIN_PATH` can be specified to override
the list identified above with one of your own.  use a semi-colon (`;`), line-feed (`\n`),
and/or carriage return (`\r`) to delimit multiple entries.

Simply create your own python file with the following bare minimum content in
it:

    from apprise.decorators import notify

    # This example assumes you want your function to trigger on foobar://
    # references:
    @notify(on="foobar", name="My Custom Notification")
    def my_wrapper(body, title, notify_type, *args, **kwargs):

         print("Define your custom code here")

         # Returning True/False will relay your status back through Apprise
         # Returning nothing (None by default) is always interpreted as True
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

    ~/.apprise.conf
    ~/.apprise.yaml
    ~/.config/apprise.conf
    ~/.config/apprise.yaml

    ~/.apprise/apprise.conf
    ~/.apprise/apprise.yaml
    ~/.config/apprise/apprise.conf
    ~/.config/apprise/apprise.yaml

    /etc/apprise.conf
    /etc/apprise.yaml
    /etc/apprise/apprise.conf
    /etc/apprise/apprise.yaml

The **configuration files** specified above can also be identified with a `.yml`
extension or even just entirely removing the `.conf` extension altogether.

The **environment variable** of `APPRISE_CONFIG_PATH` can be specified to override
the list identified above with one of your own.  use a semi-colon (`;`), line-feed (`\n`),
and/or carriage return (`\r`) to delimit multiple entries.

If a default configuration file is referenced in any way by the **apprise**
tool, you no longer need to provide it a Service URL.  Usage of the **apprise**
tool simplifies to:

    $ apprise -vv -t "my title" -b "my notification body"

If you leveraged [tagging][tagging], you can define all of Apprise Service URLs in your
configuration that you want and only specifically notify a subset of them:

    $ apprise -vv --title "Will Be Late Getting Home" \
        --body "Please go ahead and make dinner without me." \
        --tag=family

[yamlconfig]: https://github.com/caronc/apprise/wiki/config_yaml
[textconfig]: https://github.com/caronc/apprise/wiki/config_text
[tagging]: https://github.com/caronc/apprise/wiki/CLI_Usage#label-leverage-tagging
[pstorage]: https://github.com/caronc/apprise/wiki/persistent_storage

## ENVIRONMENT VARIABLES
  `APPRISE_URLS`:
  Specify the default URLs to notify IF none are otherwise specified on the command line
  explicitly.  If the `--config` (`-c`) is specified, then this will over-rides any
  reference to this variable. Use white space and/or a comma (`,`) to delimit multiple entries.

  `APPRISE_CONFIG_PATH`:
  Explicitly specify the config search path to use (over-riding the default).
  Use a semi-colon (`;`), line-feed (`\n`), and/or carriage return (`\r`) to delimit multiple entries.

  `APPRISE_PLUGIN_PATH`:
  Explicitly specify the custom plugin search path to use (over-riding the default).
  Use a semi-colon (`;`), line-feed (`\n`), and/or carriage return (`\r`) to delimit multiple entries.

  `APPRISE_STORAGE_PATH`:
  Explicitly specify the persistent storage path to use (over-riding the default).

## BUGS

If you find any bugs, please make them known at:
<https://github.com/caronc/apprise/issues>

## DONATIONS
If you found Apprise useful at all, [please consider donating][donations]!

[donations]: https://github.com/caronc/apprise/wiki/persistent_storage

## COPYRIGHT

Apprise is Copyright (C) 2025 Chris Caron <lead2gold@gmail.com>
