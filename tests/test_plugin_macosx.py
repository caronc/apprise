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
import os
import subprocess
import sys
from unittest.mock import Mock

from helpers import reload_plugin
import pytest

import apprise
from apprise.plugins.macosx import NotifyMacOSX

# Disable logging for a cleaner testing output.
logging.disable(logging.CRITICAL)


if sys.platform not in ["darwin", "linux"]:
    pytest.skip(
        "Only makes sense on macOS, but testable in Linux",
        allow_module_level=True,
    )


@pytest.fixture
def pretend_macos(mocker):
    """Fixture to simulate a macOS environment."""
    mocker.patch("platform.system", return_value="Darwin")
    mocker.patch("platform.mac_ver", return_value=("10.8", ("", "", ""), ""))

    # Reload plugin module, in order to re-run module-level code.
    reload_plugin("macosx")


@pytest.fixture
def terminal_notifier(mocker, tmp_path):
    """Provide a temporary terminal-notifier program for tests."""
    notifier_program = tmp_path.joinpath("terminal-notifier")
    notifier_program.write_text(
        "#!/bin/sh\n\n"
        'if [ "$1" = "-version" ]; then\n'
        '  echo "terminal-notifier 3.1.0."\n'
        "  exit 0\n"
        "fi\n"
        "echo hello\n"
    )

    # Set execute bit.
    os.chmod(notifier_program, 0o755)

    # Make the notifier use the temporary file instead of `terminal-notifier`.
    mocker.patch(
        "apprise.plugins.macosx.NotifyMacOSX.notify_paths",
        (str(notifier_program),),
    )

    yield notifier_program


@pytest.fixture
def macos_notify_environment(pretend_macos, terminal_notifier):
    """Prepare a simulated macOS system with terminal-notifier.

    Use the individual fixtures when a test needs direct access to them.
    """
    pass


def test_plugin_macosx_general_success(macos_notify_environment):
    """NotifyMacOSX() general checks."""

    # Toggle Enable Flag
    obj = apprise.Apprise.instantiate(
        "macosx://_/?image=True", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMacOSX) is True

    # Test url() call
    assert isinstance(obj.url(), str) is True

    # URL Identifier has been disabled as this isn't unique enough
    # to be mapped to more the 1 end point; verify that None is always
    # returned
    assert obj.url_id() is None

    # test notifications
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    # test notification without a title
    assert (
        obj.notify(title="", body="body", notify_type=apprise.NotifyType.INFO)
        is True
    )

    obj = apprise.Apprise.instantiate(
        "macosx://_/?image=True", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMacOSX) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "macosx://_/?image=False", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMacOSX) is True
    assert isinstance(obj.url(), str) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    # Test Sound
    obj = apprise.Apprise.instantiate(
        "macosx://_/?sound=default", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMacOSX) is True
    assert obj.sound == "default"
    assert isinstance(obj.url(), str) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    # Test Click (-open support)
    obj = apprise.Apprise.instantiate(
        "macosx://_/?click=http://google.com", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMacOSX) is True
    assert obj.click == "http://google.com"
    assert isinstance(obj.url(), str) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )


def test_plugin_macosx_not_executable(pretend_macos, terminal_notifier):
    """Notifications fail when terminal-notifier is not executable."""

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)

    # Unset the executable bit.
    os.chmod(terminal_notifier, 0o644)

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is False
    )


def test_plugin_macosx_invalid_path(macos_notify_environment):
    """Notifications fail when terminal-notifier cannot be found."""

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)

    # Let's disrupt the path location.
    obj.notify_path = "invalid_missing-file"
    assert not os.path.isfile(obj.notify_path)

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is False
    )


def test_plugin_macosx_command_failure(mocker, macos_notify_environment):
    """Notifications fail when terminal-notifier returns an error."""

    # Emulate a failing program.
    mocker.patch(
        "subprocess.run",
        return_value=Mock(returncode=1, stdout=b"", stderr=b"boom"),
    )

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert isinstance(obj, NotifyMacOSX) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is False
    )


def test_plugin_macosx_pretend_linux(mocker, pretend_macos):
    """The notification object is disabled when pretending to run on Linux."""

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    mocker.patch("platform.system", return_value="Linux")
    reload_plugin("macosx")

    # Our object is disabled.
    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj is None


