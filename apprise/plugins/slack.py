# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# There are 2 ways to use this plugin...
# Method 1 : Via Webhook:
#   Visit https://api.slack.com/apps
#    - Click on 'Create new App'
#    - Create one from Scratch
#    - Provide it an 'App Name' and 'Workspace'

# Method 1 (legacy) : Via Webhook:
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
# Method 2 (legacy) : Via a Bot:
#   1. visit: https://api.slack.com/apps?new_app=1
#   2. Pick an App Name (such as Apprise) and select your workspace.  Then
#       press 'Create App'
#   3. You'll be able to click on 'Bots' from here where you can then choose
#       to add a 'Bot User'.  Give it a name and choose 'Add Bot User'.
#   4. Now you can choose 'Install App' to which you can choose 'Install App
#       to Workspace'.
#   5. You will need to authorize the app which you get prompted to do.
#   6. Finally you'll get some important information providing you your
#      'OAuth Access Token' and 'Bot User OAuth Access Token' such as:
#        slack://{Oauth Access Token}
#
#        ... which might look something like:
#        slack://xoxp-1234-1234-1234-4ddbc191d40ee098cbaae6f3523ada2d
#        ... or:
#        slack://xoxb-1234-1234-4ddbc191d40ee098cbaae6f3523ada2d
#
#       You must at least give your bot the following access for it to
#       be useful:
#         - chat:write       - MUST be set otherwise you can not post into
#                              a channel
#         - users:read.email - Required if you want to be able to lookup
#                              users by their email address.
#
#      The easiest way to bring a bot into a channel (so that it can send
#      a message to it is to invite it. At this time Apprise does not support
#      an auto-join functionality. To do this:
#        - In the 'Details' section of your channel
#        - Click on the 'More' [...] (elipse icon)
#        - Click 'Add apps'
#        - You will be able to select the Bot App you previously created
#        - Your bot will join your channel.

import re
import requests
from json import dumps
from json import loads
from time import time
from datetime import (datetime, timezone)
from .base import NotifyBase
from ..common import NotifyImageSize
from ..common import NotifyType
from ..common import NotifyFormat
from ..utils.parse import (
    is_email, parse_bool, parse_list, validate_regex, urlencode)
from ..locale import gettext_lazy as _

# Extend HTTP Error Messages
SLACK_HTTP_ERROR_MAP = {
    401: 'Unauthorized - Invalid Token.',
}

# Used to break path apart into list of channels
CHANNEL_LIST_DELIM = re.compile(r'[ \t\r\n,#\\/]+')

# Channel Regular Expression Parsing
CHANNEL_RE = re.compile(
    r'^(?P<channel>[+#@]?[a-z0-9_-]{1,32})(:(?P<thread_ts>[0-9.]+))?$', re.I)

# Webhook
WEBHOOK_RE = re.compile(
    r'^([a-z]{4,5}://([^/:]+:)?([^/@]+@)?)?'
    r'(?P<webhook>[a-z0-9]{9,12}/+[a-z0-9]{9,12}/+'
    r'[a-z0-9]{20,24})([/?].*|\s*$)', re.I)

# For detecting Slack API v2 Client IDs
CLIENT_ID_RE = re.compile(r'^\d{8,}\.\d{8,}$', re.I)

# For detecting Slack API v2 Codes
CODE_RE = re.compile(r'^[a-z0-9_-]{10,}$', re.I)


class SlackMode:
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


class SlackAPIVersion:
    """
    Slack API Version
    """
    # Original - Said to be depricated on March 31st, 2025
    ONE = '1'

    # New 2024 API Format
    TWO = '2'


SLACK_API_VERSION_MAP = {
    # v1
    "v1": SlackAPIVersion.ONE,
    "1": SlackAPIVersion.ONE,
    # v2
    "v2": SlackAPIVersion.TWO,
    "2": SlackAPIVersion.TWO,
    "2024": SlackAPIVersion.TWO,
    "2025": SlackAPIVersion.TWO,
    "default": SlackAPIVersion.ONE,
}


