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

# Sources:
# - https://blink1.thingm.com/
# - https://github.com/todbot/blink1-python
# - https://github.com/todbot/blink1/blob/main/docs/blink1-hid-commands.md

import time

from ..common import NotifyType
from ..locale import gettext_lazy as _
from .base import NotifyBase

# Default our global support flag
NOTIFY_BLINK1_ENABLED = False

try:
    import hid as blink1_hid

    NOTIFY_BLINK1_ENABLED = True

except ImportError:
    # No problem -- hidapi is an optional dependency.  Users who wish to
    # use this plugin must install it:  pip install hidapi
    pass

#
# blink(1) USB HID constants
#

# USB vendor / product identifiers for all blink(1) revisions
BLINK1_VENDOR_ID = 0x27B8
BLINK1_PRODUCT_ID = 0x01ED

# HID report size (report ID byte + 8 payload bytes)
BLINK1_REPORT_ID = 0x01
BLINK1_REPORT_SIZE = 9

# Command byte: 'c' == fade to RGB with a time argument
BLINK1_CMD_FADE = ord("c")


class Blink1LED:
    """
    Defines the LED to focus on
    """

    ALL = 0
    FIRST = 1
    SECOND = 2


BLINK1_LED_CHOICES = {
    Blink1LED.ALL: "all",
    Blink1LED.FIRST: "1",
    Blink1LED.SECOND: "2",
}

# Maps inbound strings to Blink1LED constants; unknown values fall back to ALL
BLINK1_LED_MAP = {
    "0": Blink1LED.ALL,
    "all": Blink1LED.ALL,
    "a": Blink1LED.ALL,
    "1": Blink1LED.FIRST,
    "2": Blink1LED.SECOND,
}

# How long (ms) to hold the LED colour after the fade completes
BLINK1_DEFAULT_DURATION_MS = 5000
BLINK1_MIN_DURATION_MS = 0
BLINK1_MAX_DURATION_MS = 300000  # 5 minutes

# Fade transition time (ms); 0 = instant
BLINK1_DEFAULT_FADE_MS = 0
BLINK1_MIN_FADE_MS = 0
BLINK1_MAX_FADE_MS = 10000  # 10 seconds


def _blink1_fade_buf(red, green, blue, fade_ms, ledn):
    """Build the 9-byte HID feature-report buffer for a fade-to-RGB command.

    The blink(1) wire format (all values unsigned 8-bit unless noted):
      [0] REPORT_ID (0x01)
      [1] command 'c' (0x63)
      [2] red
      [3] green
      [4] blue
      [5] fade_time high byte  (fade_time = fade_ms // 10, 16-bit big-endian)
      [6] fade_time low byte
      [7] ledn (0=all, 1=LED1, 2=LED2)
      [8] 0x00 (padding)
    """
    fade_time = int(fade_ms) // 10
    th = (fade_time >> 8) & 0xFF
    tl = fade_time & 0xFF
    return [
        BLINK1_REPORT_ID,
        BLINK1_CMD_FADE,
        int(red),
        int(green),
        int(blue),
        th,
        tl,
        int(ledn),
        0x00,
    ]


