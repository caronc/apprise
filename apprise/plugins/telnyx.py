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

# To use this service you will need a Telnyx account with a phone number
# that has been assigned to a Messaging Profile:
#     https://telnyx.com
#
# Generate your API Key (V2) from the Mission Control Portal here:
#     https://portal.telnyx.com/#/app/api-keys
#
# API Reference:
#     https://developers.telnyx.com/api-reference/messages/send-a-message
#
from __future__ import annotations

import json
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_phone_no, validate_regex
from .base import NotifyBase


class NotifyTelnyx(NotifyBase):
    """A wrapper for Telnyx Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Telnyx"

    # The services URL
    service_url = "https://telnyx.com"

    # All notification requests are secure
    secure_protocol = "telnyx"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/telnyx/"

    # Telnyx uses the http protocol with JSON requests
    notify_url = "https://api.telnyx.com/v2/messages"

    # The maximum length of the body
    body_maxlen = 160

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        "{schema}://{apikey}@{from_phone}",
        "{schema}://{apikey}@{from_phone}/{targets}",
    )

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
            "from_phone": {
                "name": _("From Phone No"),
                "type": "string",
                "regex": (r"^\+?[0-9\s)(+-]+$", "i"),
                "map_to": "source",
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
            "to": {
                "alias_of": "targets",
            },
            "from": {
                "name": _("From Phone No"),
                "type": "string",
                "regex": (r"^\+?[0-9\s)(+-]+$", "i"),
                "map_to": "source",
            },
            "profile": {
                "name": _("Messaging Profile ID"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        apikey: Optional[str] = None,
        source: Optional[str] = None,
        targets: Optional[Any] = None,
        profile: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Telnyx Object."""
        super().__init__(**kwargs)

        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Telnyx API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        result = is_phone_no(source)
        if not result:
            msg = (
                f"The Account (From) Phone # specified ({source}) is invalid."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Tidy source
        self.source = result["full"]

        # Optional Messaging Profile ID
        self.profile = validate_regex(profile) if profile else None

        # Parse our targets
        self.targets = []

        has_error = False
        for target in parse_phone_no(targets):
            # Parse each phone number we found
            result = is_phone_no(target)
            if result:
                self.targets.append(result["full"])
                continue

            has_error = True
            self.logger.warning(
                f"Dropped invalid phone # ({target}) specified.",
            )

        if not targets and not has_error:
            # Default the SMS Message to ourselves
            self.targets.append(self.source)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Telnyx Notification."""

        if not self.targets:
            # We have nothing to notify
            self.logger.warning("There are no Telnyx targets to notify")
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Authorization": f"Bearer {self.apikey}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Prepare our payload
        payload = {
            # The To gets populated in the loop below
            "from": "+" + self.source,
            "to": None,
            "text": body,
        }

        if self.profile:
            payload["messaging_profile_id"] = self.profile

        # Prepare our targets
        targets = list(self.targets)
        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user
            payload["to"] = "+" + target

            # Some Debug Logging
            self.logger.debug(
                "Telnyx POST URL:"
                f" {self.notify_url} (cert_verify={self.verify_certificate})"
            )
            self.logger.debug(f"Telnyx Payload: {payload}")

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=json.dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                    allow_redirects=self.redirects,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyBase.http_response_code_lookup(
                        r.status_code
                    )

                    # set up our status code to use
                    status_code = r.status_code

                    self.logger.warning(
                        "Failed to send Telnyx notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(f"Sent Telnyx notification to {target}.")

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Telnyx: to %s ",
                    target,
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.source, self.apikey, self.profile)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Prepare our parameters
        params: dict[str, Any] = {}
        if self.profile:
            params["profile"] = self.profile

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # A nice way of cleaning up the URL length a bit
        targets = (
            []
            if len(self.targets) == 1 and self.targets[0] == self.source
            else self.targets
        )

        return "{schema}://{apikey}@{source}/{targets}?{params}".format(
            schema=self.secure_protocol,
            source=self.source,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets="/".join(
                [NotifyTelnyx.quote(f"{x}", safe="+") for x in targets]
            ),
            params=NotifyTelnyx.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""

        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get our API Key
        results["apikey"] = NotifyTelnyx.unquote(results["user"])

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyTelnyx.unquote(results["qsd"]["from"])

            # hostname will also be a target in this case
            results["targets"] = [
                *NotifyTelnyx.parse_phone_no(results["host"]),
                *NotifyTelnyx.split_path(results["fullpath"]),
            ]

        else:
            # store our source
            results["source"] = NotifyTelnyx.unquote(results["host"])

            # store targets
            results["targets"] = NotifyTelnyx.split_path(results["fullpath"])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyTelnyx.parse_phone_no(
                results["qsd"]["to"]
            )

        if "key" in results["qsd"] and len(results["qsd"]["key"]):
            results["apikey"] = NotifyTelnyx.unquote(results["qsd"]["key"])

        # Messaging Profile ID
        if "profile" in results["qsd"] and len(results["qsd"]["profile"]):
            results["profile"] = NotifyTelnyx.unquote(
                results["qsd"]["profile"]
            )

        return results
