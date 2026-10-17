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


import logging
import ssl
from unittest import mock

from helpers import AppriseURLTester
import pytest

from apprise import Apprise, NotifyFormat
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.amqp import NotifyAMQP, v091, v10
from apprise.plugins.amqp.common import (
    AMQPConfig,
    AMQPError,
    AMQPMessage,
    AMQPVersion,
)
from apprise.plugins.amqp.v091 import AMQP091Adapter
from apprise.plugins.amqp.v10 import AMQP10Adapter

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)

# Skip markers for tests that drive the real libraries
requires_pika = pytest.mark.skipif(
    not v091.PIKA_SUPPORT_AVAILABLE, reason="Requires pika"
)
requires_proton = pytest.mark.skipif(
    not v10.PROTON_SUPPORT_AVAILABLE, reason="Requires python-qpid-proton"
)

# Our Testing URLs
apprise_url_tests = (
    (
        "amqp://",
        {
            # No hostname
            "instance": None,
        },
    ),
    (
        "amqp://localhost",
        {
            # Loads, but has nowhere to publish to
            "instance": NotifyAMQP,
            "notify_response": False,
        },
    ),
    (
        "amqp://localhost/queue",
        {
            "instance": NotifyAMQP,
        },
    ),
    (
        "amqp://user:pass@localhost:5000/queue1/queue2",
        {
            "instance": NotifyAMQP,
            "privacy_url": "amqp://user:****@localhost:5000/queue1/queue2",
        },
    ),
    (
        "amqps://user@localhost/queue?verify=no",
        {
            "instance": NotifyAMQP,
            "privacy_url": "amqps://user@localhost/queue",
        },
    ),
    (
        "amqp://localhost/?exchange=alerts",
        {
            # A fanout style exchange needs no routing key
            "instance": NotifyAMQP,
        },
    ),
    (
        "amqp://localhost/key?exchange=amq.topic&mandatory=no"
        "&persistent=no&priority=5&ttl=60000&vhost=home&+source=nas",
        {
            "instance": NotifyAMQP,
        },
    ),
    (
        "amqp://localhost/?version=1.0&to=/queues/alerts",
        {
            "instance": NotifyAMQP,
        },
    ),
    (
        "amqps://user:pass@localhost/queue?ver=1&vhost=vhost:home",
        {
            "instance": NotifyAMQP,
        },
    ),
    (
        "amqp://localhost/queue?version=2",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "amqp://localhost/queue?priority=256",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "amqp://localhost/queue?ttl=-1",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "amqp://localhost/queue?ttl=soon",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "amqp://localhost/queue?exchange=" + "x" * 256,
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
)


@pytest.fixture
def amqp_stub():
    """Pretend both libraries are installed and stub out the network."""
    with (
        mock.patch.object(AMQP091Adapter, "enabled", True),
        mock.patch.object(AMQP10Adapter, "enabled", True),
        mock.patch.object(AMQP091Adapter, "connect") as connect091,
        mock.patch.object(AMQP091Adapter, "publish") as publish091,
        mock.patch.object(AMQP091Adapter, "close") as close091,
        mock.patch.object(AMQP10Adapter, "connect") as connect10,
        mock.patch.object(AMQP10Adapter, "publish") as publish10,
        mock.patch.object(AMQP10Adapter, "close") as close10,
    ):
        yield {
            AMQPVersion.V091: (connect091, publish091, close091),
            AMQPVersion.V10: (connect10, publish10, close10),
        }


def test_plugin_amqp_urls(amqp_stub):
    """NotifyAMQP() Apprise URLs."""
    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_amqp_no_libraries():
    """NotifyAMQP() stays available but refuses to load without a library."""
    with (
        mock.patch.object(AMQP091Adapter, "enabled", False),
        mock.patch.object(AMQP10Adapter, "enabled", False),
    ):
        # The plugin itself is always available and lists what to install
        assert NotifyAMQP.enabled is True
        assert NotifyAMQP.requirements["packages_recommended"] == [
            "pika",
            "python-qpid-proton",
        ]

        # A URL cannot be loaded
        assert Apprise.instantiate("amqp://localhost/queue") is None
        assert Apprise.instantiate("amqp://localhost/queue?ver=1") is None

        # Direct use explains what to install
        with pytest.raises(AppriseImproperlyConfigured, match="pip install"):
            NotifyAMQP(host="localhost", targets="queue")


def test_plugin_amqp_version_default(amqp_stub):
    """NotifyAMQP() prefers 0.9.1, but uses whatever is installed."""
    # Both installed
    obj = NotifyAMQP(host="localhost", targets="queue")
    assert obj.version == AMQPVersion.V091

    # Only proton installed
    with mock.patch.object(AMQP091Adapter, "enabled", False):
        obj = NotifyAMQP(host="localhost", targets="queue")
        assert obj.version == AMQPVersion.V10

        # Asking for 0.9.1 explains what to install
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyAMQP(host="localhost", targets="queue", version="0.9")

    # Only pika installed
    with mock.patch.object(AMQP10Adapter, "enabled", False):
        obj = NotifyAMQP(host="localhost", targets="queue")
        assert obj.version == AMQPVersion.V091

        with pytest.raises(AppriseImproperlyConfigured):
            NotifyAMQP(host="localhost", targets="queue", version="1.0")


def test_plugin_amqp_version_from_options(amqp_stub):
    """NotifyAMQP() picks the version an exclusive option belongs to."""
    with mock.patch.object(AMQP091Adapter, "enabled", True):
        # Only proton would normally mean 1.0, but these options are 0.9.1
        with mock.patch.object(AMQP10Adapter, "enabled", True):
            for kwargs in (
                {"exchange": "amq.topic"},
                {"mandatory": "no"},
                {"mandatory": False},
            ):
                obj = NotifyAMQP(host="localhost", targets="q", **kwargs)
                assert obj.version == AMQPVersion.V091

        # Empty values do not count as given
        with mock.patch.object(AMQP091Adapter, "enabled", False):
            obj = NotifyAMQP(
                host="localhost", targets="q", exchange="", mandatory=""
            )
            assert obj.version == AMQPVersion.V10

            # A 0.9.1 option without pika explains what to install
            with pytest.raises(AppriseImproperlyConfigured, match="pika"):
                NotifyAMQP(host="localhost", targets="q", exchange="x")

    # The same works straight from a URL, which keeps it short
    obj = Apprise.instantiate("amqp://localhost/key?exchange=amq.topic")
    assert obj.version == AMQPVersion.V091
    assert "version=0.9.1" in obj.url()


def test_plugin_amqp_version_option_ignored(amqp_stub):
    """NotifyAMQP() warns about and drops options of the other version."""
    with mock.patch.object(NotifyAMQP, "logger") as mock_logger:
        obj = NotifyAMQP(
            host="localhost",
            targets="/queues/q",
            version="1.0",
            exchange="x",
            mandatory="no",
        )

    assert obj.version == AMQPVersion.V10
    assert obj.exchange == ""
    assert obj.mandatory is True

    # One warning for each ignored option
    warned = [c.args[1] for c in mock_logger.warning.call_args_list]
    assert warned == ["exchange", "mandatory"]

    # Neither is written back into the URL
    assert "exchange=" not in obj.url()
    assert "mandatory=" not in obj.url()


def test_plugin_amqp_version_ambiguous(amqp_stub):
    """NotifyAMQP() uses the default when options point at both versions."""
    # Pretend mandatory belonged to AMQP 1.0 so both versions are implied
    options = {"exchange": AMQPVersion.V091, "mandatory": AMQPVersion.V10}
    with mock.patch.dict(
        "apprise.plugins.amqp.base.AMQP_VERSION_OPTIONS", options
    ):
        # Both libraries installed means 0.9.1, keeping the exchange
        obj = NotifyAMQP(
            host="localhost", targets="q", exchange="x", mandatory="no"
        )
        assert obj.version == AMQPVersion.V091
        assert obj.exchange == "x"
        assert obj.mandatory is True

        # Only proton installed means 1.0, keeping the other option
        with mock.patch.object(AMQP091Adapter, "enabled", False):
            obj = NotifyAMQP(
                host="localhost", targets="q", exchange="x", mandatory="no"
            )
            assert obj.version == AMQPVersion.V10
            assert obj.exchange == ""
            assert obj.mandatory is False


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("0.9.1", AMQPVersion.V091),
        ("0.9", AMQPVersion.V091),
        ("0-9-1", AMQPVersion.V091),
        ("v0.9.1", AMQPVersion.V091),
        ("1.0", AMQPVersion.V10),
        ("1", AMQPVersion.V10),
        ("V1", AMQPVersion.V10),
        (1.0, AMQPVersion.V10),
    ),
)
def test_plugin_amqp_version_spelling(amqp_stub, value, expected):
    """NotifyAMQP() accepts the common ways to write a version."""
    obj = NotifyAMQP(host="localhost", targets="queue", version=value)
    assert obj.version == expected


