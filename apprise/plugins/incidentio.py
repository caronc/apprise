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


# incident.io receives alerts through an "HTTP" alert source:
#  1. Visit https://app.incident.io/ and open "Alerts" -> "Sources".
#  2. Create a new alert source and pick the "HTTP" type.
#  3. incident.io shows you a URL and a secret token.  The URL looks like:
#     https://api.incident.io/v2/alert_events/http/01GW2G3V0S59R238FAHPDS1R66
#
#  The ID at the end of the URL is your alert source ID.
#  Your Apprise URL should be assembled as:
#     incidentio://{source_id}/{token}
#
# Resources:
# - https://docs.incident.io/alerts/http
# - https://docs.incident.io/api-reference/alert-events-v2/createhttp

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
# Based on: https://docs.incident.io/api-reference
INCIDENTIO_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Token.",
    404: "The alert source could not be found.",
    413: "The payload is too large.",
    422: "The alert was rejected as invalid.",
    429: "Too many requests were made.",
}


class IncidentIOAction:
    """Tracks the actions supported by the incident.io plugin."""

    # Resolve alerts on success, raise them otherwise
    MAP = "map"

    # Always raise a new alert
    TRIGGER = "trigger"

    # Always resolve the alert that shares the same deduplication key
    RESOLVE = "resolve"


# Define our incident.io actions
INCIDENTIO_ACTIONS = (
    IncidentIOAction.MAP,
    IncidentIOAction.TRIGGER,
    IncidentIOAction.RESOLVE,
)