@pytest.mark.parametrize("macos_version", ["9.12", "10.7"])
def test_plugin_macosx_pretend_old_macos(mocker, macos_version):
    """The notification object is disabled when pretending to run on older
    macOS."""

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    mocker.patch(
        "platform.mac_ver", return_value=(macos_version, ("", "", ""), "")
    )
    reload_plugin("macosx")

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj is None


def test_plugin_macosx_sender(mocker, macos_notify_environment):
    """Pass `-sender` through and preserve it in generated URLs."""

    mock_run = mocker.patch(
        "subprocess.run",
        return_value=Mock(
            returncode=0, stdout=b"terminal-notifier 2.0.0.", stderr=b""
        ),
    )

    obj = apprise.Apprise.instantiate(
        "macosx://_/?sender=me", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMacOSX) is True
    assert obj.sender == "me"
    assert "sender=me" in obj.url()

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    cmd = mock_run.call_args[0][0]
    assert "-sender" in cmd
    assert cmd[cmd.index("-sender") + 1] == "\\me"


def test_plugin_macosx_sender_default(mocker, macos_notify_environment):
    """Without an explicit override, `-sender` falls back to our own
    app_id so notifications work out of the box."""

    mock_run = mocker.patch(
        "subprocess.run",
        return_value=Mock(
            returncode=0, stdout=b"terminal-notifier 2.0.0.", stderr=b""
        ),
    )

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj.sender is None

    # The default isn't baked into the URL; it is resolved at send time
    assert "sender=" not in obj.url()

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    cmd = mock_run.call_args[0][0]
    assert "-sender" in cmd
    assert cmd[cmd.index("-sender") + 1] == "\\{}".format(obj.app_id)


def test_plugin_macosx_sender_empty_app_id(mocker, macos_notify_environment):
    """When both `sender` and our own app_id are unset, `-sender` is
    left off the command entirely rather than being sent empty."""

    mock_run = mocker.patch(
        "subprocess.run",
        return_value=Mock(
            returncode=0, stdout=b"terminal-notifier 2.0.0.", stderr=b""
        ),
    )

    asset = apprise.AppriseAsset(app_id="")
    obj = apprise.Apprise.instantiate(
        "macosx://", asset=asset, suppress_exceptions=False
    )
    assert obj.app_id == ""

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    assert "-sender" not in mock_run.call_args[0][0]


def test_plugin_macosx_version_3(mocker, macos_notify_environment):
    """`version=3` skips options that only version 2 supports."""

    mock_run = mocker.patch(
        "subprocess.run",
        return_value=Mock(
            returncode=0, stdout=b"terminal-notifier 2.0.0.", stderr=b""
        ),
    )

    obj = apprise.Apprise.instantiate(
        "macosx://_/?version=3&sender=me&image=yes",
        suppress_exceptions=False,
    )
    assert isinstance(obj, NotifyMacOSX) is True
    assert obj.version == 3
    assert "version=3" in obj.url()

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    cmd = mock_run.call_args[0][0]
    assert "-sender" not in cmd
    assert "-appIcon" not in cmd


def test_plugin_macosx_version_2(mocker, macos_notify_environment):
    """`version=2` includes the sender option."""

    mock_run = mocker.patch(
        "subprocess.run",
        return_value=Mock(
            returncode=0, stdout=b"terminal-notifier 2.0.0.", stderr=b""
        ),
    )

    obj = apprise.Apprise.instantiate(
        "macosx://_/?version=2", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMacOSX) is True
    assert obj.version == 2

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    cmd = mock_run.call_args[0][0]
    assert "-sender" in cmd


@pytest.mark.parametrize("bad_version", ["99", "abc"])
def test_plugin_macosx_version_invalid(macos_notify_environment, bad_version):
    """An unsupported or non-numeric `version=` value is rejected
    outright."""

    with pytest.raises(TypeError):
        apprise.Apprise.instantiate(
            "macosx://_/?version={}".format(bad_version),
            suppress_exceptions=False,
        )


def test_plugin_macosx_version_detection(mocker, macos_notify_environment):
    """Without an explicit override, terminal-notifier is asked which
    version it is."""

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)

    # Nothing is pinned, so nothing is carried in the URL
    assert obj.version is None
    assert "version=" not in obj.url()

    # Our surrogate program reports 3.1.0
    assert obj.tn_version == 3

    # The answer is remembered rather than probed again
    mock_run = mocker.patch("subprocess.run")
    assert obj.tn_version == 3
    assert mock_run.call_count == 0


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        (b"terminal-notifier 2.0.0.", 2),
        (b"terminal-notifier 3.1.0.", 3),
        (b"terminal-notifier 4.0.0.", 3),
        (b"", 3),
    ],
)
def test_plugin_macosx_version_probe(
    mocker, macos_notify_environment, reported, expected
):
    """The major version reported by terminal-notifier picks the dialect."""

    mocker.patch(
        "subprocess.run", return_value=Mock(returncode=0, stdout=reported)
    )

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj.tn_version == expected


