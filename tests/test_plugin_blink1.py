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

import logging
import sys
from unittest import mock

from helpers import AppriseURLTester
import pytest

from apprise import Apprise, NotifyType
from apprise.plugins.blink1 import (
    BLINK1_DEFAULT_DURATION_MS,
    BLINK1_DEFAULT_FADE_MS,
    BLINK1_MAX_DURATION_MS,
    BLINK1_MAX_FADE_MS,
    BLINK1_REPORT_SIZE,
    Blink1LED,
    NotifyBlink1,
    _blink1_fade_buf,
)

logging.disable(logging.CRITICAL)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_device(report_size=BLINK1_REPORT_SIZE, open_exc=None):
    """Return a mock hidapi device that succeeds by default."""
    dev = mock.Mock()
    dev.send_feature_report.return_value = report_size
    if open_exc is not None:
        dev.open.side_effect = open_exc
    return dev


# ---------------------------------------------------------------------------
# URL matrix used by AppriseURLTester
# ---------------------------------------------------------------------------

apprise_url_tests = (
    # First available device, all defaults
    (
        "blink1://",
        {
            "instance": NotifyBlink1,
        },
    ),
    # Explicit underscore placeholder for first device
    (
        "blink1://_/",
        {
            "instance": NotifyBlink1,
        },
    ),
    # Specific device by serial number
    (
        "blink1://ABCD1234/",
        {
            "instance": NotifyBlink1,
        },
    ),
    # Minimum allowed parameter values
    (
        "blink1://?duration=0&fade=0&ledn=0",
        {
            "instance": NotifyBlink1,
        },
    ),
    # LED 1 (first LED only)
    (
        "blink1://?ledn=1",
        {
            "instance": NotifyBlink1,
        },
    ),
    # LED 2 (second LED only)
    (
        "blink1://?ledn=2",
        {
            "instance": NotifyBlink1,
        },
    ),
    # Maximum allowed duration
    (
        f"blink1://?duration={BLINK1_MAX_DURATION_MS}",
        {
            "instance": NotifyBlink1,
        },
    ),
    # Maximum allowed fade
    (
        f"blink1://?fade={BLINK1_MAX_FADE_MS}",
        {
            "instance": NotifyBlink1,
        },
    ),
    # Non-numeric duration -> TypeError
    (
        "blink1://?duration=abc",
        {
            "instance": TypeError,
        },
    ),
    # Negative duration -> TypeError
    (
        "blink1://?duration=-1",
        {
            "instance": TypeError,
        },
    ),
    # Duration exceeds maximum -> TypeError
    (
        f"blink1://?duration={BLINK1_MAX_DURATION_MS + 1}",
        {
            "instance": TypeError,
        },
    ),
    # Non-numeric fade -> TypeError
    (
        "blink1://?fade=abc",
        {
            "instance": TypeError,
        },
    ),
    # Negative fade -> TypeError
    (
        "blink1://?fade=-1",
        {
            "instance": TypeError,
        },
    ),
    # Fade exceeds maximum -> TypeError
    (
        f"blink1://?fade={BLINK1_MAX_FADE_MS + 1}",
        {
            "instance": TypeError,
        },
    ),
)


# ---------------------------------------------------------------------------
# Import-error path (run only when hidapi is NOT installed)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    "hid" in sys.modules,
    reason="Requires that hidapi NOT be installed",
)
def test_plugin_blink1_import_error():
    """NotifyBlink1() returns None when hidapi is absent."""

    obj = Apprise.instantiate("blink1://")
    assert obj is None


# ---------------------------------------------------------------------------
# All remaining tests require hidapi to be installed
# ---------------------------------------------------------------------------


def test_plugin_blink1_urls():
    """NotifyBlink1() Apprise URL matrix."""

    pytest.importorskip("hid")

    with (
        mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid,
        mock.patch("apprise.plugins.blink1.time") as mock_time,
    ):
        mock_dev = _mk_device()
        mock_hid.device.return_value = mock_dev
        mock_time.sleep.return_value = None

        AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_blink1_device_open_failure():
    """NotifyBlink1() returns False when the USB device cannot be opened."""

    pytest.importorskip("hid")

    with mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid:
        mock_dev = _mk_device(open_exc=OSError("no device"))
        mock_hid.device.return_value = mock_dev

        obj = Apprise.instantiate("blink1://ABCD1234/")
        assert obj is not None
        assert obj.notify(body="test") is False


