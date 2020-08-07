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

# There are 2 ways to use this plugin...
# Method 1: Via Webhook:
#   Visit https://my.slack.com/services/new/incoming-webhook/
#   to create a new incoming webhook for your account. You'll need to
#   follow the wizard to pre-determine the channel(s) you want your
#   message to broadcast to, and when you're complete, you will
#   recieve a URL that looks something like this:
#   https://hooks.slack.com/services/T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7
#                                       ^         ^               ^
#                                       |         |               |
#    These are important <--------------^---------^---------------^
#
# Method 2: Via a Bot:
#   1. visit: https://api.slack.com/apps?new_app=1
#   2. Pick an App Name (such as Apprise) and select your workspace.  Then
#       press 'Create App'
#   3. You'll be able to click on 'Bots' from here where you can then choose
#       to add a 'Bot User'.  Give it a name and choose 'Add Bot User'.
#   4. Now you can choose 'Install App' to which you can choose 'Install App
#       to Workspace'.
#   5. You will need to authorize the app which you get promopted to do.
#   6. Finally you'll get some important information providing you your
#      'OAuth Access Token' and 'Bot User OAuth Access Token' such as:
#        slack://{Oauth Access Token}
#
#        ... which might look something like:
#        slack://xoxp-1234-1234-1234-4ddbc191d40ee098cbaae6f3523ada2d
#        ... or:
#        slack://xoxb-1234-1234-4ddbc191d40ee098cbaae6f3523ada2d
#

import re
import requests
from json import dumps
from json import loads
from time import time

from .NotifyBase import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..common import NotifyFormat
from ..utils import parse_bool
from ..utils import parse_list
from ..utils import validate_regex
from ..AppriseLocale import gettext_lazy as _

# Extend HTTP Error Messages
SLACK_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}

# Used to break path apart into list of channels
CHANNEL_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')


class SlackMode(object):
    """
    Tracks the mode of which we're using Slack
    """
    # We're dealing with a webhook
    # Our token looks like: T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7
    WEBHOOK = 'webhook'

    # We're dealing with a bot (using the OAuth Access Token)
    # Our token looks like: xoxp-1234-1234-1234-abc124 or
    # Our token looks like: xoxb-1234-1234-abc124 or
    BOT = 'bot'


# Define our Slack Modes
SLACK_MODES = (
    SlackMode.WEBHOOK,
    SlackMode.BOT,
)


