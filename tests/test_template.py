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
"""Tests for the template variable helpers."""

import time
from unittest import mock

import pytest

from apprise.exception import AppriseTemplateError
from apprise.utils.template import (
    MAX_TEMPLATE_VALUE_LEN,
    TemplatePlaceholderMap,
    TemplateSchema,
    normalize_name,
    resolve_values,
    validate_value,
)


def schema_of(*entries):
    """Build a schema from the entries given."""
    return TemplateSchema.parse(list(entries))


def test_declaration_accepts_a_list():
    """A list may mix bare names with names that carry a default."""
    schema = schema_of("target", {"smtp_host": "smtp.example.com"})
    assert sorted(schema.names) == ["smtp_host", "target"]
    assert schema.required == ("target",)
    assert schema.variables["smtp_host"].default == "smtp.example.com"


def test_declaration_accepts_a_mapping():
    """A mapping means the same thing as the list form.

    - a value present is the default
    - no value at all makes the variable mandatory
    """
    schema = TemplateSchema.parse(
        {
            "smtp_host": "smtp.example.com",
            "target": None,
        }
    )
    assert sorted(schema.names) == ["smtp_host", "target"]
    assert schema.required == ("target",)


def test_template_empty_default_is_required():
    """``- name:`` reads the same as a bare ``- name``."""
    assert schema_of({"target": None}).required == ("target",)


def test_template_name_case_insensitive():
    """TARGET, Target and target all name the same variable."""
    schema = schema_of("TaRgEt")
    assert schema.names == ("target",)
    assert "TARGET" in schema
    assert normalize_name("TARGET") == "target"


def test_template_rejects_duplicate_name():
    """The same name twice is refused, even in a different case."""
    with pytest.raises(AppriseTemplateError):
        schema_of("target", "TARGET")


@pytest.mark.parametrize(
    "name",
    ["", "a b", "has-dash", "x" * 33, "with.dot", "sym$"],
)
def test_template_rejects_invalid_name(name):
    """Only letters, digits and underscores are allowed."""
    with pytest.raises(AppriseTemplateError):
        schema_of(name)


def test_template_many_declarations():
    """There is no cap on how many variables are declared."""
    schema = schema_of(*[f"v{i}" for i in range(500)])
    assert len(schema.names) == 500


@pytest.mark.parametrize("entries", ["a string", 42, None])
def test_template_rejects_invalid_section(entries):
    """The section has to be a list or a mapping."""
    with pytest.raises(AppriseTemplateError):
        TemplateSchema.parse(entries)


