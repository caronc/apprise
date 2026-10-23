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


# ilert receives alerts through an "API" alert source:
#  1. Visit https://app.ilert.com/ and open "Alert sources".
#  2. Click "Add a new alert source" and choose "API" as the
#     integration type.
#  3. Pick the escalation policy that should be paged and save.
#  4. Copy the integration key shown on the alert source's detail page.
#
#  Your Apprise URL should be assembled as:
#     ilert://{integration_key}
#
#  The Events API has no way to upload files, so attachments are not
#  supported.
#
# Resources:
# - https://docs.ilert.com/developer-docs/rest-api/api-reference/events
# - https://docs.ilert.com/developer-docs/api-samples/creating-alerts-through-events

from __future__ import annotations

from hashlib import sha256
from json import dumps
from typing import Any, Optional
from uuid import uuid4

import requests

from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..conversion import commonmark_decode_backslash_escapes
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
ILERT_HTTP_ERROR_MAP = {
    400: "Bad Request - Check the integration key and payload.",
    429: "Too many requests were made.",
}


class ILertAction:
    """Tracks the actions supported by the ilert plugin."""

    # Resolve alerts on success, raise them otherwise
    MAP = "map"

    # Always raise a new alert
    TRIGGER = "trigger"

    # Always accept the alert that shares the same alert key
    ACKNOWLEDGE = "acknowledge"

    # Always resolve the alert that shares the same alert key
    RESOLVE = "resolve"


# Define our ilert actions
ILERT_ACTIONS = (
    ILertAction.MAP,
    ILertAction.TRIGGER,
    ILertAction.ACKNOWLEDGE,
    ILertAction.RESOLVE,
)

# The event type ilert expects for each fixed action
ILERT_EVENT_TYPES = {
    ILertAction.TRIGGER: "ALERT",
    ILertAction.ACKNOWLEDGE: "ACCEPT",
    ILertAction.RESOLVE: "RESOLVE",
}

# The priorities ilert accepts
ILERT_PRIORITIES = ("high", "low")


