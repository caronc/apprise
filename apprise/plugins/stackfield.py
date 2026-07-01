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

# Setting up a Stackfield incoming webhook:
#  1. Log into Stackfield at https://www.stackfield.com
#  2. Open the Room you want to receive notifications in
#  3. Go to Room Settings > Integrations > Add a new WebHook
#  4. Select "Chat Message" and click "Create Webhook"
#  5. Name the webhook (e.g. "Apprise") and click "Save and Generate URL"
#  6. Copy the webhook URL -- it will look like:
#       https://www.stackfield.com/apiwh/
#           e5a1cfbd-970e-45a1-b81c-3e004f9bdab5
#                   |-- webhook token (UUID) --|
#
#  Your Apprise URL for this plugin:
#     stackfield://e5a1cfbd-970e-45a1-b81c-3e004f9bdab5
#
# API Reference:
#   - https://www.stackfield.com/developer-api

from json import dumps
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex
from .base import NotifyBase


class NotifyStackfield(NotifyBase):
    """A wrapper for Stackfield Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Stackfield"

    # The services URL
    service_url = "https://www.stackfield.com/"

    # The default secure protocol
    secure_protocol = "stackfield"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/stackfield/"

    # Stackfield incoming webhook base URL
    notify_url = "https://www.stackfield.com/apiwh/{token}"

    # Stackfield allows at most one request per second
    request_rate_per_sec = 1

    # No native title field; framework merges title into body
    title_maxlen = 0

    # Maximum message length for a Stackfield chat message
    body_maxlen = 4000

    # Define object URL templates
    templates = ("{schema}://{token}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Webhook Token"),
                "type": "string",
                "private": True,
                "required": True,
                # Stackfield webhook tokens are standard UUIDs
                "regex": (
                    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}"
                    r"-[a-f0-9]{4}-[a-f0-9]{12}$",
                    "i",
                ),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            # token= allows the webhook UUID to be supplied as a
            # query-string argument in config files
            "token": {
                "alias_of": "token",
            },
        },
    )

    def __init__(self, token, **kwargs):
        """Initialize Stackfield Object."""
        super().__init__(**kwargs)

        # Validate our webhook token (UUID format)
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = (
                f"An invalid Stackfield webhook token ({token}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Stackfield Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Prepare our payload; "Title" is the chat message content
        payload = {
            "Title": body,
        }

        # Prepare our URL
        url = self.notify_url.format(token=self.token)

        self.logger.debug(
            "Stackfield POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Stackfield Payload: %r", payload)

        # Always call throttle before any remote server i/o is made
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
                # We had a failure
                status_str = NotifyStackfield.http_response_code_lookup(
                    r.status_code
                )
                self.logger.warning(
                    "Failed to send Stackfield notification:"
                    " {}{}error={}.".format(
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

            self.logger.info("Sent Stackfield notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Stackfield notification."
            )
            self.logger.debug("Socket Exception: %s", e)

            # Return; we're done
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(
                self.token, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            params=NotifyStackfield.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Allow the token to be supplied as a query-string argument too,
        # which is convenient when using YAML configuration files
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyStackfield.unquote(
                results["qsd"]["token"]
            )

        else:
            results["token"] = NotifyStackfield.unquote(results["host"])

        return results

    @staticmethod
    def parse_native_url(url):
        """Support https://www.stackfield.com/apiwh/TOKEN"""

        result = re.match(
            r"^https?://(?:www\.)?stackfield\.com/apiwh/"
            r"(?P<token>[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}"
            r"-[a-f0-9]{4}-[a-f0-9]{12})/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )
        if result:
            return NotifyStackfield.parse_url(
                "{schema}://{token}/{params}".format(
                    schema=NotifyStackfield.secure_protocol,
                    token=result.group("token"),
                    params=result.group("params") or "",
                )
            )

        return None
