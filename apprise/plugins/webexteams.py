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

# At the time I created this plugin, their website had lots of issues with the
# Firefox Browser.  I fell back to Chrome and had no problems.

# There are 2 ways to use this plugin...
#
# Method 1: Via Webhook (default mode):
#   Visit https://teams.webex.com and make yourself an account if you don't
#   already have one.  You'll want to create at least one 'space' before
#   getting the 'incoming webhook'.
#
#   Next you'll need to install the 'Incoming webhook' plugin found under
#   the 'other' category here: https://apphub.webex.com/integrations/
#
#   These links may not always work as time goes by and websites always
#   change, but at the time of creating this plugin this was a direct link
#   to it:
#     https://apphub.webex.com/integrations/incoming-webhooks-cisco-systems
#
#   If you're logged in, you'll be able to click on the 'Connect' button.
#   From there you'll need to accept the permissions it will ask of you.
#   Give the webhook a name such as 'apprise'.
#   When you're complete, you will recieve a URL that looks something like:
#     https://api.ciscospark.com/v1/webhooks/incoming/\
#           Y3lzY29zcGkyazovL3VzL1dFQkhPT0sajkkzYWU4fTMtMGE4Yy00
#
#   The last part of the URL is all you need to be interested in. Think of
#   this url as:
#     https://api.ciscospark.com/v1/webhooks/incoming/{token}
#
#   You will need to assemble all of your URLs for this plugin to work as:
#     wxteams://{token}
#
#
# Method 2: Via Bot/API (supports file attachments):
#   Visit https://developer.webex.com/my-apps and create a new Bot.
#   After creating the bot, you'll receive a Bot Access Token.
#
#   You will also need to know the Room ID(s) you want to post to.
#   Room IDs can be retrieved from the Webex API:
#     https://developer.webex.com/docs/api/v1/rooms/list-rooms
#
#   Assemble your Apprise URL as:
#     wxteams://{access_token}/{room_id}
#     wxteams://{access_token}/{room_id1}/{room_id2}
#
#   The plugin auto-detects the mode:
#     - If the token is 80-160 lowercase alphanumeric chars -> Webhook mode
#     - Otherwise -> Bot mode (requires at least one room ID)
#   You may also force the mode with ?mode=webhook or ?mode=bot.
#
# Resources
# - https://developer.webex.com/docs/api/basics - markdown/post syntax
# - https://developer.webex.com/docs/api/v1/messages/create-a-message
# - https://developer.cisco.com/ecosystem/webex/apps/\
#       incoming-webhooks-cisco-systems/ - Simple webhook example

from json import dumps
import re

import requests

from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on: https://developer.webex.com/docs/api/basics/rate-limiting
WEBEX_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Token.",
    415: "Unsuported media specified",
    429: "To many consecutive requests were made.",
    503: "Service is overloaded, try again later",
}


class WebexTeamsMode:
    """Tracks the mode of which we're using Webex Teams."""

    # We're dealing with an incoming webhook
    # Token is 80-160 lowercase alphanumeric chars
    WEBHOOK = "webhook"

    # We're dealing with a Bot/API access token (supports attachments)
    # Token is a Bearer access token from the Webex developer portal
    BOT = "bot"


# Define our Webex Teams Modes
WEBEX_TEAMS_MODES = (
    WebexTeamsMode.WEBHOOK,
    WebexTeamsMode.BOT,
)


