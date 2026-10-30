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

# xMatters (by Everbridge) is an incident management and on-call alerting
# platform.  Apprise raises alerts through a workflow's HTTP trigger.
#
# Steps to get your trigger URL:
#  1. Sign in to xMatters and open the Workflows tab.
#  2. Open Workflow Templates and pick the "Trigger Alerts by Webhook"
#     tile, then click Next.
#  3. Choose an authentication method.  "URL Authentication" is the
#     simplest since the API key is part of the URL.
#  4. Copy the trigger URL; it looks like:
#     https://acmeco.xmatters.com/api/integration/1/functions/\
#         ba601cb1-3513-4320-b48a-05cb501bb5af/triggers?\
#         apiKey=ffcd4dec-8a49-4a67-9e59-ed9fabcb002d&recipients=jdoe
#
#  You can paste that URL into Apprise as-is, or assemble it as:
#     xmatters://{apikey}@{host}/{integration_id}/{recipients}
#
#  With Basic or API Key Authentication, use your username and password
#  (or API key and secret) instead:
#     xmatters://{user}:{password}@{host}/{integration_id}/{recipients}
#
#  The host can be just your company name (acmeco); .xmatters.com is
#  added for you.  Recipients are the names of xMatters users, groups or
#  dynamic teams.
#
#  The webhook trigger only accepts a summary, a message and recipients,
#  so attachments are not supported.
#
# Resources:
# - https://help.xmatters.com/integrations/other/triggeralertsbywebhook.htm
# - https://help.xmatters.com/ondemand/flowdesigner/flow-triggers.htm
# - https://help.xmatters.com/xmapi/index.html#trigger-an-event

from __future__ import annotations

from json import dumps
import re
from typing import Any, Optional, Union

import requests

from ..common import NotifyFormat, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# The domain added to a host that is only a company name
XMATTERS_DOMAIN = "xmatters.com"

# Extend HTTP Error Messages
# Based on: https://help.xmatters.com/xmapi/index.html#response-codes
XMATTERS_HTTP_ERROR_MAP = {
    400: "Bad Request - Invalid payload.",
    401: "Unauthorized - Invalid credentials.",
    403: "Forbidden - The user may not trigger this workflow.",
    404: "Not Found - Invalid integration ID.",
    429: "Too many requests were made.",
}


