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


# Publish notifications to brokers such as RabbitMQ, ActiveMQ Artemis,
# Apache Qpid, or Azure Service Bus.
#
# Install the library for the AMQP version your broker supports:
#  - AMQP 0-9-1 (most brokers, RabbitMQ's default): pip install pika
#  - AMQP 1.0 (the OASIS standard): pip install python-qpid-proton
#
# Select one with ?version=. By default, Apprise prefers 0.9.1 when pika is
# installed and otherwise uses 1.0.
#
# Your Apprise URL is assembled as:
#    amqp://user:password@hostname/target
#    amqps://user:password@hostname:port/target1/target2
#
#  - AMQP 0-9-1 targets are routing keys. With the default exchange, use a
#    queue name; use ?exchange= for another exchange.
#  - AMQP 1.0 targets are queue or topic addresses. Put RabbitMQ addresses
#    such as /queues/name in ?to= to preserve their slashes.
#
# Resources:
# - https://www.rabbitmq.com/tutorials/amqp-concepts
# - https://www.rabbitmq.com/docs/amqp
# - https://docs.oasis-open.org/amqp/core/v1.0/amqp-core-overview-v1.0.html

"""AMQP Notifications"""

from __future__ import annotations

import re
from time import time
from typing import Any, Optional

from ...common import NotifyFormat, NotifyType
from ...exception import AppriseImproperlyConfigured
from ...locale import gettext_lazy as _
from ...url import PrivacyMode
from ...utils.parse import parse_bool, parse_list
from ..base import NotifyBase
from .common import (
    AMQP_CONTENT_TYPES,
    AMQP_SHORTSTR_MAX,
    AMQP_VERSION_MAP,
    AMQP_VERSION_OPTIONS,
    AMQP_VERSIONS,
    AMQPConfig,
    AMQPError,
    AMQPMessage,
    AMQPVersion,
)
from .v091 import AMQP091Adapter
from .v10 import AMQP10Adapter

# The adapter that speaks each version
AMQP_ADAPTERS = {
    AMQPVersion.V091: AMQP091Adapter,
    AMQPVersion.V10: AMQP10Adapter,
}

# A version is digits split by dots or dashes, with an optional leading v
AMQP_VERSION_FORMAT = re.compile(r"v?\d+(?:[.-]\d+)*", re.IGNORECASE)

# Strips everything but the digits from a version, so 0.9.1 becomes 091
AMQP_VERSION_DIGITS = re.compile(r"[^0-9]+")


