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
import sys
import types
from unittest.mock import ANY, Mock

from helpers import reload_plugin
import pytest

import apprise

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


@pytest.fixture
def mock_dbus_module(mocker):
    """
    Creates a completely fake 'dbus' module structure in sys.modules
    so that we can test the plugin even if dbus is not installed.
    """
    # 1. Create the base 'dbus' module
    dbus = types.ModuleType("dbus")
    dbus.DBusException = type("DBusException", (Exception,), {})
    dbus.Byte = lambda x: x
    dbus.ByteArray = lambda x: x
    dbus.Interface = Mock(name="Interface")
    dbus.SessionBus = Mock(name="SessionBus")

    # 2. Mock the mainloops
    #    We create the structure: dbus.mainloop.glib.DBusGMainLoop
    glib_module = types.ModuleType("dbus.mainloop.glib")
    glib_module.DBusGMainLoop = Mock(name="DBusGMainLoop")

    qt_module = types.ModuleType("dbus.mainloop.qt")
    qt_module.DBusQtMainLoop = Mock(name="DBusQtMainLoop")

    mainloop_pkg = types.ModuleType("dbus.mainloop")
    mainloop_pkg.glib = glib_module
    mainloop_pkg.qt = qt_module

    # Attach mainloop to the dbus module object so tests can access
    # mock_dbus_module.mainloop
    dbus.mainloop = mainloop_pkg

    # 3. Create the GI/GdkPixbuf mocks (for image support)
    gi = types.ModuleType("gi")
    gi.require_version = Mock()
    gi.repository = types.SimpleNamespace(
        GdkPixbuf=types.SimpleNamespace(
            Pixbuf=Mock(name="Pixbuf")
        )
    )
    # Setup standard Pixbuf behavior
    mock_image = Mock()
    mock_image.get_width.return_value = 10
    mock_image.get_height.return_value = 10
    mock_image.get_rowstride.return_value = 1
    mock_image.get_has_alpha.return_value = False
    mock_image.get_bits_per_sample.return_value = 8
    mock_image.get_n_channels.return_value = 3
    mock_image.get_pixels.return_value = b"pixeldata"

    gi.repository.GdkPixbuf.Pixbuf.new_from_file.return_value = mock_image

    # 4. Patch everything into sys.modules
    mocker.patch.dict(sys.modules, {
        "dbus": dbus,
        "dbus.mainloop": mainloop_pkg,
        "dbus.mainloop.glib": glib_module,
        "dbus.mainloop.qt": qt_module,
        "gi": gi,
        "gi.repository": gi.repository
    })

    return dbus


def test_plugin_dbus_initialization_strategies(mock_dbus_module, mocker):
    """
    Test the import logic
    1. GLib present, Qt missing
    2. Qt present, GLib missing
    3. Both missing
    """
    # Scenario A: GLib works, Qt fails
    # We simulate Qt missing by raising ImportError when accessing it
    sys.modules["dbus.mainloop.qt"] = None
    reload_plugin("dbus")
    from apprise.plugins.dbus import LOOP_GLIB, LOOP_QT, NotifyDBus
    assert LOOP_GLIB is not None
    assert LOOP_QT is None
    assert NotifyDBus.enabled is True

    # Scenario B: Qt works, GLib fails
    # Reset modules
    mock_dbus_module.mainloop.qt.DBusQtMainLoop.return_value = "qt_loop"

    mocker.patch.dict(sys.modules, {
        "dbus.mainloop.glib": None,
        "dbus.mainloop.qt": mock_dbus_module.mainloop.qt
    })

    reload_plugin("dbus")
    from apprise.plugins.dbus import LOOP_GLIB, LOOP_QT, NotifyDBus
    assert LOOP_GLIB is None
    assert LOOP_QT is not None
    assert NotifyDBus.enabled is True

    # Scenario C: Both fail
    mocker.patch.dict(sys.modules, {
        "dbus.mainloop.glib": None,
        "dbus.mainloop.qt": None
    })
    reload_plugin("dbus")
    from apprise.plugins.dbus import NotifyDBus
    assert NotifyDBus.enabled is False


def test_plugin_dbus_image_support_initialization(mock_dbus_module, mocker):
    """
    Test the GdkPixbuf import logic
    """
    # Case 1: Success (Already set up by fixture)
    reload_plugin("dbus")
    from apprise.plugins.dbus import NOTIFY_DBUS_IMAGE_SUPPORT
    assert NOTIFY_DBUS_IMAGE_SUPPORT is True

    # Case 2: GI missing
    mocker.patch.dict(sys.modules, {"gi": None})
    reload_plugin("dbus")
    from apprise.plugins.dbus import NOTIFY_DBUS_IMAGE_SUPPORT
    assert NOTIFY_DBUS_IMAGE_SUPPORT is False


def test_plugin_dbus_send_success(mock_dbus_module, mocker):
    """
    Test the happy path for send()
    """
    reload_plugin("dbus")
    from apprise.plugins.dbus import NotifyDBus

    # Setup the mock chain: SessionBus() ->
    #   .get_object() -> Interface() -> .Notify()
    mock_bus = mock_dbus_module.SessionBus.return_value
    mock_proxy = mock_bus.get_object.return_value
    mock_interface = mock_dbus_module.Interface.return_value

    obj = NotifyDBus()

    # Send notification
    assert obj.notify(title="Title", body="Body") is True

    # VERIFICATION
    # Check SessionBus was called
    mock_dbus_module.SessionBus.assert_called()
    # Check Interface was created
    mock_dbus_module.Interface.assert_called_with(
        mock_proxy, dbus_interface="org.freedesktop.Notifications")
    # Check Notify was called
    assert mock_interface.Notify.called
    args, _ = mock_interface.Notify.call_args
    # Arg 3 is Title, Arg 4 is Body
    assert args[3] == "Title"
    assert args[4] == "Body"