@pytest.mark.parametrize(
    "value",
    (
        "2",
        "0.8",
        "",
        "abc",
        "0.9.1.1",
        "-1",
        "junk0.9.1x",
        "release-v1.0-final",
    ),
)
def test_plugin_amqp_version_invalid(amqp_stub, value):
    """NotifyAMQP() refuses versions it does not know."""
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAMQP(host="localhost", targets="queue", version=value)


def test_plugin_amqp_options(amqp_stub):
    """NotifyAMQP() validates and stores its options."""
    # Defaults
    obj = NotifyAMQP(host="localhost", targets="queue")
    assert obj.exchange == ""
    assert obj.vhost is None
    assert obj.persistent is True
    assert obj.mandatory is True
    assert obj.priority is None
    assert obj.ttl is None
    assert obj.headers == {}

    # Everything set
    obj = NotifyAMQP(
        host="localhost",
        targets="queue",
        exchange="amq.topic",
        vhost="home",
        persistent="no",
        mandatory="no",
        priority="9",
        ttl=0,
        headers={"a": 1},
    )
    assert obj.exchange == "amq.topic"
    assert obj.vhost == "home"
    assert obj.persistent is False
    assert obj.mandatory is False
    assert obj.priority == 9
    assert obj.ttl == 0
    assert obj.headers == {"a": "1"}

    # Unusable values fall back quietly
    obj = NotifyAMQP(
        host="localhost",
        targets="queue",
        exchange=42,
        vhost="",
        priority="",
        headers="a=b",
    )
    assert obj.exchange == ""
    assert obj.vhost is None
    assert obj.priority is None
    assert obj.headers == {}

    # Out of range or not a number at all
    for kwargs in (
        {"priority": -1},
        {"priority": 256},
        {"priority": object()},
        {"ttl": 4294967296},
    ):
        with pytest.raises(AppriseImproperlyConfigured):
            NotifyAMQP(host="localhost", targets="queue", **kwargs)