class NotifyAMQP(NotifyBase):
    """A wrapper for AMQP Notifications."""

    # Each optional package enables one AMQP version. The plugin still loads
    # when neither is installed so it can report the missing dependency.
    requirements = {
        # Either package enables a supported version
        "details": _(
            "Install pika for AMQP 0.9.1, python-qpid-proton for AMQP 1.0,"
            " or both."
        ),
        "packages_recommended": [
            AMQP091Adapter.package,
            AMQP10Adapter.package,
        ],
    }

    # The default descriptive name associated with the Notification
    service_name = "AMQP"

    # The services URL
    service_url = "https://www.amqp.org/"

    # The default protocol
    protocol = "amqp"

    # The default secure protocol
    secure_protocol = "amqps"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/amqp/"

    # The default ports for both AMQP versions
    default_insecure_port = 5672
    default_secure_port = 5671

    # AMQP has no title field, so the title is placed in the body
    title_maxlen = 0

    # Character limit used when split or truncate overflow is requested
    body_maxlen = 16777216

    # Publish to each target without an added delay
    request_rate_per_sec = 0

    # Preserve the selected body format and label its content type
    notify_format = (
        NotifyFormat.TEXT,
        NotifyFormat.MARKDOWN,
        NotifyFormat.HTML,
    )

    # Define object templates
    templates = (
        "{schema}://{host}",
        "{schema}://{host}:{port}",
        "{schema}://{user}:{password}@{host}",
        "{schema}://{user}:{password}@{host}:{port}",
        "{schema}://{host}/{targets}",
        "{schema}://{host}:{port}/{targets}",
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
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
            "user": {
                "name": _("User Name"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
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
            "version": {
                "name": _("Version"),
                "type": "choice:string",
                "values": AMQP_VERSIONS,
                # 1.0 is used instead when only its library is installed
                "default": AMQPVersion.V091,
            },
            "ver": {
                "alias_of": "version",
            },
            "exchange": {
                "name": _("Exchange"),
                "type": "string",
            },
            "vhost": {
                "name": _("Virtual Host"),
                "type": "string",
            },
            "persistent": {
                "name": _("Persistent"),
                "type": "bool",
                "default": True,
            },
            "mandatory": {
                "name": _("Mandatory"),
                "type": "bool",
                "default": True,
            },
            "priority": {
                "name": _("Priority"),
                "type": "int",
                "min": 0,
                "max": 255,
            },
            "ttl": {
                "name": _("Time To Live"),
                "type": "int",
                "min": 0,
                # AMQP 1.0 stores it as an unsigned 32-bit value
                "max": 4294967295,
            },
            "to": {
                "alias_of": "targets",
            },
        },
    )

    # Define any kwargs we're using
    template_kwargs = {
        "headers": {
            "name": _("Message Headers"),
            "prefix": "+",
        },
    }

    def __init__(
        self,
        targets: Optional[list[str]] = None,
        version: Optional[str] = None,
        exchange: Optional[str] = None,
        vhost: Optional[str] = None,
        persistent: Optional[bool] = None,
        mandatory: Optional[bool] = None,
        priority: Optional[int] = None,
        ttl: Optional[int] = None,
        headers: Optional[dict[str, str]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize AMQP Object."""
        super().__init__(**kwargs)

        # The options we were given that only one AMQP version understands
        exclusive = [
            key
            for key, value in (
                ("exchange", exchange),
                ("mandatory", mandatory),
            )
            if value is not None and value != ""
        ]

        if version is None:
            # The versions those options belong to
            implied = {AMQP_VERSION_OPTIONS[key] for key in exclusive}

            # Version-specific options select their version. Otherwise use
            # the first supported version with an installed library.
            self.version = (
                implied.pop()
                if len(implied) == 1
                else next(
                    (v for v in AMQP_VERSIONS if AMQP_ADAPTERS[v].enabled),
                    AMQPVersion.V091,
                )
            )

        else:
            # Accept 0.9, 0-9-1, v1, 1.0 and similar spellings, but nothing
            # written around them
            value = str(version).strip()
            self.version = (
                AMQP_VERSION_MAP.get(AMQP_VERSION_DIGITS.sub("", value))
                if AMQP_VERSION_FORMAT.fullmatch(value)
                else None
            )
            if self.version is None:
                msg = f"An invalid AMQP version ({version}) was specified."
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

        # The adapter that speaks our version
        self.adapter = AMQP_ADAPTERS[self.version]
        if not self.adapter.enabled:
            msg = (
                f"AMQP {self.version} requires the {self.adapter.package}"
                " package; install it with:"
                f" pip install {self.adapter.package}"
            )
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        # Options that belong to the other version are ignored
        ignored = [
            key
            for key in exclusive
            if AMQP_VERSION_OPTIONS[key] != self.version
        ]
        for key in ignored:
            self.logger.warning(
                "The AMQP %s option is only used by AMQP %s; ignoring it.",
                key,
                AMQP_VERSION_OPTIONS[key],
            )

        # Our exchange; "" is the broker's default exchange
        self.exchange = (
            exchange
            if isinstance(exchange, str) and "exchange" not in ignored
            else ""
        )

        # Our virtual host; None leaves it to the broker
        self.vhost = vhost if isinstance(vhost, str) and vhost else None

        if self.version == AMQPVersion.V091:
            # AMQP 0-9-1 cannot carry longer names than this
            for key, value in (
                ("exchange", self.exchange),
                ("vhost", self.vhost),
            ):
                if value and len(value.encode("utf-8")) > AMQP_SHORTSTR_MAX:
                    msg = (
                        f"The AMQP {key} specified is longer than"
                        f" {AMQP_SHORTSTR_MAX} bytes."
                    )
                    self.logger.warning(msg)
                    raise AppriseImproperlyConfigured(msg)

        # Whether the broker should keep our messages on disk
        self.persistent = (
            self.template_args["persistent"]["default"]
            if persistent is None
            else parse_bool(
                persistent, self.template_args["persistent"]["default"]
            )
        )

        # Whether a message nobody can receive counts as a failure
        self.mandatory = (
            self.template_args["mandatory"]["default"]
            if mandatory is None or "mandatory" in ignored
            else parse_bool(
                mandatory, self.template_args["mandatory"]["default"]
            )
        )

        # Our optional message priority and expiry
        self.priority = self._bounded_int("priority", priority)
        self.ttl = self._bounded_int("ttl", ttl)

        # Extra headers to attach to every message
        self.headers = (
            {str(k): str(v) for k, v in headers.items()}
            if isinstance(headers, dict)
            else {}
        )

        # Our targets (routing keys or addresses)
        self.targets = []
        self.invalid_targets = []
        for target in parse_list(targets):
            if (
                self.version == AMQPVersion.V091
                and len(target.encode("utf-8")) > AMQP_SHORTSTR_MAX
            ):
                self.logger.warning(
                    "Dropped AMQP routing key longer than %d bytes (%s).",
                    AMQP_SHORTSTR_MAX,
                    target,
                )
                self.invalid_targets.append(target)
                continue

            self.targets.append(target)

    def _bounded_int(self, key: str, value: Any) -> Optional[int]:
        """Return ``value`` as an int within the limits of ``key``."""
        # Nothing set means the broker's own default applies
        if value is None or value == "":
            return None

        # Our limits are defined with our template arguments
        limits = self.template_args[key]

        try:
            result = int(value)

        except (TypeError, ValueError):
            # Not a number at all
            result = None

        if result is None or not limits["min"] <= result <= limits["max"]:
            msg = f"An invalid AMQP {key} ({value}) was specified."
            self.logger.warning(msg)
            raise AppriseImproperlyConfigured(msg)

        return result

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        body_format: Optional[NotifyFormat] = None,
        **kwargs: Any,
    ) -> bool:
        """Perform AMQP Notification."""

        # With an exchange (such as a fanout one) and no targets, publish
        # once with an empty routing key
        targets = self.targets or ([""] if self.exchange else [])

        if not targets:
            # There is nowhere to publish to
            self.logger.warning("There are no AMQP targets to notify.")
            return False

        # A retry skips targets that already accepted this message
        targets = [t for t in targets if not self.is_delivered(t)]
        if not targets:
            # Every target was already reached
            return True

        # Prepare how we reach the broker
        port = self.port or (
            self.default_secure_port
            if self.secure
            else self.default_insecure_port
        )

        config = AMQPConfig(
            host=self.host,
            port=port,
            secure=self.secure,
            verify_certificate=self.verify_certificate,
            user=self.user,
            password=self.password,
            vhost=self.vhost,
            connect_timeout=self.socket_connect_timeout,
            read_timeout=self.socket_read_timeout,
            exchange=self.exchange,
            mandatory=self.mandatory,
        )

        # Prepare our message once; every target receives the same one
        message = AMQPMessage(
            # Replace invalid characters instead of failing the send
            body=body.encode("utf-8", errors="replace"),
            content_type=AMQP_CONTENT_TYPES.get(
                body_format, AMQP_CONTENT_TYPES[NotifyFormat.TEXT]
            ),
            app_id=self.app_id,
            timestamp=int(time()),
            persistent=self.persistent,
            priority=self.priority,
            ttl=self.ttl,
            headers=self.headers or None,
        )

        # For logging
        url = f"{self.host}:{port}"

        self.logger.debug(
            "AMQP %s connect: %s (cert_verify=%s)",
            self.version,
            url,
            self.verify_certificate,
        )

        # Always throttle before remote server I/O
        self.throttle()

        adapter = self.adapter(config)
        try:
            # Connect and log in
            adapter.connect()

        except AMQPError as e:
            # Nothing can be published without a connection
            self.logger.warning("Could not connect to AMQP server %s.", url)
            self.logger.debug("AMQP Exception: %s", str(e))
            return False

        has_error = False
        try:
            for target in targets:
                # Name where the message is going for our logs
                where = target or f"exchange {self.exchange}"

                # Always throttle before remote server I/O
                self.throttle()

                self.logger.debug("AMQP publish to %s/%s", url, where)
                self.logger.trace("AMQP Payload: %s", body)

                try:
                    # Publish and wait for the broker to accept it
                    adapter.publish(target, message)

                except AMQPError as e:
                    # Mark our failure and move on to our next target
                    self.logger.warning(
                        "Failed to publish AMQP notification to %s.", where
                    )
                    self.logger.debug("AMQP Exception: %s", str(e))
                    has_error = True
                    continue

                # Delivered; a retry can safely skip this target
                self.mark_delivered(target)
                self.logger.info("Sent AMQP notification to %s.", where)

        finally:
            # Always let go of our connection
            adapter.close()

        return not has_error

    @property
    def url_identifier(self) -> tuple[Any, ...]:
        """Return the fields that identify this broker connection.

        Targets are intentionally excluded.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.version,
            self.user,
            self.password,
            self.host,
            self.port
            or (
                self.default_secure_port
                if self.secure
                else self.default_insecure_port
            ),
            self.vhost,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "version": self.version,
            "persistent": "yes" if self.persistent else "no",
        }

        if self.version == AMQPVersion.V091:
            # Only AMQP 0-9-1 uses these
            params["mandatory"] = "yes" if self.mandatory else "no"
            if self.exchange:
                params["exchange"] = self.exchange

        if self.vhost:
            params["vhost"] = self.vhost

        if self.priority is not None:
            params["priority"] = str(self.priority)

        if self.ttl is not None:
            params["ttl"] = str(self.ttl)

        # Keep targets containing slashes in to= so they remain intact
        targets = (*self.targets, *self.invalid_targets)
        in_path, in_to = [], []
        for target in targets:
            (in_to if "/" in target or "\\" in target else in_path).append(
                target
            )

        if in_to:
            params["to"] = ",".join(in_to)

        # Append our headers into our parameters
        params.update({f"+{k}": v for k, v in self.headers.items()})

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ""
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=NotifyAMQP.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )

        elif self.user:
            auth = "{user}@".format(
                user=NotifyAMQP.quote(self.user, safe=""),
            )

        default_port = (
            self.default_secure_port
            if self.secure
            else self.default_insecure_port
        )

        return "{schema}://{auth}{hostname}{port}/{targets}?{params}".format(
            schema=self.secure_protocol if self.secure else self.protocol,
            auth=auth,
            # never encode hostname since we're expecting it to be a valid one
            hostname=self.host,
            port=(
                ""
                if self.port is None or self.port == default_port
                else f":{self.port}"
            ),
            targets="/".join(NotifyAMQP.quote(x, safe="") for x in in_path),
            params=NotifyAMQP.urlencode(params),
        )

    def __len__(self) -> int:
        """Returns the number of targets associated with this notification."""
        # Always return at least 1 so the framework counts this instance
        return len(self.targets) if self.targets else 1

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse an AMQP URL into constructor arguments."""

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        # Our targets are found in the path
        results["targets"] = NotifyAMQP.split_path(results["fullpath"])

        # Values in to= keep the slashes used by many AMQP 1.0 addresses
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyAMQP.parse_list(
                NotifyAMQP.unquote(results["qsd"]["to"])
            )

        # The AMQP version to use; version= wins over its ver= alias
        if "ver" in results["qsd"] and len(results["qsd"]["ver"]):
            results["version"] = NotifyAMQP.unquote(results["qsd"]["ver"])

        if "version" in results["qsd"] and len(results["qsd"]["version"]):
            results["version"] = NotifyAMQP.unquote(results["qsd"]["version"])

        # The exchange to publish to
        if "exchange" in results["qsd"] and len(results["qsd"]["exchange"]):
            results["exchange"] = NotifyAMQP.unquote(
                results["qsd"]["exchange"]
            )

        # The virtual host to use
        if "vhost" in results["qsd"] and len(results["qsd"]["vhost"]):
            results["vhost"] = NotifyAMQP.unquote(results["qsd"]["vhost"])

        # Message flags
        if "persistent" in results["qsd"] and len(
            results["qsd"]["persistent"]
        ):
            results["persistent"] = parse_bool(results["qsd"]["persistent"])

        if "mandatory" in results["qsd"] and len(results["qsd"]["mandatory"]):
            results["mandatory"] = parse_bool(results["qsd"]["mandatory"])

        # Message priority and expiry
        if "priority" in results["qsd"] and len(results["qsd"]["priority"]):
            results["priority"] = NotifyAMQP.unquote(
                results["qsd"]["priority"]
            )

        if "ttl" in results["qsd"] and len(results["qsd"]["ttl"]):
            results["ttl"] = NotifyAMQP.unquote(results["qsd"]["ttl"])

        # Add our message headers and tidy entries by unquoting them
        results["headers"] = {
            NotifyAMQP.unquote(x): NotifyAMQP.unquote(y)
            for x, y in results["qsd+"].items()
        }

        return results

    @staticmethod
    def runtime_deps() -> tuple[str, ...]:
        """Return the optional packages imported by this plugin."""
        return ("pika", "proton")
