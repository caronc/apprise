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
"""
Mattermost Notifications.

This plugin supports 2 modes of operation:

1. Webhook mode (default):
   - Uses Mattermost Incoming Webhooks: /hooks/<webhook_token>
   - Targets are channel names (for example: '#support' or 'support')
   - If no targets are specified, Mattermost uses the webhook default

2. Bot mode (mode=bot):
   - Uses Mattermost REST API: /api/v4/posts
   - Requires a Bot (or User) Access Token (Bearer token)
   - Targets are channel_id values by default
   - Channel name resolution is supported when a team is known

"""

from __future__ import annotations

from itertools import chain

# Create an incoming webhook; the website will provide you with something like:
#  http://localhost:8065/hooks/yobjmukpaw3r3urc5h6i369yima
#                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^
#                              |-- this is the webhook --|
#
# You can effectively turn the url above to read this:
# mmost://localhost:8065/yobjmukpaw3r3urc5h6i369yima
#  - swap http with mmost
#  - drop /hooks/ reference
from json import dumps, loads
import re
from typing import Any

import requests

from ..common import NotifyImageSize, NotifyType, PersistentStoreMode
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

# Some Reference Locations:
# - https://docs.mattermost.com/developer/webhooks-incoming.html
# - https://docs.mattermost.com/administration/config-settings.html

IS_CHANNEL = re.compile(r"^(#|%23)(?P<name>[A-Za-z0-9_-]+)$")
IS_CHANNEL_ID = re.compile(r"^(\+|%2B)?(?P<name>[A-Za-z0-9_-]+)$")


class MattermostMode:
    """Supported Mattermost integration modes."""

    # Incoming webhook mode
    WEBHOOK = "webhook"

    # Bot API mode
    BOT = "bot"


# Define our Mattermost Modes
MATTERMOST_MODES = (
    MattermostMode.WEBHOOK,
    MattermostMode.BOT,
)


