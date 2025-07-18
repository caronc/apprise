# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2025, Chris Caron <lead2gold@gmail.com>
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
import re
import ssl
import sys
from unittest.mock import ANY, Mock, call

import pytest

import apprise
from apprise.plugins.mqtt import NotifyMQTT

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)


@pytest.fixture
def mqtt_client_mock(mocker):
    """Mocks an MQTT client and response and returns the mocked client."""

    if "paho" not in sys.modules:
        raise pytest.skip("Requires that `paho-mqtt` is installed")

    # Establish mock of the `publish()` response object.
    publish_result = Mock(**{
        "rc": 0,
        "is_published.return_value": True,
    })

    # Establish mock of the `Client()` object.
    mock_client = Mock(**{
        "connect.return_value": 0,
        "reconnect.return_value": 0,
        "is_connected.return_value": True,
        "publish.return_value": publish_result,
    })
    mocker.patch("paho.mqtt.client.Client", return_value=mock_client)

    return mock_client


@pytest.mark.skipif(
    "paho" in sys.modules, reason="Requires that `paho-mqtt` is NOT installed"
)
def test_plugin_mqtt_paho_import_error():
    """Verify `NotifyMQTT` is disabled when `paho.mqtt.client` fails
    loading."""

    # without the library, the object can't be instantiated
    obj = apprise.Apprise.instantiate("mqtt://user:pass@localhost/my/topic")
    assert obj is None


def test_plugin_mqtt_default_success(mqtt_client_mock):
    """Verify `NotifyMQTT` succeeds and has appropriate default settings."""

    # Instantiate the notifier.
    obj = apprise.Apprise.instantiate(
        "mqtt://localhost:1234/my/topic", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMQTT)
    # We only loaded 1 topic
    assert len(obj) == 1
    assert obj.url().startswith("mqtt://localhost:1234/my/topic")

    # Genrate the URL Identifier
    assert isinstance(obj.url_id(), str)

    # Verify default settings.
    assert re.search(r"qos=0", obj.url())
    assert re.search(r"version=v3.1.1", obj.url())
    assert re.search(r"session=no", obj.url())
    assert re.search(r"client_id=", obj.url()) is None

    # Verify notification succeeds.
    assert obj.notify(body="test=test") is True

    # Send another notification (a new connection isn't attempted to be
    # established as one already exists)
    assert obj.notify(body="foo=bar") is True

    # Verify the right calls have been made to the MQTT client object.
    assert mqtt_client_mock.mock_calls == [
        call.max_inflight_messages_set(200),
        call.connect("localhost", port=1234, keepalive=30),
        call.loop_start(),
        call.is_connected(),
        call.publish("my/topic", payload="test=test", qos=0, retain=False),
        call.publish().is_published(),
        call.is_connected(),
        call.publish("my/topic", payload="foo=bar", qos=0, retain=False),
        call.publish().is_published(),
    ]


def test_plugin_mqtt_multiple_topics_success(mqtt_client_mock):
    """Verify submission to multiple MQTT topics."""

    # Designate multiple topic targets.
    obj = apprise.Apprise.instantiate(
        "mqtt://localhost/my/topic,my/other/topic", suppress_exceptions=False
    )

    # Verify we have loaded 2 topics
    assert len(obj) == 2

    assert isinstance(obj, NotifyMQTT)
    assert obj.url().startswith("mqtt://localhost")
    assert re.search(r"my/topic", obj.url())
    assert re.search(r"my/other/topic", obj.url())
    assert obj.notify(body="test=test") is True

    # Verify the right calls have been made to the MQTT client object.
    assert mqtt_client_mock.mock_calls == [
        call.max_inflight_messages_set(200),
        call.connect("localhost", port=1883, keepalive=30),
        call.loop_start(),
        call.is_connected(),
        call.publish("my/topic", payload="test=test", qos=0, retain=False),
        call.publish().is_published(),
        call.is_connected(),
        call.publish(
            "my/other/topic", payload="test=test", qos=0, retain=False
        ),
        call.publish().is_published(),
    ]


def test_plugin_mqtt_to_success(mqtt_client_mock):
    """Verify `NotifyMQTT` succeeds with the `to=` parameter."""

    # Leverage the `to=` argument to identify the topic.
    obj = apprise.Apprise.instantiate(
        "mqtt://localhost?to=my/topic", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMQTT)
    assert obj.url().startswith("mqtt://localhost/my/topic")

    # Verify default settings.
    assert re.search(r"qos=0", obj.url())
    assert re.search(r"version=v3.1.1", obj.url())

    # Verify notification succeeds.
    assert obj.notify(body="test=test") is True


