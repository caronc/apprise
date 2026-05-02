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
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
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

# Steps to set up a Zoom Team Chat Incoming Webhook:
#  1. Sign in to https://marketplace.zoom.us and search for
#     "Incoming Webhook".
#  2. Click "Add" to install the Incoming Webhook app to your account.
#  3. In any Zoom Team Chat channel, type the slash command:
#        /inc connect
#     Follow the prompts to complete the connection.  You will receive:
#       - Endpoint URL:
#           https://inbots.zoom.us/incoming/hook/WEBHOOK_ID
#       - Verification Token: VERIFICATION_TOKEN
#
#  Assemble your Apprise URL using both values:
#
#     zoom://WEBHOOK_ID/VERIFICATION_TOKEN
#
#  By default, messages are sent in "full" structured format, which renders
#  the notification title as a heading and the body as the message text.
#  To send a plain-text message instead, append ?mode=simple:
#
#     zoom://WEBHOOK_ID/VERIFICATION_TOKEN?mode=simple
#
#  The native webhook URL is also supported when a ?token= parameter is
#  appended containing the verification token:
#
#     https://inbots.zoom.us/incoming/hook/WEBHOOK_ID?token=TOKEN
#
# References:
#  - https://marketplace.zoom.us/apps/eH_dLuquRd-VYcOsNGy-hQ
#  - https://support.zoom.com/hc/en/article?id=zm_kb&\
#        sysparm_article=KB0067640

from json import dumps
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
ZOOM_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid verification token.",
    404: "Webhook not found; check the Webhook ID.",
    429: "Rate limit exceeded; too many consecutive requests.",
    500: "Zoom internal server error.",
    503: "Service unavailable; try again later.",
}


class ZoomMode:
    """Tracks the notification mode for Zoom Team Chat."""

    # Plain-text message; sent without JSON wrapping
    SIMPLE = "simple"

    # Structured message with head/body sections (supports title)
    FULL = "full"


# Valid Zoom notification modes
ZOOM_MODES = (
    ZoomMode.SIMPLE,
    ZoomMode.FULL,
)

# Default notification mode
ZOOM_MODE_DEFAULT = ZoomMode.FULL


class NotifyZoom(NotifyBase):
    """A wrapper for Zoom Team Chat Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Zoom"

    # The services URL
    service_url = "https://zoom.us/"

    # The default secure protocol
    secure_protocol = "zoom"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/zoom/"

    # Zoom Team Chat incoming webhooks do not support file attachments
    attachment_support = False

    # Zoom incoming-webhook base URL
    zoom_webhook_url = "https://inbots.zoom.us/incoming/hook/{}"

    # The maximum body length for a Zoom notification
    body_maxlen = 4000

    # Maximum length for the head.text field (full mode only)
    title_maxlen = 250

    # Define object URL templates
    templates = ("{schema}://{webhook_id}/{token}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "webhook_id": {
                "name": _("Webhook ID"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "token": {
                "name": _("Verification Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": ZOOM_MODES,
                "default": ZOOM_MODE_DEFAULT,
            },
            # token= is already defined in template_tokens; this
            # alias_of entry simply advertises that ?token= is also
            # accepted as a query-string override on the URL.
            "token": {
                "alias_of": "token",
            },
        },
    )

    def __init__(self, webhook_id, token, mode=None, **kwargs):
        """Initialize Zoom Object."""
        super().__init__(**kwargs)

        # Validate our webhook ID
        self.webhook_id = validate_regex(webhook_id, r"^[A-Za-z0-9_-]+$")
        if not self.webhook_id:
            msg = (
                "A Zoom webhook ID must be specified and contain"
                " only alphanumeric, hyphen, or underscore"
                " characters."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate our verification token
        self.token = validate_regex(token)
        if not self.token:
            msg = "A Zoom verification token must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate notification mode
        if mode is None:
            # Default to full structured mode
            self.mode = ZOOM_MODE_DEFAULT

        else:
            # Allow partial prefix matching (e.g. "sim" -> "simple")
            self.mode = next(
                (m for m in ZOOM_MODES if m.startswith(mode.lower())),
                None,
            )
            if not self.mode:
                msg = "The Zoom mode ({}) is invalid.".format(mode)
                self.logger.warning(msg)
                raise TypeError(msg)

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Zoom Team Chat Notification."""

        # Build the base webhook endpoint URL
        base_url = self.zoom_webhook_url.format(
            NotifyZoom.quote(self.webhook_id, safe="")
        )

        if self.mode == ZoomMode.FULL:
            # Build the structured content object
            content = {}

            # Include the head section only when a title is present
            if title:
                content["head"] = {"text": title}

            # Always include the body section
            content["body"] = [
                {
                    "type": "message",
                    "text": body,
                }
            ]

            # Append the ?format=full query parameter
            url = "{}?format=full".format(base_url)

            # Deliver the structured payload as JSON
            return self._fetch(
                url,
                payload=dumps({"content": content}),
                content_type="application/json",
            )

        # Simple mode: plain text, title colon-prepended if provided
        text = "{}: {}".format(title, body) if title else body

        # Deliver plain text directly
        return self._fetch(base_url, payload=text)

    def _fetch(self, url, payload, content_type=None):
        """Wrapper to a Zoom webhook POST request."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Authorization": self.token,
        }

        # Set Content-Type when a structured payload is provided
        if content_type:
            headers["Content-Type"] = content_type

        self.logger.debug(
            "Zoom POST URL: {} (cert_verify={!r})".format(
                url, self.verify_certificate
            )
        )
        self.logger.debug("Zoom Payload: {!r}".format(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.no_content,
            ):
                # Report the error
                status_str = NotifyZoom.http_response_code_lookup(
                    r.status_code, ZOOM_HTTP_ERROR_MAP
                )
                self.logger.warning(
                    "Failed to send Zoom notification: {}{}error={}.".format(
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

            self.logger.info("Sent Zoom notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Zoom notification."
            )
            self.logger.debug("Socket Exception: {}".format(str(e)))
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique
        from another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.webhook_id, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified
        arguments."""

        # Always include mode so the round-trip is stable
        params = {"mode": self.mode}
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{webhook_id}/{token}/?{params}".format(
            schema=self.secure_protocol,
            webhook_id=self.pprint(self.webhook_id, privacy, safe=""),
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyZoom.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # The host holds the webhook ID
        results["webhook_id"] = NotifyZoom.unquote(results["host"])

        # The first path segment carries the verification token
        path = NotifyZoom.split_path(results["fullpath"])
        if path:
            results["token"] = NotifyZoom.unquote(path.pop(0))

        # Support ?token= override (useful with native URLs)
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyZoom.unquote(results["qsd"]["token"])

        # Support ?mode= parameter
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyZoom.unquote(results["qsd"]["mode"])

        return results

    @staticmethod
    def parse_native_url(url):
        """Support https://inbots.zoom.us/incoming/hook/WEBHOOK_ID"""
        result = re.match(
            r"^https?://inbots\.zoom\.us/incoming/hook/"
            r"(?P<webhook_id>[A-Za-z0-9_-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )
        if result:
            return NotifyZoom.parse_url(
                "{schema}://{webhook_id}/{params}".format(
                    schema=NotifyZoom.secure_protocol,
                    webhook_id=result.group("webhook_id"),
                    params=result.group("params") or "",
                )
            )
        return None
