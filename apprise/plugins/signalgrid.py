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

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, validate_regex
from .base import NotifyBase


class NotifySignalgrid(NotifyBase):
    """A wrapper for Signalgrid Notifications."""

    service_name = "Signalgrid"

    service_url = "https://signalgrid.co/"

    protocol = "signalgrid"

    setup_url = "https://docs.signalgrid.co/integrations/apprise/"

    notify_url = "https://api.signalgrid.co/v1/push"

    templates = ("{schema}://{client_key}/{channel}",)

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "client_key": {
                "name": _("Client Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "channel": {
                "name": _("Channel Token"),
                "type": "string",
                "required": True,
            },
        },
    )

    template_args = dict(
        NotifyBase.template_args,
        **{
            "client_key": {
                "alias_of": "client_key",
            },
            "channel": {
                "alias_of": "channel",
            },
            "critical": {
                "name": _("Critical Notification"),
                "type": "bool",
                "default": False,
            },
        },
    )

    notify_type_map = {
        NotifyType.INFO: "INFO",
        NotifyType.SUCCESS: "SUCCESS",
        NotifyType.WARNING: "WARN",
        NotifyType.FAILURE: "CRIT",
    }

    def __init__(self, client_key, channel, critical=False, **kwargs):
        """Initialize Signalgrid Object."""
        super().__init__(**kwargs)

        self.client_key = validate_regex(client_key)
        if not self.client_key:
            msg = "An invalid Signalgrid Client Key was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.channel = validate_regex(channel)
        if not self.channel:
            msg = "An invalid Signalgrid Channel Token was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.critical = parse_bool(critical, False)

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Signalgrid Notification."""

        headers = {
            "User-Agent": self.app_id,
        }

        payload = {
            "client_key": self.client_key,
            "channel": self.channel,
            "title": title,
            "body": body,
            "type": self.notify_type_map.get(notify_type, "INFO"),
            "critical": "true" if self.critical else "false",
        }

        self.logger.debug(
            "Signalgrid POST URL:"
            f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
        )

        # Do not log client_key or channel.
        self.logger.debug(
            "Signalgrid Payload: title=%r, type=%r, critical=%r",
            title,
            payload["type"],
            payload["critical"],
        )

        self.throttle()

        try:
            response = requests.post(
                self.notify_url,
                data=payload,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
                allow_redirects=self.redirects,
            )

            if response.status_code != requests.codes.ok:
                status_str = NotifySignalgrid.http_response_code_lookup(
                    response.status_code
                )

                self.logger.warning(
                    (
                        "Failed to send Signalgrid notification:{}{}error={}."
                    ).format(
                        status_str,
                        ", " if status_str else "",
                        response.status_code,
                    )
                )
                self.logger.debug(
                    "Response Details:\r\n%r",
                    (response.content or b"")[:2000],
                )

                return False

            self.logger.info("Sent Signalgrid notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Signalgrid notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        return True

    @property
    def url_identifier(self):
        """Return identifiers unique to this Signalgrid configuration."""
        return (
            self.protocol,
            self.client_key,
            self.channel,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Return the Signalgrid Apprise URL."""

        params = {
            "critical": "true" if self.critical else "false",
        }

        params.update(
            self.url_parameters(
                privacy=privacy,
                *args,
                **kwargs,
            )
        )

        return "{schema}://{client_key}/{channel}/?{params}".format(
            schema=self.protocol,
            client_key=self.pprint(
                self.client_key,
                privacy,
                safe="",
            ),
            channel=NotifySignalgrid.quote(
                self.channel,
                safe="",
            ),
            params=NotifySignalgrid.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parse Signalgrid URL."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # client_key occupies the URL hostname:
        # signalgrid://CLIENT_KEY/CHANNEL
        results["client_key"] = NotifySignalgrid.unquote(
            results.get("host") or ""
        )

        # channel occupies the URL path.
        fullpath = results.get("fullpath") or ""
        results["channel"] = NotifySignalgrid.unquote(fullpath.strip("/"))

        # Query-string variants are supported as well.
        if "client_key" in results["qsd"] and len(
            results["qsd"]["client_key"]
        ):
            results["client_key"] = NotifySignalgrid.unquote(
                results["qsd"]["client_key"]
            )

        if "channel" in results["qsd"] and len(results["qsd"]["channel"]):
            results["channel"] = NotifySignalgrid.unquote(
                results["qsd"]["channel"]
            )

        results["critical"] = parse_bool(results["qsd"].get("critical", False))

        return results
