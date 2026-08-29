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

# Steps to get your Signalgrid Client Key and Channel Token:
#  1. Visit https://signalgrid.co/ and sign in (or create an account).
#  2. Open your account settings and copy your Client Key.
#  3. Create (or select) a channel and copy its Channel Token.
#
#  Your Apprise URL should be assembled as:
#     signalgrid://{client_key}/{channel}
#
#  You can notify more than one channel in a single call by adding extra
#  channel tokens to the path:
#     signalgrid://{client_key}/{channel1}/{channel2}
#
# Resources:
# - https://docs.signalgrid.co/integrations/apprise/
# - https://docs.signalgrid.co/api/push-api/

from __future__ import annotations

from typing import Any, Optional

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

# Signalgrid's push API maps each Apprise notification type to one of its
# own notification type strings.
SIGNALGRID_TYPE_MAP = {
    NotifyType.INFO: "INFO",
    NotifyType.SUCCESS: "SUCCESS",
    NotifyType.WARNING: "WARN",
    NotifyType.FAILURE: "CRIT",
}


class NotifySignalgrid(NotifyBase):
    """A wrapper for Signalgrid Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Signalgrid"

    # The services URL
    service_url = "https://signalgrid.co/"

    # The default secure protocol
    secure_protocol = "signalgrid"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://docs.signalgrid.co/integrations/apprise/"

    # Signalgrid Push API URL
    notify_url = "https://api.signalgrid.co/v1/push"

    # Signalgrid's push API has no documented support for file/image
    # attachments, so we don't advertise it here.
    attachment_support = False

    # Define object URL templates
    templates = ("{schema}://{client_key}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "client_key": {
                "name": _("Client Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "targets": {
                "name": _("Channels"),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "client_key": {
                "alias_of": "client_key",
            },
            "to": {
                "alias_of": "targets",
            },
            "critical": {
                "name": _("Critical Notification"),
                "type": "bool",
                "default": False,
            },
        },
    )

    def __init__(
        self,
        client_key: Optional[str] = None,
        targets: Optional[list[str]] = None,
        critical: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize Signalgrid Object."""
        super().__init__(**kwargs)

        # Our Client Key authenticates us with Signalgrid
        self.client_key = validate_regex(client_key)
        if not self.client_key:
            msg = "An invalid Signalgrid Client Key was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store the channel(s) we're notifying. No channels is valid at
        # load time; send() will simply have nothing to notify.
        self.targets = parse_list(targets)

        # Whether this notification should be flagged as critical
        self.critical = parse_bool(critical, False)

    def __len__(self) -> int:
        """Returns the number of channels associated with this
        notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: str = NotifyType.INFO,
        attach: Optional[Any] = None,
        **kwargs: Any,
    ) -> bool:
        """Perform Signalgrid Notification."""

        # Let the user know attachments are silently dropped since
        # Signalgrid's push API has no documented way to accept them
        if attach:
            self.logger.warning(
                "Signalgrid does not support attachments; they will"
                " be ignored."
            )

        # We need at least one channel to notify
        if not self.targets:
            self.logger.warning(
                "There are no Signalgrid channels to notify, aborting."
            )
            return False

        # Track whether any channel notification failed
        has_error = False
        for channel in self.targets:
            if not self._send_to_channel(body, title, notify_type, channel):
                has_error = True

        return not has_error

    def _send_to_channel(
        self,
        body: str,
        title: str,
        notify_type: str,
        channel: str,
    ) -> bool:
        """Post a single notification to one Signalgrid channel."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
        }

        # Prepare our payload
        payload = {
            "client_key": self.client_key,
            "channel": channel,
            "title": title,
            "body": body,
            "type": SIGNALGRID_TYPE_MAP.get(notify_type, "INFO"),
            "critical": "true" if self.critical else "false",
        }

        self.logger.debug(
            "Signalgrid POST URL:"
            f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
        )

        # Never log the client key or channel token
        self.logger.debug(
            "Signalgrid Payload: title=%r, type=%r, critical=%r",
            title,
            payload["type"],
            payload["critical"],
        )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            response = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if response.status_code != requests.codes.ok:
                status_str = NotifySignalgrid.http_response_code_lookup(
                    response.status_code
                )

                self.logger.warning(
                    "Failed to send Signalgrid notification: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        response.status_code,
                    )
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    (response.content or b"")[:2000],
                )

                return False

            self.logger.info("Sent Signalgrid notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Signalgrid notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        return True

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Return identifiers unique to this Signalgrid configuration.

        Channels are delivery destinations, not connection identity, so
        they're intentionally left out here.
        """
        return (self.secure_protocol, self.client_key)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Return the Signalgrid Apprise URL."""

        # Prepare our parameters
        params = {
            "critical": "true" if self.critical else "false",
        }

        # Extend our parameters with the ones inherited from our parent
        params.update(
            self.url_parameters(
                privacy=privacy,
                *args,
                **kwargs,
            )
        )

        return "{schema}://{client_key}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            client_key=self.pprint(
                self.client_key,
                privacy,
                safe="",
            ),
            targets="/".join(
                NotifySignalgrid.quote(channel, safe="")
                for channel in self.targets
            ),
            params=NotifySignalgrid.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse Signalgrid URL."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # The client key occupies the URL hostname:
        # signalgrid://CLIENT_KEY/CHANNEL1/CHANNEL2
        results["client_key"] = NotifySignalgrid.unquote(
            results.get("host") or ""
        )

        # Every remaining path entry is a channel we deliver to
        results["targets"] = NotifySignalgrid.split_path(
            results.get("fullpath") or ""
        )

        # Support ?to= as a comma-separated alias for additional channels
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifySignalgrid.parse_list(
                results["qsd"]["to"]
            )

        # Support ?client_key= to override the hostname-derived value
        if "client_key" in results["qsd"] and results["qsd"]["client_key"]:
            results["client_key"] = NotifySignalgrid.unquote(
                results["qsd"]["client_key"]
            )

        # Support ?critical= to flag the notification as critical
        results["critical"] = parse_bool(results["qsd"].get("critical", False))

        return results
