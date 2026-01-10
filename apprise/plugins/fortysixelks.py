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

Minimal URL formats (source ends up being target):
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
    secure_protocol = ("46elks", "elks")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/46elks/"

    # 46elksAPI Request URLs
    notify_url = "https://api.46elks.com/a1/sms"

    # The maximum allowable characters allowed in the title per message
    title_maxlen = 0

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 160

    # Define object templates
    templates = (
        "{schema}://{user}:{password}@/{from_phone}",
        "{schema}://{user}:{password}@/{from_phone}/{targets}",
    )

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
            "from_phone": {
                "name": _("From Phone No"),
                "type": "string",
                "required": True,
                "map_to": "source",
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
                "alias_of": "from_phone",
            },
        },
    )

    def __init__(
        self,
        targets: Optional[Iterable[str]] = None,
        source: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialise 46elks notifier.

        :param targets: Iterable of phone numbers. E.164 is recommended.
        :param source: Optional source ID or E.164 number.
        """
        super().__init__(**kwargs)

        # Prepare our source
        self.source: Optional[str] = (source or "").strip() or None

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

        if not targets and is_phone_no(self.source):
            targets = [self.source]

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
                "from": self.source,
                "message": body,
            }

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

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000])

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
        return (self.secure_protocol[0], self.user, self.password, self.source)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Initialize our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Apprise URL can be condensed and target can be eliminated if its
        # our source phone no
        targets = (
            [] if len(self.targets) == 1 and
            self.source in self.targets else self.targets)

        return "{schema}://{user}:{pw}@{source}/{targets}?{params}".format(
            schema=self.secure_protocol[0],
            user=self.quote(self.user, safe=""),
            source=self.source if self.source else "",
            pw=self.pprint(
                self.password, privacy, mode=PrivacyMode.Secret, safe=""),
            targets="/".join(
                [Notify46Elks.quote(x, safe="+") for x in targets]
            ),
            params=Notify46Elks.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
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
                    schema=Notify46Elks.secure_protocol[0],
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

        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = Notify46Elks.unquote(
                results["qsd"]["from"]
            )

        elif results["host"]:
            results["source"] = Notify46Elks.unquote(results["host"])

        # Store our remaining targets found on path
        results["targets"].extend(
            Notify46Elks.split_path(results["fullpath"])
        )

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += Notify46Elks.parse_phone_no(
                results["qsd"]["to"]
            )

        return results
