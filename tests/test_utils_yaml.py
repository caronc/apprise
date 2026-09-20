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

"""Tests for the small YAML/template inspection boundary."""

import pytest

from apprise.utils.parse import QSD_FULL_MODE_KEYS
from apprise.utils.template import TemplatePlaceholderMap, TemplateSchema
from apprise.utils.yaml import (
    dropped_template,
    template_in_schema,
    template_references,
    templated_tag,
)


def placeholders(*names):
    """Create the same placeholder map used while parsing YAML URLs."""
    return TemplatePlaceholderMap(TemplateSchema.parse(list(names)), "")


def test_yaml_template_references_walks_values_and_url_keys_once():
    """Scan supported containers without treating names as values."""
    loop = []
    loop.append(loop)
    shared = ("${TUPLE}",)
    value = [
        None,
        7,
        "${PLAIN} and malformed ${NO-DASH}",
        {
            "json://${HOST}/": {
                "+${LITERAL_KEY}": "${VALUE}",
                "nested": shared,
            },
            "ordinary": shared,
        },
        {"${SET}"},
        loop,
    ]

    assert template_references(value) == {
        "plain",
        "host",
        "value",
        "tuple",
        "set",
    }


@pytest.mark.parametrize(
    ("url", "declared", "expected"),
    [
        (None, {"t"}, None),
        ("json://host/${T}", {"t"}, None),
        ("${OTHER}://host/", {"t"}, None),
        ("${T}://host/", {"t"}, "t"),
        ("json${T}://host/", ("t",), "t"),
        ("${T}user:pass@host/", {"t"}, "t"),
        ("${T}/path://later", {"t"}, "t"),
        ("${T}localhost/?url=http://bad.actor.com", {"t"}, "t"),
        (r"abc${T}s\://localhost", {"t"}, "t"),
        ("json://host/${T}://later", {"t"}, None),
    ],
)
def test_yaml_template_schema_boundary(url, declared, expected):
    """Only declared markers at or before the schema boundary are refused."""
    assert template_in_schema(url, declared) == expected


def test_yaml_dropped_template_reports_stable_missing_name():
    """Parser loss is detected without considering the saved source URL."""
    mapping = placeholders("a", "b")
    url = mapping.encode_url("json://user:${B}@host/${A}")

    assert dropped_template(url, {}, None) is None
    assert dropped_template(url, {"path": url}, mapping) is None
    assert (
        dropped_template(
            url,
            {
                "url": url,
                "password": mapping.encode("${B}"),
            },
            mapping,
        )
        == "a"
    )


@pytest.mark.parametrize("bucket", ("qsd", *QSD_FULL_MODE_KEYS))
def test_yaml_templated_tag_checks_every_query_bucket(bucket):
    """Every query modifier uses the same fixed-routing rule."""
    mapping = placeholders("t")
    assert templated_tag({bucket: {"tag": mapping.encode("${T}")}}, mapping)


def test_yaml_templated_tag_handles_encoded_and_global_values():
    """Per-service placeholders and raw global tags are both detected."""
    mapping = placeholders("t")

    assert templated_tag({"tag": {mapping.encode("${T}")}}, mapping)
    assert templated_tag({"tag": {"${T}"}}, mapping)
    assert not templated_tag({"qsd": None, "tag": {"${OTHER}"}}, mapping)
    assert not templated_tag([], mapping)
    assert not templated_tag({"tag": set()}, None)