class NotifyILert(NotifyBase):
    """A wrapper for ilert Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "ilert"

    # The services URL
    service_url = "https://www.ilert.com/"

    # The default secure protocol
    secure_protocol = "ilert"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/ilert/"

    # Our Events API URL
    notify_url = "https://api.ilert.com/api/events"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # The alert details support markdown
    notify_format = NotifyFormat.MARKDOWN

    # Define object URL templates
    templates = ("{schema}://{key}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "key": {
                "name": _("Integration Key"),
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
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": ILERT_ACTIONS,
                "default": ILERT_ACTIONS[0],
            },
            "dedup": {
                "name": _("Deduplication Key"),
                "type": "string",
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:string",
                "values": ILERT_PRIORITIES,
            },
            "route": {
                "name": _("Route"),
                "type": "string",
                "map_to": "routing_key",
            },
            "click": {
                "name": _("Click"),
                "type": "string",
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
        "labels": {
            "name": _("Labels"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        key: str,
        action: Optional[str] = None,
        dedup: Optional[str] = None,
        priority: Optional[str] = None,
        routing_key: Optional[str] = None,
        click: Optional[str] = None,
        include_image: bool = True,
        labels: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize ilert Object."""
        super().__init__(**kwargs)

        # The integration key identifies the alert source we raise alerts on
        self.key = validate_regex(key, *self.template_tokens["key"]["regex"])
        if not self.key:
            msg = (
                "An invalid ilert integration key ({}) was specified.".format(
                    key
                )
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Resolve our action; partial names such as "r" are accepted
        if action and isinstance(action, str):
            self.action = next(
                (
                    a
                    for a in ILERT_ACTIONS
                    if a.startswith(action.strip().lower())
                ),
                None,
            )
            if not self.action:
                msg = "The ilert action specified ({}) is invalid.".format(
                    action
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        else:
            # Default to mapping our notification type
            self.action = self.template_args["action"]["default"]

        # A fixed alert key lets several notifications share one alert
        self.dedup = dedup.strip() if dedup and dedup.strip() else None

        # Our priority; partial names such as "h" are accepted
        self.priority = None
        if priority and isinstance(priority, str) and priority.strip():
            self.priority = next(
                (
                    p
                    for p in ILERT_PRIORITIES
                    if p.startswith(priority.strip().lower())
                ),
                None,
            )
            if not self.priority:
                msg = "The ilert priority specified ({}) is invalid.".format(
                    priority
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # Send new alerts to a different escalation policy
        self.routing_key = (
            routing_key.strip()
            if routing_key and routing_key.strip()
            else None
        )

        # A link shown on the alert
        self.click = click.strip() if click and click.strip() else None

        # Display our Apprise image on the alert
        self.include_image = parse_bool(include_image, True)

        # Labels shown on the alert
        self.labels = dict(labels) if labels else {}

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        body_passthrough: bool = False,
        **kwargs: Any,
    ) -> bool:
        """Perform ilert Notification."""

        # Map resolves on success and raises an alert otherwise
        event_type = (
            ("RESOLVE" if notify_type == NotifyType.SUCCESS else "ALERT")
            if self.action == ILertAction.MAP
            else ILERT_EVENT_TYPES[self.action]
        )

        # Our own key always wins
        alert_key = self.dedup
        if not alert_key and self.action == ILertAction.TRIGGER:
            # Each notification raises its own alert.  The key is kept
            # across retries so a retry never raises a second one.
            alert_key = self.recall("alert_key")
            if alert_key is None:
                alert_key = str(uuid4())
                self.remember("alert_key", alert_key)

        elif not alert_key:
            # Every other action needs a key that stays the same between
            # notifications, so a later success can find the alert a
            # failure raised.  The title (or the first line of the body
            # when there is none) stands in for it.
            alert_key = sha256(
                (title if title else body.split("\n", 1)[0].strip()).encode(
                    "utf-8"
                )
            ).hexdigest()

        # The summary is the plain text alert title.  Without one, fall
        # back to the body without the markdown escapes Apprise added to
        # it.
        summary = (
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
            "integrationKey": self.key,
            "eventType": event_type,
            "summary": summary,
            "details": body,
            "alertKey": alert_key,
        }

        if self.priority:
            payload["priority"] = self.priority.upper()

        if self.routing_key:
            payload["routingKey"] = self.routing_key

        if self.click:
            payload["links"] = [
                {
                    "href": self.click,
                }
            ]

        # Acquire our image url if configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )

        if image_url:
            payload["images"] = [
                {
                    "src": image_url,
                    "alt": notify_type.value,
                }
            ]

        if self.labels:
            payload["labels"] = self.labels

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self.logger.debug(
            "ilert POST URL: %s (cert_verify=%s)",
            self.notify_url,
            self.verify_certificate,
        )
        self.logger.debug("ilert Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
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
                status_str = NotifyILert.http_response_code_lookup(
                    r.status_code, ILERT_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send ilert event: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug("Response Details:\r\n%s", r.content)

                # Return; we're done
                return False

            self.logger.info("Sent ilert event.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending ilert event."
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
        # The integration key identifies the connection
        return (self.secure_protocol, self.key)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
        }

        if self.action != self.template_args["action"]["default"]:
            params["action"] = self.action

        if self.dedup:
            params["dedup"] = self.dedup

        if self.priority:
            params["priority"] = self.priority

        if self.routing_key:
            params["route"] = self.routing_key

        if self.click:
            params["click"] = self.click

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our labels are passed along as +key=value entries
        params.update({"+{}".format(k): v for k, v in self.labels.items()})

        return "{schema}://{key}/?{params}".format(
            schema=self.secure_protocol,
            key=self.pprint(self.key, privacy, safe=""),
            params=NotifyILert.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our integration key is kept in the host
        results["key"] = NotifyILert.unquote(results["host"])

        # Support ?key= for an easier yaml configuration
        if "key" in results["qsd"] and results["qsd"]["key"]:
            results["key"] = NotifyILert.unquote(results["qsd"]["key"])

        if "action" in results["qsd"] and results["qsd"]["action"]:
            results["action"] = NotifyILert.unquote(results["qsd"]["action"])

        if "dedup" in results["qsd"] and results["qsd"]["dedup"]:
            results["dedup"] = NotifyILert.unquote(results["qsd"]["dedup"])

        if "priority" in results["qsd"] and results["qsd"]["priority"]:
            results["priority"] = NotifyILert.unquote(
                results["qsd"]["priority"]
            )

        if "route" in results["qsd"] and results["qsd"]["route"]:
            results["routing_key"] = NotifyILert.unquote(
                results["qsd"]["route"]
            )

        if "click" in results["qsd"] and results["qsd"]["click"]:
            results["click"] = NotifyILert.unquote(results["qsd"]["click"])

        # Include images with our message
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        # Store our +key=value label entries
        results["labels"] = {
            NotifyILert.unquote(x): NotifyILert.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results
