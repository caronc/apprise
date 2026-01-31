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

"""IRC Notifications.

This is simplified IRC client designed for notification delivery.
It focuses on reliability and predictable behaviour, not full IRC features.

URL formats (examples):
  - irc://hostname/#channel/@user
  - irc://user@hostname/#channel
  - irc://user:password@hostname/#channel
  - ircs://hostname/#channel  (TLS, default port 6697)

Targets:
  - Channels are specified as #channel
  - Users are specified as @nickname
"""

from __future__ import annotations

from itertools import chain
import re
from typing import Any, Optional

from ...common import NotifyType
from ...locale import gettext_lazy as _
from ...url import PrivacyMode
from ...utils.parse import parse_bool, parse_list
from ...utils.socket import AppriseSocketError
from ..base import NotifyBase
from . import templates
from .client import IRCClient
from .protocol import IRC_AUTH_MODES, IRCAuthMode, normalise_channel

IS_USER = re.compile(r"^\s*(@|%40)?(?P<user>[^ \t\r\n@#]+)$", re.I)

IS_CHANNEL = re.compile(
    r"^\s*(#|%23)"
    r"(?P<channel>[^ \t\r\n@#:]+)"
    r"(?::(?P<key>[^ \t\r\n]+))?\s*$",
    re.I,
)


