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

from itertools import chain
from json import dumps, loads
import re

import requests

from .. import exception
from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import (
    is_phone_no,
    parse_bool,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase

GROUP_REGEX = re.compile(r"^\s*(\#|\%35)(?P<group>[a-z0-9_-]+)", re.I)

CONTACT_REGEX = re.compile(r"^\s*(\@|\%40)?(?P<contact>[a-z0-9_-]+)", re.I)


# Priorities
class SMSEaglePriority:
    NORMAL = 0
    HIGH = 1


SMSEAGLE_PRIORITIES = (
    SMSEaglePriority.NORMAL,
    SMSEaglePriority.HIGH,
)

SMSEAGLE_PRIORITY_MAP = {
    # short for 'normal'
    "normal": SMSEaglePriority.NORMAL,
    # short for 'high'
    "+": SMSEaglePriority.HIGH,
    "high": SMSEaglePriority.HIGH,
}


class SMSEagleCategory:
    """We define the different category types that we can notify via SMS
    Eagle."""

    PHONE = "phone"
    GROUP = "group"
    CONTACT = "contact"


SMSEAGLE_CATEGORIES = (
    SMSEagleCategory.PHONE,
    SMSEagleCategory.GROUP,
    SMSEagleCategory.CONTACT,
)


class NotifySMSEagle(NotifyBase):
    """A wrapper for SMSEagle Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "SMS Eagle"

    # The services URL
    service_url = "https://smseagle.eu"

    # The default protocol
    protocol = "smseagle"

    # The default protocol
    secure_protocol = "smseagles"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_smseagle"

    # The path we send our notification to
    notify_path = "/jsonrpc/sms"

    # Support attachments
    attachment_support = True

    # The maxumum length of the text message
    # The actual limit is 160 but SMSEagle looks after the handling
    # of large messages in it's upstream service
    body_maxlen = 1200

    # The maximum targets to include when doing batch transfers
    default_batch_size = 10

    # We don't support titles for SMSEagle notifications
    title_maxlen = 0

    # Define object templates
    templates = (
        "{schema}://{token}@{host}/{targets}",
        "{schema}://{token}@{host}:{port}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "host": {
                "name": _("Hostname"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "token": {
                "name": _("Access Token"),
                "type": "string",
                "required": True,
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "map_to": "targets",
            },
            "target_group": {
                "name": _("Target Group ID"),
                "type": "string",
                "prefix": "#",
                "regex": (r"^[a-z0-9_-]+$", "i"),
                "map_to": "targets",
            },
            "target_contact": {
                "name": _("Target Contact"),
                "type": "string",
                "prefix": "@",
                "regex": (r"^[a-z0-9_-]+$", "i"),
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
            "token": {
                "alias_of": "token",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
            "status": {
                "name": _("Show Status"),
                "type": "bool",
                "default": False,
            },
            "test": {
                "name": _("Test Only"),
                "type": "bool",
                "default": False,
            },
            "flash": {
                "name": _("Flash"),
                "type": "bool",
                "default": False,
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:int",
                "values": SMSEAGLE_PRIORITIES,
                "default": SMSEaglePriority.NORMAL,
            },
        },
    )

    def __init__(
        self,
        token=None,
        targets=None,
        priority=None,
        batch=False,
        status=False,
        flash=False,
        test=False,
        **kwargs,
    ):
        """Initialize SMSEagle Object."""
        super().__init__(**kwargs)

        # Prepare Flash Mode Flag
        self.flash = flash

        # Prepare Test Mode Flag
        self.test = test

        # Prepare Batch Mode Flag
        self.batch = batch

        # Set Status type
        self.status = status

        # Parse our targets
        self.target_phones = []
        self.target_groups = []
        self.target_contacts = []

        # Used for URL generation afterwards only
        self.invalid_targets = []

        # We always use a token if provided
        self.token = validate_regex(token if token else self.user)
        if not self.token:
            msg = (
                "An invalid SMSEagle Access Token"
                f" ({token if token else self.user}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        #
        # Priority
        #
        try:
            # Acquire our priority if we can:
            #  - We accept both the integer form as well as a string
            #    representation
            self.priority = int(priority)

        except TypeError:
            # NoneType means use Default; this is an okay exception
            self.priority = self.template_args["priority"]["default"]

        except ValueError:
            # Input is a string; attempt to get the lookup from our
            # priority mapping
            priority = priority.lower().strip()

            # This little bit of black magic allows us to match against
            # low, lo, l (for low);
            # normal, norma, norm, nor, no, n (for normal)
            # ... etc
            result = (
                next(
                    (
                        key
                        for key in SMSEAGLE_PRIORITY_MAP
                        if key.startswith(priority)
                    ),
                    None,
                )
                if priority
                else None
            )

            # Now test to see if we got a match
            if not result:
                msg = (
                    f"An invalid SMSEagle priority ({priority}) was specified."
                )
                self.logger.warning(msg)
                raise TypeError(msg) from None

            # store our successfully looked up priority
            self.priority = SMSEAGLE_PRIORITY_MAP[result]

        if (
            self.priority is not None
            and self.priority not in SMSEAGLE_PRIORITY_MAP.values()
        ):
            msg = f"An invalid SMSEagle priority ({priority}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate our targerts
        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            # Allow 9 digit numbers (without country code)
            result = is_phone_no(target, min_len=9)
            if result:
                # store valid phone number
                self.target_phones.append(
                    "{}{}".format(
                        "" if target[0] != "+" else "+", result["full"]
                    )
                )
                continue

            result = GROUP_REGEX.match(target)
            if result:
                # Just store group information
                self.target_groups.append(result.group("group"))
                continue

            result = CONTACT_REGEX.match(target)
            if result:
                # Just store contact information
                self.target_contacts.append(result.group("contact"))
                continue

            self.logger.warning(
                f"Dropped invalid phone/group/contact ({target}) specified.",
            )
            self.invalid_targets.append(target)
            continue

        return

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform SMSEagle Notification."""

        if (
            not self.target_groups
            and not self.target_phones
            and not self.target_contacts
        ):
            # There were no services to notify
            self.logger.warning("There were no SMSEagle targets to notify.")
            return False

        # error tracking (used for function return)
        has_error = False

        attachments = []
        if attach and self.attachment_support:
            for attachment in attach:
                # Perform some simple error checking
                if not attachment:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access SMSEagle attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                if not re.match(r"^image/.*", attachment.mimetype, re.I):
                    # Only support images at this time
                    self.logger.warning(
                        "Ignoring unsupported SMSEagle attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    continue

                try:
                    # Prepare our Attachment in Base64
                    attachments.append({
                        "content_type": attachment.mimetype,
                        "content": attachment.base64(),
                    })

                except exception.AppriseException:
                    # We could not access the attachment
                    self.logger.error(
                        "Could not access SMSEagle attachment"
                        f" {attachment.url(privacy=True)}."
                    )
                    return False

                self.logger.debug(
                    "Appending SMSEagle attachment"
                    f" {attachment.url(privacy=True)}"
                )

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/json",
        }

        # Prepare our payload
        params_template = {
            # Our Access Token
            "access_token": self.token,
            # The message to send (populated below)
            "message": None,
            # 0 = normal priority, 1 = high priority
            "highpriority": self.priority,
            # Support unicode characters
            "unicode": 1,
            # sms or mms (if attachment)
            "message_type": "sms",
            # Response Types:
            #  simple: format response as simple object with one result field
            #  extended: format response as extended JSON object
            "responsetype": "extended",
            # SMS will be sent as flash message (1 = yes, 0 = no)
            "flash": 1 if self.flash else 0,
            # Message Simulation
            "test": 1 if self.test else 0,
        }

        # Set our schema
        schema = "https" if self.secure else "http"

        # Construct our URL
        notify_url = f"{schema}://{self.host}"
        if isinstance(self.port, int):
            notify_url += f":{self.port}"
        notify_url += self.notify_path

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        notify_by = {
            SMSEagleCategory.PHONE: {
                "method": "sms.send_sms",
                "target": "to",
            },
            SMSEagleCategory.GROUP: {
                "method": "sms.send_togroup",
                "target": "groupname",
            },
            SMSEagleCategory.CONTACT: {
                "method": "sms.send_tocontact",
                "target": "contactname",
            },
        }

        # categories separated into a tuple since notify_by.keys()
        # returns an unpredicable list in Python 2.7 which causes
        # tests to fail every so often
        for category in SMSEAGLE_CATEGORIES:
            # Create a copy of our template
            payload = {
                "method": notify_by[category]["method"],
                "params": {
                    notify_by[category]["target"]: None,
                },
            }

            # Apply Template
            payload["params"].update(params_template)

            # Set our Message
            payload["params"]["message"] = "{}{}".format(
                "" if not self.status else f"{self.asset.ascii(notify_type)} ",
                body,
            )

            if attachments:
                # Store our attachments
                payload["params"]["message_type"] = "mms"
                payload["params"]["attachments"] = attachments

            targets = getattr(self, f"target_{category}s")
            for index in range(0, len(targets), batch_size):
                # Prepare our recipients
                payload["params"][notify_by[category]["target"]] = ",".join(
                    targets[index : index + batch_size]
                )

                self.logger.debug(
                    "SMSEagle POST URL:"
                    f" {notify_url} (cert_verify={self.verify_certificate!r})"
                )
                self.logger.debug(f"SMSEagle Payload: {payload!s}")

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

                    try:
                        content = loads(r.content)

                        # Store our status
                        status_str = str(content["result"])

                    except (AttributeError, TypeError, ValueError, KeyError):
                        # ValueError = r.content is Unparsable
                        # TypeError = r.content is None
                        # AttributeError = r is None
                        # KeyError = 'result' is not found in result
                        content = {}

                    # The result set can be a list such as:
                    #   b'{"result":[{"message_id":4753,"status":"ok"}]}'
                    #
                    # It can also just be as a dictionary:
                    #   b'{"result":{"message_id":4753,"status":"ok"}}'
                    #
                    # The below code handles both cases only only fails if a
                    # non-ok value was returned

                    if (
                        r.status_code
                        not in (requests.codes.ok, requests.codes.created)
                        or not isinstance(content.get("result"), (dict, list))
                        or (
                            isinstance(content.get("result"), dict)
                            and content["result"].get("status") != "ok"
                        )
                        or (
                            isinstance(content.get("result"), list)
                            and next(
                                (
                                    True
                                    for entry in content.get("result")
                                    if isinstance(entry, dict)
                                    and entry.get("status") != "ok"
                                ),
                                False,
                            )  # pragma: no cover
                        )
                    ):

                        # We had a problem
                        status_str = (
                            content.get("result")
                            if content.get("result")
                            else NotifySMSEagle.http_response_code_lookup(
                                r.status_code
                            )
                        )

                        self.logger.warning(
                            "Failed to send {} {} SMSEagle {} notification: "
                            "{}{}error={}.".format(
                                len(targets[index : index + batch_size]),
                                (
                                    f"to {targets[index]}"
                                    if batch_size == 1
                                    else "(s)"
                                ),
                                category,
                                status_str,
                                ", " if status_str else "",
                                r.status_code,
                            )
                        )

                        self.logger.debug(
                            "Response"
                            f" {category.upper()} Details:\r\n{r.content}"
                        )

                        # Mark our failure
                        has_error = True
                        continue

                    else:
                        self.logger.info(
                            "Sent {} SMSEagle {} notification{}.".format(
                                len(targets[index : index + batch_size]),
                                category,
                                (
                                    f" to {targets[index]}"
                                    if batch_size == 1
                                    else "(s)"
                                ),
                            )
                        )

                except requests.RequestException as e:
                    self.logger.warning(
                        "A Connection error occured sending"
                        f" {len(targets[index:index + batch_size])} SMSEagle"
                        f" {category} notification(s)."
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
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.token,
            self.host,
            self.port,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "batch": "yes" if self.batch else "no",
            "status": "yes" if self.status else "no",
            "flash": "yes" if self.flash else "no",
            "test": "yes" if self.test else "no",
        }

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        default_priority = self.template_args["priority"]["default"]
        if self.priority is not None:
            # Store our priority; but only if it was specified
            params["priority"] = next(
                (
                    key
                    for key, value in SMSEAGLE_PRIORITY_MAP.items()
                    if value == self.priority
                ),
                default_priority,
            )  # pragma: no cover

        # Default port handling
        default_port = 443 if self.secure else 80
        return "{schema}://{token}@{hostname}{port}/{targets}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            token=self.pprint(
                self.token, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            ),
            targets="/".join([
                NotifySMSEagle.quote(x, safe="#@")
                for x in chain(
                    # Pass phones directly as is
                    self.target_phones,
                    # Contacts
                    [f"@{x}" for x in self.target_contacts],
                    # Groups
                    [f"#{x}" for x in self.target_groups],
                    # Pass along the same invalid entries as were provided
                    self.invalid_targets,
                )
            ]),
            params=NotifySMSEagle.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        #
        # Factor batch into calculation
        #
        batch_size = 1 if not self.batch else self.default_batch_size
        if batch_size > 1:
            # Batches can only be sent by group (you can't combine groups into
            # a single batch)
            total_targets = 0
            for c in SMSEAGLE_CATEGORIES:
                targets = len(getattr(self, f"target_{c}s"))
                total_targets += int(targets / batch_size) + (
                    1 if targets % batch_size else 0
                )
            return total_targets

        # Normal batch count; just count the targets
        return (
            len(self.target_phones)
            + len(self.target_contacts)
            + len(self.target_groups)
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
        results["targets"] = NotifySMSEagle.split_path(results["fullpath"])

        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            results["token"] = NotifySMSEagle.unquote(results["qsd"]["token"])

        elif not results["password"] and results["user"]:
            results["token"] = NotifySMSEagle.unquote(results["user"])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifySMSEagle.parse_phone_no(
                results["qsd"]["to"]
            )

        # Get Batch Mode Flag
        results["batch"] = parse_bool(results["qsd"].get("batch", False))

        # Get Flash Mode Flag
        results["flash"] = parse_bool(results["qsd"].get("flash", False))

        # Get Test Mode Flag
        results["test"] = parse_bool(results["qsd"].get("test", False))

        # Get status switch
        results["status"] = parse_bool(results["qsd"].get("status", False))

        # Get priority
        if "priority" in results["qsd"] and len(results["qsd"]["priority"]):
            results["priority"] = NotifySMSEagle.unquote(
                results["qsd"]["priority"]
            )

        return results
