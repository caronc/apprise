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

from inspect import cleandoc

# Disable logging for a cleaner testing output
import logging
import re
import threading
import types

import pytest

from apprise import Apprise, NotificationManager
from apprise.plugins import NotifyBase

logging.disable(logging.CRITICAL)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()


def test_notification_manager_general():
    """
    N_MGR: Notification Manager General testing

    """
    # Clear our set so we can test init calls
    N_MGR.unload_modules()
    assert isinstance(N_MGR.schemas(), list)
    assert len(N_MGR.schemas()) > 0
    N_MGR.unload_modules(disable_native=True)
    assert isinstance(N_MGR.schemas(), list)
    assert len(N_MGR.schemas()) == 0

    N_MGR.unload_modules()
    assert len(N_MGR) > 0

    N_MGR.unload_modules()
    iter(N_MGR)
    iter(N_MGR)

    N_MGR.unload_modules()
    assert bool(N_MGR) is False
    assert len(list(iter(N_MGR))) > 0
    assert bool(N_MGR)

    N_MGR.unload_modules()
    assert isinstance(N_MGR.plugins(), types.GeneratorType)
    assert len(list(N_MGR.plugins())) > 0
    N_MGR.unload_modules(disable_native=True)
    assert isinstance(N_MGR.plugins(), types.GeneratorType)
    assert len(list(N_MGR.plugins())) == 0
    N_MGR.unload_modules()
    assert isinstance(N_MGR["json"](host="localhost"), NotifyBase)
    N_MGR.unload_modules()
    assert "json" in N_MGR

    # Define our good:// url
    class DisabledNotification(NotifyBase):
        # Always disabled
        enabled = False

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support url() function
            return ""

    # Define our good:// url
    class GoodNotification(NotifyBase):

        secure_protocol = ("good", "goods")

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support url() function
            return ""

    N_MGR.unload_modules()
    assert N_MGR.add(GoodNotification)
    assert "good" in N_MGR
    assert "goods" in N_MGR
    assert "abcd" not in N_MGR
    assert "xyz" not in N_MGR

    N_MGR.unload_modules()
    assert N_MGR.add(GoodNotification, "abcd")
    assert "good" in N_MGR
    assert "goods" in N_MGR
    assert "abcd" in N_MGR
    assert "xyz" not in N_MGR

    N_MGR.unload_modules()
    assert N_MGR.add(GoodNotification, ["abcd", "xYz"])
    assert "good" in N_MGR
    assert "goods" in N_MGR
    assert "abcd" in N_MGR
    # Lower case
    assert "xyz" in N_MGR

    N_MGR.unload_modules()
    # Not going to work; schemas must be a list of string
    assert N_MGR.add(GoodNotification, object) is False

    N_MGR.unload_modules()
    with pytest.raises(KeyError):
        del N_MGR["good"]
    N_MGR["good"] = GoodNotification
    del N_MGR["good"]

    N_MGR.unload_modules()
    N_MGR["good"] = GoodNotification
    assert N_MGR["good"].enabled is True
    N_MGR.enable_only("json", "xml")
    assert N_MGR["good"].enabled is False
    assert N_MGR["json"].enabled is True
    assert N_MGR["jsons"].enabled is True
    assert N_MGR["xml"].enabled is True
    assert N_MGR["xmls"].enabled is True

    # Only two plugins are enabled
    assert len(list(N_MGR.plugins(include_disabled=False))) == 2

    N_MGR.enable_only("good")
    assert N_MGR["good"].enabled is True
    assert N_MGR["json"].enabled is False
    assert N_MGR["jsons"].enabled is False
    assert N_MGR["xml"].enabled is False
    assert N_MGR["xmls"].enabled is False

    assert len(list(N_MGR.plugins(include_disabled=False))) == 1

    N_MGR.unload_modules()
    N_MGR["disabled"] = DisabledNotification
    assert N_MGR["disabled"].enabled is False
    N_MGR.enable_only("disabled")
    # Can't enable items that aren't supposed to be:
    assert N_MGR["disabled"].enabled is False

    N_MGR["good"] = GoodNotification
    assert N_MGR["good"].enabled is True

    # You can't disable someething already disabled
    N_MGR.disable("disabled")
    assert N_MGR["disabled"].enabled is False

    N_MGR.unload_modules()
    N_MGR.enable_only("form", "xml")
    for schema in N_MGR.schemas(include_disabled=False):
        assert re.match(r"^(form|xml)s?$", schema, re.IGNORECASE) is not None

    N_MGR.unload_modules()
    assert N_MGR["form"].enabled is True
    assert N_MGR["xml"].enabled is True
    assert N_MGR["json"].enabled is True
    N_MGR.enable_only("form", "xml")
    assert N_MGR["form"].enabled is True
    assert N_MGR["xml"].enabled is True
    assert N_MGR["json"].enabled is False

    N_MGR.disable("invalid", "xml")
    assert N_MGR["form"].enabled is True
    assert N_MGR["xml"].enabled is False
    assert N_MGR["json"].enabled is False

    # Detect that our json object is enabled
    with pytest.raises(KeyError):
        # The below can not be indexed
        N_MGR["invalid"]

    N_MGR.unload_modules()
    N_MGR.disable("invalid", "xml")

    N_MGR.unload_modules()
    assert N_MGR["json"].enabled is True

    # Work with an empty module tree
    N_MGR.unload_modules(disable_native=True)
    with pytest.raises(KeyError):
        # The below can not be indexed
        N_MGR["good"]

    N_MGR.unload_modules()
    assert "hello" not in N_MGR
    assert "good" not in N_MGR
    assert "goods" not in N_MGR

    N_MGR["hello"] = GoodNotification
    assert "hello" in N_MGR
    assert "good" in N_MGR
    assert "goods" in N_MGR

    N_MGR.unload_modules()
    N_MGR["good"] = GoodNotification

    with pytest.raises(KeyError):
        # Can not assign the value again without getting a Conflict
        N_MGR["good"] = GoodNotification

    N_MGR.unload_modules()
    N_MGR.remove("good", "invalid")
    assert "good" not in N_MGR
    assert "goods" not in N_MGR