class NotifyIRC(NotifyBase):
    """A wrapper to IRC servers using TCP or TLS."""

    # The default descriptive name associated with the Notification
    service_name = "IRC"

    # The services URL
    service_url = "https://ircv3.net/"

    # The default insecure protocol
    protocol = "irc"

    # The default secure protocol
    secure_protocol = "ircs"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/irc/"

    # RFC 2812 maximum IRC message length is 512 bytes including CRLF.
    # Keep a conservative payload budget to accommodate prefix overhead.
    body_maxlen = 380

    # IRC is not fast... there is a lot of handshaking tht takes place
    # between us and the remote server. During development of this plugin
    # it took on average 18-22s to register with #EFnet; setting the value
    # to 30.0s to be conservative with others as their milage may vary
    irc_register_timeout = 30.0

    # Avoid flooding
    request_rate_per_sec = 0.02

    # Title is prepended to body
    title_maxlen = 0

    templates = (
        "{schema}://{host}/{targets}",
        "{schema}://{host}:{port}/{targets}",
        "{schema}://{user}@{host}/{targets}",
        "{schema}://{user}@{host}:{port}/{targets}",
        "{schema}://{user}:{password}@{host}/{targets}",
        "{schema}://{user}:{password}@{host}:{port}/{targets}",
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
                "name": _("User"),
                "type": "string",
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
            },
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "prefix": "@",
                "map_to": "targets",
            },
            "target_channel": {
                "name": _("Target Channel"),
                "type": "string",
                "prefix": "#",
                "map_to": "targets",
            },
            "targets": {
                "name": _("Targets"),
                "type": "list:string",
            },
        },
    )

    template_args = dict(
        NotifyBase.template_args,
        **{
            "to": {"name": _("Targets"), "type": "list:string"},
            "name": {"name": _("Real Name"), "type": "string"},
            "nick": {"name": _("Nickname"), "type": "string"},
            "join": {
                "name": _("Join Channels"),
                "type": "bool",
                "default": True,
            },
            "mode": {
                "name": _("Auth Mode"),
                "type": "choice:string",
                "values": IRC_AUTH_MODES,
                "default": IRCAuthMode.SERVER,
            },
        },
    )

    def __init__(
        self,
        targets: Optional[list[str]] = None,
        name: Optional[str] = None,
        join: Optional[bool] = None,
        nick: Optional[str] = None,
        mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:

        super().__init__(**kwargs)

        # Join Channel
        self.join = (
            parse_bool(join, self.template_args["join"]["default"])
            if join is not None
            else self.template_args["join"]["default"]
        )

        self.nickname = (nick or "").strip() or (self.user or "").strip()

        # Initialized value
        self.auth_mode = IRCAuthMode.SERVER

        # Apply template defaults only where the user did not supply values
        self.apply_irc_defaults(**kwargs)

        if isinstance(mode, str) and not mode.strip():
            requested = mode.strip().lower()
            matches = tuple(
                m for m in IRC_AUTH_MODES if m.startswith(requested))
            if len(matches) == 1:
                self.auth_mode = matches[0]

            else:
                msg = f"The IRC auth mode specified ({mode}) is invalid."
                self.logger.warning(msg)
                raise TypeError(msg)

        self.fullname = (name or "").strip()

        # For storing our channels and users to message
        self.channels: dict[str, Optional[str]] = {}
        self.users: list[str] = []

        # Set our timeouts
        srt = float(self.socket_read_timeout or 0.0)
        self.join_timeout = max(6.0, min(12.0, srt or 6.0))
        self.send_timeout = max(4.0, min(10.0, srt or 4.0))

        # Identify our targets
        self.targets = []
        for target in parse_list(targets):
            match = IS_CHANNEL.match(target)
            if match:
                channel = match.group("channel")
                key = match.group("key")
                self.channels[channel] = key
                continue

            match = IS_USER.match(target)
            if match:
                self.users.append(match.group("user"))
                continue

            self.logger.warning("Dropped invalid IRC target (%s).", target)

    def apply_irc_defaults(self, port=None, **kwargs):
        """
        A function that prefills defaults based on the irc details
        provided.
        """
        if self.port:
            # IRC Port was explicitly specified, therefore it is assumed
            # the caller knows what he's doing and is intentionally
            # over-riding any smarts to be applied. We also can not apply
            # any default if there was no user specified.
            return

        for i in range(len(templates.IRC_TEMPLATES)):  # pragma: no branch
            self.logger.trace(
                "Scanning %s against %s",
                self.host, templates.IRC_TEMPLATES[i][0])

            match = templates.IRC_TEMPLATES[i][1].match(self.host)
            if match:
                self.logger.info(
                    f"Applying {templates.IRC_TEMPLATES[i][0]} Defaults")

                # the secure flag can not be altered if defined in the template
                self.secure = templates.IRC_TEMPLATES[i][2].get(
                    "secure", self.secure,
                )

                # store default port
                self.port = templates.IRC_TEMPLATES[i][2].get(
                    "port", self.port,
                )

                self.auth_mode = templates.IRC_TEMPLATES[i][2].get(
                    "mode", self.auth_mode,
                )
                break

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        attach: Any = None,
        **kwargs: Any,
    ) -> bool:
        """Send a notification to IRC targets."""

        if not (self.channels or self.users):
            self.logger.warning("No IRC targets specified.")
            return False

        # prepare ourselves a nickname
        nickname = self.nickname or IRCClient.nick_generation(
            prefix=self.app_id,
        )

        self.throttle()

        client = IRCClient(
            host=self.host,
            nickname=nickname,
            fullname=self.fullname or self.app_desc,
            port=self.port,
            secure=self.secure,
            verify=self.verify_certificate,
            timeout=self.socket_read_timeout,
            password=self.password,
            auth_mode=self.auth_mode,
            nick_generator=IRCClient.nick_generation,
        )

        try:
            client.connect()
            client.register(
                timeout=self.irc_register_timeout,
                prefix=self.app_id,
            )

            message = body if not title else f"{title} {body}".strip()

            for c, key in self.channels.items():
                chan = normalise_channel(c)
                if self.join or key:
                    client.join(
                        channel=chan,
                        key=key,
                        timeout=self.join_timeout,
                        prefix=self.app_id,
                    )

                client.privmsg(
                    target=chan,
                    message=message,
                    timeout=self.send_timeout,
                )
                self.logger.info(
                    "Sent IRC notification to #%s as %s",
                    c,
                    client.nickname,
                )

            for u in self.users:
                target = u.lstrip("@")
                client.privmsg(
                    target=target,
                    message=message,
                    timeout=self.send_timeout,
                )
                self.logger.info(
                    "Sent IRC notification to @%s as %s",
                    u,
                    client.nickname,
                )

            client.quit(message=self.app_desc, timeout=self.send_timeout)
            return True

        except (AppriseSocketError, OSError, TimeoutError) as e:
            self.logger.warning(
                "Failed to send IRC notification to %s as %s.",
                self.host,
                nickname,
            )
            self.logger.debug("IRC Exception: %s", e)
            return False

        finally:
            client.close()

    @property
    def url_identifier(
            self) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
        """Return the pieces that uniquely identify this configuration."""
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.host,
            self.user,
            self.password,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Return the URL representation of this notification."""
        params: dict[str, Any] = {
            "verify": self.verify_certificate,
            "join": self.join,
        }

        if self.auth_mode and self.auth_mode != IRCAuthMode.SERVER:
            params["mode"] = self.auth_mode

        if self.fullname:
            params["name"] = self.fullname

        if self.nickname and self.nickname != (self.user or ""):
            params["nick"] = self.nickname

        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        auth = ""
        if self.user and self.password:
            auth = "{user}:{password}@".format(
                user=self.quote(self.user, safe=""),
                password=self.pprint(
                    self.password,
                    privacy,
                    mode=PrivacyMode.Secret,
                    safe="",
                ),
            )
        elif self.user:
            auth = "{user}@".format(user=self.quote(self.user, safe=""))

        default_port = IRCClient.default_secure_port \
            if self.secure else IRCClient.default_insecure_port

        port = self.port if isinstance(self.port, int) else (
            IRCClient.default_secure_port
            if self.secure else IRCClient.default_insecure_port
        )

        port = "" if port == default_port else f":{port}"

        schema = self.secure_protocol if self.secure else self.protocol
        return "{schema}://{auth}{host}{port}/{targets}?{params}".format(
            schema=schema,
            auth=auth,
            host=self.host,
            port=port,
            targets="/".join(chain(
                [self.quote(f"#{c}" if not k else "#{}:{}".format(
                    c,
                    self.pprint(
                        k,
                        privacy,
                        mode=PrivacyMode.Secret,
                        safe="")),
                    safe="#") for c, k in self.channels.items()],
                [self.quote(f"@{u}", safe="@")
                 for u in self.users],
            )),
            params=self.urlencode(params),
        )

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse an IRC URL into constructor arguments."""
        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return None

        results["targets"] = []

        if "host" in results["qsd"] and len(results["qsd"]["host"]):
            # a host was defined which means the first entry is actually one
            # of our targets
            results["targets"].append(NotifyIRC.unquote(results["host"]))

        # Store remaining targets
        results["targets"].extend(NotifyIRC.split_path(results["fullpath"]))

        # The 'to' makes it easier to use yaml configuration
        if "to" in results["qsd"] and len(results["qsd"]["to"]):
            results["targets"] += NotifyIRC.parse_list(
                NotifyIRC.unquote(results["qsd"]["to"])
            )

        # Get Join Channel Flag
        results["join"] = parse_bool(
            results["qsd"].get(
                "join", NotifyIRC.template_args["join"]["default"]
            )
        )

        # Get our IRC Name
        if "name" in results["qsd"] and len(results["qsd"]["name"]):
            results["name"] = NotifyIRC.unquote(results["qsd"]["name"])

        if "nick" in results["qsd"] and len(results["qsd"]["nick"]):
            results["nick"] = NotifyIRC.unquote(results["qsd"]["nick"])

        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            results["mode"] = NotifyIRC.unquote(results["qsd"]["mode"])

        return results