def test_template_replaces_declared_names_only():
    """An undeclared ${...} is left exactly as it was written.

    This is what keeps a password holding ``${`` intact.
    """
    placeholders = TemplatePlaceholderMap(schema_of("target"), "")
    text = "json://user:${NOT_DECLARED}@host/${TARGET}"
    encoded = placeholders.encode(text)
    assert "${NOT_DECLARED}" in encoded
    assert "${TARGET}" not in encoded


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A "$" in front is ordinary text kept beside the value
        ("$${A}", "$real"),
        # ...as is any other text either side of the marker
        ("x-$${A}-y", "x-$real-y"),
        # Two of them are simply two
        ("$$${A}", "$$real"),
    ],
)
def test_template_dollar_is_literal(text, expected):
    """There is no escape syntax; a "$" is just a "$"."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    encoded = placeholders.encode(text)

    assert placeholders.used(encoded) == {"a"}
    assert placeholders.substitute(encoded, {"a": "real"}) == expected


def test_template_marker_value_is_not_expanded():
    """A value is dropped in as it is, markers and all.

    Only the original text is scanned, so a value that happens to contain
    ${NAME} is never looked at a second time.
    """
    placeholders = TemplatePlaceholderMap(schema_of("a", "b"), "")
    encoded = placeholders.encode("${A}")

    # The value for 'a' mentions 'b', and stays exactly that text
    result = placeholders.substitute(encoded, {"a": "${B}", "b": "34"})
    assert result == "${B}"


def test_template_default_marker_is_literal():
    """One declaration never builds on another."""
    schema = TemplateSchema.parse([{"value": "34"}, {"key": "${value}"}])

    assert schema.variables["key"].default == "${value}"
    assert resolve_values(schema, None, {}) == {
        "value": "34",
        "key": "${value}",
    }


@pytest.mark.parametrize(
    "secret",
    ["p${a}ss", "$${x}", "${}", "${toolong" + "g" * 40 + "}", "$", "${"],
    ids=["inline", "double-dollar", "empty", "over-long", "bare", "unclosed"],
)
def test_template_preserves_literal_markers(secret):
    """Nothing is declared, so nothing may be replaced."""
    placeholders = TemplatePlaceholderMap(TemplateSchema(), "")
    assert placeholders.encode(secret) == secret


def test_template_replaces_repeated_name():
    """Writing one more than once fills the same value in each time."""
    placeholders = TemplatePlaceholderMap(schema_of("target"), "")
    encoded = placeholders.encode("${TARGET}/a/${TARGET}?x=${TARGET}")
    result = placeholders.substitute(encoded, {"target": "VALUE"})
    assert result == "VALUE/a/VALUE?x=VALUE"


def test_template_single_pass_substitution():
    """A value that looks like a placeholder is left as data."""
    placeholders = TemplatePlaceholderMap(schema_of("a", "b"), "")
    encoded = placeholders.encode("${A}-${B}")
    # Feed one variable the text of the other's placeholder
    other = placeholders.encode("${B}")
    result = placeholders.substitute(encoded, {"a": other, "b": "second"})
    assert result == f"{other}-second"


def test_template_display_restores_names():
    """A placeholder reads as ${NAME} again for display."""
    placeholders = TemplatePlaceholderMap(schema_of("target"), "")
    encoded = placeholders.encode("json://host/${TARGET}/${TARGET}")
    assert placeholders.display(encoded) == "json://host/${TARGET}/${TARGET}"


def test_template_used_names():
    """Only declared names count."""
    placeholders = TemplatePlaceholderMap(schema_of("a", "b"), "")
    encoded = placeholders.encode("${A} ${UNDECLARED}")
    assert placeholders.used(encoded) == {"a"}


def test_template_preserves_setting_names():
    """A variable fills in a value; it never names a setting."""
    placeholders = TemplatePlaceholderMap(schema_of("target"), "")
    encoded = placeholders.encode_obj({"${TARGET}": "${TARGET}"})
    key, value = next(iter(encoded.items()))
    assert key == "${TARGET}"
    assert value != "${TARGET}"


def test_template_fills_mapping_name():
    """A placeholder sitting in a name is filled in like any other text."""
    placeholders = TemplatePlaceholderMap(schema_of("target"), "")
    # A parsed URL keeps its query names under "qsd", not at the top
    entry = {"qsd": {placeholders.encode("${TARGET}"): 1}}

    assert placeholders.used(entry) == {"target"}
    assert placeholders.substitute(entry, {"target": "real"}) == {
        "qsd": {"real": 1}
    }


def test_template_rejects_loop():
    """A branch pointing back at itself is not followed."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    loop = {}
    loop["self"] = loop
    with pytest.raises(AppriseTemplateError):
        placeholders.encode_obj(loop)


