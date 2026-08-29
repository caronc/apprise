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

# Steps to get your API Key:
#  1. Visit https://app.pingram.io/ and sign in (or create an account).
#  2. Open your Environment settings and visit the "API Keys" section.
#  3. Create a new Secret Key (server-to-server) or Public Key. It will
#     look like: pingram_sk_AbCdEf012345 or pingram_pk_AbCdEf012345
#     Newer keys carry a JWT after the prefix, so they additionally
#     contain periods, e.g. pingram_sk_aaaa.bbbb.cccc
#
#  Your Apprise URL should be assembled as:
#     pingram://{apikey}/{target}
#
# Resources:
# - https://www.pingram.io/docs/api-reference
# - https://www.pingram.io/docs/api-reference/operations/keys_createapikey

from __future__ import annotations

from email.utils import formataddr
from itertools import chain
from json import dumps, loads
import re

import requests

from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..conversion import convert_between
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_email,
    is_phone_no,
    parse_emails,
    parse_list,
    validate_regex,
)
from .base import NotifyBase

# Used to detect a recipient ID; pairing one with an email/phone target is
# always optional for a Pingram API key.
IS_VALID_ID_RE = re.compile(r"^\s*(@|%40)?(?P<id>[\w_-]+)\s*$", re.I)


class PingramRegion:
    """Regions."""

    CA = "ca"
    US = "us"
    EU = "eu"


# Pingram endpoints; the US region has no dedicated sub-domain of its own,
# it is simply the bare/default host.
PINGRAM_API_LOOKUP = {
    PingramRegion.US: "https://api.pingram.io",
    PingramRegion.CA: "https://api.ca.pingram.io",
    PingramRegion.EU: "https://api.eu.pingram.io",
}

# A List of our regions we can use for verification
PINGRAM_REGIONS = (
    PingramRegion.US,
    PingramRegion.CA,
    PingramRegion.EU,
)


class PingramChannel:
    """Channels."""

    EMAIL = "email"
    SMS = "sms"
    INAPP = "inapp"
    WEB_PUSH = "web_push"
    MOBILE_PUSH = "mobile_push"
    SLACK = "slack"
    CALL = "call"


# A List of our channels we can use for verification
PINGRAM_CHANNELS: frozenset[str] = frozenset(
    [
        PingramChannel.EMAIL,
        PingramChannel.SMS,
        PingramChannel.INAPP,
        PingramChannel.WEB_PUSH,
        PingramChannel.MOBILE_PUSH,
        PingramChannel.SLACK,
        PingramChannel.CALL,
    ]
)


class PingramMode:
    """Modes."""

    TEMPLATE = "template"
    MESSAGE = "message"


# A List of our modes we can use for verification
PINGRAM_MODES: frozenset[str] = frozenset(
    [
        PingramMode.TEMPLATE,
        PingramMode.MESSAGE,
    ]
)


