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

import importlib
import logging
import sys
import types
from unittest import mock
from unittest.mock import ANY, Mock, call

from helpers import reload_plugin
import pytest

import apprise
from apprise.plugins.gnome import GnomeUrgency, NotifyGnome

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


def setup_glib_environment():
    """Setup a heavily mocked Glib environment."""

    # Our module base
    gi_name = "gi"

    # First we do an import without the gi library available to ensure
    # we can handle cases when the library simply isn't available

    if gi_name in sys.modules:
        # Test cases where the gi library exists; we want to remove it
        # for the purpose of testing and capture the handling of the
        # library when it is missing
        del sys.modules[gi_name]
        reload_plugin("gnome")

    # We need to fake our gnome environment for testing purposes since
    # the gi library isn't available on CI
    gi = types.ModuleType(gi_name)
    gi.repository = types.ModuleType(gi_name + ".repository")
    gi.module = types.ModuleType(gi_name + ".module")

    mock_pixbuf = mock.Mock()
    mock_notify = mock.Mock()

    gi.repository.GdkPixbuf = types.ModuleType(
        gi_name + ".repository.GdkPixbuf"
    )
    gi.repository.GdkPixbuf.Pixbuf = mock_pixbuf
    gi.repository.Notify = mock.Mock()
    gi.repository.Notify.init.return_value = True
    gi.repository.Notify.Notification = mock_notify

    # Emulate require_version function:
    gi.require_version = mock.Mock(name=gi_name + ".require_version")

    # Force the fake module to exist
    sys.modules[gi_name] = gi
    sys.modules[gi_name + ".repository"] = gi.repository
    sys.modules[gi_name + ".repository.Notify"] = gi.repository.Notify

    # Notify Object
    notify_obj = mock.Mock()
    notify_obj.set_urgency.return_value = True
    notify_obj.set_icon_from_pixbuf.return_value = True
    notify_obj.set_image_from_pixbuf.return_value = True
    notify_obj.show.return_value = True
    mock_notify.new.return_value = notify_obj
    mock_pixbuf.new_from_file.return_value = True

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    reload_plugin("gnome")


@pytest.fixture
def glib_environment():
    """Fixture to provide a mocked Glib environment to test case functions."""
    setup_glib_environment()


@pytest.fixture
def obj(glib_environment):
    """Fixture to provide a mocked Apprise instance."""

    # Create our instance
    obj = apprise.Apprise.instantiate("gnome://", suppress_exceptions=False)
    assert obj is not None
    assert isinstance(obj, NotifyGnome) is True

    # Set our duration to 0 to speed up timeouts (for testing)
    obj.duration = 0

    # Check that it found our mocked environments
    assert obj.enabled is True

    return obj


def test_plugin_gnome_general_success(obj):
    """NotifyGnome() general checks."""

    # Test url() call
    assert isinstance(obj.url(), str) is True

    # our URL Identifier is disabled
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


def test_plugin_gnome_image_success(glib_environment):
    """Verify using the `image` query argument works as intended."""

    obj = apprise.Apprise.instantiate(
        "gnome://_/?image=True", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyGnome) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "gnome://_/?image=False", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyGnome) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )


def test_plugin_gnome_priority(glib_environment):
    """Verify correctness of the `priority` query argument."""

    # Test Priority (alias of urgency)
    obj = apprise.Apprise.instantiate(
        "gnome://_/?priority=invalid", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyGnome) is True
    assert obj.urgency == 1
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "gnome://_/?priority=high", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyGnome) is True
    assert obj.urgency == 2
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "gnome://_/?priority=2", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyGnome) is True
    assert obj.urgency == 2
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )


def test_plugin_gnome_urgency(glib_environment):
    """Verify correctness of the `urgency` query argument."""

    # Test Urgeny
    obj = apprise.Apprise.instantiate(
        "gnome://_/?urgency=invalid", suppress_exceptions=False
    )
    assert obj.urgency == 1
    assert isinstance(obj, NotifyGnome) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "gnome://_/?urgency=high", suppress_exceptions=False
    )
    assert obj.urgency == 2
    assert isinstance(obj, NotifyGnome) is True
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "gnome://_/?urgency=2", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyGnome) is True
    assert obj.urgency == 2
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )


def test_plugin_gnome_parse_configuration(obj):
    """Verify configuration parsing works correctly."""

    # Test configuration parsing
    content = """
    urls:
      - gnome://:
          - priority: 0
            tag: gnome_int low
          - priority: "0"
            tag: gnome_str_int low
          - priority: low
            tag: gnome_str low
          - urgency: 0
            tag: gnome_int low
          - urgency: "0"
            tag: gnome_str_int low
          - urgency: low
            tag: gnome_str low

          # These will take on normal (default) urgency
          - priority: invalid
            tag: gnome_invalid
          - urgency: invalid
            tag: gnome_invalid

      - gnome://:
          - priority: 2
            tag: gnome_int high
          - priority: "2"
            tag: gnome_str_int high
          - priority: high
            tag: gnome_str high
          - urgency: 2
            tag: gnome_int high
          - urgency: "2"
            tag: gnome_str_int high
          - urgency: high
            tag: gnome_str high
    """

    # Create ourselves a config object
    ac = apprise.AppriseConfig()
    assert ac.add_config(content=content) is True

    aobj = apprise.Apprise()

    # Add our configuration
    aobj.add(ac)

    # We should be able to read our 14 servers from that
    # 6x low
    # 6x high
    # 2x invalid (so takes on normal urgency)
    assert len(ac.servers()) == 14
    assert len(aobj) == 14
    assert len(list(aobj.find(tag="low"))) == 6
    for s in aobj.find(tag="low"):
        assert s.urgency == GnomeUrgency.LOW

    assert len(list(aobj.find(tag="high"))) == 6
    for s in aobj.find(tag="high"):
        assert s.urgency == GnomeUrgency.HIGH

    assert len(list(aobj.find(tag="gnome_str"))) == 4
    assert len(list(aobj.find(tag="gnome_str_int"))) == 4
    assert len(list(aobj.find(tag="gnome_int"))) == 4

    assert len(list(aobj.find(tag="gnome_invalid"))) == 2
    for s in aobj.find(tag="gnome_invalid"):
        assert s.urgency == GnomeUrgency.NORMAL


def test_plugin_gnome_missing_icon(mocker, obj):
    """Verify the notification will be submitted, even if loading the icon
    fails."""

    # Inject error when loading icon.
    gi = importlib.import_module("gi")
    gi.repository.GdkPixbuf.Pixbuf.new_from_file.side_effect = AttributeError(
        "Something failed"
    )

    logger: Mock = mocker.spy(obj, "logger")
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )
    assert logger.mock_calls == [
        call.warning("Could not load notification icon (%s).", ANY),
        call.debug("Gnome Exception: Something failed"),
        call.info("Sent Gnome notification."),
    ]


def test_plugin_gnome_disabled_plugin(obj):
    """Verify notification will not be submitted if plugin is disabled."""
    obj.enabled = False
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is False
    )


def test_plugin_gnome_set_urgency():
    """Test the setting of an urgency, through `priority` keyword argument."""
    NotifyGnome(priority=0)


@pytest.mark.skipif("gi" not in sys.modules, reason="Requires gi library")
def test_plugin_gnome_gi_croaks():
    """Verify notification fails when `gi.require_version()` croaks."""

    # Make `require_version` function raise an error.
    gi = importlib.import_module("gi")
    gi.require_version.side_effect = ValueError("Something failed")

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    reload_plugin("gnome")

    # Create instance.
    obj = apprise.Apprise.instantiate("gnome://", suppress_exceptions=False)

    # The notifier is marked disabled.
    assert obj is None


@pytest.mark.skipif("gi" not in sys.modules, reason="Requires gi library")
def test_plugin_gnome_notify_croaks(mocker, obj):
    """Fail gracefully if underlying object croaks for whatever reason."""

    # Inject an error when invoking `gi.repository.Notify`.
    mocker.patch(
        "gi.repository.Notify.Notification.new",
        side_effect=AttributeError("Something failed"),
    )

    logger: Mock = mocker.spy(obj, "logger")
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is False
    )
    assert logger.mock_calls == [
        call.warning("Failed to send Gnome notification."),
        call.debug("Gnome Exception: Something failed"),
    ]
