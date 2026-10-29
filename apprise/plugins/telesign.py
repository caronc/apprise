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

# To use this service you will need a Telesign account:
#     https://www.telesign.com/
#
#  1. Sign in to the Telesign Portal:
#     https://portal.telesign.com/
#  2. Copy your Customer ID and API Key from the dashboard.
#
#  Your Apprise URL should be assembled as:
#     telesign://{customer_id}:{apikey}@{to_phone}
#     telesign://{customer_id}:{apikey}@{to_phone}/{to_phone}
#
#  The API Key often contains a slash (/); write it as %2F in the URL
#  or supply it with ?key= instead.
#
#  Telesign needs to know what kind of message is being sent.  Apprise
#  sends alerts (ARN) unless ?type= picks otp or mkt.  A Sender ID can
#  be set with ?from= once Telesign has enabled it on the account.
#
#  The SMS API only carries text, so attachments are not supported.
#
# Resources:
# - https://developer.telesign.com/enterprise/docs/sms-get-started
# - https://developer.telesign.com/enterprise/reference/sendsms
# - https://developer.telesign.com/enterprise/docs/
#       all-status-and-error-codes

from __future__ import annotations

from json import loads
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
TELESIGN_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the phone number and message.",
    401: "Unauthorized - Invalid Customer ID or API Key.",
    429: "Too many requests were made.",
    500: "Telesign is unavailable, try again later.",
}


class TelesignMessageType:
    """The kinds of message Telesign accepts."""

    # Alerts, reminders and notifications
    ARN = "ARN"

    # One-time passwords
    OTP = "OTP"

    # Marketing
    MKT = "MKT"


# Define our Telesign Message Types
TELESIGN_MESSAGE_TYPES = (
    TelesignMessageType.ARN,
    TelesignMessageType.OTP,
    TelesignMessageType.MKT,
)


class NotifyTelesign(NotifyBase):
    """A wrapper for Telesign SMS Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Telesign"

    # The services URL
    service_url = "https://www.telesign.com/"

    # The default secure protocol
    secure_protocol = "telesign"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/telesign/"

    # Our message URL
    notify_url = "https://rest-ww.telesign.com/v1/messaging"

    # Telesign accepts up to 1600 characters and splits them into SMS parts
    body_maxlen = 1600

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object URL templates
    templates = ("{schema}://{customer_id}:{apikey}@{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "customer_id": {
                "name": _("Customer ID"),
                "type": "string",
                "required": True,
                "map_to": "user",
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
                "map_to": "password",
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
            "from": {
                "name": _("Sender ID"),
                "type": "string",
                "map_to": "source",
            },
            "type": {
                "name": _("Message Type"),
                "type": "choice:string",
                "values": TELESIGN_MESSAGE_TYPES,
                "default": TelesignMessageType.ARN,
                "map_to": "message_type",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        targets: Optional[Any] = None,
        source: Optional[str] = None,
        message_type: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Telesign Object."""
        super().__init__(**kwargs)

        # Our Customer ID
        self.user = validate_regex(self.user)
        if not self.user:
            msg = "A Telesign Customer ID must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Our API Key
        self.password = validate_regex(self.password)
        if not self.password:
            msg = "A Telesign API Key must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Our message type; alerts are the default
        if message_type:
            self.message_type = next(
                (
                    t
                    for t in TELESIGN_MESSAGE_TYPES
                    if t == str(message_type).strip().upper()
                ),
                None,
            )
            if not self.message_type:
                msg = (
                    "The Telesign message type specified "
                    f"({message_type}) is invalid."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        else:
            self.message_type = self.template_args["type"]["default"]

        # The sender is optional
        self.source = source.strip() if isinstance(source, str) else None

        # The phone numbers we will notify
        self.targets = []

        # Anything we could not make sense of; kept for url()
        self.invalid_targets = []

        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if result:
                self.targets.append(result["full"])
                continue

            self.logger.warning(
                "Dropped invalid Telesign phone # (%s) specified.", target
            )
            self.invalid_targets.append(target)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Telesign Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no Telesign targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
        }

        # Our Customer ID and API Key sign in with Basic auth
        auth = (self.user, self.password)

        # Prepare our payload; the phone number is filled in below
        payload = {
            "phone_number": None,
            "message": body,
            "message_type": self.message_type,
        }

        # Only name a sender when one was given
        if self.source:
            payload["sender_id"] = self.source

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so a retry
            # does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Address this copy of our message
            payload["phone_number"] = target

            self.logger.debug(
                "Telesign POST URL: %s (cert_verify=%r)",
                self.notify_url,
                self.verify_certificate,
            )
            self.logger.debug("Telesign Payload: %s", payload)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    data=payload,
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    try:
                        content = loads(r.content)

                    except (AttributeError, TypeError, ValueError):
                        # The response was not JSON; rely on the status code
                        content = {}

                    # An error response might look like:
                    # {
                    #   "reference_id": "0123456789ABCDEF0123456789ABCDEF",
                    #   "status": {
                    #       "code": 11000,
                    #       "description": "Invalid value for parameter
                    #                       phone_number."
                    #   }
                    # }
                    status = (
                        content.get("status")
                        if isinstance(content, dict)
                        else None
                    )

                    # Prefer Telesign's own explanation when it gave one
                    status_str = (
                        status.get("description")
                        if isinstance(status, dict)
                        else None
                    ) or NotifyTelesign.http_response_code_lookup(
                        r.status_code, TELESIGN_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Telesign notification to %s: "
                        "%s%serror=%s.",
                        target,
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                self.logger.info("Sent Telesign notification to %s.", target)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Telesign "
                    "notification to %s.",
                    target,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The Customer ID and API Key identify the account
        return (self.secure_protocol, self.user, self.password)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {}

        # Only write the message type when it is not the default
        if self.message_type != self.template_args["type"]["default"]:
            params["type"] = self.message_type.lower()

        if self.source:
            params["from"] = self.source

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{user}:{apikey}@{targets}?{params}".format(
            schema=self.secure_protocol,
            user=NotifyTelesign.quote(self.user, safe=""),
            apikey=self.pprint(self.password, privacy, safe=""),
            targets="/".join(
                NotifyTelesign.quote(x, safe="+")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyTelesign.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our first phone number is in the host; the rest are in the path
        results["targets"] = (
            [NotifyTelesign.unquote(results["host"])]
            if results["host"]
            else []
        )
        results["targets"] += NotifyTelesign.split_path(results["fullpath"])

        # Allow the API Key to be given as ?key= instead
        if results["qsd"].get("key"):
            results["password"] = NotifyTelesign.unquote(results["qsd"]["key"])

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyTelesign.parse_phone_no(
                results["qsd"]["to"]
            )

        # Support ?from= for the sender
        if results["qsd"].get("from"):
            results["source"] = NotifyTelesign.unquote(results["qsd"]["from"])

        # Support ?type= for the message type
        if results["qsd"].get("type"):
            results["message_type"] = NotifyTelesign.unquote(
                results["qsd"]["type"]
            )

        return results
