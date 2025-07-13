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

# To use this plugin, you need to first access https://dev.flock.com/webhooks
# Specifically https://dev.flock.com/webhooks/incoming
#
# To create a new incoming webhook for your account. You'll need to
# follow the wizard to pre-determine the channel(s) you want your
# message to broadcast to. When you've completed this, you will
# recieve a URL that looks something like this:
# https://api.flock.com/hooks/sendMessage/134b8gh0-eba0-4fa9-ab9c-257ced0e8221
#                                                             ^
#                                                             |
#  This is important <----------------------------------------^
#
#  It becomes your 'token' that you will pass into this class
#
from json import dumps
import re

import requests

from ..common import NotifyFormat, NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

# Extend HTTP Error Messages
FLOCK_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Token.",
}

# Used to detect a channel/user
IS_CHANNEL_RE = re.compile(r"^(#|g:)(?P<id>[A-Z0-9_]+)$", re.I)
IS_USER_RE = re.compile(r"^(@|u:)?(?P<id>[A-Z0-9_]+)$", re.I)


class NotifyFlock(NotifyBase):
    """A wrapper for Flock Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Flock"

    # The services URL
    service_url = "https://flock.com/"

    # The default secure protocol
    secure_protocol = "flock"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_flock"

    # Flock uses the http protocol with JSON requests
    notify_url = "https://api.flock.com/hooks/sendMessage"

    # API Wrapper
    notify_api = "https://api.flock.co/v1/chat.sendMessage"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_72

    # Define object templates
    templates = (
        "{schema}://{token}",
        "{schema}://{botname}@{token}",
        "{schema}://{botname}@{token}/{targets}",
        "{schema}://{token}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Access Key"),
                "type": "string",
                "regex": (r"^[a-z0-9-]+$", "i"),
                "private": True,
                "required": True,
            },
            "botname": {
                "name": _("Bot Name"),
                "type": "string",
                "map_to": "user",
            },
            "to_user": {
                "name": _("To User ID"),
                "type": "string",
                "prefix": "@",
                "regex": (r"^[A-Z0-9_]+$", "i"),
                "map_to": "targets",
            },
            "to_channel": {
                "name": _("To Channel ID"),
                "type": "string",
                "prefix": "#",
                "regex": (r"^[A-Z0-9_]+$", "i"),
                "map_to": "targets",
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
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    def __init__(self, token, targets=None, include_image=True, **kwargs):
        """Initialize Flock Object."""
        super().__init__(**kwargs)

        # Build ourselves a target list
        self.targets = []

        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid Flock Access Key ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Track whether or not we want to send an image with our notification
        # or not.
        self.include_image = include_image

        # Track any issues
        has_error = False

        # Tidy our targets
        targets = parse_list(targets)

        for target in targets:
            result = IS_USER_RE.match(target)
            if result:
                self.targets.append("u:" + result.group("id"))
                continue

            result = IS_CHANNEL_RE.match(target)
            if result:
                self.targets.append("g:" + result.group("id"))
                continue

            has_error = True
            self.logger.warning(
                f"Ignoring invalid target ({target}) specified."
            )

        if has_error and not self.targets:
            # We have a bot token and no target(s) to message
            msg = "No Flock targets to notify."
            self.logger.warning(msg)
            raise TypeError(msg)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Flock Notification."""

        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # error tracking (used for function return)
        has_error = False

        if self.notify_format == NotifyFormat.HTML:
            body = f"<flockml>{body}</flockml>"

        else:
            title = NotifyFlock.escape_html(title, whitespace=False)
            body = NotifyFlock.escape_html(body, whitespace=False)

            body = "<flockml>{}{}</flockml>".format(
                "" if not title else f"<b>{title}</b><br/>", body
            )

        payload = {
            "token": self.token,
            "flockml": body,
            "sendAs": {
                "name": self.app_id if not self.user else self.user,
                # A Profile Image is only configured if we're configured to
                # allow it
                "profileImage": (
                    None
                    if not self.include_image
                    else self.image_url(notify_type)
                ),
            },
        }

        if len(self.targets):
            # Create a copy of our targets
            targets = list(self.targets)

            while len(targets) > 0:
                # Get our first item
                target = targets.pop(0)

                # Copy and update our payload
                _payload = payload.copy()
                _payload["to"] = target

                if not self._post(self.notify_api, headers, _payload):
                    has_error = True

        else:
            # Webhook
            url = f"{self.notify_url}/{self.token}"
            if not self._post(url, headers, payload):
                has_error = True

        return not has_error

    def _post(self, url, headers, payload):
        """A wrapper to the requests object."""

        # error tracking (used for function return)
        has_error = False

        self.logger.debug(
            f"Flock POST URL: {url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Flock Payload: {payload!s}")

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
                status_str = NotifyFlock.http_response_code_lookup(
                    r.status_code, FLOCK_HTTP_ERROR_MAP
                )

                self.logger.warning(
                    "Failed to send Flock notification : {}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Mark our failure
                has_error = True

            else:
                self.logger.info("Sent Flock notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Flock notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Mark our failure
            has_error = True

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "image": "yes" if self.include_image else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{token}/{targets}?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(self.token, privacy, safe=""),
            targets="/".join(
                [NotifyFlock.quote(target, safe="") for target in self.targets]
            ),
            params=NotifyFlock.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        targets = len(self.targets)
        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results["targets"] = NotifyFlock.split_path(results["fullpath"])

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyFlock.parse_list(results["qsd"]["to"])

        # The first token is stored in the hostname
        results["token"] = NotifyFlock.unquote(results["host"])

        # Include images with our message
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://api.flock.com/hooks/sendMessage/TOKEN
        """

        result = re.match(
            r"^https?://api\.flock\.com/hooks/sendMessage/"
            r"(?P<token>[a-z0-9-]{24})/?"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifyFlock.parse_url(
                "{schema}://{token}/{params}".format(
                    schema=NotifyFlock.secure_protocol,
                    token=result.group("token"),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None