def test_plugin_amqp_shortstr_limits(amqp_stub):
    """NotifyAMQP() enforces the AMQP 0.9.1 name length limit."""
    long_name = "x" * 256

    # Exchange and virtual host names that are too long
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAMQP(host="localhost", targets="q", exchange=long_name)

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAMQP(host="localhost", targets="q", vhost=long_name)

    # Exactly 255 bytes is fine (multi-byte characters count as bytes)
    obj = NotifyAMQP(host="localhost", targets="q", vhost="x" * 255)
    assert obj.vhost == "x" * 255

    with pytest.raises(AppriseImproperlyConfigured):
        NotifyAMQP(host="localhost", targets="q", vhost="é" * 128)

    # A routing key that is too long is set aside, not fatal
    obj = NotifyAMQP(host="localhost", targets=["ok", long_name])
    assert obj.targets == ["ok"]
    assert obj.invalid_targets == [long_name]
    assert len(obj) == 1

    # AMQP 1.0 has no such limit
    obj = NotifyAMQP(
        host="localhost", targets=long_name, version="1.0", vhost=long_name
    )
    assert obj.targets == [long_name]
    assert obj.vhost == long_name


def test_plugin_amqp_v10_ignores_exchange(amqp_stub):
    """NotifyAMQP() drops the exchange when AMQP 1.0 is used."""
    obj = NotifyAMQP(
        host="localhost", targets="/queues/q", version="1.0", exchange="x"
    )
    assert obj.exchange == ""

    # 0.9.1-only options are not written into the URL
    assert "exchange=" not in obj.url()
    assert "mandatory=" not in obj.url()


def test_plugin_amqp_url_round_trip(amqp_stub):
    """NotifyAMQP() URLs load back into the same configuration."""
    for url in (
        "amqp://localhost/queue",
        "amqps://user:pass@localhost:5000/q1/q2?exchange=amq.topic"
        "&vhost=home&priority=1&ttl=500&persistent=no&mandatory=no"
        "&+source=nas&+level=high",
        "amqps://user@[::1]/q?ver=1&to=/queues/a,/exchanges/x/key",
        "amqp://localhost/q?version=1.0&vhost=vhost:home",
    ):
        obj1 = Apprise.instantiate(url)
        assert isinstance(obj1, NotifyAMQP)

        obj2 = Apprise.instantiate(obj1.url())
        assert isinstance(obj2, NotifyAMQP)

        # Same connection, same targets, same options
        assert obj1.url_identifier == obj2.url_identifier
        assert sorted(obj1.targets) == sorted(obj2.targets)
        assert obj1.exchange == obj2.exchange
        assert obj1.priority == obj2.priority
        assert obj1.ttl == obj2.ttl
        assert obj1.persistent == obj2.persistent
        assert obj1.mandatory == obj2.mandatory
        assert obj1.headers == obj2.headers

    # Invalid targets survive the trip as well
    obj = NotifyAMQP(host="localhost", targets=["ok", "x" * 256])
    obj2 = Apprise.instantiate(obj.url())
    assert obj2.targets == ["ok"]
    assert obj2.invalid_targets == ["x" * 256]


