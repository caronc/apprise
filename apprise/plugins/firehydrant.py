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


# FireHydrant Signals receives alerts through a webhook event source:
#  1. Visit https://app.firehydrant.io/ and open "Signals" -> "Sources".
#  2. Copy the generic webhook URL.  It looks like:
#     https://signals.firehydrant.com/v1/process/eyJhbGciOiJIUzI1NiJ9...
#
#  To page a specific team, escalation policy, on-call schedule or user
#  instead, open "Teams", pick a team and use the URL shown on its
#  "Alert Triggers" tab.
#
#  The long token at the end of the URL is your webhook token.
#  Your Apprise URL should be assembled as:
#     firehydrant://{token}
#
#  You can also just pass the full webhook URL to Apprise as-is.
#
# Resources:
# - https://docs.firehydrant.com/docs/generic-webhook-event-source
# - https://docs.firehydrant.com/docs/events-data-model
# - https://docs.firehydrant.com/docs/signals-alert-rules#bypassing-rules

from __future__ import annotations

from hashlib import sha256
from json import dumps
import re
from typing import Any, Optional, Union
from uuid import uuid4

import requests

from ..common import NotifyImageSize, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on: https://docs.firehydrant.com/docs/events-data-model
FIREHYDRANT_HTTP_ERROR_MAP = {
    400: "The event was rejected as invalid.",
    401: "Unauthorized - Invalid Token.",
    404: "The webhook token could not be found.",
    429: "Too many events were sent.",
}

# The annotation FireHydrant reads to decide how hard to page someone
FIREHYDRANT_PRIORITY_ANNOTATION = (
    "signals.firehydrant.com/notification-priority"
)


class FireHydrantAction:
    """Tracks the actions supported by the FireHydrant plugin."""

    # Resolve alerts on success, open them otherwise
    MAP = "map"

    # Always open a new alert
    TRIGGER = "trigger"

    # Always resolve the alert that shares the same deduplication key
    RESOLVE = "resolve"


# Define our FireHydrant actions
FIREHYDRANT_ACTIONS = (
    FireHydrantAction.MAP,
    FireHydrantAction.TRIGGER,
    FireHydrantAction.RESOLVE,
)

# The event levels FireHydrant understands
FIREHYDRANT_LEVELS = ("info", "warn", "error", "fatal")

# Each notification type picks a level unless one was set
FIREHYDRANT_LEVEL_MAP = {
    NotifyType.INFO: "info",
    NotifyType.SUCCESS: "info",
    NotifyType.WARNING: "warn",
    NotifyType.FAILURE: "error",
}

# The paging priorities FireHydrant understands
FIREHYDRANT_PRIORITIES = ("low", "medium", "high")