def test_notification_manager_add_force_overrides_schema_without_unload():
    """Verify add(force=True) overrides existing schema without unloading."""
    import sys

    from apprise.plugins import N_MGR

    class NotifyDiscordCustom:
        """A minimal custom discord override used for testing."""

        protocol = "discord"
        secure_protocol = None
        service_name = "Discord (Custom)"

        def __init__(self, *args, **kwargs):
            pass

        def send(self, *args, **kwargs):
            return True

        def url(self, **kwargs):
            return "discord://"

    # Ensure native modules are loaded
    N_MGR.unload_modules()
    N_MGR.load_modules()

    # Confirm 'discord' is available and capture its module name
    assert "discord" in N_MGR
    native_plugin = N_MGR["discord"]
    native_module = native_plugin.__module__
    assert native_module in sys.modules

    # A normal add should fail due to the conflict
    assert N_MGR.add(NotifyDiscordCustom, schemas="discord") is False

    # A forced add should succeed and must not unload the native module
    assert N_MGR.add(
        NotifyDiscordCustom, schemas="discord", force=True) is True
    assert N_MGR["discord"] is NotifyDiscordCustom
    assert native_module in sys.modules


def test_notification_manager_module_loading(tmpdir):
    """
    N_MGR: Notification Manager Module Loading

    """

    # Handle loading modules twice (they gracefully handle not loading more in
    # memory then needed)
    N_MGR.load_modules()
    N_MGR.load_modules()

    #
    # Thread Testing
    #

    # This tests against a racing condition when the modules have not been
    # loaded.  When multiple instances of Apprise are all instantiated,
    # the loading of the modules will occur for each instance if detected
    # having not been previously done, this tests that we can dynamically
    # support the loading of modules once whe multiple instances to apprise
    # are instantiated.
    thread_count = 10

    def thread_test(result, no):
        """Load our apprise object with valid URLs and store our result."""
        apobj = Apprise()
        result[no] = (
            apobj.add("json://localhost")
            and apobj.add("form://localhost")
            and apobj.add("xml://localhost")
        )

    # Unload our modules
    N_MGR.unload_modules()

    # Prepare threads to load
    results = [None] * thread_count
    threads = [
        threading.Thread(target=thread_test, args=(results, no))
        for no in range(thread_count)
    ]

    # Verify we can safely load our modules in a thread safe environment
    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Verify we loaded our urls in all threads successfully
    for result in results:
        assert result is True