class NotifyPingram(NotifyBase):
    """A wrapper for Pingram Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Pingram"

    # The services URL
    service_url = "https://www.pingram.io/"

    # The default secure protocol
    secure_protocol = "pingram"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/pingram/"

    # If no Pingram Message Type is specified, then the following is used
    default_message_type = "apprise"

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.2

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # Define object templates
    templates = (
        "{schema}://{apikey}/{targets}",
        "{schema}://{type}@{apikey}/{targets}",
    )

    # Explicit URL tokens we care about (all others from base are ignored)
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "type": {
                "name": _("Message Type"),
                "type": "string",
                "regex": (r"^[A-Z0-9_-]+$", "i"),
                "map_to": "message_type",
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "required": True,
                "private": True,
                "regex": (r"^pingram_(sk|pk)_[\w.-]+$", "i"),
            },
            "target_email": {
                "name": _("Target Email"),
                "type": "string",
                "map_to": "targets",
            },
            "target_id": {
                "name": _("Target ID"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "target_sms": {
                "name": _("Target SMS"),
                "type": "string",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
        },
    )

    # Supported query args
    template_args = dict(
        NotifyBase.template_args,
        **{
            "type": {
                "alias_of": "type",
            },
            "apikey": {
                "alias_of": "apikey",
            },
            "channels": {
                "name": _("Channels"),
                "type": "list:string",
                "values": PINGRAM_CHANNELS,
            },
            "region": {
                "name": _("Region Name"),
                "type": "choice:string",
                "values": PINGRAM_REGIONS,
                "default": PingramRegion.US,
            },
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": PINGRAM_MODES,
            },
            "reply": {
                "name": _("Reply To"),
                "type": "string",
                "map_to": "reply_to",
            },
            "from": {
                "name": _("From Email"),
                "type": "string",
                "map_to": "from_addr",
            },
            "to": {
                "alias_of": "targets",
            },
            # Email Values
            "cc": {
                "name": _("Carbon Copy"),
                "type": "list:string",
            },
            "bcc": {
                "name": _("Blind Carbon Copy"),
                "type": "list:string",
            },
        },
    )

    # Define our token control
    template_kwargs = {
        "tokens": {
            "name": _("Template Tokens"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        apikey=None,
        message_type=None,
        targets=None,
        cc=None,
        bcc=None,
        reply_to=None,
        channels=None,
        region=None,
        mode=None,
        from_addr=None,
        tokens=None,
        **kwargs,
    ):
        """Initialize Notify Pingram Object."""
        super().__init__(**kwargs)

        # Our API Key
        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = "An invalid Pingram API Key ({}) was specified.".format(
                apikey
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # For tracking our email -> name lookups
        self.names = {}

        # Prepare our From Address
        from_addr_ = [self.app_id, ""]
        self.from_addr = None
        if isinstance(from_addr, str):
            result = is_email(from_addr)
            if result:
                from_addr_ = (
                    result["name"] if result["name"] else from_addr_[0],
                    result["full_email"],
                )
            else:
                # Only update the string but use the already detected info
                from_addr_[0] = from_addr

            # Store our lookup
            self.from_addr = from_addr_[1]
        self.names[from_addr_[1]] = from_addr_[0]

        # Prepare our Reply-To Address
        self.reply_to = {}
        if isinstance(reply_to, str):
            result = is_email(reply_to)
            if result and "full_email" in result:
                self.reply_to = {
                    "senderName": result["name"]
                    if result["name"]
                    else from_addr_[0],
                    "senderEmail": result["full_email"],
                }

        # Resolve our mode
        if mode and isinstance(mode, str):
            self.mode = next(
                (a for a in PINGRAM_MODES if a.startswith(mode)), None
            )
            if self.mode not in PINGRAM_MODES:
                msg = f"The Pingram mode specified ({mode}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            # Detect mode based on whether or not a message_type was
            # provided
            self.mode = (
                PingramMode.MESSAGE
                if not message_type
                else PingramMode.TEMPLATE
            )

        if not message_type:
            # Assign a default message type
            self.message_type = self.default_message_type

        else:
            self.message_type = validate_regex(
                message_type, *self.template_tokens["type"]["regex"]
            )
            if not self.message_type:
                msg = (
                    "An invalid Pingram Message Type "
                    "({}) was specified.".format(message_type)
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Store our region
        try:
            self.region = (
                self.template_args["region"]["default"]
                if region is None
                else region.lower()
            )

            if self.region not in PINGRAM_REGIONS:
                # allow the outer except to handle this common response
                raise IndexError()

        except (AttributeError, IndexError, TypeError):
            # Invalid region specified
            msg = f"The Pingram region specified ({region}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        # Initialize an empty set of channels
        self.channels = set()
        for channel_ in parse_list(channels):
            channel = channel_.lower()
            if channel not in PINGRAM_CHANNELS:
                # Invalid channel specified
                msg = (
                    "The Pingram forced channel specified "
                    f"({channel}) is invalid."
                )
                self.logger.warning(msg)
                raise TypeError(msg) from None
            self.channels.add(channel)

        # Used for URL generation afterwards only
        self._invalid_targets = []

        # Our Targets are delimited by found ids; a recipient id is always
        # optional for a Pingram API key, so a bare email/phone number is
        # enough on its own to identify a new target.
        self.targets = []
        if targets:
            current_target = {}
            for entry in parse_list(targets, sort=False):
                result = is_email(entry)
                if result:
                    if "email" not in current_target:
                        current_target["email"] = result["full_email"]
                        if not self.channels:
                            self.channels.add(PingramChannel.EMAIL)
                            self.logger.info(
                                "The Pingram default channel of "
                                f"{PingramChannel.EMAIL} was set."
                            )
                        continue

                    # Flush our current target and start a new one; a
                    # recipient id is never required to pair with it
                    self.targets.append(current_target)
                    current_target = {"email": result["full_email"]}
                    continue

                result = is_phone_no(entry)
                if result:
                    if "number" not in current_target:
                        current_target["number"] = (
                            "+" if entry[0] == "+" else ""
                        ) + result["full"]
                        if not self.channels:
                            self.channels.add(PingramChannel.SMS)
                            self.logger.info(
                                "The Pingram default channel of "
                                f"{PingramChannel.SMS} was set."
                            )
                        continue

                    # Flush our current target and start a new one; a
                    # recipient id is never required to pair with it
                    self.targets.append(current_target)
                    current_target = {"number": result["full"]}
                    continue

                result = IS_VALID_ID_RE.match(entry)
                if result:
                    if "id" not in current_target:
                        current_target["id"] = result.group("id")
                        continue

                    # Store id in next target and move on
                    self.targets.append(current_target)
                    current_target = {"id": result.group("id")}
                    continue

                self.logger.warning(
                    f"Dropped invalid Pingram target ({entry}) specified"
                )
                self._invalid_targets.append(entry)
                continue

            if current_target:
                # Flush whatever remains; an id is never required to
                # accompany an email/phone target
                self.targets.append(current_target)

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_emails(cc):
            result = is_email(recipient)
            if result:
                self.cc.add(result["full_email"])
                if result["name"]:
                    self.names[result["full_email"]] = result["name"]
                continue

            self.logger.warning(
                "Dropped invalid Carbon Copy email ({}) specified.".format(
                    recipient
                ),
            )

        # Validate recipients (bcc:) and drop bad ones:
        for recipient in parse_emails(bcc):
            result = is_email(recipient)
            if result:
                self.bcc.add(result["full_email"])
                if result["name"]:
                    self.names[result["full_email"]] = result["name"]
                continue

            self.logger.warning(
                "Dropped invalid Blind Carbon Copy email "
                "({}) specified.".format(recipient),
            )

        # Template functionality
        self.tokens = {}
        if isinstance(tokens, dict):
            self.tokens.update(tokens)

        return

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified
        arguments."""

        # Define any URL parameters
        params = {
            "mode": self.mode,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join(
                [
                    formataddr(
                        (self.names.get(e, False), e),
                        # Swap comma for its escaped url code (if
                        # detected) since we use it as a delimiter
                        charset="utf-8",
                    ).replace(",", "%2C")
                    for e in self.cc
                ]
            )

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join(
                [
                    formataddr(
                        (self.names.get(e, False), e),
                        # Swap comma for its escaped url code (if
                        # detected) since we use it as a delimiter
                        charset="utf-8",
                    ).replace(",", "%2C")
                    for e in self.bcc
                ]
            )

        if self.reply_to:
            # Handle our Reply-To Address
            params["reply"] = formataddr(
                (self.reply_to["senderName"], self.reply_to["senderEmail"]),
                # Swap comma for its escaped url code (if detected) since
                # we're using that as a delimiter
                charset="utf-8",
            )

        if self.channels:
            # Prepare our default channel
            params["channels"] = ",".join(self.channels)

        if self.region != self.template_args["region"]["default"]:
            # Prepare our default region
            params["region"] = self.region

        # handle from=
        if self.from_addr and self.names[self.from_addr] != self.app_id:
            params["from"] = self.names[self.from_addr]

        # Store any template entries if specified
        params.update({f":{k}": v for k, v in self.tokens.items()})

        targets = []
        for target in self.targets:
            # A recipient id is always optional for a Pingram API key
            if "id" in target:
                targets.append(f"@{target['id']}")
            if "number" in target:
                targets.append(f"{target['number']}")
            if "email" in target:
                targets.append(f"{target['email']}")

        mtype = (
            f"{self.message_type}@"
            if self.message_type != self.default_message_type
            else ""
        )
        return "{schema}://{mtype}{apikey}/{targets}?{params}".format(
            schema=self.secure_protocol,
            mtype=mtype,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets=NotifyPingram.quote(
                "/".join(chain(targets, self._invalid_targets)), safe="/"
            ),
            params=NotifyPingram.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this
        notification."""

        return max(1, len(self.targets))

    def gen_payload(
        self, body, title="", notify_type=NotifyType.INFO, **kwargs
    ):
        """Generates our Pingram payload."""

        payload_ = {
            "type": self.message_type,
        }
        if self.mode == PingramMode.TEMPLATE:
            # Take a copy of our token dictionary
            parameters = self.tokens.copy()

            # Apply some defaults template values
            parameters["appBody"] = body
            parameters["appTitle"] = title
            parameters["appType"] = notify_type.value
            parameters["appId"] = self.app_id
            parameters["appDescription"] = self.app_desc
            parameters["appColor"] = self.color(notify_type)
            parameters["appImageUrl"] = self.image_url(notify_type)
            parameters["appUrl"] = self.app_url

            # A Simple Email Payload Template
            payload_.update(
                {
                    "parameters": {**parameters},
                }
            )

        else:
            # Acquire text version of body if provided
            text_body = (
                convert_between(NotifyFormat.HTML, NotifyFormat.TEXT, body)
                if self.notify_format == NotifyFormat.HTML
                else body
            )

            for channel in self.channels:
                # Python v3.10 supports `match/case` but since Apprise aims
                # to be compatible with Python v3.9+, we must use if/else
                # for the time being
                if channel == PingramChannel.SMS:
                    payload_.update(
                        {
                            PingramChannel.SMS: {
                                "message": (title + "\n" + text_body)
                                if title
                                else text_body,
                            },
                        }
                    )

                elif channel == PingramChannel.CALL:
                    payload_.update(
                        {
                            PingramChannel.CALL: {
                                "message": (title + "\n" + text_body)
                                if title
                                else text_body,
                            },
                        }
                    )

                elif channel == PingramChannel.EMAIL:
                    html_body = (
                        convert_between(
                            NotifyFormat.TEXT, NotifyFormat.HTML, body
                        )
                        if self.notify_format != NotifyFormat.HTML
                        else body
                    )

                    payload_.update(
                        {
                            PingramChannel.EMAIL: {
                                "subject": title if title else self.app_id,
                                "html": html_body,
                            },
                        }
                    )

                    if self.from_addr:
                        payload_[PingramChannel.EMAIL].update(
                            {
                                "senderEmail": self.from_addr,
                                "senderName": self.names[self.from_addr],
                            }
                        )

                elif channel == PingramChannel.INAPP:
                    payload_.update(
                        {
                            PingramChannel.INAPP: {
                                "title": title if title else self.app_id,
                                "image": self.image_url(notify_type),
                            },
                        }
                    )

                elif channel == PingramChannel.WEB_PUSH:
                    payload_.update(
                        {
                            PingramChannel.WEB_PUSH: {
                                "title": title if title else self.app_id,
                                "message": text_body,
                                "icon": self.image_url(notify_type),
                            },
                        }
                    )

                elif channel == PingramChannel.MOBILE_PUSH:
                    payload_.update(
                        {
                            PingramChannel.MOBILE_PUSH: {
                                "title": title if title else self.app_id,
                                "message": text_body,
                            },
                        }
                    )

                else:  # channel == PingramChannel.SLACK
                    payload_.update(
                        {
                            PingramChannel.SLACK: {
                                "text": (title + "\n" + text_body)
                                if title
                                else text_body,
                            },
                        }
                    )

        # Copy our list to work with
        targets = list(self.targets)
        if self.from_addr:
            payload_.update(
                {
                    "options": {
                        "email": {
                            "fromAddress": self.from_addr,
                            "fromName": self.names[self.from_addr],
                        }
                    }
                }
            )

        elif self.cc or self.bcc:
            # Set up shell
            payload_.update({"options": {"email": {}}})

        while len(targets) > 0:
            target = targets.pop(0)

            # Create a copy of our template
            payload = payload_.copy()

            # the cc, bcc, to field must be unique or the send will fail,
            # the below code prepares this by ensuring the target isn't in
            # the cc list or bcc list. It also makes sure the cc list does
            # not contain any of the bcc entries
            if "email" in target:
                cc = self.cc - self.bcc - {target["email"]}
                bcc = self.bcc - {target["email"]}

            else:
                # Assume defaults
                cc = self.cc
                bcc = self.bcc

            #
            # Prepare our 'to'
            #
            payload["to"] = {**target}

            # Support cc/bcc
            if len(cc):
                payload["options"]["email"]["ccAddresses"] = list(cc)
            if len(bcc):
                payload["options"]["email"]["bccAddresses"] = list(bcc)

            yield payload

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Pingram Notification."""

        # error tracking (used for function return)
        has_error = False

        if not self.targets:
            # There is no one to email or send an sms message to; we're
            # done
            self.logger.warning("There are no Pingram recipients to notify")
            return False

        # Prepare our URL
        url = f"{PINGRAM_API_LOOKUP[self.region]}/send"

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.apikey}",
        }

        for payload in self.gen_payload(
            body, title=title, notify_type=notify_type, **kwargs
        ):
            # A target may have no "id" (it's always optional), so fall
            # back to number/email for log messages.
            target_desc = (
                payload["to"].get("id")
                or payload["to"].get("number")
                or payload["to"].get("email")
            )

            # Perform our post
            self.logger.debug(
                "Pingram POST URL: {} (cert_verify={!r})".format(
                    url, self.verify_certificate
                )
            )
            self.logger.debug("Pingram Payload: %s", target_desc)

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
                    loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # This gets thrown if we can't parse our JSON Response
                    #  - ValueError = r.content is Unparsable
                    #  - TypeError = r.content is None
                    #  - AttributeError = r is None
                    self.logger.warning(
                        "Invalid response from Pingram server."
                    )
                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Record our failure
                    has_error = True
                    continue

                # Reference status code
                status_code = r.status_code

                if status_code not in (
                    requests.codes.ok,
                    requests.codes.accepted,
                ):
                    # We had a problem
                    status_str = NotifyPingram.http_response_code_lookup(
                        status_code
                    )

                    self.logger.warning(
                        "Failed to send Pingram notification to %s: "
                        "%s%serror=%d",
                        target_desc,
                        status_str,
                        ", " if status_str else "",
                        status_code,
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Record our failure
                    has_error = True

                else:
                    self.logger.info(
                        "Sent Pingram notification to %s.",
                        target_desc,
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Pingram "
                    "notification to %s.",
                    target_desc,
                )
                self.logger.debug("Socket Exception: {}".format(str(e)))

                # Record our failure
                has_error = True

        return not has_error

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us
        to re-instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Prepare our targets (starting with our host)
        results["targets"] = []
        if results["host"]:
            results["targets"].append(NotifyPingram.unquote(results["host"]))

        # For tracking email sources
        results["from_addr"] = None
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["from_addr"] = NotifyPingram.unquote(
                results["qsd"]["from"].rstrip()
            )

        # First element is the API Key; the rest are targets
        results["targets"] += NotifyPingram.split_path(results["fullpath"])

        # check for our api key
        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            # Store our API Key
            results["apikey"] = NotifyPingram.unquote(results["qsd"]["apikey"])

        elif results["targets"]:
            # Store our API Key
            results["apikey"] = results["targets"].pop(0)

        if "region" in results["qsd"] and len(results["qsd"]["region"]):
            results["region"] = NotifyPingram.unquote(results["qsd"]["region"])

        if "channels" in results["qsd"] and len(results["qsd"]["channels"]):
            results["channels"] = NotifyPingram.unquote(
                results["qsd"]["channels"]
            )

        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            results["mode"] = NotifyPingram.unquote(results["qsd"]["mode"])

        if "reply" in results["qsd"] and len(results["qsd"]["reply"]):
            results["reply_to"] = NotifyPingram.unquote(
                results["qsd"]["reply"]
            )

        # Handling of Message Type
        if "type" in results["qsd"] and len(results["qsd"]["type"]):
            results["message_type"] = NotifyPingram.unquote(
                results["qsd"]["type"]
            )

        elif results["user"]:
            # Pull from user
            results["message_type"] = NotifyPingram.unquote(results["user"])

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"].append(
                NotifyPingram.unquote(results["qsd"]["to"])
            )

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = NotifyPingram.unquote(results["qsd"]["cc"])

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = NotifyPingram.unquote(results["qsd"]["bcc"])

        # Store our tokens
        results["tokens"] = results["qsd:"]

        return results
