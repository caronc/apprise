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


# Better Stack offers two ways to receive notifications:
#
# Incidents (pages whoever is on-call):
#  1. Visit https://betterstack.com/settings/api-tokens/0 and pick your
#     team.
#  2. Copy (or create) a token in the "Uptime API tokens" section.
#  3. Better Stack needs the e-mail of a user on your account to show
#     who requested the incident.
#
#  Your Apprise URL is assembled as:
#     betterstack://{token}/{email}
#
#  A global API token (https://betterstack.com/settings/global-api-tokens)
#  can raise an incident for any team.  List the teams after the e-mail:
#     betterstack://{token}/{email}/{team}/{team2}
#
# Logs (adds an entry to a log source):
#  1. Visit https://telemetry.betterstack.com/ and create (or open) a
#     log source of the type "HTTP".
#  2. Copy the "Source token" and the "Ingesting host" it shows you.
#
#  Your Apprise URL is assembled as:
#     betterstack://{source_token}@{ingesting_host}
#
# Resources:
# - https://betterstack.com/docs/uptime/api/create-a-new-incident/
# - https://betterstack.com/docs/logs/ingesting-data/http/logs/

from __future__ import annotations

from datetime import datetime, timezone
from json import dumps
from typing import Any, Optional, Union

import requests

from ..common import NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import is_email, parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
# Based on the response codes listed in the Better Stack API docs
BETTERSTACK_HTTP_ERROR_MAP = {
    402: "Quota or spending limit reached.",
    403: "Invalid source token.",
    404: "Authentication failed.",
    406: "Payload could not be parsed.",
    413: "Payload too large.",
}


class BetterStackMode:
    """Tracks the mode of operation for the Better Stack plugin."""

    # Create an incident that alerts the on-call person
    INCIDENT = "incident"

    # Add an entry to a log source
    LOGS = "logs"


# The ways Better Stack can alert the on-call person, mapped to the
# payload field that switches each one on
BETTERSTACK_ALERT_METHODS = {
    "call": "call",
    "sms": "sms",
    "email": "email",
    "push": "push",
    "critical": "critical_alert",
}

# Map Apprise notification types to Better Stack log levels
BETTERSTACK_LOG_LEVELS = {
    NotifyType.INFO: "info",
    NotifyType.SUCCESS: "info",
    NotifyType.WARNING: "warn",
    NotifyType.FAILURE: "error",
}


