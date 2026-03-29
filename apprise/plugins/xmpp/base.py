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
from ...utils.parse import parse_bool, parse_list, validate_regex
from ..base import NotifyBase
from .adapter import SLIXMPP_SUPPORT_AVAILABLE, SlixmppAdapter, XMPPConfig
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
    r"^\s*(?P<is_room>#|%23)?(?P<local>[^@\s/]+)((@|%40)"
    r"(?P<domain>[^@\s/]+))?(?:(/|%2F)(?P<resource>[^%/\s]+)"
    r"((/|%2F).*)?)?\s*$"
)


class NotifyXMPP(NotifyBase):
    """Send notifications via XMPP using Slixmpp."""

    # Set our global enabled flag
    enabled = SLIXMPP_SUPPORT_AVAILABLE and SlixmppAdapter._enabled

    requirements = {
        # Define our required packaging in order to work
        "packages_required": SlixmppAdapter.package_dependency(),
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
            "target_user": {
                "name": _("Target User"),
                "type": "string",
                "map_to": "targets",
            },
            "target_channels": {
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
            "xmpp": {
                "name": _("XMPP Server"),
                "type": "string",
                "map_to": "xmpp_host",
            },
            "mode": {
                "name": _("Secure Mode"),
                "type": "choice:string",
                "values": SECURE_MODES,
                "default": SecureXMPPMode.STARTTLS,
                "map_to": "secure_mode",
            },
            "roster": {
                "name": _("Get Roster"),
                "type": "bool",
                "default": False,
            },
            "subject": {
                "name": _("Use Subject"),
                "type": "bool",
                "default": False,
            },
            "keepalive": {
                "name": _("Keep Connection Alive"),
                "type": "bool",
                "default": False,
            },
            "to": {"alias_of": "targets"},
            "name": {
                "name": _("MUC Nickname"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        targets: Optional[list[(str, str)]] = None,
        secure_mode: Optional[str] = None,
        roster: Optional[bool] = None,
        subject: Optional[bool] = None,
        keepalive: Optional[bool] = None,
        name: Optional[str] = None,
        xmpp_host: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        # xmpp_host allows the connection host to differ from the JID domain.
        # Mirrors the smtp= / smtp_host pattern in the email plugin.
        self.xmpp_host = (
            xmpp_host.strip()
            if isinstance(xmpp_host, str) and xmpp_host.strip()
            else ""
        )

        try:
            self.jid, _ = self.normalize_jid(self.user or "", self.host)

        except ValueError:
            msg = f"An invalid XMPP JID ({self.user}) was specified."
            self.logger.warning(msg)
            raise TypeError(msg) from None

        self.targets: list[(str, str)] = []
        # Flag for tracking if we want Multi-User Chat function enabled
        self.want_muc = False

        for target in parse_list(targets):
            try:
                jid, is_muc = self.normalize_jid(target or "", self.host)
                mtype = "groupchat" if is_muc else "chat"
                if is_muc:
                    self.want_muc = True

            except ValueError:
                self.logger.warning(
                    "Dropped invalid XMPP target (%s).", target
                )
                continue
            self.targets.append((mtype, jid))

        if isinstance(secure_mode, str) and secure_mode.strip():
            self.secure_mode = secure_mode.strip().lower()
            self.secure_mode = next(
                (k for k in SECURE_MODES if k.startswith(self.secure_mode)),
                None,
            )
            if self.secure_mode not in SECURE_MODES:
                msg = (
                    "The XMPP secure mode specified "
                    f"({secure_mode}) is invalid."
                )
                self.logger.warning(msg)
                raise TypeError(msg)

        else:
            self.secure_mode = (
                SecureXMPPMode.NONE
                if not self.secure
                else self.template_args["mode"]["default"]
            )

        # Prepare our roster check
        self.roster = (
            self.template_args["roster"]["default"]
            if roster is None
            else bool(roster)
        )

        self.subject = (
            self.template_args["subject"]["default"]
            if subject is None
            else bool(subject)
        )

        self.keepalive = (
            self.template_args["keepalive"]["default"]
            if keepalive is None
            else bool(keepalive)
        )

        if self.secure and self.secure_mode == SecureXMPPMode.NONE:
            self.secure_mode = self.template_args["mode"]["default"]
            self.logger.warning(
                "Ambiguous XMPP configuration: secure=True and mode=None; "
                "secure setting prevails; setting mode=%s",
                self.secure_mode,
            )

        elif not self.secure and self.secure_mode != SecureXMPPMode.NONE:
            self.logger.warning(
                "Ambiguous XMPP configuration: secure=False and mode=%s; "
                "mode setting prevails; setting secure=True",
                self.secure_mode,
            )
            self.secure = True

        # MUC nickname: alphanumeric + underscore; falls back to the JID
        # username, then the app_id as a last resort
        self.name = validate_regex(name, r"^[a-zA-Z0-9_]+$") if name else None
        if self.name is None:
            self.name = self.user or self.app_id

        # Keepalive adapter (created lazily)
        self._adapter: Optional[SlixmppAdapter] = None

    def __del__(self) -> None:
        """Best-effort close for keepalive sessions."""
        try:
            if self._adapter is not None:
                self._adapter.close()

        except Exception:
            # Never raise from __del__
            pass

    @property
    def url_identifier(self) -> tuple[str, str, str, str, Optional[int]]:
        """Return the pieces that uniquely identify this configuration."""
        return (
            self.secure_protocol if self.secure else self.protocol,
            self.host,
            self.xmpp_host,
            self.user,
            self.password,
            self.port,
        )

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Return the URL representation of this notification."""

        # Initialize our parameters
        params = {
            "mode": self.secure_mode,
            "roster": "yes" if self.roster else "no",
            "subject": "yes" if self.subject else "no",
            "keepalive": "yes" if self.keepalive else "no",
        }

        # Only include name when it differs from the default
        # (JID user / app_id)
        if self.name != (self.user or self.app_id):
            params["name"] = self.name

        if self.xmpp_host and self.xmpp_host != self.host:
            params["xmpp"] = self.xmpp_host

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

        default_port = SECURE_MODES[self.secure_mode]["default_port"]
        port = self.port if isinstance(self.port, int) else default_port
        port_str = "" if port == default_port else f":{port}"

        schema = self.secure_protocol if self.secure else self.protocol

        # Targets can contain '/' as a resource separator, so ensure it is
        # always percent-encoded in the path (otherwise Apprise will split it).
        # Use %23 for the MUC '#' prefix so it is not misread as a fragment.
        targets = "/".join(
            ("%23" if mode == "groupchat" else "") + self.quote(jid, safe="")
            for (mode, jid) in self.targets
        )

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

        default_port = SECURE_MODES[self.secure_mode]["default_port"]

        self.throttle()

        config = XMPPConfig(
            jid=self.jid,
            password=self.password or "",
            host=self.xmpp_host or self.host,
            port=self.port if self.port else default_port,
            secure=self.secure_mode,
            verify_certificate=self.verify_certificate,
        )

        self.logger.debug(
            "XMPP init: jid=%s host=%s port=%d mode=%s "
            "verify_certificate=%s subject=%s roster=%s keepalive=%s "
            "targets=%s",
            self.jid,
            config.host,
            config.port,
            config.secure,
            config.verify_certificate,
            "yes" if self.subject else "no",
            "yes" if self.roster else "no",
            "yes" if self.keepalive else "no",
            self.targets,
        )

        subject = title if self.subject else ""

        if self.keepalive and self._adapter:
            # Reuse existing adapter
            return self._adapter.send_message(
                targets=self.targets,
                subject=subject,
                body=body,
            )

        adapter_kwargs = {
            "config": config,
            "targets": self.targets,
            "subject": subject,
            "body": body,
            "timeout": self.socket_connect_timeout,
            "roster": self.roster,
            "keepalive": self.keepalive,
            "want_muc": self.want_muc,
            "default_nickname": self.name,
        }
        if not self.keepalive:
            # One-shot mode: Create, process, and discard
            return SlixmppAdapter(**adapter_kwargs).process()

        # Keepalive mode, reuse a single adapter instance
        self._adapter = SlixmppAdapter(**adapter_kwargs)
        return self._adapter.send_message()

    @property
    def title_maxlen(self) -> Optional[int]:
        """
        Depending on if the subject field is set, we can control
        how the message is constructed.
        """

        return 0 if not self.subject else super().title_maxlen

    @staticmethod
    def normalize_jid(value: str, default_host: str) -> tuple[str, bool]:
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
        results = IS_JID.match(raw)
        if not results:
            raise ValueError("Invalid JID")

        is_muc = bool(results.group("is_room"))
        host = results.group("domain") or default_host

        jid = f"{results.group('local')}@{host}"
        if results.group("resource"):
            jid = f"{jid}/{results.group('resource')}"

        return jid, is_muc

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse an XMPP URL into constructor arguments."""
        results = NotifyBase.parse_url(url)
        if not results:
            return None

        # Targets from path
        results["targets"] = [
            NotifyXMPP.unquote(t)
            for t in NotifyXMPP.split_path(results.get("fullpath"))
        ]

        qd = results.get("qsd", {})

        # Support to= alias
        if "to" in qd and qd.get("to"):
            results["targets"] += NotifyXMPP.parse_list(
                NotifyXMPP.unquote(qd.get("to"))
            )

        if "mode" in results["qsd"] and len(results["qsd"]["mode"]):
            # Extract the secure mode to over-ride the default
            results["secure_mode"] = results["qsd"]["mode"].lower()

        if "roster" in results["qsd"] and len(results["qsd"]["roster"]):
            results["roster"] = parse_bool(results["qsd"]["roster"])

        if "subject" in results["qsd"] and len(results["qsd"]["subject"]):
            results["subject"] = parse_bool(results["qsd"]["subject"])

        if "keepalive" in results["qsd"] and len(results["qsd"]["keepalive"]):
            results["keepalive"] = parse_bool(results["qsd"]["keepalive"])

        if "name" in results["qsd"] and len(results["qsd"]["name"]):
            results["name"] = NotifyXMPP.unquote(results["qsd"]["name"])

        if "xmpp" in results["qsd"] and len(results["qsd"]["xmpp"]):
            results["xmpp_host"] = NotifyXMPP.unquote(results["qsd"]["xmpp"])

        return results

    @staticmethod
    def runtime_deps():
        """Return a tuple of top-level Python package names that this plugin
        imported as optional runtime dependencies.
        """
        return ("slixmpp",)
