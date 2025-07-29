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

#
# API Docs: https://developers.line.biz/en/reference/messaging-api/

from json import dumps
import re

import requests

from ..common import NotifyImageSize, NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool, parse_list, validate_regex
from .base import NotifyBase

# Used to break path apart into list of streams
TARGET_LIST_DELIM = re.compile(r"[ \t\r\n,#\\/]+")


class NotifyLine(NotifyBase):
    """A wrapper for Line Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Line"

    # The services URL
    service_url = "https://line.me/"

    # Secure Protocol
    secure_protocol = "line"

    # The URL refererenced for remote Notifications
    notify_url = "https://api.line.me/v2/bot/message/push"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_line"

    # We don't support titles for Line notifications
    title_maxlen = 0

    # Maximum body length is 5000
    body_maxlen = 5000

    # Allows the user to specify the NotifyImageSize object; this is supported
    # through the webhook
    image_size = NotifyImageSize.XY_128

    # Define object templates
    templates = ("{schema}://{token}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("Access Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
                "required": True,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "to": {
                "alias_of": "targets",
            },
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
        },
    )

    def __init__(self, token, targets=None, include_image=True, **kwargs):
        """Initialize Line Object."""
        super().__init__(**kwargs)

        # Long-Lived Access token (generated from User Profile)
        self.token = validate_regex(token)
        if not self.token:
            msg = f"An invalid Access Token ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Display our Apprise Image
        self.include_image = include_image

        # Set up our targets
        self.targets = parse_list(targets)

        # A dictionary of cached users
        self.__cached_users = {}

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Send our Line Notification."""

        if len(self.targets) == 0:
            # There were no services to notify
            self.logger.warning("There were no Line targets to notify.")
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        # Prepare our persistent_notification.create payload
        payload = {
            "to": None,
            "messages": [{
                "type": "text",
                "text": body,
                "sender": {
                    "name": self.app_id,
                },
            }],
        }

        # Acquire our image url if configured to do so
        image_url = (
            None if not self.include_image else self.image_url(notify_type)
        )

        if image_url:
            payload["messages"][0]["sender"]["iconUrl"] = image_url

        # Create a copy of the target list
        targets = list(self.targets)
        while len(targets):
            target = targets.pop(0)

            payload["to"] = target

            self.logger.debug(
                "Line POST URL:"
                f" {self.notify_url} (cert_verify={self.verify_certificate!r})"
            )
            self.logger.debug(f"Line Payload: {payload!s}")

            # Always call throttle before any remote server i/o is made
            self.throttle()
            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )
                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyLine.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send Line notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(f"Sent Line notification to {target}.")

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Line "
                    f"notification to {target}."
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                # Mark our failure
                has_error = True
                continue

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
            # never encode hostname since we're expecting it to be a valid one
            token=self.pprint(
                self.token, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            targets="/".join(
                [self.pprint(x, privacy, safe="") for x in self.targets]
            ),
            params=NotifyLine.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.targets)

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get unquoted entries
        results["targets"] = NotifyLine.split_path(results["fullpath"])

        # The 'token' makes it easier to use yaml configuration
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["token"] = NotifyLine.unquote(results["qsd"]["token"])
        else:
            results["token"] = NotifyLine.unquote(results["host"])

            # Line Long Lived Tokens included forward slashes in them.
            # As a result we need to parse further into our path and look
            # for the entry that ends in an equal symbol.
            if not results["token"].endswith("="):
                for index, entry in enumerate(
                    list(results["targets"]), start=1
                ):
                    if entry.endswith("="):
                        # Found
                        results["token"] += "/" + "/".join(
                            results["targets"][0:index]
                        )
                        results["targets"] = results["targets"][index:]
                        break

        # Include images with our message
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += list(
                filter(
                    bool,
                    TARGET_LIST_DELIM.split(
                        NotifyLine.unquote(results["qsd"]["to"])
                    ),
                )
            )

        return results
