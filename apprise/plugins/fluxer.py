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

# For this to work correctly you need to create a webhook. To do this just
# click on the little gear icon next to the channel you're part of. From
# here you'll be able to access the Webhooks menu and create a new one.
#
#  When you've completed, you'll get a URL that looks a little like this:
#  https://api.fluxer.app/webhooks/417429632418316298/\
#         JHZ7lQml277CDHmQKMHI8qBe7bk2ZwO5UKjCiOAF7711o33MyqU344Qpgv7YTpadV
#
#  Simplified, it looks like this:
#     https://api.fluxer.app/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
#
#  This plugin will simply work using the url of:
#     fluxer://WEBHOOK_ID/WEBHOOK_TOKEN
#
from __future__ import annotations

import re
from typing import Any

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import (
    is_hostname,
    is_ipaddr,
    parse_bool,
    validate_regex,
)
from .base import NotifyBase


class FluxerMode:
    """Define Fluxer Notification Modes."""

    # App posts upstream to the developer API on Fluxer's website
    CLOUD = "cloud"

    # Running a dedicated private Fluxer Server
    PRIVATE = "private"


FLUXER_MODES = (
    FluxerMode.CLOUD,
    FluxerMode.PRIVATE,
)


class NotifyFluxer(NotifyBase):
    """A wrapper for Fluxer Webhook Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Fluxer"

    # The Services URL
    service_url = "https://fluxer.app/"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/fluxer/"

    # The default protocol
    protocol = "fluxer"

    # The default secure protocol
    secure_protocol = "fluxers"

    # The maximum size of the message body
    body_maxlen = 2000

    # if our hostname matches the following we automatically enforce
    # cloud mode
    __auto_cloud_host = re.compile(r"fluxer\.app", re.IGNORECASE)

    # Default upstream/cloud host if none is defined
    cloud_notify_host = "api.fluxer.app"

    # Webhook URLs used by the Fluxer API.
    notify_url = "{prefix}/webhooks/{webhook_id}/{webhook_token}"

    template_tokens = (
        "{schema}://{webhook_id}/{webhook_token}",
        "{schema}://{host}/{webhook_id}/{webhook_token}",
        "{schema}://{host}:{port}/{webhook_id}/{webhook_token}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
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
            "webhook_id": {
                "name": _("Webhook ID"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "webhook_token": {
                "name": _("Webhook Token"),
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
            "tts": {
                "name": _("Text To Speech"),
                "type": "bool",
                "default": False,
            },
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": FLUXER_MODES,
                "default": FluxerMode.CLOUD,
            },
        },
    )

    # Used to validate Fluxer webhook identifiers and tokens
    # - webhook_id appears to be a snowflake-like integer identifier
    # - webhook_token is a URL-safe token string
    _re_webhook_id = re.compile(r"^[0-9]{10,}$")
    _re_webhook_token = re.compile(r"^[A-Za-z0-9_\-]{16,}$")

    def __init__(
        self,
        webhook_id: str,
        webhook_token: str,
        tts: bool = False,
        mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Fluxer Object."""

        super().__init__(**kwargs)

        # Webhook ID (associated with project)
        self.webhook_id = validate_regex(webhook_id)
        if not self.webhook_id:
            msg = (
                f"An invalid Fluxer Webhook ID ({webhook_id}) was "
                "specified.")
            self.logger.warning(msg)
            raise TypeError(msg)

        # Webhook Token (associated with project)
        self.webhook_token = validate_regex(webhook_token)
        if not self.webhook_token:
            msg = (
                "An invalid Fluxer Webhook Token "
                f"({webhook_token}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare our mode
        self.mode = (
            mode.strip().lower()
            if isinstance(mode, str)
            else self.template_args["mode"]["default"]
        )

        if self.mode not in FLUXER_MODES:
            msg = f"An invalid Fluxer Mode ({mode}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        if not self.host and self.mode == FluxerMode.PRIVATE:
            # No host provided
            msg = f"An invalid Fluxer Hostname ({self.host}) was provided."
            self.logger.warning(msg)
            raise TypeError(msg)

        elif self.mode == FluxerMode.PRIVATE and \
                self.__auto_cloud_host.search(self.host):
            # Is a Fluxer Cloud API
            self.mode = FluxerMode.CLOUD
            self.logger.warning(
                "Fluxer mode changed to %s mode because fluxer.app found "
                "in %s", self.mode, self.host)

        # Text To Speech
        self.tts = tts if tts is not None \
            else self.template_args["mode"]["default"]

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:

        """Perform Fluxer Notification."""

        # Prepare our headers:

        self.throttle()

        payload = {
            "content": body
        }

        if self.tts:
            payload["tts"] = True

        if self.mode == FluxerMode.CLOUD:
            prefix = f"https://{NotifyFluxer.cloud_notify_host}"

        else:
            # Prepare our Fluxer Template URL
            schema = "https" if self.secure else "http"

            # Construct Notify URL
            prefix = f"{schema}://{self.host}"
            if isinstance(self.port, int):
                prefix += f":{self.port}"

        notify_url = self.notify_url.format(
            prefix=prefix,
            webhook_id=self.webhook_id,
            webhook_token=self.webhook_token,
        )

        self.logger.debug(
            "Fluxer POST URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Fluxer Payload: {payload!s}")

        try:
            response = requests.post(
                notify_url,
                json=payload,
                headers={"User-Agent": self.app_id},
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if response.status_code not in (requests.codes.ok, 204):
                # We had a problem
                status_str = NotifyBase.http_response_code_lookup(
                    response.status_code
                )

                self.logger.warning(
                    "Failed to send Fluxer notification: "
                    "{}, error={}".format(
                        status_str,
                        response.status_code,
                    )
                )

                self.logger.debug(
                    "Response Details:\r\n%r",
                    (response.content or b"")[:2000])

                return False

            # otherwise we were successful
            self.logger.info(f"Sent Fluxer notification to '{notify_url}'.")

            return True

        except requests.RequestException as e:
            self.logger.warning(
                f"A Connection error occurred sending Fluxer:{notify_url} "
                + "notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

        return False

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        params: dict[str, str] = {
            "tts": "yes" if self.tts else "no",
            "mode": self.mode,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.mode == FluxerMode.PRIVATE:
            default_port = 443 if self.secure else 80
            return (
                "{schema}://{host}{port}{webhook_id}/"
                "{webhook_token}/?{params}".format(
                    schema=self.secure_protocol
                    if self.secure else self.protocol,
                    host=self.host,
                    port=(
                        ""
                        if self.port is None or self.port == default_port
                        else f":{self.port}"
                    ),
                    webhook_id=self.pprint(self.webhook_id, privacy, safe=""),
                    webhook_token=self.pprint(
                        self.webhook_token, privacy, safe=""),
                    params=NotifyFluxer.urlencode(params),
                )
            )
        else:  # Cloud mode
            return (
                "{schema}://{webhook_id}/{webhook_token}/?{params}".format(
                    schema=self.protocol,
                    webhook_id=self.pprint(self.webhook_id, privacy, safe=""),
                    webhook_token=self.pprint(
                        self.webhook_token, privacy, safe=""),
                    params=NotifyFluxer.urlencode(params),
                )
            )

    @property
    def url_identifier(self) -> tuple[str, str, str]:
        """Returns all of the identifiers that make this URL unique."""
        kwargs = [
            (
                self.secure_protocol
                if self.mode == FluxerMode.CLOUD
                else (self.secure_protocol if self.secure else self.protocol)
            ),
            self.host if self.mode == FluxerMode.PRIVATE else "",
            (
                443
                if self.mode == FluxerMode.CLOUD
                else (self.port if self.port else (443 if self.secure else 80))
            ),
            self.webhook_id,
            self.webhook_token,
        ]

        return kwargs

    @staticmethod
    def parse_url(url: str) -> dict[str, Any] | None:
        """Parses the URL and returns arguments for instantiating this object.

        Syntax:
          fluxer://webhook_id/webhook_token
        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Tokenize our URL
        tokens = \
            [NotifyFluxer.unquote(results["host"]),
             *NotifyFluxer.split_path(results["fullpath"])]

        # Text To Speech
        results["tts"] = parse_bool(results["qsd"].get("tts", False))

        # Mode override
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyFluxer.unquote(
                results["qsd"]["mode"].strip().lower()
            )

        else:
            # We can try to detect the mode based on the validity of the
            # hostname.
            #
            # This isn't a surfire way to do things though; it's best to
            # specify the mode= flag
            results["mode"] = (
                FluxerMode.PRIVATE
                if (
                    (
                        is_hostname(results["host"])
                        or is_ipaddr(results["host"])
                    )
                    and len(tokens) > 2
                )
                else FluxerMode.CLOUD
            )

        # Pop our tokens from back to front
        results["webhook_token"] = None if not tokens else tokens.pop()
        results["webhook_id"] = None if not tokens else tokens.pop()

        return results

    @staticmethod
    def parse_native_url(url: str) -> dict[str, Any] | None:
        """
        Support https://api.fluxer.app/webhooks/WEBHOOK_ID/WEBHOOK_TOKEN
        """

        result = re.match(
            r"^https?://api\.fluxer\.app\.com/webhooks/"
            r"(?P<webhook_id>[0-9]+)/"
            r"(?P<webhook_token>[A-Z0-9_-]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyFluxer.parse_url(
                "{schema}://{webhook_id}/{webhook_token}/{params}".format(
                    schema=NotifyFluxer.secure_protocol,
                    webhook_id=result.group("webhook_id"),
                    webhook_token=result.group("webhook_token"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None