def test_plugin_mqtt_valid_settings_success(mqtt_client_mock):
    """Verify settings as URL parameters will be accepted."""

    # Instantiate the notifier.
    obj = apprise.Apprise.instantiate(
        "mqtt://localhost/my/topic?qos=1&version=v3.1",
        suppress_exceptions=False,
    )

    assert isinstance(obj, NotifyMQTT)
    assert obj.url().startswith("mqtt://localhost")
    assert re.search(r"qos=1", obj.url())
    assert re.search(r"version=v3.1", obj.url())


def test_plugin_mqtt_invalid_settings_failure(mqtt_client_mock):
    """Verify notifier instantiation croaks on invalid settings."""

    # Test case for invalid/unsupported MQTT version.
    with pytest.raises(TypeError):
        apprise.Apprise.instantiate(
            "mqtt://localhost?version=v1.0.0.0", suppress_exceptions=False
        )

    # Test case for invalid/unsupported `qos`.
    with pytest.raises(TypeError):
        apprise.Apprise.instantiate(
            "mqtt://localhost?qos=123", suppress_exceptions=False
        )

    with pytest.raises(TypeError):
        apprise.Apprise.instantiate(
            "mqtt://localhost?qos=invalid", suppress_exceptions=False
        )


def test_plugin_mqtt_bad_url_failure(mqtt_client_mock):
    """Verify notifier is disabled when using an invalid URL."""
    obj = apprise.Apprise.instantiate("mqtt://", suppress_exceptions=False)
    assert obj is None


def test_plugin_mqtt_no_topic_failure(mqtt_client_mock):
    """Verify notification fails when no topic is given."""
    obj = apprise.Apprise.instantiate(
        "mqtt://localhost", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMQTT)
    assert obj.notify(body="test=test") is False


def test_plugin_mqtt_tls_connect_success(mqtt_client_mock):
    """Verify TLS encrypted connections work."""

    obj = apprise.Apprise.instantiate(
        "mqtts://user:pass@localhost/my/topic", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMQTT)
    assert obj.url().startswith("mqtts://user:pass@localhost/my/topic")
    assert obj.notify(body="test=test") is True

    # Verify the right calls have been made to the MQTT client object.
    assert mqtt_client_mock.mock_calls == [
        call.max_inflight_messages_set(200),
        call.username_pw_set("user", password="pass"),
        call.tls_set(
            ca_certs=ANY,
            certfile=None,
            keyfile=None,
            cert_reqs=ssl.VerifyMode.CERT_REQUIRED,
            tls_version=ssl.PROTOCOL_TLS,
            ciphers=None,
        ),
        call.tls_insecure_set(False),
        call.connect("localhost", port=8883, keepalive=30),
        call.loop_start(),
        call.is_connected(),
        call.publish("my/topic", payload="test=test", qos=0, retain=False),
        call.publish().is_published(),
    ]


def test_plugin_mqtt_tls_no_certificates_failure(mqtt_client_mock, mocker):
    """Verify TLS does not work without access to CA root certificates."""

    # Clear CA certificates.
    mocker.patch.object(NotifyMQTT, "CA_CERTIFICATE_FILE_LOCATIONS", [])

    obj = apprise.Apprise.instantiate(
        "mqtts://user:pass@localhost/my/topic", suppress_exceptions=False
    )
    assert isinstance(obj, NotifyMQTT)

    logger: Mock = mocker.spy(obj, "logger")

    # Verify notification fails w/o CA certificates.
    assert obj.notify(body="test=test") is False

    assert logger.mock_calls == [
        call.error(
            "MQTT secure communication can not be verified, "
            "CA certificates file missing"
        )
    ]


def test_plugin_mqtt_tls_no_verify_success(mqtt_client_mock):
    """Verify TLS encrypted connections work with `verify=False`."""

    # A single user (not password) + no verifying of host
    obj = apprise.Apprise.instantiate(
        "mqtts://user:pass@localhost/my/topic?verify=False",
        suppress_exceptions=False,
    )
    assert isinstance(obj, NotifyMQTT)
    assert obj.notify(body="test=test") is True

    # Verify the right calls have been made to the MQTT client object.
    # Let's only validate the single call of interest is present.
    # Everything else is identical with `test_plugin_mqtt_tls_connect_success`.
    assert call.tls_insecure_set(True) in mqtt_client_mock.mock_calls


