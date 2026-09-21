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

import base64
import json

# Disable logging for a cleaner testing output
import logging
import os
import stat
import sys
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, asset, exception, url
from apprise.common import PersistentStoreMode
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.vapid import VAPID_API_LOOKUP, NotifyVapid
from apprise.plugins.vapid.subscription import (
    WebPushSubscription,
    WebPushSubscriptionManager,
    webpush_origin,
)
from apprise.utils.cwe312 import cwe312_loggable
from apprise.utils.pem import ApprisePEMController

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")

# a test UUID we can use
SUBSCRIBER = "user@example.com"

PLUGIN_ID = "vapid"

# Windows has no POSIX file modes, so tests that check them are skipped
# there.
IS_WINDOWS = sys.platform == "win32"

# Root ignores file permissions entirely, so a read-only file still tests
# as writable. RPM builds run their test suite as root.
IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0

# Our Testing URLs
apprise_url_tests = (
    (
        "vapid://",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "vapid://:@/",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        "vapid://invalid-subscriber",
        {
            # An invalid Subscriber
            "instance": AppriseImproperlyConfigured,
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
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "vapid://user@example.au/newuser@example.au",
        {
            "instance": NotifyVapid,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
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
                "instance": AppriseImproperlyConfigured,
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
                "instance": AppriseImproperlyConfigured,
            },
        ),
        (
            "vapid://user@example.com/user1?to=user2&mode=invalid",
            {
                # test mode more
                "instance": AppriseImproperlyConfigured,
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
                # throw a bizarre code forcing us to fail to look it up
                "response": False,
                "requests_response_code": 999,
            },
        ),
        (
            "vapid://user@example.com/user1",
            {
                "instance": NotifyVapid,
                # Throws a series of connection and transfer exceptions
                # when this flag is set and tests that we gracefully handle
                # them
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
        WebPushSubscription(
            {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                "keys": {
                    "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR=",
                    "auth": 42,
                },
            }
        )

    with pytest.raises(exception.AppriseInvalidData):
        WebPushSubscription(
            {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                "keys": {
                    "p256dh": 42,
                    "auth": "k9Xzm43nBGo=",
                },
            }
        )

    with pytest.raises(exception.AppriseInvalidData):
        WebPushSubscription(
            {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            }
        )

    with pytest.raises(exception.AppriseInvalidData):
        WebPushSubscription(
            {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                "keys": {},
            }
        )

    with pytest.raises(exception.AppriseInvalidData):
        # Invalid p256dh public key provided
        wps = WebPushSubscription(
            {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                "keys": {
                    "p256dh": "BNcW4oA7zq5H9TKIrA3XfKclN2fX9P_7NR=",
                    "auth": "k9Xzm43nBGo=",
                },
            }
        )

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
    wps = WebPushSubscription(
        {
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": (
                    "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                    "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
                ),
                "auth": "k9Xzm43nBGo=",
            },
        }
    )

    assert bool(wps) is True
    assert isinstance(wps.json(), str)
    assert json.loads(wps.json())
    assert str(wps) == "abc123"
    assert wps.auth == "k9Xzm43nBGo="
    assert wps.endpoint == "https://fcm.googleapis.com/fcm/send/abc123"
    assert (
        wps.p256dh == "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
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
        WebPushSubscription(
            {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
                "keys": {
                    "p256dh": (
                        "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
                        "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
                    ),
                    "auth": "k9Xzm43nBGo=",
                },
            }
        )


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

    asset_ = asset.AppriseAsset(
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
        asset=asset_,
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
        asset=asset_,
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
        asset=asset_,
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
        asset=asset_,
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
        asset=asset_,
    )
    assert isinstance(obj, NotifyVapid)
    assert isinstance(obj.url(), str)
    assert obj.send("test") is False
    # A second message makes no difference; what is loaded into memory is used
    assert obj.send("test") is False

    # AutoGen Temporary directory
    tmpdir1 = tmpdir.mkdir("tmp01")
    asset2 = asset.AppriseAsset(
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
        asset=asset2,
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
    asset3 = asset.AppriseAsset(
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
        asset=asset3,
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
    asset_ = asset.AppriseAsset(
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
        asset=asset_,
    )
    assert isinstance(obj, NotifyVapid)


def _jwt_audience(authorization):
    """Returns the VAPID JWT audience from an Authorization header."""

    token = authorization.split("t=", 1)[1].split(",", 1)[0]
    payload = token.split(".")[1]
    # JWT segments use base64url without padding.
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["aud"]


# Valid P-256 public key shared by the test subscriptions.
TEST_P256DH = (
    "BI2RNIK2PkeCVoEfgVQNjievBi4gWvZxMiuCpOx6K6qCO"
    "5caru5QCPuc-nEaLplbbFkHxTrR9YzE8ZkTjie5Fq0"
)

# Valid authentication secret shared by the test subscriptions.
TEST_AUTH = "k9Xzm43nBGo="


def _mk_resp(code=requests.codes.ok):
    """Builds a mocked push service response carrying the code given."""

    response = requests.Request()
    response.status_code = code
    response.content = ""
    return response


def _subscription(endpoint):
    """Builds a single subscription dictionary for the endpoint given."""

    return {
        "endpoint": endpoint,
        "keys": {"p256dh": TEST_P256DH, "auth": TEST_AUTH},
    }


def _write_subscriptions(path, endpoints):
    """Builds a subscriptions.json containing the endpoints provided.

    ``endpoints`` accepts:
    - a list of endpoints, each named after its own last path segment
    - a dictionary of name to endpoint pairs
    """

    if isinstance(endpoints, dict):
        with open(path, "w") as f:
            json.dump(
                {
                    name: _subscription(endpoint)
                    for name, endpoint in endpoints.items()
                },
                f,
            )
        return

    smgr = WebPushSubscriptionManager()
    for endpoint in endpoints:
        assert smgr.add(_subscription(endpoint)) is True

    assert smgr.write(path) is True


def _mk_notifier(tmpdir, endpoints, targets, name="vapid"):
    """Builds a NotifyVapid() backed by a subscriptions file on disk.

    Returns the notifier along with the path of the file that was written.
    """

    tmpdir0 = tmpdir.mkdir(name)
    subfile = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(subfile, endpoints)

    obj = NotifyVapid(
        "user@example.ca",
        targets=targets,
        subfile=subfile,
        asset=asset.AppriseAsset(
            storage_mode=PersistentStoreMode.FLUSH,
            storage_path=str(tmpdir0),
            pem_autogen=True,
        ),
    )
    return obj, subfile


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_subscription_endpoint(mock_post, tmpdir):
    """NotifyVapid() delivers to the endpoint of the subscription itself."""

    mock_post.return_value = _mk_resp()

    endpoint = "https://fcm.googleapis.com/fcm/send/abc123"
    obj, _ = _mk_notifier(tmpdir, [endpoint], ["abc123"], name="tmp10")
    assert obj.send("test") is True

    # Use the browser-issued endpoint instead of the mode's base URL.
    assert mock_post.call_args[0][0] == endpoint
    assert mock_post.call_args[0][0] != VAPID_API_LOOKUP[obj.mode]

    # Use the endpoint's origin as the JWT audience.
    headers = mock_post.call_args[1]["headers"]
    assert _jwt_audience(headers["Authorization"]) == (
        "https://fcm.googleapis.com"
    )


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_multiple_endpoints(mock_post, tmpdir):
    """NotifyVapid() handles subscriptions hosted by different services."""

    mock_post.return_value = _mk_resp()

    endpoints = {
        "abc123": "https://fcm.googleapis.com/fcm/send/abc123",
        "xyz789": "https://web.push.apple.com/xyz789",
    }
    obj, _ = _mk_notifier(
        tmpdir, list(endpoints.values()), list(endpoints), name="tmp11"
    )
    assert obj.send("test") is True
    assert mock_post.call_count == len(endpoints)

    # Give each service its own endpoint and JWT audience.
    delivered = {}
    for call in mock_post.call_args_list:
        url = call[0][0]
        delivered[url] = _jwt_audience(call[1]["headers"]["Authorization"])

    assert set(delivered) == set(endpoints.values())
    assert delivered["https://fcm.googleapis.com/fcm/send/abc123"] == (
        "https://fcm.googleapis.com"
    )
    assert delivered["https://web.push.apple.com/xyz789"] == (
        "https://web.push.apple.com"
    )


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@pytest.mark.parametrize(
    "status_code",
    (
        requests.codes.ok,
        requests.codes.created,
        requests.codes.accepted,
        requests.codes.no_content,
    ),
)
@mock.patch("requests.post")
def test_plugin_vapid_success_codes(mock_post, tmpdir, status_code):
    """NotifyVapid() accepts its supported success responses."""

    mock_post.return_value = _mk_resp(status_code)

    obj, _ = _mk_notifier(
        tmpdir,
        ["https://fcm.googleapis.com/fcm/send/abc123"],
        ["abc123"],
        name=f"ok{status_code}",
    )

    # Supported services may acknowledge queued messages with 201 or 202.
    assert obj.send("test") is True


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_prunes_expired_subscriptions(mock_post, tmpdir):
    """A 404 or a 410 from the push service removes that subscription."""

    def respond(url, *args, **kwargs):
        # Endpoint names select the expired response returned by this mock.
        return _mk_resp(
            requests.codes.gone
            if url.endswith("GONE")
            else (
                requests.codes.not_found
                if url.endswith("MISSING")
                else requests.codes.created
            )
        )

    mock_post.side_effect = respond

    obj, subfile = _mk_notifier(
        tmpdir,
        {
            "live": "https://web.push.apple.com/LIVE",
            "gone": "https://web.push.apple.com/GONE",
            "missing": "https://web.push.apple.com/MISSING",
        },
        ["live", "gone", "missing"],
        name="prune",
    )

    # An expired endpoint is reported honestly as a failure, even though
    # another target was accepted.
    assert obj.send("test") is False

    # Remove only the expired subscriptions from disk.
    with open(subfile) as f:
        remaining = json.load(f)

    assert set(remaining) == {"live"}
    assert "gone" not in obj.subscriptions
    assert "missing" not in obj.subscriptions


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_prune_write_failure(mock_post, tmpdir):
    """A subscription file that cannot be updated does not break sending."""

    mock_post.return_value = _mk_resp(requests.codes.gone)

    obj, subfile = _mk_notifier(
        tmpdir,
        ["https://web.push.apple.com/DEAD"],
        ["dead"],
        name="writefail",
    )

    with mock.patch.object(
        WebPushSubscriptionManager, "prune", return_value=False
    ):
        assert obj.send("test") is False

    # Remove the expired subscription from memory despite the write failure.
    assert "dead" not in obj.subscriptions

    # The unchanged file still contains the expired subscription.
    with open(subfile) as f:
        assert "dead" in json.load(f)


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_prune_without_subfile(mock_post, tmpdir):
    """An expired subscription is dropped even with nothing to write to."""

    mock_post.return_value = _mk_resp(requests.codes.gone)

    obj, subfile = _mk_notifier(
        tmpdir,
        ["https://web.push.apple.com/DEAD"],
        ["dead"],
        name="nosubfile",
    )

    # Load subscriptions, then detach the file to prevent persistence.
    assert obj.subscriptions.load(subfile) is True
    obj.subscriptions_loaded = True
    obj.subfile = None

    assert obj.send("test") is False

    # The expired subscription is still dropped from memory.
    assert "dead" not in obj.subscriptions


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_subscription_remove():
    """WebPushSubscriptionManager() reports whether it removed anything."""

    smgr = WebPushSubscriptionManager()

    # Nothing can be removed from an empty manager.
    assert smgr.remove("missing") is False

    assert smgr.add(_subscription("https://web.push.apple.com/abc123")) is True
    assert len(smgr) == 1

    # Match subscription names without regard to case.
    assert smgr.remove("ABC123") is True
    assert len(smgr) == 0
    assert smgr.remove("abc123") is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@pytest.mark.parametrize(
    ("endpoint", "origin"),
    (
        # A standard endpoint keeps its origin.
        (
            "https://fcm.googleapis.com/fcm/send/abc123",
            "https://fcm.googleapis.com",
        ),
        # Lowercase the scheme and host, and omit port 443.
        (
            "HTTPS://FCM.GoogleAPIs.COM:443/fcm/send/abc123",
            "https://fcm.googleapis.com",
        ),
        # Ignore surrounding whitespace.
        (
            "  https://fcm.googleapis.com/fcm/send/abc123  ",
            "https://fcm.googleapis.com",
        ),
        # Keep a non-default port in the origin.
        (
            "https://push.example.com:8443/wpush/v1/abc123",
            "https://push.example.com:8443",
        ),
        # Keep brackets around an IPv6 host.
        ("https://[2001:db8::1]/wpush/v1/abc", "https://[2001:db8::1]"),
        (
            "https://[2001:db8::1]:8443/wpush/v1/abc",
            "https://[2001:db8::1]:8443",
        ),
        # Allow a self-hosted service on a private address.
        ("https://192.168.0.10:8443/push/abc", "https://192.168.0.10:8443"),
    ),
)
def test_plugin_vapid_endpoint_origins(endpoint, origin):
    """A valid endpoint is accepted and reduced to its origin."""

    assert webpush_origin(endpoint) == origin

    sub = WebPushSubscription(_subscription(endpoint))
    assert sub.origin == origin
    assert sub.endpoint == endpoint.strip()


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@pytest.mark.parametrize(
    "endpoint",
    (
        # Web Push requires HTTPS.
        "http://fcm.googleapis.com/fcm/send/abc123",
        "ftp://fcm.googleapis.com/fcm/send/abc123",
        "fcm.googleapis.com/fcm/send/abc123",
        # Reject embedded credentials, even empty ones.
        "https://user@fcm.googleapis.com/fcm/send/abc123",
        "https://user:pass@fcm.googleapis.com/fcm/send/abc123",
        "https://@fcm.googleapis.com/fcm/send/abc123",
        "https://:@fcm.googleapis.com/fcm/send/abc123",
        "https://:pass@fcm.googleapis.com/fcm/send/abc123",
        # Reject endpoints without a host.
        "https://",
        "https:///fcm/send/abc123",
        "://",
        "",
        "not a url",
        # Reject malformed IPv6 without raising.
        "https://[2001:db8::1/fcm/send/abc123",
        # Reject an out-of-range port without raising.
        "https://fcm.googleapis.com:99999/fcm/send/abc123",
        # Reject a host holding characters that are not legal in one.
        "https://fcm google apis.com/fcm/send/abc123",
        "https://fcm%20googleapis.com/fcm/send/abc123",
        "https://-fcm.googleapis.com/fcm/send/abc123",
        "https://.fcm.googleapis.com/fcm/send/abc123",
        f"https://{'a' * 254}.com/fcm/send/abc123",
        # Reject an IPv6 literal that is not an address at all.
        "https://[2001:db8::1::2]/fcm/send/abc123",
        "https://[not:an:address]/fcm/send/abc123",
        # Reject non-string values.
        None,
        42,
        ["https://fcm.googleapis.com/fcm/send/abc123"],
    ),
)
def test_plugin_vapid_bad_endpoints(endpoint):
    """An endpoint that cannot be used safely is rejected."""

    assert webpush_origin(endpoint) is None

    # A subscription containing an invalid endpoint cannot be loaded.
    with pytest.raises(exception.AppriseInvalidData):
        WebPushSubscription(_subscription(endpoint))

    sub = WebPushSubscription()
    assert sub.load(_subscription(endpoint)) is False
    assert sub.origin is None
    assert sub.endpoint is None
    assert bool(sub) is False

    # The manager also refuses the subscription.
    smgr = WebPushSubscriptionManager()
    assert smgr.add(_subscription(endpoint)) is False
    assert len(smgr) == 0


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_subscription_atomic_write(tmpdir):
    """A failed write leaves whatever was already on disk alone."""

    tmpdir0 = tmpdir.mkdir("atomic")
    path = os.path.join(str(tmpdir0), "subscriptions.json")

    smgr = WebPushSubscriptionManager()
    assert smgr.add(_subscription("https://web.push.apple.com/abc123")) is True
    assert smgr.write(path) is True

    with open(path) as f:
        original = json.load(f)

    assert set(original) == {"abc123"}

    # A partial write must not replace the existing file.
    smgr.clear()
    assert smgr.add(_subscription("https://web.push.apple.com/xyz789")) is True
    with mock.patch("json.dump", side_effect=OSError):
        assert smgr.write(path) is False

    with open(path) as f:
        assert json.load(f) == original

    # Do not leave temporary files behind.
    assert os.listdir(str(tmpdir0)) == ["subscriptions.json"]

    # Treat a missing destination directory as a failed write.
    assert smgr.write(os.path.join(str(tmpdir0), "missing", "s.json")) is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@pytest.mark.skipif(IS_WINDOWS, reason="Requires POSIX file modes")
def test_plugin_vapid_write_keeps_permissions(tmpdir):
    """An existing subscription file keeps the permissions it had."""

    tmpdir0 = tmpdir.mkdir("perms")
    path = os.path.join(str(tmpdir0), "subscriptions.json")

    smgr = WebPushSubscriptionManager()
    assert smgr.add(_subscription("https://web.push.apple.com/abc123")) is True
    assert smgr.write(path) is True

    # A brand new file is kept to ourselves; it lists where we deliver
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600

    # Hand the file a mode of its own and rewrite it
    os.chmod(path, 0o640)
    assert smgr.add(_subscription("https://web.push.apple.com/xyz789")) is True
    assert smgr.write(path) is True

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640

    # Confirm the new entry was written.
    with open(path) as f:
        assert set(json.load(f)) == {"abc123", "xyz789"}


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_write_follows_symlink(tmpdir):
    """A symlinked subscription file is written through, not replaced."""

    tmpdir0 = tmpdir.mkdir("symlink")
    target = os.path.join(str(tmpdir0), "real.json")
    link = os.path.join(str(tmpdir0), "subscriptions.json")

    smgr = WebPushSubscriptionManager()
    assert smgr.add(_subscription("https://web.push.apple.com/abc123")) is True
    assert smgr.write(target) is True
    os.symlink(target, link)

    # Write by way of the link
    assert smgr.add(_subscription("https://web.push.apple.com/xyz789")) is True
    assert smgr.write(link) is True

    # Our link survived and the file it points at was the one updated
    assert os.path.islink(link) is True
    assert os.path.realpath(link) == target

    with open(target) as f:
        assert set(json.load(f)) == {"abc123", "xyz789"}

    # No temporary files are left beside either path
    assert sorted(os.listdir(str(tmpdir0))) == [
        "real.json",
        "subscriptions.json",
    ]


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_bad_subfile_source(tmpdir):
    """An unavailable or invalid subscription source is refused."""

    smgr = WebPushSubscriptionManager()

    # A remote source that cannot be fetched. The download is mocked so the
    # test does not depend on anything outside this machine.
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value.status_code = (
            requests.codes.internal_server_error
        )
        mock_get.return_value.headers = {}
        mock_get.return_value.raise_for_status.side_effect = (
            requests.RequestException
        )
        mock_get.return_value.__enter__ = lambda s: s
        mock_get.return_value.__exit__ = lambda s, *a, **kw: None

        assert smgr.load("https://example.com/subscriptions.json") is False

    assert len(smgr) == 0

    # Reject an empty path as well.
    assert smgr.load("") is False
    assert len(smgr) == 0

    # A valid local file still loads normally.
    tmpdir0 = tmpdir.mkdir("local")
    path = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(path, ["https://web.push.apple.com/abc123"])

    assert smgr.load(path) is True
    assert len(smgr) == 1


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_subfile_not_in_url(tmpdir):
    """A subscription path we worked out ourselves stays out of the URL."""

    tmpdir0 = tmpdir.mkdir("portable")
    asset_ = asset.AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
        pem_autogen=True,
    )

    obj = Apprise.instantiate("vapid://user@example.ca/abc123", asset=asset_)

    # The file lives in this URL's own storage directory
    assert obj.subfile.startswith(obj.store.path)
    assert obj.subfile_specified is False

    # The URL omits local details so it can move to another installation.
    assert "subfile" not in obj.url()
    assert str(tmpdir0) not in obj.url()


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_subfile_in_url_when_asked(tmpdir):
    """A subscription path given to us is kept in the URL."""

    tmpdir0 = tmpdir.mkdir("explicit")
    subfile = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(subfile, ["https://web.push.apple.com/abc123"])

    obj = Apprise.instantiate(
        f"vapid://user@example.ca/abc123?subfile={subfile}",
        asset=asset.AppriseAsset(
            storage_mode=PersistentStoreMode.FLUSH,
            storage_path=str(tmpdir0),
            pem_autogen=True,
        ),
    )

    assert obj.subfile == subfile
    assert obj.subfile_specified is True

    # It round-trips, so a path someone chose is not lost
    assert "subfile" in obj.url()

    reloaded = Apprise.instantiate(obj.url())
    assert reloaded.subfile == subfile


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_url_moves_between_servers(tmpdir):
    """The same URL resolves to each machine's own storage directory."""

    rootA = tmpdir.mkdir("serverA")
    rootB = tmpdir.mkdir("serverB")

    def _server(root):
        return Apprise.instantiate(
            "vapid://user@example.ca/abc123",
            asset=asset.AppriseAsset(
                storage_mode=PersistentStoreMode.FLUSH,
                storage_path=str(root),
                pem_autogen=True,
            ),
        )

    objA = _server(rootA)
    objB = Apprise.instantiate(
        objA.url(),
        asset=asset.AppriseAsset(
            storage_mode=PersistentStoreMode.FLUSH,
            storage_path=str(rootB),
            pem_autogen=True,
        ),
    )

    # Both land on the same storage id, since it is worked out from the URL
    # and not from anything local to one machine
    assert objA.url_id() == objB.url_id()

    # Each instance reads from its own storage directory.
    assert objA.subfile.startswith(str(rootA))
    assert objB.subfile.startswith(str(rootB))


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_prune_keeps_other_entries(tmpdir):
    """Pruning removes only what it was asked to."""

    tmpdir0 = tmpdir.mkdir("keep")
    path = os.path.join(str(tmpdir0), "subscriptions.json")

    # Mix valid entries with a typo and an entry missing its keys.
    original = {
        "good": _subscription("https://fcm.googleapis.com/fcm/send/GOOD"),
        "dead": _subscription("https://fcm.googleapis.com/fcm/send/DEAD"),
        "httponly": _subscription("http://legacy.example.com/push/OLD"),
        "typo": _subscription("https://fcm.googleapis.com /fcm/send/X"),
        "handedit": {"endpoint": "https://fcm.googleapis.com/fcm/send/Y"},
    }
    with open(path, "w") as f:
        json.dump(original, f)

    smgr = WebPushSubscriptionManager()
    assert smgr.load(path) is True

    # Only the two usable entries were loaded
    assert set(smgr.dict) == {"good", "dead"}
    assert smgr.writable is True

    assert smgr.prune(["dead"]) is True

    with open(path) as f:
        remaining = json.load(f)

    # The expired entry is gone and nothing else was touched, so somebody's
    # typo is still theirs to fix rather than quietly deleted
    assert set(remaining) == {"good", "httponly", "typo", "handedit"}
    assert remaining["typo"] == original["typo"]
    assert remaining["handedit"] == original["handedit"]


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_prune_reloads_file(tmpdir):
    """Each prune uses the latest file instead of stale loaded state."""

    tmpdir0 = tmpdir.mkdir("concurrent")
    path = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(
        path,
        {
            n: f"https://fcm.googleapis.com/fcm/send/{n}"
            for n in ("a", "b", "c", "d")
        },
    )

    # Both instances begin with the same snapshot.
    first = WebPushSubscriptionManager()
    second = WebPushSubscriptionManager()
    assert first.load(path) is True
    assert second.load(path) is True

    assert first.prune(["a"]) is True
    assert second.prune(["c"]) is True

    with open(path) as f:
        remaining = json.load(f)

    # The second prune reloads the first one's change before writing.
    assert set(remaining) == {"b", "d"}


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@pytest.mark.skipif(IS_ROOT, reason="Root can write read-only files")
def test_plugin_vapid_readonly_file_respected(tmpdir):
    """A read-only subscription file is left alone."""

    tmpdir0 = tmpdir.mkdir("readonly")
    path = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(path, ["https://fcm.googleapis.com/fcm/send/X"])
    os.chmod(path, 0o444)

    smgr = WebPushSubscriptionManager()
    assert smgr.load(path) is True
    assert smgr.path == path

    # We can read it, but it is not ours to change
    assert smgr.writable is False

    # Swapping a file into place only needs permission on the directory, so
    # prune() has to refuse on its own rather than rely on the caller
    assert smgr.prune(["x"]) is False

    with open(path) as f:
        assert set(json.load(f)) == {"x"}


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@pytest.mark.skipif(IS_ROOT, reason="Root can write read-only files")
@mock.patch("requests.post")
def test_plugin_vapid_retires_when_not_writable(mock_post, tmpdir):
    """An expired endpoint is tracked when its file cannot be updated."""

    mock_post.return_value = _mk_resp(requests.codes.gone)

    tmpdir0 = tmpdir.mkdir("retire")
    subfile = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(subfile, ["https://web.push.apple.com/DEAD"])
    os.chmod(subfile, 0o444)

    asset_ = asset.AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
        pem_autogen=True,
    )

    obj = NotifyVapid(
        "user@example.ca",
        targets=["dead"],
        subfile=subfile,
        asset=asset_,
    )
    assert obj.send("test") is False

    # The file still holds it, because it was not ours to rewrite
    with open(subfile) as f:
        assert set(json.load(f)) == {"dead"}

    # Remember the endpoint in persistent storage instead.
    assert obj.store.get(obj.vapid_retired_key) == [
        "https://web.push.apple.com/DEAD"
    ]

    # A fresh instance skips it and does not report a false success.
    mock_post.reset_mock()
    obj2 = NotifyVapid(
        "user@example.ca",
        targets=["dead"],
        subfile=subfile,
        asset=asset_,
    )
    assert obj2.send("test") is False
    assert mock_post.call_count == 0


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_prune_edge_cases(tmpdir):
    """Pruning declines anything it cannot safely rewrite."""

    tmpdir0 = tmpdir.mkdir("edges")

    # Nothing was loaded, so there is no file to update
    smgr = WebPushSubscriptionManager()
    assert smgr.path is None
    assert smgr.writable is False
    assert smgr.prune(["anything"]) is False

    # A single entry file carries no names, so there is nothing to take out
    single = os.path.join(str(tmpdir0), "single.json")
    with open(single, "w") as f:
        json.dump(
            _subscription("https://fcm.googleapis.com/fcm/send/abc123"), f
        )

    smgr = WebPushSubscriptionManager()
    assert smgr.load(single) is True
    assert smgr.prune(["abc123"]) is False

    # A name we do not hold leaves the file exactly as it was
    many = os.path.join(str(tmpdir0), "many.json")
    _write_subscriptions(many, ["https://fcm.googleapis.com/fcm/send/abc123"])

    smgr = WebPushSubscriptionManager()
    assert smgr.load(many) is True
    assert smgr.prune(["nothing-like-this"]) is True

    with open(many) as f:
        assert set(json.load(f)) == {"abc123"}

    # Content that is no longer valid JSON is left for its owner to fix
    with open(many, "w") as f:
        f.write("{ this is not json")

    assert smgr.prune(["abc123"]) is False

    with open(many) as f:
        assert f.read() == "{ this is not json"

    # Also reject a file that does not contain an object.
    with open(many, "w") as f:
        json.dump(["not", "an", "object"], f)

    assert smgr.prune(["abc123"]) is False

    # A write that fails part way leaves the file as it was
    _write_subscriptions(many, ["https://fcm.googleapis.com/fcm/send/abc123"])
    assert smgr.load(many) is True

    with mock.patch("json.dump", side_effect=OSError):
        assert smgr.prune(["abc123"]) is False

    with open(many) as f:
        assert set(json.load(f)) == {"abc123"}


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_remote_subfile(tmpdir):
    """A remotely hosted subscription file loads as read-only."""

    tmpdir0 = tmpdir.mkdir("remote")
    local = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(local, ["https://fcm.googleapis.com/fcm/send/abc123"])

    with open(local, "rb") as f:
        payload = f.read()

    smgr = WebPushSubscriptionManager()

    # Stand in for the download an AppriseAttachment would perform
    with mock.patch("requests.get") as mock_get:
        mock_get.return_value.status_code = requests.codes.ok
        mock_get.return_value.headers = {"Content-Length": len(payload)}
        mock_get.return_value.iter_content.return_value = iter([payload])
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.__enter__ = lambda s: s
        mock_get.return_value.__exit__ = lambda s, *a, **kw: None

        assert smgr.load("https://example.com/subscriptions.json") is True

    # The subscription came through
    assert set(smgr.dict) == {"abc123"}

    # With no local source file, it cannot be rewritten.
    assert smgr.path is None
    assert smgr.writable is False
    assert smgr.prune(["abc123"]) is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_retires_when_prune_fails(mock_post, tmpdir):
    """A pruning failure still stops the endpoint being tried again."""

    mock_post.return_value = _mk_resp(requests.codes.gone)

    tmpdir0 = tmpdir.mkdir("prunefail")
    subfile = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(subfile, ["https://web.push.apple.com/DEAD"])

    asset_ = asset.AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
        pem_autogen=True,
    )

    obj = NotifyVapid(
        "user@example.ca",
        targets=["dead"],
        subfile=subfile,
        asset=asset_,
    )

    # The file is writable, but rewriting it does not work out
    with mock.patch.object(
        WebPushSubscriptionManager, "prune", return_value=False
    ):
        assert obj.send("test") is False

    # The file still lists it, since the rewrite failed
    with open(subfile) as f:
        assert set(json.load(f)) == {"dead"}

    # ...so the endpoint was remembered instead and is not asked for again
    assert obj.store.get(obj.vapid_retired_key) == [
        "https://web.push.apple.com/DEAD"
    ]

    mock_post.reset_mock()
    obj2 = NotifyVapid(
        "user@example.ca",
        targets=["dead"],
        subfile=subfile,
        asset=asset_,
    )
    assert obj2.send("test") is False
    assert mock_post.call_count == 0


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_load_forgets_previous_path(tmpdir):
    """A later load does not leave an earlier file behind to be pruned."""

    tmpdir0 = tmpdir.mkdir("stale")
    first = os.path.join(str(tmpdir0), "first.json")
    _write_subscriptions(first, ["https://fcm.googleapis.com/fcm/send/abc123"])

    smgr = WebPushSubscriptionManager()
    assert smgr.load(first) is True
    assert smgr.path == first

    # A load that fails must not leave the previous file remembered,
    # otherwise a prune would rewrite a file we are no longer using
    assert smgr.load(os.path.join(str(tmpdir0), "missing.json")) is False
    assert smgr.path is None
    assert smgr.writable is False
    assert smgr.prune(["abc123"]) is False

    # The first file is untouched
    with open(first) as f:
        assert set(json.load(f)) == {"abc123"}


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_logging_masks_secrets(tmpdir):
    """Endpoints and remote credentials do not reach the logs intact."""

    secret = "cH1s-Is-A-SeCr3t-RegIstratIon-Id"

    # An endpoint token is sensitive and must not appear in logs.
    masked = cwe312_loggable(f"https://fcm.googleapis.com/fcm/send/{secret}")
    assert secret not in masked

    # A missing value is reported rather than blowing up
    assert cwe312_loggable(None) == "(none)"
    assert cwe312_loggable("") == "(none)"

    # Keep local paths readable for troubleshooting.
    assert (
        cwe312_loggable("/etc/apprise/subscriptions.json")
        == "/etc/apprise/subscriptions.json"
    )

    smgr = WebPushSubscriptionManager()

    # A remote subscription file can carry a password
    loggable = smgr.loggable_path(
        "https://user:pass123@example.com/subscriptions.json"
    )
    assert "pass123" not in loggable

    assert smgr.loggable_path(None) == "(none)"

    # Somebody who turns masking off gets the value through untouched
    smgr_plain = WebPushSubscriptionManager(
        asset=asset.AppriseAsset(secure_logging=False)
    )
    url = "https://user:pass123@example.com/subscriptions.json"
    assert smgr_plain.loggable_path(url) == url


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_load_read_errors(tmpdir):
    """Loading tells a missing file, bad JSON and a disk problem apart."""

    tmpdir0 = tmpdir.mkdir("loaderrs")
    path = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(path, ["https://fcm.googleapis.com/fcm/send/abc123"])

    smgr = WebPushSubscriptionManager()

    # The file goes away between being resolved and being opened
    with mock.patch("builtins.open", side_effect=FileNotFoundError):
        assert smgr.load(path) is False

    # It is there, but it does not hold JSON
    with mock.patch(
        "json.load", side_effect=json.decoder.JSONDecodeError("bad", "", 0)
    ):
        assert smgr.load(path) is False

    # It is there and we are not allowed to read it
    with mock.patch("builtins.open", side_effect=OSError):
        assert smgr.load(path) is False

    # ...and it still loads when nothing is wrong
    assert smgr.load(path) is True


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_prune_read_errors(tmpdir):
    """Pruning tells a missing file, bad JSON and a disk problem apart."""

    tmpdir0 = tmpdir.mkdir("pruneerrs")
    path = os.path.join(str(tmpdir0), "subscriptions.json")
    _write_subscriptions(path, ["https://fcm.googleapis.com/fcm/send/abc123"])

    smgr = WebPushSubscriptionManager()
    assert smgr.load(path) is True

    # The file goes away before we can rewrite it
    with mock.patch("builtins.open", side_effect=FileNotFoundError):
        assert smgr.prune(["abc123"]) is False

    # Leave newly invalid content untouched rather than overwriting it.
    with mock.patch(
        "json.load", side_effect=json.decoder.JSONDecodeError("bad", "", 0)
    ):
        assert smgr.prune(["abc123"]) is False

    # We are no longer allowed to read it
    with mock.patch("builtins.open", side_effect=OSError):
        assert smgr.prune(["abc123"]) is False

    # The file is untouched throughout
    with open(path) as f:
        assert set(json.load(f)) == {"abc123"}


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_write_errors(tmpdir):
    """Writing tells a content problem apart from a disk problem."""

    tmpdir0 = tmpdir.mkdir("writeerrs")
    path = os.path.join(str(tmpdir0), "subscriptions.json")

    smgr = WebPushSubscriptionManager()
    assert smgr.add(_subscription("https://web.push.apple.com/abc123")) is True

    # Content that will not turn into JSON
    with mock.patch("json.dump", side_effect=TypeError):
        assert smgr.write(path) is False

    # A circular reference raises ValueError rather than TypeError
    with mock.patch("json.dump", side_effect=ValueError):
        assert smgr.write(path) is False

    # ...and a disk problem is reported as one
    with mock.patch("json.dump", side_effect=OSError):
        assert smgr.write(path) is False

    # Nothing was left behind by any of those
    assert os.listdir(str(tmpdir0)) == []

    assert smgr.write(path) is True


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_write_unreadable_mode(tmpdir):
    """A file whose mode cannot be read is still replaced."""

    tmpdir0 = tmpdir.mkdir("modeerr")
    path = os.path.join(str(tmpdir0), "subscriptions.json")

    smgr = WebPushSubscriptionManager()
    assert smgr.add(_subscription("https://web.push.apple.com/abc123")) is True
    assert smgr.write(path) is True

    # We cannot stat what is already there, so our own mode is kept rather
    # than guessing at one
    assert smgr.add(_subscription("https://web.push.apple.com/xyz789")) is True
    with mock.patch("os.stat", side_effect=PermissionError):
        assert smgr.write(path) is True

    with open(path) as f:
        assert set(json.load(f)) == {"abc123", "xyz789"}


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_expired_is_reported(mock_post, tmpdir):
    """An expired subscription is reported as a failure."""

    def respond(url, *args, **kwargs):
        # One device is gone, the other is fine
        return _mk_resp(
            requests.codes.gone
            if url.endswith("DEAD")
            else requests.codes.created
        )

    mock_post.side_effect = respond

    obj, _ = _mk_notifier(
        tmpdir,
        {
            "live": "https://web.push.apple.com/LIVE",
            "dead": "https://web.push.apple.com/DEAD",
        },
        ["live", "dead"],
        name="expreport",
    )

    # The expired endpoint is a real failure; it is pruned below so no
    # retry will reach for it again.
    assert obj.send("test") is False
    assert "dead" not in obj.subscriptions


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
@mock.patch("requests.post")
def test_plugin_vapid_all_expired_still_fails(mock_post, tmpdir):
    """Nothing reaching anybody is a failure however we got there."""

    mock_post.return_value = _mk_resp(requests.codes.gone)

    obj, _ = _mk_notifier(
        tmpdir,
        ["https://web.push.apple.com/DEAD"],
        ["dead"],
        name="allexp",
    )

    # Every target expired, so the message went nowhere.
    assert obj.send("test") is False


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_plugin_vapid_image_url(tmpdir):
    """The image flag survives a round trip through the URL."""

    tmpdir0 = tmpdir.mkdir("imgurl")
    asset_ = asset.AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
        pem_autogen=True,
    )

    # Images are included by default
    obj = Apprise.instantiate("vapid://user@example.ca/abc123", asset=asset_)
    assert obj.include_image is True
    assert "image=yes" in obj.url()

    # Turning them off is remembered rather than quietly lost when the URL
    # is rebuilt
    off = Apprise.instantiate(
        "vapid://user@example.ca/abc123?image=no", asset=asset_
    )
    assert off.include_image is False
    assert "image=no" in off.url()

    assert Apprise.instantiate(off.url()).include_image is False
    assert Apprise.instantiate(obj.url()).include_image is True