class NotifyFireHydrant(NotifyBase):
    """A wrapper for FireHydrant Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "FireHydrant"

    # The services URL
    service_url = "https://firehydrant.com/"

    # The default secure protocol
    secure_protocol = "firehydrant"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/firehydrant/"

    # FireHydrant Signals webhook URL
    notify_url = "https://signals.firehydrant.com/v1/process/{token}"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_256

    # The summary is cut to this length by FireHydrant anyway
    title_maxlen = 255

    # Define object URL templates
    templates = ("{schema}://{token}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9_.=-]+$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "token": {
                "alias_of": "token",
            },
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": FIREHYDRANT_ACTIONS,
                "default": FIREHYDRANT_ACTIONS[0],
            },
            # The level is picked from the notification type, however you
            # can optionally force it to be what you want
            "level": {
                "name": _("Level"),
                "type": "choice:string",
                "values": FIREHYDRANT_LEVELS,
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:string",
                "values": FIREHYDRANT_PRIORITIES,
            },
            "dedup": {
                "name": _("Deduplication Key"),
                "type": "string",
            },
            "click": {
                "name": _("Click"),
                "type": "string",
            },
            "tags": {
                "name": _("Tags"),
                "type": "list:string",
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "annotations": {
            "name": _("Annotations"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        token: str,
        action: Optional[str] = None,
        level: Optional[str] = None,
        priority: Optional[str] = None,
        dedup: Optional[str] = None,
        click: Optional[str] = None,
        tags: Optional[Union[str, list[str]]] = None,
        include_image: bool = True,
        annotations: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize FireHydrant Object."""
        super().__init__(**kwargs)

        # The webhook token our events are posted to
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = "An invalid FireHydrant token ({}) was specified.".format(
                token
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Resolve our action; partial names such as "r" are accepted
        self.action = (
            self._choice("action", action, FIREHYDRANT_ACTIONS)
            or (self.template_args["action"]["default"])
        )

        # An optional level and priority; partial names are accepted too
        self.level = self._choice("level", level, FIREHYDRANT_LEVELS)
        self.priority = self._choice(
            "priority", priority, FIREHYDRANT_PRIORITIES
        )

        # A fixed key lets several notifications update the same alert
        self.dedup = dedup.strip() if dedup and dedup.strip() else None

        # A link back to wherever the alert came from
        self.click = click.strip() if click and click.strip() else None

        # Tags such as service:api-gateway tie the alert to a catalog
        # entry.  This is not self.tags, which Apprise uses itself.
        self.event_tags = parse_list(tags)

        # Whether our notification icon is sent along with the alert
        self.include_image = include_image

        # Extra details the alert rules can match on
        self.annotations = dict(annotations) if annotations else {}

    def _choice(
        self, name: str, value: Optional[str], values: tuple[str, ...]
    ) -> Optional[str]:
        """Return the entry of ``values`` that ``value`` starts, if any."""
        # Nothing set means the caller falls back to its own default
        if not (value and isinstance(value, str)):
            return None

        # Partial names such as "r" for "resolve" are accepted
        result = next(
            (v for v in values if v.startswith(value.strip().lower())),
            None,
        )
        if not result:
            msg = "The FireHydrant {} specified ({}) is invalid.".format(
                name, value
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        return result

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform FireHydrant Notification."""

        # Work out whether we open or resolve the alert
        resolve = self.action == FireHydrantAction.RESOLVE or (
            self.action == FireHydrantAction.MAP
            and notify_type == NotifyType.SUCCESS
        )

        # Our own key always wins
        dedup = self.dedup
        if not dedup and self.action == FireHydrantAction.TRIGGER:
            # Each notification opens its own alert.  The key is kept
            # across retries so a retry never opens a second one.
            dedup = self.recall("dedup")
            if dedup is None:
                dedup = str(uuid4())
                self.remember("dedup", dedup)

        elif not dedup:
            # Map and resolve need a key that stays the same between
            # notifications, so a later success can find the alert a
            # failure opened.  The title (or the first line of the body
            # when there is none) stands in for it.
            dedup = sha256(
                (title if title else body.split("\n", 1)[0].strip()).encode(
                    "utf-8"
                )
            ).hexdigest()

        # Prepare our payload
        payload = {
            # A summary is required, so the body stands in for a title
            "summary": title if title else body[: self.title_maxlen],
            "body": body,
            "level": (
                self.level
                if self.level
                else FIREHYDRANT_LEVEL_MAP.get(notify_type, "info")
            ).upper(),
            "status": "CLOSED" if resolve else "OPEN",
            "idempotency_key": dedup,
        }

        # Our priority annotation comes first so +key=value can replace it
        annotations = (
            {FIREHYDRANT_PRIORITY_ANNOTATION: self.priority.upper()}
            if self.priority
            else {}
        )
        annotations.update(self.annotations)
        if annotations:
            payload["annotations"] = annotations

        if self.event_tags:
            payload["tags"] = self.event_tags

        if self.click:
            payload["links"] = [{"href": self.click, "text": self.click}]

        # Acquire our image url if configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )

        if image_url:
            payload["images"] = [{"src": image_url, "alt": notify_type.value}]

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Prepare our URL
        url = self.notify_url.format(token=self.token)

        self.logger.debug(
            "FireHydrant POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("FireHydrant Payload: %s", payload)

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
            ):
                # We had a problem
                status_str = NotifyFireHydrant.http_response_code_lookup(
                    r.status_code, FIREHYDRANT_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send FireHydrant event: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug("Response Details:\r\n%s", r.content)

                # Return; we're done
                return False

            self.logger.info("Sent FireHydrant event.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending FireHydrant event."
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
        # The webhook token identifies the connection
        return (self.secure_protocol, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
        }

        if self.action != self.template_args["action"]["default"]:
            params["action"] = self.action

        if self.level:
            params["level"] = self.level

        if self.priority:
            params["priority"] = self.priority

        if self.dedup:
            params["dedup"] = self.dedup

        if self.click:
            params["click"] = self.click

        if self.event_tags:
            params["tags"] = ",".join(self.event_tags)

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our annotations are passed along as +key=value entries
        params.update(
            {"+{}".format(k): v for k, v in self.annotations.items()}
        )

        return "{schema}://{token}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyFireHydrant.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our webhook token is kept in the host
        results["token"] = NotifyFireHydrant.unquote(results["host"])

        # Support ?token= for an easier yaml configuration
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyFireHydrant.unquote(
                results["qsd"]["token"]
            )

        if "action" in results["qsd"] and results["qsd"]["action"]:
            results["action"] = NotifyFireHydrant.unquote(
                results["qsd"]["action"]
            )

        if "level" in results["qsd"] and results["qsd"]["level"]:
            results["level"] = NotifyFireHydrant.unquote(
                results["qsd"]["level"]
            )

        if "priority" in results["qsd"] and results["qsd"]["priority"]:
            results["priority"] = NotifyFireHydrant.unquote(
                results["qsd"]["priority"]
            )

        if "dedup" in results["qsd"] and results["qsd"]["dedup"]:
            results["dedup"] = NotifyFireHydrant.unquote(
                results["qsd"]["dedup"]
            )

        if "click" in results["qsd"] and results["qsd"]["click"]:
            results["click"] = NotifyFireHydrant.unquote(
                results["qsd"]["click"]
            )

        if "tags" in results["qsd"] and results["qsd"]["tags"]:
            results["tags"] = parse_list(
                NotifyFireHydrant.unquote(results["qsd"]["tags"])
            )

        # Include images with our message
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        # Store our +key=value annotation entries
        results["annotations"] = {
            NotifyFireHydrant.unquote(x): NotifyFireHydrant.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """Support https://signals.firehydrant.com/v1/process/TOKEN."""
        result = re.match(
            r"^https?://signals\.firehydrant\.com/v1/process/"
            r"(?P<token>[A-Z0-9_.=-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyFireHydrant.parse_url(
                "{schema}://{token}/{params}".format(
                    schema=NotifyFireHydrant.secure_protocol,
                    token=result.group("token"),
                    params=result.group("params") or "",
                )
            )

        return None
