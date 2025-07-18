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

# PAHO MQTT Documentation:
#  https://www.eclipse.org/paho/index.php?page=clients/python/docs/index.php
#
# Looking at the PAHO MQTT Source can help shed light on what's going on too
# as their inline documentation is pretty good!
#   https://github.com/eclipse/paho.mqtt.python\
#           /blob/master/src/paho/mqtt/client.py
from datetime import datetime
from os.path import isfile
import re
import ssl
from time import sleep

from ..common import NotifyType
from ..locale import gettext_lazy as _
from ..url import PrivacyMode
from ..utils.parse import parse_bool, parse_list
from .base import NotifyBase

# Default our global support flag
NOTIFY_MQTT_SUPPORT_ENABLED = False

try:
    # 3rd party modules
    import paho.mqtt.client as mqtt

    # We're good to go!
    NOTIFY_MQTT_SUPPORT_ENABLED = True

    MQTT_PROTOCOL_MAP = {
        # v3.1.1
        "311": mqtt.MQTTv311,
        # v3.1
        "31": mqtt.MQTTv31,
        # v5.0
        "5": mqtt.MQTTv5,
        # v5.0 (alias)
        "50": mqtt.MQTTv5,
    }

except ImportError:
    # No problem; we just simply can't support this plugin because we're
    # either using Linux, or simply do not have pywin32 installed.
    MQTT_PROTOCOL_MAP = {}

# A lookup map for relaying version to user
HUMAN_MQTT_PROTOCOL_MAP = {
    "v3.1.1": "311",
    "v3.1": "31",
    "v5.0": "5",
}


