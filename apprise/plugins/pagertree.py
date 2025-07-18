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

from json import dumps
from uuid import uuid4

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import parse_list, validate_regex
from .base import NotifyBase


# Actions
class PagerTreeAction:
    CREATE = "create"
    ACKNOWLEDGE = "acknowledge"
    RESOLVE = "resolve"


# Urgencies
class PagerTreeUrgency:
    SILENT = "silent"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


PAGERTREE_ACTIONS = {
    PagerTreeAction.CREATE: "create",
    PagerTreeAction.ACKNOWLEDGE: "acknowledge",
    PagerTreeAction.RESOLVE: "resolve",
}

PAGERTREE_URGENCIES = {
    # Note: This also acts as a reverse lookup mapping
    PagerTreeUrgency.SILENT: "silent",
    PagerTreeUrgency.LOW: "low",
    PagerTreeUrgency.MEDIUM: "medium",
    PagerTreeUrgency.HIGH: "high",
    PagerTreeUrgency.CRITICAL: "critical",
}
# Extend HTTP Error Messages
PAGERTREE_HTTP_ERROR_MAP = {
    402: "Payment Required - Please subscribe or upgrade",
    403: "Forbidden - Blocked",
    404: "Not Found - Invalid Integration ID",
    405: "Method Not Allowed - Integration Disabled",
    429: "Too Many Requests - Rate Limit Exceeded",
}


