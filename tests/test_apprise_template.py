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
"""Tests for template variables end to end.

Where a variable may be written, and what each placement can reach, is
covered separately in ``test_apprise_template_placement.py``.
"""

# Disable logging for a cleaner testing output
from collections import UserDict
import logging
import os
from types import MappingProxyType
from unittest import mock

import pytest
import requests

from apprise import Apprise, AppriseAsset, AppriseConfig, NotifyTemplate
from apprise.config import ConfigBase
from apprise.exception import AppriseTemplateError
from apprise.result import AppriseResultStatus


def parse(content):
    """Return the services a YAML configuration produces."""
    return ConfigBase.config_parse_yaml(content)[0]


def load(content):
    """Build an Apprise object around a YAML configuration."""
    apobj = Apprise()
    config = AppriseConfig()
    assert config.add_config(content, format="yaml")
    assert apobj.add(config)
    return apobj


@pytest.fixture
def logging_enabled():
    """Enable logging while tests inspect captured records."""
    previous = logging.root.manager.disable
    logging.disable(logging.NOTSET)
    yield
    logging.disable(previous)


@pytest.fixture
def sent():
    """Accept every outbound request so delivery reports success."""
    with mock.patch("requests.request") as request:
        response = mock.Mock()
        response.status_code = requests.codes.ok
        response.content = ""
        response.headers = {}
        request.return_value = response
        yield request


def test_apprise_template_deferred_entry():
    """The service cannot be built while a value is missing."""
    services = parse(
        "template:\n  - target\nurls:\n  - json://localhost/?to=${TARGET}\n"
    )
    assert len(services) == 1
    assert isinstance(services[0], NotifyTemplate)
    assert services[0].template_names == ("target",)
    assert services[0].template_required == ("target",)
    assert services[0].url_id() is None


def test_apprise_template_text_config():
    """TEXT configurations keep ${...} as literal text."""
    services, _ = ConfigBase.config_parse_text(
        "json://user:${NOT_A_VAR}@localhost"
    )
    assert len(services) == 1
    assert "$" in services[0].password


@pytest.mark.parametrize(
    "entry",
    (
        "json://localhost/?tag=${T}",
        "json://localhost/?tags=${T}",
        "json://localhost/?+tag=${T}",
        "json://localhost/?-tag=${T}",
        "json://localhost/?:tag=${T}",
        "json://localhost/:\n    - tag: ${T}",
        "json://localhost/:\n    - tags: ${T}",
    ),
)
def test_apprise_template_rejects_tag_variable(entry, logging_enabled, caplog):
    """Query, singular, and plural tags all stay fixed."""
    with caplog.at_level(logging.ERROR):
        assert parse("template:\n  - t\nurls:\n  - {}\n".format(entry)) == []

    assert "not permitted in tag/tags" in caplog.text


@pytest.mark.parametrize(
    "tags",
    ("tag: ${T}", "tags: ${T}", 'tags: [fixed, "${T}"]'),
)
def test_apprise_template_rejects_global_tag_variable(
    tags, logging_enabled, caplog
):
    """Global routing tags must also be known before resolution."""
    with caplog.at_level(logging.ERROR):
        services = parse(
            f"template:\n  - t\n{tags}\nurls:\n  - json://localhost/\n"
        )

    assert services == []
    assert "not permitted in tag/tags" in caplog.text


def test_apprise_template_disabled_keeps_global_tag_marker():
    """A tag marker is ordinary text when template support is disabled."""
    services, _ = ConfigBase.config_parse_yaml(
        "template:\n  - t\ntag: ${T}\nurls:\n  - json://localhost/\n",
        asset=AppriseAsset(allow_templates=False),
    )

    assert len(services) == 1
    assert {str(tag) for tag in services[0].tags} == {"${t}"}


def test_apprise_template_keeps_undeclared_global_tag_marker():
    """Only declared variables are forbidden in routing tags."""
    services = parse(
        "template:\n  - other\ntag: ${T}\nurls:\n  - json://localhost/\n"
    )

    assert len(services) == 1
    assert {str(tag) for tag in services[0].tags} == {"${t}"}


def test_apprise_template_fills_marker_after_schema():
    """Every marker past :// is filled in, wherever it was written."""
    entry = parse(
        "template:\n  - t\nurls:\n  - json://localhost/?+${T}=1&+X=${T}\n"
    )[0]

    assert isinstance(entry, NotifyTemplate)
    assert entry.template_names == ("t",)

    # The parameter name and the value both take the supplied value
    service = entry.resolve({"t": "REAL"})
    assert service.headers == {"REAL": "1", "X": "REAL"}


