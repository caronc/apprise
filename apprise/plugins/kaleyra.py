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

# To use this service you will need a Kaleyra.io account:
#     https://www.kaleyra.io/
#
#  1. Sign in to Kaleyra.io and open the Developers section.
#  2. Copy your Account SID (e.g. HXAP16XXXXXX97IN) and create an
#     API Key.
#  3. Note the Sender ID (e.g. KLRHXA) that Kaleyra approved for your
#     account.  For two-way SMS this is your purchased phone number.
#
#  Your Apprise URL should be assembled as:
#     kaleyra://{sid}:{apikey}@{sender}/{to_phone}
#     kaleyra://{sid}:{apikey}@{sender}/{to_phone}/{to_phone}
#
#  You can shorten kaleyra:// to klr:// if you prefer.
#
#  Kaleyra hosts each account in one region.  Apprise talks to the
#  Singapore (sg) servers unless ?region= picks in (India) or eu.
#
#  Indian accounts must name a registered DLT template with
#  ?template={template_id}; the message body must then match it.
#
#  The SMS API only carries text, so attachments are not supported.
#
# Resources:
# - https://developers.kaleyra.io/docs/send-your-first-sms
# - https://developers.kaleyra.io/docs/send-bulk-sms
# - https://developers.kaleyra.io/docs/understand-route-types
# - https://developers.kaleyra.io/docs/understand-error-codes

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
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase

# Extend HTTP Error Messages
KALEYRA_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the phone numbers, sender and message.",
    401: "Unauthorized - Invalid SID or API Key, or a low balance.",
    429: "Too many requests were made.",
    500: "Kaleyra is unavailable, try again later.",
}


class KaleyraRegion:
    """The regions Kaleyra hosts accounts in."""

    # India
    IN = "in"

    # Singapore
    SG = "sg"

    # Europe
    EU = "eu"


# The API host that serves each region
KALEYRA_REGION_HOSTS = {
    KaleyraRegion.IN: "api.in.kaleyra.io",
    KaleyraRegion.SG: "api.kaleyra.io",
    KaleyraRegion.EU: "api.eu.kaleyra.io",
}

# Define our Kaleyra Regions
KALEYRA_REGIONS = tuple(KALEYRA_REGION_HOSTS.keys())


class KaleyraMessageType:
    """The route types Kaleyra accepts."""

    # The standard route outside of India
    DEFAULT = "DEFAULT"

    # Transactional messages
    TXN = "TXN"

    # Transactional messages sent outside of the DND window (India)
    TXND = "TXND"

    # Marketing
    MKT = "MKT"

    # One-time passwords
    OTP = "OTP"


# Define our Kaleyra Message Types
KALEYRA_MESSAGE_TYPES = (
    KaleyraMessageType.DEFAULT,
    KaleyraMessageType.TXN,
    KaleyraMessageType.TXND,
    KaleyraMessageType.MKT,
    KaleyraMessageType.OTP,
)