def test_notification_manager_decorators(tmpdir):
    """
    N_MGR: Notification Manager Decorator testing

    """

    # Prepare ourselves a file to work with
    notify_hook = tmpdir.mkdir("goodmodule").join("__init__.py")
    notify_hook.write(cleandoc("""
    from apprise.decorators import notify

    # We want to trigger on anyone who configures a call to clihook://
    @notify(on="clihooka")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        # A simple test - print to screen
        print("A {}: {} - {}".format(notify_type, title, body))

        # No return (so a return of None) get's translated to True

    # Define another in the same file; uppercase goes to lower
    @notify(on="CLIhookb")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        # A simple test - print to screen
        print("B {}: {} - {}".format(notify_type, title, body))

        # No return (so a return of None) get's translated to True
    """))

    N_MGR.module_detection(str(notify_hook))

    assert "clihooka" in N_MGR
    assert "clihookb" in N_MGR
    N_MGR.unload_modules()
    assert "clihooka" not in N_MGR
    assert "clihookb" not in N_MGR

    N_MGR.module_detection(str(notify_hook))
    assert "clihooka" in N_MGR
    assert "clihookb" in N_MGR
    del N_MGR["clihookb"]
    assert "clihooka" in N_MGR
    assert "clihookb" not in N_MGR
    del N_MGR["clihooka"]
    assert "clihooka" not in N_MGR
    assert "clihookb" not in N_MGR

    # Prepare ourselves a file to work with
    notify_base = tmpdir.mkdir("plugins")
    notify_test = notify_base.join("NotifyTest.py")
    notify_test.write(cleandoc("""
    #
    # Bare Minimum Valid Object
    #
    from apprise.plugins import NotifyBase
    from apprise.common import NotifyType

    class NotifyTest(NotifyBase):

        service_name = 'Test'

        # The services URL
        service_url = 'https://github.com/caronc/apprise/'

        # Define our protocol
        secure_protocol = 'myservice'

        # A URL that takes you to the setup/help of the specific protocol
        setup_url = 'https://appriseit.com/services/myservice/'

        # Define object templates
        templates = (
            '{schema}://',
        )

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
            return True

        def url(self):
            return 'myservice://'
    """))
    assert "myservice" not in N_MGR
    N_MGR.load_modules(path=str(notify_base))
    assert "myservice" in N_MGR
    del N_MGR["myservice"]
    assert "myservice" not in N_MGR

    assert "myservice" not in N_MGR
    N_MGR.load_modules(path=str(notify_base))

    # It's still not loaded because the path has already been scanned
    assert "myservice" not in N_MGR
    N_MGR.load_modules(path=str(notify_base), force=True)
    assert "myservice" in N_MGR

    # Double load will test section of code that prevents a notification
    # From reloading if previously already loaded
    N_MGR.load_modules(path=str(notify_base))
    # Our item is still loaded as expected
    assert "myservice" in N_MGR

    # Simple test to make sure we can handle duplicate entries loaded
    N_MGR.load_modules(path=str(notify_base), force=True)
    N_MGR.load_modules(path=str(notify_base), force=True)