def test_apprise_template_preserves_yaml_setting_name():
    """A marker written as a YAML setting name is not a variable.

    Only values are replaced underneath a URL, so the name stays as the
    configuration spelled it and Apprise reads it the usual way.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - json://localhost/:\n"
        "      '+${T}': 1\n      '+X': ${T}\n"
    )[0]

    service = entry.resolve({"t": "REAL"})
    assert service.headers == {"${T}": "1", "X": "REAL"}


def test_apprise_template_bad_entry_isolated():
    """One refused entry leaves the rest of the file usable."""
    services = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://u:p@gmail.com:${T}\n  - json://other/\n"
    )
    assert len(services) == 1
    assert not isinstance(services[0], NotifyTemplate)


def test_apprise_template_rejects_yaml_loop(logging_enabled, caplog):
    """A recursive YAML value rejects its entry without escaping an error."""
    with caplog.at_level(logging.ERROR):
        services = parse(
            "template:\n  - t\n"
            "urls:\n  - json://user:${T}@localhost/:\n"
            "    - headers: &loop [*loop]\n"
            "  - json://localhost/\n"
        )

    assert len(services) == 1
    assert "Looping structure" in caplog.text


@pytest.mark.parametrize(
    "url",
    [
        "json://${T}/path",
        "json://host/${T}",
        "json://user:${T}@host/",
        "json://${T}:pass@host/",
        "json://host/?to=${T}",
    ],
)
def test_apprise_template_url_fields(url):
    """Host, path, credentials and parameters all accept one."""
    services = parse(f"template:\n  - t\nurls:\n  - {url}\n")
    assert len(services) == 1
    assert isinstance(services[0], NotifyTemplate)


def test_apprise_template_yaml_setting():
    """A setting written under the URL may be templated too."""
    services = parse(
        "template:\n  - t\n"
        "urls:\n  - json://localhost/:\n    - to: ${T}\n      tag: work\n"
    )
    assert len(services) == 1
    assert services[0].template_names == ("t",)
    assert {str(t) for t in services[0].tags} == {"work"}


def test_apprise_template_yaml_url_key():
    """The mapping form is supported as well as the plain form."""
    services = parse(
        "template:\n  - t\n"
        "urls:\n  - json://localhost/${T}:\n    - tag: work\n"
    )
    assert len(services) == 1
    assert isinstance(services[0], NotifyTemplate)


def test_apprise_template_value_encoding(sent):
    """Credential punctuation reaches the parsed password field unchanged."""
    apobj = load("template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n")
    hostile = "a b&c=d?e/f@g"
    assert apobj.notify(body="x", template={"t": hostile})

    service = next(apobj.find(template={"t": hostile}))

    # The value survives untouched
    assert service.password == hostile

    # The plugin escapes that field if it later renders a URL.
    rendered = service.url()
    assert "%26" in rendered
    assert "a b&c" not in rendered


def test_apprise_template_undeclared_marker_literal():
    """``${NAME}`` only means something when it was declared.

    Anything else is ordinary text, and the entry is not treated as
    templated at all.
    """
    services = parse(
        "template:\n  - t\nurls:\n  - json://user:${NOT_DECLARED}@localhost/\n"
    )

    assert len(services) == 1
    # It loaded straight away; nothing is waiting on a value
    assert not isinstance(services[0], NotifyTemplate)
    assert services[0].password == "${NOT_DECLARED}"


def test_apprise_template_undeclared_marker_not_pending(sent):
    """The URL is sent exactly as written."""
    apobj = load(
        "template:\n  - t\nurls:\n  - json://user:${NOPE}@localhost/\n"
    )

    assert apobj.template_vars() == {}
    assert apobj.notify(body="x").status == AppriseResultStatus.SUCCESS


def test_apprise_template_success_status(sent):
    """A complete set of values delivers as normal."""
    apobj = load(
        "template:\n  - t\n"
        "urls:\n  - json://localhost/?:x=${T}\n  - json://other/\n"
    )
    result = apobj.notify(body="x", template={"t": "value"})
    assert result.status == AppriseResultStatus.SUCCESS
    assert len(list(result)) == 2


def test_apprise_template_partial_status(sent):
    """A skipped entry must not read as a clean success."""
    apobj = load(
        "template:\n  - t\n"
        "urls:\n  - json://localhost/?:x=${T}\n  - json://other/\n"
    )
    result = apobj.notify(body="x")
    assert result.status == AppriseResultStatus.PARTIAL
    assert len(list(result)) == 1


def test_apprise_template_missing_all_status(sent):
    """Every match being held back is a failure, not a no-match."""
    apobj = load("template:\n  - t\nurls:\n  - json://localhost/?:x=${T}\n")
    assert apobj.notify(body="x").status == AppriseResultStatus.FAILURE


def test_apprise_template_environment_value(sent, monkeypatch):
    """A deployment can supply values without touching the config."""
    monkeypatch.setenv("APPRISE_TEMPLATE_T", "from-env")
    apobj = load("template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n")
    assert apobj.notify(body="x").status == AppriseResultStatus.SUCCESS
    assert next(apobj.find()).password == "from-env"


def test_apprise_template_tag_matching(sent):
    """Tags are known up front, so filtering is unaffected."""
    apobj = load(
        "template:\n  - t\n"
        "urls:\n  - json://user:${T}@localhost/:\n    - tag: work\n"
        "  - json://other/:\n    - tag: home\n"
    )
    matched = list(apobj.find(tag="work", template={"t": "x"}))
    assert len(matched) == 1
    assert matched[0].password == "x"


def test_apprise_template_pending_url_display():
    """Introspection reveals which values are still wanted."""
    apobj = load("template:\n  - t\nurls:\n  - json://host/${T}\n")
    assert "${T}" in apobj.urls()[0]
    assert "${T}" in apobj.urls(privacy=True)[0]


def test_apprise_template_secret_masking():
    """A variable name is safe to show; a password is not."""
    apobj = load(
        "template:\n  - t\nurls:\n  - json://user:hunter2secret@host/${T}\n"
    )
    shown = apobj.urls(privacy=True)[0]
    assert "${T}" in shown
    assert "hunter2secret" not in shown


def test_apprise_template_service_reuse(sent):
    """Anything the service remembers survives between calls."""
    entry = parse(
        "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n"
    )[0]
    first = entry.resolve({"t": "x"})
    assert entry.resolve({"t": "x"}) is first
    assert entry.resolve({"t": "y"}) is not first

    # ...and an identifier only exists once it has been built
    assert entry.url_id() is None
    assert first.url_id()


def test_apprise_template_cache_limit():
    """A caller sending new values each time cannot grow it."""
    from apprise.template import MAX_RESOLVE_CACHE

    entry = parse(
        "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n"
    )[0]
    for i in range(MAX_RESOLVE_CACHE + 10):
        entry.resolve({"t": f"value{i}"})

    assert len(entry._cache) <= MAX_RESOLVE_CACHE


def test_apprise_template_vars_summary():
    """Callers can ask what a configuration expects."""
    apobj = load(
        "template:\n  - needed\n  - other: a-default\n"
        "urls:\n  - json://host/${NEEDED}/${OTHER}\n"
    )
    report = apobj.template_vars()

    # No default means the call or environment needs to fill the name.
    assert report["needed"]["default"] is None

    # ...otherwise the default itself is reported
    assert report["other"]["default"] == "a-default"

    assert report["needed"]["services"] == 1


def test_apprise_template_missing_name_not_captured(sent, logging_enabled):
    """Keep missing names out of logs returned to API callers."""
    captured = []
    apobj = load(
        "template:\n  - super_secret_name\n"
        "urls:\n  - json://localhost/?:x=${SUPER_SECRET_NAME}\n"
        "  - json://other/\n"
    )
    result = apobj.notify(
        body="x",
        log_callback=lambda entry, service: captured.append(entry),
        log_level=logging.DEBUG,
    )

    assert result.status == AppriseResultStatus.PARTIAL

    blob = " ".join(entry.message for entry in captured).lower()
    assert "super_secret_name" not in blob
    assert "${" not in blob

    # The operator is still told that something was left out
    assert "skipped" in blob


def test_apprise_template_config_not_captured(sent, logging_enabled):
    """A capture must never carry the configuration body."""
    captured = []
    apobj = load(
        "template:\n  - t\n"
        "urls:\n  - json://user:hunter2secret@localhost/?:x=${T}\n"
    )
    apobj.notify(
        body="x",
        log_callback=lambda entry, service: captured.append(entry),
        log_level=logging.DEBUG,
    )

    blob = " ".join(entry.message for entry in captured)
    assert "hunter2secret" not in blob


def test_apprise_template_log_capture_opt_out(logging_enabled):
    """The flag the template code relies on works on its own."""
    from apprise.logger import _ServiceLogCapture, logger

    captured = []
    with _ServiceLogCapture(
        service=None,
        log_callback=lambda entry, service: captured.append(entry),
        level=logging.DEBUG,
    ):
        logger.error("PUBLIC-MARKER")
        logger.error("PRIVATE-MARKER", extra={"apprise_capture": False})

    blob = " ".join(entry.message for entry in captured)
    assert "PUBLIC-MARKER" in blob
    assert "PRIVATE-MARKER" not in blob


def test_apprise_template_included_declarations(sent, tmpdir):
    """Each file declares what it uses; values reach them all."""
    child = tmpdir.join("child.yml")
    child.write(
        "template:\n  - shared\nurls:\n  - json://user:${SHARED}@child-host/\n"
    )
    parent = tmpdir.join("parent.yml")
    parent.write(
        "template:\n  - shared\n"
        f"include:\n  - {child!s}\n"
        "urls:\n  - json://user:${SHARED}@parent-host/\n"
    )

    apobj = Apprise()
    config = AppriseConfig(recursion=1)
    assert config.add(str(parent))
    assert apobj.add(config)

    # One value supplied once reaches both files
    built = list(apobj.find(template={"shared": "one-value"}))
    assert len(built) == 2
    assert {service.password for service in built} == {"one-value"}


def test_apprise_template_shared_yaml_block(sent):
    """A YAML anchor used twice does not confuse the parser."""
    apobj = load(
        "template:\n  - t\n"
        "shared: &shared\n  to: ${T}\n"
        "urls:\n  - json://first/:\n    <<: *shared\n"
        "  - json://second/:\n    <<: *shared\n"
    )
    assert len(list(apobj.find(template={"t": "x"}))) == 2


def test_apprise_template_cli_value(tmpdir, sent):
    """--template supplies a value for a run."""
    from click.testing import CliRunner

    from apprise import cli

    config = tmpdir.join("apprise.yml")
    config.write("template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n")

    result = CliRunner().invoke(
        cli.main,
        ["-b", "x", f"--config={config!s}", "--template-var", "t=supplied"],
    )
    assert result.exit_code == 0


def test_apprise_template_cli_invalid_value(tmpdir):
    """A --template entry has to read as NAME=VALUE."""
    from click.testing import CliRunner

    from apprise import cli

    config = tmpdir.join("apprise.yml")
    config.write("urls:\n  - json://localhost\n")

    result = CliRunner().invoke(
        cli.main,
        ["-b", "x", f"--config={config!s}", "-tv", "no-equals-sign"],
    )
    assert result.exit_code == 2
    assert "NAME=VALUE" in result.output


def test_apprise_template_cli_dry_run(tmpdir):
    """The written form and the required names are both listed."""
    from click.testing import CliRunner

    from apprise import cli

    config = tmpdir.join("apprise.yml")
    config.write(
        "template:\n  - t\n  - other: a-default\n"
        "urls:\n  - json://host/${T}/${OTHER}\n"
    )

    result = CliRunner().invoke(
        cli.main, ["-b", "x", f"--config={config!s}", "--dry-run"]
    )
    assert "${T}" in result.output
    assert "t (required)" in result.output
    assert "other (has default)" in result.output


def test_apprise_template_pending_repr():
    """It stands in for a service, so it answers the same questions."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - json://user:${T}@localhost/:\n"
        "    - tag: work\n      retry: 2\n"
    )[0]

    assert entry.schema == "json"
    assert entry.service_name == "JSON"
    assert entry.enabled is True
    assert entry.retry == 2
    assert entry.optional is None
    assert "json" in repr(entry)
    assert "${T}" in str(entry)


def test_apprise_template_unknown_service_metadata():
    """A schema we do not carry is answered for safely."""
    entry = parse(
        "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n"
    )[0]
    entry.results["schema"] = "not-a-real-schema"

    assert entry._plugin is None
    assert entry.service_name is None
    assert entry.enabled is True


def test_apprise_template_setting_display():
    """A setting is listed so it is clear a value is wanted."""
    apobj = load(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:pass@gmail.com:\n    - to: ${T}\n"
    )
    shown = apobj.urls()[0]
    assert "${T}" in shown
    # ...and it survives being escaped for the URL
    assert "%24%7B" not in shown


def test_apprise_template_repeated_name(sent):
    """A variable may be written as many times as you like."""
    apobj = load(
        "template:\n  - t\n"
        "urls:\n  - json://user:${T}@localhost/${T}/:\n    - to: ${T}\n"
    )

    service = next(apobj.find(template={"t": "same"}))
    assert service.password == "same"
    assert "/same/" in service.url()


