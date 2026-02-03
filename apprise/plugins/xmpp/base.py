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

"""XMPP Notifications.

This is intentionally minimal:
- One connection per notification send.
- No exposed XEP/plugin flags.
- Targets are JIDs provided in the path (and via to=).

Notes about JIDs in paths:
- XMPP resources use '/', which is also the Apprise path separator.
- If you need to target a resource, percent-encode the slash as '%2F'.
  Example: xmpp://user:pass@host/alice@example.com%2Fphone

"""

from __future__ import annotations

import re
from typing import Any, Optional

from ...common import NotifyType
from ...locale import gettext_lazy as _
from ...url import PrivacyMode
from ...utils.parse import parse_bool, parse_list
from ..base import NotifyBase
from .adapter import (
    SLIXMPP_SUPPORT_AVAILABLE,
    SlixmppSendOnceAdapter,
    XMPPConfig,
)

# Basic, intentionally permissive JID check:
# - no whitespace
# - must contain at least one non-separator character
IS_JID = re.compile(r"^[^\s]+$")


class NotifyXMPP(NotifyBase):
    """Send notifications via XMPP using Slixmpp."""

    # Set our global enabled flag
    enabled = SLIXMPP_SUPPORT_AVAILABLE

    requirements = {
        # Define our required packaging in order to work
        "packages_required": "slixmpp"
    }

    # The default descriptive name associated with the Notification
    service_name = "XMPP"

    # The services URL
    service_url = "https://xmpp.org/"

    # The default insecure protocol
    protocol = "xmpp"

    # The default secure protocol
    secure_protocol = "xmpps"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/xmpp/"

    # Default Ports
    default_insecure_port = 5222
    default_secure_port = 5223

    templates = (
        "{schema}://{user}:{password}@{host}",
        "{schema}://{user}:{password}@{host}:{port}",
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
                "name": _("JID"),
                "type": "string",
                "required": True,
            },
            "password": {
                "name": _("Password"),
                "type": "string",
                "private": True,
                "required": True,
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
            "to": {"alias_of": "targets"},
            "verify": {
                "name": _("Verify Certificate"),
                "type": "bool",
                "default": True,
                "map_to": "verify_certificate",
            },
        },
    )

    def __init__(
        self,
        targets: Optional[list[str]] = None,
        verify_certificate: bool | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        # The base class sets `self.secure` based on the schema.
        self.secure = bool(getattr(self, "secure", False))

        # Verify certificate controls TLS validation in secure mode.
        if verify_certificate is None:
            verify_certificate = self.template_args["verify"]["default"]
        self.verify_certificate = parse_bool(verify_certificate)

        # Apprise gives us user/password/host/port already.
        # For XMPP, user is the sender JID.
        user = (self.user or "").strip()
        # Apprise URLs split the JID across user@host. If the user part
        # does not contain "@", then infer the domain from host.
        self.jid = user if "@" in user else f"{user}@{self.host}"
        if not self.jid or not IS_JID.match(self.jid):
            msg = f"An invalid XMPP JID ({self.user}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg)

        self.targets: list[str] = []
        for target in parse_list(targets):
            jid = (target or "").strip()
            if not jid or not IS_JID.match(jid):
                self.logger.warning(
                    "Dropped invalid XMPP target (%s).", target)
                continue
            self.targets.append(jid)

    def __len__(self) -> int:
        """Return the number of outbound connections this config performs."""
        return max(1, len(self.targets) if self.targets else 1)

    @property
    def url_identifier(self) -> tuple[str, str, str, str, int | None]:
        """Return the pieces that uniquely identify this configuration."""
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.host, self.user, self.password, self.port,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Return the URL representation of this notification."""
        params: dict[str, Any] = {
            "verify": self.verify_certificate,
        }
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        auth = "{user}:{password}@".format(
            user=self.quote(self.jid, safe=""),
            password=self.pprint(
                self.password,
                privacy,
                mode=PrivacyMode.Secret,
                safe="",
            ),
        )

        default_port = (
            self.default_secure_port
            if self.secure
            else self.default_insecure_port
        )

        port = self.port if isinstance(self.port, int) else default_port
        port_str = "" if port == default_port else f":{port}"

        schema = self.secure_protocol if self.secure else self.protocol
        targets = "/".join(self.quote(t, safe="") for t in self.targets)

        query = self.urlencode(params)
        base = "{schema}://{auth}{host}{port}".format(
            schema=schema,
            auth=auth,
            host=self.host,
            port=port_str,
        )

        if targets:
            base = f"{base}/{targets}"

        return base if not query else f"{base}?{query}"

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Send a notification to one or more XMPP targets."""

        default_port = (
            self.default_secure_port
            if self.secure
            else self.default_insecure_port
        )

        self.throttle()

        cfg = XMPPConfig(
            jid=self.jid,
            password=self.password or "",
            host=self.host,
            port=self.port if self.port else default_port,
            secure=self.secure,
            verify_certificate=self.verify_certificate,
        )

        adapter = SlixmppSendOnceAdapter(
            config=cfg,
            targets=list(self.targets),
            body=body,
            subject=title,
            timeout=self.socket_connect_timeout,
            before_message=None,
            logger=self.logger,
        )

        return adapter.process()

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse an XMPP URL into constructor arguments."""
        results = NotifyBase.parse_url(url)
        if not results:
            return None

        # Targets from path
        results["targets"] = NotifyXMPP.split_path(results.get("fullpath"))

        qd = results.get("qsd", {})

        # Support to= alias
        if "to" in qd and qd.get("to"):
            results["targets"] += NotifyXMPP.parse_list(
                NotifyXMPP.unquote(qd.get("to"))
            )

        # verify=
        if "verify" in qd:
            results["verify_certificate"] = parse_bool(qd.get("verify"))

        return results
