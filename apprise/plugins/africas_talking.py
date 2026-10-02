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

# To use this plugin, you must have a Africas Talking Account setup; See here:
#  https://account.africastalking.com/
#  From here... acquire your APIKey
#
# API Details: https://developers.africastalking.com/docs/sms/sending/bulk
from __future__ import annotations

from json import loads
from typing import Any

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_phone_no,
    parse_bool,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase


class AfricasTalkingSMSMode:
    """Africas Talking SMS Mode."""

    # BulkSMS Mode
    BULKSMS = "bulksms"

    # Premium Mode
    PREMIUM = "premium"

    # Sandbox Mode
    SANDBOX = "sandbox"


# Define the types in a list for validation purposes
AFRICAS_TALKING_SMS_MODES = (
    AfricasTalkingSMSMode.BULKSMS,
    AfricasTalkingSMSMode.PREMIUM,
    AfricasTalkingSMSMode.SANDBOX,
)


# Recipient ``statusCode`` values returned inside ``SMSMessageData``.
# These are not HTTP status codes.
AFRICAS_TALKING_HTTP_ERROR_MAP = {
    100: "Processed",
    101: "Sent",
    102: "Queued",
    401: "Risk Hold",
    402: "Invalid Sender ID",
    403: "Invalid Phone Number",
    404: "Unsupported Number Type",
    405: "Insufficient Balance",
    406: "User In Blacklist",
    407: "Could Not Route",
    409: "Do Not Disturb Rejection",
    500: "Internal Server Error",
    501: "Gateway Error",
    502: "Rejected By Gateway",
}

# Recipient statusCode values meaning the message was accepted
AFRICAS_TALKING_RECIPIENT_OK = (100, 101, 102)