class NotifyBlink1(NotifyBase):
    """A wrapper for blink(1) USB LED notifications.

    Colors are driven by Apprise's notification-type color map
    (info=blue, success=green, warning=yellow, failure=red).
    No external blink1 library is required; the USB HID wire protocol
    is implemented directly via the hidapi package.
    """

    # Set our global enabled flag
    enabled = NOTIFY_BLINK1_ENABLED

    requirements = {
        "packages_required": "hidapi",
    }

    # The default descriptive name associated with the notification
    service_name = _("blink(1)")

    # The services URL
    service_url = "https://blink1.thingm.com/"

    # The default protocol
    protocol = "blink1"

    # A URL that takes you to the setup/help of the specific protocol
    setup_url = "https://appriseit.com/services/blink1/"

    # blink(1) is a local USB device; a title field has no meaning here.
    title_maxlen = 0

    # No throttling needed for a local USB device
    request_rate_per_sec = 0

    # URL templates
    templates = (
        "{schema}://",
        "{schema}://{serial}/",
    )

    template_tokens = dict(
        NotifyBase.template_tokens,
        **{
            "serial": {
                "name": _("Serial Number"),
                "type": "string",
            },
        },
    )

    template_args = dict(
        NotifyBase.template_args,
        **{
            "duration": {
                "name": _("Duration (ms)"),
                "type": "int",
                "min": BLINK1_MIN_DURATION_MS,
                "max": BLINK1_MAX_DURATION_MS,
                "default": BLINK1_DEFAULT_DURATION_MS,
            },
            "fade": {
                "name": _("Fade Time (ms)"),
                "type": "int",
                "min": BLINK1_MIN_FADE_MS,
                "max": BLINK1_MAX_FADE_MS,
                "default": BLINK1_DEFAULT_FADE_MS,
            },
            "ledn": {
                "name": _("LED Number"),
                "type": "choice:int",
                "values": BLINK1_LED_CHOICES,
                "default": Blink1LED.ALL,
            },
        },
    )

    def __init__(
        self,
        serial=None,
        duration=None,
        fade=None,
        ledn=None,
        **kwargs,
    ):
        """Initialize Blink1 Object."""

        super().__init__(**kwargs)

        # Device serial number; None means "first available device".
        # An underscore is accepted as a URL placeholder meaning "any".
        serial = serial.strip() if isinstance(serial, str) else None
        self.serial = serial if serial and serial != "_" else None

        # Duration (ms) to hold the LED colour before turning it off
        try:
            self.duration = int(
                BLINK1_DEFAULT_DURATION_MS if duration is None else duration
            )
            if not (
                BLINK1_MIN_DURATION_MS
                <= self.duration
                <= BLINK1_MAX_DURATION_MS
            ):
                raise ValueError("out of range")

        except (TypeError, ValueError):
            msg = (
                f"blink(1) duration ({duration}) must be between"
                f" {BLINK1_MIN_DURATION_MS} and"
                f" {BLINK1_MAX_DURATION_MS} ms."
            )
            self.logger.warning(msg)
            raise TypeError(msg) from None

        # Fade transition time (ms)
        try:
            self.fade = int(BLINK1_DEFAULT_FADE_MS if fade is None else fade)
            if not (BLINK1_MIN_FADE_MS <= self.fade <= BLINK1_MAX_FADE_MS):
                raise ValueError("out of range")

        except (TypeError, ValueError):
            msg = (
                f"blink(1) fade ({fade}) must be between"
                f" {BLINK1_MIN_FADE_MS} and {BLINK1_MAX_FADE_MS} ms."
            )
            self.logger.warning(msg)
            raise TypeError(msg) from None

        # LED selector; unrecognised values silently fall back to ALL
        self.ledn = (
            BLINK1_LED_MAP.get(str(ledn).lower(), Blink1LED.ALL)
            if ledn is not None
            else Blink1LED.ALL
        )

    def _open_device(self):
        """Open and return a hidapi device handle for the blink(1).

        Returns None and logs a warning when the device cannot be found.
        """
        try:
            dev = blink1_hid.device()
            dev.open(
                BLINK1_VENDOR_ID,
                BLINK1_PRODUCT_ID,
                self.serial,
            )
            return dev

        except OSError:
            msg = "Failed to open blink(1) device"
            if self.serial:
                msg += f" (serial={self.serial})"
            msg += "."
            self.logger.warning(msg)
            return None

    def _send_fade(self, dev, red, green, blue, fade_ms):
        """Send a single fade-to-RGB HID feature report.

        Returns True on success, False if the report could not be sent.
        """
        buf = _blink1_fade_buf(red, green, blue, fade_ms, self.ledn)
        try:
            rc = dev.send_feature_report(buf)

        except OSError as e:
            self.logger.warning("blink(1) HID write failed: %s", e)
            return False

        if rc != BLINK1_REPORT_SIZE:
            self.logger.warning(
                "blink(1) HID write returned %d (expected %d).",
                rc,
                BLINK1_REPORT_SIZE,
            )
            return False

        return True

    @property
    def url_identifier(self):
        """Returns all fields that uniquely identify this connection."""
        return (
            self.protocol,
            self.serial,
            self.ledn,
        )

    def send(self, body, title="", notify_type=NotifyType.INFO, **kwargs):
        """Perform blink(1) Notification."""

        # Resolve the RGB triple for this notification type
        r, g, b = self.color(notify_type=notify_type, color_type=tuple)

        dev = self._open_device()
        if dev is None:
            return False

        try:
            # Always throttle before any device I/O
            self.throttle()

            if not self._send_fade(dev, r, g, b, self.fade):
                return False

            # Hold for fade + duration, then switch off
            time.sleep((self.fade + self.duration) / 1000.0)

            # Turn off: instant fade to black
            if not self._send_fade(dev, 0, 0, 0, 0):
                return False

        finally:
            dev.close()

        self.logger.info("Sent blink(1) notification.")
        return True

    def url(self, privacy=False, *args, **kwargs):
        """Returns the URL built dynamically based on specified arguments."""

        params = {
            "duration": str(self.duration),
            "fade": str(self.fade),
            "ledn": str(self.ledn),
        }
        params.update(self.url_parameters(privacy=privacy, *args, **kwargs))

        serial = self.serial if self.serial else "_"
        return f"{self.protocol}://{serial}/?{NotifyBlink1.urlencode(params)}"

    @staticmethod
    def parse_url(url):
        """Parses the URL and returns enough arguments to re-instantiate."""

        results = NotifyBase.parse_url(url, verify_host=False)
        if not results:
            return results

        # The hostname, when present, is the device serial number.
        # An underscore or empty value means "first available device".
        host = results.get("host", "")
        if host and host != "_":
            results["serial"] = NotifyBlink1.unquote(host)

        if results["qsd"].get("duration"):
            results["duration"] = NotifyBlink1.unquote(
                results["qsd"]["duration"]
            )

        if results["qsd"].get("fade"):
            results["fade"] = NotifyBlink1.unquote(results["qsd"]["fade"])

        if results["qsd"].get("ledn"):
            results["ledn"] = NotifyBlink1.unquote(results["qsd"]["ledn"])

        return results

    @staticmethod
    def runtime_deps():
        """Return optional runtime dependency package names."""
        return ("hid",)
