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

# API Reference: https://creators.viber.com/docs/bots-api/\
#       resources/messaging/send-message
from __future__ import annotations

from collections.abc import Iterable
from json import dumps, loads
from typing import Any, Optional

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase


class NotifyViber(NotifyBase):
    """Send a Viber Bot message using the Viber REST Bot API."""

    # The default descriptive name associated with the Notification
    service_name = _("Viber")

    # The Services URL
    service_url = "https://www.viber.com/"

    # The default protocol
    secure_protocol = "viber"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/viber/"

    # Viber notification endpoint
    notify_url = "https://chatapi.viber.com/pa/send_message"

    # Service limits (documented maximum is 30KB)
    # Note: this is not exact byte accounting (UTF-8 vs chars), but it keeps
    # messages in the expected range.
    body_maxlen = 30000

    # We don't support titles for Viber notifications
    title_maxlen = 0

    # Maximum characters allowed in sender name
    viber_sender_name_limit = 28

    # Minimal URL; endpoint is fixed, token is the first path entry.
    templates = (
        "{schema}://{token}/{targets}",
    )

    template_tokens = dict(NotifyBase.template_tokens, **{
        "token": {
            "name": _("Authentication Token"),
            "type": "string",
            "private": True,
            "required": True,
        },
        "targets": {
            "name": _("Receiver IDs"),
            "type": "list:string",
        },
    })

    template_args = dict(NotifyBase.template_args, **{
        # Viber requires sender.name
        "from": {
            "name": _("Bot Name"),
            "type": "string",
            "map_to": "source",
        },
        # Optional sender.avatar URL
        "avatar": {
            "name": _("Bot Avatar URL"),
            "type": "string",
        },
        "token": {
            "alias_of": "token",
        },
        # Allow targets to also come from query string
        "to": {
            "alias_of": "targets"
        }
    })


    def __init__(
        self,
        token: str,
        targets: Optional[Iterable[str]] = None,
        source: Optional[str] = None,
        avatar: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self.token = validate_regex(token)
        if not self.token:
            msg = "An invalid Viber authentication token was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Sender name is required by the API; provide a safe default
        sourcev = (source or "").strip()
        if len(sourcev) > self.viber_sender_name_limit:
            self.logger.warning(
                f"Viber sender name exceeds {self.viber_sender_name_limit} "
                "characters, truncating.")
            sourcev = sourcev[:self.viber_sender_name_limit]
        self.source: str = sourcev

        self.avatar: Optional[str] = (avatar or "").strip() or None

        # Store our targets
        self.targets = parse_list(targets)

    def __len__(self) -> int:
        """Number of outbound HTTP requests this configuration will perform."""
        return max(1, len(self.targets))

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Rebuild the Apprise URL with secrets redacted."""

        # Define any URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        if self.source:
            params["from"] = self.source

        if self.avatar:
            params["avatar"] = self.avatar

        # Path targets
        tgt = ""
        if self.targets:
            tgt = "/".join(self.quote(t, safe="") for t in self.targets)

        # Token in first path element
        token = self.pprint(
            self.token, privacy, mode=PrivacyMode.Secret, safe="")

        query = self.urlencode(params)
        return (
            f"{self.secure_protocol}://{token}/"
            + tgt + (f"?{query}" if query else ""))

    @property
    def url_identifier(self) -> str:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.token)

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Send a Viber notification to each configured receiver ID."""
        if not self.targets:
            # There were no services to notify
            self.logger.warning("There were no Viber targets to notify")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "X-Viber-Auth-Token": self.token,
        }

        # Prepare our payload
        payload: dict[str, Any] = {
            "type": "text",
            "text": body,
            "sender": {
                "name": self.source if self.source
                else self.app_desc[:self.viber_sender_name_limit]},
        }

        if self.avatar:
            payload["sender"]["avatar"] = self.avatar

        content = None
        status_str = None
        has_error = False

        for dest in self.targets:
            payload["receiver"] = dest

            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # Viber returns the following on success:
                #   {"status":0,"status_message":"ok",...}
                try:
                    content = loads(r.content)

                except (AttributeError, TypeError, ValueError, KeyError):
                    # ValueError = r.content is Unparsable
                    # TypeError = r.content is None
                    # AttributeError = r is None
                    # KeyError = 'result' is not found in result
                    content = {}
                    self.logger.warning(
                        "Invalid JSON response from Viber sending "
                        f"notification to {dest}")
                    self.logger.debug("Response Details:\n%s", r.content)
                    has_error = True
                    continue

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = (
                        content.get("status_message")
                        if content.get("status_message")
                        else self.http_response_code_lookup(
                            r.status_code
                        )
                    )
                    self.logger.warning(
                        f"Failed to send Viber notification to {dest} - "
                        f"{status_str} error={r.status_code}."
                    )

                    self.logger.debug("Response Details:\n%s", r.content)

                    # Mark our failure
                    has_error = True
                    continue

                if int(content.get("status", -1)) != 0:
                    self.logger.warning(
                        f"Failed to send Viber notification to {dest} - "
                        "Viber Error {%s} (status=%s)",
                        content.get("status_message", "unknown"),
                        content.get("status", "unknown"),
                    )
                    self.logger.debug("Response Details:\n%s", r.content)
                    # Mark our failure
                    has_error = True
                    continue

            except requests.RequestException as e:
               self.logger.warning(
                   "A Connection error occured sending Viber notification "
                   "to %s",
                   dest,
               )
               self.logger.debug(f"Socket Exception: {e!s}")
               # Mark our failure
               has_error = True
               continue

        return not has_error

    @staticmethod
    def parse_url(url: str) -> dict[str, Any]:
        """Parse the URL and return arguments to instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Prepare a Full path to work with
        results["targets"] = [
            NotifyViber.unquote(results["host"]),
            *NotifyViber.split_path(results["fullpath"])]

        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["token"] = NotifyViber.unquote(
                results["qsd"]["token"]
            )

        else:
            results["token"] = results["targets"][0]
            results["targets"] = results["targets"][1:]

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += results["qsd"]["to"]

        # Map 'from' -> source
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyViber.unquote(
                results["qsd"]["from"]
            )

        # Map avatar
        if "avatar" in results["qsd"] and len(results["qsd"]["avatar"]):
            results["avatar"] = NotifyViber.unquote(
                results["qsd"]["avatar"]
            )

        return results
