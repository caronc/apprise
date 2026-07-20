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

# Conversion is split by format, HTML, CommonMark repair, and dialect fitting.
# Supported helpers are re-exported from ``apprise.conversion``.
from .commonmark import (
    commonmark_can_close_emphasis,
    commonmark_can_open_emphasis,
    commonmark_emphasis_run,
    commonmark_escape_link_url,
    commonmark_find_backtick_run,
    commonmark_index_backtick_runs,
    commonmark_lookahead_closer_widths,
    commonmark_match_emphasis,
    commonmark_materialize_repair,
    commonmark_new_scan_budget,
    commonmark_pick_emphasis_sentinel,
    commonmark_render_emphasis_events,
    commonmark_render_emphasis_markers,
    commonmark_repair_chunk,
    commonmark_scan_angle_dest,
    commonmark_scan_autolink_dest,
    commonmark_scan_closer_runs,
    commonmark_scan_delimiter_run,
    commonmark_scan_paren_dest,
    commonmark_scan_repair_region,
)
from .dialect import split_dialect_chunk, truncate_dialect_chunk
from .format import (
    convert_between,
    html_to_markdown,
    html_to_text,
    markdown_to_html,
    text_to_html,
    text_to_markdown,
)
from .html import (
    BLOCKQUOTE_DEPTH_MAX,
    LIST_DEPTH_MAX,
    MAX_FRAME_DEPTH,
    HTMLConverter,
    HTMLMarkdownConverter,
)

__all__ = [
    "BLOCKQUOTE_DEPTH_MAX",
    "LIST_DEPTH_MAX",
    "MAX_FRAME_DEPTH",
    "HTMLConverter",
    "HTMLMarkdownConverter",
    "commonmark_can_close_emphasis",
    "commonmark_can_open_emphasis",
    "commonmark_emphasis_run",
    "commonmark_escape_link_url",
    "commonmark_find_backtick_run",
    "commonmark_index_backtick_runs",
    "commonmark_lookahead_closer_widths",
    "commonmark_match_emphasis",
    "commonmark_materialize_repair",
    "commonmark_new_scan_budget",
    "commonmark_pick_emphasis_sentinel",
    "commonmark_render_emphasis_events",
    "commonmark_render_emphasis_markers",
    "commonmark_repair_chunk",
    "commonmark_scan_angle_dest",
    "commonmark_scan_autolink_dest",
    "commonmark_scan_closer_runs",
    "commonmark_scan_delimiter_run",
    "commonmark_scan_paren_dest",
    "commonmark_scan_repair_region",
    "convert_between",
    "html_to_markdown",
    "html_to_text",
    "markdown_to_html",
    "split_dialect_chunk",
    "text_to_html",
    "text_to_markdown",
    "truncate_dialect_chunk",
]
