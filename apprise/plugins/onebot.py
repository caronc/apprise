# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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


# OneBot 11 is an HTTP API supported by QQ bot frameworks such as NapCat,
# LLOneBot, Lagrange.OneBot, and go-cqhttp.
#
# Steps:
#  1. Install a supported framework and sign in with the QQ account that
#     will send notifications.
#  2. Enable its OneBot 11 HTTP server and note the port (often 3000 for
#     NapCat or 5700 for go-cqhttp).
#  3. Optionally set an access token for Apprise to send with each request.
#
# URL syntax (HTTP):
#   onebot://host/user_id
#   onebot://host:port/@user_id/#group_id
#   onebot://token@host:port/@user_id/#group_id
#
# URL syntax (HTTPS):
#   onebots://token@host:port/@user_id/#group_id
#
# A bare number or `@` prefix identifies a QQ user. A `#` prefix identifies
# a QQ group.
#
# Resources:
# - https://github.com/botuniverse/onebot-11
# - https://napneko.github.io/onebot/segment

from __future__ import annotations

from json import dumps, loads
import re
from typing import Any, Optional

import requests

from .. import exception
from ..apprise_attachment import AppriseAttachment
from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list
from .base import NotifyBase

# OneBot HTTP errors documented at:
# https://github.com/botuniverse/onebot-11/blob/master/communication/http.md
ONEBOT_HTTP_ERROR_MAP = {
    400: "Malformed request body.",
    401: "An access token is required.",
    403: "The access token is invalid.",
    404: "The action is not supported.",
    406: "Unsupported Content-Type.",
}

# QQ user IDs may start with `@`; group IDs start with `#`.
# Both contain 1 to 19 digits.
IS_TARGET = re.compile(r"^(?P<prefix>[@#])?(?P<id>[0-9]{1,19})$")

# Match each MIME type to its OneBot media type.
ONEBOT_MEDIA_SEGMENTS = (
    ("image/", "image"),
    ("audio/", "record"),
    ("video/", "video"),
)


