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

# To use this plugin, you need to first generate a webhook.

# When you're complete, you will recieve a URL that looks something like this:
#                https://apprise.ryver.com/application/webhook/ckhrjW8w672m6HG
#                          ^                                        ^
#                          |                                        |
#  These are important <---^----------------------------------------^
#
from json import dumps
import re

import requests

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, validate_regex
from .base import NotifyBase


class RyverWebhookMode:
    """Ryver supports to webhook modes."""

    SLACK = "slack"
    RYVER = "ryver"


# Define the types in a list for validation purposes
RYVER_WEBHOOK_MODES = (
    RyverWebhookMode.SLACK,
    RyverWebhookMode.RYVER,
)


class NotifyRyver(NotifyBase):
    """A wrapper for Ryver Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Ryver"

    # The services URL
    service_url = "https://ryver.com/"

    # The default secure protocol
    secure_protocol = "ryver"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_ryver"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 1000

    # Define object templates
    templates = (
        "{schema}://{organization}/{token}",
        "{schema}://{botname}@{organization}/{token}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "organization": {
                "name": _("Organization"),
                "type": "string",
                "required": True,
                "regex": (r"^[A-Z0-9_-]{3,32}$", "i"),
            },
            "token": {
                "name": _("Token"),
                "type": "string",
                "required": True,
                "private": True,
                "regex": (r"^[A-Z0-9]{15}$", "i"),
            },
            "botname": {
                "name": _("Bot Name"),
                "type": "string",
                "map_to": "user",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "mode": {
                "name": _("Webhook Mode"),
                "type": "choice:string",
                "values": RYVER_WEBHOOK_MODES,
                "default": RyverWebhookMode.RYVER,
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
        },
    )

    def __init__(
        self,
        organization,
        token,
        mode=RyverWebhookMode.RYVER,
        include_image=True,
        **kwargs,
    ):
        """Initialize Ryver Object."""
        super().__init__(**kwargs)

        # API Token (associated with project)
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid Ryver API Token ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Organization (associated with project)
        self.organization = validate_regex(
            organization, *self.template_tokens["organization"]["regex"]
        )
        if not self.organization:
            msg = (
                "An invalid Ryver Organization "
                f"({organization}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our webhook mode
        self.mode = None if not isinstance(mode, str) else mode.lower()

        if self.mode not in RYVER_WEBHOOK_MODES:
            msg = f"The Ryver webhook mode specified ({mode}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Place an image inline with the message body
        self.include_image = include_image

        # Slack formatting requirements are defined here which Ryver supports:
        # https://api.slack.com/docs/message-formatting
        self._re_formatting_map = {
            # New lines must become the string version
            r"\r\*\n": "\\n",
            # Escape other special characters
            r"&": "&amp;",
            r"<": "&lt;",
            r">": "&gt;",
        }

        # Iterate over above list and store content accordingly
        self._re_formatting_rules = re.compile(
            r"(" + "|".join(self._re_formatting_map.keys()) + r")",
            re.IGNORECASE,
        )

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Ryver Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        if self.mode == RyverWebhookMode.SLACK:
            # Perform Slack formatting
            title = self._re_formatting_rules.sub(  # pragma: no branch
                lambda x: self._re_formatting_map[x.group()],
                title,
            )
            body = self._re_formatting_rules.sub(  # pragma: no branch
                lambda x: self._re_formatting_map[x.group()],
                body,
            )

        url = f"https://{self.organization}.ryver.com/application/webhook/{self.token}"

        # prepare JSON Object
        payload = {
            "body": body if not title else f"**{title}**\r\n{body}",
            "createSource": {
                "displayName": self.user,
                "avatar": None,
            },
        }

        # Acquire our image url if configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )

        if image_url:
            payload["createSource"]["avatar"] = image_url

        self.logger.debug(
            f"Ryver POST URL: {url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Ryver Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                url,
                data=dumps(payload),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifyBase.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Ryver notification: {}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Ryver notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending"
                f" Ryver:{self.organization} "
                + "notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.organization, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
            "mode": self.mode,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine if there is a botname present
        botname = ""
        if self.user:
            botname = "{botname}@".format(
                botname=NotifyRyver.quote(self.user, safe=""),
            )

        return "{schema}://{botname}{organization}/{token}/?{params}".format(
            schema=self.secure_protocol,
            botname=botname,
            organization=NotifyRyver.quote(self.organization, safe=""),
            token=self.pprint(self.token, privacy, safe=""),
            params=NotifyRyver.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The first token is stored in the hostname
        results["organization"] = NotifyRyver.unquote(results["host"])

        # Now fetch the remaining tokens
        try:
            results["token"] = NotifyRyver.split_path(results["fullpath"])[0]

        except IndexError:
            # no token
            results["token"] = None

        # Retrieve the mode
        results["mode"] = results["qsd"].get("mode", RyverWebhookMode.RYVER)

        # use image= for consistency with the other plugins
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://RYVER_ORG.ryver.com/application/webhook/TOKEN
        """

        result = re.match(
            r"^https?://(?P<org>[A-Z0-9_-]+)\.ryver\.com/application/webhook/"
            r"(?P<webhook_token>[A-Z0-9]+)/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyRyver.parse_url(
                "{schema}://{org}/{webhook_token}/{params}".format(
                    schema=NotifyRyver.secure_protocol,
                    org=result.group("org"),
                    webhook_token=result.group("webhook_token"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None
