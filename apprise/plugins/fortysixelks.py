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
"""
46elks SMS Notification Service.

Minimal URL formats:
  - 46elks://user:pass@/+15551234567
  - 46elks://user:pass@/+15551234567/+46701234567
  - 46elks://user:pass@/+15551234567?from=Acme
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import (
    is_phone_no,
    parse_phone_no,
)
from .base import NotifyBase


class Notify46Elks(NotifyBase):
    """A wrapper for 46elks Notifications."""

    # The default descriptive name associated with the Notification
    service_name = _("46elks")

    # The services URL
    service_url = "https://46elks.com"

    # The default secure protocol
    secure_protocol = "46elks"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_46elks"

    # 46elksAPI Request URLs
    notify_url = "https://api.46elks.com/a1/sms"

    # The maximum allowable characters allowed in the title per message
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 160

    # Define object templates
    templates = ("{schema}://{user}:{password}@/{targets}",)

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
            "target_phone": {
                "name": _("Target Phone"),
                "type": "string",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "to": {
                "alias_of": "targets",
            },
            "from": {
                # Your registered short code or alphanumeric
                "name": _("From"),
                "type": "string",
                "map_to": "sender",
            },
        },
    )

    def __init__(
        self,
        targets: Optional[Iterable[str]] = None,
        sender: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialise 46elks notifier.

        :param targets: Iterable of phone numbers. E.164 is recommended.
        :param sender: Optional sender ID or E.164 number.
        """
        super().__init__(**kwargs)

        self.sender: Optional[str] = (sender or "").strip() or None

        if not self.password:
            msg = "No 46elks password was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        elif not self.user:
            msg = "No 46elks user was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Parse our targets
        self.targets = []

        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    f"Dropped invalid phone # ({target}) specified.",
                )
                continue

            # store valid phone number
            # Carry forward '+' if defined, otherwise do not...
            self.targets.append(
                ("+" + result["full"])
                if target.lstrip()[0] == "+"
                else result["full"]
            )

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform 46elks Notification."""

        if not self.targets:
            # There is no one to email; we're done
            self.logger.warning(
                "There are no 46elks recipients to notify"
            )
            return False

        headers = {
            "User-Agent": self.app_id,
        }

        # error tracking (used for function return)
        has_error = False

        targets = list(self.targets)
        while targets:
            target = targets.pop(0)

            # Prepare our payload
            payload = {
                "to": target,
                "message": body,
            }

            if self.sender:
                payload["from"] = self.sender

            self.logger.debug(
                "46elks POST URL:"
                f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
            )
            self.logger.debug(f"46elks Payload: {payload!s}")

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=payload,
                    headers=headers,
                    auth=(self.user, self.password),
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = (
                        Notify46Elks.http_response_code_lookup(
                            r.status_code
                        )
                    )

                    self.logger.warning(
                        "Failed to send 46elks notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        f"Sent 46elks notification to {target}."
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending 46elks"
                    f" notification to {target}."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.user, self.password, self.sender)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Initialize our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.sender:
            params["from"] = self.sender

        return "{schema}://{user}:{password}@{targets}?{params}".format(
            schema=self.secure_protocol,
            user=self.quote(self.user, safe=""),
            password=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=""),
            targets="/".join(
                [Notify46Elks.quote(x, safe="+") for x in self.targets]
            ),
            params=Notify46Elks.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        #
        # Factor batch into calculation
        #
        targets = len(self.targets)
        return targets if targets > 0 else 1

    @staticmethod
    def parse_native_url(url):
        """
        Support https://user:pw@api.46elks.com/a1/sms?to=+15551234567&from=Acme
        """

        result = re.match(
            r"^https?://(?P<credentials>[^@]+)@"
            r"api\.46elks\.com/a1/sms/?"
            r"(?P<params>\?.+)$",
            url,
            re.I,
        )

        if result:
            return Notify46Elks.parse_url(
                "{schema}://{credentials}@/{params}".format(
                    schema=Notify46Elks.secure_protocol,
                    credentials=result.group("credentials"),
                    params=result.group("params"),
                )
            )

        return None

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Prepare our targets
        results["targets"] = []

        # This means our host is actually a phone number (target)
        if results["host"]:
            results["targets"].append(
                Notify46Elks.unquote(results["host"])
            )

        # Store our remaining targets found on path
        results["targets"].extend(
            Notify46Elks.split_path(results["fullpath"])
        )

        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["sender"] = Notify46Elks.unquote(
                results["qsd"]["from"]
            )

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += Notify46Elks.parse_phone_no(
                results["qsd"]["to"]
            )

        return results