class NotifyWebexTeams(NotifyBase):
    """A wrapper for Webex Teams Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Cisco Webex Teams"

    # The services URL
    service_url = "https://webex.teams.com/"

    # The default secure protocol
    secure_protocol = ("wxteams", "webex")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/wxteams/"

    # Webex Teams Webhook URL
    notify_url = "https://api.ciscospark.com/v1/webhooks/incoming/"

    # Webex Teams Bot API URL (used in Bot mode)
    api_url = "https://webexapis.com/v1/messages"

    # Bot mode supports attachments
    attachment_support = True

    # Do not set body_maxlen as it is set in a property value below
    # since the length varies depending on whether we are using a
    # webhook (1000 chars) or the bot API (7439 chars)
    # body_maxlen = see below @property defined

    # We don't support titles for Webex notifications
    title_maxlen = 0

    # Default to markdown; fall back to text
    notify_format = NotifyFormat.MARKDOWN

    # Define object URL templates
    templates = (
        # Webhook mode (existing)
        "{schema}://{token}",
        # Bot mode (access_token in host, one or more room IDs in path)
        "{schema}://{access_token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Webhook Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-z0-9]{80,160}$", "i"),
            },
            "access_token": {
                "name": _("Bot Access Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "targets": {
                "name": _("Room IDs"),
                "type": "list:string",
            },
        },
    )

    template_args = dict(
        NotifyBase.template_args,
        **{
            "token": {
                "alias_of": "token",
            },
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": WEBEX_TEAMS_MODES,
                # mode is auto-detected if not specified
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        token=None,
        access_token=None,
        targets=None,
        mode=None,
        **kwargs,
    ):
        """Initialize Webex Teams Object."""
        super().__init__(**kwargs)

        # Resolve mode: explicit override wins, otherwise auto-detect
        if mode and isinstance(mode, str):
            self.mode = next(
                (m for m in WEBEX_TEAMS_MODES if m.startswith(mode)), None
            )
            if self.mode not in WEBEX_TEAMS_MODES:
                msg = f"The Webex Teams mode specified ({mode}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            # Auto-detect: webhook tokens are 80-160 lowercase alphanumeric
            _candidate = access_token or token
            if token and validate_regex(
                token, *self.template_tokens["token"]["regex"]
            ):
                self.mode = WebexTeamsMode.WEBHOOK

            elif _candidate:
                # Non-webhook token length/format -> assume BOT
                self.mode = WebexTeamsMode.BOT

            else:
                # No usable token at all; will fail below
                self.mode = WebexTeamsMode.WEBHOOK

        if self.mode == WebexTeamsMode.WEBHOOK:
            self.access_token = None
            self.targets = []

            # Webhook token: prefer 'token', fall back to 'access_token'
            _tok = token or access_token
            self.token = validate_regex(
                _tok, *self.template_tokens["token"]["regex"]
            )
            if not self.token:
                msg = (
                    "The Webex Teams webhook token"
                    f" specified ({_tok}) is invalid."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        else:  # WebexTeamsMode.BOT
            self.token = None

            # Bot access token: prefer 'access_token', fall back to 'token'
            _at = access_token or token
            if not _at:
                msg = "A Webex Teams bot access token must be specified."
                self.logger.warning(msg)
                raise TypeError(msg)

            self.access_token = _at

            self.targets = parse_list(targets)

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Webex Teams Notification."""
        if self.mode == WebexTeamsMode.WEBHOOK:
            if attach and self.attachment_support:
                self.logger.warning(
                    "Webex Teams Webhooks do not support"
                    " attachments; use bot mode."
                )
            return self._send_webhook(body)

        return self._send_bot(body, attach=attach)

    def _send_webhook(self, body):
        """Post via incoming webhook (no attachment support)."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        url = f"{self.notify_url}/{self.token}"

        payload = {
            (
                "markdown"
                if (self.notify_format == NotifyFormat.MARKDOWN)
                else "text"
            ): body,
        }

        self.logger.debug(
            "Webex Teams Webhook POST URL:"
            f" {url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Webex Teams Payload: {payload!s}")

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
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.no_content,
            ):
                status_str = NotifyWebexTeams.http_response_code_lookup(
                    r.status_code, WEBEX_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Webex Teams notification: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r",
                    (r.content or b"")[:2000],
                )

                return False

            self.logger.info("Sent Webex Teams notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Webex Teams notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        return True

    def _send_bot(self, body, attach=None):
        """Post via Bot/API to one or more rooms (supports attachments)."""

        if not self.targets:
            self.logger.warning(
                "Webex Teams Bot mode has no room IDs to notify, aborting."
            )
            return False

        has_error = False
        for room_id in self.targets:
            if not self._post_to_room(body, room_id, attach=attach):
                has_error = True

        return not has_error

    def _post_to_room(self, body, room_id, attach=None):
        """Send a single message (and optional attachments) to a room."""

        headers = {
            "User-Agent": self.app_id,
            "Authorization": f"Bearer {self.access_token}",
        }

        text_key = (
            "markdown"
            if self.notify_format == NotifyFormat.MARKDOWN
            else "text"
        )

        has_attachment = attach and self.attachment_support and len(attach) > 0

        if not has_attachment:
            # --- Text-only message sent as JSON ---
            headers["Content-Type"] = "application/json"
            payload = {
                "roomId": room_id,
                text_key: body,
            }

            self.logger.debug(
                "Webex Teams Bot POST URL:"
                f" {self.api_url}"
                f" (cert_verify={self.verify_certificate!r})"
            )
            self.logger.debug(f"Webex Teams Bot Payload: {payload!s}")

            self.throttle()
            try:
                r = requests.post(
                    self.api_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.ok:
                    status_str = NotifyWebexTeams.http_response_code_lookup(
                        r.status_code, WEBEX_HTTP_ERROR_MAP
                    )
                    self.logger.warning(
                        "Failed to send Webex Teams Bot"
                        " notification:"
                        " {}{}error={}.".format(
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )
                    return False

                self.logger.info(
                    f"Sent Webex Teams Bot notification to room {room_id}."
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending"
                    " Webex Teams Bot notification."
                )
                self.logger.debug(f"Socket Exception: {e!s}")
                return False

            return True

        # --- Multipart attachment(s) ---
        for no, attachment in enumerate(attach, start=1):
            if not attachment:
                self.logger.error(
                    "Could not access Webex Teams attachment"
                    f" {attachment.url(privacy=True)}."
                )
                return False

            self.logger.debug(
                "Posting Webex Teams attachment"
                f" {attachment.url(privacy=True)}"
            )

            try:
                # open() returns a BytesIO for memory attachments; the
                # context manager guarantees the handle is closed on exit
                with attachment.open() as fp:
                    files = {
                        "files": (
                            (
                                attachment.name
                                if attachment.name
                                else f"file{no:03}.dat"
                            ),
                            fp,
                            attachment.mimetype,
                        ),
                    }

                    data = {"roomId": room_id}
                    # Include message body only with the first attachment
                    if no == 1:
                        data[text_key] = body

                    self.logger.debug(
                        "Webex Teams Bot attachment POST URL:"
                        f" {self.api_url}"
                        f" (cert_verify={self.verify_certificate!r})"
                    )

                    self.throttle()
                    r = requests.post(
                        self.api_url,
                        data=data,
                        headers=headers,
                        files=files,
                        verify=self.verify_certificate,
                        timeout=self.request_timeout,
                    )

                if r.status_code != requests.codes.ok:
                    status_str = NotifyWebexTeams.http_response_code_lookup(
                        r.status_code, WEBEX_HTTP_ERROR_MAP
                    )
                    self.logger.warning(
                        "Failed to send Webex Teams attachment"
                        " {}: {}{}error={}.".format(
                            attachment.name,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r",
                        (r.content or b"")[:2000],
                    )
                    return False

                self.logger.info(
                    "Sent Webex Teams attachment"
                    f" {attachment.name} to room {room_id}."
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred posting"
                    " Webex Teams attachment."
                )
                self.logger.debug(f"Socket Exception: {e!s}")
                return False

            except OSError as e:
                self.logger.warning(
                    "An I/O error occurred while reading {}.".format(
                        attachment.name if attachment.name else "attachment"
                    )
                )
                self.logger.debug(f"I/O Exception: {e!s}")
                return False

        return True

    @property
    def body_maxlen(self):
        """The maximum allowable characters allowed in the body per message.
        Webhook mode is limited to 1000 chars; the Bot API allows 7439."""
        return 1000 if self.mode == WebexTeamsMode.WEBHOOK else 7439

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        if self.mode == WebexTeamsMode.WEBHOOK:
            return (self.secure_protocol[0], self.token)

        # BOT mode
        return (self.secure_protocol[0], self.access_token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        params = {"mode": self.mode}
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.mode == WebexTeamsMode.WEBHOOK:
            return "{schema}://{token}/?{params}".format(
                schema=self.secure_protocol[0],
                token=self.pprint(self.token, privacy, safe=""),
                params=NotifyWebexTeams.urlencode(params),
            )

        # BOT mode
        return "{schema}://{token}/{targets}/?{params}".format(
            schema=self.secure_protocol[0],
            token=self.pprint(self.access_token, privacy, safe=""),
            targets="/".join(
                [NotifyWebexTeams.quote(r, safe="") for r in self.targets]
            ),
            params=NotifyWebexTeams.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us
        to re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # Explicit mode parameter wins
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyWebexTeams.unquote(results["qsd"]["mode"])

        # Pull additional room-ID path entries (bot mode)
        entries = NotifyWebexTeams.split_path(results["fullpath"])

        # Support ?to= for room IDs
        if "to" in results["qsd"] and results["qsd"]["to"]:
            entries += NotifyWebexTeams.split_path(
                NotifyWebexTeams.unquote(results["qsd"]["to"])
            )

        # Support ?token= for the primary token/access_token
        if "token" in results["qsd"] and results["qsd"]["token"]:
            host = NotifyWebexTeams.unquote(results["qsd"]["token"])
        else:
            host = NotifyWebexTeams.unquote(results["host"])

        # Determine whether this is webhook or bot mode.
        # Path entries mean bot mode (room IDs present).
        # Explicit mode= has already been stored above.
        explicit_mode = results.get("mode", "")
        if explicit_mode == WebexTeamsMode.BOT or (
            entries and explicit_mode != WebexTeamsMode.WEBHOOK
        ):
            results["access_token"] = host
            results["targets"] = entries
        else:
            results["token"] = host

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support:
          https://api.ciscospark.com/v1/webhooks/incoming/WEBHOOK_TOKEN
          https://webexapis.com/v1/webhooks/incoming/WEBHOOK_TOKEN
        """

        result = re.match(
            r"^https?://(api\.ciscospark\.com|webexapis\.com)"
            r"/v[1-9][0-9]*/webhooks/incoming/"
            r"(?P<webhook_token>[A-Z0-9_-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyWebexTeams.parse_url(
                "{schema}://{webhook_token}/{params}".format(
                    schema=NotifyWebexTeams.secure_protocol[0],
                    webhook_token=result.group("webhook_token"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None