SLACK_API_VERSIONS = {
    # Note: This also acts as a reverse lookup mapping
    SlackAPIVersion.ONE: 'v1',
    SlackAPIVersion.TWO: 'v2',
}


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

    # Support attachments
    attachment_support = True

    # The maximum targets to include when doing batch transfers
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

    # The scopes required to work with Slack
    slack_v2_oauth_scopes = (
        # Required for creating a message
        'chat:write',
        # Required for attachments
        'files:write',
        # Required for looking up a user id when provided ones email
        'users:read.email'
    )

    # Define object templates
    templates = (
        # Webhook (2024+)
        '{schema}://{client_id}/{secret}/',  # code-aquisition URL
        '{schema}://{client_id}/{secret}/{code}',
        '{schema}://{client_id}/{secret}/{code}/{targets}',

        # Webhook (legacy)
        '{schema}://{token}',
        '{schema}://{botname}@{token}',
        '{schema}://{token}/{targets}',
        '{schema}://{botname}@{token}/{targets}',

        # Bot
        '{schema}://{access_token}/',
        '{schema}://{access_token}/{targets}',
    )

    # Define our template tokens
    template_tokens = dict(NotifyBase.template_tokens, **{
        # Slack API v2 (2024+)
        'client_id': {
            'name': _('Client ID'),
            'type': 'string',
            'private': True,
        },
        'secret': {
            'name': _('Client Secret'),
            'type': 'string',
            'private': True,
        },
        'code': {
            'name': _('Access Code'),
            'type': 'string',
            'private': True,
        },

        # Legacy Slack API v1
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
            'regex': (r'^xox[abp]-[a-z0-9-]+$', 'i'),
        },
        # Token required as part of the Webhook request
        #  AAAAAAAAA/BBBBBBBBB/CCCCCCCCCCCCCCCCCCCCCCCC
        'token': {
            'name': _('Legacy Webhook Token'),
            'type': 'string',
            'private': True,
            'regex': (r'^[a-z0-9]+/[a-z0-9]+/[a-z0-9]+$', 'i'),
        },
        'target_encoded_id': {
            'name': _('Target Encoded ID'),
            'type': 'string',
            'prefix': '+',
            'map_to': 'targets',
        },
        'target_email': {
            'name': _('Target Email'),
            'type': 'string',
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
        # Use Payload in Blocks (vs legacy way):
        #  See: https://api.slack.com/reference/messaging/payload
        'blocks': {
            'name': _('Use Blocks'),
            'type': 'bool',
            'default': False,
            'map_to': 'use_blocks',
        },
        'to': {
            'alias_of': 'targets',
        },
        'client_id': {
            'alias_of': 'client_id',
        },
        'secret': {
            'alias_of': 'secret',
        },
        'code': {
            'alias_of': 'code',
        },
        'token': {
            'name': _('Token'),
            'alias_of': ('access_token', 'token'),
        },
        'ver': {
            'name': _('Slack API Version'),
            'type': 'choice:string',
            'values': ('v1', 'v2'),
            'default': 'v1',
        },
    })

    # Formatting requirements are defined here:
    # https://api.slack.com/docs/message-formatting
    _re_formatting_map = {
        # New lines must become the string version
        r'\r\*\n': '\\n',
        # Escape other special characters
        r'&': '&amp;',
        r'<': '&lt;',
        r'>': '&gt;',
    }

    # To notify a channel, one uses <!channel|channel>
    _re_channel_support = re.compile(
        r'(?P<match>(?:<|\&lt;)?[ \t]*'
        r'!(?P<channel>[^| \n]+)'
        r'(?:[ \t]*\|[ \t]*(?:(?P<val>[^\n]+?)[ \t]*)?(?:>|\&gt;)'
        r'|(?:>|\&gt;)))', re.IGNORECASE)

    # To notify a user by their ID, one uses <@U6TTX1F9R>
    _re_user_id_support = re.compile(
        r'(?P<match>(?:<|\&lt;)?[ \t]*'
        r'@(?P<userid>[^| \n]+)'
        r'(?:[ \t]*\|[ \t]*(?:(?P<val>[^\n]+?)[ \t]*)?(?:>|\&gt;)'
        r'|(?:>|\&gt;)))', re.IGNORECASE)

    # The markdown in slack isn't [desc](url), it's <url|desc>
    #
    # To accomodate this, we need to ensure we don't escape URLs that match
    _re_url_support = re.compile(
        r'(?P<match>(?:<|\&lt;)?[ \t]*'
        r'(?P<url>(?:https?|mailto)://[^| \n]+)'
        r'(?:[ \t]*\|[ \t]*(?:(?P<val>[^\n]+?)[ \t]*)?(?:>|\&gt;)'
        r'|(?:>|\&gt;)))', re.IGNORECASE)

    def __init__(self, access_token=None, token=None, targets=None,
                 include_image=None, include_footer=None, use_blocks=None,
                 ver=None,

                 # Entries needed for Webhook - Slack API v2 (2024+)
                 client_id=None, secret=None, code=None,

                 # Catch-all
                 **kwargs):
        """
        Initialize Slack Object
        """
        super().__init__(**kwargs)

        # Setup our mode
        self.mode = SlackMode.BOT if access_token else SlackMode.WEBHOOK

        # v1 Defaults
        self.access_token = None
        self.token = None

        # v2 Defaults
        self.code = None
        self.client_id = None
        self.secret = None

        # Get our Slack API Version
        self.api_ver = SlackAPIVersion.TWO if client_id \
            and secret and not (token or access_token) and ver is None \
            else (
                SLACK_API_VERSION_MAP[NotifySlack.
                                      template_args['ver']['default']]
                if ver is None else next((
                    v for k, v in SLACK_API_VERSION_MAP.items()
                    if str(ver).lower().startswith(k)),
                    SLACK_API_VERSION_MAP[NotifySlack.
                                          template_args['ver']['default']]))

        # Depricated Notification
        if self.api_ver == SlackAPIVersion.ONE:
            self.logger.deprecate(
                'Slack Legacy API is set to be deprecated on Mar 31st, 2025. '
                'You must update your App and/or Bot')

        if self.mode is SlackMode.WEBHOOK:
            if self.api_ver == SlackAPIVersion.ONE:
                self.token = validate_regex(
                    token, *self.template_tokens['token']['regex'])
                if not self.token:
                    msg = 'An invalid Slack Token ' \
                          '({}) was specified.'.format(token)
                    self.logger.warning(msg)
                    raise TypeError(msg)

            else:  # version 2
                self.code = code
                self.client_id = client_id
                self.secret = secret

        else:  # Bot
            self.access_token = validate_regex(
                access_token, *self.template_tokens['access_token']['regex'])
            if not self.access_token:
                msg = 'An invalid Slack (Bot) OAuth Access Token ' \
                      '({}) was specified.'.format(access_token)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Look the users up by their email address and map them back to their
        # id here for future queries (if needed). This allows people to
        # specify a full email as a recipient via slack
        self._lookup_users = {}

        self.use_blocks = parse_bool(
            use_blocks, self.template_args['blocks']['default']) \
            if use_blocks is not None \
            else self.template_args['blocks']['default']

        # Build list of channels
        self.channels = parse_list(targets)
        if len(self.channels) == 0:
            # No problem; the webhook is smart enough to just notify the
            # channel it was created for; adding 'None' is just used as
            # a flag lower to not set the channels
            self.channels.append(
                None if self.mode is SlackMode.WEBHOOK
                else self.default_notification_channel)

        # Iterate over above list and store content accordingly
        self._re_formatting_rules = re.compile(
            r'(' + '|'.join(self._re_formatting_map.keys()) + r')',
            re.IGNORECASE,
        )
        # Place a thumbnail image inline with the message body
        self.include_image = include_image if include_image is not None \
            else self.template_args['image']['default']

        # Place a footer with each post
        self.include_footer = include_footer if include_footer is not None \
            else self.template_args['footer']['default']

        # Access token is required with the new 2024 Slack API and
        # is acquired after authenticating
        self.__refresh_token = None
        self.__access_token = None
        self.__access_token_expiry = datetime.now(timezone.utc)
        return

    def authenticate(self, **kwargs):
        """
        Authenticates with Slack API Servers
        """

        # First we need to acquire a code
        params = {
            'client_id': self.client_id,
            'scope': ','.join(self.slack_v2_oauth_scopes),
            # Out of Band
            'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
        }

        # Sharing this code with the user to click on and have a code generated
        # does not work if there is no valid redirect_uri provided; the
        # 'out-of-band' on defined above does not work.
        get_code_url = \
            f'https://slack.com/oauth/v2/authorize?{urlencode(params)}'

        # The following code does not work (below).
        # try:
        #     r = requests.get(
        #         get_code_url,
        #         verify=self.verify_certificate,
        #         timeout=self.request_timeout,
        #     )

        # except requests.RequestException as e:
        #     self.logger.warning(
        #         'A Connection error occurred acquiring Slack access code.',
        #     )
        #     self.logger.debug('Socket Exception: %s' % str(e))
        #     # Return; we're done
        return None

    def send(self, body, title='', notify_type=NotifyType.INFO, attach=None,
             **kwargs):
        """
        Perform Slack Notification
        """

        # error tracking (used for function return)
        has_error = False

        if self.api_ver == SlackAPIVersion.TWO:
            if not self.authenticate():
                return False
        #
        # Prepare JSON Object (applicable to both WEBHOOK and BOT mode)
        #
        if self.use_blocks:
            # Our slack format
            _slack_format = 'mrkdwn' \
                if self.notify_format == NotifyFormat.MARKDOWN \
                else 'plain_text'

            payload = {
                'username': self.user if self.user else self.app_id,
                'attachments': [{
                    'blocks': [{
                        'type': 'section',
                        'text': {
                            'type': _slack_format,
                            'text': body
                        }
                    }],
                    'color': self.color(notify_type),
                }]
            }

            # Slack only accepts non-empty header sections
            if title:
                payload['attachments'][0]['blocks'].insert(0, {
                    'type': 'header',
                    'text': {
                        'type': 'plain_text',
                        'text': title,
                        'emoji': True
                    }
                })

            # Include the footer only if specified to do so
            if self.include_footer:

                # Acquire our to-be footer icon if configured to do so
                image_url = None if not self.include_image \
                    else self.image_url(notify_type)

                # Prepare our footer based on the block structure
                _footer = {
                    'type': 'context',
                    'elements': [{
                        'type': _slack_format,
                        'text': self.app_id
                    }]
                }

                if image_url:
                    payload['icon_url'] = image_url

                    _footer['elements'].insert(0, {
                        'type': 'image',
                        'image_url': image_url,
                        'alt_text': notify_type
                    })

                payload['attachments'][0]['blocks'].append(_footer)

        else:
            #
            # Legacy API Formatting
            #
            if self.notify_format == NotifyFormat.MARKDOWN:
                body = self._re_formatting_rules.sub(  # pragma: no branch
                    lambda x: self._re_formatting_map[x.group()], body,
                )

                # Support <!channel|desc>, <!channel> entries
                for match in self._re_channel_support.findall(body):
                    # Swap back any ampersands previously updaated
                    channel = match[1].strip()
                    desc = match[2].strip()

                    # Update our string
                    body = re.sub(
                        re.escape(match[0]),
                        '<!{channel}|{desc}>'.format(
                            channel=channel, desc=desc)
                        if desc else '<!{channel}>'.format(channel=channel),
                        body,
                        re.IGNORECASE)

                # Support <@userid|desc>, <@channel> entries
                for match in self._re_user_id_support.findall(body):
                    # Swap back any ampersands previously updaated
                    user = match[1].strip()
                    desc = match[2].strip()

                    # Update our string
                    body = re.sub(
                        re.escape(match[0]),
                        '<@{user}|{desc}>'.format(user=user, desc=desc)
                        if desc else '<@{user}>'.format(user=user),
                        body,
                        re.IGNORECASE)

                # Support <url|desc>, <url> entries
                for match in self._re_url_support.findall(body):
                    # Swap back any ampersands previously updaated
                    url = match[1].replace('&amp;', '&')
                    desc = match[2].strip()

                    # Update our string
                    body = re.sub(
                        re.escape(match[0]),
                        '<{url}|{desc}>'.format(url=url, desc=desc)
                        if desc else '<{url}>'.format(url=url),
                        body,
                        re.IGNORECASE)

            # Perform Formatting on title here; this is not needed for block
            # mode above
            title = self._re_formatting_rules.sub(  # pragma: no branch
                lambda x: self._re_formatting_map[x.group()], title,
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
            # Acquire our to-be footer icon if configured to do so
            image_url = None if not self.include_image \
                else self.image_url(notify_type)

            if image_url:
                payload['icon_url'] = image_url

            # Include the footer only if specified to do so
            if self.include_footer:
                if image_url:
                    payload['attachments'][0]['footer_icon'] = image_url

                # Include the footer only if specified to do so
                payload['attachments'][0]['footer'] = self.app_id

        if attach and self.attachment_support \
                and self.mode is SlackMode.WEBHOOK:
            # Be friendly; let the user know why they can't send their
            # attachments if using the Webhook mode
            self.logger.warning(
                'Slack Webhooks do not support attachments.')

        # Prepare our Slack URL (depends on mode)
        if self.mode is SlackMode.WEBHOOK:
            url = '{}/{}'.format(self.webhook_url, self.token)

        else:  # SlackMode.BOT
            url = self.api_url.format('chat.postMessage')

        # Create a copy of the channel list
        channels = list(self.channels)

        attach_channel_list = []
        while len(channels):
            channel = channels.pop(0)
            if channel is not None:
                # We'll perform a user lookup if we detect an email
                email = is_email(channel)
                if email:
                    payload['channel'] = \
                        self.lookup_userid(email['full_email'])

                    if not payload['channel']:
                        # Move along; any notifications/logging would have
                        # come from lookup_userid()
                        has_error = True
                        continue

                else:  # Channel
                    result = CHANNEL_RE.match(channel)

                    if not result:
                        # Channel over-ride was specified
                        self.logger.warning(
                            "The specified Slack target {} is invalid;"
                            "skipping.".format(channel))

                        # Mark our failure
                        has_error = True
                        continue

                    # Store oure content
                    channel, thread_ts = \
                        result.group('channel'), result.group('thread_ts')
                    if thread_ts:
                        payload['thread_ts'] = thread_ts

                    elif 'thread_ts' in payload:
                        # Handle situations where one channel has a thread_id
                        # specified, and the next does not.  We do not want to
                        # cary forward the last value specified
                        del payload['thread_ts']

                    if channel[0] == '+':
                        # Treat as encoded id if prefixed with a +
                        payload['channel'] = channel[1:]

                    elif channel[0] == '@':
                        # Treat @ value 'as is'
                        payload['channel'] = channel

                    else:
                        # Prefix with channel hash tag (if not already)
                        payload['channel'] = \
                            channel if channel[0] == '#' \
                            else '#{}'.format(channel)

            response = self._send(url, payload)
            if not response:
                # Handle any error
                has_error = True
                continue

            # Store the valid channel or chat ID (for DMs) that will
            # be accepted by Slack's attachment method later.
            if response.get('channel'):
                attach_channel_list.append(response.get('channel'))

            self.logger.info(
                'Sent Slack notification{}.'.format(
                    ' to {}'.format(channel)
                    if channel is not None else ''))

        if attach and self.attachment_support and \
                self.mode is SlackMode.BOT and attach_channel_list:
            # Send our attachments (can only be done in bot mode)
            for no, attachment in enumerate(attach, start=1):

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

                # Get the URL to which to upload the file.
                # https://api.slack.com/methods/files.getUploadURLExternal
                _params = {
                    'filename': attachment.name
                    if attachment.name else f'file{no:03}.dat',
                    'length': len(attachment),
                }
                _url = self.api_url.format('files.getUploadURLExternal')
                response = self._send(
                    _url, {}, http_method='get', params=_params
                )
                if not (
                    response and response.get('file_id')
                    and response.get('upload_url')
                ):
                    self.logger.error('Could retrieve file upload URL.')
                    # We failed to get an upload URL, take an early exit
                    return False

                file_id = response.get('file_id')
                upload_url = response.get('upload_url')

                # Upload file
                response = self._send(upload_url, {}, attach=attachment)

                # Send file to channels
                # https://api.slack.com/methods/files.completeUploadExternal
                for channel_id in attach_channel_list:
                    _payload = {
                        'files': [{
                            "id": file_id,
                            "title": attachment.name,
                        }],
                        'channel_id': channel_id
                    }
                    _url = self.api_url.format('files.completeUploadExternal')
                    response = self._send(_url, _payload)
                    # Expected response
                    # {
                    #     "ok": true,
                    #     "files": [
                    #         {
                    #             "id": "F123ABC456",
                    #             "title": "slack-test"
                    #         }
                    #     ]
                    # }
                    if not (response and response.get('files')):
                        self.logger.error('Failed to send file to channel.')
                        # We failed to send the file to the channel,
                        # take an early exit
                        return False

        return not has_error

    def lookup_userid(self, email):
        """
        Takes an email address and attempts to resolve/acquire it's user
        id for notification purposes.
        """
        if email in self._lookup_users:
            # We're done as entry has already been retrieved
            return self._lookup_users[email]

        if self.mode is not SlackMode.BOT:
            # You can not look up
            self.logger.warning(
                'Emails can not be resolved to Slack User IDs unless you '
                'have a bot configured.')
            return None

        lookup_url = self.api_url.format('users.lookupByEmail')
        headers = {
            'User-Agent': self.app_id,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': 'Bearer {}'.format(self.access_token),
        }

        # we pass in our email address as the argument
        params = {
            'email': email,
        }

        self.logger.debug('Slack User Lookup POST URL: %s (cert_verify=%r)' % (
            lookup_url, self.verify_certificate,
        ))
        self.logger.debug('Slack User Lookup Parameters: %s' % str(params))

        # Initialize our HTTP JSON response
        response = {'ok': False}

        # Initialize our detected user id (also the response to this function)
        user_id = None

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.get(
                lookup_url,
                headers=headers,
                params=params,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            # Attachment posts return a JSON string
            try:
                response = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                pass

            # We can get a 200 response, but still fail.  A failure message
            # might look like this (missing bot permissions):
            #    {
            #      'ok': False,
            #      'error': 'missing_scope',
            #      'needed': 'users:read.email',
            #      'provided': 'calls:write,chat:write'
            #    }

            if r.status_code != requests.codes.ok \
                    or not (response and response.get('ok', False)):

                # We had a problem
                status_str = \
                    NotifySlack.http_response_code_lookup(
                        r.status_code, SLACK_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send Slack User Lookup:'
                    '{}{}error={}.'.format(
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug('Response Details:\r\n{}'.format(r.content))
                # Return; we're done
                return False

            # If we reach here, then we were successful in looking up
            # the user. A response generally looks like this:
            # {
            #   'ok': True,
            #   'user': {
            #     'id': 'J1ZQB9T9Y',
            #     'team_id': 'K1WR6TML2',
            #     'name': 'l2g',
            #     'deleted': False,
            #     'color': '9f69e7',
            #     'real_name': 'Chris C',
            #     'tz': 'America/New_York',
            #     'tz_label': 'Eastern Standard Time',
            #     'tz_offset': -18000,
            #     'profile': {
            #       'title': '',
            #       'phone': '',
            #       'skype': '',
            #       'real_name': 'Chris C',
            #       'real_name_normalized':
            #       'Chris C',
            #       'display_name': 'l2g',
            #       'display_name_normalized': 'l2g',
            #       'fields': None,
            #       'status_text': '',
            #       'status_emoji': '',
            #       'status_expiration': 0,
            #       'avatar_hash': 'g785e9c0ddf6',
            #       'email': 'lead2gold@gmail.com',
            #       'first_name': 'Chris',
            #       'last_name': 'C',
            #       'image_24': 'https://secure.gravatar.com/...',
            #       'image_32': 'https://secure.gravatar.com/...',
            #       'image_48': 'https://secure.gravatar.com/...',
            #       'image_72': 'https://secure.gravatar.com/...',
            #       'image_192': 'https://secure.gravatar.com/...',
            #       'image_512': 'https://secure.gravatar.com/...',
            #       'status_text_canonical': '',
            #       'team': 'K1WR6TML2'
            #     },
            #     'is_admin': True,
            #     'is_owner': True,
            #     'is_primary_owner': True,
            #     'is_restricted': False,
            #     'is_ultra_restricted': False,
            #     'is_bot': False,
            #     'is_app_user': False,
            #     'updated': 1603904274
            #   }
            # }
            # We're only interested in the id
            user_id = response['user']['id']

            # Cache it for future
            self._lookup_users[email] = user_id
            self.logger.info(
                'Email %s resolves to the Slack User ID: %s.', email, user_id)

        except requests.RequestException as e:
            self.logger.warning(
                'A Connection error occurred looking up Slack User.',
            )
            self.logger.debug('Socket Exception: %s' % str(e))
            # Return; we're done
            return None

        return user_id

    def _send(self, url, payload, attach=None, http_method='post', params=None,
              **kwargs):
        """
        Wrapper to the requests (post) object
        """
        self.logger.debug('Slack POST URL: %s (cert_verify=%r)' % (
            url, self.verify_certificate,
        ))
        self.logger.debug('Slack Payload: %s' % str(payload))

        headers = {
            'User-Agent': self.app_id,
            'Accept': 'application/json',
        }

        if not attach:
            headers['Content-Type'] = 'application/json; charset=utf-8'

        if self.mode is SlackMode.BOT:
            headers['Authorization'] = 'Bearer {}'.format(self.access_token)

        # Our response object
        response = {'ok': False}

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Our attachment path (if specified)
        files = None

        try:
            # Open our attachment path if required:
            if attach:
                files = {'file': (attach.name, open(attach.path, 'rb'))}

            r = requests.request(
                http_method,
                url,
                data=payload if attach else dumps(payload),
                headers=headers,
                files=files,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                params=params if params else None,
            )

            # Posts return a JSON string
            try:
                response = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                pass

            # Another response type is:
            # {
            #   'ok': False,
            #   'error': 'not_in_channel',
            # }
            status_okay = False
            if self.mode is SlackMode.BOT:
                status_okay = (
                    (response and response.get('ok', False)) or
                    # Responses for file uploads look like this
                    # 'OK - <file length>'
                    (
                        r.content and
                        isinstance(r.content, bytes) and
                        b'OK' in r.content
                    )
                )
            elif r.content == b'ok':
                # The text 'ok' is returned if this is a Webhook request
                # So the below captures that as well.
                status_okay = True

            if r.status_code != requests.codes.ok or not status_okay:
                # We had a problem
                status_str = \
                    NotifySlack.http_response_code_lookup(
                        r.status_code, SLACK_HTTP_ERROR_MAP)

                self.logger.warning(
                    'Failed to send{} to Slack: '
                    '{}{}error={}.'.format(
                        (' ' + attach.name) if attach else '',
                        status_str,
                        ', ' if status_str else '',
                        r.status_code))

                self.logger.debug(
                    'Response Details:\r\n{}'.format(r.content))
                return False

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

            # files.completeUploadExternal responses look like this:
            # {
            #     "ok": true,
            #     "files": [
            #         {
            #             "id": "F123ABC456",
            #             "title": "slack-test"
            #         }
            #     ]
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

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (
            self.secure_protocol, self.token, self.access_token,
            self.client_id, self.secret,
            # self.code is intentionally left out
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            'image': 'yes' if self.include_image else 'no',
            'footer': 'yes' if self.include_footer else 'no',
            'blocks': 'yes' if self.use_blocks else 'no',
            'ver': SLACK_API_VERSIONS[self.api_ver],
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine if there is a botname present
        botname = ''
        if self.user:
            botname = '{botname}@'.format(
                botname=NotifySlack.quote(self.user, safe=''),
            )

        if self.mode == SlackMode.WEBHOOK:

            if self.api_ver == SlackAPIVersion.ONE:
                return '{schema}://{botname}{token}/'\
                    '{targets}/?{params}'.format(
                        schema=self.secure_protocol,
                        botname=botname,
                        token='/'.join(
                            [self.pprint(token, privacy, safe='/')
                             for token in self.token.split('/')]),
                        targets='/'.join(
                            [NotifySlack.quote(x, safe='')
                                for x in self.channels]),
                        params=NotifySlack.urlencode(params),
                    )

            return '{schema}://{botname}{client_id}/{secret}{code}'\
                '{targets}?{params}'.format(
                    schema=self.secure_protocol,
                    botname=botname,
                    client_id=self.pprint(self.client_id, privacy, safe='/'),
                    secret=self.pprint(self.secret, privacy, safe=''),
                    code='' if not self.code else '/' + self.pprint(
                        self.code, privacy, safe=''),
                    targets=('/' + '/'.join(
                        [NotifySlack.quote(x, safe='')
                            for x in self.channels])) if self.channels else '',
                    params=NotifySlack.urlencode(params),
                )

        # else -> self.mode == SlackMode.BOT:
        return '{schema}://{botname}{access_token}/{targets}/'\
            '?{params}'.format(
                schema=self.secure_protocol,
                botname=botname,
                access_token=self.pprint(self.access_token, privacy, safe='/'),
                targets='/'.join(
                    [NotifySlack.quote(x, safe='') for x in self.channels]),
                params=NotifySlack.urlencode(params),
            )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """
        return len(self.channels)

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
        results['targets'] = re.split(
            r'[\s/]+', NotifySlack.unquote(results['host'])) \
            if results['host'] else []

        # Get unquoted entries
        results['targets'] += NotifySlack.split_path(results['fullpath'])

        # Support Slack API Version
        if 'ver' in results['qsd'] and len(results['qsd']['ver']):
            results['ver'] = results['qsd']['ver']

        # Get our values if defined
        if 'client_id' in results['qsd'] and len(results['qsd']['client_id']):
            # We're dealing with a Slack v2 API
            results['client_id'] = results['qsd']['client_id']

        if 'secret' in results['qsd'] and len(results['qsd']['secret']):
            # We're dealing with a Slack v2 API
            results['secret'] = results['qsd']['secret']

        if 'code' in results['qsd'] and len(results['qsd']['code']):
            # We're dealing with a Slack v2 API
            results['code'] = results['qsd']['code']

        if 'token' in results['qsd'] and len(results['qsd']['token']):
            # We're dealing with a Slack v1 API
            token = NotifySlack.unquote(results['qsd']['token']).strip('/')
            # check to see if we're dealing with a bot/user token
            if token.startswith('xo'):
                # We're dealing with a bot
                results['access_token'] = token
                results['token'] = None

            else:  # Webhook
                results['access_token'] = None
                results['token'] = token

        # Verify if our token is a bot token or part of a webhook:
        if not (results.get('token') or results.get('access_token')
                or 'client_id' in results or 'secret' in results
                or 'code' in results) and results['targets'] \
                and results['targets'][0].startswith('xo'):

            # We're dealing with a bot
            results['access_token'] = results['targets'].pop(0)
            results['token'] = None

        elif 'client_id' not in results and results['targets'] \
                and CLIENT_ID_RE.match(results['targets'][0]):
            # Store our Client ID
            results['client_id'] = results['targets'].pop(0)

        else:  # parse token from URL if present
            match = WEBHOOK_RE.match(url)
            if match:
                results['access_token'] = None
                results['token'] = match.group('webhook')
                # Eliminate webhook entries
                results['targets'] = results['targets'][3:]

        # We have several entries on our URL and we don't know where they
        # go. They could also be channels/users/emails
        if 'client_id' in results and 'secret' not in results:
            # Acquire secret
            results['secret'] = \
                results['targets'].pop(0) if results['targets'] else None

        if 'secret' in results and 'code' not in results \
                and results['targets'] and \
                CODE_RE.match(results['targets'][0]):

            # Acquire our code
            results['code'] = results['targets'].pop(0)

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if 'to' in results['qsd'] and len(results['qsd']['to']):
            results['targets'] += [x for x in filter(
                bool, CHANNEL_LIST_DELIM.split(
                    NotifySlack.unquote(results['qsd']['to'])))]

        # Get Image Flag
        results['include_image'] = \
            parse_bool(results['qsd'].get(
                'image', NotifySlack.template_args['image']['default']))

        # Get Payload structure (use blocks?)
        if 'blocks' in results['qsd'] and len(results['qsd']['blocks']):
            results['use_blocks'] = parse_bool(results['qsd']['blocks'])

        # Get Footer Flag
        results['include_footer'] = \
            parse_bool(results['qsd'].get(
                'footer', NotifySlack.template_args['footer']['default']))

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Legacy Support https://hooks.slack.com/services/TOKEN_A/TOKEN_B/TOKEN_C
        """

        result = re.match(
            r'^https?://hooks\.slack\.com/services/'
            r'(?P<token_a>[a-z0-9]+)/'
            r'(?P<token_b>[a-z0-9]+)/'
            r'(?P<token_c>[a-z0-9]+)/?'
            r'(?P<params>\?.+)?$', url, re.I)

        if result:
            return NotifySlack.parse_url(
                '{schema}://{token_a}/{token_b}/{token_c}/{params}'.format(
                    schema=NotifySlack.secure_protocol,
                    token_a=result.group('token_a'),
                    token_b=result.group('token_b'),
                    token_c=result.group('token_c'),
                    params='?ver=1' if not result.group('params')
                    else result.group('params') + '&ver=1'))

        return None
