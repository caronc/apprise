#
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

# Details at:
# https://docs.spug.dev/push/

import json
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import validate_regex
from .base import NotifyBase


class NotifySpugpush(NotifyBase):
    """A wrapper for SpugPush Notifications."""

    # The default descriptive name associated with the Notification
    service_name = _("SpugPush")

    # The services URL
    service_url = "https://docs.spug.dev/push/"

    # The default secure protocol
    secure_protocol = "spugpush"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_spugpush"

    # URL used to send notifications with
    notify_url = "https://push.spug.dev/send/"

    templates = ("{schema}://{token}",)

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Access Token"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[a-zA-Z0-9_-]{32,64}$", "i"),
            },
        },
    )

    def __init__(self, token, **kwargs):
        """Initialize SpugPush Object."""
        super().__init__(**kwargs)

        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"The SpugPush token ({token}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.webhook_url = f"{self.notify_url}{self.token}"

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""
        params = self.url_parameters(privacy=privacy, *args, **kwargs)
        return (
            f"{self.secure_protocol}://"
            f"{self.pprint(self.token, privacy, mode=PrivacyMode.Secret)}/"
            f"?{self.urlencode(params)}"
        )

    @property
    def url_identifier(self):
        """Returns a unique identifier for this plugin instance."""
        return (self.secure_protocol, self.token)

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Send a SpugPush Notification."""

        payload = {
            "title": title if title else body,
            "content": body,
        }

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        self.throttle()
        try:
            response = requests.post(
                self.webhook_url,
                headers=headers,
                data=json.dumps(payload),
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if response.status_code != requests.codes.ok:
                self.logger.warning(
                    "SpugPush notification failed: %d - %s",
                    response.status_code,
                    response.text,
                )
                return False

        except requests.RequestException as e:
            self.logger.warning(f"SpugPush Exception: {e}")
            return False

        self.logger.info("SpugPush notification sent successfully.")
        return True

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns arguments to re-instantiate the
        object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        if "token" in results["qsd"] and results["qsd"]["token"]:
            results["token"] = NotifySpugpush.unquote(results["qsd"]["token"])
        else:
            results["token"] = NotifySpugpush.unquote(results["host"])

        return results

    @staticmethod
    def parse_native_url(url):
        """Parse native SpugPush webhook URL into Apprise format."""
        match = re.match(
            r"^https://push\.spug\.dev/send/([a-z0-9_-]+)$", url, re.I
        )
        if not match:
            return None

        return NotifySpugpush.parse_url(
            f"{NotifySpugpush.secure_protocol}://{match.group(1)}"
        )
