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

# Support Python-Markdown 3.3 as shipped with Rocky Linux 9.

from html import escape
import re

from markdown import Markdown
from markdown.postprocessors import Postprocessor
from markdown.util import ETX, STX

# A backslash-escaped character that Python-Markdown left as a placeholder
_ESCAPED_PLACEHOLDER_RE = re.compile(f"{STX}([0-9]+){ETX}")


class _UnescapePostprocessor(Postprocessor):
    """Restore backslash-escaped characters as valid HTML."""

    def run(self, text: str) -> str:
        """Replace each escape placeholder with its HTML-safe character."""
        # Python-Markdown 3.3 restores these after the HTML is built, so
        # "\&" or "\<" came back raw.  Newer releases leave nothing to
        # replace here.
        return _ESCAPED_PLACEHOLDER_RE.sub(
            lambda m: escape(chr(int(m.group(1))), quote=False), text
        )


def escape_placeholders_as_html(md: Markdown) -> None:
    """Make ``md`` write backslash-escaped characters as valid HTML."""
    # This replaces Python-Markdown 3.3's own step of the same name.
    md.postprocessors.register(_UnescapePostprocessor(md), "unescape", 10)