class NotifyAfricasTalking(NotifyBase):
    """A wrapper for Africas Talking Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Africas Talking"

    # The services URL
    service_url = "https://africastalking.com/"

    # The default secure protocol
    secure_protocol = "atalk"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/africas_talking/"

    # Africas Talking API Request URLs
    notify_url = {
        AfricasTalkingSMSMode.BULKSMS: (
            "https://api.africastalking.com/version1/messaging"
        ),
        AfricasTalkingSMSMode.PREMIUM: (
            "https://content.africastalking.com/version1/messaging"
        ),
        AfricasTalkingSMSMode.SANDBOX: (
            "https://api.sandbox.africastalking.com/version1/messaging"
        ),
    }

    # The maximum allowable characters allowed in the title per message
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 160

    # The maximum amount of phone numbers that can reside within a single
    # batch transfer
    default_batch_size = 50

    # Define object templates
    templates = ("{schema}://{appuser}@{apikey}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "appuser": {
                "name": _("App User Name"),
                "type": "string",
                "regex": (r"^[A-Z0-9_-]+$", "i"),
                "required": True,
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "required": True,
                "private": True,
                "regex": (r"^[A-Z0-9_-]+$", "i"),
            },
            "target_phone": {
                "name": _("Target Phone"),
                "type": "string",
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
            "apikey": {
                "alias_of": "apikey",
            },
            "from": {
                # Your registered short code or alphanumeric
                "name": _("From"),
                "type": "string",
                "default": "AFRICASTKNG",
                "map_to": "sender",
            },
            "mode": {
                "name": _("SMS Mode"),
                "type": "choice:string",
                "values": AFRICAS_TALKING_SMS_MODES,
                "default": AFRICAS_TALKING_SMS_MODES[0],
            },
            "to": {
                "alias_of": "targets",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
        },
    )

    def __init__(
        self,
        appuser,
        apikey,
        targets=None,
        sender=None,
        batch=None,
        mode=None,
        **kwargs,
    ):
        """Initialize Africas Talking Object."""
        super().__init__(**kwargs)

        self.appuser = validate_regex(
            appuser, *self.template_tokens["appuser"]["regex"]
        )
        if not self.appuser:
            msg = (
                f"The Africas Talking appuser specified ({appuser}) is"
                " invalid."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = (
                f"The Africas Talking apikey specified ({apikey}) is invalid."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Prepare Sender
        self.sender = (
            self.template_args["from"]["default"] if sender is None else sender
        )

        # Prepare Batch Mode Flag
        self.batch = (
            self.template_args["batch"]["default"] if batch is None else batch
        )

        self.mode = (
            self.template_args["mode"]["default"]
            if not isinstance(mode, str)
            else mode.lower()
        )

        if isinstance(mode, str) and mode:
            self.mode = next(
                (
                    a
                    for a in AFRICAS_TALKING_SMS_MODES
                    if a.startswith(mode.lower())
                ),
                None,
            )

            if self.mode not in AFRICAS_TALKING_SMS_MODES:
                msg = (
                    f"The Africas Talking mode specified ({mode}) is invalid."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)
        else:
            self.mode = self.template_args["mode"]["default"]

        # Parse our targets
        self.targets = []

        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    f"Dropped invalid phone # ({target}) specified.",
                )
                continue

            # store valid phone number
            # Carry forward '+' if defined, otherwise do not...
            self.targets.append(
                ("+" + result["full"])
                if target.lstrip()[0] == "+"
                else result["full"]
            )

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Africas Talking Notification."""

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                "There are no Africas Talking recipients to notify"
            )
            return False

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "apiKey": self.apikey,
        }

        # error tracking (used for function return)
        has_error = False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # Retry only recipients that have not accepted the message.
        pending = [t for t in self.targets if not self.is_delivered(t)]

        for index in range(0, len(pending), batch_size):
            # Our batch of phone numbers
            _batch = pending[index : index + batch_size]

            # Prepare our payload
            payload = {
                "username": self.appuser,
                "to": ",".join(_batch),
                "from": self.sender,
                "message": body,
            }

            # Acquire our URL
            notify_url = self.notify_url[self.mode]

            self.logger.debug(
                "Africas Talking POST URL:"
                f" {notify_url} (cert_verify={self.verify_certificate!r})"
            )
            self.logger.debug(f"Africas Talking Payload: {payload!s}")

            # Printable target detail
            p_target = (
                _batch[0] if batch_size == 1 else f"{len(_batch)} target(s)"
            )

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    notify_url,
                    data=payload,
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )
                # Sample response
                # {
                #     "SMSMessageData": {
                #         "Message": "Sent to 1/1 Total Cost: KES 0.8000",
                #         "Recipients": [{
                #             "statusCode": 101,
                #             "number": "+254711XXXYYY",
                #             "status": "Success",
                #             "cost": "KES 0.8000",
                #             "messageId": "ATPid_SampleTxnId123"
                #         }]
                #     }
                # }

                # The service answers with 201 Created; accept any 2xx
                if not (200 <= r.status_code < 300):
                    # We had a problem
                    status_str = (
                        NotifyAfricasTalking.http_response_code_lookup(
                            r.status_code
                        )
                    )

                    self.logger.warning(
                        "Failed to send Africas Talking notification to {}: "
                        "{}{}error={}.".format(
                            p_target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Africas Talking "
                    f"notification to {p_target}."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

            # Work out which numbers in this batch accepted the message
            delivered = self._accepted(r, _batch)

            for target in _batch:
                if target not in delivered:
                    # Mark our failure; a retry sends to it again
                    has_error = True
                    continue

                # Delivered; a retry can safely skip this recipient.
                self.mark_delivered(target)

            if delivered:
                self.logger.info(
                    "Sent Africas Talking notification to {}/{}"
                    " recipient(s).".format(len(delivered), len(_batch))
                )

        return not has_error

    def _accepted(self, r: Any, batch: list[str]) -> list[str]:
        """Return the numbers in batch the service accepted.

        - An unreadable body trusts the 2xx reply for the whole batch.
        - Otherwise a number counts only when its Recipients entry has a
          success statusCode (Processed, Sent or Queued).
        """

        try:
            content = loads(r.content)

        except (TypeError, ValueError):
            # ValueError  -- r.content is not valid JSON
            # TypeError   -- r.content is None (e.g. empty body)
            content = {}

        # Dig out our list of recipients
        data = (
            content.get("SMSMessageData")
            if isinstance(content, dict)
            else None
        )
        recipients = data.get("Recipients") if isinstance(data, dict) else None

        if not isinstance(recipients, list):
            # Nothing to inspect; the 2xx reply is all we have to go on
            return list(batch)

        # Collect the digits of every number in the reply, and of the ones
        # that were accepted
        numbers = set()
        accepted = []
        for entry in recipients:
            if not isinstance(entry, dict):
                continue

            number = "".join(
                c for c in str(entry.get("number", "")) if c.isdigit()
            ).lstrip("0")
            numbers.add(number)

            try:
                code = int(entry.get("statusCode"))

            except (TypeError, ValueError):
                code = None

            if code in AFRICAS_TALKING_RECIPIENT_OK:
                accepted.append(number)
                continue

            # Use the recipient map without changing shared HTTP messages.
            status_str = AFRICAS_TALKING_HTTP_ERROR_MAP.get(code, "")
            self.logger.warning(
                "Africas Talking rejected {}: {}{}statusCode={}.".format(
                    entry.get("number"),
                    status_str,
                    ", " if status_str else "",
                    entry.get("statusCode"),
                )
            )

        # Targets are stored as digits with an optional leading "+"
        digits = {target: target.lstrip("+0") for target in batch}

        # Targets whose own number appears in the reply, accepted or not
        exact = {t for t, d in digits.items() if d in numbers}

        result = set()
        for number in accepted:
            # An exact match always identifies the right target
            matched = [t for t, d in digits.items() if d == number]
            if not matched:
                # Replies may change local numbers to international form.
                # Match ending digits only when they identify one target.
                matched = [
                    t
                    for t, d in digits.items()
                    if t not in exact
                    and (number.endswith(d) or d.endswith(number))
                ]
                if len(matched) != 1:
                    continue

            result.update(matched)

        # Keep the batch order
        return [target for target in batch if target in result]

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.appuser, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "batch": "yes" if self.batch else "no",
        }

        if self.sender != self.template_args["from"]["default"]:
            # Set our sender if it was set
            params["from"] = self.sender

        if self.mode != self.template_args["mode"]["default"]:
            # Set our mode
            params["mode"] = self.mode

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{appuser}@{apikey}/{targets}?{params}".format(
            schema=self.secure_protocol,
            appuser=NotifyAfricasTalking.quote(self.appuser, safe=""),
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets="/".join(
                [NotifyAfricasTalking.quote(x, safe="+") for x in self.targets]
            ),
            params=NotifyAfricasTalking.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + (
                1 if targets % batch_size else 0
            )

        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The Application User ID
        results["appuser"] = NotifyAfricasTalking.unquote(results["user"])

        # Prepare our targets
        results["targets"] = []

        # Our Application APIKey
        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            # Store our apikey if specified as keyword
            results["apikey"] = NotifyAfricasTalking.unquote(
                results["qsd"]["apikey"]
            )

            # This means our host is actually a phone number (target)
            results["targets"].append(
                NotifyAfricasTalking.unquote(results["host"])
            )

        else:
            # First item is our apikey
            results["apikey"] = NotifyAfricasTalking.unquote(results["host"])

        # Store our remaining targets found on path
        results["targets"].extend(
            NotifyAfricasTalking.split_path(results["fullpath"])
        )

        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["sender"] = NotifyAfricasTalking.unquote(
                results["qsd"]["from"]
            )

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyAfricasTalking.parse_phone_no(
                results["qsd"]["to"]
            )

        # Get our Mode
        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            results["mode"] = NotifyAfricasTalking.unquote(
                results["qsd"]["mode"]
            )

        # Get Batch Mode Flag
        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch", NotifyAfricasTalking.template_args["batch"]["default"]
            )
        )

        return results