def test_notification_manager_add_force_returns_false_if_conflict_persists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    N_MGR.add(force=True) must still fail safely if conflicts persist after the
    attempted unmap.

    This explicitly targets the defensive re-check branch in add().
    """
    # Ensure native modules are loaded and we have a known schema to collide on
    N_MGR.unload_modules()
    N_MGR.load_modules()
    assert "discord" in N_MGR

    class NotifyDiscordCustom:
        protocol = "discord"
        secure_protocol = None
        service_name = "Discord (Custom)"

        def __init__(self, *args, **kwargs) -> None:
            pass

        def send(self, *args, **kwargs) -> bool:
            return True

        def url(self, **kwargs) -> str:
            return "discord://"

    # Simulate an unmap failure by making remove() a no-op.
    # This ensures the conflict remains on the re-check and triggers the
    # warning + return False branch.
    def _noop_remove(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(N_MGR, "remove", _noop_remove)

    assert (
        N_MGR.add(NotifyDiscordCustom, schemas="discord", force=True) is False
    )


# ---------------------------------------------------------------------------
# Helpers shared by the runtime_deps / eviction tests
# ---------------------------------------------------------------------------

def _make_dep_plugin(schema, *deps):
    """Return a minimal NotifyBase subclass that declares *deps* in
    runtime_deps() and is always enabled."""

    class _Plugin(NotifyBase):
        protocol = schema
        enabled = True

        def notify(self, *args, **kwargs):
            return True

        def url(self, **kwargs):
            return f"{schema}://"

        @staticmethod
        def runtime_deps():
            return deps

    _Plugin.__name__ = f"Notify_{schema}"
    return _Plugin


# ---------------------------------------------------------------------------


def test_manager_dep_counter_built_on_load():
    """_dep_counter is populated after native modules are loaded."""
    N_MGR.unload_modules()
    # Trigger native load
    assert len(N_MGR.schemas()) > 0

    # The counter must exist and be a dict
    assert isinstance(N_MGR._dep_counter, dict)

    # Every library declared by an enabled plugin must appear in the counter
    for plugin in N_MGR.plugins(include_disabled=False):
        for lib in plugin.runtime_deps():
            assert lib in N_MGR._dep_counter
            assert N_MGR._dep_counter[lib] >= 1


def test_manager_dep_counter_custom_plugins():
    """_dep_counter reflects only enabled plugins with runtime_deps."""
    N_MGR.unload_modules()

    PlugA = _make_dep_plugin("plugA", "fakelib1")
    PlugB = _make_dep_plugin("plugB", "fakelib1", "fakelib2")
    PlugC = _make_dep_plugin("plugC")  # no deps

    N_MGR["plugA"] = PlugA
    N_MGR["plugB"] = PlugB
    N_MGR["plugC"] = PlugC

    # Rebuild counter to include newly registered plugins
    N_MGR._build_dep_counter()

    assert N_MGR._dep_counter.get("fakelib1", 0) >= 2
    assert N_MGR._dep_counter.get("fakelib2", 0) >= 1
    # PlugC has no deps so it contributes nothing
    assert "fakelib_none" not in N_MGR._dep_counter


def test_manager_disable_decrements_counter():
    """disable() decrements the dep counter for the disabled plugin's libs."""
    N_MGR.unload_modules()

    PlugA = _make_dep_plugin("solodep", "uniquelib99")
    N_MGR["solodep"] = PlugA
    N_MGR._build_dep_counter()

    assert N_MGR._dep_counter.get("uniquelib99", 0) >= 1
    before = N_MGR._dep_counter["uniquelib99"]

    N_MGR.disable("solodep")
    assert N_MGR._dep_counter.get("uniquelib99", 0) == before - 1


def test_manager_shared_dep_not_evicted_until_all_disabled():
    """A shared library is not evicted until every plugin using it is off."""
    import sys

    N_MGR.unload_modules()
    N_MGR.evict_on_disable = True

    # Two plugins share the same fake library
    PlugX = _make_dep_plugin("sharedX", "sharedfakelib")
    PlugY = _make_dep_plugin("sharedY", "sharedfakelib")

    # Inject a fake module so eviction has something to remove
    fake_mod = types.ModuleType("sharedfakelib")
    sys.modules["sharedfakelib"] = fake_mod

    N_MGR["sharedX"] = PlugX
    N_MGR["sharedY"] = PlugY
    N_MGR._build_dep_counter()

    assert N_MGR._dep_counter.get("sharedfakelib", 0) >= 2

    # Disable one — library should still be present (counter > 0)
    N_MGR.disable("sharedX")
    assert "sharedfakelib" in sys.modules

    # Disable the other — counter should hit 0 and library gets evicted
    N_MGR.disable("sharedY")
    assert "sharedfakelib" not in sys.modules

    N_MGR.evict_on_disable = False


def test_manager_evict_on_disable_false_by_default():
    """evict_on_disable defaults to False; no eviction even at counter 0."""
    import sys

    N_MGR.unload_modules()
    assert N_MGR.evict_on_disable is False

    PlugZ = _make_dep_plugin("nodiscard", "nodiscardlib")
    fake_mod = types.ModuleType("nodiscardlib")
    sys.modules["nodiscardlib"] = fake_mod

    N_MGR["nodiscard"] = PlugZ
    N_MGR._build_dep_counter()

    N_MGR.disable("nodiscard")

    # Library is still present because evict_on_disable is False
    assert "nodiscardlib" in sys.modules

    # Cleanup
    del sys.modules["nodiscardlib"]


