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

import logging
import os
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
    """Fixture for providing a surrogate for the `terminal-notifier`
    program."""
    notifier_program = tmp_path.joinpath("terminal-notifier")
    notifier_program.write_text("#!/bin/sh\n\necho hello")

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
    """Fixture to bundle general test case setup.

    Use this fixture if you don't need access to the individual members.
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


def test_plugin_macosx_terminal_notifier_not_executable(
    pretend_macos, terminal_notifier
):
    """When the `terminal-notifier` program is inaccessible or not executable,
    we are unable to send notifications."""

    obj = apprise.Apprise.instantiate("macosx://", suppress_exceptions=False)

    # Unset the executable bit.
    os.chmod(terminal_notifier, 0o644)

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is False
    )


def test_plugin_macosx_terminal_notifier_invalid(macos_notify_environment):
    """When the `terminal-notifier` program is wrongly addressed, notifications
    should fail."""

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


def test_plugin_macosx_terminal_notifier_croaks(
    mocker, macos_notify_environment
):
    """When the `terminal-notifier` program croaks on execution, notifications
    should fail."""

    # Emulate a failing program.
    mocker.patch("subprocess.Popen", return_value=Mock(returncode=1))

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
