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

# API reference: https://pushy.me/docs/api/send-notifications
from itertools import chain
from json import dumps, loads
import re

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# Used to detect a Device and Topic
VALIDATE_DEVICE = re.compile(r"^@(?P<device>[a-z0-9]+)$", re.I)
VALIDATE_TOPIC = re.compile(r"^[#]?(?P<topic>[a-z0-9]+)$", re.I)

# Extend HTTP Error Messages
PUSHY_HTTP_ERROR_MAP = {
    401: "Unauthorized - Invalid Token.",
}


class NotifyPushy(NotifyBase):
    """A wrapper for Pushy Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Pushy"

    # The services URL
    service_url = "https://pushy.me/"

    # All Pushy requests are secure
    secure_protocol = "pushy"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_pushy"

    # Pushy uses the http protocol with JSON requests
    notify_url = "https://api.pushy.me/push?api_key={apikey}"

    # The maximum allowable characters allowed in the body per message
    body_maxlen = 4096

    # Define object templates
    templates = ("{schema}://{apikey}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("Secret API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "target_device": {
                "name": _("Target Device"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "target_topic": {
                "name": _("Target Topic"),
                "type": "string",
                "prefix": "#",
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
            "sound": {
                # Specify something like ping.aiff
                "name": _("Sound"),
                "type": "string",
            },
            "badge": {
                "name": _("Badge"),
                "type": "int",
                "min": 0,
            },
            "to": {
                "alias_of": "targets",
            },
            "key": {
                "alias_of": "apikey",
            },
        },
    )

    def __init__(self, apikey, targets=None, sound=None, badge=None, **kwargs):
        """Initialize Pushy Object."""
        super().__init__(**kwargs)

        # Access Token (associated with project)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Pushy Secret API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Get our targets
        self.devices = []
        self.topics = []

        for target in parse_list(targets):
            result = VALIDATE_TOPIC.match(target)
            if result:
                self.topics.append(result.group("topic"))
                continue

            result = VALIDATE_DEVICE.match(target)
            if result:
                self.devices.append(result.group("device"))
                continue

            self.logger.warning(
                f"Dropped invalid topic/device  ({target}) specified.",
            )

        # Setup our sound
        self.sound = sound

        # Badge
        try:
            # Acquire our badge count if we can:
            #  - We accept both the integer form as well as a string
            #    representation
            self.badge = int(badge)
            if self.badge < 0:
                raise ValueError()

        except TypeError:
            # NoneType means use Default; this is an okay exception
            self.badge = None

        except ValueError:
            self.badge = None
            self.logger.warning(
                "The specified Pushy badge ({}) is not valid ", badge
            )

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Pushy Notification."""

        if len(self.topics) + len(self.devices) == 0:
            # There were no services to notify
            self.logger.warning("There were no Pushy targets to notify.")
            return False

        # error tracking (used for function return)
        has_error = False

        # Default Header
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accepts": "application/json",
        }

        # Our URL
        notify_url = self.notify_url.format(apikey=self.apikey)

        # Default content response object
        content = {}

        # Create a copy of targets (topics and devices)
        targets = list(self.topics) + list(self.devices)
        while len(targets):
            target = targets.pop(0)

            # prepare JSON Object
            payload = {
                # Mandatory fields
                "to": target,
                "data": {
                    "message": body,
                },
                "notification": {
                    "body": body,
                },
            }

            # Optional payload items
            if title:
                payload["notification"]["title"] = title

            if self.sound:
                payload["notification"]["sound"] = self.sound

            if self.badge is not None:
                payload["notification"]["badge"] = self.badge

            self.logger.debug(
                "Pushy POST URL:"
                f" {notify_url} (cert_verify={self.verify_certificate!r})"
            )
            self.logger.debug(f"Pushy Payload: {payload!s}")

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                # Sample response
                # See: https://pushy.me/docs/api/send-notifications
                # {
                #     "success": true,
                #     "id": "5ea9b214b47cad768a35f13a",
                #     "info": {
                #         "devices": 1
                #         "failed": ['abc']
                #     }
                # }
                try:
                    content = loads(r.content)

                except (AttributeError, TypeError, ValueError):
                    # ValueError = r.content is Unparsable
                    # TypeError = r.content is None
                    # AttributeError = r is None
                    content = {
                        "success": False,
                        "id": "",
                        "info": {},
                    }

                if r.status_code != requests.codes.ok or not content.get(
                    "success"
                ):

                    # We had a problem
                    status_str = NotifyPushy.http_response_code_lookup(
                        r.status_code, PUSHY_HTTP_ERROR_MAP
                    )

                    self.logger.warning(
                        "Failed to send Pushy notification to {}: "
                        "{}{}error={}.".format(
                            target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(f"Response Details:\r\n{r.content}")

                    has_error = True
                    continue

                else:
                    self.logger.info(f"Sent Pushy notification to {target}.")

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Pushy:%s "
                    "notification",
                    target,
                )
                self.logger.debug(f"Socket Exception: {e!s}")

                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {}
        if self.sound:
            params["sound"] = self.sound

        if self.badge is not None:
            params["badge"] = str(self.badge)

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{apikey}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets="/".join([
                NotifyPushy.quote(x, safe="@#")
                for x in chain(
                    # Topics are prefixed with a pound/hashtag symbol
                    [f"#{x}" for x in self.topics],
                    # Devices
                    [f"@{x}" for x in self.devices],
                )
            ]),
            params=NotifyPushy.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.topics) + len(self.devices)

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Token
        results["apikey"] = NotifyPushy.unquote(results["host"])

        # Retrieve all of our targets
        results["targets"] = NotifyPushy.split_path(results["fullpath"])

        # Get the sound
        if "sound" in results["qsd"] and len(results["qsd"]["sound"]):
            results["sound"] = NotifyPushy.unquote(results["qsd"]["sound"])

        # Badge
        if "badge" in results["qsd"] and results["qsd"]["badge"]:
            results["badge"] = NotifyPushy.unquote(
                results["qsd"]["badge"].strip()
            )

        # Support key variable to store Secret API Key
        if "key" in results["qsd"] and len(results["qsd"]["key"]):
            results["apikey"] = results["qsd"]["key"]

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyPushy.parse_list(results["qsd"]["to"])

        return results
