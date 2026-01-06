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

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Optional

# adding to this table just shortlists keys to scan deeper into for
# a faster response.
_BLOB_KEYWORDS = (
    "base64",
    "attachment",
    "attachments",
    "contentbytes",
    "blob",
    "file",
    "data",
    "image",
    "media",
    "document",
)


@dataclass(frozen=True)
class SanitizeOptions:
    max_depth: int = 10
    max_items: int = 2000

    # Strings longer than this are summarized
    max_str_len: int = 2048

    # Preview size for summarized strings
    preview: int = 64

    # Bound hashing work
    hash_sample_size: int = 8192

    # If True, summarize values under blob-like keys even if they are smaller
    aggressive_blob_keys: bool = True


def sanitize_payload(
        value: Any, *, options: Optional[SanitizeOptions] = None) -> Any:
    opts = options or SanitizeOptions()
    seen_ids: set[int] = set()
    items_seen = 0

    def _hash_bytes(b: bytes) -> str:
        if len(b) > opts.hash_sample_size:
            b = b[: opts.hash_sample_size]
        return sha256(b).hexdigest()[:12]

    def _summarize_str(s: str) -> str:
        nonlocal items_seen
        items_seen += 1

        length = len(s)
        if length <= opts.max_str_len:
            return s

        head = s[: opts.preview]
        tail = s[-opts.preview :] if length >= opts.preview else s
        return f"<string len={length} head={head!r} tail={tail!r}>"

    def _summarize_bytes(b: bytes) -> str:
        nonlocal items_seen
        items_seen += 1
        return f"<bytes len={len(b)} sha256={_hash_bytes(b)}>"

    def _is_blob_key(k: str) -> bool:
        lk = k.lower()
        return any(word in lk for word in _BLOB_KEYWORDS)

    def _walk(obj: Any, depth: int, *, blob_mode: bool = False) -> Any:
        nonlocal items_seen

        if items_seen >= opts.max_items:
            return "<truncated: global item limit reached>"
        if depth > opts.max_depth:
            return "<truncated: max depth reached>"

        if obj is None or isinstance(obj, (bool, int, float)):
            items_seen += 1
            return obj

        if isinstance(obj, str):
            if blob_mode and opts.aggressive_blob_keys:
                # Always summarize blob fields, even if not huge
                length = len(obj)
                head = obj[: opts.preview]
                tail = obj[-opts.preview :] if length >= opts.preview else obj
                items_seen += 1
                return (
                    f"<blob-string len={length} head={head!r} tail={tail!r}>")
            return _summarize_str(obj)

        if isinstance(obj, bytes):
            return _summarize_bytes(obj)

        obj_id = id(obj)
        if obj_id in seen_ids:
            return "<recursive>"
        seen_ids.add(obj_id)

        if isinstance(obj, dict):
            out: dict[Any, Any] = {}
            for k, v in obj.items():
                if items_seen >= opts.max_items:
                    out["<truncated>"] = "..."
                    break

                # Preserve key readability, but avoid huge key dumps
                sk = _summarize_str(k) if isinstance(k, str) \
                    else (_summarize_bytes(k) if isinstance(k, bytes) else k)

                # Enable blob mode for suspicious keys
                child_blob_mode = blob_mode
                if isinstance(k, str) and _is_blob_key(k):
                    child_blob_mode = True

                out[sk] = _walk(v, depth + 1, blob_mode=child_blob_mode)
            return out

        if isinstance(obj, (list, tuple, set, frozenset)):
            out_list: list[Any] = []
            for entry in obj:
                if items_seen >= opts.max_items:
                    out_list.append("<truncated: limit reached>")
                    break
                out_list.append(_walk(entry, depth + 1, blob_mode=blob_mode))

            if isinstance(obj, tuple):
                return tuple(out_list)
            return out_list

        items_seen += 1
        return repr(obj)

    return _walk(value, 0)