class NotifyPagerTree(NotifyBase):
    """A wrapper for PagerTree Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "PagerTree"

    # The services URL
    service_url = "https://pagertree.com/"

    # All PagerTree requests are secure
    secure_protocol = "pagertree"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_pagertree"

    # PagerTree uses the http protocol with JSON requests
    notify_url = "https://api.pagertree.com/integration/{}"

    # Define object templates
    templates = ("{schema}://{integration}",)

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "integration": {
                "name": _("Integration ID"),
                "type": "string",
                "private": True,
                "required": True,
            }
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": PAGERTREE_ACTIONS,
                "default": PagerTreeAction.CREATE,
            },
            "thirdparty": {
                "name": _("Third Party ID"),
                "type": "string",
            },
            "urgency": {
                "name": _("Urgency"),
                "type": "choice:string",
                "values": PAGERTREE_URGENCIES,
            },
            "tags": {
                "name": _("Tags"),
                "type": "string",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "headers": {
            "name": _("HTTP Header"),
            "prefix": "+",
        },
        "payload_extras": {
            "name": _("Payload Extras"),
            "prefix": ":",
        },
        "meta_extras": {
            "name": _("Meta Extras"),
            "prefix": "-",
        },
    }

    def __init__(
        self,
        integration,
        action=None,
        thirdparty=None,
        urgency=None,
        tags=None,
        headers=None,
        payload_extras=None,
        meta_extras=None,
        **kwargs,
    ):
        """Initialize PagerTree Object."""
        super().__init__(**kwargs)

        # Integration ID (associated with account)
        self.integration = validate_regex(
            integration, r"^int_[a-zA-Z0-9\-_]{7,14}$"
        )
        if not self.integration:
            msg = (
                "An invalid PagerTree Integration ID "
                f"({integration}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # thirdparty (optional, in case they want to pass the
        # acknowledge or resolve action)
        self.thirdparty = None
        if thirdparty:
            # An id was specified, we want to validate it
            self.thirdparty = validate_regex(thirdparty)
            if not self.thirdparty:
                msg = (
                    "An invalid PagerTree third party ID "
                    f"({thirdparty}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        self.headers = {}
        if headers:
            # Store our extra headers
            self.headers.update(headers)

        self.payload_extras = {}
        if payload_extras:
            # Store our extra payload entries
            self.payload_extras.update(payload_extras)

        self.meta_extras = {}
        if meta_extras:
            # Store our extra payload entries
            self.meta_extras.update(meta_extras)

        # Setup our action
        self.action = (
            NotifyPagerTree.template_args["action"]["default"]
            if action not in PAGERTREE_ACTIONS
            else PAGERTREE_ACTIONS[action]
        )

        # Setup our urgency
        self.urgency = PAGERTREE_URGENCIES.get(urgency)

        # Any optional tags to attach to the notification
        self.__tags = parse_list(tags)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform PagerTree Notification."""

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Apply any/all header over-rides defined
        # For things like PagerTree Token
        headers.update(self.headers)

        # prepare JSON Object
        payload = {
            # Generate an ID (unless one was explicitly forced to be used)
            "id": self.thirdparty if self.thirdparty else str(uuid4()),
            "event_type": self.action,
        }

        if self.action == PagerTreeAction.CREATE:
            payload["title"] = title if title else self.app_desc
            payload["description"] = body

            payload["meta"] = self.meta_extras
            payload["tags"] = self.__tags

            if self.urgency is not None:
                payload["urgency"] = self.urgency

        # Apply any/all payload over-rides defined
        payload.update(self.payload_extras)

        # Prepare our URL based on integration
        notify_url = self.notify_url.format(self.integration)

        self.logger.debug(
            "PagerTree POST URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"PagerTree Payload: {payload!s}")

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
            if r.status_code not in (
                requests.codes.ok,
                requests.codes.created,
                requests.codes.accepted,
            ):
                # We had a problem
                status_str = NotifyPagerTree.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send PagerTree notification: "
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.info("Sent PagerTree notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending PagerTree "
                f"notification to {self.host}."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

            # Return; we're done
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.integration)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "action": self.action,
        }

        if self.thirdparty:
            params["tid"] = self.thirdparty

        if self.urgency:
            params["urgency"] = self.urgency

        if self.__tags:
            params["tags"] = ",".join(list(self.__tags))

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Headers prefixed with a '+' sign
        # Append our headers into our parameters
        params.update({f"+{k}": v for k, v in self.headers.items()})

        # Meta: {} prefixed with a '-' sign
        # Append our meta extras into our parameters
        params.update({f"-{k}": v for k, v in self.meta_extras.items()})

        # Payload body extras prefixed with a ':' sign
        # Append our payload extras into our parameters
        params.update({f":{k}": v for k, v in self.payload_extras.items()})

        return "{schema}://{integration}?{params}".format(
            schema=self.secure_protocol,
            # never encode hostname since we're expecting it to be a valid one
            integration=self.pprint(self.integration, privacy, safe=""),
            params=NotifyPagerTree.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)

        if not results:
            # We're done early as we couldn't load the results
            return results

        # Add our headers that the user can potentially over-ride if they wish
        # to to our returned result set and tidy entries by unquoting them
        results["headers"] = {
            NotifyPagerTree.unquote(x): NotifyPagerTree.unquote(y)
            for x, y in results["qsd+"].items()
        }

        # store any additional payload extra's defined
        results["payload_extras"] = {
            NotifyPagerTree.unquote(x): NotifyPagerTree.unquote(y)
            for x, y in results["qsd:"].items()
        }

        # store any additional meta extra's defined
        results["meta_extras"] = {
            NotifyPagerTree.unquote(x): NotifyPagerTree.unquote(y)
            for x, y in results["qsd-"].items()
        }

        # Integration ID
        if "id" in results["qsd"] and len(results["qsd"]["id"]):
            # Shortened version of integration id
            results["integration"] = NotifyPagerTree.unquote(
                results["qsd"]["id"]
            )

        elif "integration" in results["qsd"] and len(
            results["qsd"]["integration"]
        ):
            results["integration"] = NotifyPagerTree.unquote(
                results["qsd"]["integration"]
            )

        else:
            results["integration"] = NotifyPagerTree.unquote(results["host"])

        # Set our thirdparty

        if "tid" in results["qsd"] and len(results["qsd"]["tid"]):
            # Shortened version of thirdparty
            results["thirdparty"] = NotifyPagerTree.unquote(
                results["qsd"]["tid"]
            )

        elif "thirdparty" in results["qsd"] and len(
            results["qsd"]["thirdparty"]
        ):
            results["thirdparty"] = NotifyPagerTree.unquote(
                results["qsd"]["thirdparty"]
            )

        # Set our urgency
        if "action" in results["qsd"] and len(results["qsd"]["action"]):
            results["action"] = NotifyPagerTree.unquote(
                results["qsd"]["action"]
            )

        # Set our urgency
        if "urgency" in results["qsd"] and len(results["qsd"]["urgency"]):
            results["urgency"] = NotifyPagerTree.unquote(
                results["qsd"]["urgency"]
            )

        # Set our tags
        if "tags" in results["qsd"] and len(results["qsd"]["tags"]):
            results["tags"] = parse_list(
                NotifyPagerTree.unquote(results["qsd"]["tags"])
            )

        return results
