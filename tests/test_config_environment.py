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

from click.testing import CliRunner
import pytest
import requests

from apprise import Apprise, AppriseConfig, cli
from apprise.config import ConfigBase
from apprise.config.base import _ConfigEnvironment
from apprise.config.file import ConfigFile
from apprise.config.memory import ConfigMemory
from apprise.plugins.telegram import NotifyTelegram


@pytest.fixture
def environment(monkeypatch):
    """Supply test credentials through the process environment."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
    monkeypatch.setenv("PASSWORD", "test_password")


@pytest.fixture
def local_config(tmp_path):
    """Create a local configuration source without changing its contents."""

    def create(content, fmt="text", **kwargs):
        path = tmp_path / ("apprise.yaml" if fmt == "yaml" else "apprise.conf")
        path.write_text(content)
        return ConfigFile(str(path), **kwargs)

    return create


@pytest.mark.parametrize(
    "content",
    [
        "notifications=tgram://123456789:${TELEGRAM_BOT_TOKEN}/-1001234567890",
        "urls:\n  - tgram://123456789:${TELEGRAM_BOT_TOKEN}/-1001234567890:\n"
        "      tag: notifications",
        "urls:\n  - tgram://123456789:placeholder/-1001234567890:\n"
        "      bot_token: '123456789:${TELEGRAM_BOT_TOKEN}'\n"
        "      tag: notifications",
    ],
)
def test_config_environment_telegram(environment, local_config, content):
    """TEXT and YAML URL/token forms resolve through the public loader."""
    config = AppriseConfig()
    source = local_config(
        content, fmt="yaml" if content.startswith("urls:") else "text"
    )
    assert config.add(source)
    services = config.servers()
    assert len(services) == 1
    assert services[0].bot_token == "123456789:test_token"
    assert "notifications" in services[0].tags


def test_config_environment_file(environment, tmp_path):
    """Reading local configuration never writes resolved secrets back."""
    source = (
        "notifications=tgram://123456789:${TELEGRAM_BOT_TOKEN}/-1001234567890"
    )
    path = tmp_path / "apprise.conf"
    path.write_text(source)
    config = AppriseConfig()
    assert config.add(str(path))
    assert config.servers()[0].bot_token == "123456789:test_token"
    assert path.read_text() == source


@pytest.mark.parametrize("value", ["", "one\ntwo", "one\rtwo", None])
@pytest.mark.parametrize("fmt", ["text", "yaml"])
def test_config_environment_invalid(
    environment, local_config, monkeypatch, value, fmt, mocker
):
    """A bad secret rejects the whole source, including preceding URLs."""
    if value is None:
        monkeypatch.delenv("PASSWORD")
    else:
        monkeypatch.setenv("PASSWORD", value)
    source = "json://localhost\njson://user:${PASSWORD}@localhost"
    if fmt == "yaml":
        source = (
            "urls:\n  - json://localhost\n"
            "  - json://user:${PASSWORD}@localhost"
        )
    error = mocker.patch.object(ConfigBase.logger, "error")
    assert local_config(source, fmt=fmt).servers() == []
    assert "PASSWORD" in str(error.call_args)
    if value:
        assert value not in str(error.call_args)


@pytest.mark.parametrize("fmt", ["text", "yaml"])
def test_config_environment_memory(environment, fmt):
    """Raw or API-supplied content must keep placeholders literal."""
    source = "json://user:${PASSWORD}@localhost"
    if fmt == "yaml":
        source = "urls:\n  - " + source
    config = AppriseConfig()
    assert config.add_config(source, format=fmt)
    assert config.servers()[0].password == "${PASSWORD}"
    services, _ = ConfigBase.config_parse(source, config_format=fmt)
    assert services[0].password == "${PASSWORD}"


def test_config_environment_literal(environment, monkeypatch):
    """Escapes and substituted values are not recursively expanded."""
    value = "${PASSWORD}&\\literal"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", value)
    resolver = _ConfigEnvironment()
    assert resolver.expand("${TELEGRAM_BOT_TOKEN}") == value
    assert resolver.expand("$${PASSWORD}") == "${PASSWORD}"
    assert resolver.expand("$PASSWORD ${PASSWORD:-default}") == (
        "$PASSWORD ${PASSWORD:-default}"
    )


def test_config_environment_yaml_structure(
    environment, local_config, monkeypatch
):
    """YAML delimiters in a secret remain one string option value."""
    value = "quote' colon: # [list] {mapping} &anchor"
    monkeypatch.setenv("PASSWORD", value)
    config = local_config(
        "urls:\n  - json://localhost:\n"
        "      user: example\n      password: '${PASSWORD}'",
        fmt="yaml",
    )
    services = config.servers()
    assert len(services) == 1
    assert services[0].password == value


def test_config_environment_yaml_cycles(environment, local_config):
    """Recursive YAML nodes cannot cause uncontrolled recursion."""
    assert local_config("urls: &urls [*urls]", fmt="yaml").servers() == []


def test_config_environment_yaml_collision(
    environment, local_config, monkeypatch
):
    """URL collisions fail rather than silently discarding destinations."""
    monkeypatch.setenv("PASSWORD", "localhost")
    config = local_config(
        "urls:\n  - 'json://${PASSWORD}': {}\n    'json://localhost': {}",
        fmt="yaml",
    )
    assert config.servers() == []


def test_config_environment_comments_and_includes(environment):
    """Comments and includes do not expand environment values."""
    services, includes = ConfigBase.config_parse_text(
        "# ${NOT_ALLOWED}\ninclude https://localhost/${PASSWORD}\n"
        "notifications = json://localhost",
        _environment=True,
    )
    assert len(services) == 1
    assert includes == ["https://localhost/${PASSWORD}"]


def test_config_environment_cache(environment, local_config, monkeypatch):
    """Substitution follows the resolved-service cache lifecycle."""
    config = local_config("json://user:${PASSWORD}@localhost")
    assert config.servers()[0].password == "test_password"
    monkeypatch.setenv("PASSWORD", "changed")
    assert config.servers()[0].password == "test_password"
    config.cache = False
    assert config.servers()[0].password == "changed"


def test_config_environment_http(environment, mocker):
    """An HTTP source cannot enable substitution through URL options."""
    response = requests.Response()
    response.status_code = 200
    response._content = b"json://user:${PASSWORD}@localhost"
    response.encoding = "utf-8"
    response.headers["Content-Type"] = "text/plain"
    mocker.patch("requests.post", return_value=response)
    config = AppriseConfig()
    assert config.add(
        "https://localhost/apprise.conf?environment=yes&_allow_environment=yes"
    )
    assert config.servers()[0].password == "${PASSWORD}"


def test_config_environment_cli(environment, tmp_path, mocker):
    """The CLI delivers the resolved token to the notifier without I/O."""
    path = tmp_path / "apprise.conf"
    path.write_text(
        "notifications=tgram://123456789:${TELEGRAM_BOT_TOKEN}/-1001234567890"
    )
    notify = mocker.patch.object(
        NotifyTelegram, "notify", autospec=True, return_value=True
    )
    result = CliRunner().invoke(
        cli.main,
        [
            "--config",
            str(path),
            "--body",
            "test",
            "--disable-async",
            "--tag",
            "notifications",
        ],
    )
    assert result.exit_code == 0
    notify.assert_called_once()
    assert notify.call_args.args[0].bot_token == "123456789:test_token"


def test_config_environment_direct_url(environment):
    """Direct notification URLs keep their original literal behavior."""
    source = "json://user:${PASSWORD}@localhost"
    app = Apprise()
    assert app.add(source)
    assert app[0].password == "${PASSWORD}"


def test_config_environment_local_include(environment, tmp_path):
    """Local includes inherit environment expansion from a local parent."""
    child = tmp_path / "child.conf"
    child.write_text("json://user:${PASSWORD}@localhost")
    parent = tmp_path / "parent.conf"
    parent.write_text("include child.conf")
    config = ConfigFile(str(parent), recursion=1)
    assert config.servers()[0].password == "test_password"


def test_config_environment_memory_include(environment, tmp_path):
    """Allowing file includes does not grant environment access to memory."""
    child = tmp_path / "child.conf"
    child.write_text("json://user:${PASSWORD}@localhost")
    config = ConfigMemory(
        content=f"include {child}",
        format="text",
        recursion=1,
        insecure_includes=True,
    )
    assert config.servers()[0].password == "${PASSWORD}"


def test_config_environment_remote_include(environment, tmp_path, mocker):
    """Local -> HTTP -> local chains lose environment access at HTTP."""
    child = tmp_path / "child.conf"
    child.write_text("json://user:${PASSWORD}@localhost")
    parent = tmp_path / "parent.conf"
    parent.write_text("include https://localhost/config")
    response = requests.Response()
    response.status_code = 200
    response._content = f"include {child}".encode()
    response.encoding = "utf-8"
    response.headers["Content-Type"] = "text/plain"
    mocker.patch("requests.post", return_value=response)
    config = ConfigFile(str(parent), recursion=2, insecure_includes=True)
    assert config.servers()[0].password == "${PASSWORD}"


def test_config_environment_yaml_aliases(environment):
    """Shared YAML nodes stay shared and are expanded only once."""
    item = {"password": "${PASSWORD}", "port": 80, "verify": True}
    expanded = _ConfigEnvironment().expand([item, item])
    assert expanded[0] is expanded[1]
    assert expanded[0] == {
        "password": "test_password",
        "port": 80,
        "verify": True,
    }
    assert item["password"] == "${PASSWORD}"


def test_config_environment_nul(environment, mocker):
    """NUL is rejected even when a custom environment mapping supplies it."""
    resolver = _ConfigEnvironment()
    mocker.patch("apprise.config.base.os.environ.get", return_value="a\0b")
    with pytest.raises(ValueError, match="PASSWORD contains a control"):
        resolver.expand("${PASSWORD}")
