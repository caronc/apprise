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

# Keybase Chat Notifications
#
# Keybase is an end-to-end encrypted messaging platform. Apprise sends
# notifications by connecting directly to the locally running Keybase
# service -- no binary wrapper is required.
#
# Two connection modes are supported:
#
#   socket (default)
#     Apprise connects to the Keybase service via its Unix domain socket.
#     The socket path is auto-detected for the current platform; you may
#     override it with the ?socket= query parameter.
#
#     Security: any custom socket path must contain the word "keybase"
#     (case-insensitive).  This guards against ?socket= being aimed at
#     unrelated system sockets (e.g. /var/run/docker.sock).  The default
#     auto-detected paths always satisfy this requirement.
#
#     Linux default:  $XDG_RUNTIME_DIR/keybase/keybased.sock
#     macOS default:  ~/Library/Group Containers/keybase/Library/keybased.sock
#     Windows:        \\.\pipe\keybase.service
#
#   tcp
#     Apprise connects over HTTP to a local Keybase service endpoint.
#     The service port must be provided either in the URL authority or
#     via ?port=.  The host defaults to localhost.
#
# Two target types are supported:
#
#   @username          -- direct message (1-on-1 with a Keybase user)
#   teamname           -- post to a team channel (default: #general)
#   teamname#channel   -- post to a specific team channel
#
# Apprise URL forms:
#
#   Socket mode (default):
#     keybase://_/@alice
#     keybase://_/myteam
#     keybase://_/myteam%23dev
#     keybase://_/@alice?socket=/run/user/1000/keybase/keybased.sock
#
#   TCP mode:
#     keybase://localhost:3000/@alice
#     keybase://localhost:3000/myteam%23dev
#
#   Optional Saltpack signing (requires PyNaCl):
#     keybase://_/@alice?sigkey=aabb...64hexchars
#
# The keybase service must be running and the logged-in user must have
# permission to send messages to the specified targets.
#
# API reference:
#   https://keybase.io/docs/api/1.0/call/chat/send
#   https://book.keybase.io/docs/bots
#   https://saltpack.org/signing-crypto-format

import json
import os
import socket as _socket
import stat

import requests

from ...common import NotifyType
from ...locale import gettext_lazy as _
from ...url import PrivacyMode
from ...utils.parse import parse_list
from ...utils.saltpack import (
    NACL_SUPPORT,
    AppriseSaltpackController,
    AppriseSaltpackException,
)
from ..base import NotifyBase
from .common import (
    IS_KEYBASE_SOCKET_PATH,
    IS_TEAM_TARGET,
    IS_USER_TARGET,
    IS_VALID_SIGKEY,
    KEYBASE_DEFAULT_CHANNEL,
    KEYBASE_DEFAULT_HOST,
    KEYBASE_DEFAULT_MODE,
    KEYBASE_DEFAULT_PORT,
    KEYBASE_MODES,
    KeybaseMode,
    keybase_default_socket,
)


