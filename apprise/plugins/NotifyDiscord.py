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
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _


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

    # Define object templates
    templates = (
        '{schema}://{webhook_id}/{webhook_token}',
        '{schema}://{botname}@{webhook_id}/{webhook_token}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'botname': {
            'name': _('Bot Name'),
            'type': 'string',
            'map_to': 'user',
        },
        'webhook_id': {
            'name': _('Webhook ID'),
            'type': 'string',
            'private': True,
            'required': True,
        },
        'webhook_token': {
            'name': _('Webhook Token'),
            'type': 'string',
            'private': True,
            'required': True,
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'tts': {
            'name': _('Text To Speech'),
            'type': 'bool',
            'default': False,
        },
        'avatar': {
            'name': _('Avatar Image'),
            'type': 'bool',
            'default': True,
        },
        'footer': {
            'name': _('Display Footer'),
            'type': 'bool',
            'default': False,
        },
        'footer_logo': {
            'name': _('Footer Logo'),
            'type': 'bool',
            'default': True,
        },
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': False,
            'map_to': 'include_image',
        },
    })

    def __init__(self, webhook_id, webhook_token, tts=False, avatar=True,
                 footer=False, footer_logo=True, include_image=False,
                 **kwargs):
        """
        Initialize Discord Object

        """
        super(NotifyDiscord, self).__init__(**kwargs)

        # Webhook ID (associated with project)
        self.webhook_id = validate_regex(webhook_id)
        if not self.webhook_id:
            msg = 'An invalid Discord Webhook ID ' \
                  '({}) was specified.'.format(webhook_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Token (associated with project)
        self.webhook_token = validate_regex(webhook_token)
        if not self.webhook_token:
            msg = 'An invalid Discord Webhook Token ' \
                  '({}) was specified.'.format(webhook_token)
            self.logger.warning(msg)
            raise TypeError(msg)

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

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform Discord Notification
        """

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

        if not self._send(payload):
            # We failed to post our message
            return False

        if attach:
            # Update our payload; the idea is to preserve it's other detected
            # and assigned values for re-use here too
            payload.update({
                # Text-To-Speech
                'tts': False,
                # Wait until the upload has posted itself before continuing
                'wait': True,
            })

            # Remove our text/title based content for attachment use
            if 'embeds' in payload:
                # Markdown
                del payload['embeds']

            if 'content' in payload:
                # Markdown
                del payload['content']

            # Send our attachments
            for attachment in attach:
                self.logger.info(
                    'Posting Discord Attachment {}'.format(attachment.name))
                if not self._send(payload, attach=attachment):
                    # We failed to post our message
                    return False

        # Otherwise return
        return True

    def _send(self, payload, attach=None, **kwargs):
        """
        Wrapper to the requests (post) object
        """

        # Our headers
        headers = {
            'User-Agent': self.app_id,
        }

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

        # Our attachment path (if specified)
        files = None
        try:

            # Open our attachment path if required:
            if attach:
                files = {'file': (attach.name, open(attach.path, 'rb'))}

            else:
                headers['Content-Type'] = 'application/json; charset=utf-8'

            r = requests.post(
                notify_url,
                data=payload if files else dumps(payload),
                headers=headers,
                files=files,
                verify=self.verify_certificate,
            )
            if r.status_code not in (
                    requests.codes.ok, requests.codes.no_content):

                # We had a problem
                status_str = \
                    NotifyBase.http_response_code_lookup(r.status_code)

                self.logger.warning(
                    'Failed to send {}to Discord notification: '
                    '{}{}error={}.'.format(
                        attach.name if attach else '',
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))

                # Return; we're done
                return False

            else:
                self.logger.info('Sent Discord {}.'.format(
                    'attachment' if attach else 'notification'))

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occured posting {}to Discord.'.format(
                    attach.name if attach else ''))
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        except (OSError, IOError) as e:
            self.logger.warning(
                'An I/O error occured while reading {}.'.format(
                    attach.name if attach else 'attachment'))
            self.logger.debug('I/O Exception: %s' % str(e))
            return False

        finally:
            # Close our file (if it's open) stored in the second element
            # of our files tuple (index 1)
            if files:
                files['file'][1].close()

        return True

    def url(self, privacy=False, *args, **kwargs):
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
            webhook_id=self.pprint(self.webhook_id, privacy, safe=''),
            webhook_token=self.pprint(self.webhook_token, privacy, safe=''),
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
    def parse_native_url(url):
        """
        Support https://discordapp.com/api/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
        """

        result = re.match(
            r'^https?://discordapp\.com/api/webhooks/'
            r'(?P<webhook_id>[0-9]+)/'
            r'(?P<webhook_token>[A-Z0-9_-]+)/?'
            r'(?P<args>\?.+)?$', url, re.I)

        if result:
            return NotifyDiscord.parse_url(
                '{schema}://{webhook_id}/{webhook_token}/{args}'.format(
                    schema=NotifyDiscord.secure_protocol,
                    webhook_id=result.group('webhook_id'),
                    webhook_token=result.group('webhook_token'),
                    args='' if not result.group('args')
                    else result.group('args')))

        return None

    @staticmethod
    def extract_markdown_sections(markdown):
        """
        Takes a string in a markdown type format and extracts
        the headers and their corresponding sections into individual
        fields that get passed as an embed entry to Discord.

        """
        regex = re.compile(
            r'\s*#[# \t\v]*(?P<name>[^\n]+)(\n|\s*$)'
            r'\s*((?P<value>[^#].+?)(?=\s*$|[\r\n]+\s*#))?', flags=re.S)

        common = regex.finditer(markdown)
        fields = list()
        for el in common:
            d = el.groupdict()

            fields.append({
                'name': d.get('name', '').strip('# \r\n\t\v'),
                'value': '```md\n' +
                (d.get('value').strip() if d.get('value') else '') + '\n```'
            })

        return fields