def test_template_avoids_placeholder_collision():
    """A placeholder cannot collide with the configuration."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    assert f"a{placeholders.nonce}" not in "some configuration body"


def test_template_call_value_precedence():
    """The caller beats the environment and the default."""
    schema = schema_of({"target": "from-config"})
    env = {"APPRISE_TEMPLATE_TARGET": "from-env"}
    values = resolve_values(schema, {"target": "from-call"}, env)
    assert values == {"target": "from-call"}


def test_template_config_default_beats_the_environment():
    """A default in the configuration wins over the server's own value.

    The author picked that default for this configuration in particular,
    so it is used ahead of anything the deployment set.
    """
    schema = schema_of({"target": "from-config"})
    env = {"APPRISE_TEMPLATE_TARGET": "from-env"}
    assert resolve_values(schema, None, env) == {"target": "from-config"}


def test_template_environment_fills_a_name_with_no_default():
    """The environment is what a required name falls back to."""
    schema = schema_of("target")
    env = {"APPRISE_TEMPLATE_TARGET": "from-env"}
    assert resolve_values(schema, None, env) == {"target": "from-env"}


def test_template_blank_value_reads_as_nothing_supplied():
    """Whitespace is not a value, so the next source is used."""
    schema = schema_of({"target": "from-config"})
    for blank in ("", "   ", "\t"):
        assert resolve_values(schema, {"target": blank}) == {
            "target": "from-config"
        }


def test_template_value_is_trimmed():
    """Surrounding whitespace never reaches the URL."""
    schema = schema_of("target")
    assert resolve_values(schema, {"target": "  spaced  "}) == {
        "target": "spaced"
    }


def test_template_blank_environment_value_is_ignored():
    """A blank environment value leaves the name unresolved."""
    schema = schema_of("target")
    with pytest.raises(AppriseTemplateError):
        resolve_values(schema, None, {"APPRISE_TEMPLATE_TARGET": "   "})


def test_template_default_fallback():
    """Nothing supplied anywhere falls back to the config."""
    schema = schema_of({"target": "from-config"})
    assert resolve_values(schema, None, {}) == {"target": "from-config"}


def test_template_required_value():
    """A mandatory variable with no value is an error."""
    with pytest.raises(AppriseTemplateError) as exc:
        resolve_values(schema_of("target"), None, {})

    assert exc.value.variable == "target"


def test_template_supplied_name_case_insensitive():
    """Callers may use any casing they like."""
    schema = schema_of("target")
    assert resolve_values(schema, {"TaRgEt": "x"}, {}) == {"target": "x"}


def test_template_converts_number_to_text():
    """Convert a numeric input to text."""
    schema = schema_of("target")
    assert resolve_values(schema, {"target": 42}, {}) == {"target": "42"}


def test_template_ignores_unrelated_name():
    """Each configuration ignores names that it does not use."""
    schema = schema_of({"target": "a-default"})
    values = resolve_values(schema, {"target": "x", "elsewhere": "y"}, {})
    assert values == {"target": "x"}


def test_template_checks_the_name_even_when_unused():
    """Garbage is still refused, whichever configuration it was for."""
    with pytest.raises(AppriseTemplateError):
        resolve_values(schema_of({"target": "a"}), {"not a name": "x"}, {})


def test_template_resolves_requested_names_only():
    """An entry does not pay for variables it never uses."""
    schema = schema_of("needed", {"other": "default"})
    values = resolve_values(schema, {"needed": "x"}, {}, names={"needed"})
    assert values == {"needed": "x"}


@pytest.mark.parametrize(
    "value",
    ["line\nbreak", "carriage\rreturn", "null\x00byte", "bell\x07"],
)
def test_template_rejects_control_character(value):
    """These could break out of a log line or a header."""
    with pytest.raises(AppriseTemplateError):
        validate_value("target", value)


def test_template_value_length_limit():
    """Cap values so a caller cannot flood the parser."""
    with pytest.raises(AppriseTemplateError):
        validate_value("target", "x" * (MAX_TEMPLATE_VALUE_LEN + 1))


@pytest.mark.parametrize("value", [["a"], {"a": 1}, object()])
def test_template_rejects_complex_value(value):
    """Only simple values may be supplied."""
    with pytest.raises(AppriseTemplateError):
        validate_value("target", value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(42, "42"), (1.5, "1.5"), (True, "yes"), (False, "no")],
)
def test_template_converts_scalar_value(value, expected):
    """Numbers and yes/no values are converted rather than refused."""
    assert validate_value("target", value) == expected


@pytest.mark.parametrize(
    "payload",
    [
        # Short ids keep the node name readable. Without them the payload
        # itself becomes the test id, and a single reported failure prints
        # hundreds of kilobytes, which truncates the CI log it belongs to.
        pytest.param("${" * 50000, id="open-markers"),
        pytest.param("$" * 200000, id="bare-dollars"),
        pytest.param("${A" * 20000, id="partial-names"),
        pytest.param("${" * 10000 + "}" * 10000, id="unbalanced"),
        pytest.param("${A}" * 100000, id="many-real-markers"),
        pytest.param("${" + "A" * 100000 + "}", id="over-long-name"),
        pytest.param("${" * 1000 + "A" + "}" * 1000, id="wrapped-braces"),
        pytest.param("json://h/?" + "x=${A}&" * 50000, id="long-url-tail"),
        pytest.param(
            ("a" + "0" * 16 + "t" + "9" * 5000 + "z") * 20,
            id="placeholder-lookalikes",
        ),
    ],
)
def test_template_regex_performance(payload):
    """Bound every scan so input cannot make one hang.

    Each pattern uses bounded quantifiers with nothing that can backtrack,
    so an unhelpful configuration costs time in proportion to its size and
    no more.
    """
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    for scan in (
        placeholders.encode,
        placeholders.encode_url,
        placeholders.pattern.findall,
    ):
        start = time.monotonic()
        scan(payload)
        assert time.monotonic() - start < 2


def test_template_rejects_invalid_declaration():
    """A list entry has to be a name or a name with a default."""
    with pytest.raises(AppriseTemplateError):
        TemplateSchema.parse([["not", "valid"]])


def test_template_variable_repr():
    """Useful when looking at one in a debugger."""
    variable = schema_of("target").variables["target"]
    assert "target" in repr(variable)
    assert variable.required is True


def test_template_placeholder_collision_retry():
    """A prefix that clashes with the configuration is re-rolled."""
    taken = "0" * 16
    free = "1" * 16
    with mock.patch(
        "apprise.utils.template.secrets.token_hex",
        side_effect=[taken, free],
    ):
        placeholders = TemplatePlaceholderMap(
            schema_of("a"), f"a{taken} appears here"
        )

    assert placeholders.nonce == free


def test_template_placeholder_retry_limit():
    """We never fall back to a prefix we know is unsafe."""
    taken = "0" * 16
    with (
        mock.patch(
            "apprise.utils.template.secrets.token_hex", return_value=taken
        ),
        pytest.raises(AppriseTemplateError),
    ):
        TemplatePlaceholderMap(schema_of("a"), f"a{taken}")


def test_template_shared_branch():
    """A YAML anchor used twice gives the same result both times."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    shared = {"to": "${A}"}
    encoded = placeholders.encode_obj({"first": shared, "second": shared})
    assert encoded["first"] == encoded["second"]
    assert encoded["first"] is encoded["second"]


