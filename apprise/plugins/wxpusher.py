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
# Sign-up at https://wxpusher.zjiecode.com/
#
# Login and acquire your App Token
#   - Open the backend of the application:
#         https://wxpusher.zjiecode.com/admin/
#   - Find the appToken menu from the left menu bar, here you can reset the
#     appToken, please note that after resetting, the old appToken will be
#     invalid immediately and the call interface will fail.
from itertools import chain
import json
import re

import requests

from ..common import NotifyFormat, NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase

# Topics are always numerical
IS_TOPIC = re.compile(r"^\s*(?P<topic>[1-9][0-9]{0,20})\s*$")

# users always start with UID_
IS_USER = re.compile(
    r"^\s*(?P<full>(?P<prefix>UID_)(?P<user>[^\s]+))\s*$", re.I
)


WXPUSHER_RESPONSE_CODES = {
    1000: "The request was processed successfully.",
    1001: "The token provided in the request is missing.",
    1002: "The token provided in the request is incorrect or expired.",
    1003: "The body of the message was not provided.",
    1004: (
        "The user or topic you're trying to send the message to does not exist"
    ),
    1005: "The app or topic binding process failed.",
    1006: "There was an error in sending the message.",
    1007: "The message content exceeds the allowed length.",
    1008: (
        "The API call frequency is too high and the server rejected the "
        "request."
    ),
    1009: (
        "There might be other issues that are not explicitly covered by "
        "the above codes"
    ),
    1010: "The IP address making the request is not whitelisted.",
}


class WxPusherContentType:
    """Defines the different supported content types."""

    TEXT = 1
    HTML = 2
    MARKDOWN = 3


class SubscriptionType:
    # Verify Subscription Time
    UNVERIFIED = 0
    PAID_USERS = 1
    UNSUBSCRIBED = 2


class NotifyWxPusher(NotifyBase):
    """A wrapper for WxPusher Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "WxPusher"

    # The services URL
    service_url = "https://wxpusher.zjiecode.com/"

    # The default protocol
    secure_protocol = "wxpusher"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_wxpusher"

    # WxPusher notification endpoint
    notify_url = "https://wxpusher.zjiecode.com/api/send/message"

    # Define object templates
    templates = ("{schema}://{token}/{targets}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "token": {
                "name": _("App Token"),
                "type": "string",
                "required": True,
                "regex": (r"^AT_[^\s]+$", "i"),
                "private": True,
            },
            "target_topic": {
                "name": _("Target Topic"),
                "type": "int",
                "map_to": "targets",
            },
            "target_user": {
                "name": _("Target User ID"),
                "type": "string",
                "regex": (r"^UID_[^\s]+$", "i"),
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
            "to": {
                "alias_of": "targets",
            },
            "token": {
                "alias_of": "token",
            },
        },
    )

    # Used for mapping the content type to our output since Apprise supports
    # The same formats that WxPusher does.
    __content_type_map = {
        NotifyFormat.MARKDOWN: WxPusherContentType.MARKDOWN,
        NotifyFormat.TEXT: WxPusherContentType.TEXT,
        NotifyFormat.HTML: WxPusherContentType.HTML,
    }

    def __init__(self, token, targets=None, **kwargs):
        """Initialize WxPusher Object."""
        super().__init__(**kwargs)

        # App Token (associated with WxPusher account)
        self.token = validate_regex(
            token, *self.template_tokens["token"]["regex"]
        )
        if not self.token:
            msg = f"An invalid WxPusher App Token ({token}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Used for URL generation afterwards only
        self._invalid_targets = []

        # For storing what is detected
        self._users = []
        self._topics = []

        # Parse our targets
        for target in parse_list(targets):
            # Validate targets and drop bad ones:
            result = IS_USER.match(target)
            if result:
                # store valid user
                self._users.append(result["full"])
                continue

            result = IS_TOPIC.match(target)
            if result:
                # store valid topic
                self._topics.append(int(result["topic"]))
                continue

            self.logger.warning(
                f"Dropped invalid WxPusher user/topic ({target}) specified.",
            )
            self._invalid_targets.append(target)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform WxPusher Notification."""

        if not self._users and not self._topics:
            # There were no services to notify
            self.logger.warning("There were no WxPusher targets to notify")
            return False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Prepare our payload
        payload = {
            "appToken": self.token,
            "content": body,
            "summary": title,
            "contentType": self.__content_type_map[self.notify_format],
            "topicIds": self._topics,
            "uids": self._users,
            # unsupported at this time
            # 'verifyPay': False,
            # 'verifyPayType': 0,
            "url": None,
        }

        # Some Debug Logging
        self.logger.debug(
            f"WxPusher POST URL: {self.notify_url} "
            f"(cert_verify={self.verify_certificate})"
        )
        self.logger.debug(f"WxPusher Payload: {payload}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                self.notify_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            try:
                content = json.loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            # 1000 is the expected return code for a successful query
            if (
                r.status_code == requests.codes.ok
                and content
                and content.get("code") == 1000
            ):

                # We're good!
                self.logger.info(
                    "Sent WxPusher notification to %d targets.",
                    len(self._users) + len(self._topics),
                )

            else:
                error_str = (
                    content.get("msg")
                    if content
                    else (
                        WXPUSHER_RESPONSE_CODES.get(
                            content.get("code") if content else None,
                            "An unknown error occured.",
                        )
                    )
                )

                # We had a problem
                status_str = (
                    error_str
                    if error_str
                    else NotifyWxPusher.http_response_code_lookup(
                        r.status_code
                    )
                )

                self.logger.warning(
                    "Failed to send WxPusher notification, "
                    "code={}/{}: {}".format(
                        r.status_code,
                        "unk" if not content else content.get("code"),
                        status_str,
                    )
                )

                self.logger.debug(
                    f"Response Details:\r\n{content if content else r.content}"
                )

                # Mark our failure
                return False

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending WxPusher notification."
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
        return (self.secure_protocol, self.token)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return "{schema}://{token}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            token=self.pprint(
                self.token, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            targets="/".join(
                chain(
                    [str(t) for t in self._topics],
                    self._users,
                    [
                        NotifyWxPusher.quote(x, safe="")
                        for x in self._invalid_targets
                    ],
                )
            ),
            params=NotifyWxPusher.urlencode(params),
        )

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
        results["targets"] = NotifyWxPusher.split_path(results["fullpath"])

        # App Token
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            # Extract the App token from an argument
            results["token"] = NotifyWxPusher.unquote(results["qsd"]["token"])
            # Any host entry defined is actually part of the path
            # store it's element (if defined)
            if results["host"]:
                results["targets"].append(
                    NotifyWxPusher.split_path(results["host"])
                )

        else:
            # The hostname is our source number
            results["token"] = NotifyWxPusher.unquote(results["host"])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyWxPusher.parse_list(
                results["qsd"]["to"]
            )

        return results
