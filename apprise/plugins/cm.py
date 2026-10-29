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

# To use this service you will need a CM.com account:
#     https://www.cm.com/register/
#
#  1. Sign in and open the Channels app:
#     https://www.cm.com/app/channels
#  2. Copy your Product Token from the API settings.  It looks like:
#        xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
#
#  Your Apprise URL should be assembled as:
#     cm://{token}/{to_phone}
#     cm://{sender}@{token}/{to_phone}
#
#  The sender may be a name of up to 11 letters and digits, or a phone
#  number of up to 16 digits.  Without one, "Apprise" is used.
#
#  Messages go out over SMS unless ?channels= picks others (such as
#  whatsapp or viber) that have been set up on the account.
#
#  CM.com only accepts media as a link to a file already hosted online,
#  so attachments are not supported.
#
# Resources:
# - https://developers.cm.com/messaging/docs/integration
# - https://developers.cm.com/messaging/docs/shared-features
# - https://developers.cm.com/messaging/docs/responses-errors-json

from __future__ import annotations

from json import dumps, loads
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_phone_no,
    parse_bool,
    parse_list,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase

# Extend HTTP Error Messages
CM_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the product token and phone numbers.",
    405: "Method Not Allowed.",
    500: "Unknown Error.",
}

# The channels that can reach a phone number, mapped to the spelling the
# CM.com API expects
# Based on: https://developers.cm.com/messaging/docs/shared-features
CM_CHANNELS = {
    "sms": "SMS",
    "whatsapp": "WhatsApp",
    "viber": "Viber",
    "rcs": "RCS",
}

# Used when no channels are specified
CM_CHANNEL_DEFAULT = ("sms",)

# The most SMS parts CM.com recommends joining into one message
CM_MAX_PARTS = 8


