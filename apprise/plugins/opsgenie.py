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

# Signup @ https://www.opsgenie.com
#
# Generate your Integration API Key
#   https://app.opsgenie.com/settings/integration/add/API/

# Knowing this, you can build your Opsgenie URL as follows:
#  opsgenie://{apikey}/
#  opsgenie://{apikey}/@{user}
#  opsgenie://{apikey}/*{schedule}
#  opsgenie://{apikey}/^{escalation}
#  opsgenie://{apikey}/#{team}
#
# You can mix and match what you want to notify freely
#  opsgenie://{apikey}/@{user}/#{team}/*{schedule}/^{escalation}
#
# If no target prefix is specified, then it is assumed to be a user.
#
# API Documentation: https://docs.opsgenie.com/docs/alert-api
# API Integration Docs: https://docs.opsgenie.com/docs/api-integration

import hashlib
from json import dumps, loads

import requests

from ..common import NOTIFY_TYPES, NotifyType, PersistentStoreMode
from ..locale import gettext_lazy as _
from ..utils.parse import is_uuid, parse_bool, parse_list, validate_regex
from .base import NotifyBase


class OpsgenieCategory(NotifyBase):
    """We define the different category types that we can notify."""

    USER = "user"
    SCHEDULE = "schedule"
    ESCALATION = "escalation"
    TEAM = "team"


OPSGENIE_CATEGORIES = (
    OpsgenieCategory.USER,
    OpsgenieCategory.SCHEDULE,
    OpsgenieCategory.ESCALATION,
    OpsgenieCategory.TEAM,
)


class OpsgenieAlertAction:
    """Defines the supported actions."""

    # Use mapping (specify :key=arg to over-ride)
    MAP = "map"

    # Create new alert (default)
    NEW = "new"

    # Close Alert
    CLOSE = "close"

    # Delete Alert
    DELETE = "delete"

    # Acknowledge Alert
    ACKNOWLEDGE = "acknowledge"

    # Add note to alert
    NOTE = "note"


OPSGENIE_ACTIONS = (
    OpsgenieAlertAction.MAP,
    OpsgenieAlertAction.NEW,
    OpsgenieAlertAction.CLOSE,
    OpsgenieAlertAction.DELETE,
    OpsgenieAlertAction.ACKNOWLEDGE,
    OpsgenieAlertAction.NOTE,
)

# Map all support Apprise Categories to Opsgenie Categories
OPSGENIE_ALERT_MAP = {
    NotifyType.INFO: OpsgenieAlertAction.CLOSE,
    NotifyType.SUCCESS: OpsgenieAlertAction.CLOSE,
    NotifyType.WARNING: OpsgenieAlertAction.NEW,
    NotifyType.FAILURE: OpsgenieAlertAction.NEW,
}


# Regions
class OpsgenieRegion:
    US = "us"
    EU = "eu"


# Opsgenie APIs
OPSGENIE_API_LOOKUP = {
    OpsgenieRegion.US: "https://api.opsgenie.com/v2/alerts",
    OpsgenieRegion.EU: "https://api.eu.opsgenie.com/v2/alerts",
}

# A List of our regions we can use for verification
OPSGENIE_REGIONS = (
    OpsgenieRegion.US,
    OpsgenieRegion.EU,
)


# Priorities
class OpsgeniePriority:
    LOW = 1
    MODERATE = 2
    NORMAL = 3
    HIGH = 4
    EMERGENCY = 5


OPSGENIE_PRIORITIES = {
    # Note: This also acts as a reverse lookup mapping
    OpsgeniePriority.LOW: "low",
    OpsgeniePriority.MODERATE: "moderate",
    OpsgeniePriority.NORMAL: "normal",
    OpsgeniePriority.HIGH: "high",
    OpsgeniePriority.EMERGENCY: "emergency",
}

OPSGENIE_PRIORITY_MAP = {
    # Maps against string 'low'
    "l": OpsgeniePriority.LOW,
    # Maps against string 'moderate'
    "m": OpsgeniePriority.MODERATE,
    # Maps against string 'normal'
    "n": OpsgeniePriority.NORMAL,
    # Maps against string 'high'
    "h": OpsgeniePriority.HIGH,
    # Maps against string 'emergency'
    "e": OpsgeniePriority.EMERGENCY,
    # Entries to additionally support (so more like Opsgenie's API)
    "1": OpsgeniePriority.LOW,
    "2": OpsgeniePriority.MODERATE,
    "3": OpsgeniePriority.NORMAL,
    "4": OpsgeniePriority.HIGH,
    "5": OpsgeniePriority.EMERGENCY,
    # Support p-prefix
    "p1": OpsgeniePriority.LOW,
    "p2": OpsgeniePriority.MODERATE,
    "p3": OpsgeniePriority.NORMAL,
    "p4": OpsgeniePriority.HIGH,
    "p5": OpsgeniePriority.EMERGENCY,
}