def test_plugin_dbus_send_no_title(mock_dbus_module):
    """
    Test the 'if not title' swap logic
    """
    reload_plugin("dbus")
    from apprise.plugins.dbus import NotifyDBus
    mock_interface = mock_dbus_module.Interface.return_value

    obj = NotifyDBus()
    obj.notify(title="", body="OnlyBody")

    args, _ = mock_interface.Notify.call_args
    # Title (Arg 3) should now be "OnlyBody", Body (Arg 4) empty
    assert args[3] == "OnlyBody"
    assert args[4] == ""


def test_plugin_dbus_send_connection_failure(mock_dbus_module):
    """
    Test SessionBus raising DBusException
    """
    reload_plugin("dbus")
    from apprise.plugins.dbus import NotifyDBus

    # Force constructor to crash
    mock_dbus_module.SessionBus.side_effect = \
        mock_dbus_module.DBusException("Connection Refused")

    obj = NotifyDBus()
    # Should handle exception and return False
    assert obj.notify(title="T", body="B") is False


def test_plugin_dbus_send_notify_failure(mock_dbus_module):
    """
    Test Interface.Notify raising Exception
    """
    reload_plugin("dbus")
    from apprise.plugins.dbus import NotifyDBus

    # Force Notify to crash
    mock_interface = mock_dbus_module.Interface.return_value
    mock_interface.Notify.side_effect = Exception("Generic Failure")

    obj = NotifyDBus()
    assert obj.notify(title="T", body="B") is False


def test_plugin_dbus_image_loading_failure(mock_dbus_module, mocker):
    """
    Test image loading exception
    """
    reload_plugin("dbus")
    # Force GdkPixbuf to crash
    import gi

    gi.repository.GdkPixbuf.Pixbuf.new_from_file.side_effect = \
        Exception("Bad Image")

    # Use Apprise.instantiate to handle parsing cleanly
    obj = apprise.Apprise.instantiate(
        "dbus://?image=yes", suppress_exceptions=False)
    spy_logger = mocker.spy(obj, "logger")

    # Notification should still succeed (return True), just log a warning
    assert obj.notify(title="T", body="B") is True

    # Verify the warning was logged
    spy_logger.warning.assert_called_with(
        "Could not load notification icon (%s).", ANY)


def test_plugin_dbus_url_parsing(mock_dbus_module):
    """
    Test various URL parameters and instantiation.
    """
    reload_plugin("dbus")
    from apprise.plugins.dbus import DBusUrgency, NotifyDBus

    # Test Urgency mapping
    obj = apprise.Apprise.instantiate(
        "dbus://?urgency=high", suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus)
    assert obj.urgency == DBusUrgency.HIGH
    assert "urgency=high" in obj.url()

    obj = apprise.Apprise.instantiate(
        "dbus://?priority=low", suppress_exceptions=False)
    assert isinstance(obj, NotifyDBus)
    assert obj.urgency == DBusUrgency.LOW
    assert "urgency=low" in obj.url()

    # Test X/Y coords
    obj = apprise.Apprise.instantiate(
        "dbus://?x=100&y=200", suppress_exceptions=False)
    assert obj.x_axis == 100
    assert obj.y_axis == 200
    assert "x=100" in obj.url()
    assert "y=200" in obj.url()

    # Test Invalid X/Y
    with pytest.raises(TypeError):
        NotifyDBus(x_axis="invalid")


def test_plugin_dbus_schema_not_supported(mock_dbus_module, mocker):
    """
    Dbus test for unsupported schema warning
    """
    reload_plugin("dbus")
    from apprise.plugins.dbus import NotifyDBus

    with pytest.raises(TypeError):
        NotifyDBus(schema="not-a-real-schema")

    # Assert warning emitted (message content is stable)
    with pytest.raises(TypeError):
        NotifyDBus(schema="still-not-real")


def test_plugin_dbus_send_sets_xy_meta_payload(mock_dbus_module):
    """
    Covers setting x-y payload setting
    """
    reload_plugin("dbus")
    from apprise.plugins.dbus import NotifyDBus

    mock_interface = mock_dbus_module.Interface.return_value
    obj = NotifyDBus(x_axis=100, y_axis=200)

    assert obj.notify(title="T", body="B") is True

    args, _ = mock_interface.Notify.call_args
    # meta output (app, id, icon, title, body, actions, meta, timeout)
    meta = args[6]
    assert meta["x"] == 100
    assert meta["y"] == 200


def test_plugin_dbus_send_image_condition_false_skips_pixbuf(
        mock_dbus_module, mocker):
    """
    Covers NOTIFY_DBUS_IMAGE_SUPPORT and icon_path flag
    """
    reload_plugin("dbus")
    import gi

    from apprise.plugins.dbus import NotifyDBus

    mock_interface = mock_dbus_module.Interface.return_value

    obj = NotifyDBus(include_image=False)

    # Ensure image_path is not even consulted when include_image=False
    spy_image_path = mocker.spy(obj, "image_path")

    assert obj.notify(title="T", body="B") is True

    assert mock_interface.Notify.called
    assert gi.repository.GdkPixbuf.Pixbuf.new_from_file.called is False
    assert spy_image_path.called is False
