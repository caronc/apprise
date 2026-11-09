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


# OpsiMate is a self-hosted operations console that collects alerts from
# many monitoring sources.  Its Custom Alerts API accepts alerts from any
# tool that can make an HTTP request:
#  1. Install OpsiMate (https://docs.opsimate.dev/).
#  2. Find the API token of your installation.  It is the API_TOKEN of
#     the server (security.api_token in its config file); a default
#     installation ships with the token "opsimate".
#  3. Note the host and port the OpsiMate server listens on.
#
#  Your Apprise URL should be assembled as:
#     opsimate://{apikey}@{host}
#     opsimate://{apikey}@{host}:{port}
#     opsimates://{apikey}@{host}:{port}
#
#  Each notification fires (or resolves) one alert.  Apprise's title is the
#  alert name and its body the alert summary.  The notification type picks
#  the severity: a failure is critical, a warning is warning and an info or
#  success is info.
#
#  Every alert carries an id.  OpsiMate updates the alert that already
#  carries the same id instead of adding a row, so a check that fires every
#  minute keeps one alert open rather than one per minute.  The id is
#  derived from the alert name unless ?id= names one.  Because of this, a
#  success notification with ?resolve=yes resolves the alert a failure with
#  the same title raised: a tool that reports "down" as a failure and "up"
#  as a success keeps OpsiMate's active alert view clean by itself.  A
#  resolve sends only the id and the status, so the alert keeps the name,
#  severity and summary it was fired with.
#
#  The Custom Alerts API has no way to upload files, so attachments are
#  not supported.
#
# Resources:
# - https://docs.opsimate.dev/docs/integrations/custom-alerts

from __future__ import annotations

from hashlib import sha1
from json import dumps, loads
from typing import Any, Optional

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
OPSIMATE_HTTP_ERROR_MAP = {
    400: "Validation error - OpsiMate rejected the alert payload.",
    401: "Authentication error - the OpsiMate API token is not valid.",
}

# Map Apprise notification types to OpsiMate severities
OPSIMATE_SEVERITIES = {
    NotifyType.INFO: "info",
    NotifyType.SUCCESS: "info",
    NotifyType.WARNING: "warning",
    NotifyType.FAILURE: "critical",
}


class OpsiMateStatus:
    """The alert states OpsiMate accepts."""

    FIRING = "firing"
    RESOLVED = "resolved"


