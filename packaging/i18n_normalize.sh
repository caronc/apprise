#!/usr/bin/sh
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
#
# Operations performed:
#   1) Merge duplicates: msguniq --use-first
#   2) Drop obsolete entries: msgattrib --no-obsolete
#   3) Validate: msgfmt --check
#
# This script is intended for developer/build tooling (tox/release).
set -eu

ROOT="${1:-apprise/i18n}"

command -v msguniq   >/dev/null 2>&1 || { echo "Missing msguniq (gettext)"; exit 1; }
command -v msgattrib >/dev/null 2>&1 || { echo "Missing msgattrib (gettext)"; exit 1; }
command -v msgfmt    >/dev/null 2>&1 || { echo "Missing msgfmt (gettext)"; exit 1; }

# Find .po files; exit cleanly if none exist
PO_FILES=$(find "${ROOT}" -type f -name '*.po' 2>/dev/null || true)
[ -n "${PO_FILES}" ] || exit 0

for po in ${PO_FILES}; do
    # Merge duplicates deterministically (tolerates duplicates by design)
    msguniq --use-first -o "${po}" "${po}"
    # Optionally drop obsolete entries afterwards
    msgattrib --no-obsolete -o "${po}" "${po}"
    # Validate
    msgfmt --check -o /dev/null "${po}"
done

echo "Normalised and validated PO files under ${ROOT}"