def test_plugin_amqp_url_details(amqp_stub):
    """NotifyAMQP() builds its URL and identity as expected."""
    # Default ports are left out
    obj = Apprise.instantiate("amqps://user:pass@localhost:5671/q")
    assert obj.url().startswith("amqps://user:pass@localhost/q?")
    assert (
        obj.url_identifier
        == Apprise.instantiate("amqps://user:pass@localhost/q").url_identifier
    )

    # The version always appears, so the URL means the same thing even
    # when different libraries are installed elsewhere
    assert "version=0.9.1" in obj.url()

    # Targets with slashes go into to=, others stay in the path
    obj = Apprise.instantiate(
        "amqp://localhost/plain?ver=1&to=/queues/a,back\\slash"
    )
    url = obj.url()
    assert url.startswith("amqp://localhost/plain?")
    assert "to=%2Fqueues%2Fa%2Cback%5Cslash" in url

    # Identity changes with the things that pick a connection
    base = Apprise.instantiate("amqp://localhost/q")
    for other in (
        "amqps://localhost/q",
        "amqp://localhost/q?ver=1",
        "amqp://user@localhost/q",
        "amqp://localhost:1234/q",
        "amqp://localhost/q?vhost=home",
    ):
        assert Apprise.instantiate(other).url_identifier != base.url_identifier

    # ...but not with targets or message options
    for same in (
        "amqp://localhost/other",
        "amqp://localhost/q?priority=1&exchange=x",
    ):
        assert Apprise.instantiate(same).url_identifier == base.url_identifier


def test_plugin_amqp_parse_url(amqp_stub):
    """NotifyAMQP() reads every option out of the URL."""
    results = NotifyAMQP.parse_url(
        "amqp://localhost/a/b?to=c,/queues/d&exchange=ex&vhost=vh"
        "&persistent=no&mandatory=no&priority=3&ttl=10&+h1=v1"
        "&ver=1&version=0.9"
    )
    assert sorted(results["targets"]) == ["/queues/d", "a", "b", "c"]
    assert results["exchange"] == "ex"
    assert results["vhost"] == "vh"
    assert results["persistent"] is False
    assert results["mandatory"] is False
    assert results["priority"] == "3"
    assert results["ttl"] == "10"
    assert results["headers"] == {"h1": "v1"}

    # version= wins over its ver= alias
    assert results["version"] == "0.9"

    # ver= on its own still works
    results = NotifyAMQP.parse_url("amqp://localhost/a?ver=1")
    assert results["version"] == "1"

    # No hostname to connect to
    assert NotifyAMQP.parse_url("amqp://") is None


def test_plugin_amqp_send(amqp_stub):
    """NotifyAMQP() publishes one message to every target."""
    connect, publish, close = amqp_stub[AMQPVersion.V091]

    obj = Apprise.instantiate(
        "amqp://user:pass@localhost/q1/q2?exchange=ex&vhost=home"
        "&priority=4&ttl=100&+source=nas&cto=2&rto=3"
    )
    assert obj.notify(title="Title", body="Body") is True

    # One connection, closed afterwards
    assert connect.call_count == 1
    assert close.call_count == 1

    # Both targets got the same message
    assert [c.args[0] for c in publish.call_args_list] == ["q1", "q2"]
    message = publish.call_args_list[0].args[1]
    assert message is publish.call_args_list[1].args[1]

    assert isinstance(message, AMQPMessage)
    assert message.body == b"Title\r\nBody"
    assert message.content_type == "text/plain; charset=utf-8"
    assert message.app_id == obj.app_id
    assert message.persistent is True
    assert message.priority == 4
    assert message.ttl == 100
    assert message.headers == {"source": "nas"}

    # No headers are sent as None rather than an empty table
    publish.reset_mock()
    obj = Apprise.instantiate("amqp://localhost/q")
    assert obj.notify(body="Body") is True
    assert publish.call_args.args[1].headers is None


def test_plugin_amqp_config(amqp_stub):
    """NotifyAMQP() hands the adapter everything it needs to connect."""
    configs = []

    def capture(self, config):
        # Keep the config so it can be checked below
        configs.append(config)
        self.config = config

    with mock.patch.object(AMQP091Adapter, "__init__", capture):
        obj = Apprise.instantiate(
            "amqps://user:pass@example.com/q?exchange=ex&vhost=home"
            "&mandatory=no&verify=no&cto=2&rto=3"
        )
        assert obj.notify(body="Body") is True

        obj = Apprise.instantiate("amqp://example.com:1234/q")
        assert obj.notify(body="Body") is True

    assert configs[0] == AMQPConfig(
        host="example.com",
        port=5671,
        secure=True,
        verify_certificate=False,
        user="user",
        password="pass",
        vhost="home",
        connect_timeout=2.0,
        read_timeout=3.0,
        exchange="ex",
        mandatory=False,
    )

    # Plain connections default to 5672 unless told otherwise
    assert configs[1].port == 1234
    assert configs[1].secure is False
    assert configs[1].user is None


