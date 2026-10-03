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

import concurrent.futures as cf
import contextlib
import gc
import logging
import mimetypes
import os
import sys
from types import ModuleType
import warnings

import pytest

from apprise import (
    AttachmentManager,
    ConfigurationManager,
    NotificationManager,
)
import apprise.apprise as apprise_module
from apprise.logger import logger as apprise_logger
from apprise.utils.singleton import Singleton

sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()
# Grant access to our Config Manager Singleton
C_MGR = ConfigurationManager()
# Grant access to our Attachment Manager Singleton
A_MGR = AttachmentManager()

# Packages whose module globals are restored after each test
RESTORED_PACKAGES = ("apprise", "helpers")


def is_restored_module(name):
    """True for Apprise, test helper and test file modules."""
    # Match the top-level package exactly so apprise_extra is left alone.
    top = name.partition(".")[0]
    return top in RESTORED_PACKAGES or top.startswith("test_")


def restore_module_globals(snapshot):
    """Restore module globals changed by reload().

    This keeps class identities stable between tests on the same worker.
    """
    # Restore replaced globals, but keep module references in sync with
    # sys.modules.
    changed = False
    for current, saved in snapshot.values():
        for key, value in saved.items():
            if current.get(key) is not value and not isinstance(
                value, ModuleType
            ):
                current[key] = value
                changed = True

    if not changed:
        # No reload cleanup is needed.
        return

    # A module global that no longer matches sys.modules still points at a
    # fake or replaced module, such as a mocked gi.  Put back what was there.
    for current, saved in snapshot.values():
        for key, value in current.copy().items():
            if (
                not isinstance(value, ModuleType)
                or sys.modules.get(value.__name__) is value
            ):
                continue

            if key in saved:
                current[key] = saved[key]

            else:
                current.pop(key, None)

    # A reload builds a new manager class, and its singleton instance would
    # keep the old plugin modules alive.  Keep only the current classes.
    for cls in list(Singleton._instances):
        module = sys.modules.get(cls.__module__)
        if getattr(module, cls.__name__, None) is not cls:
            Singleton._instances.pop(cls, None)

    # Drop modules created from reloaded classes so they are rebuilt later.
    # Copy the names first since a background thread may still import.
    for name in [
        name
        for name in sys.modules.copy()
        if is_restored_module(name) and name not in snapshot
    ]:
        module = sys.modules.pop(name, None)
        if module is None:
            # Another thread already removed it.
            continue

        # Also remove the reference held by its parent package.  Another
        # thread may remove it first, which is fine.
        parent, _, attr = name.rpartition(".")
        parent_module = sys.modules.get(parent)
        if getattr(parent_module, attr, None) is module:
            with contextlib.suppress(AttributeError):
                delattr(parent_module, attr)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    """Remember shared state before any fixture of the test runs."""
    # Save the globals from project and test modules.  copy() takes the
    # module list in one step, so a cleanup that imports cannot change it
    # part way through.
    item._apprise_modules = {
        name: (module.__dict__, dict(module.__dict__))
        for name, module in sys.modules.copy().items()
        if is_restored_module(name) and module is not None
    }

    # Calls left by earlier tests were already waited on and reported.
    with apprise_module._abandoned_futures_lock:
        item._apprise_earlier_calls = {
            future for future, _, _ in apprise_module._abandoned_futures
        }

    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """Clean up shared state around the test's own fixture teardown."""
    # Timed-out calls keep running after notify(), so wait for this test's
    # while its mocks and patches are still in place.
    # Take the saved state off the item, since pytest keeps every item for
    # the whole run and the copies would otherwise stay in memory.
    earlier = item.__dict__.pop("_apprise_earlier_calls", set())
    snapshot = item.__dict__.pop("_apprise_modules", None)

    with apprise_module._abandoned_futures_lock:
        running = [
            future
            for future, _, _ in apprise_module._abandoned_futures
            if future not in earlier
        ]

    # Keep calls that exceed the timeout tracked as leaks, reported once.
    _, still_running = cf.wait(running, timeout=10)

    # Let every fixture, monkeypatch and mock undo itself first.
    yield

    # sys.modules is back to normal now, so module globals can be checked
    # against it.
    if snapshot:
        restore_module_globals(snapshot)

    # Warn last, so a warning treated as an error cannot skip the cleanup.
    if still_running:
        warnings.warn(
            f"{len(still_running)} background service call(s) still "
            "running 10s after the test finished.",
            ResourceWarning,
            stacklevel=1,
        )


@pytest.fixture(scope="function", autouse=True)
def mimetypes_always_available():
    """Use the test MIME database for every test."""
    files = (os.path.join(os.path.dirname(__file__), "var", "mime.types"),)
    mimetypes.init(files=files)


@pytest.fixture(scope="function", autouse=True)
def no_throttling_everywhere(mocker):
    """Disable plugin throttling for every test.

    Function-scoped cleanup prevents patches from accumulating across the
    suite and slowing final teardown.
    """
    # Ensure we're working with a clean slate for each test
    N_MGR.unload_modules()
    C_MGR.unload_modules()
    A_MGR.unload_modules()

    for plugin in N_MGR.plugins():
        mocker.patch.object(plugin, "request_rate_per_sec", 0)


@pytest.fixture(scope="function", autouse=True)
def _reset_apprise_logger_state():
    """Reset shared logger state around every test.

    CLI tests change the Apprise and asyncio loggers. Restoring their levels
    and handlers prevents those changes from affecting later log assertions.
    """
    asyncio_logger = logging.getLogger("asyncio")

    original_level = apprise_logger.level
    original_handlers = list(apprise_logger.handlers)
    original_asyncio_level = asyncio_logger.level
    original_asyncio_handlers = list(asyncio_logger.handlers)

    # Many tests switch logging back on with logging.disable(NOTSET).  Put
    # the global level back afterwards so the next test is not affected.
    original_disable = logging.root.manager.disable

    apprise_logger.setLevel(logging.NOTSET)
    asyncio_logger.setLevel(logging.NOTSET)
    asyncio_logger.handlers[:] = []
    yield
    apprise_logger.setLevel(original_level)
    apprise_logger.handlers[:] = original_handlers
    asyncio_logger.setLevel(original_asyncio_level)
    asyncio_logger.handlers[:] = original_asyncio_handlers
    logging.disable(original_disable)


@pytest.fixture(scope="function", autouse=True)
def collect_all_garbage():
    """Collect garbage after each test to isolate plugin finalizers."""
    # Force garbage collection
    gc.collect()
