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

import json

# Disable logging for a cleaner testing output
import logging
import os
import sys
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import asset, exception, url
from apprise.common import PersistentStoreMode
from apprise.plugins.vapid import NotifyVapid
from apprise.plugins.vapid.subscription import (
    WebPushSubscription,
    WebPushSubscriptionManager,
)
from apprise.utils.pem import ApprisePEMController

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# a test UUID we can use
SUBSCRIBER = "user@example.com"

PLUGIN_ID = "vapid"

# Our Testing URLs
apprise_url_tests = (
    (
        "vapid://",
        {
            "instance": TypeError,
        },
    ),
    (
        "vapid://:@/",
        {
            "instance": TypeError,
        },
    ),
    (
        "vapid://invalid-subscriber",
        {
            # An invalid Subscriber
            "instance": TypeError,
        },
    ),
    (
        "vapid://user@example.com",
        {
            # bare bone requirements met, but we don't have our subscription
            # file or our private key (pem)
            "instance": NotifyVapid,
            # We'll fail to respond because we would not have found any
            # configuration to load
            "notify_response": False,
        },
    ),
    (
        "vapid://user@example.com?keyfile=invalid&subfile=invalid",
        {
            # Test passing keyfile and subfile on our path (even if invalid)
            "instance": NotifyVapid,
            # We'll fail to respond because we would not have found any
            # configuration to load
            "notify_response": False,
        },
    ),
    (
        "vapid://user@example.com/newuser@example.com",
        {
            # we don't have our subscription file or private key
            "instance": NotifyVapid,
            "notify_response": False,
        },
    ),
    (
        "vapid://user@example.ca/newuser@example.ca",
        {
            "instance": NotifyVapid,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        "vapid://user@example.uk/newuser@example.uk",
        {
            "instance": NotifyVapid,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "vapid://user@example.au/newuser@example.au",
        {
            "instance": NotifyVapid,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


@pytest.fixture
def patch_persistent_store_namespace(tmpdir):
    """Force an easy to test environment."""
    with (
        mock.patch.object(url.URLBase, "url_id", return_value=PLUGIN_ID),
        mock.patch.object(
            asset.AppriseAsset, "storage_mode", PersistentStoreMode.AUTO
        ),
        mock.patch.object(asset.AppriseAsset, "storage_path", str(tmpdir)),
    ):

        tmp_dir = tmpdir.mkdir(PLUGIN_ID)
        # Return the directory name
        yield str(tmp_dir)


@pytest.fixture
def subscription_reference():
    return {
        "user@example.com": {
            "endpoint": "https://fcm.googleapis.com/fcm/send/default",
            "keys": {
                "p256dh": (
                    "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                    "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
                ),
                "auth": "k9Xzm43nBGo=",
            },
        },
        "user1": {
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": (
                    "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                    "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
                ),
                "auth": "k9Xzm43nBGo=",
            },
        },
        "user2": {
            "endpoint": "https://fcm.googleapis.com/fcm/send/def456",
            "keys": {
                "p256dh": (
                    "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                    "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
                ),
                "auth": "k9Xzm43nBGo=",
            },
        },
    }


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_urls():
    """
    NotifyVapid() Apprise URLs - No Config

    """

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_urls_with_required_assets(
    patch_persistent_store_namespace, subscription_reference
):
    """NotifyVapid() Apprise URLs With Config."""

    # Determine our store
    pc = ApprisePEMController(path=patch_persistent_store_namespace)
    assert pc.keygen() is True

    # Write our subscriptions file to disk
    subscription_file = os.path.join(
        patch_persistent_store_namespace, NotifyVapid.vapid_subscription_file
    )

    with open(subscription_file, "w") as f:
        f.write(json.dumps(subscription_reference))

    tests = (
        (
            "vapid://user@example.com",
            {
                # user@example.com loaded (also used as subscriber id)
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://user@example.com/newuser@example.com",
            {
                # no newuser@example.com key entry
                "instance": NotifyVapid,
                "notify_response": False,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2",
            {
                # We'll succesfully notify 2 users
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://user1?to=user2&from=user@example.com",
            {
                # We'll succesfully notify 2 users
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://?to=user2&from=user@example.com",
            {
                # No host provided
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://user@example.com?to=user2&from=user@example.com",
            {
                # We'll succesfully notify 2 users
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2&ttl=15",
            {
                # test ttl
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2&ttl=",
            {
                # test ttl
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2&ttl=invalid",
            {
                # test ttl
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2&ttl=-4000",
            {
                # bad ttl
                "instance": TypeError,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2&mode=edge",
            {
                # test mode
                "instance": NotifyVapid,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2&mode=",
            {
                # test mode
                "instance": TypeError,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2&mode=invalid",
            {
                # test mode more
                "instance": TypeError,
            },
        ),
        (
            "vapid://user@example.com/user1",
            {
                "instance": NotifyVapid,
                # force a failure
                "response": False,
                "requests_response_code": requests.codes.internal_server_error,
            },
        ),
        (
            "vapid://user@example.com/user1",
            {
                "instance": NotifyVapid,
                # throw a bizzare code forcing us to fail to look it up
                "response": False,
                "requests_response_code": 999,
            },
        ),
        (
            "vapid://user@example.com/user1",
            {
                "instance": NotifyVapid,
                # Throws a series of connection and transfer exceptions
                # when this flag is set and tests that we gracfully handle them
                "test_requests_exceptions": True,
            },
        ),
    )

    AppriseURLTester(tests=tests).run_all()


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_subscriptions(tmpdir):
    """NotifyVapid() Subscriptions."""

    # Temporary directory
    tmpdir0 = tmpdir.mkdir("tmp00")

    with pytest.raises(exception.AppriseInvalidData):
        # Integer not supported
        WebPushSubscription(42)

    with pytest.raises(exception.AppriseInvalidData):
        # Not the correct format
        WebPushSubscription("bad-content")

    with pytest.raises(exception.AppriseInvalidData):
        # Invalid JSON
        WebPushSubscription("{")

    with pytest.raises(exception.AppriseInvalidData):
        # Empty Dictionary
        WebPushSubscription({})

    with pytest.raises(exception.AppriseInvalidData):
        WebPushSubscription({
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR=",
                "auth": 42,
            },
        })

    with pytest.raises(exception.AppriseInvalidData):
        WebPushSubscription({
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": 42,
                "auth": "k9Xzm43nBGo=",
            },
        })

    with pytest.raises(exception.AppriseInvalidData):
        WebPushSubscription({
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        })

    with pytest.raises(exception.AppriseInvalidData):
        WebPushSubscription({
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {},
        })

    with pytest.raises(exception.AppriseInvalidData):
        # Invalid p256dh public key provided
        wps = WebPushSubscription({
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR=",
                "auth": "k9Xzm43nBGo=",
            },
        })

    # An empty object
    wps = WebPushSubscription()
    assert bool(wps) is False
    assert isinstance(wps.json(), str)
    assert json.loads(wps.json())
    assert str(wps) == ""
    assert wps.auth is None
    assert wps.endpoint is None
    assert wps.p256dh is None
    assert wps.public_key is None
    # We can't write anything as there is nothing loaded
    assert wps.write(os.path.join(str(tmpdir0), "subscriptions.json")) is False

    # A valid key
    wps = WebPushSubscription({
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        "keys": {
            "p256dh": (
                "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
            ),
            "auth": "k9Xzm43nBGo=",
        },
    })

    assert bool(wps) is True
    assert isinstance(wps.json(), str)
    assert json.loads(wps.json())
    assert str(wps) == "abc123"
    assert wps.auth == "k9Xzm43nBGo="
    assert wps.endpoint == "https://fcm.googleapis.com/fcm/send/abc123"
    assert (
        wps.p256dh
        == "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
        "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
    )
    assert wps.public_key is not None

    # Currently no files here
    assert os.listdir(str(tmpdir0)) == []

    # Bad content
    assert wps.write(object) is False
    assert wps.write(None) is False
    # Can't write to a name already taken by as a directory
    assert wps.write(str(tmpdir0)) is False
    # Can't write to a name already taken by as a directory
    assert wps.write(os.path.join(str(tmpdir0), "subscriptions.json")) is True
    assert os.listdir(str(tmpdir0)) == ["subscriptions.json"]


@pytest.mark.skipif(
    "cryptography" in sys.modules,
    reason="Requires that cryptography NOT be installed",
)
def test_plugin_vapid_subscriptions_without_c():
    """NotifyVapid() Subscriptions (no Cryptography)"""
    with pytest.raises(exception.AppriseInvalidData):
        # A valid key that can't be loaded because crytography is missing
        WebPushSubscription({
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": (
                    "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                    "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
                ),
                "auth": "k9Xzm43nBGo=",
            },
        })


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_subscription_manager(tmpdir):
    """NotifyVapid() Subscription Manager."""

    # Temporary directory
    tmpdir0 = tmpdir.mkdir("tmp00")

    with pytest.raises(exception.AppriseInvalidData):
        # An invalid object
        smgr = WebPushSubscriptionManager()
        smgr["abc"] = "invalid"

    with pytest.raises(exception.AppriseInvalidData):
        # An invalid object
        smgr = WebPushSubscriptionManager()
        smgr += "invalid"

    smgr = WebPushSubscriptionManager()

    assert bool(smgr) is False
    assert len(smgr) == 0

    sub = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        "keys": {
            "p256dh": (
                "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
            ),
            "auth": "k9Xzm43nBGo=",
        },
    }

    assert smgr.add(sub) is True
    assert bool(smgr) is True
    assert len(smgr) == 1

    # Same sub (overwrites same slot)
    smgr += sub
    assert bool(smgr) is True
    assert len(smgr) == 1

    # This makes a copy
    smgr["abc"] = smgr["abc123"]
    assert bool(smgr) is True
    assert len(smgr) == 2

    assert isinstance(smgr["abc123"], WebPushSubscription)

    # Currently no files here
    assert os.listdir(str(tmpdir0)) == []

    # Write our content
    assert smgr.write(os.path.join(str(tmpdir0), "subscriptions.json")) is True

    assert os.listdir(str(tmpdir0)) == ["subscriptions.json"]

    # Reset our object
    smgr.clear()
    assert bool(smgr) is False
    assert len(smgr) == 0

    # Load our content back
    assert smgr.load(os.path.join(str(tmpdir0), "subscriptions.json")) is True
    assert bool(smgr) is True
    assert len(smgr) == 2

    # Write over our file using the standard Subscription format
    assert (
        smgr["abc123"].write(os.path.join(str(tmpdir0), "subscriptions.json"))
        is True
    )

    # We can still open this type as well
    assert smgr.load(os.path.join(str(tmpdir0), "subscriptions.json")) is True
    assert bool(smgr) is True
    assert len(smgr) == 1

    smgr.clear()
    bad_entry = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        "keys": {
            "p256dh": "invalid",
            "auth": "garbage",
        },
    }

    subscriptions = os.path.join(str(tmpdir0), "subscriptions.json")
    with open(subscriptions, "w", encoding="utf-8") as f:
        # A bad JSON file
        f.write("{")
    assert smgr.load(subscriptions) is False

    with open(subscriptions, "w", encoding="utf-8") as f:
        # not expected dictionary
        f.write("null")
    assert smgr.load(subscriptions) is False

    subscriptions = os.path.join(str(tmpdir0), "subscriptions.json")
    with open(subscriptions, "w", encoding="utf-8") as f:
        json.dump(bad_entry, f)
    assert smgr.load(subscriptions) is False

    # Create bad data
    bad_data = {
        "bad1": bad_entry,
        "bad2": bad_entry,
        "bad3": bad_entry,
        "bad4": bad_entry,
    }
    subscriptions = os.path.join(str(tmpdir0), "subscriptions.json")
    with open(subscriptions, "w", encoding="utf-8") as f:
        json.dump(bad_data, f)
    assert smgr.load(subscriptions) is False
    assert smgr.load("invalid-file") is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_initializations(mock_post, tmpdir):
    """NotifyVapid() Initializations."""

    # Assign our mock object our return value
    okay_response = requests.Request()
    okay_response.status_code = requests.codes.ok
    okay_response.content = ""
    mock_post.return_value = okay_response

    # Temporary directory
    tmpdir0 = tmpdir.mkdir("tmp00")

    # Write our subfile
    smgr = WebPushSubscriptionManager()
    sub = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        "keys": {
            "p256dh": (
                "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
            ),
            "auth": "k9Xzm43nBGo=",
        },
    }
    subfile = os.path.join(str(tmpdir0), "subscriptions.json")
    assert smgr.add(sub) is True
    assert smgr.add(smgr["abc123"]) is True
    assert os.listdir(str(tmpdir0)) == []

    with mock.patch("json.dump", side_effect=OSError):
        # We will fial to write
        assert smgr.write(subfile) is False

    assert smgr.write(subfile) is True
    assert os.listdir(str(tmpdir0)) == ["subscriptions.json"]
    assert isinstance(smgr.json(), str)

    _asset = asset.AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
        # Auto-gen our private/public key pair
        pem_autogen=True,
    )

    # Auto-Key Generation
    obj = NotifyVapid(
        "user@example.ca",
        targets=[
            "abc123",
        ],
        subfile=subfile,
        asset=_asset,
    )
    assert isinstance(obj, NotifyVapid)
    # Our subscription directory + our
    # persistent store where our keys were generated
    assert len(os.listdir(str(tmpdir0))) == 2

    # Second call re-references keys previously generated
    obj = NotifyVapid(
        "user@example.ca",
        targets=[
            "abc123",
        ],
        subfile=subfile,
        asset=_asset,
    )
    assert isinstance(obj, NotifyVapid)
    assert isinstance(obj.url(), str)
    assert obj.send("test") is True
    # A second message makes no difference; what is loaded into memory is used
    assert obj.send("test") is True

    obj = NotifyVapid(
        "user@example.ca",
        targets=[
            "abc123",
        ],
        subfile="/a/bad/path",
        asset=_asset,
    )
    assert isinstance(obj, NotifyVapid)
    assert isinstance(obj.url(), str)
    assert obj.send("test") is False
    # A second message makes no difference; what is loaded into memory is used
    assert obj.send("test") is False

    # Detect our keyfile
    cache_dir = next(
        x
        for x in os.listdir(str(tmpdir0))
        if not x.endswith("subscriptions.json")
    )

    # Test fixed assignment to our keyfile
    keyfile = os.path.join(str(tmpdir0), cache_dir, "private_key.pem")
    assert os.path.exists(keyfile)
    obj = NotifyVapid(
        "user@example.ca",
        targets=[
            "abc123",
        ],
        keyfile=keyfile,
        subfile=subfile,
        asset=_asset,
    )
    assert isinstance(obj, NotifyVapid)
    assert isinstance(obj.url(), str)
    assert obj.send("test") is True
    # A second message makes no difference; what is loaded into memory is used
    assert obj.send("test") is True

    # Invalid Keyfile
    obj = NotifyVapid(
        "user@example.ca",
        targets=[
            "abc123",
        ],
        keyfile=subfile,
        subfile=subfile,
        asset=_asset,
    )
    assert isinstance(obj, NotifyVapid)
    assert isinstance(obj.url(), str)
    assert obj.send("test") is False
    # A second message makes no difference; what is loaded into memory is used
    assert obj.send("test") is False

    # AutoGen Temporary directory
    tmpdir1 = tmpdir.mkdir("tmp01")
    _asset2 = asset.AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir1),
        # Auto-gen our private/public key pair
        pem_autogen=True,
    )

    assert os.listdir(str(tmpdir1)) == []
    obj = NotifyVapid(
        "user@example.ca",
        targets=[
            "abc123",
        ],
        keyfile=keyfile,
        asset=_asset2,
    )
    assert isinstance(obj, NotifyVapid)
    assert isinstance(obj.url(), str)
    # We have a temporary subscription file we can use
    assert os.listdir(str(tmpdir1)) == ["00088ad3"]
    # We will have a dud configuration file, but at least it's something
    # to help the user with
    assert obj.send("test") is False
    # Second instance fails as well
    assert obj.send("test") is False

    # AutoGen Temporary directory
    tmpdir2 = tmpdir.mkdir("tmp02")
    _asset3 = asset.AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir2),
        # Auto-gen our private/public key pair
        pem_autogen=True,
    )

    # Test invalid keyfile
    assert os.path.exists(keyfile)
    obj = NotifyVapid(
        "user@example.ca",
        targets=[
            "abc123",
        ],
        keyfile="invalid-file",
        subfile=subfile,
        asset=_asset3,
    )
    assert isinstance(obj, NotifyVapid)
    assert isinstance(obj.url(), str)
    assert obj.send("test") is False
    # A second message makes no difference; what is loaded into memory is used
    assert obj.send("test") is False


@pytest.mark.skipif(
    "cryptography" in sys.modules,
    reason="Requires that cryptography NOT be installed",
)
def test_plugin_vapid_initializations_without_c(tmpdir):
    """NotifyVapid() Initializations without cryptography."""
    # Temporary directory
    tmpdir0 = tmpdir.mkdir("tmp00")

    # Write our subfile
    smgr = WebPushSubscriptionManager()
    sub = {
        "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
        "keys": {
            "p256dh": (
                "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
            ),
            "auth": "k9Xzm43nBGo=",
        },
    }
    subfile = os.path.join(str(tmpdir0), "subscriptions.json")
    assert smgr.add(sub) is False
    _asset = asset.AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
        # Auto-gen our private/public key pair
        pem_autogen=True,
    )

    # Auto-Key Generation
    obj = NotifyVapid(
        "user@example.ca",
        targets=[
            "abc123",
        ],
        subfile=subfile,
        asset=_asset,
    )
    assert isinstance(obj, NotifyVapid)