def test_apprise_template_url_size_limit(monkeypatch, logging_enabled, caplog):
    """A built URL is capped no matter what values arrive."""
    import apprise.template as template_module

    entry = parse(
        "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n"
    )[0]
    monkeypatch.setattr(template_module, "MAX_RESOLVED_URL_LEN", 10)

    with caplog.at_level(logging.ERROR):
        assert entry.resolve({"t": "a-value-well-over-ten-characters"}) is None

    # The message says which lines of the file to go and look at
    assert "YAML entry #1, item #1" in caplog.text


def test_apprise_template_build_failure(logging_enabled, caplog):
    """A value the service rejects skips the entry, not the run."""
    entry = parse(
        "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n"
    )[0]

    from apprise.template import N_MGR

    with (
        mock.patch.object(
            type(N_MGR),
            "__getitem__",
            side_effect=TypeError("the value was refused"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        assert entry.resolve({"t": "x"}) is None

    assert "YAML entry #1, item #1" in caplog.text


def test_apprise_template_substitution_failure(logging_enabled, caplog):
    """A failure while filling values in is handled quietly."""
    entry = parse(
        "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n"
    )[0]

    with (
        mock.patch.object(
            entry.placeholders, "substitute", side_effect=RuntimeError("nope")
        ),
        caplog.at_level(logging.ERROR),
    ):
        assert entry.resolve({"t": "x"}) is None

    assert "YAML entry #1, item #1" in caplog.text


def test_apprise_template_exception_detail_is_never_captured(
    logging_enabled, caplog
):
    """A rejected value is not handed back through the result log."""
    apobj = Apprise()
    config = AppriseConfig()
    config.add_config(
        "template:\n  - key\n"
        "urls:\n  - sendgrid://${KEY}:user@example.com/to@example.com\n",
        format="yaml",
    )
    apobj.add(config)

    captured = []

    with caplog.at_level(logging.DEBUG, logger="apprise"):
        apobj.notify(
            body="x",
            # Refused by the service, which names it in the error it raises
            template={"key": "SECRET!!!KEY"},
            log_callback=lambda entry, plugin: captured.append(entry),
            log_level=logging.DEBUG,
        )

    messages = [str(getattr(entry, "message", entry)) for entry in captured]

    # The entry was skipped, and said so without naming the value
    assert any("Could not load" in m for m in messages)

    # The service's own exception text never reaches the caller
    assert not [m for m in messages if "Loading Exception" in m]


def test_apprise_template_location_counts_each_expansion():
    """One URL block that becomes several services numbers them apart."""
    services = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:pass@gmail.com:\n"
        "    - to: one@example.com\n      cc: ${T}\n"
        "    - to: two@example.com\n      cc: ${T}\n"
    )

    # Both came from the first block under urls:, as separate items
    assert [s.location for s in services] == [
        "YAML entry #1, item #1",
        "YAML entry #1, item #2",
    ]


def test_apprise_template_adjacent_text_masking():
    """Only the variable name is safe to show; the rest is not."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - json://user:prefix${T}suffix@localhost/\n"
    )[0]

    shown = entry.url(privacy=True)
    assert "${T}" in shown
    assert "prefix" not in shown
    assert "suffix" not in shown

    # Without privacy the whole thing reads back as written
    assert "prefix${T}suffix" in entry.url()


def test_apprise_template_query_display():
    """A parameter waiting on a value is visible in the URL."""
    entry = parse(
        "template:\n  - t\nurls:\n  - json://localhost/?:custom=${T}\n"
    )[0]
    assert "${T}" in entry.url()


def test_apprise_template_parse_time_validation(logging_enabled, caplog):
    """Report services that must validate a field while parsing."""
    with caplog.at_level(logging.ERROR):
        services = parse(
            "template:\n  - t\n"
            "urls:\n  - sendgrid://SG.abcdefghij:${T}/to@example.com\n"
        )

    assert services == []
    assert "template variable can not be used at this position" in (
        caplog.text.lower()
    )


def test_apprise_template_valid_service_position():
    """The limitation is the position, not the service."""
    services = parse(
        "template:\n  - t\n"
        "urls:\n  - sendgrid://${T}:from@example.com/to@example.com\n"
    )
    assert len(services) == 1
    assert isinstance(services[0], NotifyTemplate)


def test_apprise_template_service_coverage():
    """A spot check across a few differently shaped URLs."""
    for url in (
        "discord://${T}/${T}",
        "slack://${T}/${T}/${T}",
        "mailtos://user:pass@example.com/a@b.com?smtp=${T}",
        "twilio://sid:token@${T}/+15551234567",
        "tgram://123456789:${T}/-1001234567890",
    ):
        services = parse(f"template:\n  - t\nurls:\n  - {url}\n")
        assert len(services) == 1, url
        assert isinstance(services[0], NotifyTemplate), url


def test_apprise_template_many_url_variables(sent):
    """There is no cap on how many are used in one URL."""
    names = [f"v{i}" for i in range(60)]
    declared = "\n".join(f"  - {name}" for name in names)
    path = "/".join("${{{}}}".format(name.upper()) for name in names)

    apobj = load(f"template:\n{declared}\nurls:\n  - json://host/{path}\n")
    values = {name: f"val{i}" for i, name in enumerate(names)}

    service = next(apobj.find(template=values))
    for i in range(60):
        assert f"val{i}" in service.url()


def test_apprise_template_shared_url_setting(sent):
    """One name can fill the URL and a setting below it."""
    apobj = load(
        "template:\n  - t\n"
        "urls:\n  - json://user:${T}@localhost/:\n"
        "    - to: ${T}\n      tag: work\n"
    )
    service = next(apobj.find(template={"t": "shared"}))
    assert service.password == "shared"


def test_apprise_template_query_value_is_not_reparsed(sent):
    """A parsed query value is not reparsed as more query settings."""
    apobj = load(
        "template:\n  - v\nurls:\n  - json://localhost/?:custom=${V}\n"
    )
    control = load("template:\n  - v\nurls:\n  - json://localhost/?:c=${V}\n")

    evil = next(
        apobj.find(template={"v": "x&method=GET&to=hijacked@example.com"})
    )
    clean = next(control.find(template={"v": "x"}))

    # The marker occupied one parsed value, so its punctuation stays there.
    assert evil.method == clean.method == "POST"


def test_apprise_template_path_punctuation(sent):
    """Path fields preserve punctuation selected by the config author."""
    apobj = load("template:\n  - v\nurls:\n  - json://h/${V}/x\n")
    service = next(apobj.find(template={"v": "seg/ment?x=1&y=2#z"}))
    assert service.fullpath == "/seg/ment?x=1&y=2#z/x"


def test_apprise_template_service_validates_value(sent):
    """Garbage is handed to the service to make sense of."""
    apobj = load("template:\n  - v\nurls:\n  - json://${V}/\n")
    for value in ("ok.example.com", "evil.com/p", "not a host", "a@b"):
        assert next(apobj.find(template={"v": value}), None) is not None


def test_apprise_template_embedded_host_is_preserved(sent):
    """A partial hostname keeps author-supplied URL punctuation."""
    apobj = load("template:\n  - v\nurls:\n  - json://trusted-${V}/\n")
    service = next(
        apobj.find(template={"v": "name@evil.test:80/path?x=1#part"})
    )

    assert service.host == "trusted-name@evil.test:80/path?x=1#part"
    assert service.fullpath == "/"


@pytest.mark.parametrize(
    "entry",
    [
        # Written on its own
        "${V}://host/",
        # Written as a YAML key with settings under it
        "${V}://host/:\n    - tag: work",
        # A marker standing in for the schema and its separator
        "${V}user:pass@host/",
        # Trailing text after the marker, as in a secure variant
        "${V}s://host/",
        # Leading text before the marker
        "json${V}://host/",
        # ...and the same the other way around
        "${V}json://host/",
        # Buried in the middle of an otherwise real schema
        "js${V}on://host/",
        # A secure variant built from both
        "mailto${V}s://host/",
        # No separator at all
        "${V}",
        # A separator that is not quite one
        "${V}//host/",
        # A later separator does not hide a variable in the schema position
        "${V}/path://later",
        # The mapping form must make the same decision
        "${V}/path://later:\n    - tag: work",
        # A URL hidden in a query value cannot provide the schema boundary
        "${V}localhost/?url=http://bad.actor.com",
        # A backslash before :// does not make a variable schema acceptable
        r"abc${V}s\://localhost",
    ],
)
def test_apprise_template_rejects_schema_variable(
    entry, logging_enabled, caplog
):
    """Nothing before :// can be a template variable.

    The schema decides which service reads the URL, and that is settled
    long before a value is known, so this is a configuration error rather
    than an unresolved notification service.
    """
    with caplog.at_level(logging.ERROR):
        assert parse("template:\n  - v\nurls:\n  - {}\n".format(entry)) == []

    assert "not permitted in URL schemas" in caplog.text


def test_apprise_template_dollar_is_literal():
    """A "$" before a marker is just a "$".

    There is no escape syntax. To keep a ${NAME} literal, simply do not
    declare that name.
    """
    entry = parse("template:\n  - t\nurls:\n  - json://l/?+X=$${T}\n")[0]

    service = entry.resolve({"t": "abc"})
    assert service.headers == {"X": "$abc"}


def test_apprise_template_default_marker_is_literal():
    """A default is used exactly as written, markers and all.

    One declaration never builds on another. ``key`` below is the text
    ``${value}``, not ``34``. Assemble values in the URL instead.
    """
    apobj = load(
        "template:\n  value: 34\n  key: ${value}\n"
        "urls:\n  - json://l/?+K=${KEY}&+V=${VALUE}\n"
    )

    # K keeps the marker; V shows that 'value' really does resolve to 34
    assert next(apobj.find()).headers == {"K": "${value}", "V": "34"}


def test_apprise_template_supplied_marker_is_literal():
    """A value handed in for one call is not looked at again either."""
    apobj = load(
        "template:\n  value: 34\n  key:\n"
        "urls:\n  - json://l/?+K=${KEY}&+V=${VALUE}\n"
    )
    service = next(apobj.find(template={"key": "${value}"}))

    assert service.headers == {"K": "${value}", "V": "34"}


def test_apprise_template_environment_marker_is_literal():
    """An environment value is taken as written in the same way."""
    with mock.patch.dict(os.environ, {"APPRISE_TEMPLATE_KEY": "${value}"}):
        apobj = load(
            "template:\n  value: 34\n  key:\n"
            "urls:\n  - json://l/?+K=${KEY}&+V=${VALUE}\n"
        )
        assert next(apobj.find()).headers == {"K": "${value}", "V": "34"}


def test_apprise_template_bad_schema_isolated(sent):
    """One bad entry leaves the rest of the file usable."""
    services = parse(
        "template:\n  - v\nurls:\n  - ${V}://host/\n  - json://ok/\n"
    )
    assert len(services) == 1
    assert not isinstance(services[0], NotifyTemplate)


def test_apprise_template_credential_separators(sent):
    """Ordinary password punctuation is kept unchanged."""
    apobj = load("template:\n  - v\nurls:\n  - json://u:${V}@host/\n")
    service = next(apobj.find(template={"v": "p/a?s&s"}))
    assert service.password == "p/a?s&s"


@pytest.mark.parametrize("credentials", ("user", "user:pass"))
def test_apprise_template_combined_credentials(credentials, sent):
    """A user field may carry either supported credential form."""
    apobj = load("template:\n  - creds\nurls:\n  - json://${CREDS}@host/\n")
    service = next(apobj.find(template={"creds": credentials}))
    user, separator, password = credentials.partition(":")
    assert service.user == user
    assert service.password == (password if separator else None)
    assert service.host == "host"


def test_apprise_template_email_authority(sent):
    """A service may accept an email as its complete authority value."""
    apobj = load(
        "template:\n  - email\n"
        "urls:\n"
        "  - ses://${EMAIL}/T1JJ3T3L2/A1BRTD4JD/"
        "TIiajkdnlazkcevi7FQ/us-west-2/user2@example.com\n"
    )
    service = next(apobj.find(template={"email": "sender@example.com"}))
    assert service.from_addr == "sender@example.com"


# The characters that separate one part of a URL from the next, and a few
# everyday ones that have to survive untouched.
SEPARATORS = ("/", "&", "@")

VALUES = (
    "plain-value",
    "a/b",
    "a&b",
    "a@b",
    "user:pass",
    "one,two",
    "a/b&c@d",
    "b64/secret+value==",
)


@pytest.mark.parametrize("value", VALUES)
def test_apprise_template_url_value_is_preserved(value, sent):
    """A value written into a URL fills the one spot it was written in."""
    apobj = load("template:\n  - v\nurls:\n  - json://user:${V}@host/\n")
    service = next(apobj.find(template={"v": value}))

    # The service still talks to the host the author wrote
    assert service.host == "host"
    assert service.user == "user"

    # ...and the value arrives whole, however it was written
    assert service.password == value


@pytest.mark.parametrize("value", VALUES)
def test_apprise_template_setting_value_is_left_alone(value, sent):
    """A setting under the URL already says what its value is for."""
    apobj = load(
        "template:\n  - v\n"
        "urls:\n  - json://user:pass@host/:\n    - to: ${V}\n"
    )
    service = next(apobj.find(template={"v": value}))

    assert service.host == "host"
    assert service.password == "pass"


@pytest.mark.parametrize("value", VALUES)
def test_apprise_template_query_value_adds_no_parameter(value, sent):
    """An "&" in a value cannot become another parameter."""
    apobj = load("template:\n  - v\nurls:\n  - json://host/?:custom=${V}\n")
    control = load("template:\n  - v\nurls:\n  - json://host/?:custom=${V}\n")

    service = next(apobj.find(template={"v": value}))
    clean = next(control.find(template={"v": "plain"}))

    # Nothing the value carried changed how the service was set up
    assert service.method == clean.method
    assert service.host == clean.host == "host"


@pytest.mark.parametrize(
    "address", ["[::1]", "::1", "2001:db8::1", "127.0.0.1", "host.example"]
)
def test_apprise_template_real_addresses_survive(address, sent):
    """A genuine address is written through untouched."""
    apobj = load("template:\n  - v\nurls:\n  - json://${V}/\n")
    assert next(apobj.find(template={"v": address})).host == address


@pytest.mark.parametrize("hostile", VALUES)
def test_apprise_template_email_setting_keeps_server(hostile, sent):
    """A named email setting cannot change the configured mail server."""
    apobj = load(
        "template:\n  - v\n"
        "urls:\n  - mailtos://user:pass@example.com/:\n    - bcc: ${V}\n"
    )
    service = next(apobj.find(template={"v": hostile}))

    # The server being talked to is still the one the author wrote
    assert service.host == "example.com"
    assert service.user == "user"
    assert service.password == "pass"


def two_configurations():
    """Two separately loaded configurations, each with its own variable."""
    apobj = Apprise()
    for name in ("alpha", "beta"):
        config = AppriseConfig()
        assert config.add_config(
            f"template:\n  - {name}\n"
            f"urls:\n  - json://user:${{{name.upper()}}}@{name}-host/\n",
            format="yaml",
        )
        assert apobj.add(config)
    return apobj


def test_apprise_template_values_span_configurations(sent):
    """One set of values covers everything that is loaded.

    Each entry passes over the names belonging to the other
    configuration rather than refusing them.
    """
    built = list(
        two_configurations().find(template={"alpha": "1", "beta": "2"})
    )
    assert sorted(service.host for service in built) == [
        "alpha-host",
        "beta-host",
    ]
    assert sorted(service.password for service in built) == ["1", "2"]


def test_apprise_template_case_is_ignored_end_to_end(sent):
    """Declaration, marker, and supplied key casing may all differ."""
    apobj = Apprise()
    config = AppriseConfig()
    assert config.add_config(
        "template:\n  - MiXeD\nurls:\n  - json://user:${mIxEd}@localhost/\n",
        format="yaml",
    )
    assert apobj.add(config)

    service = next(apobj.find(template={"MIXED": "value"}))
    assert service.password == "value"


def test_apprise_template_partial_values_span_configurations(sent):
    """Supplying one still delivers to the one it belongs to."""
    built = list(two_configurations().find(template={"alpha": "1"}))
    assert [service.host for service in built] == ["alpha-host"]


def test_apprise_template_unknown_name_is_ignored(sent):
    """A name no loaded configuration uses does not block delivery."""
    built = list(
        two_configurations().find(template={"alpha": "1", "nowhere": "x"})
    )
    assert [service.host for service in built] == ["alpha-host"]


def test_apprise_template_unknown_name_does_not_change_status(sent):
    """An unused name does not turn a successful send into a partial one."""
    apobj = Apprise()
    assert apobj.add("json://untemplated/")

    result = apobj.notify(body="x", template={"nowhere": "x"})

    assert result.status == AppriseResultStatus.SUCCESS


def test_apprise_template_hides_unknown_name_from_capture(
    sent, logging_enabled
):
    """The names must not reach whoever asked for the notification."""
    captured = []
    two_configurations().notify(
        body="x",
        template={"a_secret_name": "x"},
        log_callback=lambda entry, service: captured.append(entry),
        log_level=logging.DEBUG,
    )

    blob = " ".join(entry.message for entry in captured).lower()
    assert "a_secret_name" not in blob


def test_apprise_template_logs_unknown_name_locally(
    sent, logging_enabled, caplog
):
    """The local debug log names unused inputs without logging values."""
    with caplog.at_level(logging.DEBUG):
        list(
            two_configurations().find(
                template={"NoWhErE": "do-not-log-this-value"}
            )
        )

    assert "nowhere" in caplog.text
    assert "supplied but not used" in caplog.text
    assert "do-not-log-this-value" not in caplog.text


def test_apprise_template_unused_name_log_is_bounded(logging_enabled, caplog):
    """A large unused mapping cannot create an equally large log entry."""
    values = {"name{}".format(i): "secret{}".format(i) for i in range(25)}

    with caplog.at_level(logging.DEBUG):
        list(Apprise().find(template=values))

    assert "(+5 more)" in caplog.text
    assert "name19" in caplog.text
    assert "name20" not in caplog.text
    assert "secret" not in caplog.text


def test_apprise_template_can_be_switched_off(sent):
    """The configuration is then read as it was before templates.

    Nothing is held back, nothing is read from the environment, and the
    markers stay exactly as they were written.
    """
    content = "template:\n  - v\nurls:\n  - json://user:${V}@localhost/\n"
    asset = AppriseAsset(allow_templates=False)

    apobj = Apprise(asset=asset)
    config = AppriseConfig(asset=asset)
    assert config.add_config(content, format="yaml")
    assert apobj.add(config)

    service = next(apobj.find())
    assert not isinstance(service, NotifyTemplate)
    assert service.password == "${V}"
    assert apobj.template_vars() == {}


def test_apprise_template_disabled_ignores_environment(sent, monkeypatch):
    """A value in the environment must not quietly take effect."""
    monkeypatch.setenv("APPRISE_TEMPLATE_V", "from-env")
    asset = AppriseAsset(allow_templates=False)

    apobj = Apprise(asset=asset)
    config = AppriseConfig(asset=asset)
    assert config.add_config(
        "template:\n  - v\nurls:\n  - json://user:${V}@localhost/\n",
        format="yaml",
    )
    assert apobj.add(config)

    assert next(apobj.find()).password == "${V}"


def test_apprise_template_duplicate_setting_uses_last_value():
    """PyYAML's normal last-value behavior applies below root sections."""
    services = parse(
        "urls:\n  - json://localhost/:\n"
        "    - method: GET\n      method: POST\n"
    )

    assert len(services) == 1
    assert services[0].method == "POST"


def test_config_yaml_duplicate_section_uses_last_value():
    """Repeated root sections retain PyYAML's last-value behavior."""
    services = parse("urls:\n  - json://first/\nurls:\n  - json://second/\n")

    assert len(services) == 1
    assert services[0].host == "second"


def test_apprise_template_late_declaration_is_recognized(
    logging_enabled, caplog
):
    """A declaration may follow the service that uses it."""
    with caplog.at_level(logging.DEBUG):
        services = parse(
            "urls:\n  - json://user:${LATE}@localhost/\ntemplate:\n  - late\n"
        )

    assert len(services) == 1
    assert isinstance(services[0], NotifyTemplate)
    assert "not defined" not in caplog.text


def test_apprise_template_keeps_undeclared_marker(logging_enabled, caplog):
    """An undeclared marker remains literal and receives a debug hint."""
    with caplog.at_level(logging.DEBUG):
        services = parse("urls:\n  - json://user:${MISSING}@localhost/\n")

    assert services[0].password == "${MISSING}"
    assert "'missing' is not defined" in caplog.text
    assert "kept as written" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_apprise_template_keeps_undeclared_marker_beside_declared_one(
    logging_enabled, caplog
):
    """Declaring one marker does not activate other marker-like text."""
    with caplog.at_level(logging.DEBUG):
        services = parse(
            "template:\n  - used\n"
            "urls:\n  - json://user:${MISSING}@localhost/?to=${USED}\n"
        )

    assert services[0].results["password"] == "${MISSING}"
    assert "'missing' is not defined" in caplog.text


def test_apprise_template_reports_unused_declaration(logging_enabled, caplog):
    """Debug inspection warns about declarations unused by service entries."""
    with caplog.at_level(logging.DEBUG):
        services = parse(
            "template:\n  - unused\nurls:\n  - json://localhost/\n"
        )

    assert len(services) == 1
    assert "'unused' is defined but not referenced" in caplog.text
    assert any(
        record.levelno == logging.WARNING
        and "'unused' is defined but not referenced" in record.message
        for record in caplog.records
    )


def test_apprise_template_yaml_value_counts_as_reference(
    logging_enabled, caplog
):
    """A marker in a YAML option value counts as a real use."""
    with caplog.at_level(logging.DEBUG):
        services = parse(
            "template:\n  - used\n"
            "urls:\n  - json://localhost/:\n"
            "      headers:\n        X-Test: ${USED}\n"
        )

    assert len(services) == 1
    assert isinstance(services[0], NotifyTemplate)
    assert "not referenced" not in caplog.text


def test_apprise_template_yaml_name_is_not_a_reference(
    logging_enabled, caplog
):
    """YAML setting names stay literal and do not count as variable use."""
    with caplog.at_level(logging.DEBUG):
        services = parse(
            "template:\n  - unused\n"
            "urls:\n  - json://localhost/:\n"
            "      '+${UNUSED}': literal\n"
        )

    assert len(services) == 1
    assert "'unused' is defined but not referenced" in caplog.text


def test_apprise_template_skips_reference_scan_without_debug(
    logging_enabled, caplog
):
    """Reference discovery adds no work when debug logging is disabled."""
    with (
        mock.patch(
            "apprise.config.base.template_references",
            side_effect=AssertionError("unexpected template scan"),
        ),
        caplog.at_level(logging.INFO),
    ):
        services = parse(
            "template:\n  - unused\nurls:\n  - json://localhost/\n"
        )

    assert len(services) == 1


def test_apprise_template_supports_shared_yaml_anchor():
    """A YAML anchor may reuse an entry containing a template marker."""
    services = parse(
        "template:\n  - t\n"
        "urls:\n  - &shared json://localhost/?to=${T}\n  - *shared\n"
    )

    # Both entries load and both still wait on the same value
    assert len(services) == 2
    assert all(isinstance(s, NotifyTemplate) for s in services)


def test_apprise_template_disabled_marker_is_left_alone(
    logging_enabled, caplog
):
    """Disabled templates neither inspect nor change marker-like text."""
    asset = AppriseAsset(allow_templates=False)
    with caplog.at_level(logging.DEBUG):
        services, _ = ConfigBase.config_parse_yaml(
            "template:\n  - unused\nurls:\n  - json://user:${V}@localhost/\n",
            asset=asset,
        )

    assert services[0].password == "${V}"
    assert "not defined" not in caplog.text
    assert "not referenced" not in caplog.text


@pytest.mark.parametrize(
    ("label", "content"),
    [
        (
            "marker used as a query name",
            "template:\n  - t\nurls:\n  - json://localhost/?+${T}=1\n",
        ),
        (
            "marker used as a value",
            "template:\n  - t\nurls:\n  - json://localhost/?+X=${T}\n",
        ),
        (
            "marker used as a YAML setting name",
            "template:\n  - t\n"
            "urls:\n  - json://localhost/:\n      '+${T}': 1\n",
        ),
        (
            "marker in the credentials",
            "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n",
        ),
        (
            "no template section at all",
            "urls:\n  - json://localhost/?+X=${T}\n",
        ),
    ],
)
def test_apprise_template_disabled_matches_no_section(label, content):
    """Disabled templates leave declared markers as literal text."""
    asset = AppriseAsset(allow_templates=False)
    services, _ = ConfigBase.config_parse_yaml(content, asset=asset)

    assert len(services) == 1

    # A real service, never an entry waiting on a value
    assert not isinstance(services[0], NotifyTemplate)


def test_apprise_template_disabled_ignores_the_environment(monkeypatch):
    """A disabled file never reads APPRISE_TEMPLATE_ values."""
    monkeypatch.setenv("APPRISE_TEMPLATE_T", "from-the-environment")
    content = "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n"

    services, _ = ConfigBase.config_parse_yaml(
        content, asset=AppriseAsset(allow_templates=False)
    )
    assert services[0].password == "${T}"

    # With the feature on, the same file uses that value
    assert next(load(content).find()).password == "from-the-environment"


def test_apprise_template_disabled_ignores_repeated_sections():
    """A disabled template table follows PyYAML's last-value behavior."""
    asset = AppriseAsset(allow_templates=False)
    services, _ = ConfigBase.config_parse_yaml(
        "template:\n  first: one\n  first: two\n"
        "urls:\n  - json://localhost/\n"
        "template:\n  - second\n",
        asset=asset,
    )

    assert len(services) == 1


def test_apprise_template_url_handles_a_non_text_setting():
    """A setting that is not text has no marker to show."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - json://user:${T}@localhost/:\n"
        "    - verify: no\n      retry: 2\n"
    )[0]

    # It renders without complaint, and the marker still shows
    assert "${T}" in entry.url()


@pytest.mark.parametrize("declaration", ("", "template:\n  - t\n"))
def test_config_skips_non_text_sibling_before_url(declaration):
    """A non-text sibling cannot be mistaken for the URL key."""
    services = parse(
        declaration + "urls:\n  - 1: ignored\n    json://localhost/:\n"
    )
    assert len(services) == 1


def test_apprise_template_url_shows_every_field_using_a_name():
    """Show a shared marker in every field that uses it.

    A marker identifies where the caller's value goes. Leaving it out of
    one field would hide a setting the notification still uses.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:${T}@gmail.com:\n"
        "    - to: ${T}\n      cc: ${T}\n"
    )[0]

    url = entry.url()
    assert "user:${T}@" in url
    assert "to=${T}" in url
    assert "cc=${T}" in url


def test_apprise_template_url_without_a_path():
    """Not every URL has a path to render."""
    entry = parse("template:\n  - t\nurls:\n  - json://${T}\n")[0]
    assert "${T}" in entry.url()


def test_apprise_template_invalid_declaration_refuses_file(
    logging_enabled, caplog
):
    """An unreadable template section stops the whole file."""
    with caplog.at_level(logging.ERROR):
        services = parse(
            "template:\n  - name\n  - NAME\nurls:\n  - json://localhost/\n"
        )

    assert services == []
    assert "template section" in caplog.text.lower()


def test_apprise_template_unusable_placeholder_prefix(logging_enabled, caplog):
    """Giving up on a placeholder prefix stops the whole file."""
    taken = "0" * 16
    with (
        mock.patch(
            "apprise.utils.template.secrets.token_hex", return_value=taken
        ),
        caplog.at_level(logging.ERROR),
    ):
        # The prefix it keeps choosing already appears in the file
        services = parse(
            f"template:\n  - v\nurls:\n  - json://a{taken}/${{V}}\n"
        )

    assert services == []


def test_apprise_template_mapping_form_setting_name(logging_enabled, caplog):
    """A marker naming a YAML setting is left to the usual token check.

    Apprise already refuses a setting name it does not recognise, so the
    marker takes the same path any other unusable name would.
    """
    with caplog.at_level(logging.WARNING):
        services = parse(
            "template:\n  - t\n"
            "urls:\n  - json://localhost/:\n    - ${T}: value\n"
        )

    assert len(services) == 1
    assert "Ignoring invalid token (${T})" in caplog.text

    # A file that never declared the name is treated the same way
    with caplog.at_level(logging.WARNING):
        plain = parse("urls:\n  - json://localhost/:\n    - ${T}: value\n")

    assert len(plain) == 1
    assert "Ignoring invalid token (${T})" in caplog.text


def test_apprise_template_mapping_form_bad_position(logging_enabled, caplog):
    """The positional refusal also covers the mapping form."""
    with caplog.at_level(logging.ERROR):
        services = parse(
            "template:\n  - t\n"
            "urls:\n  - sendgrid://SG.abcdefghij:${T}/to@example.com:\n"
            "    - tag: work\n"
        )

    assert services == []
    assert "can not be used at this position" in caplog.text


def test_apprise_template_vars_reports_a_disagreement(sent):
    """Two configurations may not agree on a default."""
    apobj = Apprise()
    for default in ("first-default", "second-default"):
        config = AppriseConfig()
        assert config.add_config(
            f"template:\n  - shared: {default}\n"
            "urls:\n  - json://user:${SHARED}@host/\n",
            format="yaml",
        )
        assert apobj.add(config)

    # Neither default is assumed; use a call or environment value instead.
    assert apobj.template_vars()["shared"]["default"] is None


def test_apprise_template_status_other_outcomes():
    """Only a clean run and a no-match are reworded."""
    from apprise.dispatch import template_status

    for status in (
        AppriseResultStatus.FAILURE,
        AppriseResultStatus.PARTIAL,
        AppriseResultStatus.TIMEOUT,
    ):
        assert template_status(status, ["skipped"]) == status


def test_apprise_asset_allow_templates_must_be_a_flag():
    """It is a yes or no answer, not a piece of text."""
    from apprise.exception import AppriseImproperlyConfigured

    with pytest.raises(AppriseImproperlyConfigured):
        AppriseAsset(allow_templates="yes")


def schema_for(*names):
    """A declared schema to check a URL's service choice against."""
    from apprise.utils.template import TemplateSchema

    return TemplateSchema.parse(list(names))


@pytest.mark.parametrize(
    "section", ["template:", "template: []", "template: {}"]
)
def test_apprise_template_empty_section_changes_nothing(section, sent):
    """A template section that declares nothing is simply empty.

    Nothing was declared, so every marker is ordinary text and each URL
    loads straight away.
    """
    services = parse(f"{section}\nurls:\n  - json://user:${{T}}@localhost/\n")

    assert len(services) == 1
    assert not isinstance(services[0], NotifyTemplate)
    assert services[0].password == "${T}"


def test_apprise_template_vars_counts_agreeing_configurations(sent):
    """Two configurations may declare the same variable the same way."""
    apobj = Apprise()
    for host in ("first", "second"):
        config = AppriseConfig()
        assert config.add_config(
            "template:\n  - shared: agreed\n"
            f"urls:\n  - json://user:${{SHARED}}@{host}/\n",
            format="yaml",
        )
        assert apobj.add(config)

    report = apobj.template_vars()

    # They agree, so the default stands and both entries are counted
    assert report["shared"]["default"] == "agreed"
    assert report["shared"]["services"] == 2


@pytest.mark.parametrize(
    "url",
    [
        "mailtos://user:pass@example.com/${EMAIL}",
        "sendgrid://SG.abcdefghij:from@example.com/${EMAIL}",
    ],
)
def test_apprise_template_email_address_value_works(url, sent):
    """A whole email address is a perfectly ordinary value.

    Some services are written as ``schema://{email}/...``, where the value
    really is ``user@host``.  Escaping must not stand in the way of that.
    """
    apobj = load(f"template:\n  - email\nurls:\n  - {url}\n")
    service = next(apobj.find(template={"email": "you@example.ca"}))

    assert "you@example.ca" in [
        target[1] if isinstance(target, tuple) else target
        for target in service.targets
    ]


def test_apprise_template_email_address_as_a_setting(sent):
    """The same address written against a setting instead."""
    apobj = load(
        "template:\n  - email\n"
        "urls:\n  - mailtos://user:pass@example.com/:\n    - to: ${EMAIL}\n"
    )
    service = next(apobj.find(template={"email": "you@example.ca"}))

    assert [target[1] for target in service.targets] == ["you@example.ca"]


def test_config_yaml_rejects_an_unusable_key():
    """Reject a YAML key that cannot be looked up."""
    # A list written as a key; there is nothing to index a mapping by
    assert ConfigBase.config_parse_yaml("? [a, b]\n: value\n") == ([], [])


def test_config_query_tag_check_without_templates():
    """With nothing templated there is no query to examine."""
    from apprise.utils.yaml import templated_tag

    assert templated_tag({"qsd": {}}, None) is False
    assert templated_tag("not a mapping", None) is False


def test_config_query_tag_check_skips_unusable_buckets(sent):
    """A query bucket that is not a mapping is passed over."""
    from apprise.utils.template import TemplatePlaceholderMap, TemplateSchema
    from apprise.utils.yaml import templated_tag

    placeholders = TemplatePlaceholderMap(TemplateSchema.parse(["t"]), "")
    results = {"qsd": None, "qsd+": {}, "qsd-": {}, "qsd:": {}}
    assert templated_tag(results, placeholders) is False


def test_apprise_template_rejects_invalid_supplied_name(sent):
    """A name that is not text is refused rather than guessed at.

    Nothing can be looked up by it, so the request is turned down
    instead of being filled in from a malformed mapping.
    """
    apobj = load("template:\n  - t\nurls:\n  - json://user:${T}@host/\n")

    with pytest.raises(AppriseTemplateError):
        list(apobj.find(template={"t": "value", 7: "ignored"}))


def run_cli(tmpdir, content, *args):
    """Run a dry run against a configuration written to disk."""
    from click.testing import CliRunner

    from apprise import cli

    config = tmpdir.join("apprise.yml")
    config.write(content)
    return CliRunner().invoke(
        cli.main, ["-b", "x", f"--config={config!s}", "--dry-run", *args]
    )


def test_apprise_cli_dry_run_supplied_value(tmpdir):
    """A value given on the command line is filled in for the preview."""
    result = run_cli(
        tmpdir,
        "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n",
        "--template-var",
        "t=supplied",
    )

    # The entry resolved, so it has a real identifier rather than a notice
    assert "missing value(s)" not in result.output
    assert "- n/a -" not in result.output
    assert result.exit_code == AppriseResultStatus.SUCCESS


def test_apprise_cli_dry_run_reports_no_identifier(tmpdir):
    """A service that keeps no stored data has no identifier to show."""
    from apprise.plugins.custom_json import NotifyJSON

    with mock.patch.object(NotifyJSON, "url_id", return_value=None):
        result = run_cli(tmpdir, "urls:\n  - json://localhost/\n")

    assert "- n/a -" in result.output
    assert result.exit_code == AppriseResultStatus.SUCCESS


def test_apprise_cli_dry_run_partial(tmpdir):
    """Some entries are ready and some are still waiting on a value."""
    result = run_cli(
        tmpdir,
        "template:\n  - t\n"
        "urls:\n  - json://user:${T}@localhost/\n  - json://ready/\n",
    )

    assert "could not be resolved" in result.output
    assert "1 of 2" in result.output

    # The same outcome a real run would report
    assert result.exit_code == AppriseResultStatus.PARTIAL


def test_apprise_cli_dry_run_failure(tmpdir):
    """Every entry is waiting on a value, so nothing would be sent."""
    result = run_cli(
        tmpdir, "template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n"
    )

    assert result.exit_code == AppriseResultStatus.FAILURE


def test_config_yaml_loader_failure_is_reported():
    """A YAML loader failure returns an empty configuration."""
    with mock.patch(
        "apprise.config.base.yaml.load",
        side_effect=AttributeError("no loader"),
    ):
        assert ConfigBase.config_parse_yaml("urls:\n  - json://a/\n") == (
            [],
            [],
        )


def test_apprise_cli_details_lists_required_packages():
    """A service that is switched off explains what it needs."""
    from click.testing import CliRunner

    from apprise import cli

    entry = {
        "service_name": "Example",
        "service_url": "https://example.ca",
        "setup_url": None,
        "enabled": False,
        "details": {"templates": ("{schema}://example",)},
        "category": "native",
        "attachment_support": False,
        "protocols": ("example",),
        "secure_protocols": None,
        "requirements": {
            "details": "Needs an extra package",
            "packages_required": ["examplelib"],
            "packages_recommended": [],
        },
    }

    with mock.patch(
        "apprise.Apprise.details",
        return_value={"version": "1.0", "asset": {}, "schemas": [entry]},
    ):
        result = CliRunner().invoke(cli.main, ["--details"])

    assert "Python Packages Required" in result.output
    assert "examplelib" in result.output


@pytest.mark.parametrize("supplied", ["a=b", ["a"], 7, ("a", "b")])
def test_apprise_template_rejects_a_non_mapping(supplied):
    """Values must arrive as name/value pairs."""
    apobj = load("template:\n  - t\nurls:\n  - json://user:${T}@host/\n")

    with pytest.raises(AppriseTemplateError):
        list(apobj.find(template=supplied))


def test_apprise_notify_failure_for_non_mapping():
    """A bad value table fails the call instead of raising."""
    apobj = load("template:\n  - t\nurls:\n  - json://user:${T}@host/\n")

    result = apobj.notify(body="x", template="a=b")
    assert not result
    assert result.status == AppriseResultStatus.FAILURE


def test_apprise_template_rejects_a_repeated_name():
    """Two spellings of one name leave no way to tell which was meant."""
    apobj = load("template:\n  - t\nurls:\n  - json://user:${T}@host/\n")

    with pytest.raises(AppriseTemplateError):
        list(apobj.find(template={"t": "one", "T": "two"}))


def test_apprise_template_name_not_captured(logging_enabled, caplog):
    """An unusable name is turned down before anything is written out."""
    apobj = load("template:\n  - t\nurls:\n  - json://user:${T}@host/\n")

    with caplog.at_level(logging.DEBUG), pytest.raises(AppriseTemplateError):
        list(apobj.find(template={"t": "value", "unused\nwrite": "x"}))

    assert "\nwrite" not in caplog.text


def test_apprise_template_empty_environment_value(monkeypatch, sent):
    """An empty environment value never replaces a real one.

    Whitespace is not a value, and a default written in the configuration
    outranks the environment in any case.
    """
    monkeypatch.setenv("APPRISE_TEMPLATE_T", "   ")
    apobj = load(
        "template:\n  t: fallback\nurls:\n  - json://user:${T}@localhost/\n"
    )

    service = next(apobj.find())
    assert service.password == "fallback"


@pytest.mark.parametrize("entry", ["bad name=x", "=x", "a\nb=x", "a-b=x"])
def test_apprise_template_cli_unusable_name(tmpdir, entry):
    """A --template-var name has to look like a variable name."""
    from click.testing import CliRunner

    from apprise import cli

    config = tmpdir.join("apprise.yml")
    config.write("urls:\n  - json://localhost\n")

    result = CliRunner().invoke(
        cli.main, ["-b", "x", f"--config={config!s}", "-tv", entry]
    )
    assert result.exit_code == 2
    assert "NAME=VALUE" in result.output


def test_apprise_template_cli_repeated_name(tmpdir):
    """The same name twice leaves no way to tell which value was meant."""
    from click.testing import CliRunner

    from apprise import cli

    config = tmpdir.join("apprise.yml")
    config.write("template:\n  - t\nurls:\n  - json://user:${T}@localhost/\n")

    result = CliRunner().invoke(
        cli.main,
        ["-b", "x", f"--config={config!s}", "-tv", "t=one", "-tv", "T=two"],
    )
    assert result.exit_code == 2
    assert "more than once" in result.output


def test_apprise_template_reads_a_configuration_once():
    """One find() visits each configuration source a single time."""
    apobj = Apprise()
    config = AppriseConfig(cache=False)
    assert config.add_config(
        "template:\n  - t\nurls:\n  - json://localhost/?to=${T}\n",
        format="yaml",
    )
    assert apobj.add(config)

    source = config[0]
    reads = []
    original = source.read

    def counted(*args, **kwargs):
        reads.append(1)
        return original(*args, **kwargs)

    source.read = counted
    assert len(list(apobj.find(template={"t": "x"}))) == 1
    assert len(reads) == 1


@pytest.mark.parametrize(
    "supplied",
    [
        MappingProxyType({"t": "value"}),
        UserDict({"t": "value"}),
    ],
)
def test_apprise_template_accepts_any_mapping(supplied, sent):
    """Any mapping is usable, not only a plain dictionary."""
    apobj = load("template:\n  - t\nurls:\n  - json://localhost/?to=${T}\n")

    service = next(apobj.find(template=supplied))
    assert service is not None


def test_apprise_template_cli_error_hides_value(tmpdir):
    """A refused entry must not echo whatever followed the equals sign."""
    from click.testing import CliRunner

    from apprise import cli

    config = tmpdir.join("apprise.yml")
    config.write("urls:\n  - json://localhost\n")

    result = CliRunner().invoke(
        cli.main,
        ["-b", "x", f"--config={config!s}", "-tv", "bad name=super-secret"],
    )
    assert result.exit_code == 2
    assert "super-secret" not in result.output
    assert "bad name" in result.output


def test_apprise_template_url_shows_a_list_setting():
    """Keep markers in list settings, such as email recipients.

    Email recipients are stored as a list. A listing that only checks text
    fields would silently lose their markers.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:pass@gmail.com:\n      to: ${T}\n"
    )[0]

    assert "to=${T}" in entry.url()


def test_apprise_template_url_lists_all_members():
    """A list mixing a marker with fixed members keeps them all."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:pass@gmail.com:\n"
        "      to:\n        - ${T}\n        - fixed@example.com\n"
    )[0]

    # Members come back the way a URL supplies a list: comma separated
    url = entry.url()
    assert "${T}" in url
    assert "fixed%40example.com" in url


