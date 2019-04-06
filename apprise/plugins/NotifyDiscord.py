# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

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
from ..common import NotifyImageSize
from ..common import NotifyFormat
from ..common import NotifyType
from ..utils import parse_bool


class NotifyDiscord(NotifyBase):
    """
    A wrapper to Discord Notifications

    """
    # The default descriptive name associated with the Notification
    service_name = 'Discord'

    # The services URL
    service_url = 'https://discordapp.com/'

    # The default secure protocol
    secure_protocol = 'discord'

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_discord'

    # Discord Webhook
    notify_url = 'https://discordapp.com/api/webhooks'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 2000

    def __init__(self, webhook_id, webhook_token, tts=False, avatar=True,
                 footer=False, footer_logo=True, include_image=True, **kwargs):
        """
        Initialize Discord Object

        """
        super(NotifyDiscord, self).__init__(**kwargs)

        if not webhook_id:
            msg = 'An invalid Client ID was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        if not webhook_token:
            msg = 'An invalid Webhook Token was specified.'
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our data
        self.webhook_id = webhook_id
        self.webhook_token = webhook_token

        # Text To Speech
        self.tts = tts

        # Over-ride Avatar Icon
        self.avatar = avatar

        # Place a footer
        self.footer = footer

        # include a footer_logo in footer
        self.footer_logo = footer_logo

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        return

    def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
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
        }

        # Acquire image_url
        image_url = self.image_url(notify_type)

        if self.notify_format == NotifyFormat.MARKDOWN:
            # Use embeds for payload
            payload['embeds'] = [{
                'provider': {
                    'name': self.app_id,
                    'url': self.app_url,
                },
                'title': title,
                'type': 'rich',
                'description': body,

                # Our color associated with our notification
                'color': self.color(notify_type, int),
            }]

            # Break titles out so that we can sort them in embeds
            fields = self.extract_markdown_sections(body)

            if len(fields) > 0:
                # Apply our additional parsing for a better presentation

                # Swap first entry for description
                payload['embeds'][0]['description'] = \
                    fields[0].get('name') + fields[0].get('value')
                payload['embeds'][0]['fields'] = fields[1:]

            if self.footer:
                # Acquire logo URL
                logo_url = self.image_url(notify_type, logo=True)

                # Set Footer text to our app description
                payload['embeds'][0]['footer'] = {
                    'text': self.app_desc,
                }

                if self.footer_logo and logo_url:
                    payload['embeds'][0]['footer']['icon_url'] = logo_url

            if self.include_image and image_url:
                payload['embeds'][0]['thumbnail'] = {
                    'url': image_url,
                    'height': 256,
                    'width': 256,
                }

        else:
            # not markdown
            payload['content'] = \
                body if not title else "{}\r\n{}".format(title, body)

        if self.avatar and image_url:
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

        # Always call throttle before any remote server i/o is made
        self.throttle()

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
                status_str = \
                    NotifyBase.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send Discord notification: '
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

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

    def url(self):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any arguments set
        args = {
            'format': self.notify_format,
            'overflow': self.overflow_mode,
            'tts': 'yes' if self.tts else 'no',
            'avatar': 'yes' if self.avatar else 'no',
            'footer': 'yes' if self.footer else 'no',
            'footer_logo': 'yes' if self.footer_logo else 'no',
            'image': 'yes' if self.include_image else 'no',
            'verify': 'yes' if self.verify_certificate else 'no',
        }

        return '{schema}://{webhook_id}/{webhook_token}/?{args}'.format(
            schema=self.secure_protocol,
            webhook_id=NotifyDiscord.quote(self.webhook_id, safe=''),
            webhook_token=NotifyDiscord.quote(self.webhook_token, safe=''),
            args=NotifyDiscord.urlencode(args),
        )

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
        webhook_id = NotifyDiscord.unquote(results['host'])

        # Now fetch our tokens
        try:
            webhook_token = \
                NotifyDiscord.split_path(results['fullpath'])[0]

        except IndexError:
            # Force some bad values that will get caught
            # in parsing later
            webhook_token = None

        results['webhook_id'] = webhook_id
        results['webhook_token'] = webhook_token

        # Text To Speech
        results['tts'] = parse_bool(results['qsd'].get('tts', False))

        # Use Footer
        results['footer'] = parse_bool(results['qsd'].get('footer', False))

        # Use Footer Logo
        results['footer_logo'] = \
            parse_bool(results['qsd'].get('footer_logo', True))

        # Update Avatar Icon
        results['avatar'] = parse_bool(results['qsd'].get('avatar', True))

        # Use Thumbnail
        if 'thumbnail' in results['qsd']:
            # Deprication Notice issued for v0.7.5
            NotifyDiscord.logger.deprecate(
                'The Discord URL contains the parameter '
                '"thumbnail=" which will be deprecated in an upcoming '
                'release. Please use "image=" instead.'
            )

        # use image= for consistency with the other plugins but we also
        # support thumbnail= for backwards compatibility.
        results['include_image'] = \
            parse_bool(results['qsd'].get(
                'image', results['qsd'].get('thumbnail', False)))

        return results

    @staticmethod
    def extract_markdown_sections(markdown):
        """
        Takes a string in a markdown type format and extracts
        the headers and their corresponding sections into individual
        fields that get passed as an embed entry to Discord.

        """
        regex = re.compile(
            r'^\s*#+\s*(?P<name>[^#\n]+)([ \r\t\v#])?'
            r'(?P<value>([^ \r\t\v#].+?)(\n(?!\s#))|\s*$)', flags=re.S | re.M)

        common = regex.finditer(markdown)
        fields = list()
        for el in common:
            d = el.groupdict()

            fields.append({
                'name': d.get('name', '').strip(),
                'value': '```md\n' + d.get('value', '').strip() + '\n```'
            })

        return fields
