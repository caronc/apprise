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

# Install terminal-notifier with Homebrew:
#    brew install terminal-notifier
#
# Apprise detects whether terminal-notifier 2.x or 3.x is installed.
# Use ?version= only when you need to override the detected version.
#
# Version 3 can diagnose notifications that do not appear:
#    terminal-notifier -diagnose
#
# Resources:
# - https://github.com/julienXX/terminal-notifier
from __future__ import annotations

import os
import platform
import re
import subprocess
from typing import Any, Optional, Union

from ..common import NotifyImageSize, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool
from .base import NotifyBase

# The terminal-notifier major versions we know how to talk to
NOTIFY_MACOSX_VERSIONS = ("2", "3")

# Use version 3 when detection fails.
NOTIFY_MACOSX_DEFAULT_VERSION = 3

# How long to wait for terminal-notifier to report its own version
NOTIFY_MACOSX_PROBE_TIMEOUT = 5.0

# A backstop on delivery so a wedged terminal-notifier can't hold up
# whoever called us. Posting a notification is normally instant.
NOTIFY_MACOSX_SEND_TIMEOUT = 30.0

# Extract the major version from output such as 'terminal-notifier 3.1.0.'
NOTIFY_MACOSX_VERSION_RE = re.compile(r"(?P<major>\d+)\.\d+")

# Explain terminal-notifier failures. Version 3 added codes 2 through 6.
# See https://github.com/julienXX/terminal-notifier
MACOSX_EXIT_CODE_MAP = {
    1: "No message was provided.",
    2: "An argument could not be read.",
    3: (
        "Notifications are not authorized for terminal-notifier. Run"
        " 'terminal-notifier -diagnose' to find out why."
    ),
    4: "Could not reach the notification service; is a user logged in?",
    5: "The notification service refused the request.",
    6: "Timed out waiting for a response.",
}

# Default our global support flag
NOTIFY_MACOSX_SUPPORT_ENABLED = False


if platform.system() == "Darwin":
    # Check this is Mac OS X 10.8, or higher
    major, minor = platform.mac_ver()[0].split(".")[:2]

    # Enable the plugin on supported macOS versions.
    NOTIFY_MACOSX_SUPPORT_ENABLED = int(major) > 10 or (
        int(major) == 10 and int(minor) >= 8
    )


