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

# Flowtriq is a DDoS detection and mitigation platform.
# This plugin enables any Apprise-connected tool to forward alerts
# to Flowtriq for network security correlation.
#
# URL format:
#   flowtriq://apikey@hostname/workspace_id/
#   flowtriq://apikey@hostname:port/workspace_id/
#
# The webhook endpoint is:
#   https://hostname/api/v1/workspaces/{workspace_id}/webhooks/apprise
#
# The API key is passed via the X-API-Key header.

from json import dumps

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase

# Map Apprise notification types to Flowtriq severity levels
FLOWTRIQ_SEVERITY_MAP = {
    NotifyType.INFO: "info",
    NotifyType.SUCCESS: "success",
    NotifyType.WARNING: "warning",
    NotifyType.FAILURE: "critical",
}


class NotifyFlowtriq(NotifyBase):
    """A wrapper for Flowtriq Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Flowtriq"

    # The services URL
    service_url = "https://flowtriq.com"

    # The default secure protocol
    secure_protocol = "flowtriq"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_flowtriq"

    # Disable throttle rate
    request_rate_per_sec = 0

    # The default hostname to use if none is specified
    default_host = "app.flowtriq.com"

    # Title is not used for Flowtriq
    title_maxlen = 250

    # Define object templates
    templates = (
        "{schema}://{apikey}@{host}/{workspace_id}/",
        "{schema}://{apikey}@{host}:{port}/{workspace_id}/",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
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
            "workspace_id": {
                "name": _("Workspace ID"),
                "type": "string",
                "required": True,
                "regex": (r"^[A-Za-z0-9_-]+$", "i"),
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{},
    )

    def __init__(self, apikey, workspace_id, **kwargs):
        """Initialize Flowtriq Object."""
        super().__init__(**kwargs)

        # API Key
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Flowtriq API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Workspace ID
        self.workspace_id = validate_regex(
            workspace_id,
            *self.template_tokens["workspace_id"]["regex"],
        )
        if not self.workspace_id:
            msg = (
                "An invalid Flowtriq Workspace ID "
                f"({workspace_id}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        if not self.host:
            self.host = self.default_host

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Flowtriq Notification."""

        # Build our URL
        schema = "https" if self.secure else "http"
        url = f"{schema}://{self.host}"
        if self.port:
            url += f":{self.port}"
        url += f"/api/v1/workspaces/{self.workspace_id}/webhooks/apprise"

        # Prepare our payload
        payload = {
            "title": title,
            "body": body,
            "severity": FLOWTRIQ_SEVERITY_MAP.get(notify_type, "info"),
            "type": notify_type,
            "source": "apprise",
        }

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "X-API-Key": self.apikey,
        }

        self.logger.debug(
            "Flowtriq POST URL: "
            f"{url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Flowtriq Payload: {payload!s}")

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
                status_str = NotifyFlowtriq.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Flowtriq notification: "
                    "{}{}error={}.".format(
                        status_str,
                        ", " if status_str else "",
                        r.status_code,
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Mark our failure
                return False

            else:
                self.logger.info("Sent Flowtriq notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Flowtriq "
                f"notification to {self.host}."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Mark our failure
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.workspace_id,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our default port
        default_port = 443 if self.secure else 80
        return (
            "{schema}://{apikey}@{hostname}{port}/"
            "{workspace_id}/?{params}".format(
                schema=self.secure_protocol,
                apikey=self.pprint(self.apikey, privacy, safe=""),
                hostname=self.host,
                port=(
                    ""
                    if self.port is None or self.port == default_port
                    else f":{self.port}"
                ),
                workspace_id=NotifyFlowtriq.quote(self.workspace_id, safe=""),
                params=NotifyFlowtriq.urlencode(params),
            )
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to
        re-instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The API key is stored in the user field
        results["apikey"] = (
            NotifyFlowtriq.unquote(results["user"])
            if results.get("user")
            else None
        )

        # Retrieve our escaped entries found on the fullpath
        entries = NotifyFlowtriq.split_path(results["fullpath"])

        # The first path entry is our workspace ID
        try:
            results["workspace_id"] = entries.pop(0)
        except IndexError:
            results["workspace_id"] = None

        return results
