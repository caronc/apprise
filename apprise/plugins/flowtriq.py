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
# to a Flowtriq webhook channel.
#
# Users create a webhook channel in the Flowtriq dashboard, which provides
# a webhook URL and API key. The webhook URL path is used directly.
#
# URL format (HTTP):
#   flowtriq://apikey@hostname/webhook/path/
#   flowtriq://apikey@hostname:port/webhook/path/
#
# URL format (HTTPS):
#   flowtriqs://apikey@hostname/webhook/path/
#   flowtriqs://apikey@hostname:port/webhook/path/
#
# For example, if the dashboard gives you:
#   URL:  https://flowtriq.com/hooks/abc123
#   Key:  ft_key_xxxx
#
# Then the Apprise URL is (secure):
#   flowtriqs://ft_key_xxxx@flowtriq.com/hooks/abc123/
#
# Or for a self-hosted instance over plain HTTP:
#   flowtriq://ft_key_xxxx@myhost/hooks/abc123/
#
# Alternatively, the native HTTP/HTTPS URL with the API key in the user
# field is also accepted by parse_native_url():
#   https://ft_key_xxxx@flowtriq.com/hooks/abc123
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

    # The default protocol (plain HTTP for self-hosted instances)
    protocol = "flowtriq"

    # The default secure protocol (HTTPS)
    secure_protocol = "flowtriqs"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/flowtriq/"

    # Disable throttle rate
    request_rate_per_sec = 0

    # Title is not used for Flowtriq
    title_maxlen = 250

    # Define object templates
    templates = (
        "{schema}://{apikey}@{host}/{path}/",
        "{schema}://{apikey}@{host}:{port}/{path}/",
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
            "path": {
                "name": _("Webhook Path"),
                "type": "string",
                "required": True,
                "map_to": "webhook_path",
            },
        },
    )

    def __init__(self, apikey, webhook_path, **kwargs):
        """Initialize Flowtriq Object."""
        super().__init__(**kwargs)

        # API Key
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = "An invalid Flowtriq API Key ({}) was specified.".format(
                apikey
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Path (the full path portion of the webhook URL provided
        # by the Flowtriq dashboard)
        if not webhook_path:
            msg = "A Flowtriq Webhook Path must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.webhook_path = webhook_path.strip("/")
        if not self.webhook_path:
            msg = "A Flowtriq Webhook Path must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        if not self.host:
            msg = "A Flowtriq hostname must be specified."
            self.logger.warning(msg)
            raise TypeError(msg)

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Flowtriq Notification."""

        # Build our URL
        schema = "https" if self.secure else "http"
        url = "{}://{}".format(schema, self.host)
        if self.port is not None:
            url += ":{}".format(self.port)
        url += "/{}".format(self.webhook_path)

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
            "Flowtriq POST URL: %s (cert_verify=%s)",
            url,
            self.verify_certificate,
        )
        self.logger.debug("Flowtriq Payload: %s", str(payload))

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

                self.logger.debug("Response Details:\r\n%s", r.content)

                # Mark our failure
                return False

            self.logger.info("Sent Flowtriq notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Flowtriq "
                "notification to %s.",
                self.host,
            )
            self.logger.debug("Socket Exception: %s", str(e))

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
            self.secure_protocol if self.secure else self.protocol,
            self.host,
            self.port if self.port else (443 if self.secure else 80),
            self.webhook_path,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Our default port
        default_port = 443 if self.secure else 80
        return "{schema}://{apikey}@{hostname}{port}/{path}/?{params}".format(
            schema=(self.secure_protocol if self.secure else self.protocol),
            apikey=self.pprint(self.apikey, privacy, safe=""),
            hostname=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else ":{}".format(self.port)
            ),
            path=NotifyFlowtriq.quote(self.webhook_path, safe="/"),
            params=NotifyFlowtriq.urlencode(params),
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

        # The full path (minus leading/trailing slashes) is the webhook path
        fullpath = results.get("fullpath", "")
        if fullpath:
            results["webhook_path"] = fullpath.strip("/")
        else:
            results["webhook_path"] = None

        return results
