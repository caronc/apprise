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
"""Test where ``${NAME}`` may be written and what each placement reaches.

A configuration author may put a variable in one of two places:

1. **Directly in a URL.** It can fill in any field, the host included.
   Everything else that URL holds -- credentials, path, query parameters,
   headers, payload fields, and any setting written underneath -- is sent
   to whichever host the finished URL points at. A value placed in the
   host therefore decides who receives the rest.

2. **In a named YAML setting under the URL.** It only ever reaches that
   one option. The rest of the URL stays exactly as written, so the
   destination cannot move.

URL placement is deliberately unrestricted so configuration authors can
reuse one setup across several servers. Named settings are safer when a
less-trusted caller should control only one option. The Apprise API follows
the same placement rules for every access level.
"""

# Disable logging for a cleaner testing output
import logging
from unittest import mock

import pytest
import requests

from apprise import Apprise, AppriseConfig

logging.disable(logging.CRITICAL)


def load(content):
    """Build an Apprise object around a YAML configuration."""
    apobj = Apprise()
    config = AppriseConfig()
    assert config.add_config(content, format="yaml")
    assert apobj.add(config)
    return apobj


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


# A value that would reach further than one field if anything re-parsed
# it. Every placement below is checked against this.
REACHING_VALUE = "evil.example/hook"


@pytest.mark.parametrize(
    ("placement", "entry"),
    [
        ("whole host", "json://${V}/"),
        ("part of a host", "json://${V}.example/"),
        ("host beside credentials", "json://user:pass@${V}/"),
        ("host beside a path", "json://${V}/api/notify"),
        ("host beside a query value", "json://${V}/?apikey=stored"),
        ("host beside a header", "json://${V}/?:Authorization=Bearer+s"),
        ("host beside a payload field", "json://${V}/?+token=stored"),
        ("user", "json://${V}:pass@host/"),
        ("password", "json://user:${V}@host/"),
        ("path", "json://host/${V}"),
        ("query value", "json://host/?:custom=${V}"),
    ],
)
def test_variable_in_any_url_field(placement, entry, sent):
    """Confirm every URL field accepts a variable, including the host."""
    apobj = load("template:\n  - v\nurls:\n  - {}\n".format(entry))

    assert next(apobj.find(template={"v": "filled-in"})) is not None


def test_all_url_fields_as_variables(sent):
    """One URL can be made entirely of variables."""
    apobj = load(
        "template:\n  - user\n  - secret\n  - host\n"
        "urls:\n  - json://${USER}:${SECRET}@${HOST}/\n"
    )

    service = next(
        apobj.find(
            template={"user": "me", "secret": "mine", "host": "my.example"}
        )
    )
    assert service.user == "me"
    assert service.password == "mine"
    assert service.host == "my.example"


def test_host_variable_with_settings(sent):
    """Settings written under the URL do not hold the entry back."""
    apobj = load(
        "template:\n  - host\nurls:\n  - json://user:pass@${HOST}/:\n"
        "      - headers:\n          Authorization: Bearer stored\n"
    )

    assert next(apobj.find(template={"host": "my.example"})).host == (
        "my.example"
    )


@pytest.mark.parametrize(
    "source",
    ["supplied", "environment", "default"],
)
def test_host_variable_value_sources(source, monkeypatch, sent):
    """Treat supplied, environment, and default host values alike."""
    declaration = "  host: my.example" if source == "default" else "  - host"
    supplied = {"host": "my.example"} if source == "supplied" else None
    if source == "environment":
        monkeypatch.setenv("APPRISE_TEMPLATE_HOST", "my.example")

    apobj = load(
        "template:\n{}\nurls:\n  - json://user:pass@${{HOST}}/\n".format(
            declaration
        )
    )

    service = next(apobj.find(template=supplied))
    assert service.host == "my.example"
    assert service.user == "user"


def test_url_variable_changes_destination(sent):
    """A host variable chooses where the URL and its credentials are sent."""
    apobj = load("template:\n  - v\nurls:\n  - json://user:pass@${V}/\n")

    service = next(apobj.find(template={"v": REACHING_VALUE}))
    assert service.host == REACHING_VALUE
    assert service.user == "user"
    assert service.password == "pass"


def test_setting_variable_keeps_destination(sent):
    """A named setting changes one option without moving the destination."""
    apobj = load(
        "template:\n  - v\n"
        "urls:\n  - json://user:pass@fixed.example/:\n      - to: ${V}\n"
    )

    service = next(apobj.find(template={"v": REACHING_VALUE}))
    assert service.host == "fixed.example"
    assert service.user == "user"
    assert service.password == "pass"


def test_url_and_setting_scope(sent):
    """Contrast unrestricted URL placement with a scoped YAML setting."""
    in_url = load("template:\n  - v\nurls:\n  - json://user:pass@${V}/\n")
    in_setting = load(
        "template:\n  - v\n"
        "urls:\n  - json://user:pass@fixed.example/:\n      - to: ${V}\n"
    )

    moved = next(in_url.find(template={"v": REACHING_VALUE}))
    fixed = next(in_setting.find(template={"v": REACHING_VALUE}))

    assert moved.host != fixed.host
    assert fixed.host == "fixed.example"


@pytest.mark.parametrize(
    "position",
    [
        "json://localhost/?tag=${V}",
        "json://localhost/:\n    - tag: ${V}",
        "${V}://localhost/",
        "json://localhost/?${V}=1",
    ],
)
def test_disallowed_variable_positions(position):
    """Do not let values choose a service, tag, or setting name.

    These fields are read before template values are applied.
    """
    apobj = Apprise()
    config = AppriseConfig()
    config.add_config(
        "version: 2\ntemplate:\n  - v\nurls:\n  - {}\n".format(position),
        format="yaml",
    )
    apobj.add(config)

    assert list(apobj.find(template={"v": "anything"})) == []
