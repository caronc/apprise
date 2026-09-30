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

"""Exercise YAML dependency handling and fresh-interpreter imports."""

import subprocess
import sys
from textwrap import dedent

import pytest

from apprise import common
from apprise.config import ConfigBase
from apprise.config.memory import ConfigMemory


@pytest.mark.parametrize("disable_yaml", [False, True])
def test_yaml_unavailable_in_current_interpreter(
    monkeypatch, mocker, disable_yaml
):
    """Unavailable YAML warns and leaves URL/text configuration usable."""
    monkeypatch.setattr(common, "DISABLE_YAML", disable_yaml)
    monkeypatch.setitem(sys.modules, "yaml", None)
    warning = mocker.patch.object(ConfigBase.logger, "warning")
    content = "urls:\n  - json://localhost\n"

    assert ConfigBase.config_parse_yaml(content) == ([], [])
    warning.assert_called_once_with(
        "Apprise YAML support is disabled."
        if disable_yaml
        else "Apprise YAML support requires the PyYAML package."
    )

    for config_format in (None, "yaml"):
        assert len(ConfigMemory(content=content, format=config_format)) == 0
    for config_format in (None, "text"):
        assert (
            len(ConfigMemory(content="json://localhost", format=config_format))
            == 1
        )


@pytest.mark.parametrize(
    "mode", ["missing", "disabled", "enabled", "disable_after_load"]
)
def test_yaml_dependency_handling(mode):
    """URL and text users do not need to import the YAML parser."""
    script = dedent("""
        import sys
        from importlib.abc import MetaPathFinder
        from unittest.mock import patch

        mode = sys.argv[1]
        attempts = []

        class TrackYAML(MetaPathFinder):
            def find_spec(self, fullname, path=None, target=None):
                if fullname == "yaml":
                    attempts.append(fullname)
                    if mode == "missing":
                        raise ModuleNotFoundError(
                            "No module named 'yaml'", name="yaml"
                        )
                    if mode == "disabled":
                        raise AssertionError("Disabled YAML was imported")
                return None

        sys.meta_path.insert(0, TrackYAML())
        import apprise
        from apprise import common
        from apprise.config.memory import ConfigMemory

        assert "yaml" not in sys.modules
        assert not attempts
        assert common.DISABLE_YAML is False
        common.DISABLE_YAML = mode == "disabled"

        app = apprise.Apprise()
        assert app.add("json://localhost")
        assert len(app) == 1
        for config_format in (None, "text"):
            config = ConfigMemory(
                content="json://localhost", format=config_format
            )
            assert len(config) == 1
        assert not attempts

        content = "urls:\\n  - json://localhost\\n"
        if mode in ("enabled", "disable_after_load"):
            services, includes = apprise.ConfigBase.config_parse_yaml(content)
            assert len(services) == 1
            assert includes == []
            assert "yaml" in sys.modules
            if mode == "enabled":
                for config_format in (None, "yaml"):
                    assert len(ConfigMemory(
                        content=content, format=config_format
                    )) == 1
                sys.exit(0)
            common.DISABLE_YAML = True

        with patch.object(apprise.ConfigBase.logger, "warning") as warning:
            assert apprise.ConfigBase.config_parse_yaml(content) == ([], [])
            warning.assert_called_once()
            message = warning.call_args.args[0]
            if mode == "missing":
                assert "PyYAML" in message
                assert attempts
            else:
                assert "disabled" in message

        for config_format in (None, "yaml"):
            assert len(ConfigMemory(
                content=content, format=config_format
            )) == 0
        assert len(ConfigMemory(content="json://localhost")) == 1
        if mode == "disabled":
            assert not attempts
            assert "yaml" not in sys.modules
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, mode],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
