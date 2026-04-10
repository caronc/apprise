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
import sys
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
    assert (
        N_MGR.add(NotifyDiscordCustom, schemas="discord", force=True) is True
    )
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
    notify_hook.write(
        cleandoc("""
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
    """)
    )

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
    notify_test.write(
        cleandoc("""
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
    """)
    )
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
    """Return a minimal NotifyBase subclass that declares *deps in
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
    assert "keeplib2" in sys.modules  # counter still 1 — not evicted
    assert "droplib2" not in sys.modules  # counter hit 0 — evicted

    # Cleanup
    del sys.modules["keeplib2"]
    N_MGR.evict_on_disable = False


def test_manager_unload_resets_dep_counter():
    """unload_modules() resets _dep_counter to an empty dict.

    Seeds the counter via a fake plugin rather than relying on native
    plugins whose optional libraries may not be installed (the minimal
    tox env disables all such plugins, leaving _dep_counter empty after
    a native load).
    """
    N_MGR.unload_modules()
    # Seed counter directly so the post-unload assertion is meaningful
    PlugR = _make_dep_plugin("resettest_xyz", "resetlib_xyz")
    N_MGR["resettest_xyz"] = PlugR
    N_MGR._build_dep_counter()
    assert N_MGR._dep_counter.get("resetlib_xyz", 0) >= 1

    N_MGR.unload_modules()
    assert N_MGR._dep_counter == {}


def test_manager_known_plugin_runtime_deps():
    """Plugins known to carry optional deps must declare runtime_deps()."""
    N_MGR.unload_modules()

    from apprise.plugins.blink1 import NotifyBlink1
    from apprise.plugins.fcm import NotifyFCM
    from apprise.plugins.growl import NotifyGrowl
    from apprise.plugins.mqtt import NotifyMQTT
    from apprise.plugins.simplepush import NotifySimplePush
    from apprise.plugins.smpp import NotifySMPP
    from apprise.plugins.vapid import NotifyVapid
    from apprise.plugins.xmpp.base import NotifyXMPP

    assert "hid" in NotifyBlink1.runtime_deps()
    assert "paho" in NotifyMQTT.runtime_deps()
    assert "gntp" in NotifyGrowl.runtime_deps()
    assert "smpplib" in NotifySMPP.runtime_deps()
    assert "slixmpp" in NotifyXMPP.runtime_deps()
    assert "cryptography" in NotifySimplePush.runtime_deps()
    assert "cryptography" in NotifyFCM.runtime_deps()
    assert "cryptography" in NotifyVapid.runtime_deps()

    # Base class has no deps
    assert NotifyBase.runtime_deps() == ()


# ===========================================================================
# Coverage: additional tests for previously uncovered branches
# ===========================================================================


def test_manager_len_already_loaded():
    """Verify __len__ works correctly when modules are already loaded."""
    N_MGR.unload_modules()
    # First call: triggers lazy load
    _ = len(N_MGR)
    # Second call: modules already loaded, returns length directly
    assert len(N_MGR) > 0


def test_manager_unload_orphan_custom_module():
    """Verify unload_modules() skips custom module map entries whose
    name is not present in the native module map."""
    N_MGR.unload_modules()
    N_MGR.load_modules()
    # Inject a synthetic entry whose 'name' value is not a key in
    # _module_map so the early-continue branch is exercised.
    N_MGR._custom_module_map["orphan_key_xyz"] = {
        "name": "orphan_module_xyz_not_native",
        "path": "/fake/path.py",
        "notify": {},
    }
    N_MGR.unload_modules()
    assert "orphan_key_xyz" not in N_MGR._custom_module_map


def test_module_detection_invalid_paths():
    """Verify module_detection returns early for invalid path inputs."""
    N_MGR.unload_modules()
    N_MGR.module_detection(None)
    N_MGR.module_detection([])
    N_MGR.module_detection(123)


def test_module_detection_nonexistent_path():
    """Verify a path that does not exist is silently skipped."""
    N_MGR.unload_modules()
    N_MGR.module_detection(["/tmp/__no_such_path_xyz_abc_123__"])


def test_module_detection_directory_scan(tmpdir):
    """Scans a plain directory (no __init__.py at root) containing several
    fixture files that each exercise a different branch."""
    N_MGR.unload_modules()

    # File whose name starts with '.' -> module_re fails -> ignored
    tmpdir.join(".hidden_xyz").write("")

    # File without .py extension -> valid_python_file_re fails inside
    # _import_module -> skipped
    tmpdir.join("noext_xyz").write("")

    # Valid .py but raises ImportError at module level ->
    # import_module returns None -> skipped
    tmpdir.join("badimport_xyz.py").write(
        "import this_library_does_not_exist_xyz_abc\n"
    )

    # Valid .py with no @notify -> module_pyname absent from
    # _custom_module_map after import -> skipped
    tmpdir.join("nohooks_xyz.py").write("x = 1\n")

    # Subdir without __init__.py -> no __init__.py -> skipped
    tmpdir.mkdir("subpkg_no_init_xyz")

    # Subdir WITH __init__.py, pre-populated in cache so the cache-hit
    # branch is exercised (file exists -> don't skip, but cache -> skip
    # _import_module call)
    cached_sub = tmpdir.mkdir("subpkg_cached_xyz")
    cached_init = cached_sub.join("__init__.py")
    cached_init.write("# cached\n")
    N_MGR._paths_previously_scanned.add(str(cached_init))

    N_MGR.module_detection(str(tmpdir))
    N_MGR.unload_modules()


def test_module_detection_package_dir(tmpdir):
    """Directory with __init__.py: already-scanned path is skipped;
    fresh path is imported but yields no hooks."""
    N_MGR.unload_modules()

    # A package dir (has __init__.py) with no @notify hooks
    pkgdir = tmpdir.mkdir("mypkg_xyz")
    pkg_path = str(pkgdir)
    init_path = str(pkgdir.join("__init__.py"))
    pkgdir.join("__init__.py").write("# no hooks\n")

    # Pre-populate the cache with the __init__.py path so the
    # already-scanned-inner-path branch is exercised on first call
    N_MGR._paths_previously_scanned.add(init_path)
    N_MGR.module_detection(pkg_path)

    # Discard both paths
    # so the add-to-cache branch is exercised on the second call
    N_MGR._paths_previously_scanned.discard(init_path)
    N_MGR._paths_previously_scanned.discard(pkg_path)
    N_MGR.module_detection(pkg_path)
    N_MGR.unload_modules()


def test_module_detection_non_matching_file(tmpdir):
    """File path whose basename fails module_re is silently ignored."""
    N_MGR.unload_modules()

    # A filename starting with '.' does not match module_re -> ignored
    hidden = tmpdir.join(".hidden_direct_xyz")
    hidden.write("")

    N_MGR.module_detection(str(hidden))
    N_MGR.unload_modules()


def test_module_detection_reload_existing(tmpdir):
    """_import_module clears and re-registers a custom module that was
    previously loaded into _custom_module_map."""
    N_MGR.unload_modules()

    hook = tmpdir.mkdir("reloadpkg_xyz").join("__init__.py")
    hook.write(
        cleandoc("""
        from apprise.decorators import notify

        @notify(on="reloadhookxyz")
        def handler(body, title, notify_type, *args, **kwargs):
            pass
    """)
    )

    # First load — populates _custom_module_map
    N_MGR.module_detection(str(hook))
    assert "reloadhookxyz" in N_MGR

    # Remove path from cache so the same file is processed a second time
    N_MGR._paths_previously_scanned.discard(str(hook))

    # Second load -> _import_module finds module_pyname already in
    # _custom_module_map -> clear + re-register
    N_MGR.module_detection(str(hook))
    assert "reloadhookxyz" in N_MGR
    N_MGR.unload_modules()


def test_build_dep_counter_empty_map():
    """_build_dep_counter returns early when _module_map is empty."""
    # disable_native=True sets _module_map = {} (falsy) -> returns early
    N_MGR.unload_modules(disable_native=True)
    N_MGR._build_dep_counter()
    assert N_MGR._dep_counter == {}


def test_build_dep_counter_no_runtime_deps_attr():
    """Plugin without a callable runtime_deps is skipped by
    _build_dep_counter."""
    N_MGR.unload_modules()
    N_MGR.load_modules()

    class MinimalPlugin:
        """Minimal plugin: enabled but has no runtime_deps attribute."""

        enabled = True

    N_MGR._module_map["minimal_test_xyz_657"] = {
        "plugin": {MinimalPlugin},
        "module": None,
        "path": "apprise.adhoc.minimal_test_xyz_657",
        "native": False,
    }
    # getattr returns None -> not callable(None) -> continue
    N_MGR._build_dep_counter()
    N_MGR.unload_modules()


def test_update_dep_counter_no_runtime_deps():
    """_update_dep_counter returns early when the plugin has no callable
    runtime_deps."""
    N_MGR.unload_modules()

    class NoDepPlugin:
        """Plugin with no runtime_deps attribute at all."""

    # getattr returns None -> not callable(None) -> return early
    N_MGR._update_dep_counter(NoDepPlugin, -1)


def test_evict_library_keyerror_race(monkeypatch):
    """KeyError during sys.modules eviction is handled gracefully.

    sys.modules is replaced with a subclass whose __delitem__ always
    raises KeyError.  The key is found but the delete fails, exercising
    the except-KeyError branch.  With evicted == 0 and to_remove
    non-empty the elif warning branch is also reached.
    """
    N_MGR.unload_modules()

    class BrokenModulesDict(dict):
        def __delitem__(self, key):
            raise KeyError(key)

    broken = BrokenModulesDict(sys.modules)
    broken["evict_race_lib_xyz"] = types.ModuleType("evict_race_lib_xyz")
    monkeypatch.setattr(sys, "modules", broken)

    # to_remove = ["evict_race_lib_xyz"]; del raises -> KeyError caught
    # evicted stays 0, to_remove non-empty -> warning branch reached
    N_MGR._evict_library("evict_race_lib_xyz")


def test_load_modules_import_fallback_fails(tmpdir):
    """__import__ raises ImportError and the path-based fallback also
    returns None because the file itself fails to import."""
    N_MGR.unload_modules()

    # A .py file whose top-level import always fails
    tmpdir.join("alwaysfail_xyz.py").write(
        "import this_library_does_not_exist_xyz_abc\n"
    )
    # load_modules uses the default prefix ("apprise.plugins") so
    # __import__("apprise.plugins.alwaysfail_xyz") raises ImportError,
    # then import_module(path, ...) also returns None -> skipped
    N_MGR.load_modules(path=str(tmpdir))
    N_MGR.unload_modules()


def test_load_modules_no_valid_class(tmpdir):
    """Module loads successfully but contains no qualifying class, so
    module_class stays None and the module is skipped."""
    N_MGR.unload_modules()

    # A module with only a docstring: dir() yields nothing that matches
    # module_filter_re (all dunders start with '_') -> empty list ->
    # module_class stays None -> skipped
    tmpdir.join("notifyempty_xyz.py").write('"""Empty module."""\n')

    N_MGR.load_modules(path=str(tmpdir))
    N_MGR.unload_modules()


def test_load_modules_schema_conflict(tmpdir):
    """A schema already registered is logged as a conflict and
    skipped."""
    N_MGR.unload_modules()
    N_MGR.load_modules()  # native load -> "json" in _schema_map

    tmpdir.join("notifyconflict_xyz.py").write(
        cleandoc("""
        from apprise.plugins.base import NotifyBase

        class NotifyConflict(NotifyBase):
            service_name = "Conflict"
            protocol = "json"
            secure_protocol = None
            service_url = "https://example.com"
            setup_url = "https://example.com"
            notify_url = ""
            templates = ('{schema}://',)

            def send(self, body, title="", **kwargs):
                return True

            def url(self, **kwargs):
                return "json://"
    """)
    )

    # __import__("apprise.plugins.notifyconflict_xyz") -> ImportError;
    # fallback loads the file; NotifyConflict.schemas() = {"json"};
    # "json" already in _schema_map -> conflict logged, skipped
    N_MGR.load_modules(path=str(tmpdir))
    N_MGR.unload_modules()