class NotifyMacOSX(NotifyBase):
    """Send macOS notifications through terminal-notifier.

    Source: https://github.com/julienXX/terminal-notifier
    """

    # Set our global enabled flag
    enabled = NOTIFY_MACOSX_SUPPORT_ENABLED

    requirements = {
        # Define our required packaging in order to work
        "details": _(
            "Only works with Mac OS X 10.8 and higher. Additionally "
            " requires that /usr/local/bin/terminal-notifier is locally "
            "accessible."
        )
    }

    # The default descriptive name associated with the Notification
    service_name = _("MacOSX Notification")

    # The services URL
    service_url = "https://github.com/julienXX/terminal-notifier"

    # The default protocol
    protocol = "macosx"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/macosx/"

    # Allows the user to specify the NotifyImageSize object
    image_size = NotifyImageSize.XY_128

    # Disable throttle rate for MacOSX requests since they are normally
    # local anyway
    request_rate_per_sec = 0

    # Limit notifications to 10 lines so they remain readable.
    body_max_line_count = 10

    # macosx:// URLs do not contain enough detail for a unique identifier.
    url_identifier = False

    # The possible paths to the terminal-notifier
    notify_paths = (
        "/opt/homebrew/bin/terminal-notifier",
        "/usr/local/bin/terminal-notifier",
        "/usr/bin/terminal-notifier",
        "/bin/terminal-notifier",
        "/opt/local/bin/terminal-notifier",
    )

    # Define object templates
    templates = ("{schema}://",)

    # Define our template arguments
    template_args = dict(
        NotifyBase.template_args,
        **{
            "image": {
                "name": _("Include Image"),
                "type": "bool",
                "default": True,
                "map_to": "include_image",
            },
            # Play the NAME sound when the notification appears.
            # Sound names are listed in Sound Preferences.
            # Use 'default' for the default sound.
            "sound": {
                "name": _("Sound"),
                "type": "string",
            },
            "click": {
                "name": _("Open/Click URL"),
                "type": "string",
            },
            # Detect the terminal-notifier version when this is omitted.
            "version": {
                "name": _("Terminal-Notifier Version"),
                "type": "choice:string",
                "values": NOTIFY_MACOSX_VERSIONS,
            },
            # Version 2 only; defaults to app_id when omitted.
            "sender": {
                "name": _("Sender"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        sound: Optional[str] = None,
        include_image: bool = True,
        click: Optional[str] = None,
        sender: Optional[str] = None,
        version: Optional[Union[str, int]] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize MacOSX Object."""

        super().__init__(**kwargs)

        # Track whether we want to add an image to the notification.
        self.include_image = include_image

        # Acquire the path to the `terminal-notifier` program.
        self.notify_path = next(  # pragma: no branch
            (p for p in self.notify_paths if os.access(p, os.X_OK)), None
        )

        # Open this URL when the notification is clicked.
        self.click = click

        # Play this sound when the notification appears.
        self.sound = sound

        # Version 2 uses app_id when no sender is given.
        self.sender = sender

        # None means the installed version will be detected when first needed.
        self.version = None

        # Cache the detected version for later notifications.
        self.__detected_version = None

        if version is not None:
            try:
                self.version = int(version)

            except (TypeError, ValueError):
                self.version = None

            if self.version not in (2, 3):
                msg = (
                    "The MacOSX terminal-notifier version specified "
                    "({}) is invalid.".format(version)
                )
                self.logger.warning(msg)
                raise AppriseImproperlyConfigured(msg)

    @property
    def tn_version(self) -> int:
        """Return the selected or detected terminal-notifier major version.

        Automatic detection runs only once per instance.
        """
        if self.version:
            return self.version

        if self.__detected_version is None:
            self.__detected_version = self.__probe_version()

        return self.__detected_version

    def __probe_version(self) -> int:
        """Detect the installed version with `-version`.

        Fall back to the current supported release when detection fails.
        """
        try:
            response = subprocess.run(
                [self.notify_path, "-version"],
                capture_output=True,
                timeout=NOTIFY_MACOSX_PROBE_TIMEOUT,
                check=False,
            )
            if response.returncode == 0:
                # Only a clean exit tells us anything reliable.
                result = NOTIFY_MACOSX_VERSION_RE.search(
                    response.stdout.decode("utf-8", errors="ignore")
                )
                if result:
                    # Versions before 3 use the older command options.
                    return 2 if int(result.group("major")) < 3 else 3

        except (OSError, ValueError, subprocess.SubprocessError) as e:
            self.logger.warning(
                "Could not determine the MacOSX terminal-notifier version."
            )
            self.logger.debug("MacOSX Exception: %s", str(e))

        # Use the current supported release if detection produced no version.
        return NOTIFY_MACOSX_DEFAULT_VERSION

    @staticmethod
    def escape(value: str) -> str:
        """Escape a value so terminal-notifier reads it as plain text.

        A leading backslash prevents its settings parser from mistaking the
        value for structured data. terminal-notifier removes the backslash.
        """
        return f"\\{value}"

    def send(
        self,
        body: str,
        title: str = "",
        notify_type: NotifyType = NotifyType.INFO,
        **kwargs: Any,
    ) -> bool:
        """Perform MacOSX Notification."""

        if not (self.notify_path and os.access(self.notify_path, os.X_OK)):
            self.logger.warning(
                "MacOSX Notifications requires one of the following to "
                "be in place: '{}'.".format("', '".join(self.notify_paths))
            )
            return False

        # Select the command options supported by the installed version.
        version = self.tn_version

        # Start with our notification path
        cmd = [
            self.notify_path,
            "-message",
            NotifyMacOSX.escape(body),
        ]

        # Title is an optional switch
        if title:
            cmd.extend(["-title", NotifyMacOSX.escape(title)])

        if self.click:
            cmd.extend(["-open", NotifyMacOSX.escape(self.click)])

        # The sound to play
        if self.sound:
            cmd.extend(["-sound", NotifyMacOSX.escape(self.sound)])

        if version == 2:
            # Support sender.
            sender = self.sender if self.sender else self.app_id
            if sender:
                cmd.extend(["-sender", NotifyMacOSX.escape(sender)])

        # Version 2 uses the image as an icon; version 3 attaches it.
        image_path = (
            None
            if not self.include_image
            else (
                self.image_url(notify_type)
                if version == 2
                else self.image_path(notify_type)
            )
        )
        if image_path:
            cmd.extend(
                [
                    "-appIcon" if version == 2 else "-contentImage",
                    NotifyMacOSX.escape(image_path),
                ]
            )

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Capture some output for helpful debugging later on
        self.logger.debug("MacOSX CMD: {}".format(" ".join(cmd)))

        # Send our notification
        try:
            response = subprocess.run(
                cmd,
                capture_output=True,
                timeout=NOTIFY_MACOSX_SEND_TIMEOUT,
                check=False,
            )

        except (OSError, subprocess.SubprocessError) as e:
            # The program can still vanish or wedge after our access check
            self.logger.warning("Failed to run the MacOSX terminal-notifier.")
            self.logger.debug("MacOSX Exception: %s", str(e))
            return False

        if response.returncode:
            # Translate known exit codes into useful messages.
            self.logger.warning(
                "Failed to send MacOSX notification: %s",
                MACOSX_EXIT_CODE_MAP.get(
                    response.returncode,
                    f"terminal-notifier returned {response.returncode}.",
                ),
            )
            self.logger.debug(
                "MacOSX Response: %s",
                response.stderr.decode("utf-8", errors="ignore").strip(),
            )
            return False

        self.logger.info("Sent MacOSX notification.")
        return True

    def url(self, privacy: bool = False, *args: Any, **kwargs: Any) -> str:
        """Returns the URL built dynamically based on specified arguments."""

        # Add options that must be preserved in the generated URL.
        params = {
            "image": "yes" if self.include_image else "no",
        }

        if self.version:
            # Preserve only an explicit override; otherwise detect it again.
            params["version"] = str(self.version)

        if self.click:
            params["click"] = self.click

        if self.sender:
            params["sender"] = self.sender

        # Extend our parameters
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        if self.sound:
            # Store our sound
            params["sound"] = self.sound

        return f"{self.protocol}://_/?{NotifyMacOSX.urlencode(params)}"

    @staticmethod
    def parse_url(url: str) -> Optional[dict[str, Any]]:
        """Parse a macosx:// URL and its optional query parameters."""

        results = NotifyBase.parse_url(url, verify_host=False)

        # Include images with our message
        results["include_image"] = parse_bool(
            results["qsd"].get("image", True)
        )

        # Support 'click'
        if "click" in results["qsd"] and len(results["qsd"]["click"]):
            results["click"] = NotifyMacOSX.unquote(results["qsd"]["click"])

        # Support 'sound'
        if "sound" in results["qsd"] and len(results["qsd"]["sound"]):
            results["sound"] = NotifyMacOSX.unquote(results["qsd"]["sound"])

        # Support 'sender'
        if "sender" in results["qsd"] and len(results["qsd"]["sender"]):
            results["sender"] = NotifyMacOSX.unquote(results["qsd"]["sender"])

        # Support 'version'
        if "version" in results["qsd"] and len(results["qsd"]["version"]):
            results["version"] = NotifyMacOSX.unquote(
                results["qsd"]["version"]
            )

        return results
