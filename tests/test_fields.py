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
"""Tests for turning URLs into their fields and back."""

from importlib.util import find_spec
from unittest import mock

import pytest

from apprise import Apprise
from apprise.fields import (
    _hidden,
    _typed,
    fields_to_url,
    hide_fields,
    parse_fields,
)
from apprise.manager_plugins import NotificationManager

N_MGR = NotificationManager()

# Whether cryptography is installed; Vapid is turned off without it. Checked
# this way so it holds however few tests run, unlike looking in sys.modules.
CRYPTOGRAPHY = find_spec("cryptography") is not None

# A value nested far deeper than any field allows
DEEP = "x"
for _ in range(1000):
    DEEP = [DEEP]


def round_trip(url):
    """Return a URL's fields and the URL those fields assemble."""
    obj = Apprise.instantiate(url)
    fields = obj.url_fields()
    return obj, fields, fields_to_url(fields)


def test_field_names_and_types():
    """Fields are named and typed the way details() describes them."""
    _, fields, _ = round_trip(
        "mailtos://user:secret@example.com"
        "?to=a@example.com,b@example.com&smtp=smtp.example.com&cto=20"
    )

    # ?to= is folded into targets and ?smtp= keeps its own name
    assert fields["schema"] == "mailtos"
    assert fields["targets"] == ["a@example.com", "b@example.com"]
    assert fields["smtp"] == "smtp.example.com"
    assert "to" not in fields
    assert "smtp_host" not in fields

    # Numbers and switches come back as numbers and switches
    assert fields["cto"] == 20.0
    assert fields["retry"] == 0
    assert fields["optional"] is False


def test_private_fields_are_hidden():
    """Entries marked private are masked; what the URL shows is kept."""
    obj = Apprise.instantiate("mailtos://user:secret@example.com")
    hidden = obj.url_fields(privacy=True)
    assert hidden["password"] == "****"
    assert hidden["user"] == "user"
    assert hidden["host"] == "example.com"

    # A list is private when any token that feeds it is (Revolt's channels)
    obj = Apprise.instantiate("revolt://abc/def")
    assert obj.url_fields(privacy=True)["targets"] == ["****"]

    # Text inside lists and maps is masked too; keys and numbers are not
    assert _hidden(["a", 1, {"key": "b"}]) == ["****", 1, {"key": "****"}]


