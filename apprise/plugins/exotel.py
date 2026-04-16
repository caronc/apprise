# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2026, Chris Caron <lead2gold@gmail.com>
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
import re

import requests

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


class ExotelPriority:
    """
    Priorities
    """

    NORMAL = "normal"
    HIGH = "high"


EXOTEL_PRIORITIES = (
    ExotelPriority.NORMAL,
    ExotelPriority.HIGH,
)

EXOTEL_PRIORITY_MAP = {
    # short for 'normal'
    "normal": ExotelPriority.NORMAL,
    # short for 'high'
    "+": ExotelPriority.HIGH,
    "high": ExotelPriority.HIGH,
}


class ExotelEncoding:
    """
    The different encodings supported
    """

    TEXT = "plain"
    UNICODE = "unicode"


class ExotelRegion:
    """
    Regions
    """

    US = "us"

    # India
    IN = "in"


# Exotel APIs
EXOTEL_API_LOOKUP = {
    ExotelRegion.US: "https://api.exotel.com/v1/Accounts/{sid}/Sms/send",
    ExotelRegion.IN: "https://api.in.exotel.com/v1/Accounts/{sid}/Sms/send",
}

# A List of our regions we can use for verification
EXOTEL_REGIONS = (
    ExotelRegion.US,
    ExotelRegion.IN,
)

EXOTEL_SOURCE_RE = re.compile(r"^[A-Z0-9][A-Z0-9.-]{2,15}$", re.I)


def parse_exotel_source(source):
    """Parse an Exotel source as an ExoPhone or approved Sender ID."""
    source = validate_regex(source)
    if not source:
        return None

    result = is_phone_no(source, min_len=9)
    if result:
        return result["full"]

    if EXOTEL_SOURCE_RE.match(source) and (
        not source.isdigit() or len(source) == 6
    ):
        return source

    return None


