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

# Kook (formerly Kaihei / KOOK / 开黑啦) is a Chinese gaming-focused
# communication platform similar to Discord. It supports text channels,
# voice channels, and direct messaging.
#
# === Bot Mode (Recommended) ===
# 1. Visit https://developer.kookapp.cn and sign in.
# 2. Click "Create Application" and give it a name like "Apprise".
# 3. Under your application, go to "Bot" in the left sidebar.
# 4. Copy the bot token shown on the Bot page.
# 5. Add the bot to your server (OAuth2 Invite page).
# 6. Enable Developer Mode in Kook:
#      Settings -> Others -> Developer Mode
# 7. Right-click a channel and select "Copy ID" to obtain the channel ID.
# 8. Assemble your Apprise URL:
#       kook://{bot_token}/{channel_id}
#       kook://{bot_token}/{channel1}/{channel2}
#
# For direct messages, prefix the user ID with @:
#       kook://{bot_token}/@{user_id}
#
# === Webhook Mode ===
# 1. In Kook, go to Server Settings -> Integrations -> Webhooks.
# 2. Create a new webhook for the desired channel.
# 3. Copy the webhook key from the generated webhook URL or the key field.
# 4. Assemble your Apprise URL:
#       kook://{webhook_key}?mode=webhook
#
# Native Kook incoming webhook URLs are also accepted directly:
#   https://www.kookapp.cn/api/v3/incoming/{webhook_key}
#
# API Documentation:
#   https://developer.kookapp.cn/doc/
#   https://developer.kookapp.cn/doc/http/channel-message
#   https://developer.kookapp.cn/doc/http/direct-message
#   https://developer.kookapp.cn/doc/http/asset

from json import dumps, loads
import re

import requests

from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list
from .base import NotifyBase

# Extended HTTP error messages for Kook API responses
KOOK_HTTP_ERROR_MAP = {
    400: "Bad Request - Malformed or missing parameters.",
    401: "Unauthorized - Invalid token.",
    403: "Forbidden - Insufficient permissions.",
    404: "Not Found - Invalid channel or endpoint.",
    429: "Too many consecutive requests were made.",
    500: "Internal Server Error.",
}

# Kook API base URL
KOOK_API_URL = "https://www.kookapp.cn/api/v3"


# Kook API message and asset type integers
KOOK_API_TYPE_TEXT = 1
KOOK_API_TYPE_IMAGE = 2
KOOK_API_TYPE_FILE = 4
KOOK_API_TYPE_KMARKDOWN = 9


class KookMode:
    """Tracks the mode of operation for the Kook plugin."""

    # Incoming webhook - simple, no attachment support
    WEBHOOK = "webhook"

    # Bot API - full API access with attachment support
    BOT = "bot"


# Valid mode values
KOOK_MODES = (
    KookMode.BOT,
    KookMode.WEBHOOK,
)

# Validates a Kook channel or user ID (numeric snowflake-style)
IS_TARGET_ID = re.compile(r"^\d{1,20}$")

# Prefix used in Apprise URLs to denote a DM target rather than a channel
KOOK_DM_PREFIX = "@"