def test_apprise_template_url_uses_the_argument_a_url_accepts():
    """Show YAML ``smtp:`` as the URL argument ``smtp=``.

    The YAML value is stored as ``smtp_host`` inside the service, but a URL
    must use ``smtp=`` to set that same field when read back.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:pass@gmail.com:\n      smtp: ${T}\n"
    )[0]

    url = entry.url()
    assert "smtp=${T}" in url
    assert "smtp_host" not in url

    service = Apprise.instantiate(url.replace("${T}", "mail.example.com"))
    assert service.smtp_host == "mail.example.com"


def test_apprise_template_url_shows_a_grouped_setting():
    """A header waiting on a value is shown with its URL prefix."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - json://localhost:\n      '+X-Token': ${T}\n"
    )[0]

    url = entry.url()
    assert "${T}" in url

    service = Apprise.instantiate(url.replace("${T}", "abc123"))
    assert service.headers == {"X-Token": "abc123"}


def test_apprise_template_url_skips_non_string_group_key():
    """Skip grouped settings whose YAML keys are not strings.

    YAML parses a bare ``1:`` as a number, which cannot name a URL header.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - json://localhost:\n"
        "      headers:\n        1: fixed\n        X-Token: ${T}\n"
    )[0]

    url = entry.url()
    assert "X-Token=${T}" in url
    assert "fixed" not in url


def test_apprise_template_url_deduplicates_header():
    """A header written in the URL is listed once, not twice."""
    entry = parse(
        "template:\n  - t\nurls:\n  - json://localhost/?+X-Token=${T}\n"
    )[0]

    assert entry.url().lower().count("x-token") == 1


def test_apprise_template_url_shows_a_port_waiting_on_a_value():
    """A port setting shows its marker, not the internal stand-in."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:pass@gmail.com:\n      port: ${T}\n"
    )[0]

    for url in (entry.url(), entry.url(privacy=True)):
        assert ":${T}" in url
        assert entry.placeholders.pattern.search(url) is None


