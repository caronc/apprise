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

# Sparetext sends each text from your own Android phone or iPhone, from
# your own number, so the people you notify see a number they know and can
# reply to.
#     https://sparetext.dev
#
#  1. Sign up at https://sparetext.dev, install the Sparetext app on your
#     phone (https://sparetext.dev/download) and pair it with your account.
#  2. Open API keys in the dashboard and choose New API key.  The key
#     starts with spt_live_.
#
#  Your Apprise URL should be assembled as:
#     sparetext://{apikey}/{to_phone}
#     sparetext://{apikey}/{to_phone1}/{to_phone2}/{to_phoneN}
#
#  Write each phone number with its country code (+12025550123).  A number
#  written without one is read in the country set on your Sparetext
#  account.
#
#  When more than one phone is paired with your account, ?device= picks the
#  one that sends.  Its Device ID is the "id" that the API lists for it:
#     curl -H "x-api-key: {apikey}" https://sparetext.dev/api/v1/devices
#
#  Up to 100 phone numbers go in one request; ?batch=no sends one request
#  per phone number instead.  Attachments are not supported.
#
# Resources:
# - https://sparetext.dev/docs

from __future__ import annotations

from json import dumps, loads
import re
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

# Extend HTTP Error Messages; Sparetext's own explanation is shown instead
# whenever it gives one
SPARETEXT_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the phone numbers and the message.",
    401: "Unauthorized - The API Key is invalid, revoked or expired.",
    403: "Forbidden - The API Key is not allowed to send this text.",
    409: "Conflict - The text can not be sent right now.",
    429: "Too many requests were made; try again later.",
    503: "Sparetext is busy; try again later.",
}

# A phone number written with its leading + (international format)
IS_INTERNATIONAL = re.compile(r"^[\s(]*\+")

# The GSM-7 alphabet (GSM 03.38).  A text that keeps to it fits 160
# characters in one SMS part (153 a part once split); a single character
# outside it sends the whole text as UCS-2, at 70 characters in one part
# (67 a part once split).
GSM7_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

# The GSM-7 extension table; each of these takes the room of two
GSM7_EXTENDED = frozenset("^{}\\[~]|€")