class NotifyMattermost(NotifyBase):
    """A wrapper for Mattermost Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Mattermost"

    # The services URL
    service_url = "https://mattermost.com/"

    # The default protocol
    protocol = "mmost"

    # The default secure protocol
    secure_protocol = "mmosts"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/mattermost/"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4000

    # Mattermost does not have a title
    title_maxlen = 0

    # Allow persistent caching of bot channel lookups
    storage_mode = PersistentStoreMode.AUTO

    # Keep our cache for 20 days
    default_cache_expiry_sec = 60 * 60 * 24 * 20

    # Lower rate req since service is self hosted in most
    # circumstances
    request_rate_per_sec = 0.02

    templates = (
        "{schema}://{host}/{token}",
        "{schema}://{host}:{port}/{token}",
        "{schema}://{host}/{fullpath}/{token}",
        "{schema}://{host}:{port}/{fullpath}/{token}",
        "{schema}://{user}@{host}/{token}",
        "{schema}://{user}@{host}:{port}/{token}",
        "{schema}://{user}@{host}/{fullpath}/{token}",
        "{schema}://{user}@{host}:{port}/{fullpath}/{token}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("User"),
                "type": "string",
            },
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "token": {
                # Webhook Token (webhook mode) OR Access Token (bot mode)
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "fullpath": {
                "name": _("Path"),
                "type": "string",
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "target_channel": {
                "name": _("Target Channel"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            "target_channel_id": {
                "name": _("Target Channel ID"),
                "type": "string",
                "prefix": "",
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
            "to": {
                "alias_of": "targets",
            },
            "channel": {
                # Backwards compatible
                "alias_of": "targets",
            },
            "channels": {
                # Backwards compatible
                "alias_of": "targets",
            },
            "icon_url": {
                "name": _("Icon URL"),
                "type": "string",
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
            "team": {
                "alias_of": "user",
            },
            "botname": {
                "alias_of": "user",
            },
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": MATTERMOST_MODES,
                "default": MATTERMOST_MODES[0],
            },
        },
    )

    def __init__(
        self,
        token: str,
        fullpath: str | None = None,
        targets: list[str] | str | None = None,
        include_image: bool = False,
        icon_url: str | None = None,
        mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Mattermost object."""
        super().__init__(**kwargs)

        self.schema = "https" if self.secure else "http"
        self.fullpath = (
            "" if not isinstance(fullpath, str) else fullpath.strip()
        )

        # Mode
        if isinstance(mode, str) and mode.strip():
            mode_ = mode.strip().lower()
            self.mode = next(
                (m for m in MATTERMOST_MODES if m.startswith(mode_)), None
            )
            if self.mode not in MATTERMOST_MODES:
                msg = f"The Mattermost mode specified ({mode}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.mode = self.template_args["mode"]["default"]

        # Token (webhook token in webhook mode, bearer token in bot mode)
        self.token = validate_regex(token)
        if not self.token:
            msg = f"An invalid Mattermost Token ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Used for URL generation afterwards only
        self._invalid_targets = []

        # Channels:
        self.targets = []
        for target in parse_list(targets):
            result = IS_CHANNEL.match(target)
            if result:
                if self.mode == MattermostMode.BOT and not self.user:
                    # No team was defined and we're in BOT mode
                    self.logger.warning(
                        "Mattermost bot mode requires a team to resolve "
                        "%s, dropping it.",
                        target,
                    )
                    self._invalid_targets.append(target)
                    continue

                # store valid channel
                self.targets.append(("#", result.group("name")))
                continue

            result = IS_CHANNEL_ID.match(target)
            if result:
                if self.mode == MattermostMode.WEBHOOK:
                    # store valid channel
                    self.targets.append(("#", result.group("name")))

                else:  # MattermostMode.BOT
                    # store valid channel_id
                    self.targets.append(("+", result.group("name")))
                continue

            self.logger.warning(
                "Dropping invalid Mattermost target %s",
                target,
            )
            self._invalid_targets.append(target)

        # Webhook mode features (ignored in bot mode)
        self.include_image = include_image

        # Support a user-provided icon URL
        self.icon_url = icon_url

    def __len__(self) -> int:
        """Returns the number of outbound HTTP requests expected."""
        return max(1, len(self.targets))

    def _channel_lookup(self, channel: str) -> str | None:
        """
        Resolve a channel name to a channel_id.

        Resolution occurs only during send(); results are persistently cached.
        """
        # Attempt to pull from Persistent Storage if available
        key = f"c:{channel}"
        cached = self.store.get(key)
        if cached:
            return cached

        port = "" if self.port is None else f":{self.port}"
        team = NotifyMattermost.quote(self.user, safe="")
        name = NotifyMattermost.quote(channel, safe="")

        headers: dict[str, str] = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        url = "{}://{}{}{}/api/v4/teams/name/{}/channels/name/{}".format(
            self.schema,
            self.host,
            port,
            self.fullpath.rstrip("/"),
            team,
            name,
        )

        self.logger.debug(
            "Mattermost channel lookup URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )

        self.throttle()

        try:
            r = requests.get(
                url,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                status = self.http_response_code_lookup(r.status_code)
                self.logger.warning(
                    "Mattermost channel lookup failed for %s: %s, error=%d.",
                    channel,
                    status,
                    r.status_code,
                )
                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return None

            try:
                data = loads(r.content.decode("utf-8"))

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                self.logger.debug(
                    "Mattermost channel lookup response was not JSON:\r\n%r",
                    (r.content or b"")[:2000],
                )
                return None

            channel_id = data.get("id")
            if not isinstance(channel_id, str) or not channel_id.strip():
                return None

            self.store.set(
                key,
                channel_id,
                expires=self.default_cache_expiry_sec,
            )
            return channel_id

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred performing Mattermost channel "
                "lookup for %s.",
                channel,
            )
            self.logger.debug("Socket Exception: %s", e)
            return None

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Mattermost Notification."""

        if self.mode == MattermostMode.BOT and not self.targets:
            self.logger.warning(
                "Mattermost BOT mode has no valid channels to notify, "
                "aborting."
            )
            return False

        # Initialize our error tracking
        has_error = False

        # Prepare our port reference in advance
        port = "" if self.port is None else f":{self.port}"

        headers: dict[str, str] = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        if self.mode == MattermostMode.BOT:
            url = "{}://{}{}{}/api/v4/posts".format(
                self.schema, self.host, port, self.fullpath.rstrip("/")
            )

            # Append headers
            headers["Authorization"] = f"Bearer {self.token}"
            expected = (requests.codes.created, requests.codes.ok)

        else:  # self.mode == MattermostMode.WEBHOOK
            url = "{}://{}{}{}/hooks/{}".format(
                self.schema,
                self.host,
                port,
                self.fullpath.rstrip("/"),
                self.token,
            )
            expected = (requests.codes.ok,)

        # Iterate over our targets
        targets = self.targets.copy()
        if self.mode == MattermostMode.WEBHOOK and not targets:
            targets = [(None, None)]

        for kind, value in targets:
            target = value
            if kind == "#" and self.mode == MattermostMode.BOT:
                target = self._channel_lookup(value)
                if not target:
                    has_error = True
                    continue

            if self.mode == MattermostMode.BOT:
                payload: dict[str, Any] = {
                    "channel_id": target,
                    "message": body,
                }

            else:
                payload: dict[str, Any] = {
                    "text": body,
                }

                image_url = self.icon_url
                if not image_url and self.include_image:
                    image_url = self.image_url(notify_type)

                if image_url:
                    payload["icon_url"] = image_url

                payload["username"] = (
                    self.user if self.user else self.app_id
                )

                if target:
                    payload["channel"] = target

            self.logger.debug(
                "Mattermost %s POST URL: %s (cert_verify=%r)",
                self.mode,
                url,
                self.verify_certificate,
            )
            self.logger.debug(
                "Mattermost %s Payload: %s", self.mode, payload
            )

            self.throttle()

            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code not in expected:
                    status = self.http_response_code_lookup(r.status_code)
                    self.logger.warning(
                        "Failed to send Mattermost notification to "
                        "%s: %s, error=%d.",
                        f"channel_id {target}"
                        if self.mode == MattermostMode.BOT
                        else f"channel {target}",
                        status,
                        r.status_code,
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )
                    has_error = True
                    continue

                self.logger.info(
                    "Sent Mattermost %s notification to %s.",
                    self.mode,
                    target,
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Mattermost "
                    "%s notification to %s.",
                    self.mode, target,
                )
                self.logger.debug("Socket Exception: %s", e)
                has_error = True
                continue

        # Return our overall status
        return not has_error

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.mode,
            self.token,
            self.host,
            self.port,
            self.fullpath,
            self.user if self.mode == MattermostMode.BOT else None,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        params: dict[str, Any] = {
            "image": "yes" if self.include_image else "no",
        }

        if self.mode != self.template_args["mode"]["default"]:
            params["mode"] = self.mode

        if self.mode == MattermostMode.WEBHOOK and self.icon_url:
            params["icon_url"] = self.icon_url

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.targets:
            # historically the value only accepted one channel and is
            # therefore identified as 'channel'. Channels have always been
            # optional, so that is why this setting is nested in an if block
            entries = []
            for kind, value in self.targets:
                if kind == "#":
                    entries.append(f"#{value}")
                else:
                    entries.append(f"+{value}")

            params["to"] = ",".join(chain(
                [NotifyMattermost.quote(v, safe="#+") for v in entries],
                [NotifyMattermost.quote(x, safe="")
                 for x in self._invalid_targets],
            ))

        default_port = 443 if self.secure else 80
        default_schema = self.secure_protocol if self.secure else self.protocol

        # Determine if there is a source present
        source = ""
        if self.user:
            source = "{source}@".format(
                source=NotifyMattermost.quote(self.user, safe=""),
            )

        return (
            "{schema}://{source}{hostname}{port}{fullpath}{token}"
            "/?{params}".format(
                schema=default_schema,
                source=source,
                # never encode hostname since we're expecting it to be a valid
                # one
                hostname=self.host,
                port=(
                    ""
                    if self.port is None or self.port == default_port
                    else f":{self.port}"
                ),
                fullpath=(
                    "/"
                    if not self.fullpath
                    else "{}/".format(
                        NotifyMattermost.quote(self.fullpath, safe="/")
                    )
                ),
                token=self.pprint(self.token, privacy, safe=""),
                params=NotifyMattermost.urlencode(params),
            )
        )

    @staticmethod
    def parse_url(url: str):
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Acquire our tokens; the last one will always be our token
        # all entries before it will be our path
        tokens = NotifyMattermost.split_path(results["fullpath"])

        results["token"] = None if not tokens else tokens.pop()
        results["fullpath"] = (
            "" if not tokens else "/{}".format("/".join(tokens))
        )

        # Define our optional list of channels to notify
        results["targets"] = []

        # Support both 'to' (for yaml configuration) and channel(s)=
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            # Allow the user to specify the channel to post to
            results["targets"].extend(
                NotifyMattermost.parse_list(results["qsd"]["to"])
            )

        if "channel" in results["qsd"] and len(results["qsd"]["channel"]):
            results["targets"].extend(
                NotifyMattermost.parse_list(results["qsd"]["channel"])
            )

        if "channels" in results["qsd"] and len(results["qsd"]["channels"]):
            # Allow the user to specify the channel to post to
            results["targets"].extend(
                NotifyMattermost.parse_list(results["qsd"]["channels"])
            )

        # Image manipulation
        results["include_image"] = parse_bool(
            results["qsd"].get(
                "image", NotifyMattermost.template_args["image"]["default"]
            )
        )

        # Our Mode
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyMattermost.unquote(
                results["qsd"]["mode"]
            )

        # Team support (bot mode lookup). This maps to `user`.
        if "team" in results["qsd"] and results["qsd"]["team"]:
            results["user"] = NotifyMattermost.unquote(
                results["qsd"]["team"]
            )
            if "mode" not in results:
                results["mode"] = MattermostMode.BOT

        elif "botname" in results["qsd"] and results["qsd"]["botname"]:
            results["user"] = NotifyMattermost.unquote(
                results["qsd"]["botname"]
            )

        if "icon_url" in results["qsd"]:
            results["icon_url"] = NotifyMattermost.unquote(
                results["qsd"]["icon_url"]
            )

        return results

    @staticmethod
    def parse_native_url(url: str) -> dict[str, Any] | None:
        """
        Support parsing the webhook straight from URL
            https://HOST:443/workflows/WORKFLOWID/triggers/manual/paths/invoke
            https://mattermost.HOST/hooks/TOKEN
        """

        # Match our workflows webhook URL and re-assemble
        result = re.match(
            r"^http(?P<secure>s?)://(?P<host>mattermost\.[A-Z0-9_.-]+)"
            r"(:(?P<port>[1-9][0-9]{0,5}))?"
            r"/hooks/"
            r"(?P<token>[A-Z0-9_-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            default_port = (
                int(result.group("port"))
                if result.group("port")
                else (443 if result.group("secure") else 80)
            )

            default_schema = (
                NotifyMattermost.secure_protocol
                if result.group("secure")
                else NotifyMattermost.protocol
            )

            # Construct our URL
            return NotifyMattermost.parse_url(
                "{schema}://{host}{port}/{token}/{params}".format(
                    schema=default_schema,
                    host=result.group("host"),
                    port=(
                        ""
                        if not result.group("port")
                        or int(result.group("port")) == default_port
                        else f":{default_port}"
                    ),
                    token=result.group("token"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )
        return None
