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

# Great sources
# - https://github.com/matrix-org/matrix-python-sdk
# - https://github.com/matrix-org/synapse/blob/master/docs/reverse_proxy.rst
#
# End-to-End Encryption references:
# - https://spec.matrix.org/v1.11/client-server-api/
#   #end-to-end-encryption
# - https://gitlab.matrix.org/matrix-org/olm/-/blob/master/docs/olm.md
# - https://gitlab.matrix.org/matrix-org/olm/-/blob/master/docs/megolm.md
#
import contextlib
from json import dumps, loads
import re
from time import time
import uuid

from markdown import markdown
import requests

from ...common import (
    NotifyFormat,
    NotifyImageSize,
    NotifyType,
    PersistentStoreMode,
)
from ...exception import AppriseException
from ...locale import gettext_lazy as _
from ...url import PrivacyMode
from ...utils.parse import (
    is_hostname,
    parse_bool,
    parse_list,
    validate_regex,
)
from ..base import NotifyBase
from .e2ee import (
    MATRIX_E2EE_SUPPORT,
    MatrixMegOlmSession,
    MatrixOlmAccount,
    encrypt_attachment,
    verify_device_keys,
    verify_signed_otk,
)

# Define default path
MATRIX_V1_WEBHOOK_PATH = "/api/v1/matrix/hook"
MATRIX_V2_API_PATH = "/_matrix/client/r0"
MATRIX_V3_API_PATH = "/_matrix/client/v3"
MATRIX_V3_MEDIA_PATH = "/_matrix/media/v3"
MATRIX_V2_MEDIA_PATH = "/_matrix/media/r0"


class MatrixDiscoveryException(AppriseException):
    """Apprise Matrix Exception Class."""


# Extend HTTP Error Messages
MATRIX_HTTP_ERROR_MAP = {
    403: "Unauthorized - Invalid Token.",
    429: "Rate limit imposed; wait 2s and try again",
}

# Matrix Room Syntax
IS_ROOM_ALIAS = re.compile(
    r"^\s*(#|%23)?(?P<room>[A-Za-z0-9._=-]+)((:|%3A)"
    r"(?P<home_server>[A-Za-z0-9.-]+))?\s*$",
    re.I,
)

# Room ID MUST start with an exclamation to avoid ambiguity
IS_ROOM_ID = re.compile(
    r"^\s*(!|&#33;|%21)(?P<room>[A-Za-z0-9._=-]+)((:|%3A)"
    r"(?P<home_server>[A-Za-z0-9.-]+))?\s*$",
    re.I,
)

# Matrix User ID (for DM targets); must start with @
IS_USER = re.compile(
    r"^\s*(@|%40)(?P<user>[A-Za-z0-9._=+/-]+)((:|%3A)"
    r"(?P<home_server>[A-Za-z0-9.-]+))?\s*$",
    re.I,
)


# Matrix is_image check
IS_IMAGE = re.compile(r"^image/.*", re.I)


class MatrixMessageType:
    """The Matrix Message types."""

    TEXT = "text"
    NOTICE = "notice"


# matrix message types are placed into this list for validation purposes
MATRIX_MESSAGE_TYPES = (
    MatrixMessageType.TEXT,
    MatrixMessageType.NOTICE,
)


class MatrixVersion:
    # Version 2
    V2 = "2"

    # Version 3
    V3 = "3"


# webhook modes are placed into this list for validation purposes
MATRIX_VERSIONS = (
    MatrixVersion.V2,
    MatrixVersion.V3,
)


class MatrixWebhookMode:
    # Webhook Mode is disabled
    DISABLED = "off"

    # The default webhook mode is to just be set to Matrix
    MATRIX = "matrix"

    # Support the slack webhook plugin
    SLACK = "slack"

    # Support the t2bot webhook plugin
    T2BOT = "t2bot"


# webhook modes are placed into this list for validation purposes
MATRIX_WEBHOOK_MODES = (
    MatrixWebhookMode.DISABLED,
    MatrixWebhookMode.MATRIX,
    MatrixWebhookMode.SLACK,
    MatrixWebhookMode.T2BOT,
)


