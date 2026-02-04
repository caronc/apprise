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

"""XMPP Notifications"""

from __future__ import annotations

import re
from typing import Any, Optional

from ...common import NotifyType
from ...locale import gettext_lazy as _
from ...url import PrivacyMode
from ...utils.parse import parse_list
from ..base import NotifyBase
from .adapter import (
    SLIXMPP_SUPPORT_AVAILABLE,
    SlixmppAdapter,
    XMPPConfig,
)
from .common import SECURE_MODES, SecureXMPPMode

# A pragmatic, "hardened" JID validator intended for Apprise URLs.
#
# - Supports: local@domain and local@domain/resource
# - Rejects whitespace anywhere
# - Rejects missing local or domain
# - Rejects '@' in the domain component
#
# This does not try to fully implement RFC 7622. The goal is to catch bad
# inputs early and reliably while still supporting common JID patterns.
IS_JID = re.compile(
    r"^\s*(?P<local>[^@\s/]+)((@|%40)"
    r"(?P<domain>[^@\s/]+))?(?:(/|%2F)(?P<resource>[^%/\s]+)((/|%2F).*)?)?\s*$"
)


class NotifyXMPP(NotifyBase):
    """Send notifications via XMPP using Slixmpp."""

    # Set our global enabled flag
    enabled = SLIXMPP_SUPPORT_AVAILABLE

    requirements = {
        # Define our required packaging in order to work
        "packages_required": "slixmpp >= 1.10.0"
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
                "name": _("User"),
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
            "mode": {
                "name": _("Secure Mode"),
                "type": "choice:string",
                "values": SECURE_MODES,
                "default": SecureXMPPMode.STARTTLS,
                "map_to": "secure_mode",
            },
        },
    )

    def __init__(
        self,
        targets: Optional[list[str]] = None,
        secure_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        # The base class sets `self.secure` based on the schema.
        self.secure = bool(getattr(self, "secure", False))

        try:
            self.jid = self.normalize_jid(self.user or "", self.host)

        except ValueError:
            msg = f"An invalid XMPP JID ({self.user}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        self.targets: list[str] = []
        for target in parse_list(targets):
            try:
                jid = self.normalize_jid(target or "", self.host)

            except ValueError:
                self.logger.warning(
                    "Dropped invalid XMPP target (%s).", target)
                continue
            self.targets.append(jid)

        if isinstance(secure_mode, str) and secure_mode.strip():
            self.secure_mode = secure_mode.strip().lower()
            self.secure_mode = next(
                (k for k in SECURE_MODES
                 if k.startswith(self.secure_mode)), None
            )
            if self.secure_mode not in SECURE_MODES:
                msg = (
                    "The XMPP secure mode specified "
                    f"({secure_mode}) is invalid.")
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            self.secure_mode = (
                SecureXMPPMode.NONE
                if not self.secure
                else self.template_args["mode"]["default"]
            )

    @property
    def url_identifier(self) -> tuple[str, str, str, str, int | None]:
        """Return the pieces that uniquely identify this configuration."""
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.host, self.user, self.password, self.port,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Return the URL representation of this notification."""

        # Initialize our parameters
        params = {
            "mode": self.secure_mode
        }

        # Extend our parameters
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

        # Targets can contain '/' as a resource separator, so ensure it is
        # always percent-encoded in the path (otherwise Apprise will split it).
        targets = "/".join(self.quote(t, safe="") for t in self.targets)

        return "{schema}://{auth}{host}{port}/{targets}?{params}".format(
            schema=schema,
            auth=auth,
            host=self.host,
            port=port_str,
            targets=targets,
            params=self.urlencode(params),
        )

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

        config = XMPPConfig(
            jid=self.jid,
            password=self.password or "",
            host=self.host,
            port=self.port if self.port else default_port,
            secure=self.secure_mode,
            verify_certificate=self.verify_certificate,
        )

        self.logger.debug(
            "XMPP init: jid=%s host=%s port=%d mode=%s "
            "verify_certificate=%s targets=%s",
            self.jid,
            config.host,
            config.port,
            config.secure,
            config.verify_certificate,
            self.targets,
        )

        adapter = SlixmppAdapter(
            config=config,
            targets=self.targets,
            subject=title,
            body=body,
            timeout=self.socket_connect_timeout,
        )

        return adapter.process()

    @staticmethod
    def normalize_jid(value: str, default_host: str) -> str:
        """Normalize and validate a JID.

        Behaviour:
        - If value is 'user' then it becomes 'user@default_host'.
        - If value is 'user@host' then it becomes 'user@host'.
        - If value is 'user@host/resource' then it becomes
           'user@host/resource'.
        - If value is 'user/resource' then it becomes
           'user@default_host/resource'.
        - If value already contains '@', it is used as-is, including an
           optional '/resource' suffix.
        """
        raw = (value or "").strip()
        if not raw:
            raise ValueError("Empty JID")

        results = IS_JID.match(value)
        if not results:
            raise ValueError("Invalid JID")

        host = default_host \
            if not results.group("domain") else results.group("domain")

        jid = f"{results.group('local')}@{host}"
        if results.group("resource"):
            jid = f"{jid}/{results.group('resource')}"

        return jid

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse an XMPP URL into constructor arguments."""
        results = NotifyBase.parse_url(url)
        if not results:
            return None

        # Targets from path
        results["targets"] = [
            NotifyXMPP.unquote(t)
            for t in NotifyXMPP.split_path(results.get("fullpath"))]

        qd = results.get("qsd", {})

        # Support to= alias
        if "to" in qd and qd.get("to"):
            results["targets"] += NotifyXMPP.parse_list(
                NotifyXMPP.unquote(qd.get("to"))
            )

        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            # Extract the secure mode to over-ride the default
            results["secure_mode"] = results["qsd"]["mode"].lower()

        return results
