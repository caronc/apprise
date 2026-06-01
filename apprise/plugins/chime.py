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

# Amazon Chime Incoming Webhooks
#
# To create an incoming webhook for an Amazon Chime chat room:
#  1. Open Amazon Chime and navigate to the chat room you want to
#     send notifications to.
#  2. Choose the gear icon in the top-right corner of the chat room.
#  3. Choose "Manage webhooks and bots".
#  4. Choose "Add webhook", give it a name, then choose "Create".
#  5. To copy the webhook URL, choose "Copy URL" next to your new
#     webhook in the list.
#
# The webhook URL will look something like:
#   https://hooks.chime.aws/incomingwebhooks/
#       xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx?token=AaBbCcDd%3D%3D
#
# Where the path segment after /incomingwebhooks/ is the Webhook ID
# and the ?token= query parameter is the authentication token.
#
# Your Apprise URL would be assembled as:
#   chime://{WebhookID}/{Token}
#
# For example:
#   chime://xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/AaBbCcDd%3D%3D
#
# The token value may include base64 padding characters (=). Apprise
# handles encoding automatically; you can paste the token exactly as
# it appears in the Chime webhook URL (already URL-decoded form) or
# as-is from the ?token= query parameter.
#
# References:
# - https://docs.aws.amazon.com/chime/latest/ug/webhooks.html
# - https://docs.aws.amazon.com/chime/latest/APIReference/\
#       API_CreateIncomingWebhook.html

from json import dumps
import re

import requests

from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
CHIME_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Webhook Token.",
    403: "Forbidden - Webhook has been disabled or revoked.",
    404: "Not Found - Invalid Webhook ID.",
    429: "Too many requests; rate-limit exceeded.",
}

# Amazon Chime Incoming Webhook base URL
CHIME_WEBHOOK_URL = (
    "https://hooks.chime.aws/incomingwebhooks/{webhook_id}?token={token}"
)

# Validates a Chime webhook ID (UUID-like hex string with hyphens,
# but we keep this flexible to handle any future format changes)
IS_WEBHOOK_ID = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", re.I)


class NotifyChime(NotifyBase):
    """A wrapper for Amazon Chime Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Amazon Chime"

    # The services URL
    service_url = "https://aws.amazon.com/chime/"

    # The default secure protocol
    secure_protocol = "chime"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/chime/"

    # Amazon Chime Webhook URL (used in send())
    notify_url = CHIME_WEBHOOK_URL

    # Amazon Chime webhooks support Markdown in the Content field
    notify_format = NotifyFormat.MARKDOWN

    # Chime webhooks have no native title field; title_maxlen = 0
    # causes the framework to prepend the title to the body automatically
    title_maxlen = 0

    # Maximum allowed characters in the Content field
    body_maxlen = 4096

    # Chime incoming webhooks do not support file attachments;
    # attachments can only be sent through the Chime SDK/API
    attachment_support = False

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
                "name": _("Webhook Token"),
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
            "webhook_id": {
                "alias_of": "webhook_id",
            },
            "token": {
                "alias_of": "token",
            },
        },
    )

    def __init__(self, webhook_id, token, **kwargs):
        """Initialize Amazon Chime Object."""
        super().__init__(**kwargs)

        # Validate the Webhook ID (any non-empty, non-whitespace string)
        self.webhook_id = validate_regex(webhook_id)
        if not self.webhook_id:
            msg = (
                "An invalid Amazon Chime Webhook ID "
                "({}) was specified.".format(webhook_id)
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate the Webhook Token
        self.token = validate_regex(token)
        if not self.token:
            msg = (
                "An invalid Amazon Chime Webhook Token "
                "({}) was specified.".format(token)
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Amazon Chime Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json; charset=utf-8",
        }

        # Prepare our payload; Chime webhooks accept a single Content field
        payload = {
            "Content": body,
        }

        # Construct the full webhook URL; the token must be URL-encoded
        # because it may contain base64 padding characters (=, +, /)
        notify_url = self.notify_url.format(
            webhook_id=self.webhook_id,
            token=NotifyChime.quote(self.token, safe=""),
        )

        self.logger.debug(
            "Amazon Chime POST URL: %s (cert_verify=%s)",
            notify_url,
            self.verify_certificate,
        )
        self.logger.debug("Amazon Chime Payload: %s", str(payload))

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyChime.http_response_code_lookup(
                    r.status_code, CHIME_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Amazon Chime notification: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Amazon Chime notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred posting to Amazon Chime."
            )
            self.logger.debug("Socket Exception: %s", str(e))
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.webhook_id,
            self.token,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Acquire any global URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{webhook_id}/{token}/?{params}".format(
            schema=self.secure_protocol,
            webhook_id=self.pprint(self.webhook_id, privacy, safe=""),
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyChime.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Webhook ID is in the host position
        results["webhook_id"] = NotifyChime.unquote(results["host"])

        # The token is the first entry in the URL path
        tokens = NotifyChime.split_path(results["fullpath"])
        results["token"] = tokens.pop(0) if tokens else None

        # Allow ?token= to override the path-supplied token
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyChime.unquote(results["qsd"]["token"])

        # Allow ?webhook_id= to override the host-supplied webhook ID
        if "webhook_id" in results["qsd"] and results["qsd"]["webhook_id"]:
            results["webhook_id"] = NotifyChime.unquote(
                results["qsd"]["webhook_id"]
            )

        return results

    @staticmethod
    def parse_native_url(url):
        """Support native Amazon Chime webhook URLs.

        For example:
          https://hooks.chime.aws/incomingwebhooks/
              xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx?token=AaBbCcDd%3D%3D
        """
        result = re.match(
            r"^https?://hooks\.chime\.aws/incomingwebhooks/"
            r"(?P<webhook_id>[a-z0-9][a-z0-9-]*[a-z0-9])/?"
            r"(\?.*token=(?P<token>[^&#]+).*)?$",
            url,
            re.I,
        )
        if result:
            # Unquote the token from the native URL's query string so
            # parse_url() receives the decoded form and can store it
            token = result.group("token") or ""
            return NotifyChime.parse_url(
                "{schema}://{webhook_id}/{token}".format(
                    schema=NotifyChime.secure_protocol,
                    webhook_id=result.group("webhook_id"),
                    # Re-encode so parse_url / split_path decode it once
                    token=NotifyChime.quote(
                        NotifyChime.unquote(token), safe=""
                    ),
                )
            )

        return None
