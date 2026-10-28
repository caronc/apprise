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

# To use this service you will need an Infobip account:
#     https://www.infobip.com/signup
#
#  1. Sign in and open the API Keys page:
#     https://portal.infobip.com/dev/api-keys
#  2. Create an API key that has the "sms:message:send" scope.
#  3. Find your personal Base URL; it is shown at the top of the
#     Infobip API documentation once you are signed in.  It looks like:
#        xxxxxx.api.infobip.com
#
#  Your Apprise URL should be assembled as:
#     infobip://{apikey}@{base_url}/{to_phone}
#
#  Only the first part of the Base URL (the xxxxxx part) is needed; the
#  rest is filled in for you.  A sender name or number can be set with
#  ?from=; without one, Infobip picks a sender for you.
#
#  SMS has no way to carry files, so attachments are not supported.
#
# Resources:
# - https://www.infobip.com/docs/essentials/api-essentials/base-url
# - https://www.infobip.com/docs/api/channels/sms/sms-messaging
# - https://www.infobip.com/docs/tutorials/
#       send-your-first-sms-message-using-infobip-api

from __future__ import annotations

from json import dumps, loads
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
INFOBIP_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the phone number and sender.",
    401: "Unauthorized - Invalid API Key.",
    403: "Forbidden - The API Key lacks the sms:message:send scope.",
    429: "Too many requests were made.",
}

# Message status groups that mean the message will never arrive
# Based on: https://www.infobip.com/docs/essentials/api-essentials/
#               response-status-and-error-codes
INFOBIP_FAILED_GROUPS = ("UNDELIVERABLE", "EXPIRED", "REJECTED")

# Added to a Base URL given without its domain (xxxxxx)
INFOBIP_DOMAIN = "api.infobip.com"


class NotifyInfobip(NotifyBase):
    """A wrapper for Infobip SMS Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Infobip"

    # The services URL
    service_url = "https://www.infobip.com/"

    # The default secure protocol
    secure_protocol = "infobip"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/infobip/"

    # Our message URL; the host is the account's personal Base URL
    notify_url = "https://{host}/sms/3/messages"

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object URL templates
    templates = ("{schema}://{apikey}@{host}/{targets}",)

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
            "host": {
                "name": _("Hostname"),
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
            "key": {
                "alias_of": "apikey",
            },
            "from": {
                "name": _("Sender ID"),
                "type": "string",
                "map_to": "source",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        apikey: str,
        source: Optional[str] = None,
        targets: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Infobip Object."""
        super().__init__(**kwargs)

        # Our API Key
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Infobip API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Our Base URL
        if not self.host:
            msg = "An Infobip Base URL must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # A Base URL given as just its first part gets the Infobip
        # domain added to it.
        if "." not in self.host:
            self.host = f"{self.host}.{INFOBIP_DOMAIN}"

        # The sender is optional and may be a name or a phone number
        self.source = source.strip() if isinstance(source, str) else None

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
                "Dropped invalid Infobip phone # (%s) specified.", target
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
        """Perform Infobip Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no Infobip targets to notify.")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Authorization": f"App {self.apikey}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Prepare our URL
        url = self.notify_url.format(host=self.host)

        # Prepare our message; the destination is filled in below
        message = {
            "destinations": [{"to": None}],
            "content": {"text": body},
        }

        # Only name a sender when one was given
        if self.source:
            message["sender"] = self.source

        # Prepare our payload
        payload = {"messages": [message]}

        # error tracking (used for function return)
        has_error = False

        for target in self.targets:
            # Skip a target that already accepted this message so a retry
            # does not deliver it twice.
            if self.is_delivered(target):
                continue

            # Address this copy of our message
            message["destinations"][0]["to"] = target

            self.logger.debug(
                "Infobip POST URL: %s (cert_verify=%r)",
                url,
                self.verify_certificate,
            )
            self.logger.debug("Infobip Payload: %s", payload)

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

                # The response might look like:
                # {
                #   "bulkId": "2034072219640523072",
                #   "messages": [{
                #       "messageId": "2250be2d4219-3af1-78856-aabe",
                #       "status": {
                #           "groupId": 1,
                #           "groupName": "PENDING",
                #           "id": 26,
                #           "name": "PENDING_ACCEPTED",
                #           "description": "Message sent to next instance"
                #       },
                #       "destination": "41793026727",
                #   }]
                # }
                messages = (
                    content.get("messages")
                    if isinstance(content, dict)
                    else None
                )

                # Find the first status that says this message failed
                failed = next(
                    (
                        m["status"]
                        for m in (
                            messages if isinstance(messages, list) else []
                        )
                        if isinstance(m, dict)
                        and isinstance(m.get("status"), dict)
                        and m["status"].get("groupName")
                        in INFOBIP_FAILED_GROUPS
                    ),
                    None,
                )

                if r.status_code != requests.codes.ok or failed:
                    # We had a problem
                    status_str = (
                        (failed.get("description") or failed["groupName"])
                        if failed
                        else NotifyInfobip.http_response_code_lookup(
                            r.status_code, INFOBIP_HTTP_ERROR_MAP
                        )
                    )

                    self.logger.warning(
                        "Failed to send Infobip notification to %s: "
                        "%s%serror=%s.",
                        target,
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

                self.logger.info("Sent Infobip notification to %s.", target)

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Infobip "
                    "notification to %s.",
                    target,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

            # Delivered; a retry can safely skip this target.
            self.mark_delivered(target)

        return not has_error

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The Base URL and API Key identify the account
        return (self.secure_protocol, self.host, self.apikey)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Our URL parameters
        params = {}

        if self.source:
            params["from"] = self.source

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}@{host}/{targets}?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            host=self.host,
            targets="/".join(
                NotifyInfobip.quote(x, safe="+")
                for x in (self.targets + self.invalid_targets)
            ),
            params=NotifyInfobip.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our API Key sits before the Base URL
        results["apikey"] = NotifyInfobip.unquote(results["user"])

        # Allow the API Key to be given as ?key= instead
        if results["qsd"].get("key"):
            results["apikey"] = NotifyInfobip.unquote(results["qsd"]["key"])

        # Our phone numbers are in the path
        results["targets"] = NotifyInfobip.split_path(results["fullpath"])

        # Support ?to= for targets
        if results["qsd"].get("to"):
            results["targets"] += NotifyInfobip.parse_phone_no(
                results["qsd"]["to"]
            )

        # Support ?from= for the sender
        if results["qsd"].get("from"):
            results["source"] = NotifyInfobip.unquote(results["qsd"]["from"])

        return results
