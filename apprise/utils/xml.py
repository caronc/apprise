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
import re
from xml.etree import ElementTree


def flatten_xml_response(xml_response, keep_map, defaults=None):
    """Turns a small, flat XML response (like the ones AWS SES/SNS send
    back) into a plain dictionary.

    - `keep_map` maps an XML tag name to the dictionary key its text
      should be stored under, e.g. {"RequestId": "request_id"}.
    - `defaults` seeds the returned dictionary (and is never mutated),
      so callers can guarantee certain keys always exist even when the
      response never mentions them. `type` is always set to the name
      of the root tag.
    - Any surrounding XML namespace on the root tag is stripped first,
      since it otherwise has to be repeated on every tag name we look
      for.
    - Walks the tree with an explicit stack instead of recursion, so
      an unusually deep response can't blow up with a RecursionError.
    - A tag with no text at all (e.g. `<Message/>`) is treated as an
      empty string rather than raising.

    Bad input (not a string, not parseable XML) just yields the
    defaults back with `type` left as None.
    """
    response = dict(defaults) if defaults else {}
    response["type"] = None

    try:
        # Strip any surrounding XML namespace from the root tag.
        root = ElementTree.fromstring(
            re.sub(r' xmlns="[^"]+"', "", xml_response, count=1)
        )

    except (ElementTree.ParseError, TypeError):
        # bad data just causes us to generate a bad response
        return response

    # Set the response type to the root tag name.
    response["type"] = str(root.tag)

    # Walk the tree with an explicit stack instead of recursion.
    stack = [root]
    while stack:
        element = stack.pop()
        if len(element) > 0:
            # Reverse children so the stack still visits them in document
            # order, matching the original recursive parser.
            stack.extend(reversed(element))

        elif element.tag in keep_map:
            response[keep_map[element.tag]] = (element.text or "").strip()

    return response
