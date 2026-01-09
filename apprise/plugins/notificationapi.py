# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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

# Simple API Reference:
#  - https://www.notificationapi.com/docs/reference/server#send

from __future__ import annotations

import base64
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

# Used to detect ID
IS_VALID_ID_RE = re.compile(
    r"^\s*(@|%40)?(?P<id>[\w_-]+)\s*$", re.I)


class NotificationAPIRegion:
    """Regions."""

    CA = "ca"
    US = "us"
    EU = "eu"


# NotificationAPI endpoints
NOTIFICATIONAPI_API_LOOKUP = {
    NotificationAPIRegion.US: "https://api.notificationapi.com",
    NotificationAPIRegion.CA: "https://api.ca.notificationapi.com",
    NotificationAPIRegion.EU: "https://api.eu.notificationapi.com",
}

# A List of our regions we can use for verification
NOTIFICATIONAPI_REGIONS = (
    NotificationAPIRegion.US,
    NotificationAPIRegion.CA,
    NotificationAPIRegion.EU,
)


class NotificationAPIChannel:
    """Channels"""

    EMAIL = "email"
    SMS = "sms"
    INAPP = "inapp"
    WEB_PUSH = "web_push"
    MOBILE_PUSH = "mobile_push"
    SLACK = "slack"


# A List of our channels we can use for verification
NOTIFICATIONAPI_CHANNELS: frozenset[str] = frozenset([
    NotificationAPIChannel.EMAIL,
    NotificationAPIChannel.SMS,
    NotificationAPIChannel.INAPP,
    NotificationAPIChannel.WEB_PUSH,
    NotificationAPIChannel.MOBILE_PUSH,
    NotificationAPIChannel.SLACK,
])


class NotificationAPIMode:
    """Modes"""

    TEMPLATE = "template"
    MESSAGE = "message"


# A List of our channels we can use for verification
NOTIFICATIONAPI_MODES: frozenset[str] = frozenset([
    NotificationAPIMode.TEMPLATE,
    NotificationAPIMode.MESSAGE,
])