class NotifySlack(NotifyBase):
    """
    A wrapper for Slack Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = 'Slack'

    # The services URL
    service_url = 'https://slack.com/'

    # The default secure protocol
    secure_protocol = 'slack'

    # Allow 50 requests per minute (Tier 2).
    # 60/50 = 0.2
    request_rate_per_sec = 1.2

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = 'https://github.com/caronc/apprise/wiki/Notify_slack'

    # Slack Webhook URL
    webhook_url = 'https://hooks.slack.com/services'

    # Slack API URL (used with Bots)
    api_url = 'https://slack.com/api/{}'

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 35000

    # Default Notification Format
    notify_format = NotifyFormat.MARKDOWN

    # Bot's do not have default channels to notify; so #general
    # becomes the default channel in BOT mode
    default_notification_channel = '#general'

    # Define object templates
    templates = (
        # Webhook
        '{schema}://{token_a}/{token_b}{token_c}',
        '{schema}://{botname}@{token_a}/{token_b}{token_c}',
        '{schema}://{token_a}/{token_b}{token_c}/{targets}',
        '{schema}://{botname}@{token_a}/{token_b}{token_c}/{targets}',

        # Bot
        '{schema}://{access_token}/',
        '{schema}://{access_token}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        'botname': {
            'name': _('Bot Name'),
            'type': 'string',
            'map_to': 'user',
        },
        # Bot User OAuth Access Token
        # which always starts with xoxp- e.g.:
        #     xoxb-1234-1234-4ddbc191d40ee098cbaae6f3523ada2d
        'access_token': {
            'name': _('OAuth Access Token'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^xox[abp]-[A-Z0-9-]+$', 'i'),
        },
        # Token required as part of the Webhook request
        #  /AAAAAAAAA/........./........................
        'token_a': {
            'name': _('Token A'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Z0-9]+$', 'i'),
        },
        # Token required as part of the Webhook request
        #  /........./BBBBBBBBB/........................
        'token_b': {
            'name': _('Token B'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Z0-9]+$', 'i'),
        },
        # Token required as part of the Webhook request
        #  /........./........./CCCCCCCCCCCCCCCCCCCCCCCC
        'token_c': {
            'name': _('Token C'),
            'type': 'string',
            'private': True,
            'required': True,
            'regex': (r'^[A-Za-z0-9]+$', 'i'),
        },
        'target_encoded_id': {
            'name': _('Target Encoded ID'),
            'type': 'string',
            'prefix': '+',
            'map_to': 'targets',
        },
        'target_user': {
            'name': _('Target User'),
            'type': 'string',
            'prefix': '@',
            'map_to': 'targets',
        },
        'target_channels': {
            'name': _('Target Channel'),
            'type': 'string',
            'prefix': '#',
            'map_to': 'targets',
        },
        'targets': {
            'name': _('Targets'),
            'type': 'list:string',
        },
    })

    # Define our template arguments
    template_args = dict(NotifyBase.template_args, **{
        'image': {
            'name': _('Include Image'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_image',
        },
        'footer': {
            'name': _('Include Footer'),
            'type': 'bool',
            'default': True,
            'map_to': 'include_footer',
        },
        'to': {
            'alias_of': 'targets',
        },
    })

    def __init__(self, access_token=None, token_a=None, token_b=None,
                 token_c=None, targets=None, include_image=True,
                 include_footer=True, **kwargs):
        """
        Initialize Slack Object
        """
        super(NotifySlack, self).__init__(**kwargs)

        # Setup our mode
        self.mode = SlackMode.BOT if access_token else SlackMode.WEBHOOK

        if self.mode is SlackMode.WEBHOOK:
            self.token_a = validate_regex(
                token_a, *self.template_tokens['token_a']['regex'])
            if not self.token_a:
                msg = 'An invalid Slack (first) Token ' \
                      '({}) was specified.'.format(token_a)
                self.logger.warning(msg)
                raise TypeError(msg)

            self.token_b = validate_regex(
                token_b, *self.template_tokens['token_b']['regex'])
            if not self.token_b:
                msg = 'An invalid Slack (second) Token ' \
                      '({}) was specified.'.format(token_b)
                self.logger.warning(msg)
                raise TypeError(msg)

            self.token_c = validate_regex(
                token_c, *self.template_tokens['token_c']['regex'])
            if not self.token_c:
                msg = 'An invalid Slack (third) Token ' \
                      '({}) was specified.'.format(token_c)
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.access_token = validate_regex(
                access_token, *self.template_tokens['access_token']['regex'])
            if not self.access_token:
                msg = 'An invalid Slack OAuth Access Token ' \
                      '({}) was specified.'.format(access_token)
                self.logger.warning(msg)
                raise TypeError(msg)

        if not self.user:
            self.logger.warning(
                'No user was specified; using "%s".' % self.app_id)

        # Build list of channels
        self.channels = parse_list(targets)
        if len(self.channels) == 0:
            # No problem; the webhook is smart enough to just notify the
            # channel it was created for; adding 'None' is just used as
            # a flag lower to not set the channels
            self.channels.append(
                None if self.mode is SlackMode.WEBHOOK
                else self.default_notification_channel)

        # Formatting requirements are defined here:
        # https://api.slack.com/docs/message-formatting
        self._re_formatting_map = {
            # New lines must become the string version
            r'\r\*\n': '\\n',
            # Escape other special characters
            r'&': '&amp;',
            r'<': '&lt;',
            r'>': '&gt;',
        }

        # Iterate over above list and store content accordingly
        self._re_formatting_rules = re.compile(
            r'(' + '|'.join(self._re_formatting_map.keys()) + r')',
            re.IGNORECASE,
        )

        # Place a thumbnail image inline with the message body
        self.include_image = include_image

        # Place a footer with each post
        self.include_footer = include_footer
        return

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform Slack Notification
        """

        # error tracking (used for function return)
        has_error = False

        # Perform Formatting
        title = self._re_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_formatting_map[x.group()], title,
        )
        body = self._re_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_formatting_map[x.group()], body,
        )

        # Prepare JSON Object (applicable to both WEBHOOK and BOT mode)
        payload = {
            'username': self.user if self.user else self.app_id,
            # Use Markdown language
            'mrkdwn': (self.notify_format == NotifyFormat.MARKDOWN),
            'attachments': [{
                'title': title,
                'text': body,
                'color': self.color(notify_type),
                # Time
                'ts': time(),
            }],
        }

        # Prepare our URL (depends on mode)
        if self.mode is SlackMode.WEBHOOK:
            url = '{}/{}/{}/{}'.format(
                self.webhook_url,
                self.token_a,
                self.token_b,
                self.token_c,
            )

        else:  # SlackMode.BOT
            url = self.api_url.format('chat.postMessage')

        if self.include_footer:
            # Include the footer only if specified to do so
            payload['attachments'][0]['footer'] = self.app_id

        if attach and self.mode is SlackMode.WEBHOOK:
            # Be friendly; let the user know why they can't send their
            # attachments if using the Webhook mode
            self.logger.warning(
                'Slack Webhooks do not support attachments.')

        # Create a copy of the channel list
        channels = list(self.channels)

        attach_channel_list = []
        while len(channels):
            channel = channels.pop(0)

            if channel is not None:
                _channel = validate_regex(
                    channel, r'[+#@]?(?P<value>[A-Z0-9_]{1,32})')

                if not _channel:
                    # Channel over-ride was specified
                    self.logger.warning(
                        "The specified target {} is invalid;"
                        "skipping.".format(_channel))

                    # Mark our failure
                    has_error = True
                    continue

                if len(_channel) > 1 and _channel[0] == '+':
                    # Treat as encoded id if prefixed with a +
                    payload['channel'] = _channel[1:]

                elif len(_channel) > 1 and _channel[0] == '@':
                    # Treat @ value 'as is'
                    payload['channel'] = _channel

                else:
                    # Prefix with channel hash tag
                    payload['channel'] = '#{}'.format(_channel)

                # Store the valid and massaged payload that is recognizable by
                # slack. This list is used for sending attachments later.
                attach_channel_list.append(payload['channel'])

            # Acquire our to-be footer icon if configured to do so
            image_url = None if not self.include_image \
                else self.image_url(notify_type)

            if image_url:
                payload['icon_url'] = image_url

                if self.include_footer:
                    payload['attachments'][0]['footer_icon'] = image_url

            response = self._send(url, payload)
            if not response:
                # Handle any error
                has_error = True
                continue

            self.logger.info(
                'Sent Slack notification{}.'.format(
                    ' to {}'.format(channel)
                    if channel is not None else ''))

        if attach and self.mode is SlackMode.BOT and attach_channel_list:
            # Send our attachments (can only be done in bot mode)
            for attachment in attach:

                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        'Could not access attachment {}.'.format(
                            attachment.url(privacy=True)))
                    return False

                self.logger.debug(
                    'Posting Slack attachment {}'.format(
                        attachment.url(privacy=True)))

                # Prepare API Upload Payload
                _payload = {
                    'filename': attachment.name,
                    'channels': ','.join(attach_channel_list)
                }

                # Our URL
                _url = self.api_url.format('files.upload')

                response = self._send(_url, _payload, attach=attachment)
                if not (response and response.get('file') and
                        response['file'].get('url_private')):
                    # We failed to post our attachments, take an early exit
                    return False

        return not has_error

    def _send(self, url, payload, attach=None, **kwargs):
        """
        Wrapper to the requests (post) object
        """

        self.logger.debug('Slack POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Slack Payload: %s' % str(payload))

        headers = {
            'User-Agent': self.app_id,
        }

        if not attach:
            headers['Content-Type'] = 'application/json; charset=utf-8'

        if self.mode is SlackMode.BOT:
            headers['Authorization'] = 'Bearer {}'.format(self.access_token)

        # Our response object
        response = None

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Our attachment path (if specified)
        files = None

        try:
            # Open our attachment path if required:
            if attach:
                files = {'file': (attach.name, open(attach.path, 'rb'))}

            r = requests.post(
                url,
                data=payload if attach else dumps(payload),
                headers=headers,
                files=files,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = \
                    NotifySlack.http_response_code_lookup(
                        r.status_code, SLACK_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send {}to Slack: '
                    '{}{}error={}.'.format(
                        attach.name if attach else '',
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return False

            elif attach:
                # Attachment posts return a JSON string
                try:
                    response = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # ValueError = r.content is Unparsable
                    # TypeError = r.content is None
                    # AttributeError = r is None
                    pass

                if not (response and response.get('ok', True)):
                    # Bare minimum requirements not met
                    self.logger.warning(
                        'Failed to send {}to Slack: error={}.'.format(
                            attach.name if attach else '',
                            r.status_code))

                    self.logger.debug(
                        'Response Details:\r\n{}'.format(r.content))
                    return False
            else:
                response = r.content

            # Message Post Response looks like this:
            # {
            #   "attachments": [
            #     {
            #       "color": "3AA3E3",
            #       "fallback": "test",
            #       "id": 1,
            #       "text": "my body",
            #       "title": "my title",
            #       "ts": 1573694687
            #     }
            #   ],
            #   "bot_id": "BAK4K23G5",
            #   "icons": {
            #     "image_48": "https://s3-us-west-2.amazonaws.com/...
            #   },
            #   "subtype": "bot_message",
            #   "text": "",
            #   "ts": "1573694689.003700",
            #   "type": "message",
            #   "username": "Apprise"
            # }

            # File Attachment Responses look like this
            # {
            #   "file": {
            #     "channels": [],
            #     "comments_count": 0,
            #     "created": 1573617523,
            #     "display_as_bot": false,
            #     "editable": false,
            #     "external_type": "",
            #     "filetype": "png",
            #     "groups": [],
            #     "has_rich_preview": false,
            #     "id": "FQJJLDAHM",
            #     "image_exif_rotation": 1,
            #     "ims": [],
            #     "is_external": false,
            #     "is_public": false,
            #     "is_starred": false,
            #     "mimetype": "image/png",
            #     "mode": "hosted",
            #     "name": "apprise-test.png",
            #     "original_h": 640,
            #     "original_w": 640,
            #     "permalink": "https://{name}.slack.com/files/...
            #     "permalink_public": "https://slack-files.com/...
            #     "pretty_type": "PNG",
            #     "public_url_shared": false,
            #     "shares": {},
            #     "size": 238810,
            #     "thumb_160": "https://files.slack.com/files-tmb/...
            #     "thumb_360": "https://files.slack.com/files-tmb/...
            #     "thumb_360_h": 360,
            #     "thumb_360_w": 360,
            #     "thumb_480": "https://files.slack.com/files-tmb/...
            #     "thumb_480_h": 480,
            #     "thumb_480_w": 480,
            #     "thumb_64": "https://files.slack.com/files-tmb/...
            #     "thumb_80": "https://files.slack.com/files-tmb/...
            #     "thumb_tiny": abcd...
            #     "timestamp": 1573617523,
            #     "title": "apprise-test",
            #     "url_private": "https://files.slack.com/files-pri/...
            #     "url_private_download": "https://files.slack.com/files-...
            #     "user": "UADKLLMJT",
            #     "username": ""
            #   },
            #   "ok": true
            # }
        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred posting {}to Slack.'.format(
                    attach.name if attach else ''))
            self.logger.debug('Socket Exception: %s' % str(e))
            return False

        except (OSError, IOError) as e:
            self.logger.warning(
                'An I/O error occurred while reading {}.'.format(
                    attach.name if attach else 'attachment'))
            self.logger.debug('I/O Exception: %s' % str(e))
            return False

        finally:
            # Close our file (if it's open) stored in the second element
            # of our files tuple (index 1)
            if files:
                files['file'][1].close()

        # Return the response for processing
        return response

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
            'footer': 'yes' if self.include_footer else 'no',
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.mode == SlackMode.WEBHOOK:
            # Determine if there is a botname present
            botname = ''
            if self.user:
                botname = '{botname}@'.format(
                    botname=NotifySlack.quote(self.user, safe=''),
                )

            return '{schema}://{botname}{token_a}/{token_b}/{token_c}/'\
                '{targets}/?{params}'.format(
                    schema=self.secure_protocol,
                    botname=botname,
                    token_a=self.pprint(self.token_a, privacy, safe=''),
                    token_b=self.pprint(self.token_b, privacy, safe=''),
                    token_c=self.pprint(self.token_c, privacy, safe=''),
                    targets='/'.join(
                        [NotifySlack.quote(x, safe='')
                            for x in self.channels]),
                    params=NotifySlack.urlencode(params),
                )
        # else -> self.mode == SlackMode.BOT:
        return '{schema}://{access_token}/{targets}/'\
            '?{params}'.format(
                schema=self.secure_protocol,
                access_token=self.pprint(self.access_token, privacy, safe=''),
                targets='/'.join(
                    [NotifySlack.quote(x, safe='') for x in self.channels]),
                params=NotifySlack.urlencode(params),
            )

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The first token is stored in the hostname
        token = NotifySlack.unquote(results['host'])

        # Get unquoted entries
        entries = NotifySlack.split_path(results['fullpath'])

        # Verify if our token_a us a bot token or part of a webhook:
        if token.startswith('xo'):
            # We're dealing with a bot
            results['access_token'] = token

        else:
            # We're dealing with a webhook
            results['token_a'] = token

            # Now fetch the remaining tokens
            try:
                results['token_b'] = entries.pop(0)

            except IndexError:
                # We're done
                results['token_b'] = None

            try:
                results['token_c'] = entries.pop(0)

            except IndexError:
                # We're done
                results['token_c'] = None

        # assign remaining entries to the channels we wish to notify
        results['targets'] = entries

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += [x for x in filter(
                bool, CHANNEL_LIST_DELIM.split(
                    NotifySlack.unquote(results['qsd']['to'])))]

        # Get Image Flag
        results['include_image'] = \
            parse_bool(results['qsd'].get('image', True))

        # Get Footer Flag
        results['include_footer'] = \
            parse_bool(results['qsd'].get('footer', True))

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://hooks.slack.com/services/TOKEN_A/TOKEN_B/TOKEN_C
        """

        result = re.match(
            r'^https?://hooks\.slack\.com/services/'
            r'(?P<token_a>[A-Z0-9]+)/'
            r'(?P<token_b>[A-Z0-9]+)/'
            r'(?P<token_c>[A-Z0-9]+)/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            return NotifySlack.parse_url(
                '{schema}://{token_a}/{token_b}/{token_c}/{params}'.format(
                    schema=NotifySlack.secure_protocol,
                    token_a=result.group('token_a'),
                    token_b=result.group('token_b'),
                    token_c=result.group('token_c'),
                    params='' if not result.group('params')
                    else result.group('params')))

        return None