@pytest.mark.parametrize(
    ("body_format", "content_type", "body"),
    (
        (NotifyFormat.TEXT, "text/plain", b"T & <x>\r\nBody _*#<"),
        (NotifyFormat.MARKDOWN, "text/markdown", b"# T & <x>\nBody _*#<"),
        (
            NotifyFormat.HTML,
            "text/html",
            # HTML input means the title is HTML too, so it is kept as-is
            b"<b>T & <x></b><br />\r\nBody _*#<",
        ),
    ),
)
def test_plugin_amqp_formats(amqp_stub, body_format, content_type, body):
    """NotifyAMQP() relays each format untouched with its content type."""
    _, publish, _ = amqp_stub[AMQPVersion.V091]

    obj = Apprise.instantiate("amqp://localhost/q")
    assert obj.notify(
        title="T & <x>", body="Body _*#<", body_format=body_format
    )

    message = publish.call_args.args[1]
    assert message.content_type == f"{content_type}; charset=utf-8"
    assert message.body == body


def test_plugin_amqp_send_direct(amqp_stub):
    """NotifyAMQP() treats a send() without a format as plain text."""
    _, publish, _ = amqp_stub[AMQPVersion.V091]

    obj = NotifyAMQP(host="localhost", targets="q")

    # A lone surrogate cannot be encoded, so it is replaced
    assert obj.send(body="bad \ud800 char") is True
    message = publish.call_args.args[1]
    assert message.content_type == "text/plain; charset=utf-8"
    assert message.body == b"bad ? char"


def test_plugin_amqp_send_exchange_only(amqp_stub):
    """NotifyAMQP() publishes once to an exchange with no targets."""
    _, publish, _ = amqp_stub[AMQPVersion.V091]

    obj = Apprise.instantiate("amqp://localhost/?exchange=amq.fanout")
    assert obj.notify(body="Body") is True
    assert publish.call_count == 1
    assert publish.call_args.args[0] == ""

    # AMQP 1.0 has no exchange to fall back on
    _, publish, _ = amqp_stub[AMQPVersion.V10]
    obj = Apprise.instantiate("amqp://localhost/?exchange=x&ver=1")
    assert obj.notify(body="Body") is False
    assert publish.call_count == 0


def test_plugin_amqp_send_v10(amqp_stub):
    """NotifyAMQP() uses the AMQP 1.0 adapter when asked to."""
    connect, publish, close = amqp_stub[AMQPVersion.V10]

    obj = Apprise.instantiate("amqp://localhost/?ver=1&to=/queues/a")
    assert obj.notify(body="Body") is True
    assert connect.call_count == 1
    assert publish.call_args.args[0] == "/queues/a"
    assert close.call_count == 1

    # The 0.9.1 adapter was never touched
    assert amqp_stub[AMQPVersion.V091][0].call_count == 0


def test_plugin_amqp_connect_failure(amqp_stub):
    """NotifyAMQP() fails without publishing when it cannot connect."""
    connect, publish, _ = amqp_stub[AMQPVersion.V091]
    connect.side_effect = AMQPError("refused")

    obj = Apprise.instantiate("amqp://localhost/q1/q2")
    assert obj.notify(body="Body") is False
    assert publish.call_count == 0


def test_plugin_amqp_publish_failure(amqp_stub):
    """NotifyAMQP() keeps going after one target fails."""
    _, publish, close = amqp_stub[AMQPVersion.V091]

    def refuse(target, message):
        # Only q1 is refused by the broker
        if target == "q1":
            raise AMQPError("unroutable")

    publish.side_effect = refuse

    obj = Apprise.instantiate("amqp://localhost/q1/q2")
    assert obj.notify(body="Body") is False

    # The second target was still tried, and the connection closed
    assert [c.args[0] for c in publish.call_args_list] == ["q1", "q2"]
    assert close.call_count == 1

    # The same holds when publishing to an exchange only
    publish.reset_mock()
    publish.side_effect = AMQPError("no exchange")
    obj = Apprise.instantiate("amqp://localhost/?exchange=nope")
    assert obj.notify(body="Body") is False


def test_plugin_amqp_retry(amqp_stub):
    """NotifyAMQP() retries only the targets that have not succeeded."""
    connect, publish, _ = amqp_stub[AMQPVersion.V091]

    def refuse(target, message):
        # bad always fails, good always works
        if target == "bad":
            raise AMQPError("refused")

    publish.side_effect = refuse

    with mock.patch("apprise.apprise.time.sleep"):
        obj = Apprise()
        assert obj.add("amqp://localhost/good/bad?retry=2&wait=0")
        assert not obj.notify(body="Body")

    targets = [c.args[0] for c in publish.call_args_list]
    assert targets.count("good") == 1
    assert targets.count("bad") == 3

    # Once every target has its message, nothing more is sent
    obj = NotifyAMQP(host="localhost", targets="good")
    with mock.patch.object(obj, "is_delivered", return_value=True):
        connect.reset_mock()
        assert obj.send(body="Body") is True
        assert connect.call_count == 0


