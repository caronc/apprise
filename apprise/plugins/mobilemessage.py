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


# A Mobile Message account is required:
#   https://mobilemessage.com.au/
#
#  1. Sign in to your dashboard and open Settings -> API.
#  2. Create an API key and copy its username and password.
#  3. Open Settings -> Sender IDs and choose an approved sender.
#
#  Your Apprise URL should be assembled as:
#    mobilemessage://APIUSER:APIPASS@SENDER/ToPhoneNo
#    mobilemessage://APIUSER:APIPASS@SENDER/ToPhoneNo1/ToPhoneNo2
#
# Only Australian mobiles are supported. Use 04xxxxxxxx or 614xxxxxxxx;
# other numbers are dropped before sending.
#
# API Reference:
#   https://mobilemessage.com.au/api-documentation
from __future__ import annotations

from hashlib import sha256
from json import dumps, loads
import re
from typing import Any, Optional
from uuid import uuid4

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import (
    is_phone_no,
    parse_bool,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase

# Mobile Message API errors:
# https://mobilemessage.com.au/api-documentation
MOBILEMESSAGE_HTTP_ERROR_MAP = {
    400: "Malformed request or a field failed validation.",
    401: "Invalid API credentials.",
    403: "Insufficient credit or the operation is not allowed.",
    422: "The Idempotency Key was re-used with a different payload.",
    429: "Too many requests in flight; five is the maximum.",
}

# Australian mobile numbers written in their international form
IS_AU_MOBILE = re.compile(r"^614\d{8}$")

# Tells a phone number Sender ID apart from an alphanumeric name
IS_NUMERIC_SENDER = re.compile(r"^\+?[0-9\s()-]+$")

# Character limits for one GSM-7 or Unicode message part
GSM7_PART_SIZE = 153
UCS2_PART_SIZE = 67


class NotifyMobileMessage(NotifyBase):
    """A wrapper for Mobile Message Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Mobile Message"

    # The services URL
    service_url = "https://mobilemessage.com.au/"

    # mobilemsg:// is the shorter form of the secure protocol
    secure_protocol = ("mobilemessage", "mobilemsg")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/mobilemessage/"

    # JSON API endpoint
    notify_url = "https://api.mobilemessage.com.au/v1/messages"

    # The service accepts up to 10,000 messages in a single request
    default_batch_size = 10000

    # SMS has no title field, so Apprise adds any title to the message body
    title_maxlen = 0

    # Define object templates
    templates = ("{schema}://{user}:{password}@{sender}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("API Username"),
                "type": "string",
                "required": True,
            },
            "password": {
                "name": _("API Password"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "sender": {
                "name": _("Sender ID"),
                "type": "string",
                "required": True,
                "regex": (r"^\+?[a-z0-9][a-z0-9 ()_.-]{1,19}$", "i"),
                "map_to": "source",
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
                "alias_of": "sender",
            },
            "to": {
                "alias_of": "targets",
            },
            "unicode": {
                # Keep non-GSM characters (emoji, accents) intact
                "name": _("Unicode Characters"),
                "type": "bool",
                "default": False,
            },
            "max_parts": {
                # Limit the parts and credits used by each message
                "name": _("Max Message Parts"),
                "type": "int",
                "default": 10,
                "min": 1,
                "max": 99,
            },
            "ref": {
                "name": _("Custom Reference"),
                "type": "string",
                "map_to": "ref",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": True,
            },
        },
    )

    def __init__(
        self,
        source: Optional[str] = None,
        targets: Optional[Any] = None,
        unicode: Optional[bool] = None,
        max_parts: Optional[Any] = None,
        ref: Optional[str] = None,
        batch: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Mobile Message Object."""
        super().__init__(**kwargs)

        # Basic authentication requires both API credentials
        if not (self.user and self.password):
            msg = (
                "A Mobile Message API username and password must be specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Validate the registered Sender ID
        self.source = validate_regex(
            source, *self.template_tokens["sender"]["regex"]
        )
        if not self.source:
            msg = (
                f"The Mobile Message Sender ID specified ({source}) is"
                " invalid."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        if IS_NUMERIC_SENDER.match(self.source):
            # Send numeric Sender IDs as digits only
            self.source = re.sub(r"[^\d]+", "", self.source)

        # Prepare our Unicode flag
        self.unicode = (
            self.template_args["unicode"]["default"]
            if unicode is None
            else parse_bool(unicode)
        )

        # Prepare Batch Mode Flag
        self.batch = (
            self.template_args["batch"]["default"]
            if batch is None
            else parse_bool(batch)
        )

        # How many parts a single message may be split into
        self.max_parts = self.template_args["max_parts"]["default"]
        if max_parts is not None:
            try:
                self.max_parts = int(max_parts)

            except (ValueError, TypeError):
                msg = (
                    "The Mobile Message max_parts specified"
                    f" ({max_parts}) is invalid."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg) from None

            if not (
                self.template_args["max_parts"]["min"]
                <= self.max_parts
                <= self.template_args["max_parts"]["max"]
            ):
                msg = (
                    "The Mobile Message max_parts specified"
                    f" ({max_parts}) must be between 1 and 99."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Optional reference returned by the service
        self.ref = validate_regex(ref) if ref else None

        # Parse our targets
        self.targets = []

        for target in parse_phone_no(targets):
            # Accept local numbers without the leading zero
            result = is_phone_no(target, min_len=9)
            if not result:
                self.logger.warning(
                    "Dropped invalid Mobile Message phone # (%s).",
                    target,
                )
                continue

            # Convert accepted numbers to the API's 614xxxxxxxx format
            no = result["full"]
            if no.startswith("0"):
                # Local 04xxxxxxxx form
                no = "61" + no[1:]

            elif len(no) == 9:
                # The leading zero was left off entirely
                no = "61" + no

            if not IS_AU_MOBILE.match(no):
                # Mobile Message only delivers within Australia
                self.logger.warning(
                    "Dropped non-Australian Mobile Message phone # (%s).",
                    target,
                )
                continue

            self.targets.append(no)

        return

    @property
    def body_maxlen(self) -> int:
        """Longest message the configured number of parts allows."""
        # Unicode text needs the smaller UCS-2 parts.
        part = UCS2_PART_SIZE if self.unicode else GSM7_PART_SIZE
        return self.max_parts * part

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Mobile Message Notification."""

        if not self.targets:
            self.logger.warning(
                "There are no valid Mobile Message targets to notify."
            )
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our authentication
        auth = (self.user, self.password)

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        for index in range(0, len(self.targets), batch_size):
            # The service reports on each recipient separately, so a retry
            # only has to carry the ones it has not already taken.
            targets = [
                target
                for target in self.targets[index : index + batch_size]
                if not self.is_delivered(target)
            ]

            if not targets:
                # Every recipient in this batch was taken on an earlier
                # attempt
                continue

            # One message entry per recipient
            messages = []
            for target in targets:
                entry = {
                    "to": target,
                    "message": body,
                    "sender": self.source,
                }

                if self.ref:
                    entry["custom_ref"] = self.ref

                messages.append(entry)

            # Prepare our payload
            payload = {
                "messages": messages,
                "enable_unicode": self.unicode,
                "max_parts": self.max_parts,
            }

            # Serialize once so the sent data also identifies this request.
            data = dumps(payload)

            # Identical serialized requests share the same fingerprint.
            fingerprint = sha256(data.encode("utf-8")).hexdigest()

            # Reuse the key when retrying an unanswered request so the
            # service does not send or charge for it twice.
            idempotency_key = self.recall(fingerprint)
            if idempotency_key is None:
                idempotency_key = str(uuid4())
                self.remember(fingerprint, idempotency_key)

            # Prepare our headers
            headers = {
                "User-Agent": self.app_id,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            }

            # Some Debug Logging
            self.logger.debug(
                "Mobile Message POST URL: %s (cert_verify=%s)",
                self.notify_url,
                self.verify_certificate,
            )
            # Log one representative entry instead of up to 10,000 copies.
            self.logger.debug(
                "Mobile Message Payload: %s (x%d recipient(s))",
                {**payload, "messages": messages[:1]},
                len(messages),
            )

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    self.notify_url,
                    data=data,
                    headers=headers,
                    auth=auth,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyMobileMessage.http_response_code_lookup(
                        r.status_code, MOBILEMESSAGE_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Mobile Message notification to %d"
                        " target(s): %s%serror=%s.",
                        len(targets),
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

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Mobile Message"
                    " notification to %d target(s).",
                    len(targets),
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # A body we can not read tells us nothing at all
                content = None

            # Anything but an object leaves us nothing to inspect
            content = content if isinstance(content, dict) else {}

            # A processed batch always comes back as "complete" with one
            # result per message we sent.
            results = content.get("results")
            if (
                content.get("status") != "complete"
                or not isinstance(results, list)
                or len(results) != len(targets)
            ):
                # An answer we cannot read leaves it unclear what the
                # service did, so the key stays put for a retry to reuse
                self.logger.warning(
                    "Mobile Message did not report back on every one of"
                    " the %d target(s) sent.",
                    len(targets),
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Mark our failure
                has_error = True
                continue

            # Check each recipient result for rejected messages.  A success
            # means the service took the message, not that the handset has
            # it yet.
            accepted = 0
            for target, result in zip(targets, results):
                # An entry we can not read confirms nothing, so treat it
                # the same way as a refusal
                result = result if isinstance(result, dict) else {}
                if result.get("status") == "success":
                    # Taken by the service, so a retry can skip this one
                    self.mark_delivered(target)
                    accepted += 1
                    continue

                self.logger.warning(
                    "Mobile Message did not accept %s: %s (status=%s).",
                    target,
                    result.get("error", "no reason was given"),
                    result.get("status", "unknown"),
                )

                # Mark our failure
                has_error = True

            self.logger.info(
                "Sent Mobile Message notification to %d of %d target(s).",
                accepted,
                len(targets),
            )

        return not has_error

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params: dict[str, Any] = {
            "unicode": "yes" if self.unicode else "no",
            "batch": "yes" if self.batch else "no",
            "max_parts": str(self.max_parts),
        }

        if self.ref:
            params["ref"] = self.ref

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return (
            "{schema}://{user}:{password}@{source}/{targets}?{params}".format(
                schema=self.secure_protocol[0],
                user=NotifyMobileMessage.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
                source=NotifyMobileMessage.quote(self.source, safe=""),
                targets="/".join(
                    NotifyMobileMessage.quote(x, safe="") for x in self.targets
                ),
                params=NotifyMobileMessage.urlencode(params),
            )
        )

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Return the account and sender values that identify this URL.

        Recipients do not affect the URL identity.
        """
        return (
            self.secure_protocol[0],
            self.user,
            self.password,
            self.source,
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Count requests rather than recipients when batching is enabled
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if batch_size > 1:
            targets = int(targets / batch_size) + (
                1 if targets % batch_size else 0
            )

        return max(1, targets)

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse a URL into the arguments needed to recreate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # 'from' keeps the Sender ID separate in YAML configurations
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyMobileMessage.unquote(
                results["qsd"]["from"]
            )

            # The hostname is a target in this case
            results["targets"] = [
                *NotifyMobileMessage.parse_phone_no(results["host"]),
                *NotifyMobileMessage.split_path(results["fullpath"]),
            ]

        else:
            # The hostname is our Sender ID
            results["source"] = NotifyMobileMessage.unquote(results["host"])

            # Everything left in the path is a target
            results["targets"] = NotifyMobileMessage.split_path(
                results["fullpath"]
            )

        # 'to' adds recipients from a query or YAML configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyMobileMessage.parse_phone_no(
                results["qsd"]["to"]
            )

        # Get Unicode Flag
        if "unicode" in results["qsd"] and len(results["qsd"]["unicode"]):
            results["unicode"] = parse_bool(results["qsd"]["unicode"])

        # Get Batch Mode Flag
        if "batch" in results["qsd"] and len(results["qsd"]["batch"]):
            results["batch"] = parse_bool(results["qsd"]["batch"])

        # Get our maximum message part count
        if "max_parts" in results["qsd"] and len(results["qsd"]["max_parts"]):
            results["max_parts"] = NotifyMobileMessage.unquote(
                results["qsd"]["max_parts"]
            )

        # Get our custom reference
        if "ref" in results["qsd"] and len(results["qsd"]["ref"]):
            results["ref"] = NotifyMobileMessage.unquote(results["qsd"]["ref"])

        return results
