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

import os
import platform
import subprocess

from ..common import NotifyImageSize, NotifyType
from ..exception import AppriseImproperlyConfigured
from ..locale import gettext_lazy as _
from ..utils.parse import parse_bool
from .base import NotifyBase

# The terminal-notifier major versions we know how to talk to
NOTIFY_MACOSX_VERSIONS = ("2", "3")

# Default version of terminal-notifier to use if not specified by the user.
# This is detected at runtime based on the macOS version otherwise.
NOTIFY_MACOSX_DEFAULT_VERSION = 2

# Default our global support flag
NOTIFY_MACOSX_SUPPORT_ENABLED = False


if platform.system() == "Darwin":
    # Check this is Mac OS X 10.8, or higher
    major, minor = platform.mac_ver()[0].split(".")[:2]

    # Toggle our enabled flag, if version is correct and executable
    # found. This is done in such a way to provide verbosity to the
    # end user, so they know why it may or may not work for them.
    NOTIFY_MACOSX_SUPPORT_ENABLED = int(major) > 10 or (
        int(major) == 10 and int(minor) >= 8
    )

    # macOS 26 (Tahoe) is the first release contemporaneous with
    # terminal-notifier 3.0
    if int(major) >= 26:
        NOTIFY_MACOSX_DEFAULT_VERSION = 3


class NotifyMacOSX(NotifyBase):
    """A wrapper for the MacOS X terminal-notifier tool.

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

    # Limit results to just the first 10 line otherwise there is just to much
    # content to display
    body_max_line_count = 10

    # No URL Identifier will be defined for this service as there simply isn't
    # enough details to uniquely identify one dbus:// from another.
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
            # terminal-notifier version
            "version": {
                "name": _("Terminal-Notifier Version"),
                "type": "choice:string",
                "values": NOTIFY_MACOSX_VERSIONS,
                "default": str(NOTIFY_MACOSX_DEFAULT_VERSION),
            },
            # Only applies to terminal-notifier 2.x (see `version=`);
            # defaults to our app_id when not explicitly set
            "sender": {
                "name": _("Sender"),
                "type": "string",
            },
        },
    )

    def __init__(
        self,
        sound=None,
        include_image=True,
        click=None,
        sender=None,
        version=None,
        **kwargs,
    ):
        """Initialize MacOSX Object."""

        super().__init__(**kwargs)

        # Track whether we want to add an image to the notification.
        self.include_image = include_image

        # Acquire the path to the `terminal-notifier` program.
        self.notify_path = next(  # pragma: no branch
            (p for p in self.notify_paths if os.access(p, os.X_OK)), None
        )

        # Click URL
        # Allow user to provide the `--open` argument on the notify wrapper
        self.click = click

        # Set sound object (no q/a for now)
        self.sound = sound

        # Some builds require a sender to display notifications; if
        # unset we fall back to our own app_id at send time
        self.sender = sender

        # Set the terminal-notifier version to use.
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

        else:
            self.version = NOTIFY_MACOSX_DEFAULT_VERSION

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform MacOSX Notification."""

        if not (self.notify_path and os.access(self.notify_path, os.X_OK)):
            self.logger.warning(
                "MacOSX Notifications requires one of the following to "
                "be in place: '{}'.".format("', '".join(self.notify_paths))
            )
            return False

        # Start with our notification path
        cmd = [
            self.notify_path,
            "-message",
            body,
        ]

        # Title is an optional switch
        if title:
            cmd.extend(["-title", title])

        if self.click:
            cmd.extend(["-open", self.click])

        # The sound to play
        if self.sound:
            cmd.extend(["-sound", self.sound])

        if self.version == 2:
            # Support sender.
            sender = self.sender if self.sender else self.app_id
            if sender:
                cmd.extend(["-sender", sender])

        # Support any defined images if set
        image_path = (
            None if not self.include_image else self.image_url(notify_type)
        )
        if image_path and self.version == 2:
            cmd.extend(["-appIcon", image_path])

        # Always call throttle before any remote server i/o is made
        self.throttle()

        # Capture some output for helpful debugging later on
        self.logger.debug("MacOSX CMD: {}".format(" ".join(cmd)))

        # Send our notification
        output = subprocess.Popen(cmd)

        # Wait for process to complete
        output.wait()

        if output.returncode:
            self.logger.warning("Failed to send MacOSX notification.")
            self.logger.debug(
                "MacOSX notification command exited with code %s.",
                output.returncode,
            )
            return False

        self.logger.info("Sent MacOSX notification.")
        return True

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        # Define any URL parametrs
        params = {
            "image": "yes" if self.include_image else "no",
            "version": str(self.version),
        }

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
    def parse_url(url):
        """There are no parameters nessisary for this protocol; simply having
        gnome:// is all you need.

        This function just makes sure that is in place.
        """

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
