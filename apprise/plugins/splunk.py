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

# Splunk On-Call
# API: https://portal.victorops.com/public/api-docs.html
# Main: https://www.splunk.com/en_us/products/on-call.html
# Routing Keys https://help.victorops.com/knowledge-base/routing-keys/
# Setup: https://help.victorops.com/knowledge-base/rest-endpoint-integration\
#       -guide/


from json import dumps
import re

import requests

from ..common import NOTIFY_TYPES, NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import validate_regex
from .base import NotifyBase


class SplunkAction:
    """Tracks the actions supported by Apprise Splunk Plugin."""

    # Use mapping (specify :key=arg to over-ride)
    MAP = "map"

    # Creates a timeline event but does not trigger an incident
    INFO = "info"

    # Triggers a warning (possibly causing incident) in all cases
    WARNING = "warning"

    # Triggers an incident in all cases
    CRITICAL = "critical"

    # Acknowldege entity_id provided in all cases
    ACKNOWLEDGE = "acknowledgement"

    # Recovery entity_id provided in all cases
    RECOVERY = "recovery"

    # Resolve (aliase of Recover)
    RESOLVE = "resolve"


# Define our Splunk Actions
SPLUNK_ACTIONS = (
    SplunkAction.MAP,
    SplunkAction.INFO,
    SplunkAction.ACKNOWLEDGE,
    SplunkAction.WARNING,
    SplunkAction.RECOVERY,
    SplunkAction.RESOLVE,
    SplunkAction.CRITICAL,
)


class SplunkMessageType:
    """Defines the supported splunk message types."""

    # Triggers an incident
    CRITICAL = "CRITICAL"

    # May trigger an incident, depending on your settings
    WARNING = "WARNING"

    # Acks an incident
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"

    # Creates a timeline event but does not trigger an incident
    INFO = "INFO"

    # Resolves an incident
    RECOVERY = "RECOVERY"


# Defines our supported message types
SPLUNK_MESSAGE_TYPES = (
    SplunkMessageType.CRITICAL,
    SplunkMessageType.WARNING,
    SplunkMessageType.ACKNOWLEDGEMENT,
    SplunkMessageType.INFO,
    SplunkMessageType.RECOVERY,
)


