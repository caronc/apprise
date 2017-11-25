<hr/>

**ap·prise** / *verb*<br/>
To inform or tell (someone). To make one aware of something.
<hr/>

*Apprise* allows you to take advantage of *just about* every notification service available to us today.  Send a notification to almost all of the most popular services out there today (such as Telegram, Slack, Twitter, etc). The ones that don't exist can be adapted and supported too!

## Supported Notifications
The section identifies all of the services supported by this script.

### Popular Notification Services
The table below identifies the services this tool supports and some example service urls you need to use in order to take advantage of it.

| Notification Service | Service ID | Default Port | Example Syntax |
| -------------------- | ---------- | ------------ | -------------- |
| [Boxcar](https://github.com/caronc/apprise/wiki/Notify_boxcar)  | boxcar://   | (TCP) 443   | boxcar://hostname<br />boxcar://hostname/@tag<br/>boxcar://hostname/device_token<br />boxcar://hostname/device_token1/device_token2/device_tokenN<br />boxcar://hostname/alias<br />boxcar://hostname/@tag/@tag2/alias/device_token
| [Faast](https://github.com/caronc/apprise/wiki/Notify_faast) | faast://    | (TCP) 443    | faast://authorizationtoken
| [Growl](https://github.com/caronc/apprise/wiki/Notify_growl)  | growl://   | (UDP) 23053   | growl://hostname<br />growl://hostname:portno<br />growl://password@hostname<br />growl://password@hostname:port</br>_Note: you can also use the get parameter _version_ which can allow the growl request to behave using the older v1.x protocol. An example would look like: growl://hostname?version=1
| [Join](https://github.com/caronc/apprise/wiki/Notify_join) | join://   | (TCP) 443    | join://apikey/device<br />join://apikey/device1/device2/deviceN/<br />join://apikey/group<br />join://apikey/groupA/groupB/groupN<br />join://apikey/DeviceA/groupA/groupN/DeviceN/
| [KODI](https://github.com/caronc/apprise/wiki/Notify_kodi) | kodi:// or kodis://    | (TCP) 8080 or 443   | kodi://hostname<br />kodi://user@hostname<br />kodi://user:password@hostname:port
| [Mattermost](https://github.com/caronc/apprise/wiki/Notify_mattermost) | mmost://  | (TCP) 8065 | mmost://hostname/authkey<br />mmost://hostname:80/authkey<br />mmost://user@hostname:80/authkey<br />mmost://hostname/authkey?channel=channel<br />mmosts://hostname/authkey<br />mmosts://user@hostname/authkey<br />
| [Notify My Android](https://github.com/caronc/apprise/wiki/Notify_my_android) | nma://   | (TCP) 443    | nma://apikey
| [Prowl](https://github.com/caronc/apprise/wiki/Notify_prowl) | prowl://   | (TCP) 443    | prowl://apikey<br />prowl://apikey/providerkey
| [Pushalot](https://github.com/caronc/apprise/wiki/Notify_pushalot) | palot://    | (TCP) 443    | palot://authorizationtoken
| [PushBullet](https://github.com/caronc/apprise/wiki/Notify_pushbullet) | pbul://    | (TCP) 443    | pbul://accesstoken<br />pbul://accesstoken/#channel<br/>pbul://accesstoken/A_DEVICE_ID<br />pbul://accesstoken/email@address.com<br />pbul://accesstoken/#channel/#channel2/email@address.net/DEVICE
| [Pushjet](https://github.com/caronc/apprise/wiki/Notify_pushjet) | pjet://  | (TCP) 80   | pjet://secret<br />pjet://secret@hostname<br />pjet://secret@hostname:port<br />pjets://secret@hostname<br />pjets://secret@hostname:port<br /><i>Note: if no hostname defined https://api.pushjet.io will be used
| [Pushover](https://github.com/caronc/apprise/wiki/Notify_pushover)  | pover://   | (TCP) 443   | pover://user@token<br />pover://user@token/DEVICE<br />pover://user@token/DEVICE1/DEVICE2/DEVICEN<br />_Note: you must specify both your user_id and token_
| [Rocket.Chat](https://github.com/caronc/apprise/wiki/Notify_rocketchat) | rocket:// or rockets://  | (TCP) 80 or 443   | rocket://user:password@hostname/RoomID/Channel<br />rockets://user:password@hostname:443/Channel1/Channel1/RoomID<br />rocket://user:password@hostname/Channel
| [Slack](https://github.com/caronc/apprise/wiki/Notify_slack) | slack://  | (TCP) 443   | slack://TokenA/TokenB/TokenC/Channel<br />slack://botname@TokenA/TokenB/TokenC/Channel<br />slack://user@TokenA/TokenB/TokenC/Channel1/Channel2/ChannelN
| [Super Toasty](https://github.com/caronc/apprise/wiki/Notify_toasty)  | toasty://   | (TCP) 80   | toasty://user@DEVICE<br />toasty://user@DEVICE1/DEVICE2/DEVICEN<br />_Note: you must specify both your user_id and at least 1 device!_
| [Telegram](https://github.com/caronc/apprise/wiki/Notify_telegram) | tgram://  | (TCP) 443   | tgram://bottoken/ChatID<br />tgram://bottoken/ChatID1/ChatID2/ChatIDN
| [Twitter](https://github.com/caronc/apprise/wiki/Notify_twitter) | tweet://  | (TCP) 443   | tweet://user@CKey/CSecret/AKey/ASecret
| [XBMC](https://github.com/caronc/apprise/wiki/Notify_xbmc) | xbmc:// or xbmcs://    | (TCP) 8080 or 443   | xbmc://hostname<br />xbmc://user@hostname<br />xbmc://user:password@hostname:port

### Email Support
| Service ID | Default Port | Example Syntax |
| ---------- | ------------ | -------------- |
| [mailto://](https://github.com/caronc/apprise/wiki/Notify_email)  |  (TCP) 25    | mailto://userid:pass@domain.com<br />mailto://domain.com?user=userid&pass=password<br/>mailto://domain.com:2525?user=userid&pass=password<br />mailto://user@gmail.com&pass=password<br />mailto://userid:password@example.com?smtp=mail.example.com&from=noreply@example.com&name=no%20reply
| [mailtos//](https://github.com/caronc/apprise/wiki/Notify_email) |  (TCP) 587   | mailtos://userid:pass@domain.com<br />mailtos://domain.com?user=userid&pass=password<br/>mailtos://domain.com:465?user=userid&pass=password<br />mailtos://user@hotmail.com&pass=password<br />mailtos://userid:password@example.com?smtp=mail.example.com&from=noreply@example.com&name=no%20reply

Apprise have some email services built right into it (such as hotmail, gmail, etc) that greatly simplify the mailto:// service.  See more details [here](https://github.com/caronc/apprise/wiki/Notify_email).

### Custom Notifications
| Post Method          | Service ID | Default Port | Example Syntax |
| -------------------- | ---------- | ------------ | -------------- |
| [JSON](https://github.com/caronc/apprise/wiki/Notify_Custom_JSON)       | json:// or jsons://   | (TCP) 80 or 443 | json://hostname<br />json://user@hostname<br />json://user:password@hostname:port<br />json://hostname/a/path/to/post/to
| [XML](https://github.com/caronc/apprise/wiki/Notify_Custom_XML)         | xml:// or xmls://   | (TCP) 80 or 443 | xml://hostname<br />xml://user@hostname<br />xml://user:password@hostname:port<br />xml://hostname/a/path/to/post/to