def test_apprise_template_url_never_escapes_a_marker():
    """Markers stay literal so they can be found and replaced.

    A marker is not a value yet, so escaping it would leave a caller with
    nothing to search for.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:${T}@${T}.example/:\n"
        "      to: ${T}\n      smtp: ${T}\n"
    )[0]

    for url in (entry.url(), entry.url(privacy=True)):
        assert "%24%7B" not in url
        assert url.count("${T}") == 4


def test_apprise_template_url_masks_around_a_marker_only():
    """Privacy hides stored text but never the marker itself."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:pass@gmail.com:\n"
        "      smtp: secretserver.${T}\n"
    )[0]

    shown = entry.url(privacy=True)
    assert "${T}" in shown
    assert "secretserver" not in shown


def test_apprise_template_url_rejects_unparsed_marker(logging_enabled, caplog):
    """Reject a URL when a port marker disappears during parsing.

    A port is parsed as a number, so a marker there may vanish along with
    part of the hostname. Do not load the resulting broken entry.
    """
    entries = (
        # Written on its own
        "urls:\n  - mailto://user:pass@gmail.com:${T}\n",
        # Written with settings underneath it
        "urls:\n  - mailto://user:pass@gmail.com:${T}:\n"
        "      to: me@example.com\n",
    )

    for entry in entries:
        caplog.clear()
        with caplog.at_level(logging.ERROR):
            services = parse("template:\n  - t\n" + entry)

        assert services == []
        assert "can not be used at this position" in caplog.text