class NotifyOneBot(NotifyBase):
    """Send QQ notifications through a OneBot 11 server."""

    # The default descriptive name associated with the Notification
    service_name = "OneBot"

    # The services URL
    service_url = "https://github.com/botuniverse/onebot-11"

    # The default protocol (plain HTTP)
    protocol = "onebot"

    # The default secure protocol (HTTPS)
    secure_protocol = "onebots"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/onebot/"

    # Self-hosted OneBot servers do not need client-side rate limiting.
    request_rate_per_sec = 0

    # Send every attachment as a separate message.
    attachment_support = True

    # OneBot messages use plain text.
    notify_format = NotifyFormat.TEXT

    # QQ has no title field, so Apprise adds the title to the body.
    title_maxlen = 0

    # Limit each QQ text message to this many characters.
    body_maxlen = 4500

    # Define object URL templates
    templates = (
        "{schema}://{host}/{targets}",
        "{schema}://{host}:{port}/{targets}",
        "{schema}://{token}@{host}/{targets}",
        "{schema}://{token}@{host}:{port}/{targets}",
    )

    # Define our template tokens
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
            "token": {
                "name": _("Access Token"),
                "type": "string",
                "private": True,
            },
            "target_user": {
                "name": _("Target User ID"),
                "type": "string",
                "prefix": "@",
                "regex": (r"^[0-9]{1,19}$", ""),
                "map_to": "targets",
            },
            "target_group": {
                "name": _("Target Group ID"),
                "type": "string",
                "prefix": "#",
                "regex": (r"^[0-9]{1,19}$", ""),
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
            "token": {
                "alias_of": "token",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        token: Optional[str] = None,
        targets: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a OneBot notification."""
        super().__init__(**kwargs)

        # The access token is optional
        self.token = token if isinstance(token, str) and token else None

        # Store valid QQ users and groups separately.
        self.users = []
        self.groups = []

        # Keep invalid targets so url() can reproduce the original URL.
        self.invalid_targets = []

        for target in parse_list(targets):
            result = IS_TARGET.match(target)
            if not result:
                self.logger.warning(
                    "Dropped invalid OneBot target (%s) specified.", target
                )
                self.invalid_targets.append(target)
                continue

            # A `#` prefix identifies a group; all other matches are users.
            (
                self.groups if result.group("prefix") == "#" else self.users
            ).append(result.group("id"))

    def _post(self, action: str, payload: dict[str, Any]) -> bool:
        """Run one OneBot action and report whether it succeeded."""
        # Send JSON and identify Apprise to the server.
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Authenticate when an access token is configured.
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        # Build the endpoint for this OneBot action.
        url = "{schema}://{host}{port}/{action}".format(
            schema="https" if self.secure else "http",
            host=self.host,
            port=f":{self.port}" if self.port else "",
            action=action,
        )

        self.logger.debug(
            "OneBot POST URL: %s (cert_verify=%r)",
            url,
            self.verify_certificate,
        )

        # Throttle before contacting the server.
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # Report any HTTP error returned by the server.
                status_str = NotifyOneBot.http_response_code_lookup(
                    r.status_code, ONEBOT_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send OneBot %s: %s%serror=%s.",
                    action,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )
                return False

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # Accept an empty or unreadable HTTP 200 response.
                content = {}

            # OneBot can report an action failure inside an HTTP 200 response.
            if isinstance(content, dict) and (
                content.get("status") == "failed"
                or content.get("retcode", 0) not in (0, 1)
            ):
                self.logger.warning(
                    "Failed to send OneBot %s: retcode=%s, %s",
                    action,
                    content.get("retcode"),
                    content.get("wording") or content.get("message") or "",
                )
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending OneBot %s.", action
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach: Optional[AppriseAttachment] = None,
        **kwargs: Any,
    ) -> bool:
        """Send text and attachments to each OneBot target."""
        if not (self.users or self.groups):
            # A notification needs at least one valid target.
            self.logger.warning("There are no OneBot targets to notify.")
            return False

        # Check every attachment is reachable before sending anything.
        attach = attach or []
        for attachment in attach:
            if not attachment:
                # Stop before sending if an attachment is unavailable.
                self.logger.warning(
                    "Could not access OneBot attachment %s.",
                    attachment.url(privacy=True),
                )
                return False

        # Users and groups use different actions and ID fields.
        targets = [
            ("send_private_msg", "user_id", user_id) for user_id in self.users
        ] + [
            ("send_group_msg", "group_id", group_id)
            for group_id in self.groups
        ]

        # Targets that failed are left alone until the next retry.
        failed = set()

        for action, field, target_id in targets:
            # Track text delivery separately for each target.
            target = (field, target_id)

            # Skip text already delivered by an earlier attempt.
            if not body or self.is_delivered(target):
                continue

            payload = {
                field: int(target_id),
                "message": [{"type": "text", "data": {"text": body}}],
            }

            if not self._post(action, payload):
                # Record the failure and continue with the next target.
                failed.add(target)
                continue

            self.logger.info(
                "Sent OneBot notification to %s %s.", field, target_id
            )

            # Let retries skip this delivered text.
            self.mark_delivered(target)

        # Send each attachment separately. Only one is held in memory, and
        # each is read once across all targets.
        for no, attachment in enumerate(attach, start=1):
            # The targets still waiting on this attachment.
            pending = [
                (action, field, target_id)
                for action, field, target_id in targets
                if (field, target_id) not in failed
                and not self.is_delivered(
                    ("attachment", (field, target_id), no)
                )
            ]

            if not pending:
                # Nobody needs this attachment, so don't read it.
                continue

            try:
                # Base64 avoids requiring the server to access a local path.
                data = {"file": f"base64://{attachment.base64()}"}

            except exception.AppriseException:
                # The file went away or could not be read.
                self.logger.warning(
                    "Could not read OneBot attachment %s.",
                    attachment.url(privacy=True),
                )
                return False

            # Select the matching OneBot media type.
            mime = attachment.mimetype
            kind = next(
                (k for p, k in ONEBOT_MEDIA_SEGMENTS if mime.startswith(p)),
                None,
            )

            if not kind:
                # Send other formats as named files.
                kind = "file"
                data["name"] = attachment.name or "attachment.dat"

            segment = {"type": kind, "data": data}

            for action, field, target_id in pending:
                target = (field, target_id)
                payload = {field: int(target_id), "message": [segment]}
                if not self._post(action, payload):
                    # Leave this target's remaining attachments for a retry.
                    failed.add(target)
                    continue

                # Let retries skip this delivered attachment.
                self.mark_delivered(("attachment", target, no))

        return not failed

    def __len__(self) -> int:
        """Return the number of targets for this notification."""
        # Return at least one so the framework counts this instance.
        return max(1, len(self.users) + len(self.groups))

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Return the settings that identify this server connection.

        Targets are excluded so delivery can be tracked per destination.
        """
        # Include the server address, protocol, and credentials.
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.token,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Return a OneBot URL for the current settings and targets."""
        # Include shared notification URL parameters.
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Keep `@` readable while encoding the `#` used for groups.
        targets = (
            [f"@{u}" for u in self.users]
            + [f"#{g}" for g in self.groups]
            + self.invalid_targets
        )

        return "{schema}://{token}{host}{port}/{targets}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            token=(
                "{}@".format(self.pprint(self.token, privacy, safe=""))
                if self.token
                else ""
            ),
            host=self.host,
            port="" if not self.port else f":{self.port}",
            targets="/".join(NotifyOneBot.quote(t, safe="@") for t in targets),
            params=NotifyOneBot.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse a OneBot URL into constructor arguments."""
        results = NotifyBase.parse_url(url, verify_host=True)
        if not results:
            # Stop when the base URL is invalid.
            return results

        # Read the token from the query string or URL user field.
        results["token"] = NotifyOneBot.unquote(
            results["qsd"].get("token") or results["user"]
        )

        # Treat every path entry as a target.
        results["targets"] = NotifyOneBot.split_path(results["fullpath"])

        # Support the ?to= argument
        if results["qsd"].get("to"):
            results["targets"] += NotifyOneBot.parse_list(results["qsd"]["to"])

        return results
