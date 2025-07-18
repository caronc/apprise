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

try:
    import smpplib
    import smpplib.consts
    import smpplib.gsm

    # We're good to go!
    NOTIFY_SMPP_ENABLED = True

except ImportError:
    # cryptography is required in order for this package to work
    NOTIFY_SMPP_ENABLED = False


from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..utils.parse import is_phone_no, parse_phone_no
from .base import NotifyBase


class NotifySMPP(NotifyBase):
    """A wrapper for SMPP Notifications."""

    # Set our global enabled flag
    enabled = NOTIFY_SMPP_ENABLED

    requirements = {
        # Define our required packaging in order to work
        "packages_required": "smpplib"
    }

    # The default descriptive name associated with the Notification
    service_name = _("SMPP")

    # The services URL
    service_url = "https://smpp.org/"

    # The default protocol
    protocol = "smpp"

    # The default secure protocol
    secure_protocol = "smpps"

    # Default port setup
    default_port = 2775
    default_secure_port = 3550

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_SMPP"

    # A title can not be used for SMS Messages.  Setting this to zero will
    # cause any title (if defined) to get placed into the message body.
    title_maxlen = 0

    templates = (
        "{schema}://{user}:{password}@{host}/{from_phone}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{from_phone}/{targets}",
    )

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "user": {
                "name": _("Username"),
                "type": "string",
                "required": True,
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "host": {
                "name": _("Host"),
                "type": "string",
                "required": True,
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
            "from_phone": {
                "name": _("From Phone No"),
                "type": "string",
                "regex": (r"^[0-9\s)(+-]+$", "i"),
                "required": True,
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
                "required": True,
            },
        },
    )

    def __init__(self, source=None, targets=None, **kwargs):
        """Initialize SMPP Object."""

        super().__init__(**kwargs)

        self.source = None

        if not (self.user and self.password):
            msg = "No SMPP user/pass combination was provided"
            self.logger.warning(msg)
            raise TypeError(msg)

        result = is_phone_no(source)
        if not result:
            msg = (
                f"The Account (From) Phone # specified ({source}) is invalid."
            )
            self.logger.warning(msg)
            raise TypeError(msg)

        # Tidy source
        self.source = result["full"]

        # Used for URL generation afterwards only
        self._invalid_targets = []

        # Parse our targets
        self.targets = []

        for target in parse_phone_no(targets, prefix=True):
            # Validate targets and drop bad ones:
            result = is_phone_no(target)
            if not result:
                self.logger.warning(
                    f"Dropped invalid phone # ({target}) specified.",
                )
                self._invalid_targets.append(target)
                continue

            # store valid phone number
            self.targets.append(result["full"])

    @property
    def url_identifier(self):
        """Returns all the identifiers that make this URL unique from another
        similar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user,
            self.password,
            self.host,
            self.port,
            self.source,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        return (
            "{schema}://{user}:{password}@{host}/{source}/{targets}/?{params}"
        ).format(
            schema=self.secure_protocol if self.secure else self.protocol,
            user=self.user,
            password=self.password,
            host=f"{self.host}:{self.port}" if self.port else self.host,
            source=self.source,
            targets="/".join([
                NotifySMPP.quote(t, safe="")
                for t in chain(self.targets, self._invalid_targets)
            ]),
            params=self.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification.

        Always return 1 at least
        """
        return len(self.targets) if self.targets else 1

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform SMPP Notification."""

        if not self.targets:
            # There were no targets to notify
            self.logger.warning("There were no SMPP targets to notify")
            return False

        # error tracking (used for function return)
        has_error = False

        port = (
            self.default_port if not self.secure else self.default_secure_port
        )

        client = smpplib.client.Client(
            self.host, port, allow_unknown_opt_params=True
        )
        try:
            client.connect()
            client.bind_transmitter(
                system_id=self.user, password=self.password
            )

        except smpplib.exceptions.ConnectionError as e:
            self.logger.warning(
                "Failed to establish connection to SMPP server"
                f" {self.host}: {e}"
            )
            return False

        for target in self.targets:
            parts, encoding, msg_type = smpplib.gsm.make_parts(body)

            # Always call throttle before any remote server i/o is made
            self.throttle()

            try:
                for payload in parts:
                    client.send_message(
                        source_addr_ton=smpplib.consts.SMPP_TON_INTL,
                        source_addr=self.source,
                        dest_addr_ton=smpplib.consts.SMPP_TON_INTL,
                        destination_addr=target,
                        short_message=payload,
                        data_coding=encoding,
                        esm_class=msg_type,
                        registered_delivery=True,
                    )
            except Exception as e:
                self.logger.warning(f"Failed to send SMPP notification: {e}")
                # Mark our failure
                has_error = True
                continue

            self.logger.info("Sent SMPP notification to %s", target)

        client.unbind()
        client.disconnect()
        return not has_error

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow us to re-
        instantiate this object."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Support the 'from'  and 'source' variable so that we can support
        # targets this way too.
        # The 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifySMPP.unquote(results["qsd"]["from"])

            # hostname will also be a target in this case
            results["targets"] = [
                *NotifySMPP.parse_phone_no(results["host"]),
                *NotifySMPP.split_path(results["fullpath"]),
            ]

        else:
            # store our source
            results["source"] = NotifySMPP.unquote(results["host"])

            # store targets
            results["targets"] = NotifySMPP.split_path(results["fullpath"])

        # Support the 'to' variable so that we can support targets this way too
        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifySMPP.parse_phone_no(
                results["qsd"]["to"]
            )

        results["targets"] = NotifySMPP.split_path(results["fullpath"])

        # Support the 'to' variable so that we can support targets this way too
        # 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifySMPP.parse_phone_no(
                results["qsd"]["to"]
            )

        # store any additional payload extras defined
        results["payload"] = {
            NotifySMPP.unquote(x): NotifySMPP.unquote(y)
            for x, y in results["qsd:"].items()
        }

        # Add our GET parameters in the event the user wants to pass them
        results["params"] = {
            NotifySMPP.unquote(x): NotifySMPP.unquote(y)
            for x, y in results["qsd-"].items()
        }

        # Support the 'from' and 'source' variable so that we can support
        # targets this way too.
        # 'from' makes it easier to use yaml configuration
        if "from" in results["qsd"] and len(results["qsd"]["from"]):
            results["source"] = NotifySMPP.unquote(results["qsd"]["from"])
        elif results["targets"]:
            # from phone number is the first entry in the list otherwise
            results["source"] = results["targets"].pop(0)

        return results