def test_plugin_macosx_probe_failure(mocker, macos_notify_environment):
    """A probe that never answers falls back to the current release."""

    mocker.patch("subprocess.run", side_effect=OSError("nope"))

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj.tn_version == 3


def test_plugin_macosx_escaping(mocker, macos_notify_environment):
    """Values are escaped so terminal-notifier reads them as text."""

    mock_run = mocker.patch(
        "subprocess.run",
        return_value=Mock(returncode=0, stdout=b"terminal-notifier 3.1.0."),
    )

    obj = apprise.Apprise.instantiate(
        "macosx://_/?sound=default&click=http://google.com&image=no",
        suppress_exceptions=False,
    )
    assert obj.notify(title="[Alert]", body="12345") is True

    cmd = mock_run.call_args[0][0]
    assert cmd[cmd.index("-message") + 1] == "\\12345"
    assert cmd[cmd.index("-title") + 1] == "\\[Alert]"
    assert cmd[cmd.index("-sound") + 1] == "\\default"
    assert cmd[cmd.index("-open") + 1] == "\\http://google.com"


def test_plugin_macosx_image_switch(mocker, macos_notify_environment):
    """Version 2 sets the app icon; version 3 attaches a local image."""

    mock_run = mocker.patch(
        "subprocess.run",
        return_value=Mock(returncode=0, stdout=b"terminal-notifier 3.1.0."),
    )

    obj = apprise.Apprise.instantiate(
        "macosx://_/?version=2&image=yes", suppress_exceptions=False
    )
    assert obj.notify(title="title", body="body") is True
    assert "-appIcon" in mock_run.call_args[0][0]

    obj = apprise.Apprise.instantiate(
        "macosx://_/?version=3&image=yes", suppress_exceptions=False
    )
    assert obj.notify(title="title", body="body") is True

    cmd = mock_run.call_args[0][0]
    assert "-appIcon" not in cmd
    assert "-contentImage" in cmd

    # A local file terminal-notifier can actually read
    assert os.path.isfile(cmd[cmd.index("-contentImage") + 1][1:])


@pytest.mark.parametrize("exit_code", [1, 2, 3, 4, 5, 6, 99])
def test_plugin_macosx_exit_codes(mocker, macos_notify_environment, exit_code):
    """Any non-zero exit from terminal-notifier is reported as a failure."""

    mocker.patch(
        "subprocess.run",
        return_value=Mock(
            returncode=exit_code,
            stdout=b"terminal-notifier 3.1.0.",
            stderr=b"Notifications are not allowed for this application",
        ),
    )

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj.notify(title="title", body="body") is False


def test_plugin_macosx_probe_timeout(mocker, macos_notify_environment):
    """A probe that hangs falls back to the current release."""

    mocker.patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(
            cmd="terminal-notifier", timeout=5
        ),
    )

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj.tn_version == 3


def test_plugin_macosx_probe_unclean_exit(mocker, macos_notify_environment):
    """A version reported alongside a non-zero exit isn't trusted."""

    mocker.patch(
        "subprocess.run",
        return_value=Mock(returncode=1, stdout=b"terminal-notifier 2.0.0."),
    )

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj.tn_version == 3


def test_plugin_macosx_probe_absurd_version(mocker, macos_notify_environment):
    """A version too large to convert falls back instead of raising."""

    mocker.patch(
        "subprocess.run",
        return_value=Mock(
            returncode=0, stdout=b"terminal-notifier " + b"9" * 5000 + b".0"
        ),
    )

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)
    assert obj.tn_version == 3


@pytest.mark.parametrize(
    "failure",
    [
        OSError("vanished"),
        subprocess.TimeoutExpired(cmd="terminal-notifier", timeout=30),
    ],
)
def test_plugin_macosx_run_failure(mocker, macos_notify_environment, failure):
    """A program that disappears or hangs is reported, not raised."""

    mocker.patch("subprocess.run", side_effect=failure)

    obj = apprise.Apprise.instantiate(
        "macosx://_/?version=3", suppress_exceptions=False
    )
    assert obj.notify(title="title", body="body") is False