def test_apprise_template_url_omits_a_setting_no_url_can_set():
    """Do not show ``to=`` for ``json://``, which has no such option.

    A setting the service cannot use changes nothing when sending. Adding
    it to the listed URL would suggest the value goes somewhere it does not.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - json://user:pass@localhost/:\n      to: ${T}\n"
    )[0]

    url = entry.url()
    assert "to=" not in url

    # The same setting on a service that does have it is still shown
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailto://user:pass@gmail.com:\n      to: ${T}\n"
    )[0]
    assert "to=${T}" in entry.url()


def test_apprise_template_url_grouped_setting_replaces_the_group():
    """A header written under the URL replaces the URL's whole group.

    Apprise treats a group such as headers as one setting, so writing any
    of them under the URL drops the ones the URL carried.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - json://localhost/?+X-Token=unused:\n"
        "      '+Other': ${T}\n"
    )[0]

    url = entry.url()
    assert "${T}" in url
    assert "unused" not in url


@pytest.mark.parametrize(
    ("placement", "entry"),
    [
        ("host", "json://${V}/"),
        ("part of a host", "json://api.${V}.net/"),
        ("user", "json://${V}:pass@localhost/"),
        ("password", "json://user:${V}@localhost/"),
        ("path", "json://localhost/${V}/end"),
        ("query value", "json://localhost/?:custom=${V}"),
        ("header", "json://localhost/?+X-Tok=${V}"),
        ("setting", "mailto://u:p@gmail.com:\n      smtp: ${V}\n"),
        ("port", "mailto://u:p@gmail.com:\n      port: ${V}\n"),
        (
            "list setting",
            "mailto://u:p@gmail.com:\n      to:\n"
            "        - ${V}\n        - s@e.com\n",
        ),
        (
            "beside other text",
            "mailto://u:p@gmail.com:\n      smtp: a-${V}-b\n",
        ),
    ],
)
def test_apprise_template_marker_is_never_escaped(placement, entry):
    """A marker reads back as written wherever it was put.

    Escaping is right for everything else a URL carries, but a marker is
    not a value yet. It has to stay something a reader can spot and a
    caller can search for and replace, in both privacy modes.
    """
    suffix = "" if entry.endswith("\n") else "\n"
    services = parse("template:\n  - v\nurls:\n  - " + entry + suffix)
    entry_obj = services[0]

    for url in (entry_obj.url(), entry_obj.url(privacy=True)):
        assert "${V}" in url
        assert "%24%7B" not in url