class NotifySparetext(NotifyBase):
    """A wrapper for Sparetext Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Sparetext"

    # The services URL
    service_url = "https://sparetext.dev"

    # All notification requests are secure
    secure_protocol = "sparetext"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/sparetext/"

    # The Sparetext server the texts are handed to; ?server= can point
    # Apprise at another one (such as a test server)
    default_server = "https://sparetext.dev"

    # The path of the send endpoint on that server
    notify_path = "/api/v1/messages"

    # Sparetext takes up to 100 phone numbers in one request
    default_batch_size = 100

    # The maximum length of the body; Sparetext accepts up to 1600
    # characters in one text
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
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": True,
            },
            "server": {
                "name": _("URL"),
                "type": "string",
                "default": default_server,
                "regex": (r"^https?://[^\s/?#@]+(/[^\s?#]*)?$", "i"),
            },
        },
    )

    def __init__(
        self,
        apikey: Optional[str] = None,
        targets: Optional[Any] = None,
        device: Optional[str] = None,
        batch: Optional[bool] = None,
        server: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Sparetext Object."""
        super().__init__(**kwargs)

        # Our API Key
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"An invalid Sparetext API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The phone that sends; Sparetext uses your default phone when it is
        # not given, and so it does when the value is blank
        self.device = None
        if device and str(device).strip():
            self.device = validate_regex(
                device, *self.template_args["device"]["regex"]
            )
            if not self.device:
                msg = (
                    f"An invalid Sparetext Device ID ({device}) was specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The Sparetext server; a blank value is the same as none
        self.server = self.default_server
        if server and str(server).strip():
            result = validate_regex(
                str(server).strip(), *self.template_args["server"]["regex"]
            )
            if not result:
                msg = (
                    f"An invalid Sparetext server URL ({server}) was "
                    "specified."
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.server = result.rstrip("/")

        # Send up to 100 phone numbers in one request, or one at a time
        self.batch = (
            self.template_args["batch"]["default"]
            if batch is None
            else bool(batch)
        )

        # The phone numbers we will notify, as Sparetext reads them: with a
        # leading + when written with their country code
        self.targets = []

        # Anything we could not make sense of; kept for url()
        self.invalid_targets = []

        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    "Dropped invalid Sparetext phone # (%s) specified.",
                    target,
                )
                self.invalid_targets.append(target)
                continue

            # A number without its + is left for Sparetext to read in the
            # country set on the account, so it never reaches a stranger
            # with the same digits in another country
            self.targets.append(
                ("+" if IS_INTERNATIONAL.match(target) else "")
                + result["full"]
            )

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Sparetext Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no Sparetext targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-api-key": self.apikey,
        }

        # Our endpoint
        notify_url = self.server + self.notify_path

        # Tell how the text will be split into SMS parts; one emoji (or any
        # other character outside the GSM-7 alphabet) makes it UCS-2
        encoding, parts, outside = self.sms_parts(body)
        if outside:
            self.logger.debug(
                "Sparetext text is %s because of %s: %d part(s).",
                encoding,
                " ".join(sorted(set(outside))[:5]),
                parts,
            )

        else:
            self.logger.debug(
                "Sparetext text is %s: %d part(s).", encoding, parts
            )

        # error tracking (used for function return)
        has_error = False

        # Send in batches if identified to do so
        batch_size = self.default_batch_size if self.batch else 1

        for index in range(0, len(self.targets), batch_size):
            # The phone numbers in this request
            batch = self.targets[index : index + batch_size]

            # Skip a batch that already accepted this message so a retry
            # does not deliver it twice.
            key = tuple(batch)
            if self.is_delivered(key):
                continue

            # Prepare our payload
            payload = {
                "to": batch,
                "text": body,
            }

            if self.device:
                payload["deviceId"] = self.device

            # Some Debug Logging
            self.logger.debug(
                "Sparetext POST URL: %s (cert_verify=%r)",
                notify_url,
                self.verify_certificate,
            )
            self.logger.debug("Sparetext Payload: %s", payload)

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

                try:
                    content = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # The response was not JSON; rely on the status code
                    content = {}

                # A successful response (202) looks like:
                # {"batchId": "b_...", "messages": [{...}, ...],
                #  "estimatedCompletionAt": "2026-11-25T12:00:00.000Z",
                #  "skipped": [{"to": "+12025550123",
                #               "reason": "opted_out", ...}]}
                #
                # An error response looks like:
                # {"error": {"code": "unauthorized",
                #            "message": "Sign in or send an API key."}}
                if not isinstance(content, dict):
                    content = {}

                if r.status_code not in (
                    requests.codes.ok,
                    requests.codes.accepted,
                ):
                    # We had a problem
                    status_str = NotifySparetext.http_response_code_lookup(
                        r.status_code, SPARETEXT_HTTP_ERROR_MAP
                    )

                    # Sparetext explains each refusal in a sentence; it
                    # says more than the status code does
                    error = content.get("error")
                    if isinstance(error, dict) and error.get("message"):
                        status_str = str(error["message"]).rstrip(".")

                    self.logger.warning(
                        "Failed to send Sparetext notification to %s: "
                        "%s%serror=%s.",
                        ", ".join(batch),
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )

                    # A 429 or 503 says how long to wait before trying
                    # again; ?retry= and ?wait= do that for you
                    retry_after = r.headers.get("Retry-After")
                    if retry_after:
                        self.logger.debug(
                            "Sparetext asked to retry after %s second(s).",
                            retry_after,
                        )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                # Sparetext never texts a number on the account's opt-out
                # list (it replied STOP, or was added by hand); the others
                # in the request still get the text, so this is not
                # counted as a failure.  When every number in a request
                # opted out, Sparetext refuses it (409) instead.
                skipped = content.get("skipped")
                for entry in skipped if isinstance(skipped, list) else []:
                    if isinstance(entry, dict) and entry.get("to"):
                        self.logger.warning(
                            "Sparetext did not text %s: %s.",
                            entry["to"],
                            "it is on your opt-out list"
                            if entry.get("reason") == "opted_out"
                            else entry.get("reason") or "skipped",
                        )

                if content.get("batchId"):
                    self.logger.debug(
                        "Sparetext batch %s; the last text is expected to "
                        "go out by %s.",
                        content["batchId"],
                        content.get("estimatedCompletionAt") or "(unknown)",
                    )

                # Name the numbers Sparetext queued a text for, as it wrote
                # them (with their country code); the numbers we sent
                # otherwise
                messages = content.get("messages")
                if not isinstance(messages, list):
                    messages = []

                sent = list(
                    dict.fromkeys(
                        str(m["contact"])
                        for m in messages
                        if isinstance(m, dict) and m.get("contact")
                    )
                )
                self.logger.info(
                    "Sent Sparetext notification to %s.",
                    ", ".join(sent or batch),
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Sparetext "
                    "notification to %s.",
                    ", ".join(batch),
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this batch.
            self.mark_delivered(key)

        return not has_error

    @staticmethod
    def sms_parts(text: str) -> tuple[str, int, list[str]]:
        """Returns the encoding a text goes out in, how many SMS parts it
        takes and the characters (if any) that made it UCS-2."""

        # Sparetext sends a line break as \n alone, and trims the text
        text = text.replace("\r\n", "\n").strip()

        outside = [
            c for c in text if c not in GSM7_BASIC and c not in GSM7_EXTENDED
        ]

        if outside:
            # UCS-2 counts UTF-16 code units; an emoji takes two
            encoding, single, split = "UCS-2", 70, 67
            length = len(text.encode("utf-16-le")) // 2

        else:
            encoding, single, split = "GSM-7", 160, 153
            length = sum(2 if c in GSM7_EXTENDED else 1 for c in text)

        parts = 1 if length <= single else -(-length // split)
        return encoding, parts, outside

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The server, the API Key and the phone that sends identify the
        # sender
        return (self.secure_protocol, self.server, self.apikey, self.device)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {
            "batch": "yes" if self.batch else "no",
        }

        if self.device:
            params["device"] = self.device

        if self.server != self.default_server:
            params["server"] = self.server

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets="/".join(
                [
                    NotifySparetext.quote(x, safe="+")
                    for x in self.targets + self.invalid_targets
                ]
            ),
            params=NotifySparetext.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""

        # Each request counts once; always return 1 at least
        batch_size = self.default_batch_size if self.batch else 1
        return max(1, -(-len(self.targets) // batch_size))

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our phone numbers are in the path
        results["targets"] = NotifySparetext.split_path(results["fullpath"])

        if "key" in results["qsd"] and len(results["qsd"]["key"]):
            # Allow the API Key to be given as ?key= instead; the host is
            # then a phone number to notify too
            results["apikey"] = NotifySparetext.unquote(results["qsd"]["key"])
            results["targets"] = [
                *NotifySparetext.parse_phone_no(
                    NotifySparetext.unquote(results["host"])
                ),
                *results["targets"],
            ]

        else:
            # The host is our API Key
            results["apikey"] = NotifySparetext.unquote(results["host"])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifySparetext.parse_phone_no(
                results["qsd"]["to"]
            )

        # The phone (device) that sends
        if "device" in results["qsd"] and len(results["qsd"]["device"]):
            results["device"] = NotifySparetext.unquote(
                results["qsd"]["device"]
            )

        # The Sparetext server
        if "server" in results["qsd"] and len(results["qsd"]["server"]):
            results["server"] = NotifySparetext.unquote(
                results["qsd"]["server"]
            )

        # One request for up to 100 phone numbers, or one each
        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch", NotifySparetext.template_args["batch"]["default"]
            )
        )

        return results
