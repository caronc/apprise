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

"""Check that every built wheel carries each compiled translation catalog.

Run it from the repository root after building:

    python packaging/verify_translations.py

- Apprise only reads compiled ``.mo`` files.  Without them, every language
  falls back to English.
- Every ``.po`` file in the source tree needs a matching ``.mo`` in each
  wheel in ``dist/``.
- Anything missing is listed and the script exits with an error.
"""

from __future__ import annotations

import argparse
from glob import glob
from os.path import abspath, basename, dirname, join
import sys
from typing import Optional
import zipfile

# The repository root, one level up from this script
ROOT_DIR = abspath(join(dirname(__file__), ".."))

# Where our translations live in the source tree
I18N_DIR = join(ROOT_DIR, "apprise", "i18n")


def expected_catalogs() -> list[str]:
    """The wheel path of each compiled catalog a release must carry."""
    # One per language with a catalog in the source tree
    catalogs = []
    for po_path in sorted(glob(join(I18N_DIR, "*", "LC_MESSAGES", "*.po"))):
        # e.g. apprise/i18n/fr/LC_MESSAGES/apprise.mo
        language = basename(dirname(dirname(po_path)))
        name = basename(po_path)[:-3] + ".mo"
        catalogs.append(f"apprise/i18n/{language}/LC_MESSAGES/{name}")

    return catalogs


def missing_catalogs(wheel_path: str, expected: list[str]) -> list[str]:
    """The expected compiled catalogs that ``wheel_path`` does not carry."""
    # Read the wheel's file listing
    with zipfile.ZipFile(wheel_path) as wheel:
        present = set(wheel.namelist())

    return [catalog for catalog in expected if catalog not in present]


def main(argv: Optional[list[str]] = None) -> int:
    """Checks every wheel in the dist folder and reports the outcome."""
    # Prepare our arguments
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "dist",
        nargs="?",
        default=join(ROOT_DIR, "dist"),
        help="folder holding the built wheels (default: dist)",
    )
    args = parser.parse_args(argv)

    # There is nothing to check without a wheel
    wheels = sorted(glob(join(args.dist, "*.whl")))
    if not wheels:
        print(f"No wheel found in {args.dist}")
        return 1

    # Every wheel must carry every language
    expected = expected_catalogs()
    failed = False
    for wheel_path in wheels:
        missing = missing_catalogs(wheel_path, expected)
        if missing:
            failed = True
            name = basename(wheel_path)
            print(f"{name} is missing {len(missing)} catalogs:")
            for catalog in missing:
                print(f"  - {catalog}")

        else:
            print(
                f"{basename(wheel_path)} carries all "
                f"{len(expected)} translation catalogs"
            )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
