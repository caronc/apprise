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
"""
Compatibility shim for older imports of :mod:`apprise.locale`.

This module intentionally exists to preserve backward compatibility for
consumers importing ``apprise.locale``. The implementation was moved to
:mod:`apprise.i18n_locale` to avoid clashing with the Python standard library
module named ``locale``.

If this file is accidentally imported as the top-level module ``locale``
(e.g., via a path shadowing issue), we immediately forward the import to the
real Python standard library ``locale`` module.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import sys
from types import ModuleType


def _load_stdlib_locale() -> ModuleType:
    """
    Import and return the Python standard library `locale` module, even if a
    local path entry would otherwise cause this file to be imported.

    Important: when this shim is imported incorrectly as the top-level
    module name `locale`, Python will have already inserted the current module
    into sys.modules["locale"]. We must temporarily remove that entry or an
    import of "locale" will simply return ourselves again.
    """
    pkg_dir = os.path.abspath(os.path.dirname(__file__))
    root_dir = os.path.abspath(os.path.dirname(pkg_dir))

    removed: list[tuple[int, str]] = []
    original = sys.modules.pop("locale", None)

    def _maybe_remove_path(path: str) -> None:
        if not path:
            return
        ap = os.path.abspath(path)
        if ap in (pkg_dir, root_dir):
            idx = sys.path.index(path)
            removed.append((idx, path))
            sys.path.pop(idx)

    try:
        with contextlib.suppress(Exception):
            while pkg_dir in [os.path.abspath(p) for p in sys.path if p]:
                # Remove any direct references to the package directory
                _maybe_remove_path(pkg_dir)

        with contextlib.suppress(Exception):
            while root_dir in [os.path.abspath(p) for p in sys.path if p]:
                # Remove any references to the project root
                _maybe_remove_path(root_dir)

        # Now this should resolve to the stdlib module
        stdlib_locale = importlib.import_module("locale")
        return stdlib_locale

    except Exception:
        # If something goes wrong, restore the prior module reference
        if original is not None:
            sys.modules["locale"] = original
        raise

    finally:
        # Restore sys.path in original positions (stable ordering)
        for idx, value in sorted(removed, key=lambda x: x[0]):
            sys.path.insert(idx, value)


# If this module is imported as *top level* "locale", it is a shadowing bug.
# Immediately swap ourselves for the real stdlib "locale" module.
if __name__ == "locale" and not __package__:
    _stdlib_locale = _load_stdlib_locale()
    sys.modules["locale"] = _stdlib_locale
    globals().update(_stdlib_locale.__dict__)

else:
    # Normal path: preserve backward compatibility for `apprise.locale`
    # consumers by re-exporting the real implementation.
    from . import i18n_locale as _i18n_locale
    from .logger import logger

    # Emit a deprecation warning once per interpreter session.
    logger.deprecate(
        "Importing 'apprise.locale' is deprecated. "
        "Import 'apprise.i18n_locale' instead."
    )

    # Ensure `apprise.locale` resolves to the same module as
    # `apprise.i18n_locale`.
    sys.modules[__name__] = _i18n_locale  # type: ignore[assignment]
    globals().update(_i18n_locale.__dict__)
    del _i18n_locale