class NotifyXMatters(NotifyBase):
    """A wrapper for xMatters Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "xMatters"

    # The services URL
    service_url = "https://www.xmatters.com/"

    # The default secure protocol
    secure_protocol = "xmatters"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/xmatters/"

    # Our HTTP trigger URL
    notify_url = (
        "https://{host}/api/integration/1/functions/{integration_id}/triggers"
    )

    # xMatters caps a trigger payload at 200,000 bytes, so this keeps
    # even multi-byte text well inside it.
    body_maxlen = 32768

    # Alerts are delivered by e-mail, SMS, voice and push
    notify_format = NotifyFormat.TEXT

    # Define object templates
    templates = (
        "{schema}://{apikey}@{host}/{integration_id}",
        "{schema}://{apikey}@{host}/{integration_id}/{targets}",
        "{schema}://{user}:{password}@{host}/{integration_id}",
        "{schema}://{user}:{password}@{host}/{integration_id}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
            },
            "user": {
                "name": _("Username"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "integration_id": {
                "name": _("Integration ID"),
                "type": "string",
                "required": True,
                "regex": (r"^[a-z0-9][a-z0-9-]*$", "i"),
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
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
            "to": {
                "alias_of": "targets",
            },
            "recipients": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(
        self,
        integration_id: str,
        apikey: Optional[str] = None,
        targets: Optional[Union[str, list[str]]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize xMatters Object."""
        super().__init__(**kwargs)

        # The host is required
        if not self.host:
            msg = "An xMatters host must be specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # The integration ID found in the trigger URL
        self.integration_id = validate_regex(
            integration_id, *self.template_tokens["integration_id"]["regex"]
        )
        if not self.integration_id:
            msg = (
                "An invalid xMatters integration ID "
                "({}) was specified.".format(integration_id)
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # A username and password means Basic Authentication, so any API
        # key is not needed.
        self.apikey = (
            None if self.user and self.password else validate_regex(apikey)
        )

        # We need one form of authentication or the other
        if not self.apikey and not (self.user and self.password):
            msg = (
                "An xMatters API key, or a username and password, "
                "must be specified."
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Recipient names may contain spaces, so only commas split them
        self.targets = parse_list(targets, allow_whitespace=False)

        return

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform xMatters Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # The summary is the alert subject.  Without a title, the start
        # of the body stands in for it.
        payload = {
            "summary": title if title else body[: self.title_maxlen],
            "message": body,
        }

        # Without recipients, the workflow decides who is notified
        if self.targets:
            payload["recipients"] = ",".join(self.targets)

        # A host without a domain is just the company name
        host = (
            self.host if "." in self.host else f"{self.host}.{XMATTERS_DOMAIN}"
        )

        # Prepare our URL
        notify_url = self.notify_url.format(
            host=host if not self.port else f"{host}:{self.port}",
            integration_id=NotifyXMatters.quote(self.integration_id, safe=""),
        )

        # URL Authentication passes the API key as a parameter, while
        # everything else uses Basic Authentication.
        params = {"apiKey": self.apikey} if self.apikey else None
        auth = None if self.apikey else (self.user, self.password)

        self.logger.debug(
            "xMatters POST URL: %s (cert_verify=%s)",
            notify_url,
            self.verify_certificate,
        )
        self.logger.debug("xMatters Payload: %s", payload)

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                params=params,
                auth=auth,
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
                status_str = NotifyXMatters.http_response_code_lookup(
                    r.status_code, XMATTERS_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send xMatters notification: %s%serror=%s.",
                    status_str,
                    ", " if status_str else "",
                    r.status_code,
                )

                self.logger.debug(
                    "Response Details:\r\n%r", (r.content or b"")[:2000]
                )

                # Return; we're done
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending xMatters "
                "notification to %s.",
                host,
            )
            self.logger.debug("Socket Exception: %s", str(e))

            # Return; we're done
            return False

        self.logger.info("Sent xMatters notification.")
        return True

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        # The host, its trigger and our credentials identify the connection
        return (
            self.secure_protocol,
            self.host,
            self.port,
            self.integration_id,
            self.apikey,
            self.user,
            self.password,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Extend our parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Our credentials, depending on how we authenticate
        auth = (
            "{apikey}@".format(
                apikey=self.pprint(self.apikey, privacy, safe="")
            )
            if self.apikey
            else "{user}:{password}@".format(
                user=NotifyXMatters.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )
        )

        # Our integration ID comes first, followed by our recipients
        entries = [NotifyXMatters.quote(self.integration_id, safe="")]
        entries.extend(NotifyXMatters.quote(t, safe="") for t in self.targets)

        return "{schema}://{auth}{host}{port}/{entries}/?{params}".format(
            schema=self.secure_protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            host=self.host,
            port="" if not self.port else f":{self.port}",
            entries="/".join(entries),
            params=NotifyXMatters.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The integration ID comes first, followed by our recipients
        entries = NotifyXMatters.split_path(results["fullpath"])
        results["integration_id"] = entries.pop(0) if entries else None
        results["targets"] = entries

        # Support ?to= and ?recipients= for recipients
        for key in ("to", "recipients"):
            if key in results["qsd"] and results["qsd"][key]:
                results["targets"] += parse_list(
                    NotifyXMatters.unquote(results["qsd"][key]),
                    allow_whitespace=False,
                )

        # Without a password, the user field holds our API key
        if not results["password"]:
            results["apikey"] = (
                NotifyXMatters.unquote(results["user"])
                if results["user"]
                else None
            )
            results["user"] = None

        # Support ?apikey= for our API key
        if "apikey" in results["qsd"] and results["qsd"]["apikey"]:
            results["apikey"] = NotifyXMatters.unquote(
                results["qsd"]["apikey"]
            )

        return results

    @staticmethod
    def parse_native_url(url: str) -> Optional[dict[str, Any]]:
        """Support the trigger URL copied from xMatters as-is."""
        result = re.match(
            r"^https?://(?P<host>[a-z0-9.-]+\.xmatters\.com)"
            r"/api/integration/1/functions/(?P<integration_id>[a-z0-9-]+)"
            r"/triggers/?(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyXMatters.parse_url(
                "{schema}://{host}/{integration_id}/{params}".format(
                    schema=NotifyXMatters.secure_protocol,
                    host=result.group("host"),
                    integration_id=result.group("integration_id"),
                    params=result.group("params") or "",
                )
            )

        return None
