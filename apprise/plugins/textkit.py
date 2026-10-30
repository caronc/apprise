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
# Create an account https://www.seven.io if you don't already have one

# To use this service you will need a TextKit account:
#     https://jointextkit.com
#
#  1. Sign in to the console and create an API key:
#     https://jointextkit.com/console
#  2. Keys start with ssms_sk_. A test key (ssms_sk_test_) simulates each
#     send, so nothing reaches a phone until you use a live key.
#
#  Your Apprise URL should be assembled as:
#     textkit://{apikey}/{to_phone}
#     textkit://{apikey}/{to_phone1}/{to_phone2}/{to_phoneN}
#     textkit://{apikey}/{to_phone}?from={from_phone}
#
#  Phone numbers must include the country code. ?from= is optional when
#  your account has one number. It also accepts a sender pool id (pool_...).
#
#  The API only carries text, so attachments are not supported.
#
# Resources:
# - https://jointextkit.com/docs/quickstart
# - https://api.jointextkit.com/v1/openapi.yaml

from __future__ import annotations

from json import dumps, loads
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
TEXTKIT_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the phone number and message.",
    401: "Unauthorized - Invalid API Key.",
    402: "The account does not have enough credits.",
    403: "The message was refused by a send check.",
    429: "Too many requests were made.",
    502: "The carrier rejected the message.",
    503: "TextKit is unavailable, try again later.",
}


class NotifyTextKit(NotifyBase):
    """A wrapper for TextKit SMS Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "TextKit"

    # The services URL
    service_url = "https://jointextkit.com"

    # The default secure protocol
    secure_protocol = "textkit"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/textkit/"

    # Our message URL
    notify_url = "https://api.jointextkit.com/v1/messages"

    # TextKit accepts up to 1600 characters in a message
    body_maxlen = 1600

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object URL templates
    templates = ("{schema}://{apikey}/{targets}",)

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
            "from": {
                "name": _("Originating Address"),
                "type": "string",
                "map_to": "source",
            },
            "source": {
                "alias_of": "from",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        apikey: Optional[str] = None,
        targets: Optional[Any] = None,
        source: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize TextKit Object."""
        super().__init__(**kwargs)

        # Our API Key
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid TextKit API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The sender is optional and is a phone number or a sender pool id
        self.source = source.strip() if isinstance(source, str) else None
        if self.source:
            result = is_phone_no(self.source)
            if result:
                self.source = f"+{result['full']}"

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
                "Dropped invalid TextKit phone # (%s) specified.", target
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
        """Perform TextKit Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no TextKit targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.apikey}",
        }

        # Prepare our payload; the phone number is filled in below
        payload = {
            "to": None,
            "body": body,
        }

        # Only name a sender when one was given
        if self.source:
            payload["from"] = self.source

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so a retry
            # does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Address this copy of our message
            payload["to"] = f"+{target}"

            self.logger.debug(
                "TextKit POST URL: %s (cert_verify=%r)",
                self.notify_url,
                self.verify_certificate,
            )
            self.logger.debug("TextKit Payload: %s", payload)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                # 201 is a sent message; 202 is one TextKit has accepted and
                # will send shortly, such as one held for quiet hours.
                if r.status_code not in (
                    requests.codes.created,
                    requests.codes.accepted,
                ):
                    # We had a problem
                    try:
                        # An error response looks like:
                        # {
                        #   "error": {
                        #     "code": "invalid_api_key",
                        #     "message": "Missing or malformed API key.",
                        #     "request_id": "req_BmTiQmFzCG4hFB7BR160"
                        #   }
                        # }
                        error = loads(r.content)["error"]["message"]

                    except (
                        AttributeError,
                        KeyError,
                        TypeError,
                        ValueError,
                    ):
                        # The response was not ours; rely on the status code
                        error = NotifyTextKit.http_response_code_lookup(
                            r.status_code, TEXTKIT_HTTP_ERROR_MAP
                        )

                    self.logger.warning(
                        "Failed to send TextKit notification to %s: "
                        "%s%serror=%d.",
                        target,
                        error,
                        ", " if error else "",
                        r.status_code,
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                self.logger.info("Sent TextKit notification to %s.", target)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending TextKit "
                    "notification to %s.",
                    target,
                )
                self.logger.debug("Socket Exception: %s", e)

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}
        if self.source:
            params["from"] = self.source

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(
                self.apikey, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            targets="/".join(
                NotifyTextKit.quote(x, safe="")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyTextKit.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The hostname is our API Key
        results["apikey"] = NotifyTextKit.unquote(results["host"])

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results["targets"] = NotifyTextKit.split_path(results["fullpath"])

        # Support the 'to' variable so that we can support targets this way
        # too. The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyTextKit.parse_phone_no(
                results["qsd"]["to"]
            )

        # Support the 'from' and 'source' variables
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyTextKit.unquote(results["qsd"]["from"])

        elif "source" in results["qsd"] and len(results["qsd"]["source"]):
            results["source"] = NotifyTextKit.unquote(results["qsd"]["source"])

        return results