class NotifyOpsgenie(NotifyBase):
    """A wrapper for Opsgenie Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Opsgenie"

    # The services URL
    service_url = "https://opsgenie.com/"

    # All notification requests are secure
    secure_protocol = "opsgenie"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_opsgenie"

    # The maximum length of the body
    body_maxlen = 15000

    # Our default is to no not use persistent storage beyond in-memory
    # reference
    storage_mode = PersistentStoreMode.AUTO

    # If we don't have the specified min length, then we don't bother using
    # the body directive
    opsgenie_body_minlen = 130

    # The default region to use if one isn't otherwise specified
    opsgenie_default_region = OpsgenieRegion.US

    # The maximum allowable targets within a notification
    default_batch_size = 50

    # Defines our default message mapping
    opsgenie_message_map = {
        # Add a note to existing alert
        NotifyType.INFO: OpsgenieAlertAction.NOTE,
        # Close existing alert
        NotifyType.SUCCESS: OpsgenieAlertAction.CLOSE,
        # Create notice
        NotifyType.WARNING: OpsgenieAlertAction.NEW,
        # Create notice
        NotifyType.FAILURE: OpsgenieAlertAction.NEW,
    }

    # Define object templates
    templates = (
        "{schema}://{apikey}",
        "{schema}://{user}@{apikey}",
        "{schema}://{apikey}/{targets}",
        "{schema}://{user}@{apikey}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "user": {
                "name": _("Username"),
                "type": "string",
            },
            "target_escalation": {
                "name": _("Target Escalation"),
                "prefix": "^",
                "type": "string",
                "map_to": "targets",
            },
            "target_schedule": {
                "name": _("Target Schedule"),
                "type": "string",
                "prefix": "*",
                "map_to": "targets",
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "target_team": {
                "name": _("Target Team"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets "),
                "type": "list:string",
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "region": {
                "name": _("Region Name"),
                "type": "choice:string",
                "values": OPSGENIE_REGIONS,
                "default": OpsgenieRegion.US,
                "map_to": "region_name",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:int",
                "values": OPSGENIE_PRIORITIES,
                "default": OpsgeniePriority.NORMAL,
            },
            "entity": {
                "name": _("Entity"),
                "type": "string",
            },
            "alias": {
                "name": _("Alias"),
                "type": "string",
            },
            "tags": {
                "name": _("Tags"),
                "type": "string",
            },
            "to": {
                "alias_of": "targets",
            },
            "action": {
                "name": _("Action"),
                "type": "choice:string",
                "values": OPSGENIE_ACTIONS,
                "default": OPSGENIE_ACTIONS[0],
            },
        },
    )

    # Map of key-value pairs to use as custom properties of the alert.
    template_kwargs = {
        "details": {
            "name": _("Details"),
            "prefix": "+",
        },
        "mapping": {
            "name": _("Action Mapping"),
            "prefix": ":",
        },
    }

    def __init__(
        self,
        apikey,
        targets,
        region_name=None,
        details=None,
        priority=None,
        alias=None,
        entity=None,
        batch=False,
        tags=None,
        action=None,
        mapping=None,
        **kwargs,
    ):
        """Initialize Opsgenie Object."""
        super().__init__(**kwargs)

        # API Key (associated with project)
        self.apikey = validate_regex(apikey)
        if not self.apikey:
            msg = f"An invalid Opsgenie API Key ({apikey}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # The Priority of the message
        self.priority = (
            NotifyOpsgenie.template_args["priority"]["default"]
            if not priority
            else next(
                (
                    v
                    for k, v in OPSGENIE_PRIORITY_MAP.items()
                    if str(priority).lower().startswith(k)
                ),
                NotifyOpsgenie.template_args["priority"]["default"],
            )
        )

        # Store our region
        try:
            self.region_name = (
                self.opsgenie_default_region
                if region_name is None
                else region_name.lower()
            )

            if self.region_name not in OPSGENIE_REGIONS:
                # allow the outer except to handle this common response
                raise
        except:
            # Invalid region specified
            msg = f"The Opsgenie region specified ({region_name}) is invalid."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        if action and isinstance(action, str):
            self.action = next(
                (a for a in OPSGENIE_ACTIONS if a.startswith(action)), None
            )
            if self.action not in OPSGENIE_ACTIONS:
                msg = f"The Opsgenie action specified ({action}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)
        else:
            self.action = self.template_args["action"]["default"]

        # Store our mappings
        self.mapping = self.opsgenie_message_map.copy()
        if mapping and isinstance(mapping, dict):
            for _k, _v in mapping.items():
                # Get our mapping
                k = next((t for t in NOTIFY_TYPES if t.startswith(_k)), None)
                if not k:
                    msg = (
                        f"The Opsgenie mapping key specified ({_k}) "
                        "is invalid."
                    )
                    self.logger.warning(msg)
                    raise TypeError(msg)

                _v_lower = _v.lower()
                v = next(
                    (
                        v
                        for v in OPSGENIE_ACTIONS[1:]
                        if v.startswith(_v_lower)
                    ),
                    None,
                )
                if not v:
                    msg = (
                        f"The Opsgenie mapping value (assigned to {k}) "
                        f"specified ({_v}) is invalid."
                    )
                    self.logger.warning(msg)
                    raise TypeError(msg)

                # Update our mapping
                self.mapping[k] = v

        self.details = {}
        if details:
            # Store our extra details
            self.details.update(details)

        # Prepare Batch Mode Flag
        self.batch_size = self.default_batch_size if batch else 1

        # Assign our tags (if defined)
        self.__tags = parse_list(tags)

        # Assign our entity (if defined)
        self.entity = entity

        # Assign our alias (if defined)
        self.alias = alias

        # Initialize our Targets
        self.targets = []

        # Sort our targets
        for _target in parse_list(targets):
            target = _target.strip()
            if len(target) < 2:
                self.logger.debug(f"Ignoring Opsgenie Entry: {target}")
                continue

            if target.startswith(
                NotifyOpsgenie.template_tokens["target_team"]["prefix"]
            ):

                self.targets.append(
                    {"type": OpsgenieCategory.TEAM, "id": target[1:]}
                    if is_uuid(target[1:])
                    else {"type": OpsgenieCategory.TEAM, "name": target[1:]}
                )

            elif target.startswith(
                NotifyOpsgenie.template_tokens["target_schedule"]["prefix"]
            ):

                self.targets.append(
                    {"type": OpsgenieCategory.SCHEDULE, "id": target[1:]}
                    if is_uuid(target[1:])
                    else {
                        "type": OpsgenieCategory.SCHEDULE,
                        "name": target[1:],
                    }
                )

            elif target.startswith(
                NotifyOpsgenie.template_tokens["target_escalation"]["prefix"]
            ):

                self.targets.append(
                    {"type": OpsgenieCategory.ESCALATION, "id": target[1:]}
                    if is_uuid(target[1:])
                    else {
                        "type": OpsgenieCategory.ESCALATION,
                        "name": target[1:],
                    }
                )

            elif target.startswith(
                NotifyOpsgenie.template_tokens["target_user"]["prefix"]
            ):

                self.targets.append(
                    {"type": OpsgenieCategory.USER, "id": target[1:]}
                    if is_uuid(target[1:])
                    else {
                        "type": OpsgenieCategory.USER,
                        "username": target[1:],
                    }
                )

            else:
                # Ambiguious entry; treat it as a user but not before
                # displaying a warning to the end user first:
                self.logger.debug(
                    "Treating ambigious Opsgenie target %s as a user", target
                )
                self.targets.append(
                    {"type": OpsgenieCategory.USER, "id": target}
                    if is_uuid(target)
                    else {"type": OpsgenieCategory.USER, "username": target}
                )

    def _fetch(self, method, url, payload, params=None):
        """Performs server retrieval/update and returns JSON Response."""
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
            "Authorization": f"GenieKey {self.apikey}",
        }

        # Some Debug Logging
        self.logger.debug(
            f"Opsgenie POST URL: {url} (cert_verify={self.verify_certificate})"
        )
        self.logger.debug(f"Opsgenie Payload: {payload}")

        # Initialize our response object
        content = {}

        # Always call throttle before any remote server i/o is made
        self.throttle()
        try:
            r = method(
                url,
                data=dumps(payload),
                params=params,
                headers=headers,
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            # A Response might look like:
            # {
            #     "result": "Request will be processed",
            #     "took": 0.302,
            #     "requestId": "43a29c5c-3dbf-4fa4-9c26-f4f71023e120"
            # }

            try:
                # Update our response object
                content = loads(r.content)

            except (AttributeError, TypeError, ValueError):
                # ValueError = r.content is Unparsable
                # TypeError = r.content is None
                # AttributeError = r is None
                content = {}

            if r.status_code not in (
                requests.codes.accepted,
                requests.codes.ok,
            ):
                status_str = NotifyBase.http_response_code_lookup(
                    r.status_code
                )

                self.logger.warning(
                    "Failed to send Opsgenie notification:"
                    "{}{}error={}.".format(
                        status_str, ", " if status_str else "", r.status_code
                    )
                )

                self.logger.debug(f"Response Details:\r\n{r.content}")

                return (False, content.get("requestId"))

            # If we reach here; the message was sent
            self.logger.info("Sent Opsgenie notification")
            self.logger.debug(f"Response Details:\r\n{r.content}")

            return (True, content.get("requestId"))

        except requests.RequestException as e:
            self.logger.warning(
                "A Connection error occurred sending Opsgenie notification."
            )
            self.logger.debug(f"Socket Exception: {e!s}")

        return (False, content.get("requestId"))

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Opsgenie Notification."""

        # Get our Opsgenie Action
        action = (
            OPSGENIE_ALERT_MAP[notify_type]
            if self.action == OpsgenieAlertAction.MAP
            else self.action
        )

        # Prepare our URL as it's based on our hostname
        notify_url = OPSGENIE_API_LOOKUP[self.region_name]

        # Initialize our has_error flag
        has_error = False

        # Default method is to post
        method = requests.post

        # For indexing in persistent store
        key = hashlib.sha1(
            (
                self.entity
                if self.entity
                else (
                    self.alias
                    if self.alias
                    else (title if title else self.app_id)
                )
            ).encode("utf-8")
        ).hexdigest()[0:10]

        # Get our Opsgenie Request IDs
        request_ids = self.store.get(key, [])
        if not isinstance(request_ids, list):
            request_ids = []

        if action == OpsgenieAlertAction.NEW:
            # Create a copy ouf our details object
            details = self.details.copy()
            if "type" not in details:
                details["type"] = notify_type.value

            # Use body if title not set
            title_body = title if title else body

            # Prepare our payload
            payload = {
                "source": self.app_desc,
                "message": title_body,
                "description": body,
                "details": details,
                "priority": f"P{self.priority}",
            }

            # Use our body directive if we exceed the minimum message
            # limitation
            if len(payload["message"]) > self.opsgenie_body_minlen:
                payload["message"] = (
                    f"{title_body[:self.opsgenie_body_minlen - 3]}..."
                )

            if self.__tags:
                payload["tags"] = self.__tags

            if self.entity:
                payload["entity"] = self.entity

            if self.alias:
                payload["alias"] = self.alias

            if self.user:
                payload["user"] = self.user

            # reset our request IDs - we will re-populate them
            request_ids = []

            length = len(self.targets) if self.targets else 1
            for index in range(0, length, self.batch_size):
                if self.targets:
                    # If there were no targets identified, then we simply
                    # just iterate once without the responders set
                    payload["responders"] = self.targets[
                        index : index + self.batch_size
                    ]

                # Perform our post
                success, request_id = self._fetch(method, notify_url, payload)

                if success and request_id:
                    # Save our response
                    request_ids.append(request_id)

                else:
                    has_error = True

            # Store our entries for a maximum of 60 days
            self.store.set(key, request_ids, expires=60 * 60 * 24 * 60)

        elif request_ids:
            # Prepare our payload
            payload = {
                "source": self.app_desc,
                "note": body,
            }

            if self.user:
                payload["user"] = self.user

            # Prepare our Identifier type
            params = {
                "identifierType": "id",
            }

            for request_id in request_ids:
                if action == OpsgenieAlertAction.DELETE:
                    # Update our URL
                    url = f"{notify_url}/{request_id}"
                    method = requests.delete

                elif action == OpsgenieAlertAction.ACKNOWLEDGE:
                    url = f"{notify_url}/{request_id}/acknowledge"

                elif action == OpsgenieAlertAction.CLOSE:
                    url = f"{notify_url}/{request_id}/close"

                else:  # action == OpsgenieAlertAction.CLOSE:
                    url = f"{notify_url}/{request_id}/notes"

                # Perform our post
                success, _ = self._fetch(method, url, payload, params)

                if not success:
                    has_error = True

            if not has_error and action == OpsgenieAlertAction.DELETE:
                # Remove cached entry
                self.store.clear(key)

        else:
            self.logger.info(
                "No Opsgenie notification sent due to (nothing to %s) "
                "condition",
                self.action,
            )

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (self.secure_protocol, self.region_name, self.apikey)

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "action": self.action,
            "region": self.region_name,
            "priority": (
                OPSGENIE_PRIORITIES[self.template_args["priority"]["default"]]
                if self.priority not in OPSGENIE_PRIORITIES
                else OPSGENIE_PRIORITIES[self.priority]
            ),
            "batch": "yes" if self.batch_size > 1 else "no",
        }

        # Assign our entity value (if defined)
        if self.entity:
            params["entity"] = self.entity

        # Assign our alias value (if defined)
        if self.alias:
            params["alias"] = self.alias

        # Assign our tags (if specifed)
        if self.__tags:
            params["tags"] = ",".join(self.__tags)

        # Append our details into our parameters
        params.update({f"+{k}": v for k, v in self.details.items()})

        # Append our assignment extra's into our parameters
        params.update({f":{k.value}": v for k, v in self.mapping.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # A map allows us to map our target types so they can be correctly
        # placed back into your URL below. Hence map the 'user' -> '@'
        __map = {
            OpsgenieCategory.USER: NotifyOpsgenie.template_tokens[
                "target_user"
            ]["prefix"],
            OpsgenieCategory.SCHEDULE: NotifyOpsgenie.template_tokens[
                "target_schedule"
            ]["prefix"],
            OpsgenieCategory.ESCALATION: NotifyOpsgenie.template_tokens[
                "target_escalation"
            ]["prefix"],
            OpsgenieCategory.TEAM: NotifyOpsgenie.template_tokens[
                "target_team"
            ]["prefix"],
        }

        return "{schema}://{user}{apikey}/{targets}?{params}".format(
            schema=self.secure_protocol,
            user=f"{self.user}@" if self.user else "",
            apikey=self.pprint(self.apikey, privacy, safe=""),
            targets="/".join([
                NotifyOpsgenie.quote(
                    "{}{}".format(
                        __map[x["type"]],
                        x.get("id", x.get("name", x.get("username"))),
                    )
                )
                for x in self.targets
            ]),
            params=NotifyOpsgenie.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        #
        # Factor batch into calculation
        #
        targets = len(self.targets)
        if self.batch_size > 1:
            targets = int(targets / self.batch_size) + (
                1 if targets % self.batch_size else 0
            )

        return targets if targets > 0 else 1

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # The API Key is stored in the hostname
        results["apikey"] = NotifyOpsgenie.unquote(results["host"])

        # Get our Targets
        results["targets"] = NotifyOpsgenie.split_path(results["fullpath"])

        # Add our Meta Detail keys
        results["details"] = {
            NotifyBase.unquote(x): NotifyBase.unquote(y)
            for x, y in results["qsd+"].items()
        }

        # Set our priority
        if "priority" in results["qsd"] and len(results["qsd"]["priority"]):
            results["priority"] = NotifyOpsgenie.unquote(
                results["qsd"]["priority"]
            )

        # Get Batch Boolean (if set)
        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch", NotifyOpsgenie.template_args["batch"]["default"]
            )
        )

        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            results["apikey"] = NotifyOpsgenie.unquote(
                results["qsd"]["apikey"]
            )

        if "tags" in results["qsd"] and len(results["qsd"]["tags"]):
            # Extract our tags
            results["tags"] = parse_list(
                NotifyOpsgenie.unquote(results["qsd"]["tags"])
            )

        if "region" in results["qsd"] and len(results["qsd"]["region"]):
            # Extract our region
            results["region_name"] = NotifyOpsgenie.unquote(
                results["qsd"]["region"]
            )

        if "entity" in results["qsd"] and len(results["qsd"]["entity"]):
            # Extract optional entity field
            results["entity"] = NotifyOpsgenie.unquote(
                results["qsd"]["entity"]
            )

        if "alias" in results["qsd"] and len(results["qsd"]["alias"]):
            # Extract optional alias field
            results["alias"] = NotifyOpsgenie.unquote(results["qsd"]["alias"])

        # Handle 'to' email address
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"].append(results["qsd"]["to"])

        # Store our action (if defined)
        if "action" in results["qsd"] and len(results["qsd"]["action"]):
            results["action"] = NotifyOpsgenie.unquote(
                results["qsd"]["action"]
            )

        # store any custom mapping defined
        results["mapping"] = {
            NotifyOpsgenie.unquote(x): NotifyOpsgenie.unquote(y)
            for x, y in results["qsd:"].items()
        }

        return results