def test_template_nested_setting_name():
    """A placeholder in a name is found however deeply it sits."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    nested = [{placeholders.encode("${A}"): 1}]
    assert placeholders.used(nested) == {"a"}
    assert placeholders.used([{"fine": 1}]) == set()


@pytest.mark.parametrize("value", [42, None, True])
def test_template_preserves_non_text_config(value):
    """Numbers and flags are left exactly as they are."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    assert placeholders.encode(value) == value
    assert placeholders.display(value) == value
    assert placeholders.substitute(value, {}) == value


def test_template_rejects_non_text_name():
    """Names have to be text before they can be looked up."""
    with pytest.raises(AppriseTemplateError):
        resolve_values(schema_of("a"), {42: "value"}, {})


def test_template_shared_setting_branch():
    """The same mapping seen twice is not walked twice."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    shared = {"fine": 1}
    assert placeholders.used([shared, shared]) == set()


def test_template_setting_loop():
    """A loop is refused rather than followed forever."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    loop = {"fine": 1}
    loop["self"] = [loop]
    with pytest.raises(AppriseTemplateError):
        placeholders.used(loop)


def test_template_missing_host():
    """Not every URL has a host to check."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {"host": None, "password": placeholders.encode("${A}")}
    result = placeholders.substitute(parsed, {"a": "value"})
    assert result["password"] == "value"


def test_template_preserves_address_separators():
    """URL fields keep the punctuation deliberately supplied to them."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {"fullpath": placeholders.encode("/${A}/x")}
    result = placeholders.substitute(parsed, {"a": "seg/ment?x=1&y=2#z"})
    assert result["fullpath"] == "/seg/ment?x=1&y=2#z/x"


def test_template_defers_service_validation():
    """Whatever else a value holds is passed straight through."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {"host": placeholders.encode("${A}")}
    for value in ("evil.com", "not a host at all", "??", "a@b"):
        # None of these raise; the service is left to make sense of it
        assert placeholders.substitute(parsed, {"a": value})["host"]


def test_template_keeps_credentials_unchanged():
    """Parsed credential fields safely accept ordinary delimiters."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {"password": placeholders.encode("${A}")}
    result = placeholders.substitute(parsed, {"a": "user:pass@host/a&b"})
    assert result["password"] == "user:pass@host/a&b"