def test_plugin_blink1_device_open_failure_no_serial():
    """NotifyBlink1() failure log omits serial when none is configured."""

    pytest.importorskip("hid")

    with mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid:
        mock_dev = _mk_device(open_exc=OSError("no device"))
        mock_hid.device.return_value = mock_dev

        obj = Apprise.instantiate("blink1://")
        assert obj is not None
        assert obj.notify(body="test") is False


def test_plugin_blink1_send_feature_report_exception():
    """NotifyBlink1() returns False and closes device on HID write error."""

    pytest.importorskip("hid")

    with (
        mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid,
        mock.patch("apprise.plugins.blink1.time") as mock_time,
    ):
        mock_dev = mock.Mock()
        mock_dev.send_feature_report.side_effect = OSError("USB error")
        mock_hid.device.return_value = mock_dev
        mock_time.sleep.return_value = None

        obj = Apprise.instantiate("blink1://")
        assert obj is not None
        assert obj.notify(body="test") is False

        # close() must always be called
        assert mock_dev.close.called


def test_plugin_blink1_short_report_fails():
    """NotifyBlink1() returns False when the HID report is truncated."""

    pytest.importorskip("hid")

    with (
        mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid,
        mock.patch("apprise.plugins.blink1.time") as mock_time,
    ):
        mock_dev = _mk_device(report_size=BLINK1_REPORT_SIZE - 1)
        mock_hid.device.return_value = mock_dev
        mock_time.sleep.return_value = None

        obj = Apprise.instantiate("blink1://")
        assert obj is not None
        assert obj.notify(body="test") is False


def test_plugin_blink1_notify_types():
    """NotifyBlink1() sends one fade per notification type."""

    pytest.importorskip("hid")

    with (
        mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid,
        mock.patch("apprise.plugins.blink1.time") as mock_time,
    ):
        mock_dev = _mk_device()
        mock_hid.device.return_value = mock_dev
        mock_time.sleep.return_value = None

        obj = Apprise.instantiate("blink1://ABCD1234/?fade=100&duration=50")
        assert obj is not None

        for notify_type in (
            NotifyType.INFO,
            NotifyType.SUCCESS,
            NotifyType.WARNING,
            NotifyType.FAILURE,
        ):
            assert obj.notify(body="test", notify_type=notify_type) is True

        # Each notification sends two reports (color + off)
        assert mock_dev.send_feature_report.call_count == 8
        assert mock_dev.close.call_count == 4


def test_plugin_blink1_fade_buf_layout():
    """_blink1_fade_buf() constructs the correct 9-byte HID payload."""

    buf = _blink1_fade_buf(255, 128, 0, 1000, ledn=1)

    assert len(buf) == 9
    assert buf[0] == 0x01  # REPORT_ID
    assert buf[1] == ord("c")  # command byte
    assert buf[2] == 255  # red
    assert buf[3] == 128  # green
    assert buf[4] == 0  # blue
    # fade_time = 1000 // 10 = 100 = 0x0064
    assert buf[5] == 0x00  # th
    assert buf[6] == 0x64  # tl
    assert buf[7] == 1  # ledn
    assert buf[8] == 0x00  # padding


def test_plugin_blink1_fade_rgb_args():
    """NotifyBlink1() passes correct ledn and RGB values to the device."""

    pytest.importorskip("hid")

    with (
        mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid,
        mock.patch("apprise.plugins.blink1.time") as mock_time,
    ):
        mock_dev = _mk_device()
        mock_hid.device.return_value = mock_dev
        mock_time.sleep.return_value = None

        obj = Apprise.instantiate("blink1://?fade=200&duration=100&ledn=2")
        assert obj is not None
        assert obj.notify(body="test", notify_type=NotifyType.INFO) is True

        first_call_buf = mock_dev.send_feature_report.call_args_list[0][0][0]
        assert first_call_buf[1] == ord("c")  # command byte
        assert first_call_buf[7] == 2  # ledn
        # fade_time = 200 // 10 = 20 = 0x0014
        assert first_call_buf[5] == 0x00
        assert first_call_buf[6] == 0x14