class NotifyCM(NotifyBase):
    """A wrapper for CM.com Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "CM.com"

    # The services URL
    service_url = "https://www.cm.com/"

    # The default secure protocol
    secure_protocol = "cm"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/cm/"

    # Our global messaging gateway
    notify_url = "https://gw.messaging.cm.com/v1.0/message"

    # Eight joined SMS parts of 153 characters each
    body_maxlen = 1224

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The most recipients CM.com recommends placing in one request
    default_batch_size = 1000

    # Define object URL templates
    templates = (
        "{schema}://{token}/{targets}",
        "{schema}://{source}@{token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Product Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (
                    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
                    r"[a-f0-9]{4}-[a-f0-9]{12}$",
                    "i",
                ),
            },
            "source": {
                "name": _("Sender ID"),
                "type": "string",
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
            "token": {
                "alias_of": "token",
            },
            "from": {
                "alias_of": "source",
            },
            "to": {
                "alias_of": "targets",
            },
            "channels": {
                "name": _("Channels"),
                "type": "list:string",
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
        token: str,
        source: Optional[str] = None,
        targets: Optional[Any] = None,
        channels: Optional[Any] = None,
        batch: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize CM.com Object."""
        super().__init__(**kwargs)

        # Our Product Token
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid CM.com Product Token ({token}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The sender is optional and may be a name or a phone number
        self.source = (
            source.strip()
            if isinstance(source, str) and source.strip()
            else None
        )

        # Prepare Batch Mode Flag
        self.batch = (
            self.template_args["batch"]["default"]
            if batch is None
            else parse_bool(batch)
        )

        # The channels CM.com may deliver our message over
        self.channels = []
        for channel in parse_list(channels) or CM_CHANNEL_DEFAULT:
            # Channel names are matched without regard to case
            channel = channel.lower()
            if channel not in CM_CHANNELS:
                msg = f"An invalid CM.com channel ({channel}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            # Each channel only needs to be listed once
            if channel not in self.channels:
                self.channels.append(channel)

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
                "Dropped invalid CM.com phone # (%s) specified.", target
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
        """Perform CM.com Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no CM.com targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "X-CM-PRODUCTTOKEN": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # The channel names as the API spells them
        allowed_channels = [CM_CHANNELS[c] for c in self.channels]

        # error tracking (used for function return)
        has_error = False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        for index in range(0, len(self.targets), batch_size):
            # CM.com reports on each recipient separately, so a retry only
            # has to carry the ones it has not already taken.
            targets = [
                target
                for target in self.targets[index : index + batch_size]
                if not self.is_delivered(target)
            ]

            if not targets:
                # Every recipient in this batch was taken on an earlier
                # attempt
                continue

            # CM.com wants each number as 00 followed by the country code.
            # Keep the original so the response can be matched back to it.
            recipients = {f"00{target}": target for target in targets}

            # Prepare our payload
            payload = {
                "messages": {
                    "msg": [
                        {
                            "allowedChannels": allowed_channels,
                            "from": self.source or self.app_id,
                            "to": [{"number": no} for no in recipients],
                            "body": {"type": "auto", "content": body},
                            "minimumNumberOfMessageParts": 1,
                            "maximumNumberOfMessageParts": CM_MAX_PARTS,
                        }
                    ]
                }
            }

            self.logger.debug(
                "CM.com POST URL: %s (cert_verify=%r)",
                self.notify_url,
                self.verify_certificate,
            )
            self.logger.debug("CM.com Payload: %s", payload)

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

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending CM.com "
                    "notification to %d target(s).",
                    len(targets),
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            try:
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # The response was not JSON; rely on the status code
                content = None

            # Anything but an object leaves us nothing to inspect
            content = content if isinstance(content, dict) else {}

            if r.status_code != requests.codes.ok:
                # The whole request was refused
                status_str = content.get(
                    "details"
                ) or NotifyCM.http_response_code_lookup(
                    r.status_code, CM_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send CM.com notification to %d target(s): "
                    "%s%serror=%s.",
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

            # The response might look like:
            # {
            #   "details": "Created 1 message(s)",
            #   "errorCode": 201,
            #   "messages": [{
            #       "to": "00447911123456",
            #       "status": "Rejected",
            #       "reference": null,
            #       "parts": 0,
            #       "messageDetails": "Gsm '00447911' is not a number.",
            #       "messageErrorCode": 303
            #   }]
            # }
            if not content.get("errorCode"):
                # An errorCode of 0 means every recipient was taken
                for target in targets:
                    self.mark_delivered(target)

                self.logger.info(
                    "Sent CM.com notification to %d target(s).", len(targets)
                )
                continue

            # Some recipients were refused, so look at each one
            messages = content.get("messages")
            results = {
                m.get("to"): m
                for m in (messages if isinstance(messages, list) else [])
                if isinstance(m, dict)
            }

            for no, target in recipients.items():
                # A recipient missing from the response confirms nothing,
                # so treat it the same way as a refusal
                result = results.get(no, {})
                if result.get("messageErrorCode") == 0:
                    # Taken by CM.com, so a retry can skip this one
                    self.mark_delivered(target)
                    self.logger.info("Sent CM.com notification to %s.", target)
                    continue

                self.logger.warning(
                    "CM.com did not accept %s: %s",
                    target,
                    result.get("messageDetails")
                    or content.get("details")
                    or "no reason was given",
                )

                # Mark our failure
                has_error = True

        return not has_error

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

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The Product Token identifies the account
        return (self.secure_protocol, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {
            "channels": ",".join(self.channels),
            "batch": "yes" if self.batch else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{source}{token}/{targets}?{params}".format(
            schema=self.secure_protocol,
            source=(
                "{}@".format(NotifyCM.quote(self.source, safe=""))
                if self.source
                else ""
            ),
            token=self.pprint(self.token, privacy, safe=""),
            targets="/".join(
                NotifyCM.quote(x, safe="+")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyCM.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our Product Token is the hostname
        results["token"] = NotifyCM.unquote(results["host"])

        # Allow the Product Token to be given as ?token= instead
        if results["qsd"].get("token"):
            results["token"] = NotifyCM.unquote(results["qsd"]["token"])

        # The sender sits before the Product Token
        if results["user"]:
            results["source"] = NotifyCM.unquote(results["user"])

        # Support ?from= for the sender
        if results["qsd"].get("from"):
            results["source"] = NotifyCM.unquote(results["qsd"]["from"])

        # Our phone numbers are in the path
        results["targets"] = NotifyCM.split_path(results["fullpath"])

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyCM.parse_phone_no(results["qsd"]["to"])

        # Support ?channels= for the delivery channels
        if results["qsd"].get("channels"):
            results["channels"] = NotifyCM.unquote(results["qsd"]["channels"])

        # Get Batch Mode Flag
        if results["qsd"].get("batch"):
            results["batch"] = parse_bool(results["qsd"]["batch"])

        return results
