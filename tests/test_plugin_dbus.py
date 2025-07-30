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
import re
import sys
import types
from unittest.mock import ANY, Mock, call

from helpers import reload_plugin
import pytest

import apprise
from apprise.plugins.dbus import (
    NOTIFY_DBUS_SUPPORT_ENABLED,
    DBusUrgency,
    NotifyDBus,
)

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


if not NOTIFY_DBUS_SUPPORT_ENABLED:
    pytest.skip(
        "NotifyDBus is not supported in this environment",
        allow_module_level=True)


@pytest.fixture
def enabled_dbus_environment(monkeypatch):
    """
    Fully mocked DBus and GI environment that works in local and CI
    environments.
    """

    # --- Handle dbus (real or fake) ---
    try:
        import dbus
    except ImportError:
        dbus = types.ModuleType("dbus")
        dbus.DBusException = type("DBusException", (Exception,), {})
        dbus.Interface = Mock()
        dbus.SessionBus = Mock()

        sys.modules["dbus"] = dbus

    # Inject mainloop support if not already present
    if "dbus.mainloop.glib" not in sys.modules:
        glib_loop = types.ModuleType("dbus.mainloop.glib")
        glib_loop.DBusGMainLoop = lambda: Mock(name="FakeLoop")
        sys.modules["dbus.mainloop.glib"] = glib_loop

    if "dbus.mainloop" not in sys.modules:
        sys.modules["dbus.mainloop"] = types.ModuleType("dbus.mainloop")

    # Patch specific attributes always, even if real module is present
    monkeypatch.setattr("dbus.Interface", Mock())
    monkeypatch.setattr("dbus.SessionBus", Mock())
    monkeypatch.setattr(
        "dbus.DBusException", type("DBusException", (Exception,), {}))

    # --- Mock GI / GdkPixbuf ---
    gi = types.ModuleType("gi")
    gi.require_version = Mock()
    gi.repository = types.SimpleNamespace(
        GdkPixbuf=types.SimpleNamespace(Pixbuf=Mock())
    )

    sys.modules["gi"] = gi
    sys.modules["gi.repository"] = gi.repository

    # --- Reload plugin with controlled env ---
    reload_plugin("dbus")


def test_plugin_dbus_available(enabled_dbus_environment):
    """Tests DBUS_SUPPORT_ENABLED flag"""
    from apprise.plugins import dbus as plugin_dbus
    assert plugin_dbus.NOTIFY_DBUS_SUPPORT_ENABLED is True


@pytest.mark.parametrize("param", [
    "urgency=high", "urgency=2", "urgency=invalid", "urgency=",
    "priority=high", "priority=2", "priority=invalid",
])
def test_plugin_dbus_priority_urgency_variants(
        enabled_dbus_environment, param):
    """test dbus:// urgency variants"""
    url = f"dbus://_/?{param}"
    obj = apprise.Apprise.instantiate(url, suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus)
    assert obj.notify(title="x", body="x", notify_type=apprise.NotifyType.INFO)


def test_plugin_dbus_parse_url_arguments(enabled_dbus_environment):
    """Test dbus:// argument parsing"""
    from apprise.plugins.dbus import NotifyDBus
    result = NotifyDBus.parse_url(
        "dbus://_/?urgency=high&x=5&y=5&image=no")
    assert result["urgency"] == "high"
    assert result["x_axis"] == "5"
    assert result["y_axis"] == "5"
    assert result["include_image"] is False


def test_plugin_dbus_with_gobject_cleanup(mocker, enabled_dbus_environment):
    """Simulate `gobject` being present in sys.modules."""
    original_gobject = sys.modules.get("gobject")

    try:
        sys.modules["gobject"] = mocker.Mock()
        reload_plugin("dbus")

        from apprise.plugins import dbus as plugin_dbus  # noqa F401
        assert "gobject" not in sys.modules

    finally:
        if original_gobject is not None:
            sys.modules["gobject"] = original_gobject
        else:
            sys.modules.pop("gobject", None)
        reload_plugin("dbus")


def test_plugin_dbus_no_mainloop_support(mocker):
    """Simulate both mainloops (qt and glib) being unavailable."""
    original_qt = sys.modules.get("dbus.mainloop.qt")
    original_glib = sys.modules.get("dbus.mainloop.glib")

    try:
        # Simulate missing mainloops
        sys.modules["dbus.mainloop.qt"] = None
        sys.modules["dbus.mainloop.glib"] = None

        reload_plugin("dbus")
        from apprise.plugins import dbus as plugin_dbus

        assert plugin_dbus.LOOP_QT is None
        assert plugin_dbus.LOOP_GLIB is None
        assert plugin_dbus.NOTIFY_DBUS_SUPPORT_ENABLED is False

    finally:
        # Restore previous state
        if original_qt is not None:
            sys.modules["dbus.mainloop.qt"] = original_qt
        else:
            sys.modules.pop("dbus.mainloop.qt", None)

        if original_glib is not None:
            sys.modules["dbus.mainloop.glib"] = original_glib
        else:
            sys.modules.pop("dbus.mainloop.glib", None)

        reload_plugin("dbus")