def test_apprise_template_undeclared_marker_stays_readable():
    """A name left out of the template section is still shown as written.

    It is not a variable and no value is ever filled into it, but leaving
    it readable is what shows the author why the entry never asks for it.
    """
    entry = parse(
        "template:\n  - v\n"
        "urls:\n  - json://localhost/?a=${undeclared}&b=${V}\n"
    )[0]

    url = entry.url()
    assert "b=${V}" in url
    assert "a=${undeclared}" in url

    # ...but only the declared name is something to supply a value for
    assert entry.template_names == ("v",)


def test_apprise_template_url_uses_written_name():
    """A setting keeps the name it was written under, not an alias.

    mailto's ``from`` and ``name`` both end up in ``from_addr``, yet they
    mean different things, so the listing must not rename one to the other.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailtos://u:p@gmail.com:\n      name: ${T}\n"
    )[0]

    url = entry.url()
    assert "name=${T}" in url
    assert "from=" not in url


def test_apprise_template_url_setting_precedence():
    """A YAML setting replaces a URL alias for the same field.

    Here, ``name:`` and ``from=`` both fill ``from_addr``. Listing only the
    YAML setting ensures the displayed URL behaves like the configuration.
    """
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailtos://u:p@gmail.com?from=someone@example.com:\n"
        "      name: ${T}\n"
    )[0]

    url = entry.url()
    assert "name=${T}" in url
    assert "someone%40example.com" not in url


def test_apprise_template_url_last_written_setting_wins():
    """When two names fill one field, the later one is the one listed."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailtos://u:p@gmail.com:\n"
        "      from: real@example.com\n      name: ${T}\n"
    )[0]

    url = entry.url()
    assert "name=${T}" in url
    assert "real%40example.com" not in url


