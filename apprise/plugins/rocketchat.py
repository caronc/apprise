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

from itertools import chain
from json import dumps, loads
import re

import requests

from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool, parse_list
from .base import NotifyBase

IS_CHANNEL = re.compile(r"^#(?P<name>[A-Za-z0-9_-]+)$")
IS_USER = re.compile(r"^@(?P<name>[A-Za-z0-9._-]+)$")
IS_ROOM_ID = re.compile(r"^(?P<name>[A-Za-z0-9]+)$")

# Extend HTTP Error Messages
RC_HTTP_ERROR_MAP = {
    400: "Channel/RoomId is wrong format, or missing from server.",
    401: "Authentication tokens provided is invalid or missing.",
}


class RocketChatAuthMode:
    """The Chat Authentication mode is detected."""

    # providing a webhook
    WEBHOOK = "webhook"

    # Support token submission
    TOKEN = "token"

    # Providing a username and password (default)
    BASIC = "basic"


# Define our authentication modes
ROCKETCHAT_AUTH_MODES = (
    RocketChatAuthMode.WEBHOOK,
    RocketChatAuthMode.TOKEN,
    RocketChatAuthMode.BASIC,
)


class NotifyRocketChat(NotifyBase):
    """A wrapper for Notify Rocket.Chat Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Rocket.Chat"

    # The services URL
    service_url = "https://rocket.chat/"

    # The default protocol
    protocol = "rocket"

    # The default secure protocol
    secure_protocol = "rockets"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_rocketchat"

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # The title is not used
    title_maxlen = 0

    # The maximum size of the message
    body_maxlen = 1000

    # Default to markdown
    notify_format = NotifyFormat.MARKDOWN

    # Define object templates
    templates = (
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{token}@{host}:{port}/{targets}",
        "{schema}://{user}:{token}@{host}/{targets}",
        "{schema}://{webhook}@{host}",
        "{schema}://{webhook}@{host}:{port}",
        "{schema}://{webhook}@{host}/{targets}",
        "{schema}://{webhook}@{host}:{port}/{targets}",
    )

    # Define our template arguments
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "user": {
                "name": _("Username"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "token": {
                "name": _("API Token"),
                "map_to": "password",
                "private": True,
            },
            "webhook": {
                "name": _("Webhook"),
                "type": "string",
            },
            "target_channel": {
                "name": _("Target Channel"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "target_room": {
                "name": _("Target Room ID"),
                "type": "string",
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
            "mode": {
                "name": _("Webhook Mode"),
                "type": "choice:string",
                "values": ROCKETCHAT_AUTH_MODES,
            },
            "avatar": {
                "name": _("Use Avatar"),
                "type": "bool",
                "default": False,
            },
            "webhook": {
                "alias_of": "webhook",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self, webhook=None, targets=None, mode=None, avatar=None, **kwargs
    ):
        """Initialize Notify Rocket.Chat Object."""
        super().__init__(**kwargs)

        # Set our schema
        self.schema = "https" if self.secure else "http"

        # Prepare our URL
        self.api_url = f"{self.schema}://{self.host}"

        if isinstance(self.port, int):
            self.api_url += f":{self.port}"

        # Initialize channels list
        self.channels = []

        # Initialize room list
        self.rooms = []

        # Initialize user list (webhook only)
        self.users = []

        # Assign our webhook (if defined)
        self.webhook = webhook

        # Used to track token headers upon authentication (if successful)
        # This is only used if not on webhook mode
        self.headers = {}

        # Authentication mode
        self.mode = None if not isinstance(mode, str) else mode.lower()

        if self.mode and self.mode not in ROCKETCHAT_AUTH_MODES:
            msg = f"The authentication mode specified ({mode}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Detect our mode if it wasn't specified
        if not self.mode:
            if self.webhook is not None:
                # Just a username was specified, we treat this as a webhook
                self.mode = RocketChatAuthMode.WEBHOOK
            elif self.password and len(self.password) > 32:
                self.mode = RocketChatAuthMode.TOKEN
            else:
                self.mode = RocketChatAuthMode.BASIC

            self.logger.debug(
                "Auto-Detected Rocketchat Auth Mode: %s", self.mode
            )

        if self.mode in (
            RocketChatAuthMode.BASIC,
            RocketChatAuthMode.TOKEN,
        ) and not (self.user and self.password):
            # Username & Password is required for Rocket Chat to work
            msg = "No Rocket.Chat {} was specified.".format(
                "user/pass combo"
                if self.mode == RocketChatAuthMode.BASIC
                else "user/apikey"
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        elif self.mode == RocketChatAuthMode.WEBHOOK and not self.webhook:
            msg = "No Rocket.Chat Incoming Webhook was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        if self.mode == RocketChatAuthMode.TOKEN:
            # Set our headers for further communication
            self.headers.update({
                "X-User-Id": self.user,
                "X-Auth-Token": self.password,
            })

        # Validate recipients and drop bad ones:
        for recipient in parse_list(targets):
            result = IS_CHANNEL.match(recipient)
            if result:
                # store valid device
                self.channels.append(result.group("name"))
                continue

            result = IS_ROOM_ID.match(recipient)
            if result:
                # store valid room
                self.rooms.append(result.group("name"))
                continue

            result = IS_USER.match(recipient)
            if result:
                # store valid room
                self.users.append(result.group("name"))
                continue

            self.logger.warning(
                f"Dropped invalid channel/room/user ({recipient}) specified.",
            )

        if (
            self.mode == RocketChatAuthMode.BASIC
            and len(self.rooms) == 0
            and len(self.channels) == 0
        ):
            msg = "No Rocket.Chat room and/or channels specified to notify."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare our avatar setting
        # - if specified; that trumps all
        # - if not specified and we're dealing with a basic setup, the Avatar
        #   is disabled by default. This is because if the account doesn't
        #   have the bot flag set on it it won't work as documented here:
        #       https://developer.rocket.chat/api/rest-api/endpoints\
        #             /team-collaboration-endpoints/chat/postmessage
        # - Otherwise if we're a webhook, we enable the avatar by default
        #   (if not otherwise specified) since it will work nicely.
        # Place an avatar image to associate with our content
        if self.mode == RocketChatAuthMode.BASIC:
            self.avatar = False if avatar is None else avatar

        else:  # self.mode == RocketChatAuthMode.WEBHOOK:
            self.avatar = True if avatar is None else avatar

        return

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.user,
            (
                self.password
                if self.mode
                in (RocketChatAuthMode.BASIC, RocketChatAuthMode.TOKEN)
                else self.webhook
            ),
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "avatar": "yes" if self.avatar else "no",
            "mode": self.mode,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        if self.mode in (RocketChatAuthMode.BASIC, RocketChatAuthMode.TOKEN):
            auth = "{user}:{password}@".format(
                user=NotifyRocketChat.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )

        else:
            auth = "{user}{webhook}@".format(
                user=(
                    "{}:".format(NotifyRocketChat.quote(self.user, safe=""))
                    if self.user
                    else ""
                ),
                webhook=self.pprint(
                    self.webhook, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )

        default_port = 443 if self.secure else 80
        return "{schema}://{auth}{hostname}{port}/{targets}/?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            ),
            targets="/".join([
                NotifyRocketChat.quote(x, safe="@#")
                for x in chain(
                    # Channels are prefixed with a pound/hashtag symbol
                    [f"#{x}" for x in self.channels],
                    # Rooms are as is
                    self.rooms,
                    # Users
                    [f"@{x}" for x in self.users],
                )
            ]),
            params=NotifyRocketChat.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        targets = len(self.channels) + len(self.rooms) + len(self.users)
        return targets if targets > 0 else 1

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Wrapper to _send since we can alert more then one channel."""

        # Call the _send_ function applicable to whatever mode we're in
        # - calls _send_webhook_notification if the mode variable is set
        # - calls _send_basic_notification if the mode variable is not set
        return getattr(
            self,
            "_send_{}_notification".format(
                RocketChatAuthMode.WEBHOOK
                if self.mode == RocketChatAuthMode.WEBHOOK
                else RocketChatAuthMode.BASIC
            ),
        )(body=body, title=title, notify_type=notify_type, **kwargs)

    def _send_webhook_notification(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """Sends a webhook notification."""

        # Our payload object
        payload = self._payload(body, title, notify_type)

        # Assemble our webhook URL
        path = f"hooks/{self.webhook}"

        # Build our list of channels/rooms/users (if any identified)
        targets = [f"@{u}" for u in self.users]
        targets.extend([f"#{c}" for c in self.channels])
        targets.extend([f"{r}" for r in self.rooms])

        if len(targets) == 0:
            # We can take an early exit
            return self._send(
                payload, notify_type=notify_type, path=path, **kwargs
            )

        # Otherwise we want to iterate over each of the targets

        # Initiaize our error tracking
        has_error = False

        while len(targets):
            # Retrieve our target
            target = targets.pop(0)

            # Assign our channel/room/user
            payload["channel"] = target

            if not self._send(
                payload, notify_type=notify_type, path=path, **kwargs
            ):

                # toggle flag
                has_error = True

        return not has_error

    def _send_basic_notification(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """Authenticates with the server using a user/pass combo for
        notifications."""
        # Track whether we authenticated okay

        if self.mode == RocketChatAuthMode.BASIC and not self.login():
            return False

        # prepare JSON Object
        _payload = self._payload(body, title, notify_type)

        # Initiaize our error tracking
        has_error = False

        # Build our list of channels/rooms/users (if any identified)
        channels = [f"@{u}" for u in self.users]
        channels.extend([f"#{c}" for c in self.channels])

        # Create a copy of our channels to notify against
        payload = _payload.copy()
        while len(channels) > 0:
            # Get Channel
            channel = channels.pop(0)
            payload["channel"] = channel

            if not self._send(payload, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

        # Create a copy of our room id's to notify against
        rooms = list(self.rooms)
        payload = _payload.copy()
        while len(rooms):
            # Get Room
            room = rooms.pop(0)
            payload["roomId"] = room

            if not self._send(payload, notify_type=notify_type, **kwargs):

                # toggle flag
                has_error = True

        if self.mode == RocketChatAuthMode.BASIC:
            # logout
            self.logout()

        return not has_error

    def _payload(self, body, title="", notify_type=NotifyType.INFO):
        """Prepares a payload object."""
        # prepare JSON Object
        payload = {
            "text": body,
        }

        # apply our images if they're set to be displayed
        image_url = self.image_url(notify_type)
        if self.avatar and image_url:
            payload["avatar"] = image_url

        return payload

    def _send(
        self, payload, notify_type, path="api/v1/chat.postMessage", **kwargs
    ):
        """Perform Notify Rocket.Chat Notification."""

        api_url = f"{self.api_url}/{path}"

        self.logger.debug(
            "Rocket.Chat POST URL:"
            f" {api_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Rocket.Chat Payload: {payload!s}")

        # Copy our existing headers
        headers = self.headers.copy()

        # Apply minimum headers
        headers.update({
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        })

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                api_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyRocketChat.http_response_code_lookup(
                    r.status_code, RC_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Rocket.Chat {}:notification: "
                    "{}{}error={}.".format(
                        self.mode,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.info(f"Sent Rocket.Chat {self.mode}:notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Rocket.Chat "
                f"{self.mode}:notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Return; we're done
            return False

        return True

    def login(self):
        """Login to our server."""

        payload = {
            "username": self.user,
            "password": self.password,
        }

        api_url = "{}/{}".format(self.api_url, "api/v1/login")

        try:
            r = requests.post(
                api_url,
                data=payload,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyRocketChat.http_response_code_lookup(
                    r.status_code, RC_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to authenticate {} with Rocket.Chat: "
                    "{}{}error={}.".format(
                        self.user,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.debug("Rocket.Chat authentication successful")
                response = loads(r.content)
                if response.get("status") != "success":
                    self.logger.warning(
                        f"Could not authenticate {self.user} with Rocket.Chat."
                    )
                    return False

                # Set our headers for further communication
                self.headers["X-Auth-Token"] = response.get(
                    "data", {"authToken": None}
                ).get("authToken")
                self.headers["X-User-Id"] = response.get(
                    "data", {"userId": None}
                ).get("userId")

        except (AttributeError, TypeError, ValueError):
            # Our response was not the JSON type we had expected it to be
            # - ValueError = r.content is Unparsable
            # - TypeError = r.content is None
            # - AttributeError = r is None
            self.logger.warning(
                f"A commuication error occurred authenticating {self.user} on "
                "Rocket.Chat."
            )
            return False

        except requests.RequestException as e:
            self.logger.warning(
                f"A connection error occurred authenticating {self.user} on "
                "Rocket.Chat."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        return True

    def logout(self):
        """Logout of our server."""

        api_url = "{}/{}".format(self.api_url, "api/v1/logout")

        try:
            r = requests.post(
                api_url,
                headers=self.headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyRocketChat.http_response_code_lookup(
                    r.status_code, RC_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to logoff {} from Rocket.Chat: "
                    "{}{}error={}.".format(
                        self.user,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.debug(
                    f"Rocket.Chat log off successful; response {r.content}."
                )

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred logging off the "
                "Rocket.Chat server"
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        return True

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        try:
            # Attempt to detect the webhook (if specified in the URL)
            # If no webhook is specified, then we just pass along as if nothing
            # happened. However if we do find a webhook, we want to rebuild our
            # URL without it since it conflicts with standard URLs. Support
            # %2F since that is a forward slash escaped

            # rocket://webhook@host
            # rocket://user:webhook@host
            match = re.match(
                r"^\s*(?P<schema>[^:]+://)((?P<user>[^:]+):)?"
                r"(?P<webhook>[a-z0-9]+(/|%2F)"
                r"[a-z0-9]+)\@(?P<url>.+)$",
                url,
                re.I,
            )

        except TypeError:
            # Not a string
            return None

        if match:
            # Re-assemble our URL without the webhook
            url = "{schema}{user}{url}".format(
                schema=match.group("schema"),
                user=(
                    "{}@".format(match.group("user"))
                    if match.group("user")
                    else ""
                ),
                url=match.group("url"),
            )

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        if match:
            # store our webhook
            results["webhook"] = NotifyRocketChat.unquote(
                match.group("webhook")
            )

            # Take on the password too in the event we're in basic mode
            # We do not unquote() as this is done at a later state
            results["password"] = match.group("webhook")

        # Apply our targets
        results["targets"] = NotifyRocketChat.split_path(results["fullpath"])

        # The user may have forced the mode
        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            results["mode"] = NotifyRocketChat.unquote(results["qsd"]["mode"])

        # avatar icon
        if "avatar" in results["qsd"] and len(results["qsd"]["avatar"]):
            results["avatar"] = parse_bool(results["qsd"].get("avatar", True))

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyRocketChat.parse_list(
                results["qsd"]["to"]
            )

        # The 'webhook' over-ride (if specified)
        if "webhook" in results["qsd"] and len(results["qsd"]["webhook"]):
            results["webhook"] = NotifyRocketChat.unquote(
                results["qsd"]["webhook"]
            )

        return results