@pytest.mark.parametrize(
    "url, secrets",
    (
        # The token is hidden by the privacy URL but not marked private
        ("mastodon://SECRETTOKEN123@hostname", ("SECRETTOKEN123",)),
        (
            "plivo://AUTHIDAAAAAAAAAAAAAA@SECRETTOKENBBBBBBBBBBBBBBBBBBBBBBBBB"
            "BBBBBB/15551231234",
            (
                "AUTHIDAAAAAAAAAAAAAA",
                "SECRETTOKENBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            ),
        ),
        # The token is read from the user name, which is not private
        ("ntfy://tk_SECRET123456@localhost/topic1", ("tk_SECRET123456",)),
    ),
)
def test_privacy_fields_match_url(url, secrets):
    """Text the privacy URL hides is masked in the privacy fields too."""
    obj = Apprise.instantiate(url)
    hidden = obj.url_fields(privacy=True)
    for secret in secrets:
        assert secret not in obj.url(privacy=True)
        assert secret not in str(hidden)

    # What the privacy URL shows is kept as it is
    assert hidden["schema"] == obj.url_fields()["schema"]
    assert hidden["verify"] is True
    assert hidden["retry"] == 0


def test_hide_fields():
    """hide_fields() masks fields the way url_fields(privacy=True) does."""
    obj = Apprise.instantiate("json://user:pass@localhost/?+X-Token=abc&-p1=v")
    fields = obj.url_fields()
    hidden = hide_fields(obj, fields)
    assert hidden == obj.url_fields(privacy=True)
    assert hidden["password"] == "****"
    assert hidden["headers"] == {"X-Token": "abc"}

    # The fields given are left as they were
    assert fields["password"] == "pass"


def test_privacy_fields_unloadable_url():
    """All text but the schema and fixed choices is masked."""
    fields = parse_fields("plivo://AUTHID@SECRETTOKEN/", privacy=True)
    assert fields["schema"] == "plivo"
    assert fields["auth_id"] == "****"
    assert fields["token"] == "****"
    assert "AUTHID" not in str(fields)
    assert "SECRETTOKEN" not in str(fields)

    # Values picked from a list of choices, and switches, are kept
    fields = parse_fields(
        "mailtos://user:secret@example.com?mode=ssl", privacy=True
    )
    assert fields["mode"] == "ssl"
    assert fields["verify"] is True
    assert fields["user"] == "****"
    assert fields["host"] == "****"


@pytest.mark.parametrize(
    "url",
    (
        "mailtos://user:secret@example.com/a@example.com"
        "?smtp=smtp.example.com",
        "json://user:pass@localhost:8080/hooks/alert?+X-Token=abc&-p1=v",
        "xml://localhost/a/b/",
        # A path that is already encoded is not encoded a second time
        "json://localhost/a%20b/100%25/c%2Fd",
        "form://localhost/a%20b/c",
        "synology://localhost/token/a%20b/",
        "apprise://localhost/path/token",
        "synology://localhost/token/path/",
        "tgram://123456789:abcdefg_hijklmnop/-123/456?silent=yes",
        "slack://bot@xoxb-1234-1234-abc124/#general",
        "slack://T1JJ3T3L2/Ft07XXXX/XXXXXXXX/YYYYYYYY/?mode=workflow",
        "nctalk://localhost/room?secret=abcd",
        "ses://user@example.com/T1JJ3T3L2/A1BRTD4JD/TIiacevi7FQ/us-west-2"
        "?token=SESSION",
        "kodi://[2001:db8::1]:8080",
    ),
)
def test_fields_round_trip(url):
    """The fields of a URL put the same URL together again."""
    obj, fields, built = round_trip(url)
    again = Apprise.instantiate(built)
    assert again.url() == obj.url()
    assert again.url_fields() == fields


TOKEN64 = "b" * 64
LAMETRIC_TOKEN = "A" * 86 + "=="


@pytest.mark.parametrize(
    "url, expected",
    (
        # ntfy's cloud mode reads its host as the first topic
        ("ntfys://abc", {"targets": ["abc"]}),
        # A token written as the user, or as the password
        (
            "ntfys://tk_abc123@localhost/topic",
            {"host": "localhost", "token": "tk_abc123", "targets": ["topic"]},
        ),
        (
            "ntfys://user:tk_abc@localhost/topic?auth=token",
            {"host": "localhost", "token": "tk_abc", "targets": ["topic"]},
        ),
        # Fluxer's cloud mode reads its host as the webhook id
        (
            "fluxer://0000000000/" + "B" * 40,
            {"webhook_id": "0000000000", "webhook_token": "B" * 40},
        ),
        # LaMetric's cloud mode reads its host as the app id
        (
            f"lametric://{LAMETRIC_TOKEN}@com.lametric.941c51dff3135bd87aa72d"
            "b9d855dd50/?mode=cloud",
            {
                "app_id": "941c51dff3135bd87aa72db9d855dd50",
                "app_ver": "1",
                "app_token": LAMETRIC_TOKEN,
            },
        ),
        # Rocket.Chat keeps what came before the @ as the webhook or the
        # password, as its mode says
        (
            "rockets://web/token@localhost/@user/?mode=webhook",
            {
                "host": "localhost",
                "webhook": "web/token",
                "targets": ["@user"],
            },
        ),
        (
            "rockets://user:pass%2Fwithslash@localhost/#channel/?mode=basic",
            {
                "host": "localhost",
                "user": "user",
                "password": "pass/withslash",
                "targets": ["#channel"],
            },
        ),
        # FCM's host is the API key in legacy mode, the project in OAuth2.
        # FCM is turned off without cryptography.
        pytest.param(
            "fcm://abc123/device",
            {"apikey": "abc123", "targets": ["device"]},
            marks=pytest.mark.skipif(
                not CRYPTOGRAPHY, reason="Requires cryptography"
            ),
        ),
        pytest.param(
            "fcm://myproject/device?keyfile=/tmp/keyfile.json",
            {
                "keyfile": "file:///tmp/keyfile.json",
                "project": "myproject",
                "targets": ["device"],
            },
            marks=pytest.mark.skipif(
                not CRYPTOGRAPHY, reason="Requires cryptography"
            ),
        ),
        # Matrix's t2bot mode reads its host as the webhook token
        (f"matrix://{TOKEN64}/?mode=t2bot", {"password": TOKEN64}),
    ),
)
def test_a_value_is_read_into_one_field(url, expected):
    """A value the URL writes once fills one field, and comes back once."""
    obj, fields, built = round_trip(url)
    tokens = {
        name: value
        for name, value in fields.items()
        if name != "schema" and name in obj.template_tokens
    }
    assert tokens == expected
    assert Apprise.instantiate(built).url() == obj.url()


def test_email_host_round_trip():
    """An email written as the host comes back as the same email."""
    # Octopush needs nothing extra, so this runs wherever Apprise does
    fields = parse_fields(
        "octopush://user@example.com/apikey/+15551234567?retry=2"
    )
    assert fields["api_login"] == "user@example.com"
    assert fields["targets"] == ["+15551234567"]

    # Options every service shares are kept too
    assert fields["retry"] == 2

    # The assembled URL reads back to the very same fields, and loads
    built = fields_to_url(fields)
    assert built.startswith("octopush://user@example.com/apikey/")
    assert parse_fields(built) == fields
    assert Apprise.instantiate(built) is not None


@pytest.mark.skipif(not CRYPTOGRAPHY, reason="Requires cryptography")
def test_vapid_fields_with_cryptography():
    """With cryptography, a Vapid URL has fields that build the same URL."""
    fields = parse_fields("vapid://user@example.com/abc?retry=2")
    assert fields["subscriber"] == "user@example.com"
    assert fields["targets"] == ["abc"]

    built = fields_to_url(fields)
    assert built.startswith("vapid://user@example.com/abc")
    assert parse_fields(built) == fields


@pytest.mark.skipif(
    CRYPTOGRAPHY, reason="Requires that cryptography NOT be installed"
)
def test_vapid_fields_without_cryptography():
    """Without cryptography, Vapid is turned off rather than failing.

    - It has no fields, nothing is built for it, and it does not load.
    - Every other service carries on as normal.
    """
    assert N_MGR["vapid"].enabled is False
    assert parse_fields("vapid://user@example.com/abc") == {}
    assert fields_to_url({"schema": "vapid", "subscriber": "a@b.com"}) is None
    assert Apprise.instantiate("vapid://user@example.com/abc") is None
    assert parse_fields("json://localhost")["schema"] == "json"


def test_key_value_option_maps():
    """Each +, - and : option comes back in its own map."""
    _, fields, built = round_trip(
        "json://localhost?+X-Token=abc&-p1=v&:key=val"
    )
    assert fields["headers"] == {"X-Token": "abc"}
    assert fields["params"] == {"p1": "v"}
    assert fields["payload"] == {"key": "val"}
    assert "%2BX-Token=abc" in built


def test_fields_from_a_form():
    """Fields typed into a form, in any order, make a working URL."""
    url = fields_to_url(
        {
            "schema": "MAILTOS",
            "mode": "ssl",
            "targets": ["a@example.com"],
            "host": "example.com",
            "password": "p@ss/word",
            "user": "user",
            "port": None,
            "optional": True,
        }
    )
    obj = Apprise.instantiate(url)
    assert obj.password == "p@ss/word"
    assert obj.targets == [(False, "a@example.com")]
    assert "mode=ssl" in obj.url()
    assert "optional=yes" in obj.url()

    # A path typed with a space or a lone % is encoded
    assert (
        fields_to_url(
            {"schema": "json", "host": "localhost", "path": "/a b/50%/"}
        )
        == "json://localhost/a%20b/50%25/"
    )

    # With nothing but the URL itself, there is no query string
    assert fields_to_url({"schema": "json", "host": "localhost"}) == (
        "json://localhost/"
    )


@pytest.mark.parametrize(
    "fields",
    (
        None,
        "mailtos://user@example.com",
        {},
        {"schema": 5},
        {"schema": "unknown"},
        {"schema": "json", "host": "localhost", "nope": "x"},
        {"schema": "json", "host": "localhost", 5: "x"},
        {"schema": "json", "host": "localhost", "headers": "X-Token=abc"},
        # Values must have the shape their entry describes
        {"schema": "json", "host": "localhost", "verify": [True]},
        {"schema": "json", "host": "localhost", "headers": {"a": ["b"]}},
        {"schema": "tgram", "bot_token": "1:a", "targets": [["1"]]},
        {"schema": "json", "host": "localhost", "verify": DEEP},
        # An alias takes the shape of what it stands for (sender is text)
        {
            "schema": "sfr",
            "user": "user",
            "password": "pass",
            "space_id": "000",
            "targets": ["0000000000"],
            "from": ["A", "B"],
        },
    ),
)
def test_fields_refused(fields):
    """Unknown schemas and names, and badly shaped values, are refused."""
    assert fields_to_url(fields) is None


@pytest.mark.parametrize(
    "schema", ("dbus", "glib", "gnome", "macosx", "windows")
)
def test_desktop_unreadable_url(schema):
    """A URL a desktop service cannot read gives nothing back.

    - It holds whether or not the service's own library is installed.
    """
    assert N_MGR[schema].parse_url(None) is None


def test_field_values_quoted():
    """Text is quoted so it never adds options or splits differently."""
    # Brackets only stay unquoted around a real IPv6 host
    built = fields_to_url(
        {"schema": "gotify", "host": "example.com", "token": "[abc?verify=no]"}
    )
    assert "%5Babc%3Fverify%3Dno%5D" in built
    assert "verify=no" not in built

    # An email keeps its @ only when it is one valid address
    phone = ["+15551234567"]
    built = fields_to_url(
        {
            "schema": "octopush",
            "api_login": "victim@example.com@evil.com",
            "api_key": "key",
            "targets": phone,
        }
    )
    assert "victim%40example.com%40evil.com" in built
    built = fields_to_url(
        {
            "schema": "octopush",
            "api_login": "me@example.com",
            "api_key": "key",
            "targets": phone,
        }
    )
    assert built.startswith("octopush://me@example.com/")


def test_alias_fields_merged():
    """Content given under an alias is kept, merged into what it stands for."""
    # A list alias adds to the list it stands for
    obj = Apprise.instantiate(
        fields_to_url(
            {
                "schema": "tgram",
                "bot_token": "123456789:abcdefg_hijklmnop",
                "targets": ["1"],
                "to": "2",
            }
        )
    )
    fields = obj.url_fields()
    assert sorted(fields["targets"]) == ["1", "2"]
    assert "to" not in fields

    # A one-to-one alias fills in the item it stands for
    base = {
        "schema": "sfr",
        "user": "user",
        "password": "pass",
        "space_id": "000",
        "targets": ["0000000000"],
    }
    fields = Apprise.instantiate(
        fields_to_url({**base, "from": "MyApp"})
    ).url_fields()
    assert fields["sender"] == "MyApp"
    assert "from" not in fields

    # Given both, the result is whatever the URL itself would give
    by_hand = Apprise.instantiate(
        "sfr://user:pass@000/0000000000?sender=A&from=B"
    )
    fields = Apprise.instantiate(
        fields_to_url({**base, "sender": "A", "from": "B"})
    ).url_fields()
    assert fields["sender"] == by_hand.url_fields()["sender"]


def test_list_member_fields_merged():
    """Tokens that add to the same list all end up in it."""
    obj = Apprise.instantiate(
        fields_to_url(
            {
                "schema": "slack",
                "access_token": "xoxb-1234-1234-abc124",
                "targets": ["#general"],
                "target_user": "@bob",
            }
        )
    )
    assert sorted(obj.url_fields()["targets"]) == ["#general", "@bob"]


def test_fields_unloadable_url():
    """What a URL holds is read even when its service would not load it."""
    # Nothing but the schema, in any case
    assert parse_fields("MAILTO://")["schema"] == "mailto"
    fields = parse_fields("mailtos://user:secret@example.com")
    assert (fields["user"], fields["host"]) == ("user", "example.com")
    assert (
        parse_fields("mailtos://user:secret@example.com", True)["password"]
        == "****"
    )

    # An unknown schema, or text that is not a URL, holds nothing
    for url in ("nope://x", "mailtos:", "tgram://bad", None):
        assert parse_fields(url) == {}


def test_disabled_service_fields():
    """A disabled service is treated like one that is not known."""
    with mock.patch.object(N_MGR["json"], "enabled", False):
        assert parse_fields("json://localhost") == {}
        assert fields_to_url({"schema": "json", "host": "localhost"}) is None

    # Enabled again, both work as before
    assert parse_fields("json://localhost")["host"] == "localhost"
    assert fields_to_url({"schema": "json", "host": "localhost"})


def test_broken_url_fields():
    """A URL cut off mid-way gives no fields, whatever its service."""
    for schema in N_MGR.schemas():
        for url in (f"{schema}://[", f"{schema}://:@[", f"{schema}:///["):
            assert isinstance(parse_fields(url), dict), url


def test_unreadable_own_url():
    """A URL its own plugin cannot read back has no fields."""
    obj = Apprise.instantiate("json://localhost")
    with mock.patch.object(type(obj), "parse_url", return_value=None):
        assert obj.url_fields() == {}


def test_typed_values():
    """Values are converted to the type their entry describes."""
    # Sets have no order, so they come back sorted
    assert _typed({"b", "a"}, {"type": "list:string"}) == ["a", "b"]

    # Lists split text on commas and drop empty entries
    assert _typed("a, ,b", {"type": "list:string"}) == ["a", "b"]

    # Anything that is not plain data is left out
    assert _typed(object(), {"type": "list:string"}) is None
    assert _typed(object(), {"type": "string"}) is None

    # Text that is not a number is kept as written
    assert _typed("abc", {"type": "int"}) == "abc"
    assert _typed("1.5", {"type": "float"}) == 1.5
    assert _typed(5, {"type": "string"}) == "5"
    assert _typed("yes", {"type": "bool"}) is True