class NotifyMatrix(NotifyBase):
    """A wrapper for Matrix Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Matrix"

    # The services URL
    service_url = "https://matrix.org/"

    # The default protocol
    protocol = "matrix"

    # The default secure protocol
    secure_protocol = "matrixs"

    # Support Attachments
    attachment_support = True

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/matrix/"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_32

    # The maximum allowable characters allowed in the body per message
    # https://spec.matrix.org/v1.6/client-server-api/#size-limits
    # The complete event MUST NOT be larger than 65536 bytes, when formatted
    # with the federation event format, including any signatures, and encoded
    # as Canonical JSON.
    #
    # To gracefully allow for some overhead' we'll define a max body length
    # of just slighty lower then the limit of the full message itself.
    body_maxlen = 65000

    # Throttle a wee-bit to avoid thrashing
    request_rate_per_sec = 0.5

    # How many retry attempts we'll make in the event the server asks us to
    # throttle back.
    default_retries = 2

    # The number of micro seconds to wait if we get a 429 error code and
    # the server doesn't remind us how long we should wait for
    default_wait_ms = 1000

    # Our default is to no not use persistent storage beyond in-memory
    # reference
    storage_mode = PersistentStoreMode.AUTO

    # Keep our cache for 20 days
    default_cache_expiry_sec = 60 * 60 * 24 * 20

    # Used for server discovery
    discovery_base_key = "__discovery_base"
    discovery_identity_key = "__discovery_identity"

    # Defines how long we cache our discovery for
    discovery_cache_length_sec = 86400

    # Define object templates
    templates = (
        # Targets are ignored when using t2bot mode; only a token is required
        "{schema}://{token}",
        "{schema}://{user}@{token}",
        # Matrix Server
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
        "{schema}://{token}@{host}/{targets}",
        "{schema}://{token}@{host}:{port}/{targets}",
        # Webhook mode
        "{schema}://{user}:{token}@{host}/{targets}",
        "{schema}://{user}:{token}@{host}:{port}/{targets}",
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
                "name": _("Access Token"),
                "type": "string",
                "private": True,
                "map_to": "password",
                "required": True,
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "target_room_id": {
                "name": _("Target Room ID"),
                "type": "string",
                "prefix": "!",
                "map_to": "targets",
            },
            "target_room_alias": {
                "name": _("Target Room Alias"),
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
                "default": False,
                "map_to": "include_image",
            },
            "discovery": {
                "name": _("Server Discovery"),
                "type": "bool",
                "default": True,
            },
            "hsreq": {
                "name": _("Force Home Server on Room IDs"),
                "type": "bool",
                "default": True,
            },
            "mode": {
                "name": _("Webhook Mode"),
                "type": "choice:string",
                "values": MATRIX_WEBHOOK_MODES,
                "default": MatrixWebhookMode.DISABLED,
            },
            "version": {
                "name": _("Matrix API Verion"),
                "type": "choice:string",
                "values": MATRIX_VERSIONS,
                "default": MatrixVersion.V3,
            },
            "msgtype": {
                "name": _("Message Type"),
                "type": "choice:string",
                "values": MATRIX_MESSAGE_TYPES,
                "default": MatrixMessageType.TEXT,
            },
            "e2ee": {
                "name": _("End-to-End Encryption"),
                "type": "bool",
                "default": True,
            },
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
        targets=None,
        mode=None,
        msgtype=None,
        version=None,
        include_image=None,
        discovery=None,
        hsreq=None,
        e2ee=None,
        **kwargs,
    ):
        """Initialize Matrix Object."""
        super().__init__(**kwargs)

        # Prepare a list of rooms to connect and notify; separate
        # @user DM targets from room identifiers.
        self.rooms = []
        self.users = []
        for _target in parse_list(targets):
            if IS_USER.match(_target):
                self.users.append(_target)
            else:
                self.rooms.append(_target)

        # our home server gets populated after a login/registration
        self.home_server = None

        # our user_id gets populated after a login/registration
        self.user_id = None

        # This gets initialized after a login/registration
        self.access_token = None

        # Our device ID assigned by the Matrix server during login
        self.device_id = None

        # This gets incremented for each request made against the v3 API
        self.transaction_id = 0

        # Lazy-initialized E2EE account (MatrixOlmAccount or None)
        self._e2ee_account = None

        # Place an image inline with the message body
        self.include_image = (
            self.template_args["image"]["default"]
            if include_image is None
            else include_image
        )

        # Prepare Delegate Server Lookup Check
        self.discovery = (
            self.template_args["discovery"]["default"]
            if discovery is None
            else discovery
        )

        # When enabled, room IDs missing a ':homeserver' segment will
        # be treated as legacy identifiers and automatically suffixed
        # with the authenticated homeserver.
        self.hsreq = (
            self.template_args["hsreq"]["default"] if hsreq is None else hsreq
        )

        # End-to-end encryption (server mode only; requires cryptography)
        self.e2ee = (
            self.template_args["e2ee"]["default"]
            if e2ee is None
            else parse_bool(e2ee)
        )

        # Setup our mode
        self.mode = (
            self.template_args["mode"]["default"]
            if not isinstance(mode, str)
            else mode.lower()
        )
        if self.mode and self.mode not in MATRIX_WEBHOOK_MODES:
            msg = f"The mode specified ({mode}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Setup our version
        self.version = (
            self.template_args["version"]["default"]
            if not isinstance(version, str)
            else version
        )
        if self.version not in MATRIX_VERSIONS:
            msg = f"The version specified ({version}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Setup our message type
        self.msgtype = (
            self.template_args["msgtype"]["default"]
            if not isinstance(msgtype, str)
            else msgtype.lower()
        )
        if self.msgtype and self.msgtype not in MATRIX_MESSAGE_TYPES:
            msg = f"The msgtype specified ({msgtype}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        if self.mode == MatrixWebhookMode.T2BOT:
            # t2bot configuration requires that a webhook id is specified
            self.access_token = validate_regex(
                self.password, r"^[a-z0-9]{64}$", "i"
            )
            if not self.access_token:
                msg = (
                    "An invalid T2Bot/Matrix Webhook ID "
                    f"({self.password}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        elif not is_hostname(self.host):
            msg = f"An invalid Matrix Hostname ({self.host}) was specified"
            self.logger.warning(msg)
            raise TypeError(msg)

        else:
            # Verify port if specified
            if self.port is not None and not (
                isinstance(self.port, int)
                and self.port >= self.template_tokens["port"]["min"]
                and self.port <= self.template_tokens["port"]["max"]
            ):
                msg = f"An invalid Matrix Port ({self.port}) was specified"
                self.logger.warning(msg)
                raise TypeError(msg)

        if self.mode != MatrixWebhookMode.DISABLED:
            # Discovery only works when we're not using webhooks
            self.discovery = False

        #
        # Initialize from cache if present
        #
        if self.mode != MatrixWebhookMode.T2BOT:
            # our home server gets populated after a login/registration
            self.home_server = self.store.get("home_server")

            # our user_id gets populated after a login/registration
            self.user_id = self.store.get("user_id")

            # This gets initialized after a login/registration
            self.access_token = self.store.get("access_token")

            # Device ID assigned by server
            self.device_id = self.store.get("device_id")

        # This gets incremented for each request made against the v3 API
        self.transaction_id = (
            0 if not self.access_token else self.store.get("transaction_id", 0)
        )

        # Restore E2EE account from store if available
        if self.e2ee and MATRIX_E2EE_SUPPORT:
            acct_data = self.store.get("e2ee_account")
            if acct_data:
                with contextlib.suppress(Exception):
                    self._e2ee_account = MatrixOlmAccount.from_dict(acct_data)

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Matrix Notification."""

        # Call the _send_ function applicable to whatever mode we're in
        # - calls _send_webhook_notification if the mode variable is set
        # - calls _send_server_notification if the mode variable is not set
        return getattr(
            self,
            "_send_{}_notification".format(
                "webhook"
                if self.mode != MatrixWebhookMode.DISABLED
                else "server"
            ),
        )(body=body, title=title, notify_type=notify_type, **kwargs)

    def _send_webhook_notification(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """Perform Matrix Notification as a webhook."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        if self.mode != MatrixWebhookMode.T2BOT:
            # Acquire our access token from our URL
            access_token = self.password if self.password else self.user

            # Prepare our URL
            url = "{schema}://{hostname}{port}{webhook_path}/{token}".format(
                schema="https" if self.secure else "http",
                hostname=self.host,
                port=("" if not self.port else f":{self.port}"),
                webhook_path=MATRIX_V1_WEBHOOK_PATH,
                token=access_token,
            )

        else:
            #
            # t2bot Setup
            #

            # Prepare our URL
            url = (
                "https://webhooks.t2bot.io/api/v1/matrix/hook/"
                f"{self.access_token}"
            )

        # Retrieve our payload
        payload = getattr(self, f"_{self.mode}_webhook_payload")(
            body=body, title=title, notify_type=notify_type, **kwargs
        )

        self.logger.debug(
            "Matrix POST URL: {} (cert_verify={!r})".format(
                url, self.verify_certificate
            )
        )
        self.logger.debug(f"Matrix Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyMatrix.http_response_code_lookup(
                    r.status_code, MATRIX_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Matrix notification: {}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r",
                    (r.content or b"")[:2000],
                )

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Matrix notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Matrix notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            # Return; we're done
            return False

        return True

    def _slack_webhook_payload(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """Format the payload for a Slack based message."""

        if not hasattr(self, "_re_slack_formatting_rules"):
            # Prepare some one-time slack formatting variables

            self._re_slack_formatting_map = {
                # New lines must become the string version
                r"\r\*\n": "\\n",
                # Escape other special characters
                r"&": "&amp;",
                r"<": "&lt;",
                r">": "&gt;",
            }

            # Iterate over above list and store content accordingly
            self._re_slack_formatting_rules = re.compile(
                r"(" + "|".join(self._re_slack_formatting_map.keys()) + r")",
                re.IGNORECASE,
            )

        # Perform Formatting
        title = self._re_slack_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_slack_formatting_map[x.group()],
            title,
        )

        body = self._re_slack_formatting_rules.sub(  # pragma: no branch
            lambda x: self._re_slack_formatting_map[x.group()],
            body,
        )

        # prepare JSON Object
        payload = {
            "username": self.user if self.user else self.app_id,
            # Use Markdown language
            "mrkdwn": self.notify_format == NotifyFormat.MARKDOWN,
            "attachments": [
                {
                    "title": title,
                    "text": body,
                    "color": self.color(notify_type),
                    "ts": time(),
                    "footer": self.app_id,
                }
            ],
        }

        return payload

    def _matrix_webhook_payload(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """Format the payload for a Matrix based message."""

        payload = {
            "displayName": self.user if self.user else self.app_id,
            "format": (
                "plain" if self.notify_format == NotifyFormat.TEXT else "html"
            ),
            "text": "",
        }

        if self.notify_format == NotifyFormat.HTML:
            payload["text"] = "{title}{body}".format(
                title=(
                    ""
                    if not title
                    else f"<h1>{NotifyMatrix.escape_html(title)}</h1>"
                ),
                body=body,
            )

        elif self.notify_format == NotifyFormat.MARKDOWN:
            payload["text"] = "{title}{body}".format(
                title=(
                    ""
                    if not title
                    else f"<h1>{NotifyMatrix.escape_html(title)}</h1>"
                ),
                body=markdown(body),
            )

        else:  # NotifyFormat.TEXT
            payload["text"] = body if not title else f"{title}\r\n{body}"

        return payload

    def _t2bot_webhook_payload(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """Format the payload for a T2Bot Matrix based messages."""

        # Retrieve our payload
        payload = self._matrix_webhook_payload(
            body=body, title=title, notify_type=notify_type, **kwargs
        )

        # Acquire our image url if we're configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )

        if image_url:
            # t2bot can take an avatarUrl Entry
            payload["avatarUrl"] = image_url

        return payload

    def _send_server_notification(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Direct Matrix Server Notification (no webhook)"""

        if self.access_token is None and self.password and not self.user:
            self.access_token = self.password
            self.transaction_id = uuid.uuid4()

        if (
            self.access_token is None
            and not self._login()
            and not self._register()
        ):
            # We need to register
            return False

        # When authenticating with a raw access token (no username) the
        # login flow is skipped, so user_id and device_id are never returned
        # by the server.  Resolve them via /account/whoami so that E2EE key
        # upload and DM room lookup (m.direct) work correctly.
        if not self.user and (not self.user_id or not self.device_id):
            self._whoami()

        if len(self.rooms) == 0 and not self.users:
            # Attempt to retrieve a list of already joined channels
            self.rooms = self._joined_rooms()

            if len(self.rooms) == 0:
                # Nothing to notify
                self.logger.warning(
                    "There were no Matrix rooms specified to notify."
                )
                return False

        # Create a copy of our rooms to join and message
        rooms = list(self.rooms)

        # Initialize our error tracking
        has_error = False

        # Resolve DM user targets (@user) to room IDs
        for _user in self.users:
            dm_room_id = self._dm_room_find_or_create(_user)
            if dm_room_id:
                rooms.append(dm_room_id)
            else:
                self.logger.warning(
                    "Could not find or create a DM room for Matrix user %s.",
                    _user,
                )
                has_error = True

        # E2EE setup (once per send call, not per room).
        # e2ee_capable means prerequisites are met; encryption is still
        # decided per-room based on whether that room requires E2EE.
        e2ee_capable = False
        if self.e2ee and self.secure and MATRIX_E2EE_SUPPORT:
            e2ee_capable = self._e2ee_setup()
            if not e2ee_capable:
                self.logger.warning(
                    "Matrix E2EE setup failed; "
                    "messages will be sent unencrypted."
                )

        # Plaintext attachment payloads for unencrypted rooms.
        # Lazy-initialized on the first unencrypted room so that purely
        # E2EE setups never upload attachments in plaintext.
        attachments = None
        attachments_ready = False

        while len(rooms) > 0:
            # Get our room
            room = rooms.pop(0)

            # Get our room_id from our response
            room_id = self._room_join(room)
            if not room_id:
                # Notify our user about our failure
                self.logger.warning(f"Could not join Matrix room {room}.")

                # Mark our failure
                has_error = True
                continue

            if e2ee_capable and self._e2ee_room_encrypted(room_id):
                # E2EE path: encrypt message and any attachments
                if not self._e2ee_send_to_room(
                    room_id, body, title, notify_type
                ):
                    has_error = True
                    continue

                if attach and self.attachment_support:
                    session = self._e2ee_get_megolm(room_id)
                    for attachment in attach:
                        if not attachment:
                            has_error = True
                            break
                        if not self._e2ee_send_attachment(
                            attachment, room_id, session
                        ):
                            has_error = True
                continue

            # --- Unencrypted path (existing behaviour) ---

            # Upload attachments once; reuse content_uris for every
            # subsequent unencrypted room in this send call.
            if attach and self.attachment_support and not attachments_ready:
                attachments = self._send_attachments(attach)
                attachments_ready = True
                if attachments is False:
                    return False

            # Acquire our image url if we're configured to do so
            image_url = (
                None if not self.include_image else self.image_url(notify_type)
            )

            # Always use PUT with a transaction ID
            # (spec-compliant since 2015)
            path = "/rooms/{}/send/m.room.message/{}".format(
                NotifyMatrix.quote(room_id), self.transaction_id
            )

            if image_url and self.version == MatrixVersion.V2:
                # Define our payload
                image_payload = {
                    "msgtype": "m.image",
                    "url": image_url,
                    "body": f"{title if title else notify_type}",
                }

                # Post our content
                postokay, _, _ = self._fetch(
                    path, payload=image_payload, method="PUT"
                )
                if not postokay:
                    # Mark our failure
                    has_error = True
                    continue

                # Increment transaction ID so subsequent sends
                # don't reuse the same path
                if self.access_token != self.password:
                    self.transaction_id += 1
                    self.store.set(
                        "transaction_id",
                        self.transaction_id,
                        expires=self.default_cache_expiry_sec,
                    )
                    path = "/rooms/{}/send/m.room.message/{}".format(
                        NotifyMatrix.quote(room_id), self.transaction_id
                    )

            if attachments:
                for attachment in attachments:
                    attachment["room_id"] = room_id
                    attachment["type"] = "m.room.message"

                    postokay, _, _ = self._fetch(
                        path, payload=attachment, method="PUT"
                    )

                    # Increment the transaction ID to avoid future messages
                    # being recognized as retransmissions and ignored
                    if self.access_token != self.password:
                        self.transaction_id += 1
                        self.store.set(
                            "transaction_id",
                            self.transaction_id,
                            expires=self.default_cache_expiry_sec,
                        )
                        path = "/rooms/{}/send/m.room.message/{}".format(
                            NotifyMatrix.quote(room_id),
                            self.transaction_id,
                        )

                    if not postokay:
                        # Mark our failure
                        has_error = True
                        continue

            # Define our payload
            payload = {
                "msgtype": f"m.{self.msgtype}",
                "body": "{title}{body}".format(
                    title="" if not title else f"# {title}\r\n",
                    body=body,
                ),
            }

            # Update our payload advance formatting for the services that
            # support them.
            if self.notify_format == NotifyFormat.HTML:
                payload.update(
                    {
                        "format": "org.matrix.custom.html",
                        "formatted_body": "{title}{body}".format(
                            title=("" if not title else f"<h1>{title}</h1>"),
                            body=body,
                        ),
                    }
                )

            elif self.notify_format == NotifyFormat.MARKDOWN:
                title_ = (
                    ""
                    if not title
                    else (
                        "<h1>{}".format(
                            NotifyMatrix.escape_html(title, whitespace=False)
                        )
                        + "</h1>"
                    )
                )

                payload.update(
                    {
                        "format": "org.matrix.custom.html",
                        "formatted_body": "{title}{body}".format(
                            title=title_,
                            body=markdown(body),
                        ),
                    }
                )

            # Post our content
            postokay, _, _ = self._fetch(path, payload=payload, method="PUT")

            # Increment the transaction ID to avoid future messages being
            # recognized as retransmissions and ignored
            if self.access_token != self.password:
                self.transaction_id += 1
                self.store.set(
                    "transaction_id",
                    self.transaction_id,
                    expires=self.default_cache_expiry_sec,
                )

            if not postokay:
                # Notify our user
                self.logger.warning(
                    f"Could not send notification Matrix room {room}."
                )

                # Mark our failure
                has_error = True
                continue

        return not has_error

    def _send_attachments(self, attach):
        """Posts all of the provided attachments."""

        payloads = []

        for attachment in attach:
            if not attachment:
                # invalid attachment (bad file)
                return False

            if (
                not IS_IMAGE.match(attachment.mimetype)
                and self.version == MatrixVersion.V2
            ):
                # unsuppored at this time
                continue

            postokay, response, _ = self._fetch(
                "/upload", attachment=attachment
            )
            if not (postokay and isinstance(response, dict)):
                # Failed to perform upload
                return False

            # If we get here, we'll have a response that looks like:
            # {
            #     "content_uri": "mxc://example.com/a-unique-key"
            # }

            if self.version == MatrixVersion.V3:
                # Prepare our payload
                is_image = IS_IMAGE.match(attachment.mimetype)
                payloads.append(
                    {
                        "body": attachment.name,
                        "info": {
                            "mimetype": attachment.mimetype,
                            "size": len(attachment),
                        },
                        "msgtype": "m.image" if is_image else "m.file",
                        "url": response.get("content_uri"),
                    }
                )
                if not is_image:
                    # Setup `m.file'
                    payloads[-1]["filename"] = attachment.name

            else:
                # Prepare our payload
                payloads.append(
                    {
                        "info": {
                            "mimetype": attachment.mimetype,
                        },
                        "msgtype": "m.image",
                        "body": "tta.webp",
                        "url": response.get("content_uri"),
                    }
                )

        return payloads

    def _register(self):
        """Register with the service if possible."""

        # Prepare our Registration Payload. This will only work if
        # registration is enabled for the public
        payload = {
            "kind": "user",
            "auth": {"type": "m.login.dummy"},
        }

        # parameters
        params = {
            "kind": "user",
        }

        # If a user is not specified, one will be randomly generated for
        # you. If you do not specify a password, you will be unable to
        # login to the account if you forget the access_token.
        if self.user:
            payload["username"] = self.user

        if self.password:
            payload["password"] = self.password

        # Register
        postokay, response, _ = self._fetch(
            "/register", payload=payload, params=params
        )
        if not (postokay and isinstance(response, dict)):
            # Failed to register
            return False

        # Pull the response details
        self.access_token = response.get("access_token")
        self.home_server = response.get("home_server")
        self.user_id = response.get("user_id")
        self.device_id = response.get("device_id")

        self.store.set(
            "access_token",
            self.access_token,
            expires=self.default_cache_expiry_sec,
        )
        self.store.set(
            "home_server",
            self.home_server,
            expires=self.default_cache_expiry_sec,
        )
        self.store.set(
            "user_id", self.user_id, expires=self.default_cache_expiry_sec
        )
        if self.device_id:
            self.store.set(
                "device_id",
                self.device_id,
                expires=self.default_cache_expiry_sec,
            )

        if self.access_token is not None:
            # Store our token into our store
            self.logger.debug("Registered successfully with Matrix server.")
            return True

        return False

    def _login(self):
        """Acquires the matrix token required for making future requests.

        If we fail we return False, otherwise we return True
        """

        if self.access_token:
            # Login not required; silently skip-over
            return True

        if self.user and self.password:
            # Prepare our Authentication Payload
            if self.version == MatrixVersion.V3:
                payload = {
                    "type": "m.login.password",
                    "identifier": {
                        "type": "m.id.user",
                        "user": self.user,
                    },
                    "password": self.password,
                }

            else:
                payload = {
                    "type": "m.login.password",
                    "user": self.user,
                    "password": self.password,
                }

        else:
            # It's not possible to register since we need these 2 values
            # to make the action possible.
            self.logger.warning(
                "Failed to login to Matrix server: "
                "token or user/pass combo is missing."
            )
            return False

        # Build our URL
        postokay, response, _ = self._fetch("/login", payload=payload)
        if not (postokay and isinstance(response, dict)):
            # Failed to login
            return False

        # Pull the response details
        self.access_token = response.get("access_token")
        self.home_server = response.get("home_server")
        self.user_id = response.get("user_id")
        self.device_id = response.get("device_id")

        if not self.access_token:
            return False

        self.logger.debug("Authenticated successfully with Matrix server.")

        # Store our token into our store
        self.store.set(
            "access_token",
            self.access_token,
            expires=self.default_cache_expiry_sec,
        )
        self.store.set(
            "home_server",
            self.home_server,
            expires=self.default_cache_expiry_sec,
        )
        self.store.set(
            "user_id", self.user_id, expires=self.default_cache_expiry_sec
        )
        if self.device_id:
            self.store.set(
                "device_id",
                self.device_id,
                expires=self.default_cache_expiry_sec,
            )

        return True

    def _whoami(self):
        """Resolve user_id, device_id, and home_server via GET /account/whoami.

        Called when a raw access token is supplied (no login flow), so
        the server never returned these identifiers directly.  Results
        are cached in the persistent store for future calls.

        Returns True on success, False otherwise.
        """
        ok, response, _ = self._fetch(
            "/account/whoami", payload=None, method="GET"
        )
        if not (ok and isinstance(response, dict)):
            return False

        self.user_id = response.get("user_id") or self.user_id
        self.device_id = response.get("device_id") or self.device_id

        # Extract home_server from user_id (@localpart:homeserver) so that
        # DM targets without an explicit homeserver resolve correctly.
        if self.user_id and not self.home_server:
            parts = self.user_id.split(":", 1)
            if len(parts) == 2:
                self.home_server = parts[1]

        if self.user_id:
            self.store.set(
                "user_id",
                self.user_id,
                expires=self.default_cache_expiry_sec,
            )
        if self.device_id:
            self.store.set(
                "device_id",
                self.device_id,
                expires=self.default_cache_expiry_sec,
            )
        if self.home_server:
            self.store.set(
                "home_server",
                self.home_server,
                expires=self.default_cache_expiry_sec,
            )
        return True

    def _logout(self):
        """Relinquishes token from remote server."""

        if not self.access_token:
            # Login not required; silently skip-over
            return True

        # Prepare our Registration Payload
        payload = {}

        # Expire our token
        postokay, response, _ = self._fetch("/logout", payload=payload)
        if not postokay and response.get("errcode") != "M_UNKNOWN_TOKEN":
            # If we get here, the token was declared as having already
            # been expired.  The response looks like this:
            # {
            #    u'errcode': u'M_UNKNOWN_TOKEN',
            #    u'error': u'Access Token unknown or expired',
            # }
            #
            # In this case it's okay to safely return True because
            # we're logged out in this case.
            return False

        # else: The response object looks like this if we were successful:
        #  {}

        # Pull the response details
        self.access_token = None
        self.home_server = None
        self.user_id = None
        self.device_id = None
        self._e2ee_account = None

        # clear our tokens (including E2EE upload flag so it re-uploads
        # after a fresh login)
        self.store.clear(
            "access_token",
            "home_server",
            "user_id",
            "transaction_id",
            "device_id",
            "e2ee_keys_uploaded",
        )

        self.logger.debug("Unauthenticated successfully with Matrix server.")

        return True

    def _room_join(self, room):
        """Joins a matrix room if we're not already in it.

        Otherwise it attempts to create it if it doesn't exist and
        always returns the room_id if it was successful, otherwise it
        returns None
        """

        if not self.access_token:
            # We can't join a room if we're not logged in
            return None

        if not isinstance(room, str):
            # Not a supported string
            return None

        # Prepare our Join Payload
        payload = {}

        # Check if it's a room id...
        result = IS_ROOM_ID.match(room)
        if result:
            room_token = result.group("room")
            explicit_home_server = result.group("home_server")

            # Determine the homeserver context (used for cache metadata)
            home_server = (
                explicit_home_server
                if explicit_home_server
                else self.home_server
            )

            # When hsreq is enabled (legacy behaviour), we always require
            # a ':homeserver' segment on room IDs. Otherwise, we honour
            # exactly what the caller provided and do not synthesise a
            # homeserver when it was not specified.
            cache_key = f"!{room_token}:{home_server}"
            if explicit_home_server or self.hsreq:
                room_id = cache_key
            else:
                room_id = f"!{room_token}"

            # Check our cache for speed:
            try:
                return self.store[cache_key]["id"]

            except KeyError:
                pass

            # Build our URL
            path = f"/join/{NotifyMatrix.quote(room_id)}"

            # Attempt to join the channel
            postokay, response, _status_code = self._fetch(
                path, payload=payload
            )
            if not postokay:
                return None

            # Prefer the server-provided room_id if one was returned,
            # otherwise fall back to whatever we joined with.
            joined_id = (
                response.get("room_id") if isinstance(response, dict) else None
            ) or room_id

            # Cache mapping for faster future lookups.
            self.store.set(
                cache_key,
                {
                    "id": joined_id,
                    "home_server": home_server,
                },
            )

            return joined_id

        # Try to see if it's an alias then...
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # There is nothing else it could be
            self.logger.warning(
                f"Ignoring illegally formed room {room} "
                "from Matrix server list."
            )
            return None

        # If we reach here, we're dealing with a channel alias
        home_server = (
            self.home_server
            if not result.group("home_server")
            else result.group("home_server")
        )

        # tidy our room (alias) identifier
        room = "#{}:{}".format(result.group("room"), home_server)

        # Check our cache for speed:
        try:
            # We're done as we've already joined the channel
            return self.store[room]["id"]

        except KeyError:
            # No worries, we'll try to acquire the info
            pass

        # If we reach here, we need to join the channel

        # Build our URL
        path = f"/join/{NotifyMatrix.quote(room)}"

        # Attempt to join the channel
        postokay, response, status_code = self._fetch(path, payload=payload)
        if postokay:
            # Cache our entry for fast access later
            self.store.set(
                room,
                {
                    "id": response.get("room_id"),
                    "home_server": home_server,
                },
            )

            return response.get("room_id")

        # Only attempt to create a room when the server clearly indicates
        # the alias does not exist. A join can fail for many reasons, such
        # as invite required, auth failure, or permissions, and in those
        # cases auto-creating is both noisy and incorrect.
        if (
            status_code == requests.codes.not_found
            or response.get("errcode") == "M_NOT_FOUND"
        ):
            return self._room_create(room)

        self.logger.warning(
            "Could not join Matrix room alias %s (error=%s). "
            "If this is a private room, ensure the user is invited or "
            "already joined, or specify the room_id (!...).",
            room,
            status_code,
        )
        return None

    def _room_create(self, room):
        """Creates a matrix room and return it's room_id if successful
        otherwise None is returned."""
        if not self.access_token:
            # We can't create a room if we're not logged in
            return None

        if not isinstance(room, str):
            # Not a supported string
            return None

        # Build our room if we have to:
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # Illegally formed room
            return None

        # Our home_server
        home_server = (
            result.group("home_server")
            if result.group("home_server")
            else self.home_server
        )

        # update our room details
        room = "#{}:{}".format(result.group("room"), home_server)

        # Prepare our Create Payload
        payload = {
            "room_alias_name": result.group("room"),
            # Set our channel name
            "name": "#{} - {}".format(result.group("room"), self.app_desc),
            # hide the room by default; let the user open it up if they
            # wish to others.
            "visibility": "private",
            "preset": "trusted_private_chat",
        }

        postokay, response, _ = self._fetch("/createRoom", payload=payload)
        if not postokay:
            # Failed to create channel
            # Typical responses:
            #   - {u'errcode': u'M_ROOM_IN_USE',
            #      u'error': u'Room alias already taken'}
            #   - {u'errcode': u'M_UNKNOWN',
            #      u'error': u'Internal server error'}
            if response and response.get("errcode") == "M_ROOM_IN_USE":
                return self._room_id(room)
            return None

        # Cache our entry for fast access later
        self.store.set(
            response.get("room_alias"),
            {
                "id": response.get("room_id"),
                "home_server": home_server,
            },
        )

        return response.get("room_id")

    def _joined_rooms(self):
        """Returns a list of the current rooms the logged in user is a
        part of."""

        if not self.access_token:
            # No list is possible
            return []

        postokay, response, _ = self._fetch(
            "/joined_rooms", payload=None, method="GET"
        )
        if not postokay:
            # Failed to retrieve listings
            return []

        # Return our list of rooms
        return response.get("joined_rooms", [])

    def _room_id(self, room):
        """Get room id from its alias.
        Args:
            room (str): The room alias name.

        Returns:
            returns the room id if it can, otherwise it returns None
        """

        if not self.access_token:
            # We can't get a room id if we're not logged in
            return None

        if not isinstance(room, str):
            # Not a supported string
            return None

        # Build our room if we have to:
        result = IS_ROOM_ALIAS.match(room)
        if not result:
            # Illegally formed room
            return None

        # Our home_server
        home_server = (
            result.group("home_server")
            if result.group("home_server")
            else self.home_server
        )

        # update our room details
        room = "#{}:{}".format(result.group("room"), home_server)

        # Make our request
        postokay, response, _ = self._fetch(
            f"/directory/room/{NotifyMatrix.quote(room)}",
            payload=None,
            method="GET",
        )

        if postokay:
            return response.get("room_id")

        return None

    def _fetch(
        self,
        path,
        payload=None,
        params=None,
        attachment=None,
        method="POST",
        url_override=None,
    ):
        """Wrapper to request.post() to manage it's response better and
        make the send() function cleaner and easier to maintain.

        This function always returns a 3-tuple:
            (success, response, status_code)

        The response is a dict when JSON is parseable, otherwise an empty
        dict. The status_code defaults to 500 on local failures.
        """

        # Define our headers
        if params is None:
            params = {}
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.access_token is not None:
            headers["Authorization"] = f"Bearer {self.access_token}"

        # Server Discovery / Well-known URI
        if url_override:
            url = url_override

        else:
            try:
                url = self.base_url

            except MatrixDiscoveryException:
                # Discovery failed; we're done
                return (False, {}, requests.codes.internal_server_error)

        # Default return status code
        status_code = requests.codes.internal_server_error

        if path == "/upload":
            if self.version == MatrixVersion.V3:
                url += MATRIX_V3_MEDIA_PATH + path

            else:
                url += MATRIX_V2_MEDIA_PATH + path

            params.update({"filename": attachment.name})
            with open(attachment.path, "rb") as fp:
                payload = fp.read()

            # Update our content type
            headers["Content-Type"] = attachment.mimetype

        elif not url_override:
            if self.version == MatrixVersion.V3:
                url += MATRIX_V3_API_PATH + path

            else:
                url += MATRIX_V2_API_PATH + path

        # Our response object
        response = {}

        # fetch function
        fn = (
            requests.post
            if method == "POST"
            else (requests.put if method == "PUT" else requests.get)
        )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Define how many attempts we'll make if we get caught in a
        # throttle event
        retries = self.default_retries if self.default_retries > 0 else 1
        while retries > 0:
            # Decrement our throttle retry count
            retries -= 1

            self.logger.debug(
                "Matrix {} URL: {} (cert_verify={!r})".format(
                    (
                        "POST"
                        if method == "POST"
                        else ("PUT" if method == "PUT" else "GET")
                    ),
                    url,
                    self.verify_certificate,
                )
            )
            self.logger.debug(f"Matrix Payload: {payload!s}")

            # Initialize our response object
            r = None

            try:
                r = fn(
                    url,
                    data=dumps(payload) if not attachment else payload,
                    params=params if params else None,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # Store status code
                status_code = r.status_code

                self.logger.debug(
                    "Matrix Response: code={}, {}".format(
                        r.status_code, r.content
                    )
                )
                response = loads(r.content)

                if r.status_code == requests.codes.too_many_requests:
                    wait_ms = self.default_wait_ms
                    try:
                        wait_ms = response["retry_after_ms"]

                    except KeyError:
                        try:
                            errordata = response["error"]
                            wait_ms = errordata["retry_after_ms"]
                        except KeyError:
                            pass

                    self.logger.warning(
                        "Matrix server requested we throttle back "
                        "{}ms; retries left {}.".format(wait_ms, retries)
                    )
                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    # Throttle for specified wait
                    self.throttle(wait=wait_ms / 1000)

                    # Try again
                    continue

                elif r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyMatrix.http_response_code_lookup(
                        r.status_code, MATRIX_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to handshake with Matrix server: "
                        "{}{}error={}.".format(
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    # Return; we're done
                    return (False, response, status_code)

            except (AttributeError, TypeError, ValueError):
                # This gets thrown if we can't parse our JSON Response
                #  - ValueError = r.content is Unparsable
                #  - TypeError = r.content is None
                #  - AttributeError = r is None
                self.logger.warning("Invalid response from Matrix server.")
                self.logger.debug(
                    "Response Details:\r\n%r",
                    b"" if not r else (r.content or b""),
                )
                return (False, {}, status_code)

            except (
                requests.TooManyRedirects,
                requests.RequestException,
            ) as e:
                self.logger.warning(
                    "A Connection error occurred while registering "
                    "with Matrix server."
                )
                self.logger.debug("Socket Exception: %s", e)
                # Return; we're done
                return (False, response, status_code)

            except OSError as e:
                self.logger.warning(
                    "An I/O error occurred while reading {}.".format(
                        attachment.name if attachment else "unknown file"
                    )
                )
                self.logger.debug("I/O Exception: %s", e)
                return (False, {}, status_code)

            return (True, response, status_code)

        # If we get here, we ran out of retries
        return (False, {}, status_code)

    # ---------------------------------------------------------------
    # E2EE helpers
    # ---------------------------------------------------------------

    def _e2ee_room_encrypted(self, room_id):
        """Return ``True`` if *room_id* has E2EE enabled on the server.

        The result is cached in the persistent store so subsequent sends
        to the same room do not issue additional network requests.
        """
        cache_key = "e2ee_room_enc_{}".format(room_id)
        cached = self.store.get(cache_key)
        if cached is not None:
            return cached

        ok, response, _ = self._fetch(
            "/rooms/{}/state/m.room.encryption".format(
                NotifyMatrix.quote(room_id)
            ),
            method="GET",
        )
        result = ok and bool(response)
        self.store.set(
            cache_key,
            result,
            expires=self.default_cache_expiry_sec,
        )
        return result

    def _e2ee_setup(self):
        """Ensure the E2EE device account exists and keys are uploaded.

        Creates a new :class:`MatrixOlmAccount` if one does not yet
        exist in the persistent store, then calls
        :meth:`_e2ee_upload_keys` if the server has not yet received
        our device keys for the current access token.

        Returns ``True`` on success, ``False`` on failure.
        """
        if self._e2ee_account is None:
            acct_data = self.store.get("e2ee_account")
            if acct_data:
                try:
                    self._e2ee_account = MatrixOlmAccount.from_dict(acct_data)
                except Exception:
                    self._e2ee_account = None

            if self._e2ee_account is None:
                self._e2ee_account = MatrixOlmAccount()
                self.store.set(
                    "e2ee_account",
                    self._e2ee_account.to_dict(),
                    expires=self.default_cache_expiry_sec,
                )

        if not self.store.get("e2ee_keys_uploaded"):
            return self._e2ee_upload_keys()

        return True

    def _e2ee_upload_keys(self):
        """POST device keys to ``/_matrix/client/v3/keys/upload``."""
        if not self.user_id or not self.device_id:
            self.logger.warning(
                "Matrix E2EE: cannot upload keys without user_id "
                "and device_id; ensure login completes first."
            )
            return False

        payload = {
            "device_keys": self._e2ee_account.device_keys_payload(
                self.user_id, self.device_id
            )
        }
        postokay, _, _ = self._fetch("/keys/upload", payload=payload)
        if not postokay:
            self.logger.warning("Matrix E2EE: device key upload failed.")
            return False

        self.store.set(
            "e2ee_keys_uploaded",
            True,
            expires=self.default_cache_expiry_sec,
        )
        self.logger.debug(
            "Matrix E2EE: device keys uploaded for %s / %s.",
            self.user_id,
            self.device_id,
        )
        return True

    def _e2ee_get_megolm(self, room_id):
        """Return the current outbound MegOLM session for *room_id*.

        Creates a new session when none exists or when the existing one
        has reached the rotation threshold.  Also clears the
        ``e2ee_key_shared_*`` flag so the new session key is re-shared.
        """
        store_key = "e2ee_megolm_{}".format(room_id)
        session_data = self.store.get(store_key)

        if session_data:
            session = MatrixMegOlmSession.from_dict(session_data)
            if not session.should_rotate():
                return session

        # New or rotated session
        session = MatrixMegOlmSession()
        self.store.set(
            store_key,
            session.to_dict(),
            expires=self.default_cache_expiry_sec,
        )
        # Clear key-shared flag so we share the new session key
        self.store.clear("e2ee_key_shared_{}".format(room_id))
        return session

    def _e2ee_save_megolm(self, room_id, session):
        """Persist the updated MegOLM session state."""
        self.store.set(
            "e2ee_megolm_{}".format(room_id),
            session.to_dict(),
            expires=self.default_cache_expiry_sec,
        )

    def _e2ee_room_members(self, room_id):
        """Query device keys for all joined members of *room_id*.

        Returns a nested dict::

            {user_id: {device_id: {"curve25519": ..., "ed25519": ...}}}

        Returns ``None`` on HTTP failure, empty dict when the room has
        no members (unlikely but tolerated).
        """
        path = "/rooms/{}/joined_members".format(NotifyMatrix.quote(room_id))
        postokay, response, _ = self._fetch(path, payload=None, method="GET")
        if not postokay or not isinstance(response, dict):
            return None

        member_ids = list(response.get("joined", {}).keys())
        if not member_ids:
            return {}

        postokay, resp, _ = self._fetch(
            "/keys/query",
            payload={"device_keys": {uid: [] for uid in member_ids}},
        )
        if not postokay or not isinstance(resp, dict):
            return None

        result = {}
        for uid, devices in resp.get("device_keys", {}).items():
            result[uid] = {}
            for dev_id, dev_info in devices.items():
                if not verify_device_keys(dev_info, uid, dev_id):
                    self.logger.debug(
                        "Matrix E2EE: device key signature invalid "
                        "for %s / %s; device skipped.",
                        uid,
                        dev_id,
                    )
                    continue
                keys = dev_info.get("keys", {})
                result[uid][dev_id] = {
                    "curve25519": keys.get("curve25519:{}".format(dev_id), ""),
                    "ed25519": keys.get("ed25519:{}".format(dev_id), ""),
                }
        return result

    def _e2ee_share_room_key(self, room_id, session):
        """Send the MegOLM session key to all devices in *room_id*.

        Flow:
          1. Fetch joined-member device keys via /keys/query
          2. Claim one-time keys via /keys/claim
          3. Create outbound Olm sessions and encrypt the room-key event
          4. Deliver via PUT /sendToDevice/m.room.encrypted/{txnId}

        Returns ``True`` on success (partial device failures are
        tolerated), ``False`` only when a critical step fails.
        """
        members = self._e2ee_room_members(room_id)
        if members is None:
            self.logger.warning(
                "Matrix E2EE: failed to query room members for %s.",
                room_id,
            )
            return False

        if not members:
            return True

        # Build the claim request for all member devices.
        # "signed_curve25519" is the algorithm Matrix clients publish and
        # servers are required to support; "curve25519" (unsigned) is
        # deprecated and usually yields no keys on current servers.
        otk_request = {}
        for uid, devs in members.items():
            otk_request[uid] = dict.fromkeys(devs, "signed_curve25519")

        postokay, otk_resp, _ = self._fetch(
            "/keys/claim",
            payload={"one_time_keys": otk_request},
        )
        if not postokay:
            self.logger.warning("Matrix E2EE: failed to claim one-time keys.")
            return False

        otk_keys = (
            otk_resp.get("one_time_keys", {})
            if isinstance(otk_resp, dict)
            else {}
        )

        # Build to-device message payload
        to_device_msgs = {}
        room_key_content = {
            "algorithm": "m.megolm.v1.aes-sha2",
            "room_id": room_id,
            "session_id": session.session_id,
            "session_key": session.session_key(),
        }

        for uid, devices in members.items():
            to_device_msgs[uid] = {}
            for dev_id, dev_info in devices.items():
                # Skip our own device to avoid self-Olm-session setup
                if uid == self.user_id and dev_id == self.device_id:
                    continue

                their_ik = dev_info.get("curve25519", "")
                if not their_ik:
                    continue

                # Locate and verify the OTK for this device.
                # Servers return signed_curve25519 keys (the algorithm we
                # requested) as {"key": ..., "signatures": ...} dicts.
                # Locate and verify the OTK for this device.
                # signed_curve25519 OTKs are always KeyObjects
                # {"key": ..., "signatures": ...}; plain-string values
                # are not valid for this algorithm and are rejected.
                their_otk = None
                otk_entry = otk_keys.get(uid, {}).get(dev_id, {})
                if isinstance(otk_entry, dict):
                    for k, v in otk_entry.items():
                        if not k.startswith("signed_curve25519:"):
                            continue
                        if not isinstance(v, dict):
                            self.logger.debug(
                                "Matrix E2EE: OTK for %s / %s is "
                                "not a KeyObject; skipped.",
                                uid,
                                dev_id,
                            )
                            break
                        ed25519_pub = dev_info.get("ed25519", "")
                        if not ed25519_pub or not verify_signed_otk(
                            v, uid, dev_id, ed25519_pub
                        ):
                            self.logger.debug(
                                "Matrix E2EE: OTK signature "
                                "invalid for %s / %s; skipped.",
                                uid,
                                dev_id,
                            )
                        else:
                            their_otk = v.get("key")
                        break

                if not their_otk:
                    continue

                try:
                    olm_session = self._e2ee_account.create_outbound_session(
                        their_ik, their_otk
                    )
                except Exception:
                    self.logger.debug(
                        "Matrix E2EE: failed to build Olm session "
                        "for %s / %s.",
                        uid,
                        dev_id,
                    )
                    continue

                inner = dumps(
                    {
                        "type": "m.room_key",
                        "content": room_key_content,
                        "sender": self.user_id,
                        "recipient": uid,
                        "recipient_keys": {
                            "ed25519": dev_info.get("ed25519", "")
                        },
                        "keys": {"ed25519": self._e2ee_account.signing_key},
                        "sender_device": self.device_id,
                    }
                )
                ciphertext = olm_session.encrypt(inner)

                to_device_msgs[uid][dev_id] = {
                    "algorithm": "m.olm.v1.curve25519-aes-sha2",
                    "ciphertext": {their_ik: ciphertext},
                    "sender_key": self._e2ee_account.identity_key,
                }

        # Only send if at least one device message was built
        if not any(v for v in to_device_msgs.values()):
            return True

        self.transaction_id += 1
        self.store.set(
            "transaction_id",
            self.transaction_id,
            expires=self.default_cache_expiry_sec,
        )
        path = "/sendToDevice/m.room.encrypted/{}".format(self.transaction_id)
        postokay, _, _ = self._fetch(
            path,
            payload={"messages": to_device_msgs},
            method="PUT",
        )
        if not postokay:
            self.logger.warning(
                "Matrix E2EE: failed to deliver room key to devices in %s.",
                room_id,
            )
            return False

        return True

    def _e2ee_send_to_room(self, room_id, body, title, notify_type):
        """Encrypt and send one message to *room_id* via MegOLM.

        Shares the MegOLM session key with room members when the
        session is new or has just been rotated.
        Returns ``True`` on success, ``False`` on failure.
        """
        session = self._e2ee_get_megolm(room_id)

        # Share room key if this session has not been announced yet
        shared_flag = "e2ee_key_shared_{}".format(room_id)
        if not self.store.get(shared_flag):
            if not self._e2ee_share_room_key(room_id, session):
                return False
            self.store.set(
                shared_flag,
                True,
                expires=self.default_cache_expiry_sec,
            )

        # Build the inner plaintext event
        msg_content = {
            "msgtype": "m.{}".format(self.msgtype),
            "body": "{title}{body}".format(
                title="" if not title else "# {}\r\n".format(title),
                body=body,
            ),
        }

        if self.notify_format == NotifyFormat.HTML:
            msg_content.update(
                {
                    "format": "org.matrix.custom.html",
                    "formatted_body": "{title}{body}".format(
                        title=(
                            "" if not title else "<h1>{}</h1>".format(title)
                        ),
                        body=body,
                    ),
                }
            )

        elif self.notify_format == NotifyFormat.MARKDOWN:
            msg_content.update(
                {
                    "format": "org.matrix.custom.html",
                    "formatted_body": "{title}{body}".format(
                        title=(
                            ""
                            if not title
                            else "<h1>{}</h1>".format(
                                NotifyMatrix.escape_html(
                                    title, whitespace=False
                                )
                            )
                        ),
                        body=markdown(body),
                    ),
                }
            )

        inner_event = {
            "type": "m.room.message",
            "content": msg_content,
            "room_id": room_id,
        }

        ciphertext = session.encrypt(inner_event)
        self._e2ee_save_megolm(room_id, session)

        path = "/rooms/{}/send/m.room.encrypted/{}".format(
            NotifyMatrix.quote(room_id), self.transaction_id
        )
        encrypted_payload = {
            "algorithm": "m.megolm.v1.aes-sha2",
            "ciphertext": ciphertext,
            "sender_key": self._e2ee_account.identity_key,
            "session_id": session.session_id,
            "device_id": self.device_id or "",
        }

        postokay, _, _ = self._fetch(
            path, payload=encrypted_payload, method="PUT"
        )

        if self.access_token != self.password:
            self.transaction_id += 1
            self.store.set(
                "transaction_id",
                self.transaction_id,
                expires=self.default_cache_expiry_sec,
            )

        return postokay

    def _e2ee_send_attachment(self, attachment, room_id, session):
        """Encrypt *attachment* and deliver it to *room_id* via MegOLM.

        Steps:
        1. Read the file into memory and encrypt with AES-256-CTR.
        2. Upload the ciphertext to the media server (content_uri).
        3. Build an ``m.room.message`` inner event whose ``file`` field
           carries the EncryptedFile metadata (key + iv + sha256).
        4. Encrypt the inner event with MegOLM and PUT to the room.

        Returns ``True`` on success, ``False`` on any failure.
        """
        # Read file bytes
        try:
            with open(attachment.path, "rb") as fh:
                file_data = fh.read()
        except OSError as e:
            self.logger.warning(
                "Matrix E2EE: could not read attachment {}.".format(
                    attachment.name or "file"
                )
            )
            self.logger.debug(f"I/O Exception: {e!s}")
            return False

        # Encrypt locally with AES-256-CTR
        ciphertext, file_info = encrypt_attachment(file_data)

        # Upload the ciphertext to the media server.
        # The encrypted bytes are posted directly rather than from a file
        # path, so we call requests.post() directly instead of _fetch().
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/octet-stream",
            "Accept": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        try:
            base = self.base_url
        except Exception:
            return False

        media_path = (
            MATRIX_V3_MEDIA_PATH
            if self.version == MatrixVersion.V3
            else MATRIX_V2_MEDIA_PATH
        )
        upload_url = base + media_path + "/upload"

        self.throttle()
        try:
            r = requests.post(
                upload_url,
                data=ciphertext,
                params={"filename": attachment.name or "file"},
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
        except requests.RequestException as e:
            self.logger.warning(
                "Matrix E2EE: connection error uploading encrypted attachment."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        try:
            upload_resp = loads(r.content)
        except Exception:
            upload_resp = {}

        if r.status_code != requests.codes.ok or not upload_resp.get(
            "content_uri"
        ):
            self.logger.warning(
                "Matrix E2EE: media upload failed (HTTP {}).".format(
                    r.status_code
                )
            )
            return False

        file_info["url"] = upload_resp["content_uri"]

        # Build the inner plaintext attachment event
        is_image = IS_IMAGE.match(attachment.mimetype)
        inner_event = {
            "type": "m.room.message",
            "content": {
                "msgtype": "m.image" if is_image else "m.file",
                "body": attachment.name or "file",
                "file": file_info,
            },
            "room_id": room_id,
        }

        # Encrypt with MegOLM and send
        ciphertext_event = session.encrypt(inner_event)
        self._e2ee_save_megolm(room_id, session)

        path = "/rooms/{}/send/m.room.encrypted/{}".format(
            NotifyMatrix.quote(room_id), self.transaction_id
        )
        encrypted_payload = {
            "algorithm": "m.megolm.v1.aes-sha2",
            "ciphertext": ciphertext_event,
            "sender_key": self._e2ee_account.identity_key,
            "session_id": session.session_id,
            "device_id": self.device_id or "",
        }
        postokay, _, _ = self._fetch(
            path, payload=encrypted_payload, method="PUT"
        )
        if self.access_token != self.password:
            self.transaction_id += 1
            self.store.set(
                "transaction_id",
                self.transaction_id,
                expires=self.default_cache_expiry_sec,
            )
        return postokay

    def _dm_room_find_or_create(self, user):
        """Resolve *user* (``@localpart`` or ``@localpart:homeserver``)
        to a Matrix room ID suitable for direct messaging.

        Lookup order:
        1. Persistent-store cache.
        2. ``GET /user/{selfId}/account_data/m.direct`` -- check whether
           an existing DM room already exists for this user.
        3. ``POST /createRoom`` with ``is_direct=true`` and an invite for
           the target user.  The ``m.direct`` account-data entry is then
           updated so other clients also recognise the room as a DM.

        Returns the room ID string on success, or ``None`` on failure.
        """
        result = IS_USER.match(user)
        if not result:
            self.logger.warning("Matrix DM: invalid user identifier %r.", user)
            return None

        home_server = (
            result.group("home_server")
            if result.group("home_server")
            else self.home_server
        )
        user_id = "@{}:{}".format(result.group("user"), home_server)

        cache_key = "dm_room_{}".format(user_id)
        cached = self.store.get(cache_key)
        if cached:
            return cached

        # Fetch existing m.direct mapping from the server
        mdirect = {}
        if self.user_id:
            ok, resp, _ = self._fetch(
                "/user/{}/account_data/m.direct".format(
                    NotifyMatrix.quote(self.user_id)
                ),
                method="GET",
            )
            if ok and isinstance(resp, dict):
                mdirect = resp
                rooms = mdirect.get(user_id, [])
                if rooms:
                    room_id = rooms[0]
                    self.store.set(
                        cache_key,
                        room_id,
                        expires=self.default_cache_expiry_sec,
                    )
                    return room_id

        # No existing DM room -- create one
        ok, response, _ = self._fetch(
            "/createRoom",
            payload={
                "is_direct": True,
                "preset": "trusted_private_chat",
                "invite": [user_id],
            },
        )
        if not ok or not isinstance(response, dict):
            self.logger.warning(
                "Matrix DM: failed to create room for %s.", user_id
            )
            return None

        room_id = response.get("room_id")
        if not room_id:
            return None

        self.store.set(
            cache_key,
            room_id,
            expires=self.default_cache_expiry_sec,
        )

        # Update the m.direct account-data mapping so other clients
        # recognise this room as a DM conversation.
        if self.user_id:
            mdirect[user_id] = [*mdirect.get(user_id, []), room_id]
            self._fetch(
                "/user/{}/account_data/m.direct".format(
                    NotifyMatrix.quote(self.user_id)
                ),
                payload=mdirect,
                method="PUT",
            )

        return room_id

    # ---------------------------------------------------------------
    # Destructor / URL / parse
    # ---------------------------------------------------------------

    def __del__(self):
        """Ensure we relinquish our token."""
        if self.mode == MatrixWebhookMode.T2BOT:
            # nothing to do
            return

        if self.store.mode != PersistentStoreMode.MEMORY:
            # We no longer have to log out as we have persistant storage
            # to re-use our credentials with
            return

        if (
            self.access_token is not None
            and self.access_token == self.password
            and not self.user
        ):
            return

        self._logout()

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.mode,
            (
                self.host
                if self.mode != MatrixWebhookMode.T2BOT
                else self.access_token
            ),
            self.port if self.port else (443 if self.secure else 80),
            self.user if self.mode != MatrixWebhookMode.T2BOT else None,
            self.password if self.mode != MatrixWebhookMode.T2BOT else None,
        )

    @staticmethod
    def runtime_deps():
        """Return runtime dependency package names.

        E2EE support requires the `cryptography` package.
        """
        return ("cryptography",)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified
        arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
            "mode": self.mode,
            "version": self.version,
            "msgtype": self.msgtype,
            "discovery": "yes" if self.discovery else "no",
            "hsreq": "yes" if self.hsreq else "no",
        }

        if not self.e2ee:
            params["e2ee"] = "no"

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        auth = ""
        if self.mode != MatrixWebhookMode.T2BOT:
            # Determine Authentication
            if self.user and self.password:
                auth = "{user}:{password}@".format(
                    user=NotifyMatrix.quote(self.user, safe=""),
                    password=self.pprint(
                        self.password,
                        privacy,
                        mode=PrivacyMode.Secret,
                        safe="",
                    ),
                )

            elif self.user or self.password:
                auth = "{value}@".format(
                    value=NotifyMatrix.quote(
                        self.user if self.user else self.password, safe=""
                    ),
                )

        return "{schema}://{auth}{hostname}{port}/{rooms}?{params}".format(
            schema=(self.secure_protocol if self.secure else self.protocol),
            auth=auth,
            hostname=(
                NotifyMatrix.quote(self.host, safe="")
                if self.mode != MatrixWebhookMode.T2BOT
                else self.pprint(self.access_token, privacy, safe="")
            ),
            port=("" if not self.port else f":{self.port}"),
            rooms=NotifyMatrix.quote("/".join(self.rooms + self.users)),
            params=NotifyMatrix.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this
        notification."""
        targets = len(self.rooms) + len(self.users)
        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us
        to re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        if not results.get("host"):
            return None

        # Get our rooms
        results["targets"] = NotifyMatrix.split_path(results["fullpath"])

        # Support the 'to' variable so that we can support rooms this
        # way too.  The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyMatrix.parse_list(results["qsd"]["to"])

        # Boolean to include an image or not
        results["include_image"] = parse_bool(
            results["qsd"].get(
                "image",
                NotifyMatrix.template_args["image"]["default"],
            )
        )

        # Boolean to perform a server discovery
        results["discovery"] = parse_bool(
            results["qsd"].get(
                "discovery",
                NotifyMatrix.template_args["discovery"]["default"],
            )
        )

        # Boolean to enforce ':homeserver' on room IDs when missing
        results["hsreq"] = parse_bool(
            results["qsd"].get(
                "hsreq",
                NotifyMatrix.template_args["hsreq"]["default"],
            )
        )

        # E2EE flag
        if "e2ee" in results["qsd"]:
            results["e2ee"] = parse_bool(results["qsd"]["e2ee"])

        # Get our mode
        results["mode"] = results["qsd"].get("mode")

        # t2bot detection... look for just a hostname, and/or just a
        # user/host if we match this; we can go ahead and set the mode
        # (but only if it was otherwise not set)
        if (
            results["mode"] is None
            and not results["password"]
            and not results["targets"]
        ):
            # Default mode to t2bot
            results["mode"] = MatrixWebhookMode.T2BOT

        if (
            results["mode"]
            and results["mode"].lower() == MatrixWebhookMode.T2BOT
        ):
            # unquote our hostname and pass it in as the password/token
            results["password"] = NotifyMatrix.unquote(results["host"])

        # Support the message type keyword
        if "msgtype" in results["qsd"] and len(results["qsd"]["msgtype"]):
            results["msgtype"] = NotifyMatrix.unquote(
                results["qsd"]["msgtype"]
            )

        # Support the use of the token= keyword
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["password"] = NotifyMatrix.unquote(results["qsd"]["token"])

        elif not results["password"] and results["user"]:
            # swap
            results["password"] = results["user"]
            results["user"] = None

        # Support the use of the version= or v= keyword
        if "version" in results["qsd"] and len(results["qsd"]["version"]):
            results["version"] = NotifyMatrix.unquote(
                results["qsd"]["version"]
            )

        elif "v" in results["qsd"] and len(results["qsd"]["v"]):
            results["version"] = NotifyMatrix.unquote(results["qsd"]["v"])

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://webhooks.t2bot.io/api/v1/matrix/hook/WEBHOOK_TOKEN/
        """

        result = re.match(
            r"^https?://webhooks\.t2bot\.io/api/v[0-9]+/matrix/hook/"
            r"(?P<webhook_token>[A-Z0-9_-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            mode = f"mode={MatrixWebhookMode.T2BOT}"

            return NotifyMatrix.parse_url(
                "{schema}://{webhook_token}/{params}".format(
                    schema=NotifyMatrix.secure_protocol,
                    webhook_token=result.group("webhook_token"),
                    params=(
                        f"?{mode}"
                        if not result.group("params")
                        else "{}&{}".format(result.group("params"), mode)
                    ),
                )
            )

        return None

    def server_discovery(self):
        """
        Home Server Discovery as documented here:
           https://spec.matrix.org/v1.11/client-server-api/#well-known-uri
        """

        if not (self.discovery and self.secure):
            # Nothing further to do with insecure server setups
            return ""

        # Get our content from cache
        base_url, identity_url = (
            self.store.get(self.discovery_base_key),
            self.store.get(self.discovery_identity_key),
        )

        if not (base_url is None and identity_url is None):
            # We can use our cached value and return early
            return base_url

        # the Matrix ID at the first colon.
        verify_url = (
            "{schema}://{hostname}{port}/.well-known/matrix/client".format(
                schema="https" if self.secure else "http",
                hostname=self.host,
                port=("" if not self.port else f":{self.port}"),
            )
        )

        _, response, status_code = self._fetch(
            None, method="GET", url_override=verify_url
        )

        # Output may look as follows:
        # {
        #     "m.homeserver": {
        #         "base_url": "https://matrix.example.com"
        #     },
        #     "m.identity_server": {
        #         "base_url": "https://nuxref.com"
        #     }
        # }

        if status_code == requests.codes.not_found:
            # This is an acceptable response; we're done
            self.logger.debug(
                "Matrix Well-Known Base URI not found at %s",
                verify_url,
            )

            # Set our keys out for fast recall later on
            self.store.set(
                self.discovery_base_key,
                "",
                expires=self.discovery_cache_length_sec,
            )
            self.store.set(
                self.discovery_identity_key,
                "",
                expires=self.discovery_cache_length_sec,
            )
            return ""

        elif status_code != requests.codes.ok:
            # We're done early as we couldn't load the results
            msg = "Matrix Well-Known Base URI Discovery Failed"
            self.logger.warning(
                "%s - %s returned error code: %d",
                msg,
                verify_url,
                status_code,
            )
            raise MatrixDiscoveryException(msg, error_code=status_code)

        if not response:
            # This is an acceptable response; we simply do nothing
            self.logger.debug(
                "Matrix Well-Known Base URI not defined %s", verify_url
            )

            # Set our keys out for fast recall later on
            self.store.set(
                self.discovery_base_key,
                "",
                expires=self.discovery_cache_length_sec,
            )
            self.store.set(
                self.discovery_identity_key,
                "",
                expires=self.discovery_cache_length_sec,
            )
            return ""

        #
        # Parse our m.homeserver information
        #
        try:
            base_url = response["m.homeserver"]["base_url"].rstrip("/")
            results = NotifyBase.parse_url(base_url, verify_host=True)

        except (AttributeError, TypeError, KeyError):
            # AttributeError: result wasn't a string (rstrip failed)
            # TypeError     : response wasn't a dictionary
            # KeyError      : response not to standards
            results = None

        if not results:
            msg = "Matrix Well-Known Base URI Discovery Failed"
            self.logger.warning(
                "%s - m.homeserver payload is missing or invalid: %s",
                msg,
                response,
            )
            raise MatrixDiscoveryException(msg)

        #
        # Our .well-known extraction was successful; now we need to
        # verify that the version information resolves.
        #
        verify_url = f"{base_url}/_matrix/client/versions"
        # Post our content
        _, _, status_code = self._fetch(
            None, method="GET", url_override=verify_url
        )
        if status_code != requests.codes.ok:
            # We're done early as we couldn't load the results
            msg = "Matrix Well-Known Base URI Discovery Verification Failed"
            self.logger.warning(
                "%s - %s returned error code: %d",
                msg,
                verify_url,
                status_code,
            )
            raise MatrixDiscoveryException(msg, error_code=status_code)

        #
        # Phase 2: Handle m.identity_server IF defined
        #
        if "m.identity_server" in response:
            try:
                identity_url = response["m.identity_server"][
                    "base_url"
                ].rstrip("/")
                results = NotifyBase.parse_url(identity_url, verify_host=True)

            except (AttributeError, TypeError, KeyError):
                # AttributeError: result wasn't a string (rstrip failed)
                # TypeError     : response wasn't a dictionary
                # KeyError      : response not to standards
                results = None

            if not results:
                msg = "Matrix Well-Known Identity URI Discovery Failed"
                self.logger.warning(
                    "%s - m.identity_server payload is missing or invalid: %s",
                    msg,
                    response,
                )
                raise MatrixDiscoveryException(msg)

            #
            #  Verify identity server found
            #
            verify_url = f"{identity_url}/_matrix/identity/v2"

            # Post our content
            _postokay, _, status_code = self._fetch(
                None, method="GET", url_override=verify_url
            )
            if status_code != requests.codes.ok:
                # We're done early as we couldn't load the results
                msg = "Matrix Well-Known Identity URI Discovery Failed"
                self.logger.warning(
                    "%s - %s returned error code: %d",
                    msg,
                    verify_url,
                    status_code,
                )
                raise MatrixDiscoveryException(msg, error_code=status_code)

            # Update our cache
            self.store.set(
                self.discovery_identity_key,
                identity_url,
                # Add 2 seconds to prevent this key from expiring before
                # base
                expires=self.discovery_cache_length_sec + 2,
            )
        else:
            # No identity server
            self.store.set(
                self.discovery_identity_key,
                "",
                # Add 2 seconds to prevent this key from expiring before
                # base
                expires=self.discovery_cache_length_sec + 2,
            )

        # Update our cache
        self.store.set(
            self.discovery_base_key,
            base_url,
            expires=self.discovery_cache_length_sec,
        )

        return base_url

    @property
    def base_url(self):
        """Returns the base_url if known."""
        try:
            base_url = self.server_discovery()
            if base_url:
                # We can use our cached value and return early
                return base_url

        except MatrixDiscoveryException:
            self.store.clear(
                self.discovery_base_key, self.discovery_identity_key
            )
            raise

        # If we get hear, we need to build our URL dynamically based on
        # what was provided to us during the plugins initialization
        return "{schema}://{hostname}{port}".format(
            schema="https" if self.secure else "http",
            hostname=self.host,
            port=("" if not self.port else f":{self.port}"),
        )

    @property
    def identity_url(self):
        """Returns the identity_url if known."""
        base_url = self.base_url
        identity_url = self.store.get(self.discovery_identity_key)
        return identity_url if identity_url else base_url