class NotifyKook(NotifyBase):
    """A wrapper for Kook Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Kook"

    # The services URL
    service_url = "https://www.kookapp.cn/"

    # The default secure protocol
    secure_protocol = "kook"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/kook/"

    # Kook Bot API - post a channel message
    notify_url = KOOK_API_URL + "/message/create"

    # Kook Bot API - post a direct message
    dm_url = KOOK_API_URL + "/direct-message/create"

    # Kook CDN upload endpoint for file attachments
    asset_url = KOOK_API_URL + "/asset/create"

    # Kook incoming webhook URL template (webhook mode)
    webhook_notify_url = KOOK_API_URL + "/incoming/{key}"

    # Bot mode supports file attachments via the CDN upload path
    attachment_support = True

    # Kook supports up to 5000 characters per message
    body_maxlen = 5000

    # No native title field; the framework prepends title to body
    title_maxlen = 0

    # Default to markdown since Kook supports KMarkdown natively
    notify_format = NotifyFormat.MARKDOWN

    # Define object URL templates
    templates = (
        # Webhook mode (single key, ?mode=webhook)
        "{schema}://{token}",
        # Bot mode with one or more channel/DM targets in the path
        "{schema}://{token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
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
            # Allow the token to also be supplied as a query param
            "token": {
                "alias_of": "token",
            },
            # Comma-separated alias for targets
            "to": {
                "alias_of": "targets",
            },
            # Operating mode: bot (default) or webhook
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": KOOK_MODES,
                "default": KookMode.BOT,
            },
        },
    )

    def __init__(
        self,
        token,
        targets=None,
        mode=None,
        **kwargs,
    ):
        """Initialize Kook Object."""
        super().__init__(**kwargs)

        # Validate and store the bot token / webhook key
        self.token = token
        if not self.token:
            msg = "A Kook token must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Resolve operating mode
        if mode and isinstance(mode, str):
            # Accept a partial prefix match (e.g. "web" -> "webhook")
            self.mode = next(
                (m for m in KOOK_MODES if m.startswith(mode.lower())),
                None,
            )
            if self.mode not in KOOK_MODES:
                msg = f"The Kook mode specified ({mode}) is not valid."
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            # Default to bot mode
            self.mode = KookMode.BOT

        # Disable attachment support in webhook mode (CDN upload requires auth)
        if self.mode == KookMode.WEBHOOK:
            self.attachment_support = False

        # Process targets: channel IDs (bare) and DM users (@user_id)
        self.channels = []
        self.dm_users = []

        # Track invalid targets so they survive a URL round-trip
        self._invalid_targets = []

        for target in parse_list(targets):
            # Detect DM prefix
            if target.startswith(KOOK_DM_PREFIX):
                user_id = target[len(KOOK_DM_PREFIX) :]
                if IS_TARGET_ID.match(user_id):
                    # Valid DM user ID
                    self.dm_users.append(user_id)

                else:
                    self.logger.warning(
                        "Dropping invalid Kook DM user ID: %s",
                        target,
                    )
                    self._invalid_targets.append(target)

            else:
                # Strip optional # channel prefix for convenience
                channel_id = target[1:] if target.startswith("#") else target
                if IS_TARGET_ID.match(channel_id):
                    # Valid channel ID
                    self.channels.append(channel_id)

                else:
                    self.logger.warning(
                        "Dropping invalid Kook channel ID: %s",
                        target,
                    )
                    self._invalid_targets.append(target)

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Kook Notification."""

        # Dispatch to the appropriate sending method based on mode
        if self.mode == KookMode.WEBHOOK:
            return self._send_webhook(body)

        return self._send_bot(body, attach=attach)

    def _send_webhook(self, body):
        """Post a notification via Kook incoming webhook."""

        # Prepare the API endpoint
        url = self.webhook_notify_url.format(key=self.token)

        # Use KMarkdown when the body is markdown; plain text otherwise
        kook_type = (
            KOOK_API_TYPE_KMARKDOWN
            if self.notify_format == NotifyFormat.MARKDOWN
            else KOOK_API_TYPE_TEXT
        )

        # Prepare the payload
        payload = {
            "type": kook_type,
            "content": body,
        }

        self.logger.debug(
            "Kook Webhook POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Kook Webhook Payload: %s", str(payload))

        # Throttle before the network request
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers={
                    "User-Agent": self.app_id,
                    "Content-Type": "application/json",
                },
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # Failed
                status_str = NotifyKook.http_response_code_lookup(
                    r.status_code, KOOK_HTTP_ERROR_MAP
                )
                self.logger.warning(
                    "Failed to send Kook webhook notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug("Response Details:\r\n%s", r.content)
                return False

            # Check for API-level error in the JSON response
            try:
                content = loads(r.content) or {}

            except (AttributeError, TypeError, ValueError):
                content = {}

            if content.get("code", 0) != 0:
                self.logger.warning(
                    "Failed to send Kook webhook notification:"
                    " code=%s, message=%s.",
                    content.get("code"),
                    content.get("message", "Unknown"),
                )
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending"
                " Kook webhook notification."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        self.logger.info("Sent Kook webhook notification.")
        return True

    def _send_bot(self, body, attach=None):
        """Post a notification via Kook Bot API to channels and DM users."""

        # No targets means nothing to send
        if not self.channels and not self.dm_users:
            self.logger.warning(
                "Kook: no targets specified; nothing to notify."
            )
            return False

        # Use KMarkdown when the body is markdown; plain text otherwise
        kook_type = (
            KOOK_API_TYPE_KMARKDOWN
            if self.notify_format == NotifyFormat.MARKDOWN
            else KOOK_API_TYPE_TEXT
        )

        # Prepare the authorization header
        headers = {
            "User-Agent": self.app_id,
            "Authorization": f"Bot {self.token}",
            "Content-Type": "application/json",
        }

        # Track overall success
        has_error = False

        # Build the combined target list: (url, target_id) pairs
        targets = [(self.notify_url, ch) for ch in self.channels] + [
            (self.dm_url, uid) for uid in self.dm_users
        ]

        for endpoint, target_id in targets:
            # Prepare the message payload for this target
            payload = {
                "type": kook_type,
                "target_id": target_id,
                "content": body,
            }

            self.logger.debug(
                "Kook Bot POST URL: %s (cert_verify=%s)",
                endpoint,
                self.verify_certificate,
            )
            self.logger.debug("Kook Bot Payload: %s", str(payload))

            # Throttle before each network request
            self.throttle()

            try:
                r = requests.post(
                    endpoint,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code != requests.codes.ok:
                    status_str = NotifyKook.http_response_code_lookup(
                        r.status_code, KOOK_HTTP_ERROR_MAP
                    )
                    self.logger.warning(
                        "Failed to send Kook Bot notification to"
                        " %s: %s%serror=%s.",
                        target_id,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                    self.logger.debug("Response Details:\r\n%s", r.content)
                    has_error = True
                    continue

                # Check API-level error code
                try:
                    content = loads(r.content) or {}

                except (AttributeError, TypeError, ValueError):
                    content = {}

                if content.get("code", 0) != 0:
                    self.logger.warning(
                        "Failed to send Kook Bot notification to"
                        " %s: code=%s, message=%s.",
                        target_id,
                        content.get("code"),
                        content.get("message", "Unknown"),
                    )
                    has_error = True
                    continue

                self.logger.info(
                    "Sent Kook Bot notification to %s.", target_id
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Kook Bot"
                    " notification to %s.",
                    target_id,
                )
                self.logger.debug("Socket Exception: %s", str(e))
                has_error = True
                continue

        # Handle file attachments after the text message is sent
        if attach and self.attachment_support and not has_error:
            for attachment in attach:
                # Upload each attachment to the Kook CDN and post a
                # follow-up message per target referencing the returned URL
                cdn_url = self._upload(attachment)
                if cdn_url is None:
                    # Upload failed; abort attachments for this send
                    return False

                # Determine the Kook type for the attachment message
                attach_type = (
                    KOOK_API_TYPE_IMAGE
                    if attachment.mimetype.startswith("image/")
                    else KOOK_API_TYPE_FILE
                )

                for endpoint, target_id in targets:
                    # Prepare the attachment message payload
                    payload = {
                        "type": attach_type,
                        "target_id": target_id,
                        "content": cdn_url,
                    }

                    self.logger.debug(
                        "Kook Bot Attachment POST URL: %s (cert_verify=%s)",
                        endpoint,
                        self.verify_certificate,
                    )
                    self.logger.debug(
                        "Kook Bot Attachment Payload: %s", str(payload)
                    )

                    # Throttle before each attachment post
                    self.throttle()

                    try:
                        r = requests.post(
                            endpoint,
                            data=dumps(payload),
                            headers=headers,
                            verify=self.verify_certificate,
                            timeout=self.request_timeout,
                            allow_redirects=self.redirects,
                        )

                        if r.status_code != requests.codes.ok:
                            status_str = NotifyKook.http_response_code_lookup(
                                r.status_code, KOOK_HTTP_ERROR_MAP
                            )
                            self.logger.warning(
                                "Failed to post Kook attachment to"
                                " %s: %s%serror=%s.",
                                target_id,
                                status_str,
                                ", " if status_str else "",
                                r.status_code,
                            )
                            self.logger.debug(
                                "Response Details:\r\n%s", r.content
                            )
                            has_error = True
                            continue

                        # Check API-level error code in the attachment response
                        try:
                            content = loads(r.content) or {}

                        except (AttributeError, TypeError, ValueError):
                            content = {}

                        if content.get("code", 0) != 0:
                            self.logger.warning(
                                "Failed to post Kook attachment to"
                                " %s: code=%s, message=%s.",
                                target_id,
                                content.get("code"),
                                content.get("message", "Unknown"),
                            )
                            has_error = True

                    except requests.RequestException as e:
                        self.logger.warning(
                            "A Connection error occurred posting"
                            " Kook attachment to %s.",
                            target_id,
                        )
                        self.logger.debug("Socket Exception: %s", str(e))
                        has_error = True

        return not has_error

    def _upload(self, attachment):
        """Upload a file to the Kook CDN and return the CDN URL.

        Returns None on any failure.
        """

        # Guard 1: verify the attachment is accessible before opening it
        if not attachment:
            self.logger.warning(
                "Could not access Kook attachment %s.",
                attachment.url(privacy=True),
            )
            return None

        # Prepare the file tuple; handle open errors explicitly
        files = None
        try:
            # Guard 2: OSError is caught in the except below
            files = {
                "file": (
                    attachment.name or "attachment.dat",
                    attachment.open(),
                    attachment.mimetype,
                ),
            }

            self.logger.debug(
                "Kook CDN Upload URL: %s (cert_verify=%s)",
                self.asset_url,
                self.verify_certificate,
            )

            # Throttle before the network request
            self.throttle()

            r = requests.post(
                self.asset_url,
                headers={
                    "User-Agent": self.app_id,
                    "Authorization": f"Bot {self.token}",
                },
                files=files,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                status_str = NotifyKook.http_response_code_lookup(
                    r.status_code, KOOK_HTTP_ERROR_MAP
                )
                self.logger.warning(
                    "Failed to upload Kook attachment: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )
                self.logger.debug("Response Details:\r\n%s", r.content)
                return None

            # Parse the CDN URL from the response body
            try:
                content = loads(r.content) or {}

            except (AttributeError, TypeError, ValueError):
                content = {}

            cdn_url = content.get("data", {}).get("url")
            if not cdn_url:
                self.logger.warning("Kook CDN upload returned no URL.")
                return None

            self.logger.debug("Kook CDN upload succeeded: %s", cdn_url)
            return cdn_url

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred uploading Kook attachment."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return None

        except OSError as e:
            self.logger.warning(
                "An I/O error occurred while reading Kook attachment %s.",
                attachment.name or "attachment",
            )
            self.logger.debug("I/O Exception: %s", str(e))
            return None

        finally:
            # Guard 3: always close the file handle
            if files:
                files["file"][1].close()

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique."""
        return (self.secure_protocol, self.mode, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Collect optional query parameters
        params = {}

        # Include mode only when non-default (webhook)
        if self.mode != KookMode.BOT:
            params["mode"] = self.mode

        # Append standard Apprise URL parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Reconstruct the targets list from channels and DM users
        all_targets = list(self.channels) + [
            f"{KOOK_DM_PREFIX}{uid}" for uid in self.dm_users
        ]
        # Preserve invalid targets so they survive a round-trip
        all_targets += self._invalid_targets

        if all_targets:
            return "{schema}://{token}/{targets}/?{params}".format(
                schema=self.secure_protocol,
                token=self.pprint(self.token, privacy, safe=""),
                targets="/".join(
                    NotifyKook.quote(t, safe="@") for t in all_targets
                ),
                params=NotifyKook.urlencode(params),
            )

        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyKook.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The host field holds the bot token / webhook key
        results["token"] = NotifyKook.unquote(results["host"])

        # Allow ?token= to override the host-supplied token
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyKook.unquote(results["qsd"]["token"])

        # Collect path entries as targets
        results["targets"] = NotifyKook.split_path(results["fullpath"])

        # Allow ?to= as a comma-separated alias for targets
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyKook.parse_list(results["qsd"]["to"])

        # Extract operating mode
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyKook.unquote(results["qsd"]["mode"])

        return results

    @staticmethod
    def parse_native_url(url):
        """Support pasting full Kook incoming webhook URLs directly.

        Supports: https://www.kookapp.cn/api/v3/incoming/{key}
        """
        result = re.match(
            r"^https?://www\.kookapp\.cn/api/v3/incoming/"
            r"(?P<key>[A-Za-z0-9_=+-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )
        if result:
            return NotifyKook.parse_url(
                "{schema}://{key}/?mode=webhook{extra}".format(
                    schema=NotifyKook.secure_protocol,
                    key=result.group("key"),
                    extra=(
                        "&" + result.group("params").lstrip("?")
                        if result.group("params")
                        else ""
                    ),
                )
            )

        return None
