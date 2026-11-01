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

# SMSTunnel sends each text from your own Android phone, from your own
# number, so the people you notify see a number they know and can reply to.
#     https://smstunnel.io
#
#  1. Install the SMSTunnel app on your Android phone and sign in:
#       https://play.google.com/store/apps/details?id=io.smstunnel.app
#  2. Sign in at https://smstunnel.io with the same account; your phone
#     is listed under Phones.
#  3. Open Apps in the dashboard and choose Add an app.  Its key can send
#     texts (the sms:send permission).  The key starts with sk_live_.
#
#  Your Apprise URL should be assembled as:
#     smstunnel://{apikey}/{to_phone}
#     smstunnel://{apikey}/{to_phone1}/{to_phone2}/{to_phoneN}
#
#  Phone numbers should include their country code (+14155550123).  Add
#  ?country=40 to also accept local numbers such as 0712 345 678.
#
#  When more than one phone is linked to your account, ?device= picks the
#  one that sends.  Its Device ID is the "id" that the API lists for it:
#     curl -H "X-API-Key: {apikey}" https://smstunnel.io/api/v1/devices
#
#  One text is sent per phone number.  Attachments are not supported.
#
# Resources:
# - https://smstunnel.io/docs
# - https://smstunnel.io/api-reference

from __future__ import annotations

from json import dumps, loads
import re
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
SMSTUNNEL_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the phone number and the message.",
    401: "Unauthorized - The API Key is invalid or expired.",
    403: "Forbidden - The API Key or plan does not allow this text.",
    404: "Not Found - The phone (device) was not found on your account.",
    429: "Too many requests were made; try again later.",
    500: "SMSTunnel is unavailable; try again later.",
    503: "SMSTunnel is unavailable; try again later.",
}

# A country calling code such as 1, 40, +40 or 0040
IS_COUNTRY_CODE = re.compile(r"^\s*(\+|00)?(?P<code>[1-9][0-9]{0,2})\s*$")

# A phone number written with its leading + (international format)
IS_INTERNATIONAL = re.compile(r"^[\s(]*\+")