def test_plugin_mqtt_session_client_id_success(mqtt_client_mock):
    """Verify handling `session=yes` and `client_id=` works."""

    obj = apprise.Apprise.instantiate(
        "mqtt://user@localhost/my/topic?session=yes&client_id=apprise",
        suppress_exceptions=False,
    )

    assert isinstance(obj, NotifyMQTT)
    assert obj.url().startswith("mqtt://user@localhost")
    assert re.search(r"my/topic", obj.url())
    assert re.search(r"client_id=apprise", obj.url())
    assert re.search(r"session=yes", obj.url())
    assert re.search(r"retain=no", obj.url())
    assert obj.notify(body="test=test") is True


def test_plugin_mqtt_retain(mqtt_client_mock):
    """Verify handling of Retain Message Flag."""

    obj = apprise.Apprise.instantiate(
        "mqtt://user@localhost/my/topic?retain=yes", suppress_exceptions=False
    )

    assert isinstance(obj, NotifyMQTT)
    assert obj.url().startswith("mqtt://user@localhost")
    assert re.search(r"my/topic", obj.url())
    assert re.search(r"session=no", obj.url())
    assert re.search(r"retain=yes", obj.url())
    assert obj.notify(body="test=test") is True


def test_plugin_mqtt_connect_failure(mqtt_client_mock):
    """Verify `NotifyMQTT` fails when MQTT `connect()` fails."""

    # Emulate a situation where the `connect()` method fails.
    mqtt_client_mock.connect.return_value = 2

    obj = apprise.Apprise.instantiate(
        "mqtt://localhost/my/topic", suppress_exceptions=False
    )

    # Verify notification fails.
    assert obj.notify(body="test=test") is False


def test_plugin_mqtt_reconnect_failure(mqtt_client_mock):
    """Verify `NotifyMQTT` fails when MQTT `reconnect()` fails."""

    # Emulate a situation where MQTT reconnect fails.
    mqtt_client_mock.reconnect.return_value = 2
    mqtt_client_mock.is_connected.return_value = False

    obj = apprise.Apprise.instantiate(
        "mqtt://localhost/my/topic", suppress_exceptions=False
    )

    # Verify notification fails.
    assert obj.notify(body="test=test") is False


def test_plugin_mqtt_publish_failure(mqtt_client_mock):
    """Verify `NotifyMQTT` fails when MQTT `publish()` fails."""

    # Emulate a situation where the `publish()` method fails.
    mqtt_response = mqtt_client_mock.publish.return_value
    mqtt_response.rc = 2

    obj = apprise.Apprise.instantiate(
        "mqtt://localhost/my/topic", suppress_exceptions=False
    )

    # Verify notification fails.
    assert obj.notify(body="test=test") is False


def test_plugin_mqtt_exception_failure(mqtt_client_mock):
    """Verify `NotifyMQTT` fails when an exception happens."""

    obj = apprise.Apprise.instantiate(
        "mqtt://localhost/my/topic", suppress_exceptions=False
    )

    # Emulate a situation where `connect()` raises an exception.
    mqtt_client_mock.connect.return_value = None

    # Verify notification fails.
    for side_effect in (ValueError, ConnectionError, ssl.CertificateError):
        mqtt_client_mock.connect.side_effect = side_effect
        assert obj.notify(body="test=test") is False


def test_plugin_mqtt_not_published_failure(mqtt_client_mock, mocker):
    """Verify `NotifyMQTT` fails there if the message has not been
    published."""

    # Speed up testing by making `NotifyMQTT` not block anywhere.
    mocker.patch.object(NotifyMQTT, "socket_read_timeout", 0.00025)
    mocker.patch.object(NotifyMQTT, "mqtt_block_time_sec", 0)

    # Emulate a situation where `is_published()` returns `False`.
    mqtt_response = mqtt_client_mock.publish.return_value
    mqtt_response.is_published.return_value = False

    obj = apprise.Apprise.instantiate(
        "mqtt://localhost/my/topic", suppress_exceptions=False
    )

    # Verify notification fails.
    assert obj.notify(body="test=test") is False


def test_plugin_mqtt_not_published_recovery_success(mqtt_client_mock):
    """Verify `NotifyMQTT` success after recovering from
    is_published==False."""

    # Emulate a situation where `is_published()` returns `False`.
    mqtt_response = mqtt_client_mock.publish.return_value
    mqtt_response.is_published.return_value = None
    mqtt_response.is_published.side_effect = (False, True)

    obj = apprise.Apprise.instantiate(
        "mqtt://localhost/my/topic", suppress_exceptions=False
    )

    # Verify notification fails.
    assert obj.notify(body="test=test") is True