def test_apprise_template_url_round_trip():
    """A listed URL resolves to what the saved configuration resolves to.

    Settings that hold no marker are listed too, so nothing the entry needs
    is lost when the URL is filled in and loaded on its own.
    """
    config = (
        "template:\n  - t\n"
        "urls:\n  - mailtos://u:p@gmail.com:\n"
        "      to: rcpt@example.com\n      name: ${T}\n"
    )

    entry = parse(config)[0]
    url = entry.url().replace("${T}", "Bob")

    # The recipient is carried over rather than dropped
    assert "to=rcpt%40example.com" in url

    apobj = load(config)
    saved = next(apobj.find(template={"t": "Bob"}))

    reloaded = Apprise()
    assert reloaded.add(url)
    listed = next(reloaded.find())

    assert listed.from_addr == saved.from_addr
    assert listed.targets == saved.targets


def test_apprise_template_flatten_reads_nested_lists():
    """A list wrapped in more lists is read as one list of text."""
    from apprise.template import _flatten

    assert _flatten(["a", ["b", ("c",)]]) == ["a", "b", "c"]

    # A set is ordered only once every member is known to be text
    assert _flatten({"b", "a"}) == ["a", "b"]


def test_apprise_template_flatten_rejects_non_text():
    """Anything that is not text makes the whole setting unusable."""
    from apprise.template import _flatten

    # A number cannot hold a marker
    assert _flatten(["a", 5]) is None

    # ...and neither can one nested inside another list
    assert _flatten(["a", ["b", 5]]) is None

    # A set mixing text and numbers cannot even be ordered
    assert _flatten({"${T}", 5}) is None


def test_apprise_template_flatten_stops_at_the_nesting_limit():
    """A list that contains itself is abandoned rather than followed."""
    from apprise.template import _flatten

    loop = ["a"]
    loop.append(loop)
    assert _flatten(loop) is None


def test_apprise_template_url_omits_empty_setting():
    """An empty list, or a value no URL can carry, is left out."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailtos://u:p@gmail.com:\n"
        "      to: []\n      cc: null\n      name: ${T}\n"
    )[0]

    url = entry.url()
    assert "name=${T}" in url
    assert "to=" not in url
    assert "cc=" not in url


def test_apprise_template_url_args_without_a_usable_plugin():
    """A service we cannot describe simply gets no translation."""
    from apprise.template import _url_args

    # Nothing to describe at all
    assert _url_args(None) == {}

    # ...and a plugin whose details cannot be read is treated the same way
    class Broken:
        """Stands in for a service that cannot be described."""

    with mock.patch("apprise.plugins.details", side_effect=ValueError("nope")):
        assert _url_args(Broken) == {}


def test_apprise_template_settable_needs_a_known_service():
    """A schema with no plugin behind it can carry no settings."""
    entry = parse(
        "template:\n  - t\n"
        "urls:\n  - mailtos://u:p@gmail.com:\n      name: ${T}\n"
    )[0]

    # Point the entry at a schema no plugin provides
    entry.results["schema"] = "not-a-real-schema"
    assert entry._settable("name") is False