def test_manager_evict_library_graceful_keyerror():
    """_evict_library handles a missing sys.modules key gracefully."""
    import sys

    N_MGR.unload_modules()

    # Put a module in, then remove it manually before eviction to simulate
    # a race or double-eviction scenario
    fake_mod = types.ModuleType("ghostlib")
    sys.modules["ghostlib"] = fake_mod
    del sys.modules["ghostlib"]

    # Should not raise even though the key is gone
    N_MGR._evict_library("ghostlib")


def test_manager_evict_library_removes_submodules():
    """_evict_library removes the top-level package and all its submodules."""
    import sys

    N_MGR.unload_modules()

    root = types.ModuleType("mypkg")
    sub = types.ModuleType("mypkg.sub")
    deep = types.ModuleType("mypkg.sub.deep")

    sys.modules["mypkg"] = root
    sys.modules["mypkg.sub"] = sub
    sys.modules["mypkg.sub.deep"] = deep

    N_MGR._evict_library("mypkg")

    assert "mypkg" not in sys.modules
    assert "mypkg.sub" not in sys.modules
    assert "mypkg.sub.deep" not in sys.modules


def test_manager_enable_only_updates_dep_counter():
    """enable_only() decrements counters for disabled plugins.

    We isolate this test to fake libraries only to avoid evicting real native
    extensions (e.g. cryptography/PyO3) that cannot be safely re-imported in
    the same interpreter session.
    """
    import sys

    N_MGR.unload_modules()
    N_MGR.evict_on_disable = True

    PlugKeep = _make_dep_plugin("keepme2", "keeplib2")
    PlugDrop = _make_dep_plugin("dropme2", "droplib2")

    fake_keep = types.ModuleType("keeplib2")
    fake_drop = types.ModuleType("droplib2")
    sys.modules["keeplib2"] = fake_keep
    sys.modules["droplib2"] = fake_drop

    N_MGR["keepme2"] = PlugKeep
    N_MGR["dropme2"] = PlugDrop

    # Seed the dep counter for only our two fake plugins so that disabling
    # dropme2 drives the droplib2 counter to zero — without touching real
    # native-library plugins loaded alongside them.
    N_MGR._dep_counter["keeplib2"] = 1
    N_MGR._dep_counter["droplib2"] = 1

    # Disable dropme2 directly; keepme2 stays enabled.
    N_MGR.disable("dropme2")

    assert N_MGR["keepme2"].enabled is True
    assert N_MGR["dropme2"].enabled is False
    assert "keeplib2" in sys.modules       # counter still 1 — not evicted
    assert "droplib2" not in sys.modules   # counter hit 0 — evicted

    # Cleanup
    del sys.modules["keeplib2"]
    N_MGR.evict_on_disable = False


def test_manager_unload_resets_dep_counter():
    """unload_modules() resets _dep_counter to an empty dict."""
    N_MGR.unload_modules()
    # Trigger load so counter is built
    assert len(N_MGR.schemas()) > 0
    assert len(N_MGR._dep_counter) > 0

    N_MGR.unload_modules()
    assert N_MGR._dep_counter == {}


def test_manager_known_plugin_runtime_deps():
    """Plugins known to carry optional deps must declare runtime_deps()."""
    N_MGR.unload_modules()

    from apprise.plugins.fcm import NotifyFCM
    from apprise.plugins.growl import NotifyGrowl
    from apprise.plugins.mqtt import NotifyMQTT
    from apprise.plugins.simplepush import NotifySimplePush
    from apprise.plugins.smpp import NotifySMPP
    from apprise.plugins.vapid import NotifyVapid
    from apprise.plugins.xmpp.base import NotifyXMPP

    assert "paho" in NotifyMQTT.runtime_deps()
    assert "gntp" in NotifyGrowl.runtime_deps()
    assert "smpplib" in NotifySMPP.runtime_deps()
    assert "slixmpp" in NotifyXMPP.runtime_deps()
    assert "cryptography" in NotifySimplePush.runtime_deps()
    assert "cryptography" in NotifyFCM.runtime_deps()
    assert "cryptography" in NotifyVapid.runtime_deps()

    # Base class has no deps
    assert NotifyBase.runtime_deps() == ()
