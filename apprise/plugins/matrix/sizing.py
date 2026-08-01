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

"""Matrix event sizing helpers."""

import contextvars
from json import dumps

from ...common import NotifyFormat
from .e2ee import predict_megolm_ciphertext_len

# Matrix's hard event-size ceiling.
# https://spec.matrix.org/v1.11/client-server-api/#size-limits
MATRIX_EVENT_BYTE_LIMIT = 65536

# Reserve room for fields Apprise doesn't control: homeserver-added event
# metadata (event_id, origin_server_ts, sender, age, unsigned, and -- once
# federated -- signatures) and small JSON punctuation slop. The title and
# device_id are measured exactly elsewhere, not guessed here.
MATRIX_EVENT_SAFETY_MARGIN = 4000

# Allow for the JSON fields around plaintext or encrypted message content.
MATRIX_CONTENT_JSON_OVERHEAD = 200

# sender_key/session_id are always the unpadded base64 of a 32-byte
# Curve25519/Ed25519 key -- exactly 43 characters regardless of value.
MATRIX_E2EE_KEY_LEN = 43

# device_id has no length limit in the Matrix spec and is server-assigned,
# so it cannot be measured before the first login on a fresh connection.
# This generous fallback covers any realistic device_id when its real
# value isn't known yet at sizing time; a known device_id is measured
# exactly instead (see device_id_overhead_bytes()).
MATRIX_DEVICE_ID_FALLBACK_BYTES = 512

# Exact JSON structural overhead of an m.room.encrypted payload's
# fixed-shape fields, excluding the ciphertext and device_id values --
# both measured separately since they vary per send. Computed once here
# instead of guessed, using a placeholder of the guaranteed key length.
MATRIX_E2EE_ENVELOPE_STRUCTURAL_BYTES = len(
    dumps(
        {
            "algorithm": "m.megolm.v1.aes-sha2",
            "ciphertext": "",
            "sender_key": "x" * MATRIX_E2EE_KEY_LEN,
            "session_id": "x" * MATRIX_E2EE_KEY_LEN,
            "device_id": "",
        },
        ensure_ascii=False,
    ).encode("utf-8")
)

# Share the calculated limit with the framework's body_maxlen property.
# Context-local storage keeps concurrent notifications isolated.
effective_body_maxlen = contextvars.ContextVar(
    "matrix_effective_body_maxlen", default=None
)


def utf8_char_len(ch):
    """Return the UTF-8 byte length of a single character."""
    # Use the code point range to determine its encoded width.
    cp = ord(ch)

    # ASCII occupies one byte.
    if cp <= 0x7F:
        return 1

    # Extended Latin and similar characters occupy two bytes.
    if cp <= 0x7FF:
        return 2

    # Characters in the basic multilingual plane occupy three bytes.
    if cp <= 0xFFFF:
        return 3

    # Supplementary characters such as emoji occupy four bytes.
    return 4


def sanitize_text(text):
    """Replace lone UTF-16 surrogates so text can be UTF-8 encoded.

    Sanitizing before sizing keeps the calculation aligned with delivery.
    """
    # Preserve empty and absent values without allocating a new string.
    if not text:
        return text

    # Replace invalid code points while preserving normal Unicode.
    return text.encode("utf-8", errors="replace").decode("utf-8")


def rstrip_end(text):
    """Find the end of ``text.rstrip()`` without copying the input."""
    # Walk backward until the last meaningful character is found.
    end = len(text)
    while end > 0 and text[end - 1].isspace():
        end -= 1

    # The caller can safely slice up to this position.
    return end


def strip_bounds(text):
    """Find the bounds of ``text.strip()`` without copying the input."""
    # Find the first non-whitespace character.
    length = len(text)
    start = 0
    while start < length and text[start].isspace():
        start += 1

    # Find the last non-whitespace character.
    end = length
    while end > start and text[end - 1].isspace():
        end -= 1

    # These indexes describe the same result as text.strip().
    return start, end


def json_char_bytes(ch):
    """Return a character's UTF-8 cost after JSON string escaping."""
    # Quotes and backslashes gain a leading escape character.
    if ch in ('"', "\\"):
        return 2

    # Common control characters use their short escapes.
    if ch in ("\b", "\f", "\n", "\r", "\t"):
        return 2

    # Remaining control characters use the six-byte Unicode form.
    if ord(ch) < 0x20:
        return 6

    # All other characters retain their normal UTF-8 width.
    return utf8_char_len(ch)


def max_byte_budget(cost_fn, byte_budget, ceiling):
    """Find the largest input accepted by a non-decreasing cost function."""
    # Stop when the fixed event structure is already too large.
    if cost_fn(0) > byte_budget:
        return 0

    # Search the permitted raw-byte range.
    low, high = 0, ceiling
    while low < high:
        # Bias upward so a two-value range continues to make progress.
        middle = (low + high + 1) // 2

        # Keep fitting values and discard values that exceed the budget.
        if cost_fn(middle) <= byte_budget:
            low = middle
        else:
            high = middle - 1

    # Both bounds now identify the largest fitting value.
    return low


def fit_char_limit(body, byte_budget, cost_fn):
    """Return a character limit safe for every chunk in ``body``.

    A linear sliding window protects dense regions rather than averages.
    """
    # Empty messages still need a positive framework limit.
    length = len(body)
    if length == 0:
        return 1

    # This ceiling covers rich representations and encryption growth.
    ceiling = byte_budget * 16 + 1024
    raw_byte_target = max_byte_budget(cost_fn, byte_budget, ceiling)

    # Track the JSON-escaped window and its left edge.
    window_sum = 0
    left = 0
    shortest_over = None

    for right, ch in enumerate(body):
        # Add the next character to the active window.
        window_sum += json_char_bytes(ch)

        # Shrink until the active window fits again.
        while window_sum > raw_byte_target:
            window_length = right - left + 1

            # The shortest overflowing window defines the safe limit.
            if shortest_over is None or window_length < shortest_over:
                shortest_over = window_length

            # Remove the leftmost character before advancing the window.
            window_sum -= json_char_bytes(body[left])
            left += 1

    # No window overflow means the complete body already fits.
    if shortest_over is None:
        return length

    # One less than the shortest overflow is safe for every chunk.
    return max(1, shortest_over - 1)


