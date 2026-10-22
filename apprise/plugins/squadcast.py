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


# Squadcast (now SolarWinds Incident Response) receives alerts through
# an "Incident Webhook" alert source:
#  1. Visit https://app.squadcast.com/ and open "Services".
#  2. Pick your service and click on "Alert Sources".
#  3. Search for "Incident Webhook" and copy the Webhook URL.  It looks
#     like:
#     https://api.squadcast.com/v2/incidents/api/{webhook_key}
#
#  The key at the end of the URL is your webhook key.
#  Your Apprise URL should be assembled as:
#     squadcast://{webhook_key}
#
#  Accounts hosted in Europe use api.eu.squadcast.com instead; add
#  ?region=eu to your Apprise URL for those.
#
# Resources:
# - https://support.squadcast.com/integrations/incident-webhook-incident-webhook-api

from __future__ import annotations

from hashlib import sha256
from json import dumps
import re
from typing import Any, Optional
from uuid import uuid4

import requests

from ..common import NotifyFormat, NotifyType
from ..conversion import commonmark_decode_backslash_escapes
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
SQUADCAST_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Webhook Key.",
    404: "The webhook key could not be found.",
    413: "The payload is too large.",
    429: "Too many requests were made.",
}


class SquadcastRegion:
    """Tracks the regions Squadcast is hosted in."""

    # United States
    US = "us"

    # Europe
    EU = "eu"


# The webhook URL used by each region
SQUADCAST_API_LOOKUP = {
    SquadcastRegion.US: "https://api.squadcast.com/v2/incidents/api/{key}",
    SquadcastRegion.EU: "https://api.eu.squadcast.com/v2/incidents/api/{key}",
}

# Define our Squadcast regions
SQUADCAST_REGIONS = (
    SquadcastRegion.US,
    SquadcastRegion.EU,
)


class SquadcastAction:
    """Tracks the actions supported by the Squadcast plugin."""

    # Resolve incidents on success, trigger them otherwise
    MAP = "map"

    # Always trigger a new incident
    TRIGGER = "trigger"

    # Always resolve the incident that shares the same event ID
    RESOLVE = "resolve"


# Define our Squadcast actions
SQUADCAST_ACTIONS = (
    SquadcastAction.MAP,
    SquadcastAction.TRIGGER,
    SquadcastAction.RESOLVE,
)

# The priorities Squadcast accepts
SQUADCAST_PRIORITIES = ("P1", "P2", "P3", "P4", "P5")


