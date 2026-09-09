# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
#
# GatewayAPI Plugin
# Copyright (c) 2025, tombii
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

# To use this service you will need a GatewayAPI account
# You will need an API token
#     https://gatewayapi.com
import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase


class NotifyGatewayAPI(NotifyBase):
    """A wrapper for GatewayAPI Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "GatewayAPI"

    # The services URL
    service_url = "https://gatewayapi.com"

    # All notification requests are secure
    secure_protocol = "gatewayapi"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_gatewayapi"

    # GatewayAPI uses the http protocol with form-encoded requests
    notify_url = "https://gatewayapi.com/rest/mtsms"

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = ("{schema}://{apikey}@{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "key": {
                "alias_of": "apikey",
            },
            "to": {
                "alias_of": "targets",
            },
            "from": {
                "name": _("From Phone No/Sender"),
                "type": "string",
            },
        },
    )

    def __init__(self, apikey=None, targets=None, source=None, **kwargs):
        """Initialize GatewayAPI Object."""
        super().__init__(**kwargs)

        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate the sender (optional)
        # GatewayAPI allows:
        # - Alphanumeric: up to 11 characters
        # - Numeric only: up to 15 digits
        self.source = None
        if source:
            # Try alphanumeric format first (up to 11 chars)
            self.source = validate_regex(
                source, regex=r'^[A-Za-z0-9]{1,11}$', flags=0
            )

            if not self.source:
                # Try numeric-only format (up to 15 digits)
                self.source = validate_regex(
                    source, regex=r'^[0-9]{1,15}$', flags=0
                )

            if not self.source:
                self.logger.warning(
                    f"Invalid sender '{source}' specified. Sender must be "
                    "alphanumeric (1-11 chars) or numeric (1-15 digits). "
                    "Using default sender."
                )

        # Parse our targets
        self.targets = []

        has_error = False
        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if result:
                self.targets.append(result["full"])
                continue

            has_error = True
            self.logger.warning(
                f"Dropped invalid phone # ({target}) specified.",
            )

        if not self.targets and has_error:
            msg = "No valid phone numbers were specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform GatewayAPI Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no GatewayAPI targets to notify")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
        }

        # Prepare our payload with all recipients in a single request
        payload = {
            "message": body,
        }

        # Add all recipients using array indexing
        for idx, target in enumerate(self.targets):
            payload[f"recipients.{idx}.msisdn"] = int(target)

        # Add sender if specified
        if self.source:
            payload["sender"] = self.source

        # Some Debug Logging
        self.logger.debug(
            "GatewayAPI POST URL:"
            f" {self.notify_url} (cert_verify={self.verify_certificate})"
        )
        self.logger.debug(f"GatewayAPI Payload: {payload}")

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                auth=(self.apikey, ""),
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
            ):
                # We had a problem
                status_str = NotifyBase.http_response_code_lookup(r.status_code)

                # set up our status code to use
                status_code = r.status_code

                self.logger.warning(
                    "Failed to send GatewayAPI notification to {}: "
                    "{}{}error={}.".format(
                        ", ".join(self.targets),
                        status_str,
                        ", " if status_str else "",
                        status_code,
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                return False

            else:
                self.logger.info(
                    "Sent GatewayAPI notification to {} target(s).".format(
                        len(self.targets)
                    )
                )

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending GatewayAPI notification"
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Prepare our parameters
        params = {}

        if self.source:
            params["from"] = self.source

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}@{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, mode=PrivacyMode.Secret, safe=""),
            targets="/".join(
                [NotifyGatewayAPI.quote(f"{x}", safe="+") for x in self.targets]
            ),
            params=NotifyGatewayAPI.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""

        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get our API Key
        if results.get("user"):
            results["apikey"] = NotifyGatewayAPI.unquote(results["user"])
        elif results.get("password"):
            results["apikey"] = NotifyGatewayAPI.unquote(results["password"])

        # Support the 'key' variable
        if "key" in results["qsd"] and len(results["qsd"]["key"]):
            results["apikey"] = NotifyGatewayAPI.unquote(results["qsd"]["key"])

        # Support the 'from' variable so that we can support sender
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyGatewayAPI.unquote(results["qsd"]["from"])

        # store our targets
        results["targets"] = [
            NotifyGatewayAPI.unquote(results["host"]),
            *NotifyGatewayAPI.split_path(results["fullpath"]),
        ]

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyGatewayAPI.parse_phone_no(results["qsd"]["to"])

        return results