@requires_pika
def test_plugin_amqp_v091_connect():
    """AMQP091Adapter() connects with the right pika settings."""
    with mock.patch("pika.BlockingConnection") as mock_conn:
        # Plain, with a login
        adapter = AMQP091Adapter(
            AMQPConfig(
                host="localhost",
                port=5672,
                user="user",
                password="pass",
                connect_timeout=2.0,
                read_timeout=3.0,
            )
        )
        adapter.connect()
        assert adapter.connection is mock_conn.return_value

        params = mock_conn.call_args.args[0]
        assert params.host == "localhost"
        assert params.port == 5672
        assert params.virtual_host == "/"
        assert params.credentials.username == "user"
        assert params.credentials.password == "pass"
        assert params.connection_attempts == 1
        assert params.socket_timeout == 2.0
        assert params.stack_timeout == 5.0
        assert params.blocked_connection_timeout == 3.0
        assert params.heartbeat == 3
        assert params.ssl_options is None

        # A user without a password, and our own virtual host.  A short
        # read timeout still asks for a whole second of heartbeat.
        AMQP091Adapter(
            AMQPConfig(
                host="localhost",
                port=1,
                user="user",
                vhost="home",
                read_timeout=0.2,
            )
        ).connect()
        params = mock_conn.call_args.args[0]
        assert params.credentials.password == ""
        assert params.virtual_host == "home"
        assert params.heartbeat == 1

        # No login keeps pika's default account
        AMQP091Adapter(AMQPConfig(host="localhost", port=1)).connect()
        params = mock_conn.call_args.args[0]
        assert params.credentials.username == "guest"

        # TLS, checking the certificate
        AMQP091Adapter(
            AMQPConfig(host="example.com", port=5671, secure=True)
        ).connect()
        options = mock_conn.call_args.args[0].ssl_options
        assert options.server_hostname == "example.com"
        assert options.context.verify_mode == ssl.CERT_REQUIRED
        assert options.context.check_hostname is True

        # TLS, accepting any certificate
        AMQP091Adapter(
            AMQPConfig(
                host="example.com",
                port=5671,
                secure=True,
                verify_certificate=False,
            )
        ).connect()
        options = mock_conn.call_args.args[0].ssl_options
        assert options.context.verify_mode == ssl.CERT_NONE
        assert options.context.check_hostname is False


@requires_pika
@pytest.mark.parametrize(
    "error",
    (
        "pika.exceptions.AMQPConnectionError",
        "pika.exceptions.ProbableAuthenticationError",
        "ssl.SSLError",
        "ConnectionRefusedError",
        "ValueError",
        "TypeError",
    ),
)
def test_plugin_amqp_v091_connect_failure(error):
    """AMQP091Adapter() turns connection problems into AMQPError."""
    import pika  # noqa: F401

    exc = eval(error)
    with mock.patch("pika.BlockingConnection", side_effect=exc("boom")):
        adapter = AMQP091Adapter(AMQPConfig(host="localhost", port=5672))
        with pytest.raises(AMQPError):
            adapter.connect()

        # Nothing was left behind
        assert adapter.connection is None


@requires_pika
def test_plugin_amqp_v091_connect_empty_error():
    """AMQP091Adapter() names an exception that has no message."""
    import pika

    with mock.patch(
        "pika.BlockingConnection",
        side_effect=pika.exceptions.AMQPConnectionError(),
    ):
        adapter = AMQP091Adapter(AMQPConfig(host="localhost", port=5672))
        with pytest.raises(AMQPError, match="AMQPConnectionError"):
            adapter.connect()


@requires_pika
def test_plugin_amqp_v091_publish():
    """AMQP091Adapter() publishes with confirms and message properties."""
    import pika

    message = AMQPMessage(
        body=b"hello",
        content_type="text/plain; charset=utf-8",
        app_id="Apprise",
        timestamp=1234,
        priority=3,
        ttl=60000,
        headers={"a": "b"},
    )

    with mock.patch("pika.BlockingConnection") as mock_conn:
        connection = mock_conn.return_value
        channel = connection.channel.return_value

        adapter = AMQP091Adapter(
            AMQPConfig(
                host="localhost", port=5672, exchange="ex", mandatory=False
            )
        )
        adapter.connect()

        # The first publish opens a confirming channel
        adapter.publish("key", message)
        assert connection.channel.call_count == 1
        assert channel.confirm_delivery.call_count == 1

        kwargs = channel.basic_publish.call_args.kwargs
        assert kwargs["exchange"] == "ex"
        assert kwargs["routing_key"] == "key"
        assert kwargs["body"] == b"hello"
        assert kwargs["mandatory"] is False

        props = kwargs["properties"]
        assert props.content_type == "text/plain; charset=utf-8"
        assert props.delivery_mode == 2
        assert props.priority == 3
        assert props.expiration == "60000"
        assert props.timestamp == 1234
        assert props.app_id == "Apprise"
        assert props.headers == {"a": "b"}

        # The channel is reused while it stays open
        channel.is_open = True
        adapter.publish("key2", message)
        assert connection.channel.call_count == 1

        # ...and replaced once the broker closes it
        channel.is_open = False
        adapter.publish(
            "key3",
            AMQPMessage(
                body=b"x",
                content_type="text/plain",
                app_id="Apprise",
                timestamp=1,
                persistent=False,
            ),
        )
        assert connection.channel.call_count == 2

        props = channel.basic_publish.call_args.kwargs["properties"]
        assert props.delivery_mode == 1
        assert props.expiration is None
        assert props.priority is None

        # Refused messages become AMQPError
        for exc in (
            pika.exceptions.UnroutableError([]),
            pika.exceptions.NackError([]),
            pika.exceptions.ChannelClosedByBroker(404, "NOT_FOUND"),
            pika.exceptions.ShortStringTooLong("x"),
            pika.exceptions.StreamLostError("lost"),
            OSError("lost"),
        ):
            channel.basic_publish.side_effect = exc
            with pytest.raises(AMQPError):
                adapter.publish("key", message)

        # Opening a channel on a closed connection fails the same way
        channel.is_open = False
        connection.channel.side_effect = (
            pika.exceptions.ConnectionWrongStateError()
        )
        with pytest.raises(AMQPError):
            adapter.publish("key", message)


