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

from __future__ import annotations

from typing import Any, Optional
from xml.parsers import expat


class _Element:
    """One element that has been opened but not yet closed."""

    __slots__ = ("leaf", "tag", "text")

    def __init__(self, tag: str) -> None:
        # The element's name, exactly as the document spells it.
        self.tag = tag

        # Text arrives in one or more pieces and is joined on close.
        self.text: list[str] = []

        # Cleared the moment a child element opens beneath this one.
        self.leaf = True


def flatten_xml_response(
    xml_response: Optional[str],
    keep_map: dict[str, str],
    defaults: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Turns a small, flat XML response (like the ones AWS SES/SNS send
    back) into a plain dictionary.

    - `keep_map` maps an XML tag name to the dictionary key its text
      should be stored under, e.g. {"RequestId": "request_id"}.
    - `defaults` seeds the returned dictionary (and is never mutated),
      so callers can guarantee certain keys always exist even when the
      response never mentions them. `type` is always set to the name
      of the root tag.
    - Tags are read exactly as the document spells them, so a default
      XML namespace on the root does not have to be repeated on every
      tag name we look for.
    - A document carrying a DTD is refused outright. A handful of
      nested entity definitions can otherwise expand into megabytes of
      text before the parser gives up, and AWS never sends one.
    - Walks the document as it is read instead of building a tree, so
      an unusually deep response can't blow up with a RecursionError.
    - A tag with no text at all (e.g. `<Message/>`) is treated as an
      empty string rather than raising.

    Bad input (not a string, not parseable XML) just yields the
    defaults back with `type` left as None.
    """
    response = dict(defaults) if defaults else {}
    response["type"] = None

    # Collected separately so a response that fails partway through
    # leaves the defaults above exactly as they were.
    found: dict[str, Any] = {}
    root_tag: Optional[str] = None

    # Every element opened but not yet closed, outermost first.
    stack: list[_Element] = []

    def start_element(tag: str, attrs: dict[str, str]) -> None:
        """Open an element and note that its parent is not a leaf."""
        nonlocal root_tag

        if stack:
            # An element holding another element is a branch, not a leaf.
            stack[-1].leaf = False

        else:
            # The outermost tag names the kind of response this is.
            root_tag = tag

        stack.append(_Element(tag))

    def character_data(data: str) -> None:
        """Collect one piece of the open element's text."""
        # A parser may hand a single element's text over in several calls.
        stack[-1].text.append(data)

    def end_element(tag: str) -> None:
        """Close an element and keep its text if it was asked for."""
        element = stack.pop()

        # Only a leaf holds a value worth keeping.
        if element.leaf and element.tag in keep_map:
            found[keep_map[element.tag]] = "".join(element.text).strip()

    def start_doctype(*args: Any) -> None:
        """Refuse a document that carries a DTD."""
        # Raising here stops the parse before any entity is expanded.
        raise expat.ExpatError("A DTD is not permitted in a response.")

    parser = expat.ParserCreate()
    parser.StartDoctypeDeclHandler = start_doctype
    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CharacterDataHandler = character_data

    try:
        parser.Parse(xml_response, True)

    except (expat.ExpatError, TypeError):
        # bad data just causes us to generate a bad response
        return response

    # The document was read in full, so its values can be trusted.
    response["type"] = str(root_tag)
    response.update(found)

    return response