class NotifyOpsiMate(NotifyBase):
    """A wrapper for OpsiMate Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "OpsiMate"

    # The services URL
    service_url = "https://opsimate.dev/"

    # The default protocol
    protocol = "opsimate"

    # The default secure protocol
    secure_protocol = "opsimates"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/opsimate/"

    # OpsiMate is self-hosted and normally on the local network, so there
    # is no need to throttle
    request_rate_per_sec = 0

    # The alert summary is plain text
    notify_format = NotifyFormat.TEXT

    # The Custom Alerts API has no field for files
    attachment_support = False

    # Our Custom Alerts API path
    notify_path = "/api/v1/alerts/custom"

    # A name derived from the body (when there is no title) is cut here
    opsimate_alert_name_maxlen = 120

    # The tag every alert carries so OpsiMate shows where it came from
    opsimate_source_tag = "apprise"

    # Define object URL templates
    templates = (
        "{schema}://{apikey}@{host}",
        "{schema}://{apikey}@{host}:{port}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "apikey": {
                "alias_of": "apikey",
            },
            "token": {
                "alias_of": "apikey",
            },
            "id": {
                "name": _("Alert ID"),
                "type": "string",
                "map_to": "alert_id",
            },
            "team": {
                "name": _("Team"),
                "type": "string",
            },
            "resolve": {
                "name": _("Resolve on Success"),
                "type": "bool",
                "default": False,
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
        apikey: str,
        alert_id: Optional[str] = None,
        team: Optional[str] = None,
        resolve: bool = False,
        tags: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize OpsiMate Object."""
        super().__init__(**kwargs)

        # The API token of the OpsiMate server
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = "An invalid OpsiMate API token ({}) was specified.".format(
                apikey
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # A fixed alert id; every notification then addresses one alert
        self.alert_id = (
            alert_id.strip() if alert_id and alert_id.strip() else None
        )

        # The team that owns the alert
        self.team = team.strip() if team and team.strip() else None

        # Resolve the alert on a success notification instead of firing it
        self.resolve = parse_bool(resolve, False)

        # Extra tags shown on the alert
        self.tags = dict(tags) if tags else {}

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform OpsiMate Notification."""

        # The title names the alert.  Without one, the first line of the
        # body stands in for it.
        alert_name = title.strip() if title else ""
        if not alert_name:
            alert_name = (
                body.strip()
                .split("\n", 1)[0]
                .strip()[: self.opsimate_alert_name_maxlen]
            )

        # The id ties repeats of the same alert together.  OpsiMate updates
        # the alert that carries it instead of creating another, so the
        # same name must always yield the same id.
        alert_id = self.alert_id
        if not alert_id:
            alert_id = "apprise-{}".format(
                sha1(alert_name.strip().lower().encode("utf-8")).hexdigest()[
                    :16
                ]
            )

        if self.resolve and notify_type == NotifyType.SUCCESS:
            # A success resolves the alert when asked to.  Only the id and
            # the status are sent: OpsiMate keeps the name, severity and
            # summary the alert was fired with for every field left out.
            status = OpsiMateStatus.RESOLVED
            payload = {
                "id": alert_id,
                "status": status,
            }

        else:
            # Everything else fires the alert
            status = OpsiMateStatus.FIRING

            # Our tags; the source always identifies Apprise
            tags = dict(self.tags)
            tags["source"] = self.opsimate_source_tag
            if self.team:
                tags["team"] = self.team

            # Prepare our payload
            payload = {
                "id": alert_id,
                "alertName": alert_name,
                "summary": body,
                "severity": OPSIMATE_SEVERITIES[notify_type],
                "status": status,
                "tags": tags,
            }

            if self.team:
                payload["team"] = self.team

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-token": self.apikey,
        }

        # Set our schema
        schema = "https" if self.secure else "http"

        notify_url = "{}://{}".format(schema, self.host)
        if isinstance(self.port, int):
            notify_url += ":{}".format(self.port)

        notify_url += self.notify_path

        self.logger.debug(
            "OpsiMate POST URL: %s (cert_verify=%s)",
            notify_url,
            self.verify_certificate,
        )
        self.logger.debug("OpsiMate Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
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
                status_str = NotifyOpsiMate.http_response_code_lookup(
                    r.status_code, OPSIMATE_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send OpsiMate alert: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                if r.status_code == requests.codes.bad_request:
                    # OpsiMate names the fields it rejected; pass that on
                    self.logger.warning(
                        "OpsiMate validation error: %s",
                        self._validation_details(r.content),
                    )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

            self.logger.info(
                "Sent OpsiMate alert (%s): %s", status, alert_name
            )

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending OpsiMate alert to %s.",
                self.host,
            )
            self.logger.debug("Socket Exception: %s", str(e))

            # Return; we're done
            return False

        return True

    @staticmethod
    def _validation_details(content: Any) -> str:
        """Reduces OpsiMate's 400 response to the message its details
        carry, falling back to the raw body when it is not what we expect."""
        try:
            response = loads(content)
            details = response.get("details") or []
            messages = [
                "{}: {}".format(
                    ".".join(str(p) for p in detail.get("path", [])),
                    detail.get("message", ""),
                )
                for detail in details
                if isinstance(detail, dict)
            ]
            return (
                "; ".join(messages)
                if messages
                else str(response.get("error", response))
            )

        except (AttributeError, TypeError, ValueError):
            # ValueError = content is unparsable
            # TypeError = content is None
            # AttributeError = response is not a dictionary
            return repr((content or b"")[:2000])

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.apikey,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "resolve": "yes" if self.resolve else "no",
        }

        if self.alert_id:
            params["id"] = self.alert_id

        if self.team:
            params["team"] = self.team

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our tags are passed along as +key=value entries
        params.update({"+{}".format(k): v for k, v in self.tags.items()})

        default_port = 443 if self.secure else 80
        return "{schema}://{apikey}@{host}{port}/?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            # never encode hostname since we're expecting it to be a valid one
            host=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else ":{}".format(self.port)
            ),
            params=NotifyOpsiMate.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our API token leads the host
        results["apikey"] = (
            NotifyOpsiMate.unquote(results["user"])
            if results.get("user")
            else None
        )

        # Support ?apikey= and ?token= for an easier yaml configuration
        for key in ("apikey", "token"):
            if key in results["qsd"] and results["qsd"][key]:
                results["apikey"] = NotifyOpsiMate.unquote(results["qsd"][key])
                break

        if "id" in results["qsd"] and results["qsd"]["id"]:
            results["alert_id"] = NotifyOpsiMate.unquote(results["qsd"]["id"])

        if "team" in results["qsd"] and results["qsd"]["team"]:
            results["team"] = NotifyOpsiMate.unquote(results["qsd"]["team"])

        # Resolve the alert on a success notification
        results["resolve"] = parse_bool(
            results["qsd"].get(
                "resolve", NotifyOpsiMate.template_args["resolve"]["default"]
            )
        )

        # Store our +key=value tag entries
        results["tags"] = {
            NotifyOpsiMate.unquote(x): NotifyOpsiMate.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results