@requires_pika
def test_plugin_amqp_v091_close():
    """AMQP091Adapter() closes quietly whatever state it is in."""
    adapter = AMQP091Adapter(AMQPConfig(host="localhost", port=5672))

    # Never connected
    adapter.close()

    with mock.patch("pika.BlockingConnection") as mock_conn:
        connection = mock_conn.return_value

        # Open connection is closed
        connection.is_open = True
        adapter.connect()
        adapter.close()
        assert connection.close.call_count == 1
        assert adapter.connection is None
        assert adapter.channel is None

        # Already closed connection is left alone
        connection.is_open = False
        adapter.connect()
        adapter.close()
        assert connection.close.call_count == 1

        # A failing close is swallowed
        connection.is_open = True
        connection.close.side_effect = OSError("gone")
        adapter.connect()
        adapter.close()
        assert adapter.connection is None


@requires_proton
def test_plugin_amqp_v10_connect():
    """AMQP10Adapter() connects with the right proton settings."""
    with (
        mock.patch.object(v10, "BlockingConnection") as mock_conn,
        mock.patch.object(v10, "SSLDomain") as mock_ssl,
    ):
        # Plain, with a login
        adapter = AMQP10Adapter(
            AMQPConfig(
                host="localhost",
                port=5672,
                user="user",
                password="pass",
                connect_timeout=2.0,
                read_timeout=3.0,
            )
        )
        adapter.connect()
        assert adapter.connection is mock_conn.return_value
        assert adapter.connection.timeout == 3.0

        args, kwargs = mock_conn.call_args
        assert args[0] == "amqp://localhost:5672"
        assert kwargs["timeout"] == 2.0
        assert kwargs["ssl_domain"] is None
        assert kwargs["reconnect"] is False
        assert kwargs["user"] == "user"
        assert kwargs["password"] == "pass"
        assert kwargs["allowed_mechs"] == "PLAIN"
        assert "virtual_host" not in kwargs

        # No login is anonymous; IPv6 is bracketed; 0 timeouts stay small
        AMQP10Adapter(
            AMQPConfig(host="::1", port=1, connect_timeout=0, read_timeout=0)
        ).connect()
        args, kwargs = mock_conn.call_args
        assert args[0] == "amqp://[::1]:1"
        assert kwargs["allowed_mechs"] == "ANONYMOUS"
        assert "user" not in kwargs
        assert kwargs["timeout"] == 0.1
        assert mock_conn.return_value.timeout == 0.1

        # A user without a password, and a virtual host
        AMQP10Adapter(
            AMQPConfig(
                host="example.com", port=1, user="user", vhost="vhost:home"
            )
        ).connect()
        kwargs = mock_conn.call_args.kwargs
        assert kwargs["password"] == ""
        assert kwargs["virtual_host"] == "vhost:home"

        # The certificate is still checked against the real host
        assert kwargs["sni"] == "example.com"

        # Plain connections never build a TLS domain
        assert mock_ssl.call_count == 0

        # TLS, checking the certificate against a trusted CA bundle
        AMQP10Adapter(
            AMQPConfig(host="example.com", port=5671, secure=True)
        ).connect()
        args, kwargs = mock_conn.call_args
        domain = mock_ssl.return_value
        assert args[0] == "amqps://example.com:5671"
        assert kwargs["ssl_domain"] is domain
        mock_ssl.assert_called_with(mock_ssl.MODE_CLIENT)
        assert domain.set_trusted_ca_db.call_count == 1
        domain.set_peer_authentication.assert_called_with(
            mock_ssl.VERIFY_PEER_NAME
        )

        # TLS, accepting any certificate
        domain.reset_mock()
        AMQP10Adapter(
            AMQPConfig(
                host="example.com",
                port=5671,
                secure=True,
                verify_certificate=False,
            )
        ).connect()
        assert domain.set_trusted_ca_db.call_count == 0
        domain.set_peer_authentication.assert_called_with(
            mock_ssl.ANONYMOUS_PEER
        )