def test_plugin_dbus_general_success(mocker, enabled_dbus_environment):
    """NotifyDBus() general tests.

    Test class loading using different arguments, provided via URL.
    """
    # Re-import NotifyDBus after plugin has been reloaded
    from apprise.plugins.dbus import NotifyDBus

    # Create our instance (identify all supported types)
    obj = apprise.Apprise.instantiate("dbus://", suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert obj.url().startswith("dbus://_/")
    obj = apprise.Apprise.instantiate("kde://", suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert obj.url().startswith("kde://_/")
    obj = apprise.Apprise.instantiate("qt://", suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert obj.url().startswith("qt://_/")
    obj.duration = 0

    # Set our X and Y coordinate and try the notification
    assert (
        NotifyDBus(x_axis=0, y_axis=0, **{"schema": "dbus"}).notify(
            title="", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

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

    # Test our arguments through the instantiate call
    obj = apprise.Apprise.instantiate(
        "dbus://_/?image=True", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert obj.url().startswith("dbus://_/")
    assert re.search("image=yes", obj.url())

    # URL ID Generation is disabled
    assert obj.url_id() is None

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "dbus://_/?image=False", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert obj.url().startswith("dbus://_/")
    assert re.search("image=no", obj.url())

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    # Test priority (alias to urgency) handling
    obj = apprise.Apprise.instantiate(
        "dbus://_/?priority=invalid", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "dbus://_/?priority=high", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "dbus://_/?priority=2", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    # Test urgency handling
    obj = apprise.Apprise.instantiate(
        "dbus://_/?urgency=invalid", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "dbus://_/?urgency=high", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "dbus://_/?urgency=2", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    obj = apprise.Apprise.instantiate(
        "dbus://_/?urgency=", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )

    # Test x/y
    obj = apprise.Apprise.instantiate(
        "dbus://_/?x=5&y=5", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyDBus)
    assert isinstance(obj.url(), str)
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )


def test_plugin_dbus_general_failure(enabled_dbus_environment):
    """Verify a few failure conditions."""

    with pytest.raises(TypeError):
        NotifyDBus(**{"schema": "invalid"})

    with pytest.raises(TypeError):
        apprise.Apprise.instantiate(
            "dbus://_/?x=invalid&y=invalid", suppress_exceptions=False
        )


def test_plugin_dbus_notify_generic_exception(
        mocker, enabled_dbus_environment):
    """Trigger a generic exception in .notify() to hit fallback handler."""

    # Step 1: Provide minimal valid dbus/glib environment
    fake_loop = Mock(name="FakeMainLoop")
    sys.modules["dbus.mainloop.glib"] = types.SimpleNamespace(
        DBusGMainLoop=lambda: fake_loop
    )
    sys.modules["gi"] = types.SimpleNamespace(require_version=Mock())
    sys.modules["gi.repository"] = types.SimpleNamespace(
        GdkPixbuf=types.SimpleNamespace(Pixbuf=Mock())
    )

    # Step 2: Patch SessionBus.get_object to return an object with a Notify()
    # that raises
    mock_iface = Mock()
    mock_iface.Notify.side_effect = RuntimeError("boom")

    mock_obj = Mock()
    mock_session = Mock()
    mock_session.get_object.return_value = mock_obj

    mocker.patch("dbus.SessionBus", return_value=mock_session)
    mocker.patch("dbus.Interface", return_value=mock_iface)

    # Step 3: Reload plugin with mocked environment
    reload_plugin("dbus")

    # Step 4: Create instance and spy on logger
    obj = apprise.Apprise.instantiate("dbus://", suppress_exceptions=False)
    logger_spy = mocker.spy(obj, "logger")

    # Step 5: Trigger .notify() — should enter final except Exception block
    assert obj.notify(
        title="x", body="x", notify_type=apprise.NotifyType.INFO
    ) is False

    # Step 6: Confirm the fallback exception logging was triggered
    logger_spy.warning.assert_called_with("Failed to send DBus notification.")
    assert any("boom" in str(arg)
               for call in logger_spy.debug.call_args_list
               for arg in call.args)


def test_plugin_dbus_parse_configuration(enabled_dbus_environment):

    # Test configuration parsing
    content = """
    urls:
      - dbus://:
          - priority: 0
            tag: dbus_int low
          - priority: "0"
            tag: dbus_str_int low
          - priority: low
            tag: dbus_str low
          - urgency: 0
            tag: dbus_int low
          - urgency: "0"
            tag: dbus_str_int low
          - urgency: low
            tag: dbus_str low

          # These will take on normal (default) urgency
          - priority: invalid
            tag: dbus_invalid
          - urgency: invalid
            tag: dbus_invalid

      - dbus://:
          - priority: 2
            tag: dbus_int high
          - priority: "2"
            tag: dbus_str_int high
          - priority: high
            tag: dbus_str high
          - urgency: 2
            tag: dbus_int high
          - urgency: "2"
            tag: dbus_str_int high
          - urgency: high
            tag: dbus_str high
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
        assert s.urgency == DBusUrgency.LOW

    assert len(list(aobj.find(tag="high"))) == 6
    for s in aobj.find(tag="high"):
        assert s.urgency == DBusUrgency.HIGH

    assert len(list(aobj.find(tag="dbus_str"))) == 4
    assert len(list(aobj.find(tag="dbus_str_int"))) == 4
    assert len(list(aobj.find(tag="dbus_int"))) == 4

    assert len(list(aobj.find(tag="dbus_invalid"))) == 2
    for s in aobj.find(tag="dbus_invalid"):
        assert s.urgency == DBusUrgency.NORMAL


def test_plugin_dbus_missing_icon(mocker, enabled_dbus_environment):
    """Test exception when loading icon; the notification will still be
    sent."""

    # Inject error when loading icon.
    gi = importlib.import_module("gi")
    gi.repository.GdkPixbuf.Pixbuf.new_from_file.side_effect = AttributeError(
        "Something failed"
    )

    obj = apprise.Apprise.instantiate("dbus://", suppress_exceptions=False)
    logger: Mock = mocker.spy(obj, "logger")
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )
    assert logger.mock_calls == [
        call.warning("Could not load notification icon (%s).", ANY),
        call.debug("DBus Exception: Something failed"),
        call.info("Sent DBus notification."),
    ]


def test_plugin_dbus_disabled_plugin(enabled_dbus_environment):
    """Verify notification will not be submitted if plugin is disabled."""
    obj = apprise.Apprise.instantiate("dbus://", suppress_exceptions=False)

    obj.enabled = False

    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is False
    )


@pytest.mark.parametrize("urgency, expected", [
    (0, DBusUrgency.LOW),
    (1, DBusUrgency.NORMAL),
    (2, DBusUrgency.HIGH),
    ("high", DBusUrgency.HIGH),
    ("invalid", DBusUrgency.NORMAL),
])
def test_plugin_dbus_set_urgency(enabled_dbus_environment, urgency, expected):
    """Test the setting of an urgency."""
    assert NotifyDBus(urgency=urgency).urgency == expected


def test_plugin_dbus_gi_missing(enabled_dbus_environment):
    """Verify notification succeeds even if the `gi` package is not
    available."""

    # Make `require_version` function raise an ImportError.
    gi = importlib.import_module("gi")
    gi.require_version.side_effect = ImportError()

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    reload_plugin("dbus")

    # Create the instance.
    obj = apprise.Apprise.instantiate("dbus://", suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    obj.duration = 0

    # Test url() call.
    assert isinstance(obj.url(), str) is True

    # The notification succeeds even though the gi library was not loaded.
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )


def test_plugin_dbus_gi_require_version_error(enabled_dbus_environment):
    """Verify notification succeeds even if `gi.require_version()` croaks."""

    # Make `require_version` function raise a ValueError.
    gi = importlib.import_module("gi")
    gi.require_version.side_effect = ValueError("Something failed")

    # When patching something which has a side effect on the module-level code
    # of a plugin, make sure to reload it.
    reload_plugin("dbus")

    # Create instance.
    obj = apprise.Apprise.instantiate("dbus://", suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus) is True
    obj.duration = 0

    # Test url() call.
    assert isinstance(obj.url(), str) is True

    # The notification succeeds even though the gi library was not loaded.
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is True
    )


def test_plugin_dbus_module_croaks(monkeypatch):
    """
    Simulate dbus module missing entirely and confirm plugin disables itself.
    """

    # Drop the dbus module entirely from sys.modules
    monkeypatch.setitem(sys.modules, "dbus", None)

    reload_plugin("dbus")

    # Plugin instantiation should fail (plugin is skipped)
    obj = apprise.Apprise.instantiate("dbus://", suppress_exceptions=False)
    assert obj is None

    # Plugin class still exists but is disabled
    from apprise.plugins.dbus import NotifyDBus
    assert NotifyDBus.enabled is False


def test_plugin_dbus_session_croaks(mocker, enabled_dbus_environment):
    """Verify notification fails if DBus session initialization croaks."""

    from dbus import DBusException as RealDBusException

    # Patch SessionBus before plugin is imported or evaluated
    mocker.patch("dbus.SessionBus", side_effect=RealDBusException("test"))

    # Set up minimal working env so the plugin doesn't disable itself
    fake_loop = Mock(name="FakeMainLoop")
    sys.modules["dbus.mainloop.glib"] = types.SimpleNamespace(
        DBusGMainLoop=lambda: fake_loop
    )
    sys.modules["gi"] = types.SimpleNamespace(require_version=Mock())
    sys.modules["gi.repository"] = types.SimpleNamespace(
        GdkPixbuf=types.SimpleNamespace(Pixbuf=Mock())
    )

    # Must reload plugin *after* environment is patched
    reload_plugin("dbus")

    from apprise.plugins.dbus import NotifyDBus
    obj = apprise.Apprise.instantiate("dbus://", suppress_exceptions=False)

    assert isinstance(obj, NotifyDBus)

    # Notify should fail gracefully
    assert (
        obj.notify(
            title="title", body="body", notify_type=apprise.NotifyType.INFO
        )
        is False
    )
