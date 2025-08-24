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

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_email,
    is_phone_no,
    parse_emails,
    parse_list,
    validate_regex,
)
from .base import NotifyBase

# Valid targets:
# id:sms
# id:email
# id
IS_VALID_TARGET_RE = re.compile(
    r"^\s*(((?P<id>[\w_-]+)\s*:)?(?P<target>.+)|(?P<id2>[\w_-]+))", re.I)


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

    AUTO = "AUTO"
    EMAIL = "EMAIL"
    SMS = "SMS"


# A List of our channels we can use for verification
NOTIFICATIONAPI_CHANNELS: frozenset[str] = frozenset([
    NotificationAPIChannel.AUTO,
    NotificationAPIChannel.EMAIL,
    NotificationAPIChannel.SMS,
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
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_notificationapi"

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
        "channel": {
            "name": _("Channel"),
            "type": "choice:string",
            "values": NOTIFICATIONAPI_CHANNELS,
            "default": NotificationAPIChannel.AUTO,
        },
        "region": {
            "name": _("Region Name"),
            "type": "choice:string",
            "values": NOTIFICATIONAPI_REGIONS,
            "default": NotificationAPIRegion.US,
        },
        "base_url": {
            "name": _("Base URL Override"),
            "type": "string",
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
                 targets=None, cc=None, bcc=None, channel=None, region=None,
                 from_addr=None, tokens=None, **kwargs):
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

        # Temporary from_addr to work with for parsing
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

        # Our Targets; must be formatted as
        #  id:email or id:phone_no
        self.email_targets = []
        self.sms_targets = []
        self.id_targets = []

        if not message_type:
            # Assign a default message type
            self.message_type = self.default_message_type

        else:
            # Validate information
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

        if targets:
            # Validate recipients (to:) and drop bad ones:
            for entry in parse_list(targets):
                result = IS_VALID_TARGET_RE.match(entry)
                if not result:
                    msg = (
                        "The NotificationAPI target specified "
                        f"({entry}) is invalid.")
                    self.logger.warning(msg)
                    continue

                if result.group("id2"):
                    self.id_targets.append({
                        "id": result.group("id2"),
                    })
                    continue

                # Store our content
                uid, recipient = result.group("id"), result.group("target")

                result = is_email(recipient)
                if result:
                    self.email_targets.append({
                        "id": uid,
                        "email": result["full_email"],
                    })
                    continue

                result = is_phone_no(recipient)
                if result:
                    self.sms_targets.append({
                        "id": uid,
                        "number": result["full"],
                    })
                    continue

                msg = (
                    "The NotificationAPI target specified "
                    f"({entry}) is invalid.")
                self.logger.warning(msg)

        if channel is None:
            self.channel = NotificationAPIChannel.AUTO

        else:
            # Store our channel
            try:
                self.channel = (
                    self.template_args["channel"]["default"]
                    if channel is None else channel.upper()
                )

                if self.channel not in NOTIFICATIONAPI_CHANNELS:
                    # allow the outer except to handle this common response
                    raise IndexError()

            except (AttributeError, IndexError, TypeError):
                # Invalid channel specified
                msg = (
                    "The NotificationAPI channel specified "
                    f"({channel}) is invalid.")
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

        elif tokens:
            msg = (
                "The specified NotificationAPI Template Tokens "
                f"({tokens}) are not identified as a dictionary."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    @property
    def url_identifier(self):
        """
        Returns all of the identifiers that make this URL unique from
        another simliar one. Targets or end points should never be identified
        here.
        """
        return (self.secure_protocol[0], self.client_id, self.client_secret)

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Our URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

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

        if self.channel != self.template_args["channel"]["default"]:
            # Prepare our default channel
            params["channel"] = self.channel.lower()

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

        return "{schema}://{mtype}@{cid}/{secret}/{targets}?{params}".format(
            schema=self.secure_protocol[0],
            mtype=self.message_type,
            cid=self.pprint(self.client_id, privacy, safe=""),
            secret=self.pprint(self.client_secret, privacy, safe=""),
            targets="" if not (
                self.sms_targets or self.email_targets) else "/".join(
                chain(
                    [
                        NotifyNotificationAPI.quote(
                            "{}:{}".format(x["id"], x["email"]), safe="")
                        for x in self.email_targets],
                    [
                        NotifyNotificationAPI.quote(
                            "{}:{}".format(
                                x["id"], x["number"]), safe="")
                        for x in self.sms_targets],
                    [
                        NotifyNotificationAPI.quote(x, safe="")
                        for x["id"] in self.id_targets],
                    )),
            params=NotifyNotificationAPI.urlencode(params),
        )

    def __len__(self):
        """
        Returns the number of targets associated with this notification
        """

        return max(
            1,
            len(self.email_targets) + len(self.sms_targets)
            + len(self.id_targets))

    def gen_payload(self, body, title="", notify_type=NotifyType.INFO,
                    **kwargs):
        """
        generates our NotificationAPI payload
        """

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
        _payload = {
            "type": self.message_type,
            "parameters": {**parameters},
        }

        if self.channel != NotificationAPIChannel.AUTO:
            _payload["forceChannels"] = [self.channel]

        # Copy our list to work with
        targets = list(self.email_targets) + \
            list(self.sms_targets) + list(self.id_targets)

        if self.from_addr:
            _payload.update({
                "options": {
                    "email": {
                        "fromAddress": self.names[self.from_addr],
                        "fromName": self.from_addr}}})

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

        if not (self.email_targets or self.sms_targets):
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
                body, title="", notify_type=NotifyType.INFO, **kwargs):
            # Perform our post
            self.logger.debug(
                "NotifiationAPI POST URL: {} (cert_verify={!r})".format(
                    url, self.verify_certificate))
            self.logger.debug(
                "NotifiationAPI Payload: %s", str(payload["to"]["id"]))

            # TODO: Prepare our default response
            # response = {}

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
                    # TODO: Use response variable to assist in status
                    # handling
                    # response = loads(r.content)
                    loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # This gets thrown if we can't parse our JSON Response
                    #  - ValueError = r.content is Unparsable
                    #  - TypeError = r.content is None
                    #  - AttributeError = r is None
                    self.logger.warning(
                        "Invalid response from NotifiationAPI server.")
                    self.logger.debug(
                        "Response Details:\r\n{}".format(r.content))

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
                        "Failed to send NotifiationAPI notification to %s: "
                        "%s%serror=%d",
                        payload["to"]["id"],
                        status_str,
                        ", " if status_str else "",
                        status_code)
                    self.logger.debug(
                        "Response Details:\r\n%s", str(r.content))

                    # Record our failure
                    has_error = True

                else:
                    self.logger.info(
                        "Sent NotifiationAPI notification to %s.",
                        payload["to"]["id"])


            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending NotifiationAPI "
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
        results["targets"] = [
            NotifyNotificationAPI.unquote(results["host"])]

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

        if "channel" in results["qsd"] and len(results["qsd"]["channel"]):
            results["channel"] = \
                NotifyNotificationAPI.unquote(results["qsd"]["channel"])

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
