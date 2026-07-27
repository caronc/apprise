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

# Fit plugin dialect conversions to service limits after CommonMark repair.
# Plugins may also reuse these helpers for custom dialect output.

import re

from .commonmark import (
    commonmark_materialize_repair,
    commonmark_repair_chunk,
    commonmark_scan_closer_runs,
    commonmark_scan_repair_region,
)

# Only CommonMark markup can make a longer converted prefix fit again.
# Use it to avoid unnecessary per-position checks for plain text.
_COMMONMARK_MARKUP_RE = re.compile(r"[\\`*_\[\]()<>]")

# Limit repeat checks so results do not depend on CPU speed. Most repaired
# prefixes that fit appear just above the best result, so check more there and
# reserve a few checks for longer prefixes near the other end of the range.
_VERIFY_SCAN_UPWARD_PROBES = 24
_VERIFY_SCAN_DOWNWARD_PROBES = 8


def _longest_fitting_prefix(body, offset, limit, dialect_convert, pending):
    """Return the longest fitting conversion, consumed length, and state.

    Search from ``offset`` while using the remaining body as repair lookahead.
    The consumed length is relative to ``offset`` for easy cursor advancement.
    """
    n = len(body) - offset

    # Cap lookahead because every fitting probe scans it again. Preserve the
    # next character separately so an edge run still sees its true neighbor.
    lookahead_span = min(max(1, limit * 8), 2048)

    def _repair(mid):
        abs_mid = offset + mid
        lookahead_end = abs_mid + lookahead_span
        lookahead = body[abs_mid:lookahead_end]
        boundary_next_ch = body[lookahead_end : lookahead_end + 1] or None
        return commonmark_repair_chunk(
            body[offset:abs_mid],
            pending,
            next_chunk=lookahead or None,
            next_chunk_boundary_ch=boundary_next_ch,
        )

    def _fits(mid):
        candidate, candidate_pending = _repair(mid)
        candidate = dialect_convert(candidate)
        return len(candidate) <= limit, candidate, candidate_pending

    best_converted, best_len, best_pending = "", 0, pending

    # Grow geometrically so both expanding and shrinking conversions find a
    # useful search boundary without starting at the full remaining body.
    probe = min(n, max(1, limit))
    hi = None
    while True:
        fits, candidate, candidate_pending = _fits(probe)
        if not fits:
            hi = probe
            break
        best_converted, best_len, best_pending = (
            candidate,
            probe,
            candidate_pending,
        )
        if probe >= n:
            # The entire remaining body fits -- nothing more to search.
            return best_converted, best_len, best_pending
        probe = min(n, probe * 2)

    # The first failed probe bounds the later verification window.
    first_fail = hi

    # Later checks only need a short range beyond the first failed length.
    verify_end = min(n, first_fail + min(lookahead_span, 24))

    # Scan once so every tested prefix can reuse the parsed sections.
    shared_span = verify_end
    shared_text = body[offset : offset + shared_span + lookahead_span]
    scan_atoms, covered_end, sentinel = commonmark_scan_repair_region(
        shared_text, pending, lookahead_span
    )

    # Index closing ``*`` and ``_`` runs once for the same repeated checks.
    closer_index, closer_covered_end = commonmark_scan_closer_runs(shared_text)

    def _repair_shared(mid):
        # Directly repair prefixes that cannot reuse the shared scan.
        return commonmark_materialize_repair(
            body,
            offset,
            mid,
            pending,
            scan_atoms,
            covered_end,
            sentinel,
            lookahead_span,
            closer_index=closer_index,
            closer_covered_end=closer_covered_end,
        )

    def _fits_shared(mid):
        candidate, candidate_pending = _repair_shared(mid)
        candidate = dialect_convert(candidate)
        return len(candidate) <= limit, candidate, candidate_pending

    # Bisect between the largest fit and first overflow. Dialect repair can
    # occasionally make a longer prefix shorter, so verify that case below.
    lo, hi = best_len + 1, hi - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        fits, candidate, candidate_pending = _fits_shared(mid)
        if fits:
            # This prefix fits. Try a longer one.
            best_converted, best_len, best_pending = (
                candidate,
                mid,
                candidate_pending,
            )
            lo = mid + 1
        else:
            # Too long. Try a shorter prefix.
            hi = mid - 1

    # A longer repaired prefix can become shorter anywhere bisection skipped.
    # Verify back to the best known fit instead of assuming a local boundary.
    # Plain text cannot create a later repaired fit, so skip its scan.
    verify_region = body[offset + best_len : offset + verify_end]
    if _COMMONMARK_MARKUP_RE.search(verify_region):
        # Check above the best result and keep the longest prefix that fits.
        upward_end = min(verify_end, best_len + _VERIFY_SCAN_UPWARD_PROBES)
        best_upward = None
        for mid in range(best_len + 1, upward_end + 1):
            fits, candidate, candidate_pending = _fits_shared(mid)
            if fits:
                best_upward = (candidate, mid, candidate_pending)

        # Check downward; the first fit is the longest in this range.
        for probes, mid in enumerate(
            range(verify_end, upward_end, -1), start=1
        ):
            fits, candidate, candidate_pending = _fits_shared(mid)
            if fits:
                return candidate, mid, candidate_pending
            if probes >= _VERIFY_SCAN_DOWNWARD_PROBES:
                break

        if best_upward is not None:
            return best_upward

    if best_len == 0:
        # Not even a single character fits. Force progress anyway.
        best_converted, best_pending = _repair_shared(1)
        best_converted = dialect_convert(best_converted)
        best_len = 1

    return best_converted, best_len, best_pending


def split_dialect_chunk(body, limit, dialect_convert):
    """Split repaired CommonMark into converted pieces within ``limit``.

    The converter must return the same result for the same input. Longer input
    should usually stay the same length or grow after conversion. Local markup
    repairs may make it shorter.
    """
    if not body:
        return [dialect_convert(body)]

    converted = dialect_convert(body)
    if len(converted) <= limit:
        return [converted]

    pieces = []
    # Advance a cursor to avoid copying the full remaining body per piece.
    n = len(body)
    offset = 0
    # Carry repair state so later pieces consume real closing markers.
    pending = {}
    while offset < n:
        piece, consumed, pending = _longest_fitting_prefix(
            body, offset, limit, dialect_convert, pending
        )
        # Skip redundant empty closers, but always return at least one piece.
        if piece or not pieces:
            pieces.append(piece)
        offset += consumed

    return pieces


def truncate_dialect_chunk(body, limit, dialect_convert):
    """Return the longest converted prefix within ``limit``.

    Truncate mode discards all remaining content.
    """
    if not body:
        return dialect_convert(body)

    converted = dialect_convert(body)
    if len(converted) <= limit:
        return converted

    # Truncate mode has no prior or subsequent repair state.
    piece, _, _ = _longest_fitting_prefix(body, 0, limit, dialect_convert, {})
    return piece
