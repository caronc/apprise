![Apprise Logo](https://raw.githubusercontent.com/caronc/apprise/master/apprise/assets/themes/default/apprise-logo.png)

<hr/>

**ap·prise** / *verb*<br/>
To inform or tell (someone). To make one aware of something.
<hr/>

*Apprise* allows you to send a notification to *almost* all of the most popular *notification* services available to us today such as: Telegram, Discord, Slack, Amazon SNS, Gotify, etc.

* One notification library to rule them all.
* A common and intuitive notification syntax.
* Supports the handling of images and attachments (_to the notification services that will accept them_).
* It's incredibly lightweight.
* Amazing response times because all messages sent asynchronously.

Developers who wish to provide a notification service no longer need to research each and every one out there. They no longer need to try to adapt to the new ones that comeout thereafter. They just need to include this one library and then they can immediately gain access to almost all of the notifications services available to us today.

System Administrators and DevOps who wish to send a notification now no longer need to find the right tool for the job. Everything is already wrapped and supported within the `apprise` command line tool (CLI) that ships with this product.

[![Paypal](https://img.shields.io/badge/paypal-donate-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=MHANV39UZNQ5E)
[![Follow](https://img.shields.io/twitter/follow/l2gnux)](https://twitter.com/l2gnux/)<br/>
[![Discord](https://img.shields.io/discord/558793703356104724.svg?colorB=7289DA&label=Discord&logo=Discord&logoColor=7289DA&style=flat-square)](https://discord.gg/MMPeN2D)
[![Python](https://img.shields.io/pypi/pyversions/apprise.svg?style=flat-square)](https://pypi.org/project/apprise/)
[![Build Status](https://github.com/caronc/apprise/actions/workflows/tests.yml/badge.svg)](https://github.com/caronc/apprise/actions/workflows/tests.yml)
[![CodeCov Status](https://codecov.io/github/caronc/apprise/branch/master/graph/badge.svg)](https://codecov.io/github/caronc/apprise)
[![PyPi Downloads](https://img.shields.io/pepy/dt/apprise.svg?style=flat-square)](https://pypi.org/project/apprise/)

# Table of Contents
<!--ts-->
* [Supported Notifications](#supported-notifications)
  * [Productivity Based Notifications](#productivity-based-notifications)
  * [SMS Notifications](#sms-notifications)
  * [Desktop Notifications](#desktop-notifications)
  * [Email Notifications](#email-notifications)
  * [Custom Notifications](#custom-notifications)
* [Installation](#installation)
* [Command Line Usage](#command-line-usage)
  * [Configuration Files](#cli-configuration-files)
  * [File Attachments](#cli-file-attachments)
  * [Loading Custom Notifications/Hooks](#cli-loading-custom-notificationshooks)
  * [Environment Variables](#cli-environment-variables)
* [Developer API Usage](#developer-api-usage)
  * [Configuration Files](#api-configuration-files)
  * [File Attachments](#api-file-attachments)
  * [Loading Custom Notifications/Hooks](#api-loading-custom-notificationshooks)
* [Persistent Storage](#persistent-storage)
* [More Supported Links and Documentation](#want-to-learn-more)
<!--te-->

# Supported Notifications

The section identifies all of the services supported by this library. [Check out the wiki for more information on the supported modules here](https://github.com/caronc/apprise/wiki).

## Productivity Based Notifications

The table below identifies the services this tool supports and some example service urls you need to use in order to take advantage of it. Click on any of the services listed below to get more details on how you can configure Apprise to access them.

| Notification Service | Service ID | Default Port | Example Syntax |
| -------------------- | ---------- | ------------ | -------------- |
| [Apprise API](https://github.com/caronc/apprise/wiki/Notify_apprise_api)  | apprise:// or apprises:// | (TCP) 80 or 443 | apprise://hostname/Token
| [AWS SES](https://github.com/caronc/apprise/wiki/Notify_ses)  | ses://   | (TCP) 443   | ses://user@domain/AccessKeyID/AccessSecretKey/RegionName<br/>ses://user@domain/AccessKeyID/AccessSecretKey/RegionName/email1/email2/emailN
| [Bark](https://github.com/caronc/apprise/wiki/Notify_bark)  | bark://   | (TCP) 80 or 443   | bark://hostname<br />bark://hostname/device_key<br />bark://hostname/device_key1/device_key2/device_keyN<br/>barks://hostname<br />barks://hostname/device_key<br />barks://hostname/device_key1/device_key2/device_keyN
| [BlueSky](https://github.com/caronc/apprise/wiki/Notify_bluesky) | bluesky://  | (TCP) 443   | bluesky://Handle:AppPw<br />bluesky://Handle:AppPw/TargetHandle<br />bluesky://Handle:AppPw/TargetHandle1/TargetHandle2/TargetHandleN
| [Chanify](https://github.com/caronc/apprise/wiki/Notify_chanify) | chantify://    | (TCP) 443    | chantify://token
| [Discord](https://github.com/caronc/apprise/wiki/Notify_discord)  | discord://   | (TCP) 443   | discord://webhook_id/webhook_token<br />discord://avatar@webhook_id/webhook_token
| [Emby](https://github.com/caronc/apprise/wiki/Notify_emby)  | emby:// or embys:// | (TCP) 8096 | emby://user@hostname/<br />emby://user:password@hostname
| [Enigma2](https://github.com/caronc/apprise/wiki/Notify_enigma2)  | enigma2:// or enigma2s:// | (TCP) 80 or 443 | enigma2://hostname
| [FCM](https://github.com/caronc/apprise/wiki/Notify_fcm) | fcm://    | (TCP) 443    | fcm://project@apikey/DEVICE_ID<br />fcm://project@apikey/#TOPIC<br/>fcm://project@apikey/DEVICE_ID1/#topic1/#topic2/DEVICE_ID2/
| [Feishu](https://github.com/caronc/apprise/wiki/Notify_feishu) | feishu://    | (TCP) 443    | feishu://token
| [Flock](https://github.com/caronc/apprise/wiki/Notify_flock) | flock://    | (TCP) 443    | flock://token<br/>flock://botname@token<br/>flock://app_token/u:userid<br/>flock://app_token/g:channel_id<br/>flock://app_token/u:userid/g:channel_id
| [Google Chat](https://github.com/caronc/apprise/wiki/Notify_googlechat) | gchat://    | (TCP) 443    | gchat://workspace/key/token
| [Gotify](https://github.com/caronc/apprise/wiki/Notify_gotify) | gotify:// or gotifys://   | (TCP) 80 or 443    | gotify://hostname/token<br />gotifys://hostname/token?priority=high
| [Growl](https://github.com/caronc/apprise/wiki/Notify_growl)  | growl://   | (UDP) 23053   | growl://hostname<br />growl://hostname:portno<br />growl://password@hostname<br />growl://password@hostname:port</br>**Note**: you can also use the get parameter _version_ which can allow the growl request to behave using the older v1.x protocol. An example would look like: growl://hostname?version=1
| [Guilded](https://github.com/caronc/apprise/wiki/Notify_guilded)  | guilded://   | (TCP) 443   | guilded://webhook_id/webhook_token<br />guilded://avatar@webhook_id/webhook_token
| [Home Assistant](https://github.com/caronc/apprise/wiki/Notify_homeassistant)       | hassio:// or hassios://   | (TCP) 8123 or 443 | hassio://hostname/accesstoken<br />hassio://user@hostname/accesstoken<br />hassio://user:password@hostname:port/accesstoken<br />hassio://hostname/optional/path/accesstoken
| [IFTTT](https://github.com/caronc/apprise/wiki/Notify_ifttt) | ifttt://    | (TCP) 443    | ifttt://webhooksID/Event<br />ifttt://webhooksID/Event1/Event2/EventN<br/>ifttt://webhooksID/Event1/?+Key=Value<br/>ifttt://webhooksID/Event1/?-Key=value1
| [Join](https://github.com/caronc/apprise/wiki/Notify_join) | join://   | (TCP) 443    | join://apikey/device<br />join://apikey/device1/device2/deviceN/<br />join://apikey/group<br />join://apikey/groupA/groupB/groupN<br />join://apikey/DeviceA/groupA/groupN/DeviceN/
| [KODI](https://github.com/caronc/apprise/wiki/Notify_kodi) | kodi:// or kodis://    | (TCP) 8080 or 443   | kodi://hostname<br />kodi://user@hostname<br />kodi://user:password@hostname:port
| [Kumulos](https://github.com/caronc/apprise/wiki/Notify_kumulos) | kumulos:// | (TCP) 443 | kumulos://apikey/serverkey
| [LaMetric Time](https://github.com/caronc/apprise/wiki/Notify_lametric) | lametric:// | (TCP) 443 | lametric://apikey@device_ipaddr<br/>lametric://apikey@hostname:port<br/>lametric://client_id@client_secret
| [Lark](https://github.com/caronc/apprise/wiki/Notify_lark) | lark://  | (TCP) 443   | lark://BotToken
| [Line](https://github.com/caronc/apprise/wiki/Notify_line) | line:// | (TCP) 443 | line://Token@User<br/>line://Token/User1/User2/UserN
| [Mailgun](https://github.com/caronc/apprise/wiki/Notify_mailgun) | mailgun:// | (TCP) 443 | mailgun://user@hostname/apikey<br />mailgun://user@hostname/apikey/email<br />mailgun://user@hostname/apikey/email1/email2/emailN<br />mailgun://user@hostname/apikey/?name="From%20User"
| [Mastodon](https://github.com/caronc/apprise/wiki/Notify_mastodon) | mastodon:// or mastodons://| (TCP) 80 or 443  | mastodon://access_key@hostname<br />mastodon://access_key@hostname/@user<br />mastodon://access_key@hostname/@user1/@user2/@userN
| [Matrix](https://github.com/caronc/apprise/wiki/Notify_matrix) | matrix:// or matrixs://  | (TCP) 80 or 443 | matrix://hostname<br />matrix://user@hostname<br />matrixs://user:pass@hostname:port/#room_alias<br />matrixs://user:pass@hostname:port/!room_id<br />matrixs://user:pass@hostname:port/#room_alias/!room_id/#room2<br />matrixs://token@hostname:port/?webhook=matrix<br />matrix://user:token@hostname/?webhook=slack&format=markdown
| [Mattermost](https://github.com/caronc/apprise/wiki/Notify_mattermost) | mmost:// or mmosts:// | (TCP) 8065 | mmost://hostname/authkey<br />mmost://hostname:80/authkey<br />mmost://user@hostname:80/authkey<br />mmost://hostname/authkey?channel=channel<br />mmosts://hostname/authkey<br />mmosts://user@hostname/authkey<br />
| [Microsoft Power Automate / Workflows (MSTeams)](https://github.com/caronc/apprise/wiki/Notify_workflows) | workflows://  | (TCP) 443   | workflows://WorkflowID/Signature/
| [Microsoft Teams](https://github.com/caronc/apprise/wiki/Notify_msteams) | msteams://  | (TCP) 443   | msteams://TokenA/TokenB/TokenC/
| [Misskey](https://github.com/caronc/apprise/wiki/Notify_misskey) | misskey:// or misskeys://| (TCP) 80 or 443  | misskey://access_token@hostname
| [MQTT](https://github.com/caronc/apprise/wiki/Notify_mqtt) | mqtt://  or mqtts:// | (TCP) 1883 or 8883   | mqtt://hostname/topic<br />mqtt://user@hostname/topic<br />mqtts://user:pass@hostname:9883/topic
| [Nextcloud](https://github.com/caronc/apprise/wiki/Notify_nextcloud) | ncloud:// or nclouds:// | (TCP) 80 or 443 | ncloud://adminuser:pass@host/User<br/>nclouds://adminuser:pass@host/User1/User2/UserN
| [NextcloudTalk](https://github.com/caronc/apprise/wiki/Notify_nextcloudtalk) | nctalk:// or nctalks:// | (TCP) 80 or 443 | nctalk://user:pass@host/RoomId<br/>nctalks://user:pass@host/RoomId1/RoomId2/RoomIdN
| [Notica](https://github.com/caronc/apprise/wiki/Notify_notica) | notica://  | (TCP) 443   | notica://Token/
| [Notifiarr](https://github.com/caronc/apprise/wiki/Notify_notifiarr) | notifiarr:// | (TCP) 443 | notifiarr://apikey/#channel<br />notifiarr://apikey/#channel1/#channel2/#channeln
| [Notifico](https://github.com/caronc/apprise/wiki/Notify_notifico) | notifico://  | (TCP) 443   | notifico://ProjectID/MessageHook/
| [ntfy](https://github.com/caronc/apprise/wiki/Notify_ntfy) | ntfy://  | (TCP) 80 or 443   | ntfy://topic/<br/>ntfys://topic/
| [Office 365](https://github.com/caronc/apprise/wiki/Notify_office365) | o365://  | (TCP) 443   | o365://TenantID:AccountEmail/ClientID/ClientSecret<br />o365://TenantID:AccountEmail/ClientID/ClientSecret/TargetEmail<br />o365://TenantID:AccountEmail/ClientID/ClientSecret/TargetEmail1/TargetEmail2/TargetEmailN
| [OneSignal](https://github.com/caronc/apprise/wiki/Notify_onesignal) | onesignal:// | (TCP) 443 | onesignal://AppID@APIKey/PlayerID<br/>onesignal://TemplateID:AppID@APIKey/UserID<br/>onesignal://AppID@APIKey/#IncludeSegment<br/>onesignal://AppID@APIKey/Email
| [Opsgenie](https://github.com/caronc/apprise/wiki/Notify_opsgenie) | opsgenie:// | (TCP) 443 | opsgenie://APIKey<br/>opsgenie://APIKey/UserID<br/>opsgenie://APIKey/#Team<br/>opsgenie://APIKey/\*Schedule<br/>opsgenie://APIKey/^Escalation
| [PagerDuty](https://github.com/caronc/apprise/wiki/Notify_pagerduty) | pagerduty:// | (TCP) 443 | pagerduty://IntegrationKey@ApiKey<br/>pagerduty://IntegrationKey@ApiKey/Source/Component
| [PagerTree](https://github.com/caronc/apprise/wiki/Notify_pagertree) | pagertree:// | (TCP) 443 | pagertree://integration_id
| [ParsePlatform](https://github.com/caronc/apprise/wiki/Notify_parseplatform) | parsep:// or parseps:// | (TCP) 80 or 443 | parsep://AppID:MasterKey@Hostname<br/>parseps://AppID:MasterKey@Hostname
| [PopcornNotify](https://github.com/caronc/apprise/wiki/Notify_popcornnotify) | popcorn://  | (TCP) 443   | popcorn://ApiKey/ToPhoneNo<br/>popcorn://ApiKey/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/<br/>popcorn://ApiKey/ToEmail<br/>popcorn://ApiKey/ToEmail1/ToEmail2/ToEmailN/<br/>popcorn://ApiKey/ToPhoneNo1/ToEmail1/ToPhoneNoN/ToEmailN
| [Prowl](https://github.com/caronc/apprise/wiki/Notify_prowl) | prowl://   | (TCP) 443    | prowl://apikey<br />prowl://apikey/providerkey
| [PushBullet](https://github.com/caronc/apprise/wiki/Notify_pushbullet) | pbul://    | (TCP) 443    | pbul://accesstoken<br />pbul://accesstoken/#channel<br/>pbul://accesstoken/A_DEVICE_ID<br />pbul://accesstoken/email@address.com<br />pbul://accesstoken/#channel/#channel2/email@address.net/DEVICE
| [Pushjet](https://github.com/caronc/apprise/wiki/Notify_pushjet) | pjet:// or pjets:// | (TCP) 80 or 443 | pjet://hostname/secret<br />pjet://hostname:port/secret<br />pjets://secret@hostname/secret<br />pjets://hostname:port/secret
| [Push (Techulus)](https://github.com/caronc/apprise/wiki/Notify_techulus) | push://    | (TCP) 443    | push://apikey/
| [Pushed](https://github.com/caronc/apprise/wiki/Notify_pushed) | pushed://    | (TCP) 443    | pushed://appkey/appsecret/<br/>pushed://appkey/appsecret/#ChannelAlias<br/>pushed://appkey/appsecret/#ChannelAlias1/#ChannelAlias2/#ChannelAliasN<br/>pushed://appkey/appsecret/@UserPushedID<br/>pushed://appkey/appsecret/@UserPushedID1/@UserPushedID2/@UserPushedIDN
| [PushMe](https://github.com/caronc/apprise/wiki/Notify_pushme) | pushme://  | (TCP) 443   | pushme://Token/
| [Pushover](https://github.com/caronc/apprise/wiki/Notify_pushover)  | pover://   | (TCP) 443   | pover://user@token<br />pover://user@token/DEVICE<br />pover://user@token/DEVICE1/DEVICE2/DEVICEN<br />**Note**: you must specify both your user_id and token
| [Pushplus](https://github.com/caronc/apprise/wiki/Notify_pushplus) | pushplus://  | (TCP) 443   | pushplus://Token
| [PushSafer](https://github.com/caronc/apprise/wiki/Notify_pushsafer)  | psafer:// or psafers://  | (TCP) 80 or 443  | psafer://privatekey<br />psafers://privatekey/DEVICE<br />psafer://privatekey/DEVICE1/DEVICE2/DEVICEN
| [Pushy](https://github.com/caronc/apprise/wiki/Notify_pushy)  | pushy://  | (TCP) 443  | pushy://apikey/DEVICE<br />pushy://apikey/DEVICE1/DEVICE2/DEVICEN<br />pushy://apikey/TOPIC<br />pushy://apikey/TOPIC1/TOPIC2/TOPICN
| [PushDeer](https://github.com/caronc/apprise/wiki/Notify_pushdeer) | pushdeer:// or pushdeers:// | (TCP) 80 or 443 | pushdeer://pushKey<br />pushdeer://hostname/pushKey<br />pushdeer://hostname:port/pushKey
| [QQ Push](https://github.com/caronc/apprise/wiki/Notify_qq) | qq://  | (TCP) 443   | qq://Token
| [Reddit](https://github.com/caronc/apprise/wiki/Notify_reddit) | reddit:// | (TCP) 443   | reddit://user:password@app_id/app_secret/subreddit<br />reddit://user:password@app_id/app_secret/sub1/sub2/subN
| [Resend](https://github.com/caronc/apprise/wiki/Notify_resend) | resend://  | (TCP) 443   | resend://APIToken:FromEmail/<br />resend://APIToken:FromEmail/ToEmail<br />resend://APIToken:FromEmail/ToEmail1/ToEmail2/ToEmailN/
| [Revolt](https://github.com/caronc/apprise/wiki/Notify_Revolt) | revolt:// | (TCP) 443   |  revolt://bottoken/ChannelID<br />revolt://bottoken/ChannelID1/ChannelID2/ChannelIDN |
| [Rocket.Chat](https://github.com/caronc/apprise/wiki/Notify_rocketchat) | rocket:// or rockets://  | (TCP) 80 or 443   | rocket://user:password@hostname/RoomID/Channel<br />rockets://user:password@hostname:443/#Channel1/#Channel1/RoomID<br />rocket://user:password@hostname/#Channel<br />rocket://webhook@hostname<br />rockets://webhook@hostname/@User/#Channel
| [RSyslog](https://github.com/caronc/apprise/wiki/Notify_rsyslog) | rsyslog://  | (UDP) 514 | rsyslog://hostname<br />rsyslog://hostname/Facility
| [Ryver](https://github.com/caronc/apprise/wiki/Notify_ryver) | ryver://  | (TCP) 443   | ryver://Organization/Token<br />ryver://botname@Organization/Token
| [SendGrid](https://github.com/caronc/apprise/wiki/Notify_sendgrid) | sendgrid://  | (TCP) 443   | sendgrid://APIToken:FromEmail/<br />sendgrid://APIToken:FromEmail/ToEmail<br />sendgrid://APIToken:FromEmail/ToEmail1/ToEmail2/ToEmailN/
| [SendPulse](https://github.com/caronc/apprise/wiki/Notify_sendpulse) | sendpulse://  | (TCP) 443   | sendpulse://user@host/ClientId/ClientSecret<br />sendpulse://user@host/ClientId/clientSecret/ToEmail<br />sendpulse://user@host/ClientId/ClientSecret/ToEmail1/ToEmail2/ToEmailN/
| [ServerChan](https://github.com/caronc/apprise/wiki/Notify_serverchan) | schan://   | (TCP) 443    | schan://sendkey/
| [Signal API](https://github.com/caronc/apprise/wiki/Notify_signal) | signal://  or signals:// | (TCP) 80 or 443  | signal://hostname:port/FromPhoneNo<br/>signal://hostname:port/FromPhoneNo/ToPhoneNo<br/>signal://hostname:port/FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [SIGNL4](https://github.com/caronc/apprise/wiki/Notify_signl4) | signl4://  | (TCP) 80 or 443  | signl4://hostname
| [SimplePush](https://github.com/caronc/apprise/wiki/Notify_simplepush) | spush://   | (TCP) 443    | spush://apikey<br />spush://salt:password@apikey<br />spush://apikey?event=Apprise
| [Slack](https://github.com/caronc/apprise/wiki/Notify_slack) | slack://  | (TCP) 443   | slack://TokenA/TokenB/TokenC/<br />slack://TokenA/TokenB/TokenC/Channel<br />slack://botname@TokenA/TokenB/TokenC/Channel<br />slack://user@TokenA/TokenB/TokenC/Channel1/Channel2/ChannelN
| [SMTP2Go](https://github.com/caronc/apprise/wiki/Notify_smtp2go) | smtp2go:// | (TCP) 443 | smtp2go://user@hostname/apikey<br />smtp2go://user@hostname/apikey/email<br />smtp2go://user@hostname/apikey/email1/email2/emailN<br />smtp2go://user@hostname/apikey/?name="From%20User"
| [SparkPost](https://github.com/caronc/apprise/wiki/Notify_sparkpost) | sparkpost:// | (TCP) 443 | sparkpost://user@hostname/apikey<br />sparkpost://user@hostname/apikey/email<br />sparkpost://user@hostname/apikey/email1/email2/emailN<br />sparkpost://user@hostname/apikey/?name="From%20User"
| [Spike.sh](https://github.com/caronc/apprise/wiki/Notify_spike) | spike://  | (TCP) 443   | spike://Token
| [Splunk](https://github.com/caronc/apprise/wiki/Notify_splunk) | splunk:// or victorops:/ | (TCP) 443 | splunk://route_key@apikey<br />splunk://route_key@apikey/entity_id
| [Spug Push](https://github.com/caronc/apprise/wiki/Notify_spugpush) | spugpush://  | (TCP) 443   | spugpush://Token
| [Streamlabs](https://github.com/caronc/apprise/wiki/Notify_streamlabs) | strmlabs:// | (TCP) 443 | strmlabs://AccessToken/<br/>strmlabs://AccessToken/?name=name&identifier=identifier&amount=0&currency=USD
| [Synology Chat](https://github.com/caronc/apprise/wiki/Notify_synology_chat) | synology:// or synologys:// |  (TCP) 80 or 443 | synology://hostname/token<br />synology://hostname:port/token
| [Syslog](https://github.com/caronc/apprise/wiki/Notify_syslog) | syslog://  | n/a | syslog://<br />syslog://Facility
| [Telegram](https://github.com/caronc/apprise/wiki/Notify_telegram) | tgram://  | (TCP) 443   | tgram://bottoken/ChatID<br />tgram://bottoken/ChatID1/ChatID2/ChatIDN
| [Twitter](https://github.com/caronc/apprise/wiki/Notify_twitter) | twitter://  | (TCP) 443   | twitter://CKey/CSecret/AKey/ASecret<br/>twitter://user@CKey/CSecret/AKey/ASecret<br/>twitter://CKey/CSecret/AKey/ASecret/User1/User2/User2<br/>twitter://CKey/CSecret/AKey/ASecret?mode=tweet
| [Twist](https://github.com/caronc/apprise/wiki/Notify_twist) | twist://  | (TCP) 443   | twist://pasword:login<br/>twist://password:login/#channel<br/>twist://password:login/#team:channel<br/>twist://password:login/#team:channel1/channel2/#team3:channel
| [Vapid (WebPush)](https://github.com/caronc/apprise/wiki/Notify_vapid) | vapid://    | (TCP) 443    | vapid://subscriber/target<br/>vapid://subscriber/target?subfile=path&keyfile=path
| [Webex Teams (Cisco)](https://github.com/caronc/apprise/wiki/Notify_wxteams) | wxteams://  | (TCP) 443   | wxteams://Token
| [WeCom Bot](https://github.com/caronc/apprise/wiki/Notify_wecombot) | wecombot://  | (TCP) 443   | wecombot://BotKey
| [WhatsApp](https://github.com/caronc/apprise/wiki/Notify_whatsapp) | whatsapp://  | (TCP) 443   | whatsapp://AccessToken@FromPhoneID/ToPhoneNo<br/>whatsapp://Template:AccessToken@FromPhoneID/ToPhoneNo
| [WxPusher](https://github.com/caronc/apprise/wiki/Notify_wxpusher) | wxpusher://  | (TCP) 443   | wxpusher://AppToken@UserID1/UserID2/UserIDN<br/>wxpusher://AppToken@Topic1/Topic2/Topic3<br/>wxpusher://AppToken@UserID1/Topic1/
| [XBMC](https://github.com/caronc/apprise/wiki/Notify_xbmc) | xbmc:// or xbmcs://    | (TCP) 8080 or 443   | xbmc://hostname<br />xbmc://user@hostname<br />xbmc://user:password@hostname:port
| [Zulip Chat](https://github.com/caronc/apprise/wiki/Notify_zulip) | zulip://  | (TCP) 443   | zulip://botname@Organization/Token<br />zulip://botname@Organization/Token/Stream<br />zulip://botname@Organization/Token/Email

## SMS Notifications

SMS Notifications for the most part do not have a both a `title` and `body`.  They consist of a single `body` which is usually no more then 160 characters in length.  When using Apprise, the `title` and `body` are therefore combined into a single message prior to their transmission.

| Notification Service | Service ID | Default Port | Example Syntax |
| -------------------- | ---------- | ------------ | -------------- |
| [Africas Talking](https://github.com/caronc/apprise/wiki/Notify_africas_talking) | atalk://  | (TCP) 443   | atalk://AppUser@ApiKey/ToPhoneNo<br/>atalk://AppUser@ApiKey/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Automated Packet Reporting System (ARPS)](https://github.com/caronc/apprise/wiki/Notify_aprs)  | aprs:// | (TCP) 10152 | aprs://user:pass@callsign<br/>aprs://user:pass@callsign1/callsign2/callsignN
| [AWS SNS](https://github.com/caronc/apprise/wiki/Notify_sns)  | sns://   | (TCP) 443   | sns://AccessKeyID/AccessSecretKey/RegionName/+PhoneNo<br/>sns://AccessKeyID/AccessSecretKey/RegionName/+PhoneNo1/+PhoneNo2/+PhoneNoN<br/>sns://AccessKeyID/AccessSecretKey/RegionName/Topic<br/>sns://AccessKeyID/AccessSecretKey/RegionName/Topic1/Topic2/TopicN
| [BulkSMS](https://github.com/caronc/apprise/wiki/Notify_bulksms) | bulksms://  | (TCP) 443   | bulksms://user:password@ToPhoneNo<br/>bulksms://User:Password@ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [BulkVS](https://github.com/caronc/apprise/wiki/Notify_bulkvs) | bulkvs://  | (TCP) 443   | bulkvs://user:password@FromPhoneNo<br/>bulkvs://user:password@FromPhoneNo/ToPhoneNo<br/>bulkvs://user:password@FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Burst SMS](https://github.com/caronc/apprise/wiki/Notify_burst_sms) | burstsms://  | (TCP) 443   | burstsms://ApiKey:ApiSecret@FromPhoneNo/ToPhoneNo<br/>burstsms://ApiKey:ApiSecret@FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Clickatell](https://github.com/caronc/apprise/wiki/Notify_clickatell)                         | clickatell://               | (TCP) 443       | clickatell://ApiKey/ToPhoneNo<br/>clickatell://FromPhoneNo@ApiKey/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN
| [ClickSend](https://github.com/caronc/apprise/wiki/Notify_clicksend) | clicksend://  | (TCP) 443   | clicksend://user:pass@PhoneNo<br/>clicksend://user:pass@ToPhoneNo1/ToPhoneNo2/ToPhoneNoN
| [DAPNET](https://github.com/caronc/apprise/wiki/Notify_dapnet) | dapnet://  | (TCP) 80   | dapnet://user:pass@callsign<br/>dapnet://user:pass@callsign1/callsign2/callsignN
| [D7 Networks](https://github.com/caronc/apprise/wiki/Notify_d7networks) | d7sms://  | (TCP) 443   | d7sms://token@PhoneNo<br/>d7sms://token@ToPhoneNo1/ToPhoneNo2/ToPhoneNoN
| [DingTalk](https://github.com/caronc/apprise/wiki/Notify_dingtalk)  | dingtalk://   | (TCP) 443   | dingtalk://token/<br />dingtalk://token/ToPhoneNo<br />dingtalk://token/ToPhoneNo1/ToPhoneNo2/ToPhoneNo1/
| [Free-Mobile](https://github.com/caronc/apprise/wiki/Notify_freemobile)  | freemobile://   | (TCP) 443   | freemobile://user@password/
| [httpSMS](https://github.com/caronc/apprise/wiki/Notify_httpsms) | httpsms://  | (TCP) 443   | httpsms://ApiKey@FromPhoneNo<br/>httpsms://ApiKey@FromPhoneNo/ToPhoneNo<br/>httpsms://ApiKey@FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Kavenegar](https://github.com/caronc/apprise/wiki/Notify_kavenegar) | kavenegar://  | (TCP) 443   | kavenegar://ApiKey/ToPhoneNo<br/>kavenegar://FromPhoneNo@ApiKey/ToPhoneNo<br/>kavenegar://ApiKey/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN
| [MessageBird](https://github.com/caronc/apprise/wiki/Notify_messagebird) | msgbird://  | (TCP) 443   | msgbird://ApiKey/FromPhoneNo<br/>msgbird://ApiKey/FromPhoneNo/ToPhoneNo<br/>msgbird://ApiKey/FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [MSG91](https://github.com/caronc/apprise/wiki/Notify_msg91) | msg91://  | (TCP) 443   | msg91://TemplateID@AuthKey/ToPhoneNo<br/>msg91://TemplateID@AuthKey/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Plivo](https://github.com/caronc/apprise/wiki/Notify_plivo) | plivo://  | (TCP) 443   | plivo://AuthID@Token@FromPhoneNo<br/>plivo://AuthID@Token/FromPhoneNo/ToPhoneNo<br/>plivo://AuthID@Token/FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Seven](https://github.com/caronc/apprise/wiki/Notify_seven)                                   | seven://                    | (TCP) 443   | seven://ApiKey/FromPhoneNo<br/>seven://ApiKey/FromPhoneNo/ToPhoneNo<br/>seven://ApiKey/FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Société Française du Radiotéléphone (SFR)](https://github.com/caronc/apprise/wiki/Notify_sfr) | sfr://   | (TCP) 443    | sfr://user:password>@spaceId/ToPhoneNo<br/>sfr://user:password>@spaceId/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Signal API](https://github.com/caronc/apprise/wiki/Notify_signal) | signal://  or signals:// | (TCP) 80 or 443  | signal://hostname:port/FromPhoneNo<br/>signal://hostname:port/FromPhoneNo/ToPhoneNo<br/>signal://hostname:port/FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Sinch](https://github.com/caronc/apprise/wiki/Notify_sinch) | sinch://  | (TCP) 443   | sinch://ServicePlanId:ApiToken@FromPhoneNo<br/>sinch://ServicePlanId:ApiToken@FromPhoneNo/ToPhoneNo<br/>sinch://ServicePlanId:ApiToken@FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/<br/>sinch://ServicePlanId:ApiToken@ShortCode/ToPhoneNo<br/>sinch://ServicePlanId:ApiToken@ShortCode/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [SMPP](https://github.com/caronc/apprise/wiki/Notify_SMPP)    | smpp:// or smpps://  | (TCP) 443  | smpp://user:password@hostname:port/FromPhoneNo/ToPhoneNo<br/>smpps://user:password@hostname:port/FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN
| [SMSEagle](https://github.com/caronc/apprise/wiki/Notify_smseagle) | smseagle:// or smseagles:// | (TCP) 80 or 443  | smseagles://hostname:port/ToPhoneNo<br/>smseagles://hostname:port/@ToContact<br/>smseagles://hostname:port/#ToGroup<br/>smseagles://hostname:port/ToPhoneNo1/#ToGroup/@ToContact/
| [SMS Manager](https://github.com/caronc/apprise/wiki/Notify_sms_manager) | smsmgr://  | (TCP) 443   | smsmgr://ApiKey@ToPhoneNo<br/>smsmgr://ApiKey@ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Threema Gateway](https://github.com/caronc/apprise/wiki/Notify_threema) | threema://  | (TCP) 443   | threema://GatewayID@secret/ToPhoneNo<br/>threema://GatewayID@secret/ToEmail<br/>threema://GatewayID@secret/ToThreemaID/<br/>threema://GatewayID@secret/ToEmail/ToThreemaID/ToPhoneNo/...
| [Twilio](https://github.com/caronc/apprise/wiki/Notify_twilio) | twilio://  | (TCP) 443   | twilio://AccountSid:AuthToken@FromPhoneNo<br/>twilio://AccountSid:AuthToken@FromPhoneNo/ToPhoneNo<br/>twilio://AccountSid:AuthToken@FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/<br/>twilio://AccountSid:AuthToken@FromPhoneNo/ToPhoneNo?apikey=Key<br/>twilio://AccountSid:AuthToken@ShortCode/ToPhoneNo<br/>twilio://AccountSid:AuthToken@ShortCode/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/<br/>twilio://AccountSid:AuthToken@FromPhoneNo/ToPhoneNo?method=call<br/>twilio://AccountSid:AuthToken@FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN?method=call
| [Voipms](https://github.com/caronc/apprise/wiki/Notify_voipms) | voipms://  | (TCP) 443   | voipms://password:email/FromPhoneNo<br/>voipms://password:email/FromPhoneNo/ToPhoneNo<br/>voipms://password:email/FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/
| [Vonage](https://github.com/caronc/apprise/wiki/Notify_nexmo) (formerly Nexmo) | nexmo://  | (TCP) 443   | nexmo://ApiKey:ApiSecret@FromPhoneNo<br/>nexmo://ApiKey:ApiSecret@FromPhoneNo/ToPhoneNo<br/>nexmo://ApiKey:ApiSecret@FromPhoneNo/ToPhoneNo1/ToPhoneNo2/ToPhoneNoN/

## Desktop Notifications

| Notification Service | Service ID | Default Port | Example Syntax |
| -------------------- | ---------- | ------------ | -------------- |
| [Linux DBus Notifications](https://github.com/caronc/apprise/wiki/Notify_dbus)  | dbus://<br />qt://<br />glib://<br />kde://  | n/a  | dbus://<br />qt://<br />glib://<br />kde://
| [Linux Gnome Notifications](https://github.com/caronc/apprise/wiki/Notify_gnome) | gnome://    |        n/a          | gnome://
| [MacOS X Notifications](https://github.com/caronc/apprise/wiki/Notify_macosx) | macosx://    |        n/a          | macosx://
| [Windows Notifications](https://github.com/caronc/apprise/wiki/Notify_windows) | windows://    |        n/a          | windows://

## Email Notifications

| Service ID | Default Port | Example Syntax |
| ---------- | ------------ | -------------- |
| [mailto://](https://github.com/caronc/apprise/wiki/Notify_email)  |  (TCP) 25    | mailto://userid:pass@domain.com<br />mailto://domain.com?user=userid&pass=password<br/>mailto://domain.com:2525?user=userid&pass=password<br />mailto://user@gmail.com&pass=password<br />mailto://mySendingUsername:mySendingPassword@example.com?to=receivingAddress@example.com<br />mailto://userid:password@example.com?smtp=mail.example.com&from=noreply@example.com&name=no%20reply
| [mailtos://](https://github.com/caronc/apprise/wiki/Notify_email) |  (TCP) 587   | mailtos://userid:pass@domain.com<br />mailtos://domain.com?user=userid&pass=password<br/>mailtos://domain.com:465?user=userid&pass=password<br />mailtos://user@hotmail.com&pass=password<br />mailtos://mySendingUsername:mySendingPassword@example.com?to=receivingAddress@example.com<br />mailtos://userid:password@example.com?smtp=mail.example.com&from=noreply@example.com&name=no%20reply

Apprise have some email services built right into it (such as yahoo, fastmail, hotmail, gmail, etc) that greatly simplify the mailto:// service.  See more details [here](https://github.com/caronc/apprise/wiki/Notify_email).

## Custom Notifications

| Post Method          | Service ID | Default Port | Example Syntax |
| -------------------- | ---------- | ------------ | -------------- |
| [Form](https://github.com/caronc/apprise/wiki/Notify_Custom_Form)       | form:// or forms://   | (TCP) 80 or 443 | form://hostname<br />form://user@hostname<br />form://user:password@hostname:port<br />form://hostname/a/path/to/post/to
| [JSON](https://github.com/caronc/apprise/wiki/Notify_Custom_JSON)       | json:// or jsons://   | (TCP) 80 or 443 | json://hostname<br />json://user@hostname<br />json://user:password@hostname:port<br />json://hostname/a/path/to/post/to
| [XML](https://github.com/caronc/apprise/wiki/Notify_Custom_XML)         | xml:// or xmls://   | (TCP) 80 or 443 | xml://hostname<br />xml://user@hostname<br />xml://user:password@hostname:port<br />xml://hostname/a/path/to/post/to

# Installation

The easiest way is to install Apprise from PyPI:
```bash
pip install apprise
```

Apprise is also packaged as an RPM and available through [EPEL](https://docs.fedoraproject.org/en-US/epel/) supporting CentOS, Redhat, Rocky, Oracle Linux, etc.
```bash
# Follow instructions on https://docs.fedoraproject.org/en-US/epel
# to get your system connected up to EPEL and then:
# Redhat/CentOS 7.x users
yum install apprise

# Redhat/CentOS 8.x+ and/or Fedora Users
dnf install apprise
```

You can also check out the [Graphical version of Apprise](https://github.com/caronc/apprise-api) to centralize your configuration and notifications through a manageable webpage.

# Command Line Usage

A small command line interface (CLI) tool is also provided with this package called *apprise*. If you know the server urls you wish to notify, you can simply provide them all on the command line and send your notifications that way:
```bash
# Send a notification to as many servers as you want
# as you can easily chain one after another (the -vv provides some
# additional verbosity to help let you know what is going on):
apprise -vv -t 'my title' -b 'my notification body' \
   'mailto://myemail:mypass@gmail.com' \
   'pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b'

# If you don't specify a --body (-b) then stdin is used allowing
# you to use the tool as part of your every day administration:
cat /proc/cpuinfo | apprise -vv -t 'cpu info' \
   'mailto://myemail:mypass@gmail.com'

# The title field is totally optional
uptime | apprise -vv \
   'discord:///4174216298/JHMHI8qBe7bk2ZwO5U711o3dV_js'
```

## CLI Configuration Files

No one wants to put their credentials out for everyone to see on the command line.  No problem *apprise* also supports configuration files.  It can handle both a specific [YAML format](https://github.com/caronc/apprise/wiki/config_yaml) or a very simple [TEXT format](https://github.com/caronc/apprise/wiki/config_text). You can also pull these configuration files via an HTTP query too! You can read more about the expected structure of the configuration files [here](https://github.com/caronc/apprise/wiki/config).
```bash
# By default if no url or configuration is specified apprise will attempt to load
# configuration files (if present) from:
#  ~/.apprise
#  ~/.apprise.yaml
#  ~/.config/apprise.conf
#  ~/.config/apprise.yaml
#  /etc/apprise.conf
#  /etc/apprise.yaml

# Also a subdirectory handling allows you to leverage plugins
#  ~/.apprise/apprise
#  ~/.apprise/apprise.yaml
#  ~/.config/apprise/apprise.conf
#  ~/.config/apprise/apprise.yaml
#  /etc/apprise/apprise.yaml
#  /etc/apprise/apprise.conf

# Windows users can store their default configuration files here:
#  %APPDATA%/Apprise/apprise.conf
#  %APPDATA%/Apprise/apprise.yaml
#  %LOCALAPPDATA%/Apprise/apprise.conf
#  %LOCALAPPDATA%/Apprise/apprise.yaml
#  %ALLUSERSPROFILE%\Apprise\apprise.conf
#  %ALLUSERSPROFILE%\Apprise\apprise.yaml
#  %PROGRAMFILES%\Apprise\apprise.conf
#  %PROGRAMFILES%\Apprise\apprise.yaml
#  %COMMONPROGRAMFILES%\Apprise\apprise.conf
#  %COMMONPROGRAMFILES%\Apprise\apprise.yaml

# The configuration files specified above can also be identified with a `.yml`
# extension or even just entirely removing the `.conf` extension altogether.

# If you loaded one of those files, your command line gets really easy:
apprise -vv -t 'my title' -b 'my notification body'

# If you want to deviate from the default paths or specify more than one,
# just specify them using the --config switch:
apprise -vv -t 'my title' -b 'my notification body' \
   --config=/path/to/my/config.yml

# Got lots of configuration locations? No problem, you can specify them all:
# Apprise can even fetch the configuration from over a network!
apprise -vv -t 'my title' -b 'my notification body' \
   --config=/path/to/my/config.yml \
   --config=https://localhost/my/apprise/config
```

## CLI File Attachments

Apprise also supports file attachments too! Specify as many attachments to a notification as you want.
```bash
# Send a funny image you found on the internet to a colleague:
apprise -vv --title 'Agile Joke' \
        --body 'Did you see this one yet?' \
        --attach https://i.redd.it/my2t4d2fx0u31.jpg \
        'mailto://myemail:mypass@gmail.com'

# Easily send an update from a critical server to your dev team
apprise -vv --title 'system crash' \
        --body 'I do not think Jim fixed the bug; see attached...' \
        --attach /var/log/myprogram.log \
        --attach /var/debug/core.2345 \
        --tag devteam
```

## CLI Loading Custom Notifications/Hooks

To create your own custom `schema://` hook so that you can trigger your own custom code,
simply include the `@notify` decorator to wrap your function.
```python
from apprise.decorators import notify
#
# The below assumes you want to catch foobar:// calls:
#
@notify(on="foobar", name="My Custom Foobar Plugin")
def my_custom_notification_wrapper(body, title, notify_type, *args, **kwargs):
    """My custom notification function that triggers on all foobar:// calls
    """
    # Write all of your code here... as an example...
    print("{}: {} - {}".format(notify_type.upper(), title, body))

    # Returning True/False is a way to relay your status back to Apprise.
    # Returning nothing (None by default) is always interpreted as a Success
```

Once you've defined your custom hook, you just need to tell Apprise where it is at runtime.
```bash
# By default if no plugin path is specified apprise will attempt to load
# all plugin files (if present) from the following directory paths:
#  ~/.apprise/plugins
#  ~/.config/apprise/plugins
#  /var/lib/apprise/plugins

# Windows users can store their default plugin files in these directories:
#  %APPDATA%/Apprise/plugins
#  %LOCALAPPDATA%/Apprise/plugins
#  %ALLUSERSPROFILE%\Apprise\plugins
#  %PROGRAMFILES%\Apprise\plugins
#  %COMMONPROGRAMFILES%\Apprise\plugins

# If you placed your plugin file within one of the directories already defined
# above, then your call simply needs to look like:
apprise -vv --title 'custom override' \
        --body 'the body of my message' \
        foobar:\\

# However you can override the path like so
apprise -vv --title 'custom override' \
        --body 'the body of my message' \
        --plugin-path /path/to/my/plugin.py \
        foobar:\\
```

You can read more about creating your own custom notifications and/or hooks [here](https://github.com/caronc/apprise/wiki/decorator_notify).

## CLI Environment Variables

Those using the Command Line Interface (CLI) can also leverage environment variables to pre-set the default settings:

| Variable                | Description       |
|------------------------ | ----------------- |
| `APPRISE_URLS`          |  Specify the default URLs to notify IF none are otherwise specified on the command line explicitly. If the `--config` (`-c`) is specified, then this will overrides any reference to this variable. Use white space and/or a comma (`,`) to delimit multiple entries.
|  `APPRISE_CONFIG_PATH`  | Explicitly specify the config search path to use (overriding the default). The path(s) defined here must point to the absolute filename to open/reference. Use a semi-colon (`;`), line-feed (`\n`), and/or carriage return (`\r`) to delimit multiple entries.
|  `APPRISE_PLUGIN_PATH`  | Explicitly specify the custom plugin search path to use (overriding the default). Use a semi-colon (`;`), line-feed (`\n`), and/or carriage return (`\r`) to delimit multiple entries.
|  `APPRISE_STORAGE_PATH` | Explicitly specify the persistent storage path to use (overriding the default).

# Developer API Usage

To send a notification from within your python application, just do the following:
```python
import apprise

# Create an Apprise instance
apobj = apprise.Apprise()

# Add all of the notification services by their server url.
# A sample email notification:
apobj.add('mailto://myuserid:mypass@gmail.com')

# A sample pushbullet notification
apobj.add('pbul://o.gn5kj6nfhv736I7jC3cj3QLRiyhgl98b')

# Then notify these services any time you desire. The below would
# notify all of the services loaded into our Apprise object.
apobj.notify(
    body='what a great notification service!',
    title='my notification title',
)
```

## API Configuration Files

Developers need access to configuration files too. The good news is their use just involves declaring another object (called *AppriseConfig*) that the *Apprise* object can ingest.  You can also freely mix and match config and notification entries as often as you wish! You can read more about the expected structure of the configuration files [here](https://github.com/caronc/apprise/wiki/config).
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
apobj.add('mailto://myuser:mypass@hotmail.com', tag='admin')

# Then notify these services any time you desire. The below would
# notify all of the services that have not been bound to any specific
# tag.
apobj.notify(
    body='what a great notification service!',
    title='my notification title',
)

# Tagging allows you to specifically target only specific notification
# services you've loaded:
apobj.notify(
    body='send a notification to our admin group',
    title='Attention Admins',
    # notify any services tagged with the 'admin' tag
    tag='admin',
)

# If you want to notify absolutely everything (regardless of whether
# it's been tagged or not), just use the reserved tag of 'all':
apobj.notify(
    body='send a notification to our admin group',
    title='Attention Admins',
    # notify absolutely everything loaded, regardless on whether
    # it has a tag associated with it or not:
    tag='all',
)
```

## API File Attachments

Attachments are very easy to send using the Apprise API:
```python
import apprise

# Create an Apprise instance
apobj = apprise.Apprise()

# Add at least one service you want to notify
apobj.add('mailto://myuser:mypass@hotmail.com')

# Then send your attachment.
apobj.notify(
    title='A great photo of our family',
    body='The flash caused Jane to close her eyes! hah! :)',
    attach='/local/path/to/my/DSC_003.jpg',
)

# Send a web based attachment too! In the below example, we connect to a home
# security camera and send a live image to an email. By default remote web
# content is cached, but for a security camera we might want to call notify
# again later in our code, so we want our last image retrieved to expire(in
# this case after 3 seconds).
apobj.notify(
    title='Latest security image',
    attach='http://admin:password@hikvision-cam01/ISAPI/Streaming/channels/101/picture?cache=3'
)
```

To send more than one attachment, just use a list, set, or tuple instead:
```python
import apprise

# Create an Apprise instance
apobj = apprise.Apprise()

# Add at least one service you want to notify
apobj.add('mailto://myuser:mypass@hotmail.com')

# Now add all of the entries we're interested in:
attach = (
    # ?name= allows us to rename the actual jpeg as found on the site
    # to be another name when sent to our receipient(s)
    'https://i.redd.it/my2t4d2fx0u31.jpg?name=FlyingToMars.jpg',

    # Now add another:
    '/path/to/funny/joke.gif',
)

# Send your multiple attachments with a single notify call:
apobj.notify(
    title='Some good jokes.',
    body='Hey guys, check out these!',
    attach=attach,
)
```

## API Loading Custom Notifications/Hooks

By default, no custom plugins are loaded at all for those building from within the Apprise API.
It's at the developers discretion to load custom modules. But should you choose to do so, it's as easy
as including the path reference in the `AppriseAsset()` object prior to the initialization of your `Apprise()`
instance.

For example:
```python
from apprise import Apprise
from apprise import AppriseAsset

# Prepare your Asset object so that you can enable the custom plugins to
# be loaded for your instance of Apprise...
asset = AppriseAsset(plugin_paths="/path/to/scan")

# OR You can also generate scan more then one file too:
asset = AppriseAsset(
    plugin_paths=[
        # Iterate over all python libraries found in the root of the
        # specified path. This is NOT a recursive (directory) scan; only
        # the first level is parsed. HOWEVER, if a directory containing
        # an __init__.py is found, it will be included in the load.
        "/dir/containing/many/python/libraries",

        # An absolute path to a plugin.py to exclusively load
        "/path/to/plugin.py",

        # if you point to a directory that has an __init__.py file found in
        # it, then only that file is loaded (it's similar to point to a
        # absolute .py file. Hence, there is no (level 1) scanning at all
        # within the directory specified.
        "/path/to/dir/library"
    ]
)

# Now that we've got our asset, we just work with our Apprise object as we
# normally do
aobj = Apprise(asset=asset)

# If our new custom `foobar://` library was loaded (presuming we prepared
# one like in the examples above).  then you would be able to safely add it
# into Apprise at this point
aobj.add('foobar://')

# Send our notification out through our foobar://
aobj.notify("test")
```

You can read more about creating your own custom notifications and/or hooks [here](https://github.com/caronc/apprise/wiki/decorator_notify).

# Persistent Storage

Persistent storage allows Apprise to cache re-occurring actions optionaly to disk. This can greatly reduce the overhead used to send a notification.

There are 3 Persistent Storage operational states Apprise can operate using:
1. `auto`:  Flush gathered cache information to the filesystem on demand.  This option is incredibly light weight.  This is the default behavior for all CLI usage.
   * Developers who choose to use this operational mode can also force cached information manually if they choose.
   * The CLI will use this operational mode by default.
1. `flush`: Flushes any cache information to the filesystem during every transaction.
1. `memory`: Effectively disable Persistent Storage.  Any caching of data required by each plugin used is done in memory.  Apprise effectively operates as it always did before peristent storage was available. This setting ensures no content is every written to disk.
   * By default this is the mode Apprise will operate under for those developing with it unless they configure it to otherwise operate as `auto` or `flush`.  This is done through the `AppriseAsset()` object and is explained further on in this documentation.

## CLI Persistent Storage Commands

You can provide the keyword `storage` on your CLI call to see the persistent storage options available to you.
```bash
# List all of the occupied space used by Apprise's Persistent Storage:
apprise storage list

# list is the default option, so the following does the same thing:
apprise storage

# You can prune all of your storage older then 30 days
# and not accessed for this period like so:
apprise storage prune

# You can do a hard reset (and wipe all persistent storage) with:
apprise storage clean

```

You can also filter your results by adding tags and/or URL Identifiers.  When you get a listing (`apprise storage list`), you may see:
```
   # example output of 'apprise storage list':
   1. f7077a65                                             0.00B    unused
      - matrixs://abcdef:****@synapse.example12.com/%23general?image=no&mode=off&version=3&msgtype...
      tags: team

   2. 0e873a46                                            81.10B    active
      - tgram://W...U//?image=False&detect=yes&silent=no&preview=no&content=before&mdv=v1&format=m...
      tags: personal

   3. abcd123                                             12.00B    stale

```
The (persistent storage) cache states are:
 - `unused`: This plugin has not commited anything to disk for reuse/cache purposes
 - `active`: This plugin has written content to disk.  Or at the very least, it has prepared a persistent storage location it can write into.
 - `stale`: The system detected a location where a URL may have possibly written to in the past, but there is nothing linking to it using the URLs provided.  It is likely wasting space or is no longer of any use.

You can use this information to filter your results by specifying _URL ID_ (UID) values after your command.  For example:
```bash
# The below commands continue with the example already identified above
# the following would match abcd123 (even though just ab was provided)
# The output would only list the 'stale' entry above
apprise storage list ab

# knowing our filter is safe, we could remove it
# the below command would not obstruct our other to URLs and would only
# remove our stale one:
apprise storage clean ab

# Entries can be filtered by tag as well:
apprise storage list --tag=team

# You can match on multiple URL ID's as well:
# The followin would actually match the URL ID's of 1. and .2 above
apprise storage list f 0
```
When using the CLI, Persistent storage is set to the operational mode of `auto` by default, you can change this by providing `--storage-mode=` (`-SM`) during your calls.  If you want to ensure it's always set to a value of your choice.

For more information on persistent storage, [visit here](https://github.com/caronc/apprise/wiki/persistent_storage).

## API Persistent Storage Commands
For developers, persistent storage is set in the operational mode of `memory` by default.

It's at the developers discretion to enable it (by switching it to either `auto` or `flush`). Should you choose to do so: it's as easy as including the information in the `AppriseAsset()` object prior to the initialization of your `Apprise()` instance.

For example:
```python
from apprise import Apprise
from apprise import AppriseAsset
from apprise import PersistentStoreMode

# Prepare a location the persistent storage can write it's cached content to.
# By setting this path, this immediately assumes you wish to operate the
# persistent storage in the operational 'auto' mode
asset = AppriseAsset(storage_path="/path/to/save/data")

# If you want to be more explicit and set more options, then you may do the
# following
asset = AppriseAsset(
    # Set our storage path directory (minimum requirement to enable it)
    storage_path="/path/to/save/data",

    # Set the mode... the options are:
    # 1. PersistentStoreMode.MEMORY
    #       - disable persistent storage from writing to disk
    # 2. PersistentStoreMode.AUTO
    #       - write to disk on demand
    # 3. PersistentStoreMode.FLUSH
    #       - write to disk always and often
    storage_mode=PersistentStoreMode.FLUSH

    # The URL IDs are by default 8 characters in length. You can increase and
    # decrease it's value here.  The value must be > 2. The default value is 8
    # if not otherwise specified
    storage_idlen=8,
)

# Now that we've got our asset, we just work with our Apprise object as we
# normally do
aobj = Apprise(asset=asset)
```

For more information on persistent storage, [visit here](https://github.com/caronc/apprise/wiki/persistent_storage).

# Want To Learn More?

If you're interested in reading more about this and other methods on how to customize your own notifications, please check out the following links:
* 📣 [Using the CLI](https://github.com/caronc/apprise/wiki/CLI_Usage)
* 🛠️ [Development API](https://github.com/caronc/apprise/wiki/Development_API)
* 🔧 [Troubleshooting](https://github.com/caronc/apprise/wiki/Troubleshooting)
* ⚙️ [Configuration File Help](https://github.com/caronc/apprise/wiki/config)
* ⚡ [Create Your Own Custom Notifications](https://github.com/caronc/apprise/wiki/decorator_notify)
* 💾 [Persistent Storage](https://github.com/caronc/apprise/wiki/persistent_storage)
* 🌎 [Apprise API/Web Interface](https://github.com/caronc/apprise-api)
* 🎉 [Showcase](https://github.com/caronc/apprise/wiki/showcase)

Want to help make Apprise better?
* 💡 [Contribute to the Apprise Code Base](https://github.com/caronc/apprise/wiki/Development_Contribution)
* ❤️ [Sponsorship and Donations](https://github.com/caronc/apprise/wiki/Sponsors)
