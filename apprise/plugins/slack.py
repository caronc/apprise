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

import contextlib
from json import dumps, loads
import re
from time import time

import requests

from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_bool, parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
SLACK_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Token.",
}

# Used to break path apart into list of channels
CHANNEL_LIST_DELIM = re.compile(r"[ \t\r\n,#\\/]+")

# Channel Regular Expression Parsing
CHANNEL_RE = re.compile(
    r"^(?P<channel>[+#@]?[A-Z0-9_-]{1,32})(:(?P<thread_ts>[0-9.]+))?$", re.I
)


class SlackMode:
    """Tracks the mode of which we're using Slack."""

    # We're dealing with a webhook
    # Our token looks like: T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7
    WEBHOOK = "webhook"

    # We're dealing with a bot (using the OAuth Access Token)
    # Our token looks like: xoxp-1234-1234-1234-abc124 or
    # Our token looks like: xoxb-1234-1234-abc124 or
    BOT = "bot"


# Define our Slack Modes
SLACK_MODES = (
    SlackMode.WEBHOOK,
    SlackMode.BOT,
)


class NotifySlack(NotifyBase):
    """A wrapper for Slack Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Slack"

    # The services URL
    service_url = "https://slack.com/"

    # The default secure protocol
    secure_protocol = "slack"

    # Allow 50 requests per minute (Tier 2).
    # 60/50 = 0.2
    request_rate_per_sec = 1.2

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_slack"

    # Support attachments
    attachment_support = True

    # The maximum targets to include when doing batch transfers
    # Slack Webhook URL
    webhook_url = "https://hooks.slack.com/services"

    # Slack API URL (used with Bots)
    api_url = "https://slack.com/api/{}"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 35000

    # Default Notification Format
    notify_format = NotifyFormat.MARKDOWN

    # Bot's do not have default channels to notify; so #general
    # becomes the default channel in BOT mode
    default_notification_channel = "#general"

    # Define object templates
    templates = (
        # Webhook
        "{schema}://{token_a}/{token_b}/{token_c}",
        "{schema}://{botname}@{token_a}/{token_b}{token_c}",
        "{schema}://{token_a}/{token_b}/{token_c}/{targets}",
        "{schema}://{botname}@{token_a}/{token_b}/{token_c}/{targets}",
        # Bot
        "{schema}://{access_token}/",
        "{schema}://{access_token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "botname": {
                "name": _("Bot Name"),
                "type": "string",
                "map_to": "user",
            },
            # Bot User OAuth Access Token
            # which always starts with xoxp- e.g.:
            #     xoxb-1234-1234-4ddbc191d40ee098cbaae6f3523ada2d
            "access_token": {
                "name": _("OAuth Access Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^xox[abp]-[A-Z0-9-]+$", "i"),
            },
            # Token required as part of the Webhook request
            #  /AAAAAAAAA/........./........................
            "token_a": {
                "name": _("Token A"),
                "type": "string",
                "private": True,
                "regex": (r"^[A-Z0-9]+$", "i"),
            },
            # Token required as part of the Webhook request
            #  /........./BBBBBBBBB/........................
            "token_b": {
                "name": _("Token B"),
                "type": "string",
                "private": True,
                "regex": (r"^[A-Z0-9]+$", "i"),
            },
            # Token required as part of the Webhook request
            #  /........./........./CCCCCCCCCCCCCCCCCCCCCCCC
            "token_c": {
                "name": _("Token C"),
                "type": "string",
                "private": True,
                "regex": (r"^[A-Za-z0-9]+$", "i"),
            },
            "target_encoded_id": {
                "name": _("Target Encoded ID"),
                "type": "string",
                "prefix": "+",
                "map_to": "targets",
            },
            "target_email": {
                "name": _("Target Email"),
                "type": "string",
                "map_to": "targets",
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "target_channels": {
                "name": _("Target Channel"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
            "footer": {
                "name": _("Include Footer"),
                "type": "bool",
                "default": True,
                "map_to": "include_footer",
            },
            # Use Payload in Blocks (vs legacy way):
            #  See: https://api.slack.com/reference/messaging/payload
            "blocks": {
                "name": _("Use Blocks"),
                "type": "bool",
                "default": False,
                "map_to": "use_blocks",
            },
            "to": {
                "alias_of": "targets",
            },
            "token": {
                "name": _("Token"),
                "alias_of": ("access_token", "token_a", "token_b", "token_c"),
            },
        },
    )

    # Formatting requirements are defined here:
    # https://api.slack.com/docs/message-formatting
    _re_formatting_map = {
        # New lines must become the string version
        r"\r\*\n": "\\n",
        # Escape other special characters
        r"&": "&amp;",
        r"<": "&lt;",
        r">": "&gt;",
    }

    # To notify a channel, one uses <!channel|channel>
    _re_channel_support = re.compile(
        r"(?P<match>(?:<|\&lt;)?[ \t]*"
        r"!(?P<channel>[^| \n]+)"
        r"(?:[ \t]*\|[ \t]*(?:(?P<val>[^\n]+?)[ \t]*)?(?:>|\&gt;)"
        r"|(?:>|\&gt;)))",
        re.IGNORECASE,
    )

    # To notify a user by their ID, one uses <@U6TTX1F9R>
    _re_user_id_support = re.compile(
        r"(?P<match>(?:<|\&lt;)?[ \t]*"
        r"@(?P<userid>[^| \n]+)"
        r"(?:[ \t]*\|[ \t]*(?:(?P<val>[^\n]+?)[ \t]*)?(?:>|\&gt;)"
        r"|(?:>|\&gt;)))",
        re.IGNORECASE,
    )

    # The markdown in slack isn't [desc](url), it's <url|desc>
    #
    # To accomodate this, we need to ensure we don't escape URLs that match
    _re_url_support = re.compile(
        r"(?P<match>(?:<|\&lt;)?[ \t]*"
        r"(?P<url>(?:https?|mailto)://[^| \n]+)"
        r"(?:[ \t]*\|[ \t]*(?:(?P<val>[^\n]+?)[ \t]*)?(?:>|\&gt;)"
        r"|(?:>|\&gt;)))",
        re.IGNORECASE,
    )

    def __init__(
        self,
        access_token=None,
        token_a=None,
        token_b=None,
        token_c=None,
        targets=None,
        include_image=None,
        include_footer=None,
        use_blocks=None,
        **kwargs,
    ):
        """Initialize Slack Object."""
        super().__init__(**kwargs)

        # Setup our mode
        self.mode = SlackMode.BOT if access_token else SlackMode.WEBHOOK

        if self.mode is SlackMode.WEBHOOK:
            self.access_token = None
            self.token_a = validate_regex(
                token_a, *self.template_tokens["token_a"]["regex"]
            )
            if not self.token_a:
                msg = (
                    "An invalid Slack (first) Token "
                    f"({token_a}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            self.token_b = validate_regex(
                token_b, *self.template_tokens["token_b"]["regex"]
            )
            if not self.token_b:
                msg = (
                    "An invalid Slack (second) Token "
                    f"({token_b}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            self.token_c = validate_regex(
                token_c, *self.template_tokens["token_c"]["regex"]
            )
            if not self.token_c:
                msg = (
                    "An invalid Slack (third) Token "
                    f"({token_c}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.token_a = None
            self.token_b = None
            self.token_c = None
            self.access_token = validate_regex(
                access_token, *self.template_tokens["access_token"]["regex"]
            )
            if not self.access_token:
                msg = (
                    "An invalid Slack OAuth Access Token "
                    f"({access_token}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        # Look the users up by their email address and map them back to their
        # id here for future queries (if needed). This allows people to
        # specify a full email as a recipient via slack
        self._lookup_users = {}

        self.use_blocks = (
            parse_bool(use_blocks, self.template_args["blocks"]["default"])
            if use_blocks is not None
            else self.template_args["blocks"]["default"]
        )

        # Build list of channels
        self.channels = parse_list(targets)
        if len(self.channels) == 0:
            # No problem; the webhook is smart enough to just notify the
            # channel it was created for; adding 'None' is just used as
            # a flag lower to not set the channels
            self.channels.append(
                None
                if self.mode is SlackMode.WEBHOOK
                else self.default_notification_channel
            )

        # Iterate over above list and store content accordingly
        self._re_formatting_rules = re.compile(
            r"(" + "|".join(self._re_formatting_map.keys()) + r")",
            re.IGNORECASE,
        )
        # Place a thumbnail image inline with the message body
        self.include_image = \
            self.template_args["image"]["default"] \
            if include_image is None else include_image

        # Place a footer with each post
        self.include_footer = \
            self.template_args["footer"]["default"] \
            if include_footer is None else include_footer

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Slack Notification."""

        # error tracking (used for function return)
        has_error = False

        #
        # Prepare JSON Object (applicable to both WEBHOOK and BOT mode)
        #
        if self.use_blocks:
            # Our slack format
            _slack_format = (
                "mrkdwn"
                if self.notify_format == NotifyFormat.MARKDOWN
                else "plain_text"
            )

            payload = {
                "username": self.user if self.user else self.app_id,
                "attachments": [{
                    "blocks": [{
                        "type": "section",
                        "text": {"type": _slack_format, "text": body},
                    }],
                    "color": self.color(notify_type),
                }],
            }

            # Slack only accepts non-empty header sections
            if title:
                payload["attachments"][0]["blocks"].insert(
                    0,
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": title,
                            "emoji": True,
                        },
                    },
                )

            # Include the footer only if specified to do so
            if self.include_footer:

                # Acquire our to-be footer icon if configured to do so
                image_url = (
                    None
                    if not self.include_image
                    else self.image_url(notify_type)
                )

                # Prepare our footer based on the block structure
                _footer = {
                    "type": "context",
                    "elements": [{"type": _slack_format, "text": self.app_id}],
                }

                if image_url:
                    payload["icon_url"] = image_url

                    _footer["elements"].insert(
                        0,
                        {
                            "type": "image",
                            "image_url": image_url,
                            "alt_text": notify_type,
                        },
                    )

                payload["attachments"][0]["blocks"].append(_footer)

        else:
            #
            # Legacy API Formatting
            #
            if self.notify_format == NotifyFormat.MARKDOWN:
                body = self._re_formatting_rules.sub(  # pragma: no branch
                    lambda x: self._re_formatting_map[x.group()],
                    body,
                )

                # Support <!channel|desc>, <!channel> entries
                for match in self._re_channel_support.findall(body):
                    # Swap back any ampersands previously updaated
                    channel = match[1].strip()
                    desc = match[2].strip()

                    # Update our string
                    body = re.sub(
                        re.escape(match[0]),
                        f"<!{channel}|{desc}>" if desc else f"<!{channel}>",
                        body,
                        flags=re.IGNORECASE,
                    )

                # Support <@userid|desc>, <@channel> entries
                for match in self._re_user_id_support.findall(body):
                    # Swap back any ampersands previously updaated
                    user = match[1].strip()
                    desc = match[2].strip()

                    # Update our string
                    body = re.sub(
                        re.escape(match[0]),
                        f"<@{user}|{desc}>" if desc else f"<@{user}>",
                        body,
                        flags=re.IGNORECASE,
                    )

                # Support <url|desc>, <url> entries
                for match in self._re_url_support.findall(body):
                    # Swap back any ampersands previously updaated
                    url = match[1].replace("&amp;", "&")
                    desc = match[2].strip()

                    # Update our string
                    body = re.sub(
                        re.escape(match[0]),
                        f"<{url}|{desc}>" if desc else f"<{url}>",
                        body,
                        flags=re.IGNORECASE,
                    )

            # Perform Formatting on title here; this is not needed for block
            # mode above
            title = self._re_formatting_rules.sub(  # pragma: no branch
                lambda x: self._re_formatting_map[x.group()],
                title,
            )

            # Prepare JSON Object (applicable to both WEBHOOK and BOT mode)
            payload = {
                "username": self.user if self.user else self.app_id,
                # Use Markdown language
                "mrkdwn": self.notify_format == NotifyFormat.MARKDOWN,
                "attachments": [{
                    "title": title,
                    "text": body,
                    "color": self.color(notify_type),
                    # Time
                    "ts": time(),
                }],
            }
            # Acquire our to-be footer icon if configured to do so
            image_url = (
                None if not self.include_image else self.image_url(notify_type)
            )

            if image_url:
                payload["icon_url"] = image_url

            # Include the footer only if specified to do so
            if self.include_footer:
                if image_url:
                    payload["attachments"][0]["footer_icon"] = image_url

                # Include the footer only if specified to do so
                payload["attachments"][0]["footer"] = self.app_id

        if (
            attach
            and self.attachment_support
            and self.mode is SlackMode.WEBHOOK
        ):
            # Be friendly; let the user know why they can't send their
            # attachments if using the Webhook mode
            self.logger.warning("Slack Webhooks do not support attachments.")

        # Prepare our Slack URL (depends on mode)
        if self.mode is SlackMode.WEBHOOK:
            url = (
                f"{self.webhook_url}/{self.token_a}"
                f"/{self.token_b}/{self.token_c}"
            )

        else:  # SlackMode.BOT
            url = self.api_url.format("chat.postMessage")

        # Create a copy of the channel list
        channels = list(self.channels)

        attach_channel_list = []
        while len(channels):
            channel = channels.pop(0)
            if channel is not None:
                # We'll perform a user lookup if we detect an email
                email = is_email(channel)
                if email:
                    payload["channel"] = self.lookup_userid(
                        email["full_email"]
                    )

                    if not payload["channel"]:
                        # Move along; any notifications/logging would have
                        # come from lookup_userid()
                        has_error = True
                        continue

                else:  # Channel
                    result = CHANNEL_RE.match(channel)

                    if not result:
                        # Channel over-ride was specified
                        self.logger.warning(
                            f"The specified Slack target {channel} is invalid;"
                            "skipping."
                        )

                        # Mark our failure
                        has_error = True
                        continue

                    # Store oure content
                    channel, thread_ts = result.group("channel"), result.group(
                        "thread_ts"
                    )
                    if thread_ts:
                        payload["thread_ts"] = thread_ts

                    elif "thread_ts" in payload:
                        # Handle situations where one channel has a thread_id
                        # specified, and the next does not.  We do not want to
                        # cary forward the last value specified
                        del payload["thread_ts"]

                    if channel[0] == "+":
                        # Treat as encoded id if prefixed with a +
                        payload["channel"] = channel[1:]

                    elif channel[0] == "@":
                        # Treat @ value 'as is'
                        payload["channel"] = channel

                    else:
                        # Prefix with channel hash tag (if not already)
                        payload["channel"] = (
                            channel if channel[0] == "#" else f"#{channel}"
                        )

            response = self._send(url, payload)
            if not response:
                # Handle any error
                has_error = True
                continue

            # Store the valid channel or chat ID (for DMs) that will
            # be accepted by Slack's attachment method later.
            if response.get("channel"):
                attach_channel_list.append(response.get("channel"))

            self.logger.info(
                "Sent Slack notification{}.".format(
                    f" to {channel}" if channel is not None else ""
                )
            )

        if (
            attach
            and self.attachment_support
            and self.mode is SlackMode.BOT
            and attach_channel_list
        ):
            # Send our attachments (can only be done in bot mode)
            for no, attachment in enumerate(attach, start=1):

                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                self.logger.debug(
                    f"Posting Slack attachment {attachment.url(privacy=True)}"
                )

                # Get the URL to which to upload the file.
                # https://api.slack.com/methods/files.getUploadURLExternal
                _params = {
                    "filename": (
                        attachment.name
                        if attachment.name
                        else f"file{no:03}.dat"
                    ),
                    "length": len(attachment),
                }
                _url = self.api_url.format("files.getUploadURLExternal")
                response = self._send(
                    _url, {}, http_method="get", params=_params
                )
                if not (
                    response
                    and response.get("file_id")
                    and response.get("upload_url")
                ):
                    self.logger.error("Could retrieve file upload URL.")
                    # We failed to get an upload URL, take an early exit
                    return False

                file_id = response.get("file_id")
                upload_url = response.get("upload_url")

                # Upload file
                response = self._send(upload_url, {}, attach=attachment)

                # Send file to channels
                # https://api.slack.com/methods/files.completeUploadExternal
                for channel_id in attach_channel_list:
                    _payload = {
                        "files": [{
                            "id": file_id,
                            "title": attachment.name,
                        }],
                        "channel_id": channel_id,
                    }
                    _url = self.api_url.format("files.completeUploadExternal")
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
                    if not (response and response.get("files")):
                        self.logger.error("Failed to send file to channel.")
                        # We failed to send the file to the channel,
                        # take an early exit
                        return False

        return not has_error

    def lookup_userid(self, email):
        """Takes an email address and attempts to resolve/acquire it's user id
        for notification purposes."""
        if email in self._lookup_users:
            # We're done as entry has already been retrieved
            return self._lookup_users[email]

        if self.mode is not SlackMode.BOT:
            # You can not look up
            self.logger.warning(
                "Emails can not be resolved to Slack User IDs unless you "
                "have a bot configured."
            )
            return None

        lookup_url = self.api_url.format("users.lookupByEmail")
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {self.access_token}",
        }

        # we pass in our email address as the argument
        params = {
            "email": email,
        }

        self.logger.debug(
            "Slack User Lookup POST URL:"
            f" {lookup_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Slack User Lookup Parameters: {params!s}")

        # Initialize our HTTP JSON response
        response = {"ok": False}

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
            with contextlib.suppress(AttributeError, TypeError, ValueError):
                # Load our JSON object if we can

                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                response = loads(r.content)

            # We can get a 200 response, but still fail.  A failure message
            # might look like this (missing bot permissions):
            #    {
            #      'ok': False,
            #      'error': 'missing_scope',
            #      'needed': 'users:read.email',
            #      'provided': 'calls:write,chat:write'
            #    }

            if r.status_code != requests.codes.ok or not (
                response and response.get("ok", False)
            ):

                # We had a problem
                status_str = NotifySlack.http_response_code_lookup(
                    r.status_code, SLACK_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Slack User Lookup:{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")
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
            user_id = response["user"]["id"]

            # Cache it for future
            self._lookup_users[email] = user_id
            self.logger.info(
                "Email %s resolves to the Slack User ID: %s.", email, user_id
            )

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred looking up Slack User.",
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            # Return; we're done
            return None

        return user_id

    def _send(
        self,
        url,
        payload,
        attach=None,
        http_method="post",
        params=None,
        **kwargs,
    ):
        """Wrapper to the requests (post) object."""
        self.logger.debug(
            f"Slack POST URL: {url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Slack Payload: {payload!s}")

        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
        }

        if not attach:
            headers["Content-Type"] = "application/json; charset=utf-8"

        if self.mode is SlackMode.BOT:
            headers["Authorization"] = f"Bearer {self.access_token}"

        # Our response object
        response = {"ok": False}

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Our attachment path (if specified)
        files = None

        try:
            # Open our attachment path if required:
            if attach:
                files = {
                    "file": (
                        attach.name,
                        # file handle is safely closed in `finally`; inline
                        # open is intentional
                        open(attach.path, "rb"),  # noqa: SIM115
                        ),
                    }

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
            with contextlib.suppress(AttributeError, TypeError, ValueError):
                # Load our JSON object if we can
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                response = loads(r.content)

            # Another response type is:
            # {
            #   'ok': False,
            #   'error': 'not_in_channel',
            # }
            status_okay = False
            if self.mode is SlackMode.BOT:
                status_okay = (
                    (response and response.get("ok", False))
                    or
                    # Responses for file uploads look like this
                    # 'OK - <file length>'
                    (
                        r.content
                        and isinstance(r.content, bytes)
                        and b"OK" in r.content
                    )
                )
            elif r.content == b"ok":
                # The text 'ok' is returned if this is a Webhook request
                # So the below captures that as well.
                status_okay = True

            if r.status_code != requests.codes.ok or not status_okay:
                # We had a problem
                status_str = NotifySlack.http_response_code_lookup(
                    r.status_code, SLACK_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send{} to Slack: {}{}error={}.".format(
                        (" " + attach.name) if attach else "",
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")
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
                "A Connection error occurred posting {}to Slack.".format(
                    attach.name if attach else ""
                )
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while reading {}.".format(
                    attach.name if attach else "attachment"
                )
            )
            self.logger.debug(f"I/O Exception: {e!s}")
            return False

        finally:
            # Close our file (if it's open) stored in the second element
            # of our files tuple (index 1)
            if files:
                files["file"][1].close()

        # Return the response for processing
        return response

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.token_a,
            self.token_b,
            self.token_c,
            self.access_token,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
            "footer": "yes" if self.include_footer else "no",
            "blocks": "yes" if self.use_blocks else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine if there is a botname present
        botname = ""
        if self.user:
            botname = "{botname}@".format(
                botname=NotifySlack.quote(self.user, safe=""),
            )

        if self.mode == SlackMode.WEBHOOK:
            return (
                "{schema}://{botname}{token_a}/{token_b}/{token_c}/"
                "{targets}/?{params}".format(
                    schema=self.secure_protocol,
                    botname=botname,
                    token_a=self.pprint(self.token_a, privacy, safe=""),
                    token_b=self.pprint(self.token_b, privacy, safe=""),
                    token_c=self.pprint(self.token_c, privacy, safe=""),
                    targets="/".join(
                        [NotifySlack.quote(x, safe="") for x in self.channels]
                    ),
                    params=NotifySlack.urlencode(params),
                )
            )
        # else -> self.mode == SlackMode.BOT:
        return "{schema}://{botname}{access_token}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            botname=botname,
            access_token=self.pprint(self.access_token, privacy, safe=""),
            targets="/".join(
                [NotifySlack.quote(x, safe="") for x in self.channels]
            ),
            params=NotifySlack.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.channels)

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The first token is stored in the hostname
        token = NotifySlack.unquote(results["host"])

        # Get unquoted entries
        entries = NotifySlack.split_path(results["fullpath"])

        # Verify if our token_a us a bot token or part of a webhook:
        if token.startswith("xo"):
            # We're dealing with a bot
            results["access_token"] = token

        else:
            # We're dealing with a webhook
            results["token_a"] = token
            results["token_b"] = entries.pop(0) if entries else None
            results["token_c"] = entries.pop(0) if entries else None

        # assign remaining entries to the channels we wish to notify
        results["targets"] = entries

        # Support the token flag where you can set it to the bot token
        # or the webhook token (with slash delimiters)
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            # Break our entries up into a list; we can ue the Channel
            # list delimiter above since it doesn't contain any characters
            # we don't otherwise accept anyway in our token
            entries = list(
                filter(
                    bool,
                    CHANNEL_LIST_DELIM.split(
                        NotifySlack.unquote(results["qsd"]["token"])
                    ),
                )
            )

            # check to see if we're dealing with a bot/user token
            if entries and entries[0].startswith("xo"):
                # We're dealing with a bot
                results["access_token"] = entries[0]
                results["token_a"] = None
                results["token_b"] = None
                results["token_c"] = None

            else:  # Webhook
                results["access_token"] = None
                results["token_a"] = entries.pop(0) if entries else None
                results["token_b"] = entries.pop(0) if entries else None
                results["token_c"] = entries.pop(0) if entries else None

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += list(
                filter(
                    bool,
                    CHANNEL_LIST_DELIM.split(
                        NotifySlack.unquote(results["qsd"]["to"])
                    ),
                )
            )

        # Get Image Flag
        results["include_image"] = \
            parse_bool(results["qsd"].get(
                "image", NotifySlack.template_args["image"]["default"]))

        # Get Payload structure (use blocks?)
        if "blocks" in results["qsd"] and len(results["qsd"]["blocks"]):
            results["use_blocks"] = parse_bool(results["qsd"]["blocks"])

        # Get Footer Flag
        results["include_footer"] = \
            parse_bool(results["qsd"].get(
                "footer", NotifySlack.template_args["footer"]["default"]))

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://hooks.slack.com/services/TOKEN_A/TOKEN_B/TOKEN_C
        """

        result = re.match(
            r"^https?://hooks\.slack\.com/services/"
            r"(?P<token_a>[A-Z0-9]+)/"
            r"(?P<token_b>[A-Z0-9]+)/"
            r"(?P<token_c>[A-Z0-9]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifySlack.parse_url(
                "{schema}://{token_a}/{token_b}/{token_c}/{params}".format(
                    schema=NotifySlack.secure_protocol,
                    token_a=result.group("token_a"),
                    token_b=result.group("token_b"),
                    token_c=result.group("token_c"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None