class NotifyIncidentIO(NotifyBase):
    """A wrapper for incident.io Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "incident.io"

    # The services URL
    service_url = "https://incident.io/"

    # The default secure protocol
    secure_protocol = "incidentio"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/incidentio/"

    # incident.io HTTP alert source URL
    notify_url = "https://api.incident.io/v2/alert_events/http/{source}"

    # The alert description supports markdown
    notify_format = NotifyFormat.MARKDOWN

    # Define object URL templates
    templates = ("{schema}://{source}/{token}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "source": {
                "name": _("Alert Source ID"),
                "type": "string",
                "required": True,
                "regex": (r"^[A-Z0-9]+$", "i"),
            },
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "source": {
                "alias_of": "source",
            },
            "token": {
                "alias_of": "token",
            },
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": INCIDENTIO_ACTIONS,
                "default": INCIDENTIO_ACTIONS[0],
            },
            "dedup": {
                "name": _("Deduplication Key"),
                "type": "string",
            },
            "click": {
                "name": _("Click"),
                "type": "string",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "metadata": {
            "name": _("Metadata"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        source: str,
        token: str,
        action: Optional[str] = None,
        dedup: Optional[str] = None,
        click: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize incident.io Object."""
        super().__init__(**kwargs)

        # The alert source our alerts are posted to
        self.source = validate_regex(
            source, *self.template_tokens["source"]["regex"]
        )
        if not self.source:
            msg = (
                "An invalid incident.io alert source ID ({}) was "
                "specified.".format(source)
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The secret token generated with the alert source
        self.token = validate_regex(token)
        if not self.token:
            msg = "An invalid incident.io token ({}) was specified.".format(
                token
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Resolve our action; partial names such as "r" are accepted
        if action and isinstance(action, str):
            self.action = next(
                (
                    a
                    for a in INCIDENTIO_ACTIONS
                    if a.startswith(action.strip().lower())
                ),
                None,
            )
            if not self.action:
                msg = (
                    "The incident.io action specified ({}) is invalid.".format(
                        action
                    )
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        else:
            # Default to mapping our notification type
            self.action = self.template_args["action"]["default"]

        # A fixed key lets several notifications update the same alert
        self.dedup = dedup.strip() if dedup and dedup.strip() else None

        # A link back to wherever the alert came from
        self.click = click.strip() if click and click.strip() else None

        # Extra details the alert source can be set up to read
        self.metadata = dict(metadata) if metadata else {}

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        body_passthrough: bool = False,
        **kwargs: Any,
    ) -> bool:
        """Perform incident.io Notification."""

        # Work out whether we raise or resolve the alert
        resolve = self.action == IncidentIOAction.RESOLVE or (
            self.action == IncidentIOAction.MAP
            and notify_type == NotifyType.SUCCESS
        )

        # Our own key always wins
        dedup = self.dedup
        if not dedup and self.action == IncidentIOAction.TRIGGER:
            # Each notification raises its own alert.  The key is kept
            # across retries so a retry never raises a second one.
            dedup = self.recall("dedup")
            if dedup is None:
                dedup = str(uuid4())
                self.remember("dedup", dedup)

        elif not dedup:
            # Map and resolve need a key that stays the same between
            # notifications, so a later success can find the alert a
            # failure raised.  The title (or the first line of the body
            # when there is none) stands in for it.
            dedup = sha256(
                (title if title else body.split("\n", 1)[0].strip()).encode(
                    "utf-8"
                )
            ).hexdigest()

        # A title is required and is plain text.  Without one, fall back
        # to the body without the markdown escapes Apprise added to it.
        alert_title = (
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
            "title": alert_title,
            "description": body,
            "status": "resolved" if resolve else "firing",
            "deduplication_key": dedup,
        }

        if self.click:
            payload["source_url"] = self.click

        if self.metadata:
            payload["metadata"] = self.metadata

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(self.token),
        }

        # Prepare our URL
        url = self.notify_url.format(source=self.source)

        self.logger.debug(
            "incident.io POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("incident.io Payload: %s", payload)

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
                status_str = NotifyIncidentIO.http_response_code_lookup(
                    r.status_code, INCIDENTIO_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send incident.io alert: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug("Response Details:\r\n%s", r.content)

                # Return; we're done
                return False

            self.logger.info("Sent incident.io alert.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending incident.io alert."
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
        # The alert source and its secret identify the connection
        return (self.secure_protocol, self.source, self.token)

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}

        if self.action != self.template_args["action"]["default"]:
            params["action"] = self.action

        if self.dedup:
            params["dedup"] = self.dedup

        if self.click:
            params["click"] = self.click

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our metadata is passed along as +key=value entries
        params.update({"+{}".format(k): v for k, v in self.metadata.items()})

        return "{schema}://{source}/{token}/?{params}".format(
            schema=self.secure_protocol,
            source=NotifyIncidentIO.quote(self.source, safe=""),
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyIncidentIO.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our alert source ID is kept in the host
        results["source"] = NotifyIncidentIO.unquote(results["host"])

        # Our token is the first path entry
        entries = NotifyIncidentIO.split_path(results["fullpath"])
        results["token"] = entries[0] if entries else None

        # Support ?source= and ?token= for an easier yaml configuration
        if "source" in results["qsd"] and results["qsd"]["source"]:
            results["source"] = NotifyIncidentIO.unquote(
                results["qsd"]["source"]
            )

        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyIncidentIO.unquote(
                results["qsd"]["token"]
            )

        if "action" in results["qsd"] and results["qsd"]["action"]:
            results["action"] = NotifyIncidentIO.unquote(
                results["qsd"]["action"]
            )

        if "dedup" in results["qsd"] and results["qsd"]["dedup"]:
            results["dedup"] = NotifyIncidentIO.unquote(
                results["qsd"]["dedup"]
            )

        if "click" in results["qsd"] and results["qsd"]["click"]:
            results["click"] = NotifyIncidentIO.unquote(
                results["qsd"]["click"]
            )

        # Store our +key=value metadata entries
        results["metadata"] = {
            NotifyIncidentIO.unquote(x): NotifyIncidentIO.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """Support https://api.incident.io/v2/alert_events/http/SOURCE_ID."""
        result = re.match(
            r"^https?://api\.incident\.io/v2/alert_events/http/"
            r"(?P<source>[A-Z0-9]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            # A ?token= is part of the URL incident.io hands out
            return NotifyIncidentIO.parse_url(
                "{schema}://{source}/{params}".format(
                    schema=NotifyIncidentIO.secure_protocol,
                    source=result.group("source"),
                    params=result.group("params") or "",
                )
            )

        return None