class NotifyNotificationAPI(NotifyBase):
    """
    A wrapper for NotificationAPI Notifications
    """

    # The default descriptive name associated with the Notification
    service_name = "NotificationAPI"

    # The services URL
    service_url = "https://www.notificationapi.com/"

    # The default secure protocol
    secure_protocol = ("napi", "notificationapi")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/notificationapi/"

    # If no NotificationAPI Message Type is specified, then the following is
    # used
    default_message_type = "apprise"

    # Allow 300 requests per minute.
    # 60/300 = 0.2
    request_rate_per_sec = 0.2

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # Define object templates
    templates = (
        "{schema}://{client_id}/{client_secret}/{targets}",
        "{schema}://{type}@{client_id}/{client_secret}/{targets}",
    )

    # Explicit URL tokens we care about (all others from base are ignored)
    template_tokens = dict(NotifyBase.template_tokens, **{
        "type": {
            "name": _("Message Type"),
            "type": "string",
            "regex": (r"^[A-Z0-9_-]+$", "i"),
            "required": True,
            "map_to": "message_type",
        },
        "client_id": {
            "name": _("Client ID"),
            "type": "string",
            "required": True,
        },
        "client_secret": {
            "name": _("Client Secret"),
            "type": "string",
            "required": True,
            "private": True,
        },
        "target_email": {
            "name": _("Target Email"),
            "type": "string",
            "map_to": "targets",
        },
        "target_id": {
            "name": _("Target ID"),
            "type": "string",
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
    })

    # Supported query args
    template_args = dict(NotifyBase.template_args, **{
        "type": {
            "alias_of": "type",
        },
        "channels": {
            "name": _("Channels"),
            "type": "list:string",
            "values": NOTIFICATIONAPI_CHANNELS,
        },
        "region": {
            "name": _("Region Name"),
            "type": "choice:string",
            "values": NOTIFICATIONAPI_REGIONS,
            "default": NotificationAPIRegion.US,
        },
        "mode": {
            "name": _("Mode"),
            "type": "choice:string",
            "values": NOTIFICATIONAPI_MODES,
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
        "id": {
            "alias_of": "client_id",
        },
        "secret": {
            "alias_of": "client_secret",
        }
    })

    # Define our token control
    template_kwargs = {
        "tokens": {
            "name": _("Template Tokens"),
            "prefix": ":",
        },
    }

    def __init__(self, client_id, client_secret, message_type=None,
                 targets=None, cc=None, bcc=None, reply_to=None,
                 channels=None, region=None, mode=None, from_addr=None,
                 tokens=None, **kwargs):
        """
        Initialize Notify NotificationAPI Object
        """
        super().__init__(**kwargs)

        # Client ID
        self.client_id = validate_regex(client_id)
        if not self.client_id:
            msg = "An invalid NotificationAPI Client ID " \
                  "({}) was specified.".format(client_id)
            self.logger.warning(msg)
            raise TypeError(msg)

        # Client Secret
        self.client_secret = validate_regex(client_secret)
        if not self.client_secret:
            msg = "An invalid NotificationAPI Client Secret " \
                  "({}) was specified.".format(client_secret)
            self.logger.warning(msg)
            raise TypeError(msg)

        # For tracking our email -> name lookups
        self.names = {}

        # Prepare our From Address
        _from_addr = [self.app_id, ""]
        self.from_addr = None
        if isinstance(from_addr, str):
            result = is_email(from_addr)
            if result:
                _from_addr = (
                    result["name"] if result["name"] else _from_addr[0],
                    result["full_email"])
            else:
                # Only update the string but use the already detected info
                _from_addr[0] = from_addr

                # Store our lookup
            self.from_addr = _from_addr[1]
        self.names[_from_addr[1]] = _from_addr[0]

        # Prepare our Reply-To Address
        self.reply_to = {}
        if isinstance(reply_to, str):
            result = is_email(reply_to)
            if result and "full_email" in result:
                self.reply_to = {
                    "senderName": result["name"]
                    if result["name"] else _from_addr[0],
                    "senderEmail": result["full_email"],
                }

        # Our Targets are delimited by found ids
        self.targets = []
        if mode and isinstance(mode, str):
            self.mode = next(
                (a for a in NOTIFICATIONAPI_MODES if a.startswith(mode)), None
            )
            if self.mode not in NOTIFICATIONAPI_MODES:
                msg = \
                    f"The NotificationAPI mode specified ({mode}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            # Detect mode based on whether or not a message_type was provided
            self.mode = NotificationAPIMode.MESSAGE if not message_type else \
                NotificationAPIMode.TEMPLATE

        if not message_type:
            # Assign a default message type
            self.message_type = self.default_message_type

        else:
            self.message_type = validate_regex(
                message_type, *self.template_tokens["type"]["regex"])
            if not self.message_type:
                msg = "An invalid NotificationAPI Message Type " \
                      "({}) was specified.".format(message_type)
                self.logger.warning(msg)
                raise TypeError(msg)

        # Precompute auth header
        # Ruby/docs show POST "/{client_id}/sender" with:
        #      Basic base64(client_id:client_secret)
        # https://www.notificationapi.com/docs/reference/server
        token = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()).decode("ascii")
        self.auth_header = f"Basic {token}"

        # Acquire Carbon Copies
        self.cc = set()

        # Acquire Blind Carbon Copies
        self.bcc = set()

        # Store our region
        try:
            self.region = (
                self.template_args["region"]["default"]
                if region is None else region.lower()
            )

            if self.region not in NOTIFICATIONAPI_REGIONS:
                # allow the outer except to handle this common response
                raise IndexError()

        except (AttributeError, IndexError, TypeError):
            # Invalid region specified
            msg = \
                f"The NotificationAPI region specified ({region}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        # Initialize an empty set of channels
        self.channels = set()
        for _channel in parse_list(channels):
            channel = _channel.lower()
            if channel not in NOTIFICATIONAPI_CHANNELS:
                # Invalid channel specified
                msg = (
                    "The NotificationAPI forced channel specified "
                    f"({channel}) is invalid.")
                self.logger.warning(msg)
                raise TypeError(msg) from None
            self.channels.add(channel)

        # Used for URL generation afterwards only
        self._invalid_targets = []

        if targets:
            current_target = {}
            for entry in parse_list(targets, sort=False):
                result = is_email(entry)
                if result:
                    if "email" not in current_target:
                        current_target["email"] = result["full_email"]
                        if not self.channels:
                            self.channels.add(NotificationAPIChannel.EMAIL)
                            self.logger.info(
                                "The NotificationAPI default channel of "
                                f"{NotificationAPIChannel.EMAIL} was set.")
                        continue

                    elif "id" in current_target:
                        # Store and move on
                        self.targets.append(current_target)
                        current_target = {
                            "email": result["full_email"]
                        }
                        continue

                    # if we got here, we have to many emails making it now
                    # ambiguous as to who the sender intended to notify
                    msg = (
                        "The NotificationAPI received too many emails "
                        "creating an ambiguous situation; aborted at "
                        f"'{entry}'.")
                    self.logger.warning(msg)
                    raise TypeError(msg) from None

                result = is_phone_no(entry)
                if result:
                    if "number" not in current_target:
                        current_target["number"] = \
                            ("+" if entry[0] == "+" else "") + result["full"]
                        if not self.channels:
                            self.channels.add(NotificationAPIChannel.SMS)
                            self.logger.info(
                                "The NotificationAPI default channel of "
                                f"{NotificationAPIChannel.SMS} was set.")
                        continue

                    elif "id" in current_target:
                        # Store and move on
                        self.targets.append(current_target)
                        current_target = {
                            "number": result["full"]
                        }
                        continue

                    # if we got here, we have to many emails making it now
                    # ambiguous as to who the sender intended to notify
                    msg = (
                        "The NotificationAPI received too many phone no's "
                        "creating an ambiguous situation; aborted at "
                        f"'{entry}'.")
                    self.logger.warning(msg)
                    raise TypeError(msg) from None

                result = IS_VALID_ID_RE.match(entry)
                if result:
                    if "id" not in current_target:
                        current_target["id"] = result.group("id")
                        continue

                    # Store id in next target and move on
                    self.targets.append(current_target)
                    current_target = {
                        "id": result.group("id")
                    }
                    continue

                self.logger.warning(
                    "Dropped invalid NotificationAPI target "
                    f"({entry}) specified")
                self._invalid_targets.append(entry)
                continue

            if "id" in current_target:
                # Store our final entry
                self.targets.append(current_target)
                current_target = {}

            if current_target:
                # we have email or sms, but no id to go with it
                msg = (
                    "The NotificationAPI did not detect an id to "
                    "correlate the following with {}".format(
                        str(current_target)))
                self.logger.warning(msg)
                raise TypeError(msg) from None

        # Validate recipients (cc:) and drop bad ones:
        for recipient in parse_emails(cc):
            result = is_email(recipient)
            if result:
                self.cc.add(result["full_email"])
                if result["name"]:
                    self.names[result["full_email"]] = result["name"]
                continue

            self.logger.warning(
                "Dropped invalid Carbon Copy email "
                "({}) specified.".format(recipient),
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
        """
        Returns all of the identifiers that make this URL unique from
        another similar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol[0], self.client_id, self.client_secret)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            "mode": self.mode,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if len(self.cc) > 0:
            # Handle our Carbon Copy Addresses
            params["cc"] = ",".join([
                formataddr(
                    (self.names.get(e, False), e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset="utf-8").replace(",", "%2C")
                for e in self.cc])

        if len(self.bcc) > 0:
            # Handle our Blind Carbon Copy Addresses
            params["bcc"] = ",".join([
                formataddr(
                    (self.names.get(e, False), e),
                    # Swap comma for it's escaped url code (if detected) since
                    # we're using that as a delimiter
                    charset="utf-8").replace(",", "%2C")
                for e in self.bcc])

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

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))
        # Store any template entries if specified
        params.update({f":{k}": v for k, v in self.tokens.items()})

        targets = []
        for target in self.targets:
            # ID is always present
            targets.append(f"@{target['id']}")
            if "number" in target:
                targets.append(f"{target['number']}")
            if "email" in target:
                targets.append(f"{target['email']}")

        mtype = f"{self.message_type}@" \
            if self.message_type != self.default_message_type else ""
        return "{schema}://{mtype}{cid}/{secret}/{targets}?{params}".format(
            schema=self.secure_protocol[0],
            mtype=mtype,
            cid=self.pprint(self.client_id, privacy, safe=""),
            secret=self.pprint(self.client_secret, privacy, safe=""),
            targets=NotifyNotificationAPI.quote("/".join(
                chain(targets, self._invalid_targets)), safe="/"),
            params=NotifyNotificationAPI.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """

        return max(1, len(self.targets))

    def gen_payload(self, body, title="", notify_type=NotifyType.INFO,
                    **kwargs):
        """
        generates our NotificationAPI payload
        """

        _payload = {
            "type": self.message_type,
        }
        if self.mode == NotificationAPIMode.TEMPLATE:
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
            _payload.update({
                "parameters": {**parameters},
            })

        else:
            # Acquire text version of body if provided
            text_body = convert_between(
                NotifyFormat.HTML, NotifyFormat.TEXT, body) \
                if self.notify_format == NotifyFormat.HTML else body

            for channel in self.channels:
                # Python v3.10 supports `match/case` but since Apprise aims to
                # be compatible with Python v3.9+, we must use if/else for the
                # time being
                if channel == NotificationAPIChannel.SMS:
                    _payload.update({
                        NotificationAPIChannel.SMS: {
                            "message": (title + "\n" + text_body)
                            if title else text_body,
                        },
                    })

                elif channel == NotificationAPIChannel.EMAIL:
                    html_body = convert_between(
                        NotifyFormat.TEXT, NotifyFormat.HTML, body) \
                        if self.notify_format != NotifyFormat.HTML else body

                    _payload.update({
                        NotificationAPIChannel.EMAIL: {
                            "subject": title if title else self.app_id,
                            "html": html_body,
                        },
                    })

                    if self.from_addr:
                        _payload[NotificationAPIChannel.EMAIL].update({
                            "senderEmail": self.from_addr,
                            "senderName": self.names[self.from_addr],
                        })

                elif channel == NotificationAPIChannel.INAPP:
                    _payload.update({
                        NotificationAPIChannel.INAPP: {
                            "title": title if title else self.app_id,
                            "image": self.image_url(notify_type),
                        },
                    })

                elif channel == NotificationAPIChannel.WEB_PUSH:
                    _payload.update({
                        NotificationAPIChannel.WEB_PUSH: {
                            "title": title if title else self.app_id,
                            "message": text_body,
                            "icon": self.image_url(notify_type),
                        },
                    })

                elif channel == NotificationAPIChannel.MOBILE_PUSH:
                    _payload.update({
                        NotificationAPIChannel.MOBILE_PUSH: {
                            "title": title if title else self.app_id,
                            "message": text_body,
                        },
                    })

                else:  # channel == NotificationAPIChannel.SLACK
                    _payload.update({
                        NotificationAPIChannel.SLACK: {
                            "text": (title + "\n" + text_body)
                            if title else text_body,
                        },
                    })

        # Copy our list to work with
        targets = list(self.targets)
        if self.from_addr:
            _payload.update({
                "options": {
                    "email": {
                        "fromAddress": self.from_addr,
                        "fromName": self.names[self.from_addr]}}})

        elif self.cc or self.bcc:
            # Set up shell
            _payload.update({"options": {"email": {}}})

        while len(targets) > 0:
            target = targets.pop(0)

            # Create a copy of our template
            payload = _payload.copy()

            # the cc, bcc, to field must be unique or SendMail will fail,
            # the below code prepares this by ensuring the target isn't in
            # the cc list or bcc list. It also makes sure the cc list does
            # not contain any of the bcc entries
            if "email" in target:
                cc = (self.cc - self.bcc - {target["email"]})
                bcc = (self.bcc - {target["email"]})

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
        """
        Perform NotificationAPI Notification
        """

        # error tracking (used for function return)
        has_error = False

        if not self.targets:
            # There is no one to email or send an sms message to; we're done
            self.logger.warning(
                "There are no NotificationAPI recipients to notify"
            )
            return False

        # Prepare our URL
        url = (
            f"{NOTIFICATIONAPI_API_LOOKUP[self.region]}/"
            f"{self.client_id}/sender")

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": self.auth_header,
        }

        for payload in self.gen_payload(
                body, title=title, notify_type=notify_type, **kwargs):
            # Perform our post
            self.logger.debug(
                "NotificationAPI POST URL: {} (cert_verify={!r})".format(
                    url, self.verify_certificate))
            self.logger.debug(
                "NotificationAPI Payload: %s", str(payload["to"]["id"]))

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                try:
                    loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # This gets thrown if we can't parse our JSON Response
                    #  - ValueError = r.content is Unparsable
                    #  - TypeError = r.content is None
                    #  - AttributeError = r is None
                    self.logger.warning(
                        "Invalid response from NotificationAPI server.")
                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000])

                    # Record our failure
                    has_error = True
                    continue

                # Reference status code
                status_code = r.status_code

                if status_code not in (
                        requests.codes.ok, requests.codes.accepted):
                    # We had a problem
                    status_str = \
                        NotifyNotificationAPI.http_response_code_lookup(
                            status_code)

                    self.logger.warning(
                        "Failed to send NotificationAPI notification to %s: "
                        "%s%serror=%d",
                        payload["to"]["id"],
                        status_str,
                        ", " if status_str else "",
                        status_code)

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000])

                    # Record our failure
                    has_error = True

                else:
                    self.logger.info(
                        "Sent NotificationAPI notification to %s.",
                        payload["to"]["id"])

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending NotificationAPI "
                    "notification to %s.", payload["to"]["id"])
                self.logger.debug("Socket Exception: {}".format(str(e)))

                # Record our failure
                has_error = True

        return not has_error

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Define our minimum requirements; defining them now saves us from
        # having to if/else all kinds of branches below...
        results["client_id"] = None
        results["client_secret"] = None

        # Prepare our targets (starting with our host)
        results["targets"] = []
        if results["host"]:
            results["targets"].append(
                NotifyNotificationAPI.unquote(results["host"]))

        # For tracking email sources
        results["from_addr"] = None
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["from_addr"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["from"].rstrip())

        # First 2 elements are the client_id and client_secret
        # Following are targets
        results["targets"] += \
            NotifyNotificationAPI.split_path(results["fullpath"])
        # check for our client id
        if "id" in results["qsd"] and len(results["qsd"]["id"]):
            # Store our Client ID
            results["client_id"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["id"])

        elif results["targets"]:
            # Store our Client ID
            results["client_id"] = results["targets"].pop(0)

        if "secret" in results["qsd"] and len(results["qsd"]["secret"]):
            # Store our Client Secret
            results["client_secret"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["secret"])

        elif results["targets"]:
            # Store our Client Secret
            results["client_secret"] = results["targets"].pop(0)

        if "region" in results["qsd"] and len(results["qsd"]["region"]):
            results["region"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["region"])

        if "channels" in results["qsd"] and len(results["qsd"]["channels"]):
            results["channels"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["channels"])

        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            results["mode"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["mode"])

        if "reply" in results["qsd"] and len(results["qsd"]["reply"]):
            results["reply_to"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["reply"])

        # Handling of Message Type
        if "type" in results["qsd"] and len(results["qsd"]["type"]):
            results["message_type"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["type"])

        elif results["user"]:
            # Pull from user
            results["message_type"] = \
                NotifyNotificationAPI.unquote(results["user"])

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"].append(
                NotifyNotificationAPI.unquote(results["qsd"]["to"]))

        # Handle Carbon Copy Addresses
        if "cc" in results["qsd"] and len(results["qsd"]["cc"]):
            results["cc"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["cc"])

        # Handle Blind Carbon Copy Addresses
        if "bcc" in results["qsd"] and len(results["qsd"]["bcc"]):
            results["bcc"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["bcc"])

        # Store our tokens
        results["tokens"] = results["qsd:"]

        return results
