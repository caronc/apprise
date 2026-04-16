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

# To use this plugin, simply signup with Octopush:
#  https://octopush.com/
#
# The API reference used to build this plugin was documented here:
#  https://dev.octopush.com/en/sms-gateway-api-documentation/send-sms/

from json import dumps

import requests

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import (
    is_email,
    is_phone_no,
    parse_bool,
    parse_phone_no,
    validate_regex,
)
from .base import NotifyBase


class OctopushType:
    """Octopush message types."""

    PREMIUM = "sms_premium"
    LOW_COST = "sms_low_cost"


OCTOPUSH_TYPE_MAP = {
    # Maps against string 'sms_premium'
    "p": OctopushType.PREMIUM,
    "sms_p": OctopushType.PREMIUM,
    "smsp": OctopushType.PREMIUM,
    "+": OctopushType.PREMIUM,
    # Maps against string 'sms_low_cost'
    "l": OctopushType.LOW_COST,
    "sms_l": OctopushType.LOW_COST,
    "smsl": OctopushType.LOW_COST,
    "-": OctopushType.LOW_COST,
}

OCTOPUSH_TYPES = (
    OctopushType.PREMIUM,
    OctopushType.LOW_COST,
)


class OctopushPurpose:
    """Octopush purposes."""

    ALERT = "alert"
    WHOLESALE = "wholesale"


OCTOPUSH_PURPOSES = (
    OctopushPurpose.ALERT,
    OctopushPurpose.WHOLESALE,
)