@requires_proton
def test_plugin_amqp_v10_connect_failure():
    """AMQP10Adapter() turns connection problems into AMQPError."""
    from proton import ConnectionException, SSLException, Timeout

    for exc in (
        ConnectionException("refused"),
        Timeout("slow"),
        SSLException("bad ca"),
        OSError("lost"),
        ValueError(),
    ):
        with mock.patch.object(v10, "BlockingConnection", side_effect=exc):
            adapter = AMQP10Adapter(AMQPConfig(host="localhost", port=5672))
            with pytest.raises(AMQPError):
                adapter.connect()

            # Nothing was left behind
            assert adapter.connection is None


@requires_proton
def test_plugin_amqp_v10_publish():
    """AMQP10Adapter() sends raw bytes with the message properties."""
    from proton.utils import LinkDetached, SendException

    message = AMQPMessage(
        body=b"hello",
        content_type="text/plain; charset=utf-8",
        app_id="Apprise",
        timestamp=1234,
        priority=7,
        ttl=60000,
        headers={"a": "b"},
    )

    with mock.patch.object(v10, "BlockingConnection") as mock_conn:
        connection = mock_conn.return_value
        sender = connection.create_sender.return_value

        adapter = AMQP10Adapter(AMQPConfig(host="localhost", port=5672))
        adapter.connect()
        adapter.publish("/queues/q", message)

        # One link per address, released afterwards
        assert connection.create_sender.call_args.args[0] == "/queues/q"
        assert sender.close.call_count == 1

        msg = sender.send.call_args.args[0]
        assert msg.body == b"hello"
        assert msg.inferred is True
        assert msg.content_type == "text/plain; charset=utf-8"
        assert msg.durable is True
        assert msg.creation_time == 1234
        assert msg.properties == {"a": "b"}
        assert msg.priority == 7
        assert msg.ttl == 60.0

        # Without a priority or expiry the protocol defaults apply
        adapter.publish(
            "/queues/q",
            AMQPMessage(
                body=b"x",
                content_type="text/plain",
                app_id="Apprise",
                timestamp=1,
                persistent=False,
            ),
        )
        msg = sender.send.call_args.args[0]
        assert msg.durable is False
        assert msg.priority == 4
        assert msg.ttl == 0

        # A refused message becomes AMQPError and the link is released
        sender.close.reset_mock()
        sender.send.side_effect = SendException(2)
        with pytest.raises(AMQPError):
            adapter.publish("/queues/q", message)

        assert sender.close.call_count == 1

        # A refused address never opens a link, and a link the broker
        # already closed is let go quietly
        connection.create_sender.side_effect = LinkDetached(mock.Mock())
        with pytest.raises(AMQPError):
            adapter.publish("/queues/nope", message)

        connection.create_sender.side_effect = None
        sender.send.side_effect = None
        sender.close.side_effect = LinkDetached(mock.Mock())
        adapter.publish("/queues/q", message)


@requires_proton
def test_plugin_amqp_v10_close():
    """AMQP10Adapter() closes within its read timeout, whatever happens."""
    from proton import Endpoint, Timeout

    adapter = AMQP10Adapter(
        AMQPConfig(host="localhost", port=5672, read_timeout=3.0)
    )

    # Never connected
    adapter.close()

    with mock.patch.object(v10, "BlockingConnection") as mock_conn:
        connection = mock_conn.return_value
        conn = connection.conn

        # A broker that says goodbye
        adapter.connect()
        adapter.close()
        assert adapter.connection is None
        assert conn.close.call_count == 1

        # We wait no longer than our read timeout for the goodbye
        cond = connection.wait.call_args.args[0]
        assert connection.wait.call_args.kwargs["timeout"] == 3.0

        # The goodbye arrives once the broker is no longer active
        conn.state = Endpoint.REMOTE_ACTIVE
        assert cond() is False
        conn.state = Endpoint.REMOTE_CLOSED
        assert cond() is True

        # The socket is shut, and proton never waits a second time
        assert conn.transport.close_tail.call_count == 1
        assert conn.transport.close_head.call_count == 1
        assert connection.timeout == 0.1
        assert connection.close.call_count == 1

        # A broker that never answers is shut down all the same
        connection.reset_mock()
        connection.wait.side_effect = Timeout("no goodbye")
        adapter.connect()
        adapter.close()
        assert conn.transport.close_tail.call_count == 1
        assert connection.close.call_count == 1

        # Nothing that fails along the way escapes
        connection.reset_mock()
        conn.close.side_effect = OSError("gone")
        conn.transport = None
        connection.close.side_effect = OSError("gone")
        adapter.connect()
        adapter.close()
        assert adapter.connection is None