class NotifyBetterStack(NotifyBase):
    """A wrapper for Better Stack Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Better Stack"

    # The services URL
    service_url = "https://betterstack.com/"

    # The default secure protocol
    secure_protocol = "betterstack"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/betterstack/"

    # Better Stack Incidents API URL
    incident_url = "https://incidents.betterstack.com/api/v3/incidents"

    # Define object URL templates
    templates = (
        # Incident mode
        "{schema}://{token}",
        "{schema}://{token}/{from_addr}",
        "{schema}://{token}/{targets}",
        "{schema}://{token}/{from_addr}/{targets}",
        # Logs mode
        "{schema}://{token}@{host}",
        "{schema}://{token}@{host}:{port}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "host": {
                "name": _("Hostname"),
                "type": "string",
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "from_addr": {
                "name": _("From Email"),
                "type": "string",
            },
            "targets": {
                "name": _("Target Team"),
                "type": "list:string",
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
            "from": {
                "alias_of": "from_addr",
            },
            "to": {
                "alias_of": "targets",
            },
            "policy": {
                "name": _("Escalation Policy"),
                "type": "string",
            },
            "alert": {
                "name": _("Alert Methods"),
                "type": "list:string",
            },
            "team_wait": {
                "name": _("Team Wait"),
                "type": "int",
                "min": 0,
            },
        },
    )

    def __init__(
        self,
        token: str,
        from_addr: Optional[str] = None,
        targets: Optional[Union[str, list[str]]] = None,
        policy: Optional[str] = None,
        alert: Optional[Union[str, list[str]]] = None,
        team_wait: Optional[Union[int, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Better Stack Object."""
        super().__init__(**kwargs)

        # An ingesting host is only given when sending logs
        self.mode = (
            BetterStackMode.LOGS if self.host else BetterStackMode.INCIDENT
        )

        # Our API or source token
        self.token = validate_regex(token)
        if not self.token:
            msg = "An invalid Better Stack token ({}) was specified.".format(
                token
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The e-mail of the user requesting the incident
        self.from_addr = None
        if from_addr:
            result = is_email(from_addr)
            if not result:
                msg = (
                    "An invalid Better Stack From Email ({}) was "
                    "specified.".format(from_addr)
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

            self.from_addr = result["full_email"]

        # The teams to raise an incident for.  Team names may hold spaces.
        self.targets = parse_list(targets, allow_whitespace=False)

        # The escalation policy to use
        self.policy = policy.strip() if policy else None

        # The alert methods to switch on.  None leaves the choice to the
        # Better Stack team settings.
        self.alert = None
        if alert:
            self.alert = []
            for method in parse_list(alert):
                method = method.lower()
                if method not in BETTERSTACK_ALERT_METHODS:
                    msg = (
                        "An invalid Better Stack alert method ({}) was "
                        "specified.".format(method)
                    )
                    self.logger.warning(msg)
                    raise AppriseImproperlyConfigured(msg)

                # Store each method only once
                if method not in self.alert:
                    self.alert.append(method)

        # Seconds to wait before escalating to the whole team
        self.team_wait = None
        if team_wait not in (None, ""):
            try:
                self.team_wait = int(team_wait)
                if self.team_wait < 0:
                    raise ValueError()

            except (TypeError, ValueError):
                msg = (
                    "An invalid Better Stack team wait ({}) was "
                    "specified.".format(team_wait)
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg) from None

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform Better Stack Notification."""

        if self.mode == BetterStackMode.LOGS:
            # Prepare our log entry
            payload = {
                "dt": datetime.now(timezone.utc).isoformat(),
                "level": BETTERSTACK_LOG_LEVELS.get(notify_type, "info"),
                "message": body,
            }

            # Only include a title when one was given
            if title:
                payload["title"] = title

            # Prepare our URL
            url = "https://{host}{port}".format(
                host=self.host,
                port="" if self.port is None else ":{}".format(self.port),
            )

            return self._post(url, payload)

        # Prepare our incident payload
        payload = {
            "summary": title if title else body,
        }

        # The body becomes the full description when a title is used
        if title:
            payload["name"] = title
            payload["description"] = body

        if self.from_addr:
            payload["requester_email"] = self.from_addr

        if self.policy:
            payload["policy_id"] = self.policy

        if self.team_wait is not None:
            payload["team_wait"] = self.team_wait

        if self.alert is not None:
            # Switch on the methods asked for and switch off the rest
            for method, field in BETTERSTACK_ALERT_METHODS.items():
                payload[field] = method in self.alert

        # Without teams, the team that owns the token gets the incident
        has_error = False
        for team in self.targets if self.targets else [None]:
            # Skip a team that already has this incident so a retry
            # does not raise it twice
            if self.is_delivered(team):
                continue

            # Name the team that should own the incident
            if team:
                payload["team_name"] = team

            if not self._post(self.incident_url, payload):
                # Mark our failure
                has_error = True
                continue

            # Delivered, so a retry can safely skip this team
            self.mark_delivered(team)

        return not has_error

    def _post(self, url: str, payload: dict[str, Any]) -> bool:
        """Post ``payload`` to ``url`` and return whether it was accepted."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(self.token),
        }

        self.logger.debug(
            "Better Stack POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Better Stack Payload: %s", payload)

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
                status_str = NotifyBetterStack.http_response_code_lookup(
                    r.status_code, BETTERSTACK_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Better Stack %s: %s%serror=%s.",
                    self.mode,
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug("Response Details:\r\n%s", r.content)

                # Return; we're done
                return False

            self.logger.info("Sent Better Stack %s.", self.mode)

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Better Stack %s.",
                self.mode,
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
        return (
            self.secure_protocol,
            self.mode,
            self.token,
            self.host,
            self.port if self.port else 443,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}

        if self.policy:
            params["policy"] = self.policy

        if self.alert is not None:
            params["alert"] = ",".join(self.alert)

        if self.team_wait is not None:
            params["team_wait"] = str(self.team_wait)

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.mode == BetterStackMode.LOGS:
            return "{schema}://{token}@{host}{port}/?{params}".format(
                schema=self.secure_protocol,
                token=self.pprint(self.token, privacy, safe=""),
                host=self.host,
                port="" if self.port is None else ":{}".format(self.port),
                params=NotifyBetterStack.urlencode(params),
            )

        # Our requester e-mail (if any) leads the path, then our teams
        entries = [self.from_addr] if self.from_addr else []
        entries += self.targets

        return "{schema}://{token}/{entries}?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            entries="".join(
                "{}/".format(NotifyBetterStack.quote(e, safe="@"))
                for e in entries
            ),
            params=NotifyBetterStack.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # One incident is raised per team, and always at least one
        return (
            len(self.targets)
            if self.mode == BetterStackMode.INCIDENT and self.targets
            else 1
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        if results.get("user"):
            # Logs mode keeps the source token in the user field
            results["token"] = NotifyBetterStack.unquote(results["user"])

        elif not ("token" in results["qsd"] and results["qsd"]["token"]):
            # Incident mode keeps the API token in the host field
            results["token"] = NotifyBetterStack.unquote(results["host"])
            results["host"] = None

        # Support ?token= for an easier yaml configuration
        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifyBetterStack.unquote(
                results["qsd"]["token"]
            )

        # Support ?from= for the requester e-mail
        if "from" in results["qsd"] and results["qsd"]["from"]:
            results["from_addr"] = NotifyBetterStack.unquote(
                results["qsd"]["from"]
            )

        # Our path holds an optional requester e-mail followed by teams
        results["targets"] = []
        for entry in NotifyBetterStack.split_path(results["fullpath"]):
            if not results.get("from_addr") and is_email(entry):
                # The first e-mail found is our requester
                results["from_addr"] = entry
                continue

            results["targets"].append(entry)

        # Support ?to= for teams
        if "to" in results["qsd"] and results["qsd"]["to"]:
            results["targets"] += NotifyBetterStack.parse_list(
                results["qsd"]["to"], allow_whitespace=False
            )

        if "policy" in results["qsd"] and results["qsd"]["policy"]:
            results["policy"] = NotifyBetterStack.unquote(
                results["qsd"]["policy"]
            )

        if "alert" in results["qsd"] and results["qsd"]["alert"]:
            results["alert"] = NotifyBetterStack.unquote(
                results["qsd"]["alert"]
            )

        if "team_wait" in results["qsd"] and results["qsd"]["team_wait"]:
            results["team_wait"] = NotifyBetterStack.unquote(
                results["qsd"]["team_wait"]
            )

        return results