class NotifyOctopush(NotifyBase):
    """A wrapper for Octopush Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Octopush"

    # The services URL
    service_url = "https://octopush.com/"

    # The default secure protocol
    secure_protocol = "octopush"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/octopush/"

    # Notification URLs
    notify_url = "https://api.octopush.com/v1/public/sms-campaign/send"

    # The maximum length of the body
    body_maxlen = 1224

    # The maximum amount of phone numbers that can reside within a single
    # batch/frame transfer
    default_batch_size = 500

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    # Define object templates
    templates = (
        "{schema}://{api_login}/{api_key}/{targets}",
        "{schema}://{sender}:{api_login}/{api_key}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "api_login": {
                "name": _("API Login"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "api_key": {
                "name": _("API Key"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "sender": {
                "name": _("Sender"),
                "type": "string",
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
            "login": {
                "alias_of": "api_login",
            },
            "key": {
                "alias_of": "api_key",
            },
            "batch": {
                "name": _("Batch Mode"),
                "type": "bool",
                "default": False,
            },
            "replies": {
                "name": _("Accept Replies"),
                "type": "bool",
                "default": False,
            },
            "purpose": {
                "name": _("Purpose"),
                "type": "choice:string",
                "values": OCTOPUSH_PURPOSES,
                "default": OctopushPurpose.ALERT,
            },
            "type": {
                "name": _("Type"),
                "type": "choice:string",
                "values": OCTOPUSH_TYPES,
                "default": OctopushType.PREMIUM,
                "map_to": "mtype",
            },
        },
    )

    def __init__(
        self,
        api_login,
        api_key,
        targets=None,
        batch=False,
        sender=None,
        purpose=None,
        mtype=None,
        replies=False,
        **kwargs,
    ):
        """Initialize Octopush Object."""
        super().__init__(**kwargs)

        # Store our API Login
        self.api_login = validate_regex(api_login)
        if not self.api_login or not is_email(self.api_login):
            msg = "An invalid Octopush API Login ({}) was specified.".format(
                api_login
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Store our API Key
        self.api_key = validate_regex(api_key)
        if not self.api_key:
            msg = "An invalid Octopush API Key ({}) was specified.".format(
                api_key
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Prepare Batch Mode Flag
        self.batch = batch

        # Prepare Replies Mode Flag
        self.replies = replies

        # The type of the message
        if mtype is None:
            self.mtype = self.template_args["type"]["default"]
        else:
            mtype = str(mtype).lower().strip()
            self.mtype = (
                next(
                    (
                        value
                        for key, value in OCTOPUSH_TYPE_MAP.items()
                        if mtype.startswith(key)
                    ),
                    None,
                )
                if mtype
                else None
            )

        if self.mtype is None:
            msg = "The Octopush type specified ({}) is invalid.".format(mtype)
            self.logger.warning(msg)
            raise TypeError(msg)

        self.purpose = (
            self.template_args["purpose"]["default"]
            if purpose is None
            else validate_regex(purpose)
        )
        if not self.purpose:
            msg = "The Octopush purpose specified ({}) is invalid.".format(
                purpose
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        self.purpose = self.purpose.lower()
        if self.purpose not in OCTOPUSH_PURPOSES:
            msg = "The Octopush purpose specified ({}) is invalid.".format(
                purpose
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        self.sender = None
        if sender:
            self.sender = validate_regex(sender)
            if not self.sender:
                msg = "An invalid Octopush sender ({}) was specified.".format(
                    sender
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        # Initialize numbers list
        self.targets = []

        # Validate targets and drop bad ones:
        for target in parse_phone_no(targets):
            result = is_phone_no(target)
            if result:
                # Store valid phone number in E.164 format
                self.targets.append("+{}".format(result["full"]))
                continue

            self.logger.warning(
                "Dropped invalid phone ({}) specified.".format(target),
            )

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform Octopush Notification."""
        if not self.targets:
            self.logger.warning("No Octopush targets to notify.")
            return False

        # error tracking (used for function return)
        has_error = False

        # Send in batches if identified to do so
        batch_size = 1 if not self.batch else self.default_batch_size

        # Prepare our headers
        headers = {
            "User-Agent": self.app_id,
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "api-key": self.api_key,
            "api-login": self.api_login,
            "cache-control": "no-cache",
        }

        for index in range(0, len(self.targets), batch_size):
            recipients = [
                {"phone_number": phone_no}
                for phone_no in self.targets[index : index + batch_size]
            ]

            payload = {
                "recipients": recipients,
                "text": body,
                "type": self.mtype,
                "purpose": self.purpose,
                "sender": self.sender if self.sender else self.app_id,
                "with_replies": self.replies,
            }

            p_targets = self.targets[index : index + batch_size]
            verbose_dest = (
                ", ".join(p_targets)
                if len(p_targets) <= 3
                else "{} recipients".format(len(p_targets))
            )

            # Always call throttle before any remote server i/o is made
            self.throttle()

            self.logger.debug(
                "Octopush POST URL: {} (cert_verify={})".format(
                    self.notify_url, self.verify_certificate
                )
            )
            self.logger.debug("Octopush Payload: {}".format(payload))

            try:
                r = requests.post(
                    self.notify_url,
                    data=dumps(payload),
                    headers=headers,
                    verify=self.verify_certificate,
                    timeout=self.request_timeout,
                )

                if r.status_code != requests.codes.created:
                    status_str = NotifyOctopush.http_response_code_lookup(
                        r.status_code
                    )

                    self.logger.warning(
                        "Failed to send Octopush notification to {}: "
                        "{}{}error={}.".format(
                            verbose_dest,
                            status_str,
                            ", " if status_str else "",
                            r.status_code,
                        )
                    )

                    self.logger.debug(
                        "Response Details:\r\n%r", (r.content or b"")[:2000]
                    )

                    has_error = True
                    continue

                self.logger.info(
                    "Sent Octopush notification to {}.".format(verbose_dest)
                )

            except requests.RequestException as e:
                self.logger.warning(
                    "A Connection error occurred sending Octopush:%s "
                    "notification.",
                    verbose_dest,
                )
                self.logger.debug("Socket Exception: %s", str(e))

                has_error = True
                continue

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique."""
        return (
            self.secure_protocol,
            self.api_login,
            self.api_key,
            self.sender,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""
        params = {
            "batch": "yes" if self.batch else "no",
            "replies": "yes" if self.replies else "no",
            "type": self.mtype,
            "purpose": self.purpose,
        }

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        return "{schema}://{sender}{api_login}/{api_key}/{targets}?{params}".format(
            schema=self.secure_protocol,
            sender="{}:".format(NotifyOctopush.quote(self.sender, safe=""))
            if self.sender
            else "",
            api_login=self.pprint(self.api_login, privacy, safe="@"),
            api_key=self.pprint(
                self.api_key,
                privacy,
                mode=PrivacyMode.Secret,
                safe="",
            ),
            targets="/".join(
                [NotifyOctopush.quote(x, safe="+") for x in self.targets]
            ),
            params=NotifyOctopush.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        batch_size = 1 if not self.batch else self.default_batch_size
        targets = len(self.targets)
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
            return results

        tokens = NotifyOctopush.split_path(results["fullpath"])

        if "key" in results["qsd"] and len(results["qsd"]["key"]):
            results["api_key"] = NotifyOctopush.unquote(results["qsd"]["key"])
        elif tokens:
            results["api_key"] = NotifyOctopush.unquote(tokens.pop(0))

        # The remaining elements are the phone numbers we want to contact
        results["targets"] = tokens
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyOctopush.parse_phone_no(
                results["qsd"]["to"]
            )

        if "login" in results["qsd"] and len(results["qsd"]["login"]):
            results["api_login"] = NotifyOctopush.unquote(
                results["qsd"]["login"]
            )
        elif results["user"] or results["password"]:
            results["api_login"] = "{}@{}".format(
                NotifyOctopush.unquote(results["user"])
                if not results["password"]
                else NotifyOctopush.unquote(results["password"]),
                NotifyOctopush.unquote(results["host"]),
            )

        results["batch"] = parse_bool(
            results["qsd"].get(
                "batch", NotifyOctopush.template_args["batch"]["default"]
            )
        )
        results["replies"] = parse_bool(
            results["qsd"].get(
                "replies",
                NotifyOctopush.template_args["replies"]["default"],
            )
        )

        if "type" in results["qsd"] and len(results["qsd"]["type"]):
            results["mtype"] = NotifyOctopush.unquote(results["qsd"]["type"])

        if "purpose" in results["qsd"] and len(results["qsd"]["purpose"]):
            results["purpose"] = NotifyOctopush.unquote(
                results["qsd"]["purpose"]
            )

        if "sender" in results["qsd"] and len(results["qsd"]["sender"]):
            results["sender"] = NotifyOctopush.unquote(
                results["qsd"]["sender"]
            )
        elif results["user"] and results["password"]:
            results["sender"] = NotifyOctopush.unquote(results["user"])

        return results
