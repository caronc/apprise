# BSD 2-Clause License
#
# Copyright (c) 2025, Chris Caron
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

from __future__ import annotations

import importlib
import os
import sys
from types import ModuleType

import pytest

from apprise.logger import LogCapture, logging


def test_apprise_locale_is_compat_alias() -> None:
    """
    Verify `apprise.locale` remains importable for backwards compatibility,
    and maps to the same implementation as `apprise.i18n_locale`.
    """
    import apprise.i18n_locale as i18n_locale
    import apprise.locale as compat_locale

    assert compat_locale is i18n_locale
    assert sys.modules["apprise.locale"] is i18n_locale
    assert hasattr(compat_locale, "AppriseLocale")
    assert hasattr(compat_locale.AppriseLocale, "detect_language")
    assert hasattr(compat_locale, "LOCALE")


def test_locale_shadowing_resolves_to_stdlib(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verify that when the Apprise package directory is placed on sys.path
    (a situation that can cause accidental stdlib `locale` shadowing),
    importing `locale` still yields the standard library module, not
    `apprise/locale.py`.
    """
    # Import apprise to locate the package directory on disk
    import apprise as apprise_pkg

    pkg_dir = os.path.abspath(os.path.dirname(apprise_pkg.__file__))

    # Save original state so we can restore cleanly
    original_sys_path = list(sys.path)
    original_locale_mod = sys.modules.get("locale")

    try:
        # Force the exact shadowing scenario:
        # Put the *package directory* first, so `import locale` would find
        # apprise/locale.py if the shim did not defend against it.
        sys.path.insert(0, pkg_dir)

        # Ensure a fresh import resolution
        sys.modules.pop("locale", None)

        stdlib_locale = importlib.import_module("locale")
        assert isinstance(stdlib_locale, ModuleType)
        assert stdlib_locale.__name__ == "locale"

        # If shadowing occurred, __file__ would end with
        # ".../apprise/locale.py"
        # The shim should instead have swapped in the stdlib module.
        mod_file = getattr(stdlib_locale, "__file__", "") or ""
        assert not mod_file.endswith(os.path.join("apprise", "locale.py"))

        # Basic sanity check that we got the real stdlib module
        assert hasattr(stdlib_locale, "getlocale")
        assert hasattr(stdlib_locale, "setlocale")

        # Also verify the path manipulation is not left in a broken state
        assert sys.path[0] == pkg_dir

    finally:
        # Restore sys.path
        sys.path[:] = original_sys_path

        # Restore the previous locale module reference if there was one
        sys.modules.pop("locale", None)
        if original_locale_mod is not None:
            sys.modules["locale"] = original_locale_mod


def test_apprise_locale_emits_deprecation_warning() -> None:
    """
    Ensure Deprication warning is in place for apprise.locale
    """
    sys.modules.pop("apprise.locale", None)
    sys.modules.pop("apprise.i18n_locale", None)

    # If the test suite globally disabled logging, we must re-enable it
    # temporarily or LogCapture will never see anything.
    previous_disable = logging.root.manager.disable
    logging.disable(0)
    try:
        with LogCapture(level=logging.DEPRECATE) as captured:
            importlib.import_module("apprise.locale")
    finally:
        logging.disable(previous_disable)

    out = captured.getvalue()
    assert "deprecated" in out.lower()
    assert "apprise.i18n_locale" in out