class NotifyKeybase(NotifyBase):
    """A wrapper for Keybase Chat Notifications."""

    # The default descriptive name associated with the Notification
    service_name = "Keybase"

    # The services URL
    service_url = "https://keybase.io/"

    # The default protocol
    protocol = "keybase"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/keybase/"

    # PyNaCl is recommended for Saltpack signing mode
    requirements = {
        "packages_recommended": "PyNaCl",
    }

    # Keybase messages are plain text
    body_maxlen = 10000

    # No title concept in Keybase chat
    title_maxlen = 0

    # Keybase supports file attachments via the 'attach' API method
    attachment_support = True

    # No remote rate limit; local service call
    request_rate_per_sec = 0

    # No URL identifier -- this is a local service, not a remote endpoint
    url_identifier = False

    # Define object URL templates
    # First template: socket mode (no host/port in authority)
    # Second template: TCP mode (host:port in authority)
    templates = (
        "{schema}://{targets}",
        "{schema}://{host}:{port}/{targets}",
    )

    # Define our template tokens
    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            # @username -- direct message to a Keybase user
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            # teamname -- message to a team's default channel
            "target_team": {
                "name": _("Target Team"),
                "type": "string",
                "map_to": "targets",
            },
            # teamname#channel -- message to a specific team channel
            "target_team_channel": {
                "name": _("Target Team Channel"),
                "type": "string",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
            "host": {
                "name": _("Hostname"),
                "type": "string",
            },
            "port": {
                "name": _("Port"),
                "type": "int",
                "min": 1,
                "max": 65535,
            },
        },
    )

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            # Comma-separated alias for targets in the path
            "to": {
                "alias_of": "targets",
            },
            # Optional Ed25519 signing-key seed (64 hex chars)
            "sigkey": {
                "name": _("Signing Key"),
                "type": "string",
                "private": True,
            },
            # Connection mode: socket (default) or tcp
            "mode": {
                "name": _("Mode"),
                "type": "choice:string",
                "values": KEYBASE_MODES,
                "default": KEYBASE_DEFAULT_MODE,
            },
            # Override socket path for socket mode.
            # The path must contain the word "keybase" (case-insensitive)
            # to prevent accidental use of unrelated system sockets.
            "socket": {
                "name": _("Socket Path"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        targets=None,
        sigkey=None,
        mode=None,
        socket_path=None,
        **kwargs,
    ):
        """Initialize Keybase Object."""
        super().__init__(**kwargs)

        # Parsed and validated target list.
        # Each entry is a tuple: ("user", username) or
        # ("team", team_name, channel_name)
        self.targets = []

        # Track invalid targets for URL round-tripping
        self._invalid_targets = []

        # Parse each raw target string
        for raw in parse_list(targets):
            # Try user DM (@username)
            match = IS_USER_TARGET.match(raw)
            if match:
                self.targets.append(("user", match.group("name")))
                continue

            # Try team (teamname or teamname#channel)
            match = IS_TEAM_TARGET.match(raw)
            if match:
                team = match.group("team")
                channel = match.group("channel") or KEYBASE_DEFAULT_CHANNEL
                self.targets.append(("team", team, channel))
                continue

            # Drop the target and record it for URL round-trip
            self.logger.warning(
                "Dropping invalid Keybase target: %s",
                raw,
            )
            self._invalid_targets.append(raw)

        # Require at least one valid target
        if not self.targets:
            msg = "No valid Keybase targets were specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        # Validate and store the optional Saltpack signing key seed
        self.sigkey = None
        if sigkey:
            if not IS_VALID_SIGKEY.match(sigkey):
                msg = "Keybase signing key must be exactly 64 hex characters."
                self.logger.warning(msg)
                raise TypeError(msg)
            # Store normalised to lowercase
            self.sigkey = sigkey.lower()

        # Determine connection mode:
        #   1. Explicit mode= kwarg (highest priority)
        #   2. Port present in URL -> implies TCP
        #   3. Default to socket
        if mode and mode.lower() in KEYBASE_MODES:
            self.mode = mode.lower()

        elif self.port is not None:
            # A port in the URL authority always signals TCP mode
            self.mode = KeybaseMode.TCP

        else:
            # No port, no explicit mode -> use Unix socket
            self.mode = KEYBASE_DEFAULT_MODE

        # Store the socket path (socket mode only); auto-detect if absent
        self.socket_path = (
            socket_path if socket_path else keybase_default_socket()
        )

        # Validate the socket path when it refers to a user-provided value
        # and the path already exists on disk.
        if socket_path and self.mode == KeybaseMode.SOCKET:
            # Security guard: reject paths that do not reference keybase.
            # This prevents ?socket= from being aimed at unrelated system
            # sockets (e.g. /var/run/docker.sock,
            # /run/containerd/containerd.sock).  Every legitimate Keybase
            # socket path -- platform defaults and custom installs alike --
            # contains the word "keybase".
            if not IS_KEYBASE_SOCKET_PATH.search(socket_path):
                msg = (
                    "Keybase socket path must contain 'keybase' to"
                    " prevent misuse of unrelated system"
                    " sockets: {}".format(socket_path)
                )
                self.logger.warning(msg)
                raise TypeError(msg)

            # Reject anything that is not a Unix domain socket -- this
            # prevents socket= from being pointed at regular files
            # (/etc/shadow, /dev/sda, ...) or other non-socket objects.
            try:
                path_stat = os.stat(self.socket_path)

            except OSError:
                # Path does not exist yet; the service may not be running.
                # Accept it now; the connect() call will fail if needed.
                path_stat = None

            if path_stat is not None and not stat.S_ISSOCK(path_stat.st_mode):
                msg = (
                    "Keybase socket path does not point to a"
                    " socket: {}".format(self.socket_path)
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        # For TCP mode: apply defaults for missing host / port
        if self.mode == KeybaseMode.TCP:
            if not self.host or self.host == "_":
                # Fall back to localhost when no real host was given
                self.host = KEYBASE_DEFAULT_HOST

            if self.port is None:
                # Use the well-known keybase service port default
                self.port = KEYBASE_DEFAULT_PORT

    def _stat_socket_path(self):
        """Raise OSError if socket_path does not point to a Unix socket."""

        # Check whether the path exists and is actually a socket file
        try:
            path_stat = os.stat(self.socket_path)
            if not stat.S_ISSOCK(path_stat.st_mode):
                # Path exists but is not a socket (e.g. a regular file)
                raise OSError(
                    "Path is not a Unix socket: {}".format(self.socket_path)
                )

        except FileNotFoundError as exc:
            # Socket file missing -- service is likely not running
            raise OSError(
                "Keybase socket not found: {}. "
                "Is the Keybase service running?".format(self.socket_path)
            ) from exc

    def _send_socket(self, payload):
        """Send payload over a Unix domain socket; return response dict."""

        # AF_UNIX is required for socket mode
        if not hasattr(_socket, "AF_UNIX"):
            raise OSError(
                "Unix domain sockets are unavailable on this "
                "platform; configure mode=tcp instead."
            )

        # Safety: verify the path is a Unix socket before connecting.
        self._stat_socket_path()

        # Open a stream socket for the Unix domain transport
        sock = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        sock.settimeout(self.socket_read_timeout)

        try:
            # Connect to the keybase service socket file
            sock.connect(self.socket_path)

            # Encode and send the JSON payload terminated by a newline
            data = json.dumps(payload).encode("utf-8") + b"\n"
            sock.sendall(data)

            # Read until the newline-terminated response arrives
            buf = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    # Connection closed before full response
                    break

                buf += chunk
                if b"\n" in buf:
                    # Complete response received
                    break

        finally:
            # Always close the socket regardless of outcome
            sock.close()

        # Parse the first newline-delimited JSON object in the buffer
        try:
            return json.loads(buf.split(b"\n")[0])

        except (ValueError, IndexError):
            # Non-JSON or empty response -- treat as success (no error key)
            return {}

    def _send_tcp(self, payload):
        """Send payload via HTTP to the local keybase service."""

        # Construct the keybase HTTP API endpoint
        url = "http://{}:{}/v1".format(self.host, self.port)

        # Attempt the HTTP POST
        try:
            r = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                verify=self.verify_certificate,
                timeout=self.request_timeout,
            )

            # Non-OK HTTP status is returned as an API-level error dict
            if r.status_code != requests.codes.ok:
                return {
                    "error": {
                        "code": r.status_code,
                        "message": r.text[:200],
                    }
                }

            # Parse and return the JSON response body
            try:
                return r.json()

            except ValueError:
                # Empty or non-JSON body
                return {}

        except requests.RequestException as exc:
            # Re-raise as OSError so send() handles it uniformly
            raise OSError(str(exc)) from exc

    def send(
        self,
        body,
        title="",
        notify_type=NotifyType.INFO,
        attach=None,
        **kwargs,
    ):
        """Perform Keybase Chat Notification."""

        # Apply Saltpack signing when a signing key is configured
        if self.sigkey:
            if not NACL_SUPPORT:
                self.logger.warning(
                    "Keybase Saltpack signing requires PyNaCl;"
                    " install with: pip install PyNaCl"
                )
                return False

            # Sign the message body with Saltpack v2.0
            controller = AppriseSaltpackController()
            try:
                body = controller.sign(body, self.sigkey)

            except AppriseSaltpackException as exc:
                self.logger.warning("Keybase Saltpack signing failed: %s", exc)
                return False

        # Track overall delivery status across all targets
        has_error = False

        # Iterate over all targets and send one message per target
        for target in self.targets:
            kind = target[0]

            if kind == "user":
                # Direct-message channel descriptor
                _, username = target
                channel = {"name": username}

            else:
                # Team channel descriptor
                _, team, ch_name = target
                channel = {
                    "name": team,
                    "topic_name": ch_name,
                    "members_type": "team",
                }

            # Build the keybase chat API JSON payload
            payload = {
                "method": "send",
                "params": {
                    "options": {
                        "channel": channel,
                        "message": {"body": body},
                    },
                },
            }

            self.logger.debug("Keybase target: %s", channel)
            self.logger.debug("Keybase payload: %s", payload)

            # Throttle before each service call
            self.throttle()

            # Dispatch to the appropriate transport
            try:
                response = (
                    self._send_socket(payload)
                    if self.mode == KeybaseMode.SOCKET
                    else self._send_tcp(payload)
                )

            except OSError as exc:
                self.logger.warning(
                    "Keybase %s connection error for %s: %s",
                    self.mode,
                    channel.get("name"),
                    exc,
                )
                has_error = True
                continue

            # Check for API-level errors in the JSON response
            if "error" in response:
                err = response["error"]
                self.logger.warning(
                    "Keybase API error for %s: %s",
                    channel.get("name"),
                    err.get("message", "unknown")
                    if isinstance(err, dict)
                    else str(err),
                )
                has_error = True
                continue

            self.logger.info(
                "Sent Keybase notification to %s.",
                channel.get("name"),
            )

            # Send any file attachments to the same target
            if attach and self.attachment_support:
                for attachment in attach:
                    # Verify the attachment file is accessible
                    if not attachment:
                        self.logger.warning(
                            "Could not access Keybase attachment: %s.",
                            attachment.url(privacy=True),
                        )
                        has_error = True
                        continue

                    # Build the keybase file attach API payload
                    attach_payload = {
                        "method": "attach",
                        "params": {
                            "options": {
                                "channel": channel,
                                "filename": attachment.path,
                                "title": attachment.name,
                            },
                        },
                    }

                    self.logger.debug(
                        "Keybase attachment: %s",
                        attachment.url(privacy=True),
                    )

                    # Throttle before each service call
                    self.throttle()

                    # Dispatch to the appropriate transport
                    try:
                        response = (
                            self._send_socket(attach_payload)
                            if self.mode == KeybaseMode.SOCKET
                            else self._send_tcp(attach_payload)
                        )

                    except OSError as exc:
                        self.logger.warning(
                            "Keybase %s attachment error for %s: %s",
                            self.mode,
                            channel.get("name"),
                            exc,
                        )
                        has_error = True
                        continue

                    # Check for API-level errors in the response
                    if "error" in response:
                        err = response["error"]
                        self.logger.warning(
                            "Keybase API attachment error for %s: %s",
                            channel.get("name"),
                            err.get("message", "unknown")
                            if isinstance(err, dict)
                            else str(err),
                        )
                        has_error = True
                        continue

                    self.logger.info(
                        "Sent Keybase attachment (%s) to %s.",
                        attachment.name,
                        channel.get("name"),
                    )

        return not has_error

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Collect any extra URL parameters
        params = self.url_parameters(privacy=privacy, *args, **kwargs)

        # Include the signing key when set
        if self.sigkey:
            params["sigkey"] = self.pprint(
                self.sigkey,
                privacy=privacy,
                mode=PrivacyMode.Secret,
                safe="",
            )

        # Always emit the mode so generated URLs are self-documenting
        params["mode"] = self.mode

        # Include the socket path only when it differs from the
        # auto-detected platform default (socket mode only)
        if (
            self.mode == KeybaseMode.SOCKET
            and self.socket_path != keybase_default_socket()
        ):
            params["socket"] = self.socket_path

        # Build the ordered target path segments
        parts = []
        for target in self.targets:
            kind = target[0]
            if kind == "user":
                _, username = target
                # Re-add the @ prefix; safe-quote for URL path
                parts.append("@" + NotifyKeybase.quote(username, safe=""))
            else:
                _, team, channel = target
                if channel == KEYBASE_DEFAULT_CHANNEL:
                    parts.append(NotifyKeybase.quote(team, safe=""))

                else:
                    # Encode # as %23 so it survives URL round-trip
                    parts.append(
                        NotifyKeybase.quote(team, safe="")
                        + "%23"
                        + NotifyKeybase.quote(channel, safe="")
                    )

        # Append any invalid targets unchanged for round-trip preservation
        for raw in self._invalid_targets:
            parts.append(NotifyKeybase.quote(raw, safe=""))

        # TCP mode: emit real host:port in the URL authority
        if self.mode == KeybaseMode.TCP:
            return "{schema}://{host}:{port}/{targets}?{params}".format(
                schema=self.protocol,
                host=self.host,
                port=self.port,
                targets="/".join(parts),
                params=NotifyKeybase.urlencode(params),
            )

        # Socket mode: use _ as a placeholder host
        return "{schema}://_/{targets}?{params}".format(
            schema=self.protocol,
            targets="/".join(parts),
            params=NotifyKeybase.urlencode(params),
        )

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments that can allow
        us to re-instantiate this object."""

        # Pre-encode any bare '#' in the URL path to '%23' so that
        # 'teamname#channel' is treated identically to
        # 'teamname%23channel'.  A literal '#' in a URL is the fragment
        # separator; without this step the channel name would be silently
        # discarded by the underlying URL parser.  Only the path portion
        # is affected -- split on '?' first so query-string values are
        # left untouched.
        _q = url.find("?")
        if _q >= 0:
            url = url[:_q].replace("#", "%23") + url[_q:]

        else:
            url = url.replace("#", "%23")

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # Collect all target strings
        targets = []

        # Extract the host field and port
        host = NotifyKeybase.unquote(results.get("host") or "")
        port = results.get("port")

        # The host is a notification target only when no port is present.
        # A port in the authority signals TCP mode; the host is then a
        # connection endpoint, not a chat target.
        if host and host != "_" and port is None:
            if results.get("user") == "":
                # @ prefix was present -> direct-message target
                targets.append("@" + host)

            else:
                # Team or bare username -> chat target
                targets.append(host)

        # Path segments carry the remaining targets
        targets += NotifyKeybase.split_path(results["fullpath"])

        # ?to= query param is an alias for targets
        if "to" in results["qsd"] and results["qsd"]["to"]:
            targets += NotifyKeybase.parse_list(results["qsd"]["to"])

        results["targets"] = targets

        # Extract the optional Saltpack signing key
        if "sigkey" in results["qsd"] and results["qsd"]["sigkey"]:
            results["sigkey"] = NotifyKeybase.unquote(results["qsd"]["sigkey"])

        # Extract the connection mode; explicit mode= wins over auto-detect
        if "mode" in results["qsd"] and results["qsd"]["mode"]:
            results["mode"] = NotifyKeybase.unquote(
                results["qsd"]["mode"]
            ).lower()

        # Extract an optional custom socket path
        if "socket" in results["qsd"] and results["qsd"]["socket"]:
            results["socket_path"] = NotifyKeybase.unquote(
                results["qsd"]["socket"]
            )

        return results

    @staticmethod
    def runtime_deps():
        """Return a tuple of top-level Python package names that this
        plugin imported as optional runtime dependencies."""
        return ("nacl",)