def test_plugin_blink1_off_sent_after_duration():
    """NotifyBlink1() sends an off command after sleeping for fade+duration."""

    pytest.importorskip("hid")

    with (
        mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid,
        mock.patch("apprise.plugins.blink1.time") as mock_time,
    ):
        mock_dev = _mk_device()
        mock_hid.device.return_value = mock_dev
        mock_time.sleep.return_value = None

        obj = Apprise.instantiate("blink1://?fade=500&duration=2000")
        assert obj is not None
        assert obj.notify(body="test") is True

        mock_time.sleep.assert_called_once_with(2.5)

        # Second report should be the "off" command (all zeros for RGB)
        off_buf = mock_dev.send_feature_report.call_args_list[1][0][0]
        assert off_buf[2] == 0  # red
        assert off_buf[3] == 0  # green
        assert off_buf[4] == 0  # blue


def test_plugin_blink1_off_command_failure_returns_false():
    """NotifyBlink1() returns False when the off HID write fails."""

    pytest.importorskip("hid")

    with (
        mock.patch("apprise.plugins.blink1.blink1_hid") as mock_hid,
        mock.patch("apprise.plugins.blink1.time") as mock_time,
    ):
        mock_dev = mock.Mock()
        # First call (color fade) succeeds; second call (off) fails.
        mock_dev.send_feature_report.side_effect = [
            BLINK1_REPORT_SIZE,
            BLINK1_REPORT_SIZE - 1,
        ]
        mock_hid.device.return_value = mock_dev
        mock_time.sleep.return_value = None

        obj = Apprise.instantiate("blink1://")
        assert obj is not None
        assert obj.notify(body="test") is False

        # close() must still be called
        assert mock_dev.close.called


def test_plugin_blink1_url_round_trip():
    """NotifyBlink1() URL reconstructs an equivalent object."""

    obj = NotifyBlink1(serial="ABCD1234", duration=3000, fade=500, ledn=1)
    rebuilt = NotifyBlink1(**NotifyBlink1.parse_url(obj.url()))

    assert rebuilt.serial == "ABCD1234"
    assert rebuilt.duration == 3000
    assert rebuilt.fade == 500
    assert rebuilt.ledn == 1


def test_plugin_blink1_url_round_trip_no_serial():
    """NotifyBlink1() URL round-trips correctly without a serial."""

    obj = NotifyBlink1()
    rebuilt = NotifyBlink1(**NotifyBlink1.parse_url(obj.url()))

    assert rebuilt.serial is None
    assert rebuilt.duration == BLINK1_DEFAULT_DURATION_MS
    assert rebuilt.fade == BLINK1_DEFAULT_FADE_MS
    assert rebuilt.ledn == Blink1LED.ALL


def test_plugin_blink1_url_identifier():
    """NotifyBlink1() url_identifier distinguishes different connections."""

    obj_a = NotifyBlink1()
    obj_b = NotifyBlink1(serial="ABCD1234")
    obj_c = NotifyBlink1(ledn=1)

    assert obj_a.url_identifier != obj_b.url_identifier
    assert obj_a.url_identifier != obj_c.url_identifier
    assert obj_b.url_identifier != obj_c.url_identifier


def test_plugin_blink1_invalid_ledn_defaults():
    """NotifyBlink1() silently falls back to ALL for an unrecognised ledn."""

    obj = NotifyBlink1(ledn="99")
    assert obj.ledn == Blink1LED.ALL


def test_plugin_blink1_runtime_deps():
    """NotifyBlink1.runtime_deps() returns the importable hid module name."""

    assert NotifyBlink1.runtime_deps() == ("hid",)


def test_plugin_blink1_parse_url_underscore():
    """NotifyBlink1() treats underscore host as first-device placeholder."""

    result = NotifyBlink1.parse_url("blink1://_/")
    assert result is not None
    assert result.get("serial") is None


def test_plugin_blink1_parse_url_serial():
    """NotifyBlink1() extracts serial number from URL host field."""

    result = NotifyBlink1.parse_url("blink1://DEADBEEF/")
    assert result is not None
    assert result["serial"] == "DEADBEEF"