class NotifySquadcast(NotifyBase):
    """A wrapper for Squadcast Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Squadcast"

    # The services URL
    service_url = "https://www.squadcast.com/"

    # The default secure protocol
    secure_protocol = "squadcast"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/squadcast/"

    # The incident description supports markdown
    notify_format = NotifyFormat.MARKDOWN

    # Squadcast refuses payloads over 30KB.  This leaves room for the
    # title and the rest of the payload.
    body_maxlen = 30000

    # Define object URL templates
    templates = ("{schema}://{key}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "key": {
                "name": _("Webhook Key"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9_-]+$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "key": {
                "alias_of": "key",
            },
            "region": {
                "name": _("Region Name"),
                "type": "choice:string",
                "values": SQUADCAST_REGIONS,
                "default": SquadcastRegion.US,
                "map_to": "region_name",
            },
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": SQUADCAST_ACTIONS,
                "default": SQUADCAST_ACTIONS[0],
            },
            "dedup": {
                "name": _("Deduplication Key"),
                "type": "string",
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:string",
                "values": SQUADCAST_PRIORITIES,
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "tags": {
            "name": _("Tags"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        key: str,
        region_name: Optional[str] = None,
        action: Optional[str] = None,
        dedup: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Squadcast Object."""
        super().__init__(**kwargs)

        # The webhook key identifies the service our incidents go to
        self.key = validate_regex(key, *self.template_tokens["key"]["regex"])
        if not self.key:
            msg = (
                "An invalid Squadcast webhook key ({}) was specified.".format(
                    key
                )
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Pick the region our account is hosted in
        self.region_name = (
            region_name.strip().lower()
            if region_name and isinstance(region_name, str)
            else self.template_args["region"]["default"]
        )
        if self.region_name not in SQUADCAST_REGIONS:
            msg = "The Squadcast region specified ({}) is invalid.".format(
                region_name
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Resolve our action; partial names such as "r" are accepted
        if action and isinstance(action, str):
            self.action = next(
                (
                    a
                    for a in SQUADCAST_ACTIONS
                    if a.startswith(action.strip().lower())
                ),
                None,
            )
            if not self.action:
                msg = "The Squadcast action specified ({}) is invalid.".format(
                    action
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        else:
            # Default to mapping our notification type
            self.action = self.template_args["action"]["default"]

        # A fixed event ID lets several notifications share one incident
        self.dedup = dedup.strip() if dedup and dedup.strip() else None

        # Our priority; a plain number such as 1 is read as P1
        self.priority = None
        if priority and isinstance(priority, str) and priority.strip():
            self.priority = priority.strip().upper()
            if self.priority.isdigit():
                self.priority = "P{}".format(self.priority)

            if self.priority not in SQUADCAST_PRIORITIES:
                msg = (
                    "The Squadcast priority specified ({}) is invalid.".format(
                        priority
                    )
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Tags shown on the incident
        self.tags_map = dict(tags) if tags else {}

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        body_passthrough: bool = False,
        **kwargs: Any,
    ) -> bool:
        """Perform Squadcast Notification."""

        # Work out whether we trigger or resolve the incident
        resolve = self.action == SquadcastAction.RESOLVE or (
            self.action == SquadcastAction.MAP
            and notify_type == NotifyType.SUCCESS
        )

        # Squadcast resolves every incident without an event ID when it
        # receives another one, so we always send one.  Our own key wins.
        event_id = self.dedup
        if not event_id and self.action == SquadcastAction.TRIGGER:
            # Each notification triggers its own incident.  The key is
            # kept across retries so a retry never triggers a second one.
            event_id = self.recall("event_id")
            if event_id is None:
                event_id = str(uuid4())
                self.remember("event_id", event_id)

        elif not event_id:
            # Map and resolve need a key that stays the same between
            # notifications, so a later success can find the incident a
            # failure triggered.  The title (or the first line of the
            # body when there is none) stands in for it.
            event_id = sha256(
                (title if title else body.split("\n", 1)[0].strip()).encode(
                    "utf-8"
                )
            ).hexdigest()

        # The message is the plain text incident title.  Without one,
        # fall back to the body without the markdown escapes Apprise
        # added to it.
        message = (
            title
            if title
            else (
                body
                if body_passthrough
                else commonmark_decode_backslash_escapes(body)
            )[: self.title_maxlen]
        )

        # Prepare our payload
        payload = {
            "message": message,
            "description": body,
            "status": "resolve" if resolve else "trigger",
            "event_id": event_id,
        }

        if self.priority:
            payload["priority"] = self.priority

        if self.tags_map:
            payload["tags"] = self.tags_map

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Prepare our URL
        url = SQUADCAST_API_LOOKUP[self.region_name].format(key=self.key)

        self.logger.debug(
            "Squadcast POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Squadcast Payload: %s", payload)

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
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
                requests.codes.accepted,
                requests.codes.no_content,
            ):
                # We had a problem
                status_str = NotifySquadcast.http_response_code_lookup(
                    r.status_code, SQUADCAST_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Squadcast incident: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug("Response Details:\r\n%s", r.content)

                # Return; we're done
                return False

            self.logger.info("Sent Squadcast incident.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Squadcast incident."
            )
            self.logger.debug("Socket Exception: %s", str(e))

            # Return; we're done
            return False

        return True

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The region and webhook key identify the connection
        return (self.secure_protocol, self.region_name, self.key)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}

        if self.region_name != self.template_args["region"]["default"]:
            params["region"] = self.region_name

        if self.action != self.template_args["action"]["default"]:
            params["action"] = self.action

        if self.dedup:
            params["dedup"] = self.dedup

        if self.priority:
            params["priority"] = self.priority

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our tags are passed along as +key=value entries
        params.update({"+{}".format(k): v for k, v in self.tags_map.items()})

        return "{schema}://{key}/?{params}".format(
            schema=self.secure_protocol,
            key=self.pprint(self.key, privacy, safe=""),
            params=NotifySquadcast.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our webhook key is kept in the host
        results["key"] = NotifySquadcast.unquote(results["host"])

        # Support ?key= for an easier yaml configuration
        if "key" in results["qsd"] and results["qsd"]["key"]:
            results["key"] = NotifySquadcast.unquote(results["qsd"]["key"])

        if "region" in results["qsd"] and results["qsd"]["region"]:
            results["region_name"] = NotifySquadcast.unquote(
                results["qsd"]["region"]
            )

        if "action" in results["qsd"] and results["qsd"]["action"]:
            results["action"] = NotifySquadcast.unquote(
                results["qsd"]["action"]
            )

        if "dedup" in results["qsd"] and results["qsd"]["dedup"]:
            results["dedup"] = NotifySquadcast.unquote(results["qsd"]["dedup"])

        if "priority" in results["qsd"] and results["qsd"]["priority"]:
            results["priority"] = NotifySquadcast.unquote(
                results["qsd"]["priority"]
            )

        # Store our +key=value tag entries
        results["tags"] = {
            NotifySquadcast.unquote(x): NotifySquadcast.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """Support https://api.squadcast.com/v2/incidents/api/KEY."""
        result = re.match(
            r"^https?://api\.(?P<eu>eu\.)?squadcast\.com/v2/incidents/api/"
            r"(?P<key>[A-Z0-9_-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            results = NotifySquadcast.parse_url(
                "{schema}://{key}/{params}".format(
                    schema=NotifySquadcast.secure_protocol,
                    key=result.group("key"),
                    params=result.group("params") or "",
                )
            )

            if result.group("eu"):
                # The webhook URL was handed out by the EU region
                results["region_name"] = SquadcastRegion.EU

            return results

        return None
