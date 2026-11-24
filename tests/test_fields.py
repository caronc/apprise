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
    _as_list,
    _hidden,
    _typed,
    fields_to_url,
    hide_fields,
    missing_fields,
    parse_fields,
)
from apprise.manager_plugins import NotificationManager
from apprise.plugins import details

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

    # The assembled URL holds the very same fields (and the defaults the
    # plugin writes out itself), and loads the same as the original
    built = fields_to_url(fields)
    assert built.startswith("octopush://user@example.com/apikey/")
    again = parse_fields(built)
    assert {name: again[name] for name in fields} == fields
    assert (
        Apprise.instantiate(built).url()
        == Apprise.instantiate(
            "octopush://user@example.com/apikey/+15551234567?retry=2"
        ).url()
    )


@pytest.mark.skipif(not CRYPTOGRAPHY, reason="Requires cryptography")
def test_vapid_fields_with_cryptography():
    """With cryptography, a Vapid URL has fields that build the same URL."""
    fields = parse_fields("vapid://user@example.com/abc?retry=2")
    assert fields["subscriber"] == "user@example.com"
    assert fields["targets"] == ["abc"]

    built = fields_to_url(fields)
    assert built.startswith("vapid://user@example.com/abc")
    again = parse_fields(built)
    assert {name: again[name] for name in fields} == fields


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

    # A path typed with a space or a lone % is kept the way the plugin keeps
    # it from a URL that wrote it encoded
    built = fields_to_url(
        {"schema": "json", "host": "localhost", "path": "/a b/50%/"}
    )
    assert (
        Apprise.instantiate(built).fullpath
        == Apprise.instantiate("json://localhost/a%20b/50%25/").fullpath
    )

    # With nothing but the host, the URL is the one the plugin writes
    assert fields_to_url({"schema": "json", "host": "localhost"}) == (
        Apprise.instantiate("json://localhost").url()
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

    # Given both, the one given last wins, as a URL is read left to right
    fields = Apprise.instantiate(
        fields_to_url({**base, "sender": "A", "from": "B"})
    ).url_fields()
    assert fields["sender"] == "B"
    fields = Apprise.instantiate(
        fields_to_url({**base, "from": "B", "sender": "A"})
    ).url_fields()
    assert fields["sender"] == "A"


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
        assert missing_fields({"schema": "json"}) == []

    # Enabled again, all of them work as before
    assert parse_fields("json://localhost")["host"] == "localhost"
    assert fields_to_url({"schema": "json", "host": "localhost"})
    assert missing_fields({"schema": "json"}) == ["host"]


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


def test_list_entries():
    """Values are turned into a list of entries."""
    # Text is split on commas, dropping the empty entries
    assert _as_list("a,,b,") == ["a", "b"]

    # A list or set is used as it is
    assert _as_list(("a", "b")) == ["a", "b"]

    # Any other value becomes a list of one
    assert _as_list(5) == [5]


def test_several_topics_stay_topics_without_a_host():
    """Two topics with no host stay two topics on the hosted service.

    - The URL is the one the plugin writes itself, with mode=cloud, so the
      first topic is never read back as a host.
    """
    url = fields_to_url({"schema": "ntfy", "targets": ["abcd", "abcd124"]})
    fields = parse_fields(url)
    assert fields["targets"] == ["abcd", "abcd124"]
    assert fields["mode"] == "cloud"
    assert "host" not in fields


def test_one_topic_stays_a_topic_without_a_host():
    """A single topic with no host stays a topic on the hosted service."""
    fields = parse_fields(
        fields_to_url({"schema": "ntfy", "targets": ["abcd"]})
    )
    assert fields["targets"] == ["abcd"]
    assert fields["mode"] == "cloud"


def test_topics_follow_a_given_host():
    """With a host, the topics are on that server."""
    fields = parse_fields(
        fields_to_url(
            {
                "schema": "ntfy",
                "host": "ntfy.example.com",
                "targets": ["a", "b"],
            }
        )
    )
    assert fields["host"] == "ntfy.example.com"
    assert fields["targets"] == ["a", "b"]
    assert fields["mode"] == "private"


def test_a_format_a_plugin_sets_itself_is_written_back():
    """Revolt reads markdown by default; its fields keep it as markdown.

    - parse_fields() gives the plain value, never NotifyFormat.MARKDOWN.
    - The URL built from those fields loads with the same format.
    """
    url = "revolt://{}/{}".format("i" * 24, "t" * 64)
    fields = parse_fields(url)
    assert fields["format"] == "markdown"
    assert type(fields["format"]) is str

    built = fields_to_url(fields)
    assert "NotifyFormat" not in built
    assert (
        Apprise.instantiate(built).notify_format
        == Apprise.instantiate(url).notify_format
    )


def test_fields_build_the_url_the_plugin_writes():
    """fields_to_url() gives the URL the plugin itself writes.

    - Reading a URL into fields and building it again gives back what
      loading the URL gives, for services with rules of their own.
    """
    for url in (
        "ntfys://topic1?to=topic2,topic3",
        "ntfy://myserver/alerts?to=more",
        "kodi://user:pass@localhost:8080",
        "xbmc://localhost",
        "lametric://root:8b799edf-6f98-4d3a-9be7-2862fb4e5752@192.168.0.5:8080/",
        "slack://T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ/#chan",
        "json://[2001:db8::1]:8080/hook/",
    ):
        built = fields_to_url(parse_fields(url))
        assert (
            Apprise.instantiate(built).url() == Apprise.instantiate(url).url()
        ), url


def test_fields_that_do_not_load_give_no_url():
    """A required token left out makes no URL at all."""
    assert fields_to_url({"schema": "slack", "targets": ["#chan"]}) is None


def test_an_alias_names_the_value_it_stands_for():
    """An alias with a single target fills that target's value."""
    obj = Apprise.instantiate(
        fields_to_url(
            {
                "schema": "tgram",
                "bot_token": "123456789:abcdefg_hijklmnop",
                "to": "2,3",
            }
        )
    )
    assert sorted(obj.url_fields()["targets"]) == ["2", "3"]


def test_option_names_are_read_without_case():
    """Option names are read without case; key/value names and values keep it.

    - ?METHOD= is read as method, and its value stays as written.
    - +X-Token, -Page and :Key keep their case: that name is sent on.
    """
    fields = parse_fields(
        "json://localhost/?METHOD=PUT&+X-Token=AbC&-Page=Two&:Key=Val"
    )
    assert fields["method"] == "PUT"
    assert fields["headers"] == {"X-Token": "AbC"}
    assert fields["params"] == {"Page": "Two"}
    assert fields["payload"] == {"Key": "Val"}

    # Built again, the key/value names come back exactly as written
    again = parse_fields(fields_to_url(fields))
    assert again["headers"] == {"X-Token": "AbC"}
    assert again["params"] == {"Page": "Two"}
    assert again["payload"] == {"Key": "Val"}


def test_a_refused_value_is_never_logged():
    """A refused value is not written to the log."""
    from apprise.logger import logger

    with (
        mock.patch.object(logger, "isEnabledFor", return_value=True),
        mock.patch.object(logger, "callHandlers") as handlers,
    ):
        assert (
            fields_to_url({"schema": "pushplus", "token": "MY-SECRET"}) is None
        )

    logged = " ".join(
        call.args[0].getMessage() for call in handlers.call_args_list
    )
    assert "MY-SECRET" not in logged
    # The failure itself is still logged, without the value
    assert "pushplus:// fields could not be loaded" in logged


def test_quiet_logs_only_affects_its_own_block():
    """Logging works again after the block."""
    from apprise.logger import logger, quiet_logs

    with (
        mock.patch.object(logger, "isEnabledFor", return_value=True),
        mock.patch.object(logger, "callHandlers") as handlers,
    ):
        with quiet_logs():
            logger.warning("hidden")
        logger.warning("shown")

    messages = [call.args[0].getMessage() for call in handlers.call_args_list]
    assert messages == ["shown"]


def test_quiet_logs_covers_loggers_below_apprise():
    """A plugin logging through its own apprise.* logger is kept quiet too."""
    import logging

    from apprise.logger import quiet_logs

    child = logging.getLogger("apprise.custom_plugin")
    with (
        mock.patch.object(logging.Logger, "isEnabledFor", return_value=True),
        mock.patch.object(logging.Logger, "callHandlers") as handlers,
    ):
        with quiet_logs():
            child.warning("hidden")
        child.warning("shown")

    messages = [call.args[0].getMessage() for call in handlers.call_args_list]
    assert messages == ["shown"]


@pytest.mark.parametrize(
    "token, filled",
    (
        # The three parts of a webhook
        (
            "T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ",
            {
                "token_a": "T1JJ3T3L2",
                "token_b": "A1BRTD4JD",
                "token_c": "TIiajkdnlazkcOXrIdevi7FQ",
            },
        ),
        # An access token
        ("xoxb-1234-1234-abc124", {"access_token": "xoxb-1234-1234-abc124"}),
    ),
)
def test_one_alias_for_several_tokens_fills_the_right_ones(token, filled):
    """One token field may hold an access token or a webhook's three parts."""
    url = fields_to_url(
        {"schema": "slack", "token": token, "targets": ["#chan"]}
    )
    fields = Apprise.instantiate(url).url_fields()
    assert {name: fields[name] for name in filled} == filled


def test_an_alias_the_plugin_cannot_read_fills_the_first_token():
    """When the plugin reads none of the tokens, the first one gets it."""
    from apprise.fields import _aliased

    info = {
        "tokens": {"a": {"map_to": "a"}, "b": {"map_to": "b"}},
        "args": {"both": {"alias_of": ("a", "b")}},
        "kwargs": {},
    }
    plugin = mock.Mock(parse_url=mock.Mock(return_value=None))
    assert _aliased("both", "x", plugin, "test", info) == {"a": "x"}
    plugin.parse_url.assert_called_once_with("test://?both=x")


def test_every_member_of_a_list_is_kept():
    """Keep every field that contributes to the same list."""
    url = fields_to_url(
        {
            "schema": "rocket",
            "host": "localhost",
            "webhook": "abc",
            "target_channel": "chan",
            "target_user": "bob",
        }
    )
    assert sorted(parse_fields(url)["targets"]) == ["#chan", "@bob"]


def test_building_a_url_writes_no_files():
    """A URL is built without leaving a key or subscription file behind."""
    from apprise.plugins.vapid import subscription

    with mock.patch.object(
        subscription.WebPushSubscriptionManager, "autogen"
    ) as autogen:
        fields_to_url({"schema": "vapid", "subscriber": "user@example.com"})

    assert autogen.call_count == 0


def test_a_plugin_needing_arguments_the_url_always_gives_still_loads():
    """Supply required constructor arguments omitted from fields."""
    url = "sparkpost://user@localhost.localdomain/{}".format("c" * 32)
    assert fields_to_url(parse_fields(url)) is not None


def test_quiet_logs_covers_a_logger_made_after_apprise_loaded():
    """An apprise.* logger made later is quiet in the next quiet block.

    - Python's own logging is left as it is (getLogger is not replaced).
    """
    import logging

    from apprise.logger import quiet_logs

    assert "getLogger" not in vars(logging.Logger.manager)
    later = logging.getLogger("apprise.made_later")
    other = logging.getLogger("not_apprise.made_later")
    with (
        mock.patch.object(logging.Logger, "isEnabledFor", return_value=True),
        mock.patch.object(logging.Logger, "callHandlers") as handlers,
    ):
        with quiet_logs():
            later.warning("hidden")
            # A logger outside apprise is never touched
            other.warning("other")
        later.warning("shown")

    messages = [call.args[0].getMessage() for call in handlers.call_args_list]
    assert messages == ["other", "shown"]


def test_the_plugin_is_built_with_nothing_written_by_apprise():
    """Disable managed files while loading the plugin."""
    from apprise.plugins.custom_json import NotifyJSON

    with mock.patch.object(
        NotifyJSON, "__init__", autospec=True, side_effect=NotifyJSON.__init__
    ) as init:
        assert fields_to_url({"schema": "json", "host": "localhost"})

    asset = init.call_args.kwargs["asset"]
    assert asset.pem_autogen is False
    assert asset.pgp_autogen is False
    assert asset.storage_mode == "memory"


def test_a_broken_plugin_constructor_is_not_hidden():
    """Only refused fields give None; any other constructor error raises."""
    from apprise.plugins.custom_json import NotifyJSON

    with (
        mock.patch.object(
            NotifyJSON, "__init__", side_effect=TypeError("bug")
        ),
        pytest.raises(TypeError),
    ):
        fields_to_url({"schema": "json", "host": "localhost"})


def test_a_broken_url_method_is_not_hidden():
    """Fields that load but whose url() fails raise, not give None."""
    from apprise.plugins.custom_json import NotifyJSON

    with (
        mock.patch.object(NotifyJSON, "url", side_effect=RuntimeError("bug")),
        pytest.raises(RuntimeError),
    ):
        fields_to_url({"schema": "json", "host": "localhost"})


@pytest.mark.parametrize(
    "fields, expected",
    (
        # A switch sent as text is read the way a URL reads it
        ({"schema": "kodi", "host": "localhost", "image": "no"}, "image=no"),
        ({"schema": "kodi", "host": "localhost", "image": "yes"}, "image=yes"),
        # A number sent for a text entry is used as text
        ({"schema": "json", "host": "localhost", "user": 5}, "json://5@"),
        ({"schema": "dot", "apikey": 5, "device_id": "a"}, "dot://5@a"),
    ),
)
def test_values_are_given_to_the_plugin_as_their_own_type(fields, expected):
    """Convert each value to the type its entry declares."""
    assert expected in fields_to_url(fields)


@pytest.mark.parametrize("value", (True, 5, 1.5))
def test_a_number_or_switch_for_a_text_field_never_raises(value):
    """A value of the wrong plain type is refused or used, never a crash."""
    for schema in ("46elks", "amqp", "fcm", "mqtt", "pushplus"):
        for name in details(N_MGR[schema])["tokens"]:
            if name != "schema":
                fields_to_url({"schema": schema, name: value})


@pytest.mark.parametrize("tz", ("/etc/passwd", "../../etc/passwd"))
def test_a_timezone_given_as_a_file_path_is_refused(tz):
    """A file path is no timezone; the fields give no URL."""
    assert (
        fields_to_url({"schema": "json", "host": "localhost", "tz": tz})
        is None
    )


def test_an_unknown_field_name_is_logged_quoted():
    """A field name holding a line break can't start a log entry of its own."""
    from apprise.logger import logger

    with (
        mock.patch.object(logger, "isEnabledFor", return_value=True),
        mock.patch.object(logger, "callHandlers") as handlers,
    ):
        assert (
            fields_to_url({"schema": "json", "host": "x", "a\nFAKE": "1"})
            is None
        )

    logged = " ".join(
        call.args[0].getMessage() for call in handlers.call_args_list
    )
    assert "\n" not in logged
    assert "'a\\nFAKE'" in logged


@pytest.mark.parametrize(
    "fields, missing",
    (
        # Enough to notify with
        ({"schema": "json", "host": "localhost"}, []),
        ({"schema": "ntfy", "targets": ["a"]}, []),
        # An alias fills what it stands for (?to= is the targets)
        ({"schema": "ntfy", "to": "a"}, []),
        # Either way of giving the token is enough
        ({"schema": "slack", "token": "xoxb-1234-1234-abc124"}, []),
        (
            {
                "schema": "slack",
                "token": "T1JJ3T3L2/A1BRTD4JD/TIiajkdnlazkcOXrIdevi7FQ",
            },
            [],
        ),
        # A member of a list fills the list
        (
            {
                "schema": "rocket",
                "host": "h",
                "webhook": "w",
                "target_user": "b",
            },
            [],
        ),
        # A service that needs nothing after ://
        ({"schema": "blink1"}, []),
        # An API key or a login is needed, though neither is marked required
        (
            {
                "schema": "xmatters",
                "host": "example.com",
                "integration_id": "abc",
            },
            ["apikey"],
        ),
        (
            {
                "schema": "xmatters",
                "host": "example.com",
                "integration_id": "abc",
                "apikey": "key",
            },
            [],
        ),
        # Nothing given: the slot of the simplest pattern is named
        ({"schema": "ntfy"}, ["topic"]),
        ({"schema": "json"}, ["host"]),
        # Loads, but has nobody to notify
        ({"schema": "bark", "host": "localhost"}, ["targets"]),
        # Of two ways in, only the closer one is asked for
        ({"schema": "slack", "targets": ["#chan"]}, ["access_token"]),
        # An unknown schema has nothing to ask for
        ({"schema": "nope"}, []),
        ({}, []),
    ),
)
def test_missing_fields_names_what_a_url_still_needs(fields, missing):
    """missing_fields() names the required fields still empty."""
    assert missing_fields(fields) == missing


def test_an_alias_wins_over_the_field_it_stands_for():
    """A single value given under an alias wins, as ?key= wins in a URL.

    - schema://user:pass@hostname?user=user2 is read as user2.
    - ?login= is another name for the api_login field.
    - A list still gathers every entry instead.
    """
    assert (
        parse_fields("json://user:pass@hostname?user=user2")["user"] == "user2"
    )

    url = fields_to_url(
        {
            "schema": "octopush",
            "api_login": "first@example.com",
            "login": "second@example.com",
            "api_key": "key",
            "targets": ["+15551234567"],
        }
    )
    assert parse_fields(url)["api_login"] == "second@example.com"
    # A URL writes its path before its query, so the order fields are
    # given in never lets the path value win
    url = fields_to_url(
        {
            "schema": "octopush",
            "login": "second@example.com",
            "api_login": "first@example.com",
            "api_key": "key",
            "targets": ["+15551234567"],
        }
    )
    assert parse_fields(url)["api_login"] == "second@example.com"
    # Read from a URL the same way
    assert (
        parse_fields(
            "octopush://first@example.com/key/+15551234567"
            "?login=second@example.com"
        )["api_login"]
        == "second@example.com"
    )


def test_an_option_given_twice_keeps_its_last_value():
    """The last of several values for one query option is used."""
    fields = parse_fields(
        "json://user:pass@hostname?user=user2&user=user3&USER=user4"
    )
    assert fields["user"] == "user4"


@pytest.mark.parametrize("schema", ("mailto", "deltachat", "resend"))
def test_options_that_make_one_value_together_are_combined(schema):
    """?from= and ?name= become one sender, as the URL itself reads them."""
    fields = {
        "schema": schema,
        "from": "reply@example.net",
        "name": "Display Name",
    }
    if schema == "mailto":
        fields.update(user="sender", host="example.com")
    elif schema == "resend":
        fields["apikey"] = "re_abc123"
    fields["targets"] = ["to@example.org"]

    # Each service names the sender its own way (from, or from_addr)
    read = parse_fields(fields_to_url(fields))
    sender = read.get("from") or read.get("from_addr")
    assert sender == "Display Name <reply@example.net>"


@pytest.mark.parametrize(
    "name, sender",
    (
        # A whole number is written the way it is usually typed
        (15.0, "15 <reply@example.net>"),
        # A switch is written the way a URL writes it
        (True, "yes <reply@example.net>"),
    ),
)
def test_a_number_or_switch_is_combined_as_a_url_writes_it(name, sender):
    """A sender name that is not text is written as a URL would show it."""
    fields = {
        "schema": "mailto",
        "user": "sender",
        "host": "example.com",
        "from": "reply@example.net",
        "name": name,
        "targets": ["to@example.org"],
    }
    assert parse_fields(fields_to_url(fields))["from"] == sender


def test_options_that_combine_into_nothing_keep_the_value_given():
    """Blank ?from= and ?name= give no sender, so the last one is used."""
    fields = {
        "schema": "mailto",
        "user": "sender",
        "host": "example.com",
        "from": " ",
        "name": " ",
        "targets": ["to@example.org"],
    }
    assert "from=%20" in fields_to_url(fields)