class NotifySMSTunnel(NotifyBase):
    """A wrapper for SMSTunnel Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "SMSTunnel"

    # The services URL
    service_url = "https://smstunnel.io"

    # All notification requests are secure
    secure_protocol = "smstunnel"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/smstunnel/"

    # SMSTunnel uses the http protocol with JSON requests
    notify_url = "https://smstunnel.io/api/v1/sms/send"

    # The maximum length of the body; SMSTunnel accepts up to 1600
    # characters (10 concatenated SMS)
    body_maxlen = 1600

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
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
                "regex": (r"^[a-z0-9_-]+$", "i"),
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
            "device": {
                "name": _("Device ID"),
                "type": "string",
                "regex": (r"^[a-z0-9_-]+$", "i"),
            },
            "country": {
                "name": _("Country"),
                "type": "string",
                "regex": (r"^(\+|00)?[1-9][0-9]{0,2}$", "i"),
            },
        },
    )

    def __init__(
        self,
        apikey: Optional[str] = None,
        targets: Optional[Any] = None,
        device: Optional[str] = None,
        country: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize SMSTunnel Object."""
        super().__init__(**kwargs)

        # Our API Key
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"An invalid SMSTunnel API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The phone that sends; SMSTunnel picks one when not given, and
        # so it does when the value is blank
        self.device = None
        if device and str(device).strip():
            self.device = validate_regex(
                device, *self.template_args["device"]["regex"]
            )
            if not self.device:
                msg = (
                    f"An invalid SMSTunnel Device ID ({device}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The country code that completes local phone numbers; a blank
        # value is the same as none
        self.country = None
        if country and str(country).strip():
            result = IS_COUNTRY_CODE.match(str(country))
            if not result:
                msg = (
                    f"An invalid SMSTunnel country code ({country}) was "
                    "specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.country = result.group("code")

        # The phone numbers we will notify (with their country code)
        self.targets = []

        # Anything we could not make sense of; kept for url()
        self.invalid_targets = []

        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    "Dropped invalid SMSTunnel phone # (%s) specified.",
                    target,
                )
                self.invalid_targets.append(target)
                continue

            phone = result["full"]
            if not IS_INTERNATIONAL.match(target):
                if phone.startswith("00"):
                    # 00 is the same as a leading +
                    phone = phone[2:]

                elif self.country:
                    # A local number; drop the trunk prefix (0) if present
                    # and put our country code in front of it
                    phone = self.country + (
                        phone[1:] if phone.startswith("0") else phone
                    )

                elif phone.startswith("0"):
                    self.logger.warning(
                        "Dropped local SMSTunnel phone # (%s); include its "
                        "country code or set ?country=.",
                        target,
                    )
                    self.invalid_targets.append(target)
                    continue

            self.targets.append(phone)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform SMSTunnel Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no SMSTunnel targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-Key": self.apikey,
        }

        # Prepare our payload; the phone number is filled in below as
        # SMSTunnel takes one recipient per request
        payload = {
            "to": None,
            "message": body,
        }

        if self.device:
            payload["deviceId"] = self.device

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so
            # a retry does not deliver it twice.
            if self.is_delivered(target):
                continue

            payload["to"] = f"+{target}"

            # Some Debug Logging
            self.logger.debug(
                "SMSTunnel POST URL: %s (cert_verify=%r)",
                self.notify_url,
                self.verify_certificate,
            )
            self.logger.debug("SMSTunnel Payload: %s", payload)

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

                try:
                    content = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # The response was not JSON; rely on the status code
                    content = {}

                # A successful response looks like:
                # {"success": true, "messageId": "...",
                #  "data": {"messageId": "...", "branded": false,
                #           "remaining": {...}}}
                #
                # An error response looks like:
                # {"message": "Invalid or expired API key",
                #  "error": "Unauthorized", "statusCode": 401}
                if not isinstance(content, dict):
                    content = {}

                if (
                    r.status_code != requests.codes.ok
                    or content.get("success") is False
                ):
                    # We had a problem
                    status_str = NotifySMSTunnel.http_response_code_lookup(
                        r.status_code, SMSTUNNEL_HTTP_ERROR_MAP
                    )

                    # Add SMSTunnel's own explanation when it gave one
                    reason = content.get("message") or content.get("error")
                    if isinstance(reason, list):
                        # Each refused field is listed on its own
                        reason = "; ".join(str(x) for x in reason)

                    if reason:
                        status_str = (
                            f"{status_str} {reason}" if status_str else reason
                        )

                    self.logger.warning(
                        "Failed to send SMSTunnel notification to %s: "
                        "%s%serror=%s.",
                        payload["to"],
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

                if content.get("queued"):
                    # The phone was offline; it sends the text once it
                    # is back online
                    self.logger.info(
                        "Queued SMSTunnel notification to %s until your "
                        "phone is back online.",
                        payload["to"],
                    )

                else:
                    self.logger.info(
                        "Sent SMSTunnel notification to %s.", payload["to"]
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending SMSTunnel "
                    "notification to %s.",
                    payload["to"],
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The API Key and the phone that sends identify the sender
        return (self.secure_protocol, self.apikey, self.device)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {}

        if self.device:
            params["device"] = self.device

        if self.country:
            params["country"] = self.country

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets="/".join(
                [
                    NotifySMSTunnel.quote(f"+{x}", safe="+")
                    for x in self.targets
                ]
                + [
                    NotifySMSTunnel.quote(x, safe="+")
                    for x in self.invalid_targets
                ]
            ),
            params=NotifySMSTunnel.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return 1 at least
        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our phone numbers are in the path
        results["targets"] = NotifySMSTunnel.split_path(results["fullpath"])

        if "key" in results["qsd"] and len(results["qsd"]["key"]):
            # Allow the API Key to be given as ?key= instead; the host is
            # then a phone number to notify too
            results["apikey"] = NotifySMSTunnel.unquote(results["qsd"]["key"])
            results["targets"] = [
                *NotifySMSTunnel.parse_phone_no(
                    NotifySMSTunnel.unquote(results["host"])
                ),
                *results["targets"],
            ]

        else:
            # The host is our API Key
            results["apikey"] = NotifySMSTunnel.unquote(results["host"])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifySMSTunnel.parse_phone_no(
                results["qsd"]["to"]
            )

        # The phone (device) that sends
        if "device" in results["qsd"] and len(results["qsd"]["device"]):
            results["device"] = NotifySMSTunnel.unquote(
                results["qsd"]["device"]
            )

        # The country code that completes local phone numbers
        if "country" in results["qsd"] and len(results["qsd"]["country"]):
            results["country"] = NotifySMSTunnel.unquote(
                results["qsd"]["country"]
            )

        return results