class NotifyExotel(NotifyBase):
    """
    A wrapper for Exotel Notifications
    """

    # Exotel supports static bulk SMS by accepting an array of To values on
    # the same /Sms/send endpoint.
    default_batch_size = 100

    # The default descriptive name associated with the Notification
    service_name = "Exotel"

    # The services URL
    service_url = "https://exotel.com/"

    # The default protocol
    secure_protocol = "exotel"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/exotel/"

    # The maximum length of the body
    body_maxlen = 2000

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        "{schema}://{sid}:{token}@{from_phone}",
        "{schema}://{sid}:{token}@{from_phone}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "sid": {
                "name": _("Account SID"),
                "type": "string",
                "required": True,
                "private": True,
            },
            "token": {
                "name": _("Token"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "from_phone": {
                "name": _("From Phone No / Sender ID"),
                "type": "string",
                "required": True,
                "regex": (
                    r"^(?:(?=.{3,16}$)(?=.*[A-Z.-])[A-Z0-9][A-Z0-9.-]*"
                    r"|[0-9]{6}|\+?[0-9\s)(+-]{9,})$",
                    "i",
                ),
                "map_to": "source",
            },
            "target_phone": {
                "name": _("Target Phone No"),
                "type": "string",
                "prefix": "+",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
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
            "from": {
                "alias_of": "from_phone",
            },
            "sid": {
                "alias_of": "sid",
            },
            "token": {
                "alias_of": "token",
            },
            "apikey": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "map_to": "apikey",
            },
            "key": {
                "alias_of": "apikey",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
            "unicode": {
                # Unicode characters
                "name": _("Unicode Characters"),
                "type": "bool",
                "default": True,
            },
            "region": {
                "name": _("Region Name"),
                "type": "choice:string",
                "values": EXOTEL_REGIONS,
                "default": ExotelRegion.US,
                "map_to": "region_name",
            },
            "priority": {
                "name": _("Priority"),
                "type": "choice:string",
                "values": EXOTEL_PRIORITIES,
                "default": ExotelPriority.NORMAL,
            },
        },
    )

    def __init__(
        self,
        sid,
        token,
        source,
        targets=None,
        apikey=None,
        batch=None,
        unicode=None,
        priority=None,
        region_name=None,
        **kwargs,
    ):
        """
        Initialize Exotel Object
        """
        super().__init__(**kwargs)

        # Account SID
        self.sid = validate_regex(sid)
        if not self.sid:
            msg = "An invalid Exotel SID ({}) was specified.".format(sid)
            self.logger.warning(msg)
            raise TypeError(msg)

        # API Token (associated with account)
        self.token = validate_regex(token)
        if not self.token:
            msg = "An invalid Exotel API Token ({}) was specified.".format(
                token
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # API Key used as the HTTP Basic Auth username. Older URLs did not
        # carry this separately, so default it to the account SID.
        self.apikey = validate_regex(apikey if apikey else sid)
        if not self.apikey:
            msg = "An invalid Exotel API Key ({}) was specified.".format(
                apikey
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Used for URL generation afterwards only
        self.invalid_targets = []

        # Store our region
        self.region_name = (
            self.template_args["region"]["default"]
            if region_name is None
            else validate_regex(region_name)
        )
        if not self.region_name:
            self.region_name = ""
        else:
            self.region_name = self.region_name.lower()

        if self.region_name not in EXOTEL_REGIONS:
            # Invalid region specified
            msg = "The Exotel region specified ({}) is invalid.".format(
                region_name
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Define whether or not we should set the unicode flag
        self.unicode = (
            self.template_args["unicode"]["default"]
            if unicode is None
            else bool(unicode)
        )

        # Define whether or not we should operate in batch mode
        self.batch = (
            self.template_args["batch"]["default"]
            if batch is None
            else bool(batch)
        )

        #
        # Priority
        #
        if priority is None:
            # Default
            self.priority = self.template_args["priority"]["default"]

        else:
            # Input is a string; attempt to get the lookup from our
            # priority mapping
            self.priority = priority.lower().strip()

            # Allow partial matching against supported priorities:
            # normal, norma, norm, nor, no, n (for normal)
            # high, hig, hi, h (for high)
            result = (
                next(
                    (
                        key
                        for key in EXOTEL_PRIORITY_MAP
                        if key.startswith(self.priority)
                    ),
                    None,
                )
                if self.priority
                else None
            )

            # Now test to see if we got a match
            if not result:
                msg = "An invalid Exotel priority ({}) was specified.".format(
                    priority
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            # store our successfully looked up priority
            self.priority = EXOTEL_PRIORITY_MAP[result]

        # The Source Phone #
        self.source = source

        result = parse_exotel_source(source)
        if not result:
            msg = (
                "The Account (From) Phone # / Sender ID specified "
                "({}) is invalid.".format(source)
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our parsed value
        self.source = result

        # Parse our targets
        self.targets = []

        for target in parse_phone_no(targets):
            # Validate targets and drop bad ones:
            result = is_phone_no(target, min_len=9)
            if not result:
                self.logger.warning(
                    "Dropped invalid phone # ({}) specified.".format(target),
                )
                self.invalid_targets.append(target)
                continue

            # store valid phone number
            self.targets.append(result["full"])

        if len(self.targets) == 0 and not self.invalid_targets:
            # No targets specified, use our own source.
            self.targets.append(self.source)

        return

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """
        Perform Exotel Notification
        """

        if not self.targets:
            # There were no endpoints to notify
            self.logger.warning("There were no Exotel targets to notify.")
            return False

        # error tracking (used for function return)
        has_error = False

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Our authentication
        auth = (self.apikey, self.token)

        # Prepare our payload
        payload = {
            "From": self.source,
            "Body": body,
            "EncodingType": ExotelEncoding.UNICODE
            if self.unicode
            else ExotelEncoding.TEXT,
            "Priority": self.priority,
            # The to gets populated in the loop below
            "To": None,
        }

        # Prepare our targets
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = (
            list(self.targets)
            if batch_size == 1
            else [
                self.targets[index : index + batch_size]
                for index in range(0, len(self.targets), batch_size)
            ]
        )

        # Prepare our notify_url
        notify_url = EXOTEL_API_LOOKUP[self.region_name].format(sid=self.sid)

        while len(targets):
            # Get our target to notify
            target = targets.pop(0)

            # Prepare our user(s)
            payload["To"] = target

            p_target = (
                "{} targets".format(len(target))
                if isinstance(target, list)
                else target
            )

            # Some Debug Logging
            self.logger.debug(
                "Exotel POST URL: {} (cert_verify={})".format(
                    notify_url, self.verify_certificate
                )
            )
            self.logger.debug("Exotel Payload: {}".format(payload))

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                r = requests.post(
                    notify_url,
                    auth=auth,
                    data=payload.copy(),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.ok:
                    # We had a problem
                    status_str = NotifyExotel.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send Exotel notification to {}: "
                        "{}{}error={}.".format(
                            p_target,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    # Mark our failure
                    has_error = True
                    continue

                else:
                    self.logger.info(
                        "Sent Exotel notification to %s.", p_target
                    )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Exotel:%s "
                    "notification.",
                    p_target,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                # Mark our failure
                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol,
            self.apikey,
            self.sid,
            self.token,
            self.source,
            self.region_name,
        )

    def url(self, privacy=False, *args, **kwargs):
        """
        Returns the URL built dynamically based on specified arguments.
        """

        # Define any URL parameters
        params = {
            "batch": "yes" if self.batch else "no",
            "unicode": "yes" if self.unicode else "no",
            "region": self.region_name,
            "priority": self.priority,
        }
        if self.apikey != self.sid:
            params["apikey"] = self.pprint(self.apikey, privacy, safe="")

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{sid}:{token}@{source}/{targets}/?{params}".format(
            schema=self.secure_protocol,
            sid=self.pprint(
                self.sid, privacy, mode=PrivacyMode.Secret, safe=""
            ),
            token=self.pprint(self.token, privacy, safe=""),
            source=NotifyExotel.quote(self.source, safe=""),
            targets="/".join(
                [
                    NotifyExotel.quote(x, safe="")
                    for x in chain(self.targets, self.invalid_targets)
                ]
            ),
            params=NotifyExotel.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
        if not targets:
            return 1

        if batch_size > 1:
            targets = int(targets / batch_size) + (
                1 if targets % batch_size else 0
            )

        return targets

    @staticmethod
    def parse_url(url):
        """
        Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object.

        """
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Get our entries; split_path() looks after unquoting content for us
        # by default
        results["targets"] = NotifyExotel.split_path(results["fullpath"])

        # The hostname is our source number
        results["source"] = NotifyExotel.unquote(results["host"])

        # Get our account_sid and token from the user/pass config
        results["sid"] = NotifyExotel.unquote(results["user"])
        results["token"] = NotifyExotel.unquote(results["password"])

        # Get region
        if "region" in results["qsd"] and len(results["qsd"]["region"]):
            results["region_name"] = NotifyExotel.unquote(
                results["qsd"]["region"]
            )

        # API Token
        if "token" in results["qsd"] and len(results["qsd"]["token"]):
            # Extract the Token from an argument
            results["token"] = NotifyExotel.unquote(results["qsd"]["token"])

        # API SID
        if "sid" in results["qsd"] and len(results["qsd"]["sid"]):
            # Extract the API SID from an argument
            results["sid"] = NotifyExotel.unquote(results["qsd"]["sid"])

        # API Key
        if "apikey" in results["qsd"] and len(results["qsd"]["apikey"]):
            # Extract the API Key from an argument
            results["apikey"] = NotifyExotel.unquote(results["qsd"]["apikey"])

        elif "key" in results["qsd"] and len(results["qsd"]["key"]):
            # Extract the API Key from an argument
            results["apikey"] = NotifyExotel.unquote(results["qsd"]["key"])

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifyExotel.unquote(results["qsd"]["from"])
        if "source" in results["qsd"] and len(results["qsd"]["source"]):
            results["source"] = NotifyExotel.unquote(results["qsd"]["source"])

        # Support the 'to' variable so that we can support rooms this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyExotel.parse_phone_no(
                results["qsd"]["to"]
            )

        # Get priority
        if "priority" in results["qsd"] and len(results["qsd"]["priority"]):
            results["priority"] = NotifyExotel.unquote(
                results["qsd"]["priority"]
            )

        # Get Batch Mode Flag
        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch", NotifyExotel.template_args["batch"]["default"]
            )
        )

        # Unicode Characters
        results["unicode"] = parse_bool(
            results["qsd"].get(
                "unicode", NotifyExotel.template_args["unicode"]["default"]
            )
        )

        return results