def test_template_preserves_an_embedded_host_value():
    """A partial hostname keeps all author-supplied punctuation."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {"host": placeholders.encode("trusted-${A}")}
    result = placeholders.substitute(
        parsed, {"a": "name@evil.test:80/path?x=1#part"}
    )
    assert result["host"] == "trusted-name@evil.test:80/path?x=1#part"


def test_template_keeps_host_beside_fixed_credentials():
    """A host value does not replace separately parsed credentials."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {
        "user": "fixed",
        "password": None,
        "host": placeholders.encode("${A}"),
    }
    result = placeholders.substitute(parsed, {"a": "name@evil.test:80"})
    assert result["user"] == "fixed"
    assert result["host"] == "name@evil.test:80"


def test_template_allows_a_complete_email_host():
    """A whole authority field may intentionally carry an email value."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {
        "user": None,
        "password": None,
        "host": placeholders.encode("${A}"),
    }
    result = placeholders.substitute(parsed, {"a": "user@example.com"})
    assert result["user"] == "user"
    assert result["host"] == "example.com"


def test_template_allows_full_authority_credentials():
    """A whole authority may carry user:pass@host."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {
        "user": None,
        "password": None,
        "host": placeholders.encode("${A}"),
    }
    result = placeholders.substitute(parsed, {"a": "user:pass@example.com"})
    assert result["user"] == "user"
    assert result["password"] == "pass"
    assert result["host"] == "example.com"


@pytest.mark.parametrize("authority", ("@example.com", "user@"))
def test_template_contains_a_malformed_authority(authority):
    """An incomplete authority stays in the field as supplied."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {
        "user": None,
        "password": None,
        "host": placeholders.encode("${A}"),
    }
    result = placeholders.substitute(parsed, {"a": authority})
    assert result["user"] is None
    assert result["host"] == authority


def test_template_allows_combined_credentials():
    """A whole user field may carry user:pass credentials."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {
        "user": placeholders.encode("${A}"),
        "password": None,
        "host": "example.com",
    }
    result = placeholders.substitute(parsed, {"a": "user:pass"})
    assert result["user"] == "user"
    assert result["password"] == "pass"


def test_template_leaves_a_setting_value_alone():
    """A setting written under the URL already says what it is for."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    parsed = {"bcc": placeholders.encode("${A}")}
    result = placeholders.substitute(parsed, {"a": "b64/secret@host&x"})
    assert result["bcc"] == "b64/secret@host&x"


def test_template_ignores_non_text_setting_keys():
    """YAML allows a number as a key; there is nothing to look at."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    entry = {1: "x", 2.5: "y"}
    assert placeholders.used(entry) == set()
    assert placeholders.substitute(entry, {}) == {1: "x", 2.5: "y"}


def test_template_fills_name_beside_text():
    """A name mixing a marker with fixed text keeps the fixed part."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    entry = {"qsd": {"x-" + placeholders.encode("${A}"): 1}}
    assert placeholders.substitute(entry, {"a": "real"}) == {
        "qsd": {"x-real": 1}
    }


def test_template_preserves_yaml_names():
    """A marker written as a YAML setting name stays plain text."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    encoded = placeholders.encode_obj({"${A}": "${A}"})

    # The name is untouched while the value became a placeholder
    assert list(encoded) == ["${A}"]
    assert placeholders.used(encoded) == {"a"}


@pytest.mark.parametrize(
    ("url", "expected_names"),
    [
        # Everything after :// is fair game
        ("json://${A}/path?x=${A}", {"a"}),
        # ...and nothing before it is
        ("${A}://host/", set()),
        # A URL with no separator at all has nothing to read
        ("${A}user:pass@host/", set()),
    ],
)
def test_template_encode_url_preserves_schema(url, expected_names):
    """Only the text past :// is ever replaced."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    assert placeholders.used(placeholders.encode_url(url)) == expected_names


def test_template_encode_url_passes_non_text_through():
    """There is no URL to read inside a number."""
    placeholders = TemplatePlaceholderMap(schema_of("a"), "")
    assert placeholders.encode_url(42) == 42
