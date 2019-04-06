![Apprise Logo](http://repo.nuxref.com/pub/img/logo-apprise.png)

<hr/>

**ap·prise** / *verb*<br/>
To inform or tell (someone). To make one aware of something.
<hr/>

*Apprise* allows you to send a notification to *almost* all of the most popular *notification* services available to us today such as: Telegram, Pushbullet, Slack, Twitter, etc.

* One notification library to rule them all.
* A common and intuitive notification syntax.
* Supports the handling of images (to the notification services that will accept them).

System owners who wish to provide a notification service no longer need to research each and every new one as they appear. They just need to include this one library and then they can immediately gain access to almost all of the notifications services available to us today.

System Administrators who wish to send a notification from a scheduled task or from the command line also no longer need to find the right tool for the job.  Everything is already wrapped and supported within the *apprise* script that ships with this product.

[![Paypal](https://img.shields.io/badge/paypal-donate-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=MHANV39UZNQ5E)
[![Patreon](https://img.shields.io/badge/patreon-donate-green.svg)](https://www.patreon.com/caronc)<br/>
[![Discord](https://img.shields.io/discord/558793703356104724.svg?colorB=7289DA&label=Discord&logo=Discord&logoColor=7289DA&style=flat-square)](https://discord.gg/MMPeN2D)
[![Python](https://img.shields.io/pypi/pyversions/apprise.svg?style=flat-square)](https://pypi.org/project/apprise/)
[![Build Status](https://travis-ci.org/caronc/apprise.svg?branch=master)](https://travis-ci.org/caronc/apprise)
[![CodeCov Status](https://codecov.io/github/caronc/apprise/branch/master/graph/badge.svg)](https://codecov.io/github/caronc/apprise)
[![PyPi](https://img.shields.io/pypi/dm/apprise.svg?style=flat-square)](https://pypi.org/project/apprise/)

## Supported Notifications
The section identifies all of the services supported by this library. [Check out the wiki for more information on the supported modules here](https://github.com/caronc/apprise/wiki).

### Popular Notification Services
The table below identifies the services this tool supports and some example service urls you need to use in order to take advantage of it.

| Notification Service | Service ID | Default Port | Example Syntax |
| -------------------- | ---------- | ------------ | -------------- |
| [AWS SNS](https://github.com/caronc/apprise/wiki/Notify_sns)  | sns://   | (TCP) 443   | sns://AccessKeyID/AccessSecretKey/RegionName/+PhoneNo<br/>sns://AccessKeyID/AccessSecretKey/RegionName/+PhoneNo1/+PhoneNo2/+PhoneNoN<br/>sns://AccessKeyID/AccessSecretKey/RegionName/Topic<br/>sns://AccessKeyID/AccessSecretKey/RegionName/Topic1/Topic2/TopicN
| [Boxcar](https://github.com/caronc/apprise/wiki/Notify_boxcar)  | boxcar://   | (TCP) 443   | boxcar://hostname<br />boxcar://hostname/@tag<br/>boxcar://hostname/device_token<br />boxcar://hostname/device_token1/device_token2/device_tokenN<br />boxcar://hostname/@tag/@tag2/device_token
| [Discord](https://github.com/caronc/apprise/wiki/Notify_discord)  | discord://   | (TCP) 443   | discord://webhook_id/webhook_token<br />discord://avatar@webhook_id/webhook_token
| [Dbus](https://github.com/caronc/apprise/wiki/Notify_dbus)  | dbus://<br />qt://<br />glib://<br />kde://  | n/a  | dbus://<br />qt://<br />glib://<br />kde://
| [Emby](https://github.com/caronc/apprise/wiki/Notify_emby)  | emby:// or embys:// | (TCP) 8096 | emby://user@hostname/<br />emby://user:password@hostname
| [Faast](https://github.com/caronc/apprise/wiki/Notify_faast) | faast://    | (TCP) 443    | faast://authorizationtoken
| [Flock](https://github.com/caronc/apprise/wiki/Notify_flock) | flock://    | (TCP) 443    | flock://token<br/>flock://botname@token<br/>flock://app_token/u:userid<br/>flock://app_token/g:channel_id<br/>flock://app_token/u:userid/g:channel_id
| [Gitter](https://github.com/caronc/apprise/wiki/Notify_gitter) | gitter://    | (TCP) 443    | gitter://token/room<br/>gitter://token/room1/room2/roomN
| [Gnome](https://github.com/caronc/apprise/wiki/Notify_gnome) | gnome://    |        n/a          | gnome://
| [Gotify](https://github.com/caronc/apprise/wiki/Notify_gotify) | gotify:// or gotifys://   | (TCP) 80 or 443    | gotify://hostname/token<br />gotifys://hostname/token?priority=high
| [Growl](https://github.com/caronc/apprise/wiki/Notify_growl)  | growl://   | (UDP) 23053   | growl://hostname<br />growl://hostname:portno<br />growl://password@hostname<br />growl://password@hostname:port</br>**Note**: you can also use the get parameter _version_ which can allow the growl request to behave using the older v1.x protocol. An example would look like: growl://hostname?version=1
| [IFTTT](https://github.com/caronc/apprise/wiki/Notify_ifttt) | ifttt://    | (TCP) 443    | ifttt://webhooksID/Event<br />ifttt://webhooksID/Event1/Event2/EventN<br/>ifttt://webhooksID/Event1/?+Key=Value<br/>ifttt://webhooksID/Event1/?-Key=value1
| [Join](https://github.com/caronc/apprise/wiki/Notify_join) | join://   | (TCP) 443    | join://apikey/device<br />join://apikey/device1/device2/deviceN/<br />join://apikey/group<br />join://apikey/groupA/groupB/groupN<br />join://apikey/DeviceA/groupA/groupN/DeviceN/
| [KODI](https://github.com/caronc/apprise/wiki/Notify_kodi) | kodi:// or kodis://    | (TCP) 8080 or 443   | kodi://hostname<br />kodi://user@hostname<br />kodi://user:password@hostname:port
| [Matrix](https://github.com/caronc/apprise/wiki/Notify_matrix) | matrix:// or matrixs://  | (TCP) 80 or 443 | matrix://hostname<br />matrix://user@hostname<br />matrixs://user:pass@hostname:port/#room_alias<br />matrixs://user:pass@hostname:port/!room_id<br />matrixs://user:pass@hostname:port/#room_alias/!room_id/#room2<br />matrixs://token@hostname:port/?webhook=matrix<br />matrix://user:token@hostname/?webhook=slack&format=markdown
| [Mattermost](https://github.com/caronc/apprise/wiki/Notify_mattermost) | mmost://  | (TCP) 8065 | mmost://hostname/authkey<br />mmost://hostname:80/authkey<br />mmost://user@hostname:80/authkey<br />mmost://hostname/authkey?channel=channel<br />mmosts://hostname/authkey<br />mmosts://user@hostname/authkey<br />
| [Microsoft Teams](https://github.com/caronc/apprise/wiki/Notify_msteams) | msteams://  | (TCP) 443   | msteams://TokenA/TokenB/TokenC/
| [Prowl](https://github.com/caronc/apprise/wiki/Notify_prowl) | prowl://   | (TCP) 443    | prowl://apikey<br />prowl://apikey/providerkey
| [PushBullet](https://github.com/caronc/apprise/wiki/Notify_pushbullet) | pbul://    | (TCP) 443    | pbul://accesstoken<br />pbul://accesstoken/#channel<br/>pbul://accesstoken/A_DEVICE_ID<br />pbul://accesstoken/email@address.com<br />pbul://accesstoken/#channel/#channel2/email@address.net/DEVICE
| [Pushjet](https://github.com/caronc/apprise/wiki/Notify_pushjet) | pjet:// or pjets:// | (TCP) 80 or 443 | pjet://secret@hostname<br />pjet://secret@hostname:port<br />pjets://secret@hostname<br />pjets://secret@hostname:port
| [Pushed](https://github.com/caronc/apprise/wiki/Notify_pushed) | pushed://    | (TCP) 443    | pushed://appkey/appsecret/<br/>pushed://appkey/appsecret/#ChannelAlias<br/>pushed://appkey/appsecret/#ChannelAlias1/#ChannelAlias2/#ChannelAliasN<br/>pushed://appkey/appsecret/@UserPushedID<br/>pushed://appkey/appsecret/@UserPushedID1/@UserPushedID2/@UserPushedIDN
| [Pushover](https://github.com/caronc/apprise/wiki/Notify_pushover)  | pover://   | (TCP) 443   | pover://user@token<br />pover://user@token/DEVICE<br />pover://user@token/DEVICE1/DEVICE2/DEVICEN<br />**Note**: you must specify both your user_id and token
| [Rocket.Chat](https://github.com/caronc/apprise/wiki/Notify_rocketchat) | rocket:// or rockets://  | (TCP) 80 or 443   | rocket://user:password@hostname/RoomID/Channel<br />rockets://user:password@hostname:443/Channel1/Channel1/RoomID<br />rocket://user:password@hostname/Channel
| [Ryver](https://github.com/caronc/apprise/wiki/Notify_ryver) | ryver://  | (TCP) 443   | ryver://Organization/Token<br />ryver://botname@Organization/Token
| [Slack](https://github.com/caronc/apprise/wiki/Notify_slack) | slack://  | (TCP) 443   | slack://TokenA/TokenB/TokenC/Channel<br />slack://botname@TokenA/TokenB/TokenC/Channel<br />slack://user@TokenA/TokenB/TokenC/Channel1/Channel2/ChannelN
| [Telegram](https://github.com/caronc/apprise/wiki/Notify_telegram) | tgram://  | (TCP) 443   | tgram://bottoken/ChatID<br />tgram://bottoken/ChatID1/ChatID2/ChatIDN
| [Twitter](https://github.com/caronc/apprise/wiki/Notify_twitter) | tweet://  | (TCP) 443   | tweet://user@CKey/CSecret/AKey/ASecret
| [XBMC](https://github.com/caronc/apprise/wiki/Notify_xbmc) | xbmc:// or xbmcs://    | (TCP) 8080 or 443   | xbmc://hostname<br />xbmc://user@hostname<br />xbmc://user:password@hostname:port
| [XMPP](https://github.com/caronc/apprise/wiki/Notify_xmpp) | xmpp:// or xmpps://    | (TCP) 5222 or 5223   | xmpp://password@hostname<br />xmpp://user:password@hostname<br />xmpps://user:password@hostname:port?jid=user@hostname/resource<br/>xmpps://password@hostname/target@myhost, target2@myhost/resource
| [Windows Notification](https://github.com/caronc/apprise/wiki/Notify_windows) | windows://    |        n/a          | windows://
| [Webex Teams (Cisco)](https://github.com/caronc/apprise/wiki/Notify_wxteams) | wxteams://  | (TCP) 443   | wxteams://Token


### Email Support
| Service ID | Default Port | Example Syntax |
| ---------- | ------------ | -------------- |
| [mailto://](https://github.com/caronc/apprise/wiki/Notify_email)  |  (TCP) 25    | mailto://userid:pass@domain.com<br />mailto://domain.com?user=userid&pass=password<br/>mailto://domain.com:2525?user=userid&pass=password<br />mailto://user@gmail.com&pass=password<br />mailto://mySendingUsername:mySendingPassword@example.com?to=receivingAddress@example.com<br />mailto://userid:password@example.com?smtp=mail.example.com&from=noreply@example.com&name=no%20reply
| [mailtos://](https://github.com/caronc/apprise/wiki/Notify_email) |  (TCP) 587   | mailtos://userid:pass@domain.com<br />mailtos://domain.com?user=userid&pass=password<br/>mailtos://domain.com:465?user=userid&pass=password<br />mailtos://user@hotmail.com&pass=password<br />mailtos://mySendingUsername:mySendingPassword@example.com?to=receivingAddress@example.com<br />mailtos://userid:password@example.com?smtp=mail.example.com&from=noreply@example.com&name=no%20reply

Apprise have some email services built right into it (such as yahoo, fastmail, hotmail, gmail, etc) that greatly simplify the mailto:// service.  See more details [here](https://github.com/caronc/apprise/wiki/Notify_email).

### Custom Notifications
| Post Method          | Service ID | Default Port | Example Syntax |
| -------------------- | ---------- | ------------ | -------------- |
| [JSON](https://github.com/caronc/apprise/wiki/Notify_Custom_JSON)       | json:// or jsons://   | (TCP) 80 or 443 | json://hostname<br />json://user@hostname<br />json://user:password@hostname:port<br />json://hostname/a/path/to/post/to
| [XML](https://github.com/caronc/apprise/wiki/Notify_Custom_XML)         | xml:// or xmls://   | (TCP) 80 or 443 | xml://hostname<br />xml://user@hostname<br />xml://user:password@hostname:port<br />xml://hostname/a/path/to/post/to

## Installation
The easiest way is to install this package is from pypi:
```bash
pip install apprise
```
## Command Line
A small command line tool is also provided with this package called *apprise*. If you know the server url's you wish to notify, you can simply provide them all on the command line and send your notifications that way:
```bash
# Send a notification to as many servers as you want
# as you can easily chain one after another:
apprise -t 'my title' -b 'my notification body' \
   'mailto://myemail:mypass@gmail.com' \
   'pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b'

# If you don't specify a --body (-b) then stdin is used allowing
# you to use the tool as part of your every day administration:
cat /proc/cpuinfo | apprise -t 'cpu info' \
      'mailto://myemail:mypass@gmail.com'

# The title field is totally optional
uptime | apprise \
 'discord:///4174216298/JHMHI8qBe7bk2ZwO5U711o3dV_js'
```

### Configuration Files
No one wants to put there credentials out for everyone to see on the command line.  No problem *apprise* also supports configuration files.  It can handle both a specific [YAML format](https://github.com/caronc/apprise/wiki/config_yaml) or a very simple [TEXT format](https://github.com/caronc/apprise/wiki/config_text). You can also pull these configuration files via an HTTP query too! More information concerning Apprise configuration can be found [here](https://github.com/caronc/apprise/wiki/config)
```bash
# By default now if no url or configuration is specified aprise will
# peek for this data in:
#  ~/.apprise
#  ~/.apprise.yml
#  ~/.config/apprise
#  ~/.config/apprise.yml

# If you loaded one of those files, your command line gets really easy:
apprise -t 'my title' -b 'my notification body'

# Know the location of the configuration source? No problem, just
# specify it.
apprise -t 'my title' -b 'my notification body' \
	--config=/path/to/my/config.yml

# Got lots of configuration locations? No problem, specify them all:
apprise -t 'my title' -b 'my notification body' \
	--config=/path/to/my/config.yml \
	--config=https://localhost/my/apprise/config
```

## Developers
To send a notification from within your python application, just do the following:
```python
import apprise

# Create an Apprise instance
apobj = apprise.Apprise()

# Add all of the notification services by their server url.
# A sample email notification
apobj.add('mailto://myemail:mypass@gmail.com')

# A sample pushbullet notification
apobj.add('pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b')

# Then notify these services any time you desire. The below would
# notify all of the services loaded into our Apprise object.
apobj.notify(
    body='what a great notification service!',
    title='my notification title',
)
```

### Configuration Files
Developers need access to configuration files too. The good news is their use just involves declaring another object (called *AppriseConfig*) that the *Apprise* object can ingest.  You can also freely mix and match config and notification entries as often as you wish!
```python
import apprise

# Create an Apprise instance
apobj = apprise.Apprise()

# Create an Config instance
config = apprise.AppriseConfig()

# Add a configuration source:
config.add('/path/to/my/config.yml')

# Add another...
config.add('https://myserver:8080/path/to/config')

# Make sure to add our config into our apprise object
apobj.add(config)

# You can mix and match; add an entry directly if you want too
# In this entry we associate the 'admin' tag with our notification
apobj.add('mailto://myemail:mypass@gmail.com', tag='admin')

# Then notify these services any time you desire. The below would
# notify all of the services loaded into our Apprise object; this includes
# all items identified in the configuration files.
apobj.notify(
    body='what a great notification service!',
    title='my notification title',
)

# If you're using tagging, then you can load all of your notifications
# but only selectively notify the ones associated with one or more 
# matched tags:
apobj.notify(
    body='send a notification to our admin group'
    title='Attention Admins',
    # notify any services tagged with the 'admin' tag
    tag='admin',
)
```

If you're interested in reading more about this and other methods on how to customize your own notifications, please check out the wiki at https://github.com/caronc/apprise/wiki/Development_API
