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
import os
from os.path import expanduser
import platform
import re

from ..logger import logger

# Pre-Escape content since we reference it so much
ESCAPED_PATH_SEPARATOR = re.escape("\\/")
ESCAPED_WIN_PATH_SEPARATOR = re.escape("\\")
ESCAPED_NUX_PATH_SEPARATOR = re.escape("/")

TIDY_WIN_PATH_RE = re.compile(
    rf"(^[{ESCAPED_WIN_PATH_SEPARATOR}]{{2}}|[^{ESCAPED_WIN_PATH_SEPARATOR}\s][{ESCAPED_WIN_PATH_SEPARATOR}]|[\s][{ESCAPED_WIN_PATH_SEPARATOR}]{{2}}])([{ESCAPED_WIN_PATH_SEPARATOR}]+)",
)
TIDY_WIN_TRIM_RE = re.compile(
    rf"^(.+[^:][^{ESCAPED_WIN_PATH_SEPARATOR}])[\s{ESCAPED_WIN_PATH_SEPARATOR}]*$",
)

TIDY_NUX_PATH_RE = re.compile(
    rf"([{ESCAPED_NUX_PATH_SEPARATOR}])([{ESCAPED_NUX_PATH_SEPARATOR}]+)",
)

# A simple path decoder we can re-use which looks after
# ensuring our file info is expanded correctly when provided
# a path.
__PATH_DECODER = (
    os.path.expandvars
    if platform.system() == "Windows"
    else os.path.expanduser
)


def path_decode(path):
    """Returns the fully decoded path based on the operating system."""
    return os.path.abspath(__PATH_DECODER(path))


def tidy_path(path):
    """Take a filename and or directory and attempts to tidy it up by removing
    trailing slashes and correcting any formatting issues.

    For example: ////absolute//path// becomes:
        /absolute/path
    """
    # Windows
    path = TIDY_WIN_PATH_RE.sub("\\1", path.strip())
    # Linux
    path = TIDY_NUX_PATH_RE.sub("\\1", path)

    # Windows Based (final) Trim
    path = expanduser(TIDY_WIN_TRIM_RE.sub("\\1", path))
    return path


def dir_size(path, max_depth=3, missing_okay=True, _depth=0, _errors=None):
    """Scans a provided path an returns it's size (in bytes) of path
    provided."""

    if _errors is None:
        _errors = set()

    if _depth > max_depth:
        _errors.add(path)
        return (0, _errors)

    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size

                    elif entry.is_dir(follow_symlinks=False):
                        (totals, _) = dir_size(
                            entry.path,
                            max_depth=max_depth,
                            _depth=_depth + 1,
                            _errors=_errors,
                        )
                        total += totals

                except FileNotFoundError:
                    # no worries; Nothing to do
                    continue

                except OSError as e:
                    # Permission error of some kind or disk problem...
                    # There is nothing we can do at this point
                    _errors.add(entry.path)
                    logger.warning(
                        "dir_size detetcted inaccessible path: %s",
                        os.fsdecode(entry.path),
                    )
                    logger.debug(f"dir_size Exception: {e!s}")
                    continue

    except FileNotFoundError:
        if not missing_okay:
            # Conditional error situation
            _errors.add(path)

    except OSError as e:
        # Permission error of some kind or disk problem...
        # There is nothing we can do at this point
        _errors.add(path)
        logger.warning(
            "dir_size detetcted inaccessible path: %s", os.fsdecode(path)
        )
        logger.debug(f"dir_size Exception: {e!s}")

    return (total, _errors)


def bytes_to_str(value):
    """Covert an integer (in bytes) into it's string representation with
    acompanied unit value (such as B, KB, MB, GB, TB, etc)"""
    unit = "B"
    try:
        value = float(value)

    except (ValueError, TypeError):
        return None

    if value >= 1024.0:
        value = value / 1024.0
        unit = "KB"
        if value >= 1024.0:
            value = value / 1024.0
            unit = "MB"
            if value >= 1024.0:
                value = value / 1024.0
                unit = "GB"
                if value >= 1024.0:
                    value = value / 1024.0
                    unit = "TB"

    return f"{round(value, 2):.2f}{unit}"