class NotifyKaleyra(NotifyBase):
    """A wrapper for Kaleyra SMS Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Kaleyra"

    # The services URL
    service_url = "https://www.kaleyra.com/"

    # The default secure protocol; klr:// is a shorter alias
    secure_protocol = ("kaleyra", "klr")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/kaleyra/"

    # Our message URL; the region host and SID are filled in at send time
    notify_url = "https://{host}/v1/{sid}/messages"

    # Kaleyra accepts up to 4000 characters and splits them into SMS parts
    body_maxlen = 4000

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # The most recipients Kaleyra accepts in one transactional request
    default_batch_size = 100

    # Define object URL templates
    templates = ("{schema}://{sid}:{apikey}@{sender}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "sid": {
                "name": _("Account SID"),
                "type": "string",
                "required": True,
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "sender": {
                "name": _("Sender ID"),
                "type": "string",
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
            "sid": {
                "alias_of": "sid",
            },
            "key": {
                "alias_of": "apikey",
            },
            "from": {
                "alias_of": "sender",
            },
            "sender": {
                "alias_of": "sender",
            },
            "region": {
                "name": _("Region"),
                "type": "choice:string",
                "values": KALEYRA_REGIONS,
                "default": KaleyraRegion.SG,
            },
            "type": {
                "name": _("Message Type"),
                "type": "choice:string",
                "values": KALEYRA_MESSAGE_TYPES,
                "map_to": "message_type",
            },
            "template": {
                "name": _("Template ID"),
                "type": "string",
            },
            "flash": {
                "name": _("Flash"),
                "type": "bool",
                "default": False,
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        sid: Optional[str] = None,
        apikey: Optional[str] = None,
        sender: Optional[str] = None,
        targets: Optional[Any] = None,
        region: Optional[str] = None,
        message_type: Optional[str] = None,
        template: Optional[str] = None,
        flash: Optional[bool] = None,
        batch: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Kaleyra Object."""
        super().__init__(**kwargs)

        # Our Account SID
        self.sid = validate_regex(sid)
        if not self.sid:
            msg = "A Kaleyra Account SID must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Our API Key
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = "A Kaleyra API Key must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The Sender ID (or two-way number) the message comes from
        self.sender = validate_regex(sender)
        if not self.sender:
            msg = "A Kaleyra Sender ID must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The region our account lives in; Singapore is the default
        self.region = (
            str(region).strip().lower()
            if region
            else self.template_args["region"]["default"]
        )
        if self.region not in KALEYRA_REGIONS:
            msg = f"The Kaleyra region specified ({region}) is invalid."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The route type is optional; Kaleyra picks one when not given
        self.message_type = None
        if message_type:
            self.message_type = str(message_type).strip().upper()
            if self.message_type not in KALEYRA_MESSAGE_TYPES:
                msg = (
                    "The Kaleyra message type specified "
                    f"({message_type}) is invalid."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # A registered (DLT) template is optional
        self.template = None
        if template:
            self.template = validate_regex(template)
            if not self.template:
                msg = (
                    "An invalid Kaleyra Template ID "
                    f"({template}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Flash messages show on screen without being stored
        self.flash = (
            self.template_args["flash"]["default"]
            if flash is None
            else bool(flash)
        )

        # Send several phone numbers in one request when batching
        self.batch = (
            self.template_args["batch"]["default"]
            if batch is None
            else bool(batch)
        )

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
                "Dropped invalid Kaleyra phone # (%s) specified.", target
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
        """Perform Kaleyra Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no Kaleyra targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-key": self.apikey,
        }

        # Prepare our URL for the region our account lives in
        url = self.notify_url.format(
            host=KALEYRA_REGION_HOSTS[self.region],
            sid=NotifyKaleyra.quote(self.sid, safe=""),
        )

        # Prepare our payload; the phone numbers are filled in below.
        # Kaleyra picks the right encoding for the text with AUTO.
        payload = {
            "to": None,
            "sender": self.sender,
            "body": body,
            "unicode": "AUTO",
        }

        # Only name a route type when one was given
        if self.message_type:
            payload["type"] = self.message_type

        # Indian accounts must match a registered template
        if self.template:
            payload["template_id"] = self.template

        if self.flash:
            payload["flash"] = "1"

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # error tracking (used for function return)
        has_error = False

        for index in range(0, len(self.targets), batch_size):
            # Skip a batch that already went out so a retry does not
            # deliver it to those recipients twice.
            if self.is_delivered(index):
                continue

            # Kaleyra takes several phone numbers separated by a comma
            targets = self.targets[index : index + batch_size]
            payload["to"] = ",".join(targets)

            self.logger.debug(
                "Kaleyra POST URL: %s (cert_verify=%r)",
                url,
                self.verify_certificate,
            )
            self.logger.debug("Kaleyra Payload: %s", payload)

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

                try:
                    content = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # The response was not JSON; rely on the status code
                    content = {}

                # A successful response looks like:
                # {"id": "ee8a...", "totalCount": 1, "data": [...],
                #  "error": {}}
                #
                # An error response looks like:
                # {"code": "E413", "message": "Invalid/incorrect inputs",
                #  "data": [], "error": {"sender": "..."}}
                if not isinstance(content, dict):
                    content = {}

                if not 200 <= r.status_code < 300 or content.get("error"):
                    # Prefer Kaleyra's own explanation when it gave one
                    status_str = content.get(
                        "message"
                    ) or NotifyKaleyra.http_response_code_lookup(
                        r.status_code, KALEYRA_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Kaleyra notification to %s: "
                        "%s%serror=%s.",
                        ", ".join(targets),
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

                self.logger.info(
                    "Sent Kaleyra notification to %s.", ", ".join(targets)
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Kaleyra "
                    "notification to %s.",
                    ", ".join(targets),
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this batch.
            self.mark_delivered(index)

        return not has_error

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Each batch is one request; always count at least 1
        batch_size = 1 if not self.batch else self.default_batch_size
        return max(1, -(-len(self.targets) // batch_size))

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The region, SID, API Key and sender identify the account
        return (
            self.secure_protocol[0],
            self.region,
            self.sid,
            self.apikey,
            self.sender,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {
            "flash": "yes" if self.flash else "no",
            "batch": "yes" if self.batch else "no",
        }

        # Only write the region when it is not the default
        if self.region != self.template_args["region"]["default"]:
            params["region"] = self.region

        if self.message_type:
            params["type"] = self.message_type.lower()

        if self.template:
            params["template"] = self.template

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{sid}:{apikey}@{sender}/{targets}?{params}".format(
            schema=self.secure_protocol[0],
            sid=NotifyKaleyra.quote(self.sid, safe=""),
            apikey=self.pprint(self.apikey, privacy, safe=""),
            sender=NotifyKaleyra.quote(self.sender, safe="+"),
            targets="/".join(
                NotifyKaleyra.quote(x, safe="+")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyKaleyra.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our Account SID and API Key
        results["sid"] = NotifyKaleyra.unquote(results["user"])
        results["apikey"] = NotifyKaleyra.unquote(results["password"])

        # The host is the Sender ID we send from
        results["sender"] = NotifyKaleyra.unquote(results["host"])

        # Our phone numbers are in the path
        results["targets"] = NotifyKaleyra.split_path(results["fullpath"])

        # Allow the Account SID to be given as ?sid= instead
        if results["qsd"].get("sid"):
            results["sid"] = NotifyKaleyra.unquote(results["qsd"]["sid"])

        # Allow the API Key to be given as ?key= instead
        if results["qsd"].get("key"):
            results["apikey"] = NotifyKaleyra.unquote(results["qsd"]["key"])

        # Support ?from= and ?sender= for the Sender ID
        if results["qsd"].get("from"):
            results["sender"] = NotifyKaleyra.unquote(results["qsd"]["from"])

        if results["qsd"].get("sender"):
            results["sender"] = NotifyKaleyra.unquote(results["qsd"]["sender"])

        # Support ?region= for where our account lives
        if results["qsd"].get("region"):
            results["region"] = NotifyKaleyra.unquote(results["qsd"]["region"])

        # Support ?type= for the route type
        if results["qsd"].get("type"):
            results["message_type"] = NotifyKaleyra.unquote(
                results["qsd"]["type"]
            )

        # Support ?template= for a registered template
        if results["qsd"].get("template"):
            results["template"] = NotifyKaleyra.unquote(
                results["qsd"]["template"]
            )

        # Support ?flash= and ?batch=
        results["flash"] = parse_bool(results["qsd"].get("flash", False))
        results["batch"] = parse_bool(results["qsd"].get("batch", False))

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyKaleyra.parse_phone_no(
                results["qsd"]["to"]
            )

        return results