def payload_budget(asset, title_len, body_len):
    """Mirror the asset payload cap using lengths only.

    The asset still applies the authoritative cap to the original strings.
    """
    # Read the optional combined title and body limit from the asset.
    cap = asset._payload_max_size

    # A disabled cap leaves both inputs untouched.
    if not cap:
        return title_len, body_len

    # Content already within the cap needs no allocation.
    total = title_len + body_len
    if total <= cap:
        return title_len, body_len

    # Give the full budget to the only nonempty side.
    if not title_len:
        return 0, cap

    if not body_len:
        return cap, 0

    # Short inputs may be preserved when the other side keeps enough room.
    threshold = asset._payload_buffer_threshold
    min_buffer = asset._payload_min_buffer

    # Keep a short title whole when the body retains its minimum allowance.
    if title_len <= threshold:
        body_reserve = min(body_len, min_buffer)
        if title_len + body_reserve <= cap:
            return title_len, cap - title_len

    # Apply the same preference when the body is the short side.
    if body_len <= threshold:
        title_reserve = min(title_len, min_buffer)
        if body_len + title_reserve <= cap:
            return cap - body_len, body_len

    # Otherwise divide the cap in proportion to the original lengths.
    title_budget = (title_len * cap) // total
    body_budget = cap - title_budget

    # Preserve at least one title character when the cap permits it.
    if not title_budget and body_budget > 0:
        title_budget = 1
        body_budget -= 1

    # Both budgets always add back up to the configured cap.
    return title_budget, body_budget


def payload_preview(asset, body, title):
    """Build the bounded, normalized preview used for event sizing."""
    # Locate trim boundaries without copying large inputs.
    title_start, title_end = strip_bounds(title) if title else (0, 0)
    title_len = title_end - title_start
    body_len = rstrip_end(body) if body else 0

    # Match the asset's cap allocation before materializing either slice.
    title_limit, body_limit = payload_budget(asset, title_len, body_len)
    preview_title = (
        "" if not title else title[title_start : title_start + title_limit]
    )
    preview_body = "" if not body else body[:body_limit]

    # Sanitize only the bounded copies used by the sizing scan.
    return sanitize_text(preview_body), sanitize_text(preview_title)


def device_id_overhead_bytes(device_id):
    """Return a device ID's JSON byte cost or a conservative fallback."""
    # Fresh logins do not expose the device ID until after initial sizing.
    if not device_id:
        return MATRIX_DEVICE_ID_FALLBACK_BYTES

    # Include any JSON escaping required by the known ID.
    return sum(json_char_bytes(ch) for ch in device_id)


def title_overhead_bytes(title, body_format, escape_html):
    """Return the JSON byte cost added by Matrix title wrappers."""
    # An absent title adds no wrapper or content bytes.
    if not title:
        return 0

    # Plain messages include the title once.
    plain_wrapper = f"# {title}\r\n"
    plain_bytes = sum(json_char_bytes(ch) for ch in plain_wrapper)

    # Plain messages do not carry a second title representation.
    if body_format not in (NotifyFormat.HTML, NotifyFormat.MARKDOWN):
        return plain_bytes

    # Rich messages include a second HTML title.
    title_html = (
        title
        if body_format == NotifyFormat.HTML
        else escape_html(title, whitespace=False)
    )
    formatted_wrapper = f"<h1>{title_html}</h1>"

    # Rich messages pay for both the plain and formatted titles.
    return plain_bytes + sum(json_char_bytes(ch) for ch in formatted_wrapper)


def wire_cost(
    content_bytes,
    body_format,
    e2ee_capable,
    title_bytes,
    device_id,
):
    """Estimate a chunk's final Matrix event size."""
    # Rich messages carry both plain and formatted representations.
    multiplier = (
        2 if body_format in (NotifyFormat.HTML, NotifyFormat.MARKDOWN) else 1
    )

    # Combine message representations, title wrappers, and fixed JSON fields.
    inner_bytes = (
        content_bytes * multiplier + title_bytes + MATRIX_CONTENT_JSON_OVERHEAD
    )

    # Unencrypted events stop at the inner content estimate.
    if not e2ee_capable:
        return inner_bytes

    # E2EE adds MegOLM growth and the outer encrypted-event fields.
    return (
        predict_megolm_ciphertext_len(inner_bytes)
        + MATRIX_E2EE_ENVELOPE_STRUCTURAL_BYTES
        + device_id_overhead_bytes(device_id)
    )


def body_char_limit(
    body,
    title,
    body_format,
    e2ee_capable,
    device_id,
    escape_html,
):
    """Calculate the safe Matrix body limit for one notification."""
    # Measure the title once because every candidate chunk shares it.
    title_bytes = title_overhead_bytes(title, body_format, escape_html)

    # Convert each possible content size into its final event estimate.
    def cost_fn(content_bytes):
        return wire_cost(
            content_bytes,
            body_format,
            e2ee_capable,
            title_bytes,
            device_id,
        )

    # Leave room for metadata added after Apprise submits the content.
    byte_budget = MATRIX_EVENT_BYTE_LIMIT - MATRIX_EVENT_SAFETY_MARGIN

    # Find the character count that keeps every body chunk within budget.
    return fit_char_limit(body, byte_budget, cost_fn)