class NotifySplunk(NotifyBase):
    """A wrapper for Splunk Notifications."""

    # The default descriptive name associated with the Notification
    service_name = _("Splunk On-Call")

    # The services URL
    service_url = "https://www.splunk.com/en_us/products/on-call.html"

    # The default secure protocol
    secure_protocol = ("splunk", "victorops")

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_splunk"

    # Notification URL
    notify_url = (
        "https://alert.victorops.com/integrations/generic/20131114/"
        "alert/{apikey}/{routing_key}"
    )

    # Define object templates
    templates = (
        "{schema}://{routing_key}@{apikey}",
        "{schema}://{routing_key}@{apikey}/{entity_id}",
    )

    # The title is not used
    title_maxlen = 60

    # body limit
    body_maxlen = 400

    # Defines our default message mapping
    splunk_message_map = {
        # Creates a timeline event but doesnot trigger an incident
        NotifyType.INFO: SplunkMessageType.INFO,
        # Resolves an incident
        NotifyType.SUCCESS: SplunkMessageType.RECOVERY,
        # May trigger an incident, depending on your settings
        NotifyType.WARNING: SplunkMessageType.WARNING,
        # Triggers an incident
        NotifyType.FAILURE: SplunkMessageType.CRITICAL,
    }

    # Define our tokens; these are the minimum tokens required required to
    # be passed into this function (as arguments). The syntax appends any
    # previously defined in the base package and builds onto them
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
                "regex": (r"^[A-Z0-9_-]+$", "i"),
            },
            "routing_key": {
                "name": _("Target Routing Key"),
                "type": "string",
                "required": True,
                "regex": (r"^[A-Z0-9_-]+$", "i"),
            },
            "entity_id": {
                # Provide a value such as: "disk space/db01.mycompany.com"
                "name": _("Entity ID"),
                "type": "string",
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
            "routing_key": {
                "alias_of": "routing_key",
            },
            "route": {
                "alias_of": "routing_key",
            },
            "entity_id": {
                "alias_of": "entity_id",
            },
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": SPLUNK_ACTIONS,
                "default": SPLUNK_ACTIONS[0],
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "mapping": {
            "name": _("Action Mapping"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        apikey,
        routing_key,
        entity_id=None,
        action=None,
        mapping=None,
        **kwargs,
    ):
        """Initialize Splunk Object."""
        super().__init__(**kwargs)

        self.apikey = validate_regex(
            apikey, *self.template_tokens["apikey"]["regex"]
        )
        if not self.apikey:
            msg = f"The Splunk API Key specified ({apikey}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.routing_key = validate_regex(
            routing_key, *self.template_tokens["routing_key"]["regex"]
        )
        if not self.routing_key:
            msg = (
                f"The Splunk Routing Key specified ({routing_key}) is invalid."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        if not (
            isinstance(entity_id, str) and len(entity_id.strip(" \r\n\t\v/"))
        ):
            # Use routing key
            self.entity_id = f"{self.app_id}/{self.routing_key}"

        else:
            # Assign what was defined:
            self.entity_id = entity_id.strip(" \r\n\t\v/")

        if action and isinstance(action, str):
            self.action = next(
                (a for a in SPLUNK_ACTIONS if a.startswith(action)), None
            )
            if self.action not in SPLUNK_ACTIONS:
                msg = f"The Splunk action specified ({action}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.action = self.template_args["action"]["default"]

        # Store our mappings
        self.mapping = self.splunk_message_map.copy()
        if mapping and isinstance(mapping, dict):
            for _k, _v in mapping.items():
                # Get our mapping
                k = next((t for t in NOTIFY_TYPES if t.startswith(_k)), None)
                if not k:
                    msg = (
                        f"The Splunk mapping key specified ({_k}) is invalid."
                    )
                    self.logger.warning(msg)
                    raise TypeError(msg)

                _v_upper = _v.upper()
                v = next(
                    (
                        v
                        for v in SPLUNK_MESSAGE_TYPES
                        if v.startswith(_v_upper)
                    ),
                    None,
                )
                if not v:
                    msg = (
                        f"The Splunk mapping value (assigned to {k}) "
                        f"specified ({_v}) is invalid."
                    )
                    self.logger.warning(msg)
                    raise TypeError(msg)

                # Update our mapping
                self.mapping[k] = v

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Send our notification."""

        # prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Set up our message type
        if self.action == SplunkAction.MAP:
            # Use Mapping
            message_type = self.mapping[notify_type]

        elif self.action == SplunkAction.ACKNOWLEDGE:
            # Always Acknowledge
            message_type = SplunkMessageType.ACKNOWLEDGEMENT

        elif self.action == SplunkAction.INFO:
            # Creates a timeline event but does not trigger an incident
            message_type = SplunkMessageType.INFO

        elif self.action == SplunkAction.CRITICAL:
            # Always create Incident
            message_type = SplunkMessageType.CRITICAL

        elif self.action == SplunkAction.WARNING:
            # Always trigger warning (potentially creating incident)
            message_type = SplunkMessageType.WARNING

        else:  # self.action == SplunkAction.RECOVERY or SplunkAction.RESOLVE
            # Always Recover
            message_type = SplunkMessageType.RECOVERY

        # Prepare our payload
        payload = {
            "entity_id": self.entity_id,
            "message_type": message_type,
            "entity_display_name": title if title else self.app_desc,
            "state_message": body,
            "monitoring_tool": self.app_id,
        }

        notify_url = self.notify_url.format(
            apikey=self.apikey, routing_key=self.routing_key
        )

        self.logger.debug(
            "Splunk GET URL:"
            f" {notify_url} (cert_verify={self.verify_certificate!r})"
        )
        self.logger.debug(f"Splunk Payload: {payload!s}")

        # Always call throttle before any remote server i/o is made
        self.throttle()

        try:
            r = requests.post(
                notify_url,
                data=dumps(payload).encode("utf-8"),
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )
            # Sample Response
            # {
            #   "result" : "success",
            #   "entity_id" : "disk space/db01.mycompany.com"
            # }

            if r.status_code != requests.codes.ok:
                # We had a problem
                status_str = NotifySplunk.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Splunk notification: {}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                # Return; we're done
                return False

            else:
                self.logger.info("Sent Splunk notification.")

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Splunk notification."
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
        return (
            self.secure_protocol[0],
            self.routing_key,
            self.entity_id,
            self.apikey,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "action": self.action,
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Append our assignment extra's into our parameters
        params.update({f":{k.value}": v for k, v in self.mapping.items()})

        return "{schema}://{routing_key}@{apikey}/{entity_id}?{params}".format(
            schema=self.secure_protocol[0],
            routing_key=self.routing_key,
            entity_id=(
                "" if self.entity_id == self.routing_key else self.entity_id
            ),
            apikey=self.pprint(self.apikey, privacy, safe=""),
            params=NotifySplunk.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""

        # parse_url already handles getting the `user` and `password` fields
        # populated.
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Entity ID
        if "entity_id" in results["qsd"] and len(results["qsd"]["entity_id"]):
            results["entity_id"] = NotifySplunk.unquote(
                results["qsd"]["entity_id"]
            )
        else:
            results["entity_id"] = NotifySplunk.unquote(results["fullpath"])

        # API Key
        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            results["apikey"] = NotifySplunk.unquote(results["qsd"]["apikey"])

        else:
            results["apikey"] = NotifySplunk.unquote(results["host"])

        # Routing Key
        if "routing_key" in results["qsd"] and len(
            results["qsd"]["routing_key"]
        ):
            results["routing_key"] = NotifySplunk.unquote(
                results["qsd"]["routing_key"]
            )

        elif "route" in results["qsd"] and len(results["qsd"]["route"]):
            results["routing_key"] = NotifySplunk.unquote(
                results["qsd"]["route"]
            )

        else:
            results["routing_key"] = NotifySplunk.unquote(results["user"])

        # Store our action (if defined)
        if "action" in results["qsd"] and len(results["qsd"]["action"]):
            results["action"] = NotifySplunk.unquote(results["qsd"]["action"])

        # store any custom mapping defined
        results["mapping"] = {
            NotifySplunk.unquote(x): NotifySplunk.unquote(y)
            for x, y in results["qsd:"].items()
        }

        return results

    @staticmethod
    def parse_native_url(url):
        """
        Support https://alert.victorops.com/integrations/generic/20131114/ \
                     alert/apikey/routing_key
        """

        result = re.match(
            r"^https?://alert\.victorops\.com/integrations/generic/"
            r"(?P<version>[0-9]+)/alert/(?P<apikey>[0-9a-z_-]+)"
            r"(/(?P<routing_key>[^?/]+))"
            r"(/(?P<entity_id>[^?]+))?/*"
            r"(?P<params>\?.+)?$",
            url,
            re.I,
        )

        if result:
            return NotifySplunk.parse_url(
                "{schema}://{routing_key}@{apikey}/{entity_id}{params}".format(
                    schema=NotifySplunk.secure_protocol[0],
                    apikey=result.group("apikey"),
                    routing_key=result.group("routing_key"),
                    entity_id=(
                        ""
                        if not result.group("entity_id")
                        else result.group("entity_id")
                    ),
                    params=(
                        ""
                        if not result.group("params")
                        else result.group("params")
                    ),
                )
            )

        return None
