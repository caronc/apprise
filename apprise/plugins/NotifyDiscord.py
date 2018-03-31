# -*- coding: utf-8 -*-
#
# Discord Notify Wrapper
#
# Copyright (C) 2018 Chris Caron <lead2gold@gmail.com>
#
# This file is part of apprise.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# For this to work correctly you need to create a webhook. To do this just
# click on the little gear icon next to the channel you're part of. From
# here you'll be able to access the Webhooks menu and create a new one.
#
#  When you've completed, you'll get a URL that looks a little like this:
#  https://discordapp.com/api/webhooks/417429632418316298/\
#         JHZ7lQml277CDHmQKMHI8qBe7bk2ZwO5UKjCiOAF7711o33MyqU344Qpgv7YTpadV_js
#
#  Simplified, it looks like this:
#     https://discordapp.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
#
#  This plugin will simply work using the url of:
#     discord://WEBHOOK_ID/WEBHOOK_TOKEN
#
# API Documentation on Webhooks:
#    - https://discordapp.com/developers/docs/resources/webhook
#
import re
import requests
from json import dumps

from .NotifyBase import NotifyBase
from .NotifyBase import HTTP_ERROR_MAP
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..utils import parse_bool


class NotifyDiscord(NotifyBase):
    """
    A wrapper to Discord Notifications

    """

    # The default secure protocol
    secure_protocol = 'discord'

    # Discord Webhook
    notify_url = 'https://discordapp.com/api/webhooks'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 2000

    # Default Notify Format
    notify_format = NotifyFormat.MARKDOWN

    def __init__(self, webhook_id, webhook_token, tts=False, avatar=True,
                 footer=False, thumbnail=True, **kwargs):
        """
        Initialize Discord Object

        """
        super(NotifyDiscord, self).__init__(**kwargs)

        if not webhook_id:
            raise TypeError(
                'An invalid Client ID was specified.'
            )

        if not webhook_token:
            raise TypeError(
                'An invalid Webhook Token was specified.'
            )

        # Store our data
        self.webhook_id = webhook_id
        self.webhook_token = webhook_token

        # Text To Speech
        self.tts = tts

        # Over-ride Avatar Icon
        self.avatar = avatar

        # Place a footer icon
        self.footer = footer

        # Place a thumbnail image inline with the message body
        self.thumbnail = thumbnail

        return

    def notify(self, title, body, notify_type, **kwargs):
        """
        Perform Discord Notification
        """

        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'multipart/form-data',
        }

        # Prepare JSON Object
        payload = {
            # Text-To-Speech
            'tts': self.tts,

            # If Text-To-Speech is set to True, then we do not want to wait
            # for the whole message before continuing. Otherwise, we wait
            'wait': self.tts is False,

            # Our color associated with our notification
            'color': self.color(notify_type, int),

            'embeds': [{
                'provider': {
                    'name': self.app_id,
                    'url': self.app_url,
                },
                'title': title,
                'type': 'rich',
                'description': body,
            }]
        }

        if self.notify_format == NotifyFormat.MARKDOWN:
            fields = self.extract_markdown_sections(body)

            if len(fields) > 0:
                # Apply our additional parsing for a better presentation

                # Swap first entry for description
                payload['embeds'][0]['description'] = \
                    fields[0].get('name') + fields[0].get('value')
                payload['embeds'][0]['fields'] = fields[1:]

        if self.footer:
            logo_url = self.image_url(notify_type, logo=True)
            payload['embeds'][0]['footer'] = {
                'text': self.app_desc,
            }
            if logo_url:
                payload['embeds'][0]['footer']['icon_url'] = logo_url

        image_url = self.image_url(notify_type)
        if image_url:
            if self.thumbnail:
                payload['embeds'][0]['thumbnail'] = {
                    'url': image_url,
                    'height': 256,
                    'width': 256,
                }

            if self.avatar:
                payload['avatar_url'] = image_url

        if self.user:
            # Optionally override the default username of the webhook
            payload['username'] = self.user

        # Construct Notify URL
        notify_url = '{0}/{1}/{2}'.format(
            self.notify_url,
            self.webhook_id,
            self.webhook_token,
        )

        self.logger.debug('Discord POST URL: %s (cert_verify=%r)' % (
            notify_url, self.verify_certificate,
        ))
        self.logger.debug('Discord Payload: %s' % str(payload))
        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
            )
            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):
                # We had a problem
                try:
                    self.logger.warning(
                        'Failed to send Discord notification: '
                        '%s (error=%s).' % (
                            HTTP_ERROR_MAP[r.status_code],
                            r.status_code))

                except KeyError:
                    self.logger.warning(
                        'Failed to send Discord notification '
                        '(error=%s).' % r.status_code)

                self.logger.debug('Response Details: %s' % r.raw.read())

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Discord notification.')

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured sending Discord '
                'notification.'
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        return True

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to substantiate this object.

        Syntax:
          discord://webhook_id/webhook_token

        """
        results = NotifyBase.parse_url(url)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Store our webhook ID
        webhook_id = results['host']

        # Now fetch our tokens
        try:
            webhook_token = [x for x in filter(bool, NotifyBase.split_path(
                results['fullpath']))][0]

        except (ValueError, AttributeError, IndexError):
            # Force some bad values that will get caught
            # in parsing later
            webhook_token = None

        results['webhook_id'] = webhook_id
        results['webhook_token'] = webhook_token

        # Text To Speech
        results['tts'] = parse_bool(results['qsd'].get('tts', False))

        # Use Footer
        results['footer'] = parse_bool(results['qsd'].get('footer', False))

        # Update Avatar Icon
        results['avatar'] = parse_bool(results['qsd'].get('avatar', True))

        # Use Thumbnail
        results['thumbnail'] = \
            parse_bool(results['qsd'].get('thumbnail', True))

        return results

    @staticmethod
    def extract_markdown_sections(markdown):
        """
        Takes a string in a markdown type format and extracts
        the headers and their corresponding sections into individual
        fields that get passed as an embed entry to Discord.

        """
        regex = re.compile(
            r'\s*#+\s*(?P<name>[^#\n]+)([ \r\t\v#]*)'
            r'(?P<value>(.+?)(\n(?!\s#))|\s*$)', flags=re.S)

        common = regex.finditer(markdown)
        fields = list()
        for el in common:
            d = el.groupdict()

            fields.append({
                'name': d.get('name', '').strip(),
                'value': '```md\n' + d.get('value', '').strip() + '\n```'
            })

        return fields