class NotifyMQTT(NotifyBase):
    """A wrapper for MQTT Notifications."""

    # Set our global enabled flag
    enabled = NOTIFY_MQTT_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        "packages_required": "paho-mqtt != 2.0.*"
    }

    # The default descriptive name associated with the Notification
    service_name = "MQTT Notification"

    # The default protocol
    protocol = "mqtt"

    # Secure protocol
    secure_protocol = "mqtts"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://github.com/caronc/apprise/wiki/Notify_mqtt"

    # MQTT does not have a title
    title_maxlen = 0

    # The maximum length a body can be set to
    body_maxlen = 268435455

    # Use a throttle; but it doesn't need to be so strict since most
    # MQTT server hostings can handle the small bursts of packets and are
    # locally hosted anyway
    request_rate_per_sec = 0.5

    # Port Defaults (unless otherwise specified)
    mqtt_insecure_port = 1883

    # The default secure port to use (if mqtts://)
    mqtt_secure_port = 8883

    # The default mqtt keepalive value
    mqtt_keepalive = 30

    # The default mqtt transport
    mqtt_transport = "tcp"

    # The number of seconds to wait for a publish to occur at before
    # checking to see if it's been sent yet.
    mqtt_block_time_sec = 0.2

    # Set the maximum number of messages with QoS>0 that can be part way
    # through their network flow at once.
    mqtt_inflight_messages = 200

    # Define object templates
    templates = (
        "{schema}://{user}@{host}/{topic}",
        "{schema}://{user}@{host}:{port}/{topic}",
        "{schema}://{user}:{password}@{host}/{topic}",
        "{schema}://{user}:{password}@{host}:{port}/{topic}",
    )

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
                "required": True,
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
                "required": True,
            },
            "topic": {
                "name": _("Target Queue"),
                "type": "string",
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
            "qos": {
                "name": _("QOS"),
                "type": "int",
                "default": 0,
                "min": 0,
                "max": 2,
            },
            "version": {
                "name": _("Version"),
                "type": "choice:string",
                "values": HUMAN_MQTT_PROTOCOL_MAP,
                "default": "v3.1.1",
            },
            "client_id": {
                "name": _("Client ID"),
                "type": "string",
            },
            "session": {
                "name": _("Use Session"),
                "type": "bool",
                "default": False,
            },
            "retain": {
                "name": _("Retain Messages"),
                "type": "bool",
                "default": False,
            },
        },
    )

    def __init__(
        self,
        targets=None,
        version=None,
        qos=None,
        client_id=None,
        session=None,
        retain=None,
        **kwargs,
    ):
        """Initialize MQTT Object."""

        super().__init__(**kwargs)

        # Initialize topics
        self.topics = parse_list(targets)

        if version is None:
            self.version = self.template_args["version"]["default"]
        else:
            self.version = version

        # Save our client id if specified
        self.client_id = client_id

        # Maintain our session (associated with our user id if set)
        self.session = (
            self.template_args["session"]["default"]
            if session is None or not self.client_id
            else parse_bool(session)
        )

        # Our Retain Message Flag
        self.retain = (
            self.template_args["retain"]["default"]
            if retain is None
            else parse_bool(retain)
        )

        # Set up our Quality of Service (QoS)
        try:
            self.qos = (
                self.template_args["qos"]["default"]
                if qos is None
                else int(qos)
            )

            if (
                self.qos < self.template_args["qos"]["min"]
                or self.qos > self.template_args["qos"]["max"]
            ):
                # Let error get handle on exceptio higher up
                raise ValueError("")

        except (ValueError, TypeError):
            msg = f"An invalid MQTT QOS ({qos}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        if not self.port:
            # Assign port (if not otherwise set)
            self.port = (
                self.mqtt_secure_port
                if self.secure
                else self.mqtt_insecure_port
            )

        self.ca_certs = None
        if self.secure:
            # verify SSL key or abort
            # TODO: There is no error reporting or aborting here?
            #       It could be useful to inform the user _where_ Apprise
            #       tried to find the root CA certificates file.
            self.ca_certs = next(
                (
                    cert
                    for cert in self.CA_CERTIFICATE_FILE_LOCATIONS
                    if isfile(cert)
                ),
                None,
            )

        # Set up our MQTT Publisher
        try:
            # Get our protocol
            self.mqtt_protocol = MQTT_PROTOCOL_MAP[
                re.sub(r"[^0-9]+", "", self.version)
            ]

        except KeyError:
            msg = (
                f"An invalid MQTT Protocol version ({version}) was specified."
            )
            self.logger.warning(msg)
            raise TypeError(msg) from None

        # Our MQTT Client Object
        self.client = mqtt.Client(
            client_id=self.client_id,
            clean_session=not self.session,
            userdata=None,
            protocol=self.mqtt_protocol,
            transport=self.mqtt_transport,
        )

        # Our maximum number of in-flight messages
        self.client.max_inflight_messages_set(self.mqtt_inflight_messages)

        # Toggled to False once our connection has been established at least
        # once
        self.__initial_connect = True

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform MQTT Notification."""

        if len(self.topics) == 0:
            # There were no services to notify
            self.logger.warning("There were no MQTT topics to notify.")
            return False

        # For logging:
        url = f"{self.host}:{self.port}"

        try:
            if self.__initial_connect:
                # Our initial connection
                if self.user:
                    self.client.username_pw_set(
                        self.user, password=self.password
                    )

                if self.secure:
                    if self.ca_certs is None:
                        self.logger.error(
                            "MQTT secure communication can not be verified, "
                            "CA certificates file missing"
                        )
                        return False

                    self.client.tls_set(
                        ca_certs=self.ca_certs,
                        certfile=None,
                        keyfile=None,
                        cert_reqs=ssl.CERT_REQUIRED,
                        tls_version=ssl.PROTOCOL_TLS,
                        ciphers=None,
                    )

                    # Set our TLS Verify Flag
                    self.client.tls_insecure_set(not self.verify_certificate)

                # Establish our connection
                if (
                    self.client.connect(
                        self.host,
                        port=self.port,
                        keepalive=self.mqtt_keepalive,
                    )
                    != mqtt.MQTT_ERR_SUCCESS
                ):
                    self.logger.warning(
                        "An MQTT connection could not be established for"
                        f" {url}"
                    )
                    return False

                # Start our client loop
                self.client.loop_start()

                # Throttle our start otherwise the starting handshaking doesnt
                # work. I'm not sure if this is a bug or not, but with qos=0,
                # and without this sleep(), the messages randomly fails to be
                # delivered.
                sleep(0.01)

                # Toggle our flag since we never need to enter this area again
                self.__initial_connect = False

            # Create a copy of the subreddits list
            topics = list(self.topics)

            has_error = False
            while len(topics) > 0 and not has_error:
                # Retrieve our subreddit
                topic = topics.pop()

                # For logging:
                url = f"{self.host}:{self.port}/{topic}"

                # Always call throttle before any remote server i/o is made
                self.throttle()

                # handle a re-connection
                if (
                    not self.client.is_connected()
                    and self.client.reconnect() != mqtt.MQTT_ERR_SUCCESS
                ):
                    self.logger.warning(
                        f"An MQTT connection could not be sustained for {url}"
                    )
                    has_error = True
                    break

                # Some Debug Logging
                self.logger.debug(
                    "MQTT POST URL:"
                    f" {url} (cert_verify={self.verify_certificate})"
                )
                self.logger.debug(f"MQTT Payload: {body!s}")

                result = self.client.publish(
                    topic, payload=body, qos=self.qos, retain=self.retain
                )

                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    # Toggle our status
                    self.logger.warning(
                        f"An error (rc={result.rc}) occured when sending MQTT"
                        f" to {url}"
                    )
                    has_error = True
                    break

                elif not result.is_published():
                    self.logger.debug(
                        "Blocking until MQTT payload is published..."
                    )
                    reference = datetime.now()
                    while not has_error and not result.is_published():
                        # Throttle
                        sleep(self.mqtt_block_time_sec)

                        # Our own throttle so we can abort eventually....
                        elapsed = (datetime.now() - reference).total_seconds()
                        if elapsed >= self.socket_read_timeout:
                            self.logger.warning(
                                "The MQTT message could not be delivered"
                            )
                            has_error = True

                # if we reach here; we're at the bottom of our loop
                # we loop around and do the next topic now

        except ConnectionError as e:
            self.logger.warning(f"MQTT Connection Error received from {url}")
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        except ssl.CertificateError as e:
            self.logger.warning(
                f"MQTT SSL Certificate Error received from {url}"
            )
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        except ValueError as e:
            # ValueError's are thrown from publish() call if there is a problem
            self.logger.warning(f"MQTT Publishing error received: from {url}")
            self.logger.debug(f"Socket Exception: {e!s}")
            return False

        if not has_error:
            # Verbal notice
            self.logger.info("Sent MQTT notification")

        return not has_error

    @property
    def url_identifier(self):
        """Returns all of the identifiers that make this URL unique from
        another simliar one.

        Targets or end points should never be identified here.
        """
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.user,
            self.password,
            self.host,
            (
                self.port
                if self.port
                else (
                    self.mqtt_secure_port
                    if self.secure
                    else self.mqtt_insecure_port
                )
            ),
            self.fullpath.rstrip("/"),
            self.client_id,
        )

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parameters
        params = {
            "version": self.version,
            "qos": str(self.qos),
            "session": "yes" if self.session else "no",
            "retain": "yes" if self.retain else "no",
        }

        if self.client_id:
            # Our client id is set if specified
            params["client_id"] = self.client_id

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        # Determine Authentication
        auth = ""
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=NotifyMQTT.quote(self.user, safe=""),
                password=self.pprint(
                    self.password, privacy, mode=PrivacyMode.Secret, safe=""
                ),
            )
        elif self.user:
            auth = "{user}@".format(
                user=NotifyMQTT.quote(self.user, safe=""),
            )

        default_port = (
            self.mqtt_secure_port if self.secure else self.mqtt_insecure_port
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
            targets=",".join(
                [NotifyMQTT.quote(x, safe="/") for x in self.topics]
            ),
            params=NotifyMQTT.urlencode(params),
        )

    def __len__(self):
        """Returns the number of targets associated with this notification."""
        return len(self.topics)

    @staticmethod
    def parse_url(url):
        """There are no parameters nessisary for this protocol; simply having
        windows:// is all you need.

        This function just makes sure that is in place.
        """

        results = NotifyBase.parse_url(url)
        if not results:
            # We're done early as we couldn't load the results
            return results

        try:
            # Acquire topic(s)
            results["targets"] = parse_list(
                NotifyMQTT.unquote(results["fullpath"].lstrip("/"))
            )

        except AttributeError:
            # No 'fullpath' specified
            results["targets"] = []

        # The MQTT protocol version to use
        if "version" in results["qsd"] and len(results["qsd"]["version"]):
            results["version"] = NotifyMQTT.unquote(results["qsd"]["version"])

        # The MQTT Client ID
        if "client_id" in results["qsd"] and len(results["qsd"]["client_id"]):
            results["client_id"] = NotifyMQTT.unquote(
                results["qsd"]["client_id"]
            )

        if "session" in results["qsd"] and len(results["qsd"]["session"]):
            results["session"] = parse_bool(results["qsd"]["session"])

        # Message Retain Flag
        if "retain" in results["qsd"] and len(results["qsd"]["retain"]):
            results["retain"] = parse_bool(results["qsd"]["retain"])

        # The MQTT Quality of Service to use
        if "qos" in results["qsd"] and len(results["qsd"]["qos"]):
            results["qos"] = NotifyMQTT.unquote(results["qsd"]["qos"])

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"].extend(
                NotifyMQTT.parse_list(results["qsd"]["to"])
            )

        # return results
        return results

    @property
    def CA_CERTIFICATE_FILE_LOCATIONS(self):
        """Return possible locations to root certificate authority (CA)
        bundles.

        Taken from https://golang.org/src/crypto/x509/root_linux.go
        TODO: Maybe refactor to a general utility function?
        """
        candidates = [
            # Debian/Ubuntu/Gentoo etc.
            "/etc/ssl/certs/ca-certificates.crt",
            # Fedora/RHEL 6
            "/etc/pki/tls/certs/ca-bundle.crt",
            # OpenSUSE
            "/etc/ssl/ca-bundle.pem",
            # OpenELEC
            "/etc/pki/tls/cacert.pem",
            # CentOS/RHEL 7
            "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
            # macOS Homebrew; brew install ca-certificates
            "/usr/local/etc/ca-certificates/cert.pem",
        ]

        # Certifi provides Mozilla's carefully curated collection of Root
        # Certificates for validating the trustworthiness of SSL certificates
        # while verifying the identity of TLS hosts. It has been extracted from
        # the Requests project.
        try:
            import certifi

            candidates.append(certifi.where())
        except ImportError:  # pragma: no cover
            pass

        return candidates
