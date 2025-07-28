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

from datetime import datetime, timedelta, timezone
import gzip
import json

# Disable logging for a cleaner testing output
import logging
import os
import shutil
import sys
import time
from unittest import mock
import zlib

import pytest

from apprise import exception
from apprise.asset import AppriseAsset
from apprise.persistent_store import (
    CacheJSONEncoder,
    CacheObject,
    PersistentStore,
    PersistentStoreMode,
)

logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


def test_persistent_storage_asset(tmpdir):
    """Tests the Apprise Asset Object when setting the Persistent Store."""

    asset = AppriseAsset(storage_path=str(tmpdir))
    assert asset.storage_path == str(tmpdir)
    assert asset.storage_mode is PersistentStoreMode.AUTO

    # If there is no storage path, we're always set to memory
    asset = AppriseAsset(
        storage_path=None, storage_mode=PersistentStoreMode.MEMORY
    )
    assert asset.storage_path is None
    assert asset.storage_mode is PersistentStoreMode.MEMORY


def test_persistent_storage_bad_mode(tmpdir):
    """Persistent Storage Bad Mode Testing."""
    # Create ourselves an attachment object set in Memory Mode only
    with pytest.raises(AttributeError):
        PersistentStore(
            namespace="abc", path=str(tmpdir), mode="invalid"
        )

    with pytest.raises(AttributeError):
        AppriseAsset(storage_mode="invalid")


def test_disabled_persistent_storage(tmpdir):
    """Persistent Storage General Testing."""
    # Create ourselves an attachment object set in Memory Mode only
    pc = PersistentStore(
        namespace="abc", path=str(tmpdir), mode=PersistentStoreMode.MEMORY
    )
    assert pc.read() is None
    assert pc.read("mykey") is None
    with pytest.raises(AttributeError):
        # Invalid key specified
        pc.read("!invalid")
    assert pc.write("data") is False
    assert pc.get("key") is None
    assert pc.set("key", "value")
    assert pc.get("key") == "value"

    assert pc.set("key2", "value")
    pc.clear("key", "key-not-previously-set")
    assert pc.get("key2") == "value"
    assert pc.get("key") is None

    # Set it again
    assert pc.set("key", "another-value")
    # Clears all
    pc.clear()
    assert pc.get("key2") is None
    assert pc.get("key") is None
    # A second call to clear on an already empty cache set
    pc.clear()

    # No dirty flag is set as ther is nothing to write to disk
    pc.set("not-persistent", "value", persistent=False)
    del pc["not-persistent"]
    with pytest.raises(KeyError):
        # Can't delete it twice
        del pc["not-persistent"]

    # A Persistent key
    pc.set("persistent", "value")
    # Removes it and sets/clears the dirty flag
    del pc["persistent"]

    # After all of the above, nothing was done to the directory
    assert len(os.listdir(str(tmpdir))) == 0

    with pytest.raises(AttributeError):
        # invalid persistent store specified
        PersistentStore(namespace="abc", path=str(tmpdir), mode="garbage")


def test_persistent_storage_init(tmpdir):
    """Test storage initialization."""
    with pytest.raises(AttributeError):
        PersistentStore(namespace="", path=str(tmpdir))
    with pytest.raises(AttributeError):
        PersistentStore(namespace=None, path=str(tmpdir))

    with pytest.raises(AttributeError):
        PersistentStore(namespace="_", path=str(tmpdir))
    with pytest.raises(AttributeError):
        PersistentStore(namespace=".", path=str(tmpdir))
    with pytest.raises(AttributeError):
        PersistentStore(namespace="-", path=str(tmpdir))

    with pytest.raises(AttributeError):
        PersistentStore(namespace="_abc", path=str(tmpdir))
    with pytest.raises(AttributeError):
        PersistentStore(namespace=".abc", path=str(tmpdir))
    with pytest.raises(AttributeError):
        PersistentStore(namespace="-abc", path=str(tmpdir))

    with pytest.raises(AttributeError):
        PersistentStore(namespace="%", path=str(tmpdir))


def test_persistent_storage_general(tmpdir):
    """Persistent Storage General Testing."""
    namespace = "abc"
    # Create ourselves an attachment object
    pc = PersistentStore()

    # Default mode when a path is not provided
    assert pc.mode == PersistentStoreMode.MEMORY

    assert pc.size() == 0
    assert pc.files() == []
    assert pc.files(exclude=True, lazy=False) == []
    assert pc.files(exclude=False, lazy=False) == []
    pc.set("key", "value")
    # There is no disk size utilized
    assert pc.size() == 0
    assert pc.files(exclude=True, lazy=False) == []
    assert pc.files(exclude=False, lazy=False) == []

    # Create ourselves an attachment object
    pc = PersistentStore(namespace=namespace, path=str(tmpdir))

    # Default mode when a path is provided
    assert pc.mode == PersistentStoreMode.AUTO

    # Get our path associated with our Persistent Store
    assert pc.path == os.path.join(str(tmpdir), "abc")

    # Expiry testing
    assert pc.set("key", "value", datetime.now() + timedelta(hours=1))
    # i min in the future
    assert pc.set("key", "value", 60)

    with pytest.raises(AttributeError):
        assert pc.set("key", "value", "invalid")

    pc = PersistentStore(namespace=namespace, path=str(tmpdir))

    # Our key is still valid and we load it from disk
    assert pc.get("key") == "value"
    assert pc["key"] == "value"

    pc = PersistentStore(namespace=namespace, path=str(tmpdir))
    assert pc.keys()
    # Second call after already initialized skips over initialization
    assert pc.keys()

    pc = PersistentStore(namespace=namespace, path=str(tmpdir))

    with pytest.raises(KeyError):
        # The below
        pc["unassigned_key"]


def test_persistent_storage_auto_mode(tmpdir):
    """Persistent Storage Auto Write Testing."""
    namespace = "abc"
    # Create ourselves an attachment object
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.AUTO
    )

    pc.write(b"test")
    with mock.patch("os.unlink", side_effect=FileNotFoundError()):
        assert pc.delete(all=True) is True

    # Create a temporary file we can delete
    with open(os.path.join(pc.path, pc.temp_dir, "test.file"), "wb") as fd:
        fd.write(b"data")

    # Delete just the temporary files
    assert pc.delete(temp=True) is True

    # Delete just the temporary files
    # Create a cache entry and delete it
    assert pc.set("key", "value") is True
    pc.write(b"test")
    assert pc.delete(cache=True) is True
    # Verify our data entry wasn't removed
    assert pc.read() == b"test"
    # But our cache was
    assert pc.get("key") is None

    # A reverse of the above... create a cache an data variable and
    # Clear the data; make sure our cache is still there
    assert pc.set("key", "value") is True
    assert pc.write(b"test", key="iokey") is True
    assert pc.delete("iokey") is True
    assert pc.get("key") == "value"
    assert pc.read("iokey") is None


def test_persistent_storage_flush_mode(tmpdir):
    """Persistent Storage Forced Write Testing."""
    namespace = "abc"
    # Create ourselves an attachment object
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # Reference path
    path = os.path.join(str(tmpdir), namespace)

    assert pc.size() == 0
    assert list(pc.files()) == []

    # Key is not set yet
    assert pc.get("key") is None
    assert len(pc.keys()) == 0
    assert "key" not in pc

    # Verify our data is set
    assert pc.set("key", "value")
    assert len(pc.keys()) == 1
    assert "key" in list(pc.keys())

    assert pc.size() > 0
    assert len(pc.files()) == 1

    # Second call uses Lazy cache
    # Just our cache file
    assert len(pc.files()) == 1

    # Setting the same value again uses a lazy mode and
    # bypasses all of the write overhead
    assert pc.set("key", "value")

    path_content = os.listdir(path)
    # var, cache.psdata, and tmp
    assert len(path_content) == 3

    # Assignments (causes another disk write)
    pc["key"] = "value2"

    # Setting the same value and explictly marking the field as not being
    # perisistent
    pc.set("key-xx", "abc123", persistent=False)
    # Changing it's value doesn't alter the persistent flag
    pc["key-xx"] = "def678"
    # Setting it twice
    pc["key-xx"] = "def678"

    # Our retrievals
    assert pc["key-xx"] == "def678"
    assert pc.get("key-xx") == "def678"

    # But on the destruction of our object, it is not available again
    del pc
    # Create ourselves an attachment object
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    assert pc.get("key-xx") is None
    with pytest.raises(KeyError):
        pc["key-xx"]

    # Now our key is set
    assert "key" in pc
    assert pc.get("key") == "value2"

    # A directory was created identified by the namespace
    assert len(os.listdir(str(tmpdir))) == 1
    assert namespace in os.listdir(str(tmpdir))

    path_content = os.listdir(path)
    assert len(path_content) == 4

    # Another write doesn't change the file count
    pc["key"] = "value3"
    path_content = os.listdir(path)
    assert len(path_content) == 4

    # Our temporary directory used for all file handling in this namespace
    assert pc.temp_dir in path_content
    # Our cache file
    assert os.path.basename(pc.cache_file) in path_content

    path = os.path.join(pc.path, pc.temp_dir)
    path_content = os.listdir(path)

    # We always do our best to clean any temporary files up
    assert len(path_content) == 0

    # Destroy our object
    del pc

    # Re-initialize it
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # Our key is persistent and available right away
    assert pc.get("key") == "value3"
    assert "key" in pc

    # Remove our item
    del pc["key"]
    assert pc.size() == 0
    assert "key" not in pc

    assert pc.write("data") is True
    assert pc.read() == b"data"
    assert pc.write(b"data") is True
    assert pc.read() == b"data"

    assert pc.read("default") == b"data"
    assert pc.write("data2", key="mykey") is True
    assert pc.read("mykey") == b"data2"

    # We can selectively delete our key
    assert pc.delete("mykey")
    assert pc.read("mykey") is None
    # Other keys are not touched
    assert pc.read("default") == b"data"
    assert pc.read() == b"data"
    # Full purge
    assert pc.delete()
    assert pc.read("mykey") is None
    assert pc.read() is None

    # Practice with files
    with open(os.path.join(TEST_VAR_DIR, "apprise-test.gif"), "rb") as fd:
        assert pc.write(fd, key="mykey", compress=False) is True

        # Read our content back
        fd.seek(0)
        assert pc.read("mykey", compress=False) == fd.read()

    with open(os.path.join(TEST_VAR_DIR, "apprise-test.gif"), "rb") as fd:
        assert pc.write(fd, key="mykey", compress=True) is True

        # Read our content back; content will be compressed
        fd.seek(0)
        assert pc.read("mykey", compress=True) == fd.read()

    class Foobar:
        def read(*args, **kwargs):
            return 42

    foobar = Foobar()
    # read() returns a non string/bin
    with pytest.raises(exception.AppriseDiskIOError):
        pc.write(foobar, key="foobar", compress=True)
    assert pc.read("foobar") is None

    class Foobar:
        def read(*args, **kwargs):
            return "good"

    foobar = Foobar()
    # read() returns a string so the below write works
    assert pc.write(foobar, key="foobar", compress=True)
    assert pc.read("foobar") == b"good"
    pc.delete()

    class Foobar:
        def read(*args, **kwargs):
            # Throw an exception
            raise TypeError()

    foobar = Foobar()
    # read() returns a non string/bin
    with pytest.raises(exception.AppriseDiskIOError):
        pc.write(foobar, key="foobar", compress=True)
    assert pc.read("foobar") is None

    # Set our max_file_size
    _prev_max_file_size = pc.max_file_size
    pc.max_file_size = 1
    assert pc.delete()

    assert pc.write("data") is False
    assert pc.read() is None

    # Restore setting
    pc.max_file_size = _prev_max_file_size

    # Reset
    pc.delete()

    assert pc.write("data")
    # Corrupt our data
    data = pc.read(compress=False)[:20] + pc.read(compress=False)[:10]
    pc.write(data, compress=False)

    # Now we'll get an exception reading back the corrupted data
    assert pc.read() is None

    # Keep in mind though the data is still there; operator should write
    # and read the way they expect to and things will work out fine
    # This test just proves that Apprise Peresistent storage still
    # gracefully handles bad data
    assert pc.read(compress=False) == data

    # No key exists also returns None
    assert pc.read("no-key-exists") is None

    pc.write(b"test")
    pc["key"] = "value"
    with mock.patch("os.unlink", side_effect=FileNotFoundError()):
        assert pc.delete(all=True) is True
    with mock.patch("os.unlink", side_effect=OSError()):
        assert pc.delete(all=True) is False

    # Create a temporary file we can delete
    tmp_file = os.path.join(pc.path, pc.temp_dir, "test.file")
    with open(tmp_file, "wb") as fd:
        fd.write(b"data")

    assert pc.set("key", "value") is True
    assert pc.write(b"test", key="iokey") is True
    # Delete just the temporary files
    assert pc.delete(temp=True) is True
    assert os.path.exists(tmp_file) is False
    # our other entries are untouched
    assert pc.get("key") == "value"
    assert pc.read("iokey") == b"test"

    # Delete just the temporary files
    # Create a cache entry and delete it
    assert pc.set("key", "value") is True
    assert pc.write(b"test") is True
    assert pc.delete(cache=True) is True
    # Verify our data entry wasn't removed
    assert pc.read() == b"test"
    # But our cache was
    assert pc.get("key") is None

    # A reverse of the above... create a cache an data variable and
    # Clear the data; make sure our cache is still there
    assert pc.set("key", "value") is True
    assert pc.write(b"test", key="iokey") is True
    assert pc.delete("iokey") is True
    assert pc.get("key") == "value"
    assert pc.read("iokey") is None

    # Create some custom files
    cust1_file = os.path.join(pc.path, "test.file")
    cust2_file = os.path.join(pc.path, pc.data_dir, "test.file")
    with open(cust1_file, "wb") as fd:
        fd.write(b"data")
    with open(cust2_file, "wb") as fd:
        fd.write(b"data")

    # Even after a full flush our files will exist
    assert pc.delete()
    assert os.path.exists(cust1_file) is True
    assert os.path.exists(cust2_file) is True

    # However, if we turn off validate, we do a full sweep because these
    # unknown files are lingering in our directory space
    assert pc.delete(validate=False)
    assert os.path.exists(cust1_file) is False
    assert os.path.exists(cust2_file) is False

    pc["key"] = "value"
    pc["key2"] = "value2"
    assert "key" in pc
    assert "key2" in pc
    pc.clear("key")
    assert "key" not in pc
    assert "key2" in pc

    # Set expired content
    pc.set(
        "expired",
        "expired-content",
        expires=datetime.now() - timedelta(days=1),
    )

    # It's actually there... but it's expired so our persistent
    # storage is behaving as it should
    assert "expired" not in pc
    assert pc.get("expired") is None
    # Prune our content
    pc.prune()


def test_persistent_storage_corruption_handling(tmpdir):
    """Test corrupting handling of storage."""

    # Namespace
    namespace = "def456"

    # Initialize it
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    cache_file = pc.cache_file
    assert not os.path.isfile(cache_file)

    # Store our key
    pc["mykey"] = 42
    assert os.path.isfile(cache_file)

    with gzip.open(cache_file, "rb") as f:
        # Read our content from disk
        json.loads(f.read().decode("utf-8"))

    # Remove object
    del pc

    # Corrupt the file
    with open(cache_file, "wb") as f:
        f.write(b"{")

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # File is corrupted
    assert "mykey" not in pc
    pc["mykey"] = 42
    del pc

    # File is corrected now
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    assert "mykey" in pc

    # Corrupt the file again
    with gzip.open(cache_file, "wb") as f:
        # Bad JSON File
        f.write(b"{")

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # File is corrupted
    assert "mykey" not in pc
    pc["mykey"] = 42
    del pc

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # Test our force flush
    assert pc.flush(force=True) is True
    # double call
    assert pc.flush(force=True) is True

    # Zlib error handling as well during open
    with (
        mock.patch("gzip.open", side_effect=OSError()),
        pytest.raises(KeyError),
    ):
        pc["mykey"] = 43

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # Zlib error handling as well during open
    with mock.patch("gzip.open", side_effect=OSError()):
        # No keys can be returned
        assert not pc.keys()

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    with (
        mock.patch("json.loads", side_effect=TypeError()),
        mock.patch("os.unlink", side_effect=FileNotFoundError()),
        pytest.raises(KeyError),
    ):
        pc["mykey"] = 44

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    with (
        mock.patch("json.loads", side_effect=TypeError()),
        mock.patch("os.unlink", side_effect=OSError()),
        pytest.raises(KeyError),
    ):
        pc["mykey"] = 45

    pc["my-new-key"] = 43
    with mock.patch("gzip.open", side_effect=OSError()):
        # We will fail to flush our content to disk
        assert pc.flush(force=True) is False

    with mock.patch("json.dumps", side_effect=TypeError()):
        # We will fail to flush our content to disk
        assert pc.flush(force=True) is False

    with mock.patch("os.makedirs", side_effect=OSError()):
        pc = PersistentStore(
            namespace=namespace,
            path=str(tmpdir),
            mode=PersistentStoreMode.FLUSH,
        )

        # Directory initialization failed so we fall back to memory mode
        assert pc.mode == PersistentStoreMode.MEMORY

    # Handle file updates
    pc = PersistentStore(
        namespace="file-time-refresh",
        path=str(tmpdir),
        mode=PersistentStoreMode.AUTO,
    )

    pc["test"] = "abcd"
    assert pc.write(b"data", key="abcd") is True
    assert pc.read("abcd", expires=True) == b"data"
    assert pc.write(b"data2", key="defg") is True
    assert pc.read("defg", expires=False) == b"data2"
    assert pc.write(b"data3", key="hijk") is True
    assert pc.read("hijk", expires=False) == b"data3"
    assert pc["test"] == "abcd"

    with mock.patch("os.utime", side_effect=(OSError(), FileNotFoundError())):
        pc.flush()

    # directory initialization okay
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    assert "mykey" not in pc
    pc["mykey"] = 42
    del pc

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )
    assert "mykey" in pc

    # Remove the last entry
    del pc["mykey"]
    with (
        mock.patch("os.rename", side_effect=OSError()),
        mock.patch("os.unlink", side_effect=OSError()),
    ):
        assert not pc.flush(force=True)

    # Create another entry
    pc["mykey"] = 42
    with mock.patch("tempfile.NamedTemporaryFile", side_effect=OSError()):
        assert not pc.flush(force=True)

        # Temporary file cleanup failure
        with mock.patch(
            "tempfile._TemporaryFileWrapper.close", side_effect=OSError()
        ):
            assert not pc.flush(force=True)

    # Create another entry
    pc["mykey"] = 43
    mock_ntf = mock.MagicMock()
    mock_ntf.name = os.path.join(tmpdir, "file")

    #
    # Recursion loop checking
    #
    with mock.patch(
        "tempfile.NamedTemporaryFile",
        side_effect=[FileNotFoundError(), FileNotFoundError(), mock_ntf],
    ):
        # No way to have recursion loop
        assert not pc.flush(force=True, _recovery=True)

    with mock.patch(
        "tempfile.NamedTemporaryFile",
        side_effect=[FileNotFoundError(), FileNotFoundError(), mock_ntf],
    ):
        # No way to have recursion loop
        assert not pc.flush(force=False, _recovery=True)

    with mock.patch(
        "tempfile.NamedTemporaryFile",
        side_effect=[FileNotFoundError(), FileNotFoundError(), mock_ntf],
    ):
        # No way to have recursion loop
        assert not pc.flush(force=False, _recovery=False)

    with mock.patch(
        "tempfile.NamedTemporaryFile",
        side_effect=[FileNotFoundError(), FileNotFoundError(), mock_ntf],
    ):
        # No way to have recursion loop
        assert not pc.flush(force=True, _recovery=False)

    with (
        mock.patch(
            "tempfile._TemporaryFileWrapper.close",
            side_effect=(OSError(), None),
        ),
        mock.patch("os.unlink", side_effect=(OSError())),
    ):
        assert not pc.flush(force=True)

    with mock.patch(
        "tempfile._TemporaryFileWrapper.close", side_effect=OSError()
    ):
        assert not pc.flush(force=True)

    with (
        mock.patch(
            "tempfile._TemporaryFileWrapper.close",
            side_effect=(OSError(), None),
        ),
        mock.patch("os.unlink", side_effect=OSError()),
    ):
        assert not pc.flush(force=True)

    with (
        mock.patch(
            "tempfile._TemporaryFileWrapper.close",
            side_effect=(OSError(), None),
        ),
        mock.patch("os.unlink", side_effect=FileNotFoundError()),
    ):
        assert not pc.flush(force=True)

    del pc

    # directory initialization okay
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # Allows us to play with encoding errors
    pc.encoding = "ascii"

    # Handle write() calls
    with mock.patch("os.stat", side_effect=OSError()):
        # We fail to fetch the filesize of our old file causing us to fail
        assert pc.write("abcd") is False

    # ボールト translates to vault (no bad word here) :)
    data = "ボールト"

    # We'll have encoding issues
    assert pc.write(data) is False

    with mock.patch("gzip.open", side_effect=FileNotFoundError()):
        pc = PersistentStore(namespace=namespace, path=str(tmpdir))

        # recovery mode will kick in and even it will fail
        assert pc.write(b"key") is False

    with mock.patch("gzip.open", side_effect=OSError()):
        pc = PersistentStore(namespace=namespace, path=str(tmpdir))

        # Falls to default
        assert pc.get("key") is None

        pc = PersistentStore(namespace=namespace, path=str(tmpdir))
        with pytest.raises(KeyError):
            pc["key"] = "value"

        pc = PersistentStore(namespace=namespace, path=str(tmpdir))
        with pytest.raises(KeyError):
            pc["key"]

        pc = PersistentStore(namespace=namespace, path=str(tmpdir))
        with pytest.raises(KeyError):
            del pc["key"]

        pc = PersistentStore(namespace=namespace, path=str(tmpdir))
        # Fails to set key
        assert pc.set("key", "value") is False

        pc = PersistentStore(namespace=namespace, path=str(tmpdir))
        # Fails to clear
        assert pc.clear() is False

        pc = PersistentStore(namespace=namespace, path=str(tmpdir))
        # Fails to prune
        assert pc.prune() is False

    # Set some expired content
    pc.set(
        "key",
        "value",
        persistent=False,
        expires=datetime.now() - timedelta(days=1),
    )
    pc.set(
        "key2",
        "value2",
        persistent=True,
        expires=datetime.now() - timedelta(days=1),
    )

    # Set some un-expired content
    pc.set("key3", "value3", persistent=True)
    pc.set("key4", "value4", persistent=False)
    assert pc.prune() is True

    # Second call has no change made
    assert pc.prune() is False

    # Reset
    pc.delete()

    # directory initialization okay
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # Write some content that expires almost immediately
    pc.set(
        "key1",
        "value",
        persistent=True,
        expires=datetime.now() + timedelta(seconds=1),
    )
    pc.set(
        "key2",
        "value",
        persistent=True,
        expires=datetime.now() + timedelta(seconds=1),
    )
    pc.set(
        "key3",
        "value",
        persistent=True,
        expires=datetime.now() + timedelta(seconds=1),
    )
    pc.flush()

    # Wait out our expiry
    time.sleep(1.3)

    # now initialize our storage again
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # This triggers our __load_cache() which reads in a value
    # determined to have already been expired
    assert "key1" not in pc
    assert "key2" not in pc
    assert "key3" not in pc

    # Sweep
    pc.delete()
    pc.set("key", "value")
    pc.set("key2", "value2")
    pc.write("more-content")
    # Flush our content to disk
    pc.flush()

    # Ideally we'd use os.stat below, but it is called inside a list
    # comprehension block and mock doesn't appear to throw the exception
    # there.  So this is a bit of a cheat, but it works
    with mock.patch("builtins.sum", side_effect=OSError()):
        assert pc.size(exclude=True, lazy=False) == 0
        assert pc.size(exclude=False, lazy=False) == 0

    pc = PersistentStore(namespace=namespace, path=str(tmpdir))
    with mock.patch("glob.glob", side_effect=OSError()):
        assert pc.files(exclude=True, lazy=False) == []
        assert pc.files(exclude=False, lazy=False) == []

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir), mode=PersistentStoreMode.FLUSH
    )

    # Causes an initialization
    pc["abc"] = 1
    with mock.patch("os.unlink", side_effect=OSError()):
        # Now we can't set data
        with pytest.raises(KeyError):
            pc["new-key"] = "value"
        # However keys that alrady exist don't get caught in check
        # and therefore won't throw
        pc["abc"] = "value"

    #
    # Handles flush() when the queue is empty
    #
    pc.clear()
    with mock.patch("os.unlink", side_effect=OSError()):
        # We can't remove backup cache file
        assert pc.flush(force=True) is False

    with mock.patch("os.unlink", side_effect=FileNotFoundError()):
        # FileNotFound is not an issue
        assert pc.flush(force=True) is True

    with mock.patch("os.rename", side_effect=OSError()):
        # We can't create a backup
        assert pc.flush(force=True) is False

    with mock.patch("os.rename", side_effect=FileNotFoundError()):
        # FileNotFound is not an issue
        assert pc.flush(force=True) is True

    # Flush any previous cache and data
    pc.delete()

    #
    # Handles flush() cases where is data to write
    #

    # Create a key
    pc.set("abc", "a-test-value")
    with mock.patch("os.unlink", side_effect=(OSError(), None)):
        # We failed to move our content in place
        assert pc.flush(force=True) is False

    with mock.patch("os.unlink", side_effect=(OSError(), FileNotFoundError())):
        # We failed to move our content in place
        assert pc.flush(force=True) is False

    with mock.patch("os.unlink", side_effect=(OSError(), OSError())):
        # We failed to move our content in place
        assert pc.flush(force=True) is False


def test_persistent_custom_io(tmpdir):
    """Test reading and writing custom files."""

    # Initialize it for memory only
    pc = PersistentStore(path=str(tmpdir))

    with pytest.raises(AttributeError):
        pc.open("!invalid#-Key")

    # We can't open the file as it does not exist
    with pytest.raises(FileNotFoundError):
        pc.open("valid-key")

    with pytest.raises(AttributeError):
        # Bad data
        pc.open(1234)

    with pytest.raises(FileNotFoundError), pc.open("key") as fd:
        pass

    # Also can be caught using Apprise Exception Handling
    with pytest.raises(exception.AppriseFileNotFound), pc.open("key") as fd:
        pass

    # Write some valid data
    with pc.open("new-key", "wb") as fd:
        fd.write(b"data")

    with mock.patch(
        "builtins.open",
        new_callable=mock.mock_open,
        read_data="mocked file content",
    ) as mock_file:
        mock_file.side_effect = OSError
        with (
            pytest.raises(exception.AppriseDiskIOError),
            pc.open("new-key", compress=True) as fd,
        ):
            pass

    # Again but with compression this time
    with mock.patch(
        "gzip.open",
        new_callable=mock.mock_open,
        read_data="mocked file content",
    ) as mock_file:
        mock_file.side_effect = OSError
        with (
            pytest.raises(exception.AppriseDiskIOError),
            pc.open("new-key", compress=True) as fd,
        ):
            pass

    # Zlib error handling as well during open
    with mock.patch(
        "gzip.open",
        new_callable=mock.mock_open,
        read_data="mocked file content",
    ) as mock_file:
        mock_file.side_effect = zlib.error
        with (
            pytest.raises(exception.AppriseDiskIOError),
            pc.open("new-key", compress=True) as fd,
        ):
            pass

    # Writing
    with pytest.raises(AttributeError):
        pc.write(1234)

    with pytest.raises(AttributeError):
        pc.write(None)

    with pytest.raises(AttributeError):
        pc.write(True)

    pc = PersistentStore(str(tmpdir))
    with pc.open("key", "wb") as fd:
        fd.write(b"test")
        fd.close()

    # Handle error capuring when failing to write to disk
    with mock.patch(
        "gzip.open",
        new_callable=mock.mock_open,
        read_data="mocked file content",
    ) as mock_file:
        mock_file.side_effect = zlib.error

        # We fail to write to disk
        assert pc.write(b"test") is False

        # We support other errors too
        mock_file.side_effect = OSError
        assert pc.write(b"test") is False

    with pytest.raises(AttributeError):
        pc.write(b"data", key="!invalid#-Key")

    pc.delete()
    with mock.patch("os.unlink", side_effect=OSError()):
        # Write our data and the __move() will fail under the hood
        assert pc.write(b"test") is False

    pc.delete()
    with mock.patch("os.rename", side_effect=OSError()):
        # Write our data and the __move() will fail under the hood
        assert pc.write(b"test") is False

    pc.delete()
    with mock.patch("os.unlink", side_effect=(OSError(), FileNotFoundError())):
        # Write our data and the __move() will fail under the hood
        assert pc.write(b"test") is False

    pc.delete()
    with mock.patch("os.unlink", side_effect=(OSError(), None)):
        # Write our data and the __move() will fail under the hood
        assert pc.write(b"test") is False

    pc.delete()
    with mock.patch("os.unlink", side_effect=(OSError(), OSError())):
        # Write our data and the __move() will fail under the hood
        assert pc.write(b"test") is False

    pc.delete()
    with mock.patch("os.rename", side_effect=(None, OSError(), None)):
        assert pc.write(b"test") is False

    with mock.patch("os.rename", side_effect=(None, OSError(), OSError())):
        assert pc.write(b"test") is False

    with mock.patch(
        "os.rename", side_effect=(None, OSError(), FileNotFoundError())
    ):
        assert pc.write(b"test") is False

    pc.delete()
    with mock.patch("os.rename", side_effect=(None, None, None, OSError())):
        # not enough reason to fail
        assert pc.write(b"test") is True

    with (
        mock.patch("os.stat", side_effect=OSError()),
        mock.patch("os.close", side_effect=(None, OSError())),
    ):
        assert pc.write(b"test") is False

    pc.delete()
    with mock.patch(
        "tempfile._TemporaryFileWrapper.close", side_effect=OSError()
    ):
        assert pc.write(b"test") is False

    pc.delete()
    with (
        mock.patch(
            "tempfile._TemporaryFileWrapper.close",
            side_effect=(OSError(), None),
        ),
        mock.patch("os.unlink", side_effect=OSError()),
    ):
        assert pc.write(b"test") is False

    pc.delete()
    with (
        mock.patch(
            "tempfile._TemporaryFileWrapper.close",
            side_effect=(OSError(), None),
        ),
        mock.patch("os.unlink", side_effect=FileNotFoundError()),
    ):
        assert pc.write(b"test") is False


def test_persistent_storage_cache_object(tmpdir):
    """General testing of a CacheObject."""
    # A cache object
    c = CacheObject(123)

    ref = datetime.now(tz=timezone.utc)
    expires = ref + timedelta(days=1)
    # Create a cache object that expires tomorrow
    c = CacheObject("abcd", expires=expires)
    assert c.expires == expires
    assert c.expires_sec > 86390.0 and c.expires_sec <= 86400.0
    assert bool(c) is True
    assert "never" not in str(c)
    assert "str:+:abcd" in str(c)

    #
    # Testing CacheObject.set()
    #
    c.set(123)
    assert "never" not in str(c)
    assert "int:+:123" in str(c)
    hash_value = c.hash()
    assert isinstance(hash_value, str)

    c.set(124)
    assert "never" not in str(c)
    assert "int:+:124" in str(c)
    assert c.hash() != hash_value

    c.set(123)
    # sha is the same again if we set the value back
    assert c.hash() == hash_value

    c.set(124)
    assert isinstance(c.hash(), str)
    assert c.value == 124
    assert bool(c) is True
    c.set(124, expires=False, persistent=False)
    assert bool(c) is True
    assert c.expires is None
    assert c.expires_sec is None
    c.set(124, expires=True)
    # we're expired now
    assert bool(c) is False

    #
    # Testing CacheObject equality (==)
    #
    a = CacheObject("abc")
    b = CacheObject("abc")

    assert a == b
    assert a == "abc"
    assert b == "abc"

    # Equality is no longer a thing
    b = CacheObject("abc", 30)
    assert a != b
    # however we can look at the value inside
    assert a == b.value

    b = CacheObject("abc", persistent=False)
    a = CacheObject("abc", persistent=True)
    # Persistent flag matters
    assert a != b
    # however we can look at the value inside
    assert a == b.value
    b = CacheObject("abc", persistent=True)
    assert a == b

    # Epoch
    EPOCH = datetime(1970, 1, 1)

    # test all of our supported types (also test time naive and aware times)
    for entry in (
        "string",
        123,
        1.2222,
        datetime.now(),
        datetime.now(tz=timezone.utc),
        None,
        False,
        True,
        b"\0",
    ):
        # Create a cache object that expires tomorrow
        c = CacheObject(entry, datetime.now() + timedelta(days=1))

        # Verify our content hasn't expired
        assert c

        # Verify we can dump our object
        result = json.loads(
            json.dumps(c, separators=(",", ":"), cls=CacheJSONEncoder)
        )

        # Instantiate our object
        cc = CacheObject.instantiate(result)
        assert cc.json() == c.json()

    # Test our JSON Encoder against items we don't support
    with pytest.raises(TypeError):
        json.loads(
            json.dumps(object(), separators=(",", ":"), cls=CacheJSONEncoder)
        )

    assert CacheObject.instantiate(None) is None
    assert CacheObject.instantiate({}) is None

    # Bad data
    assert (
        CacheObject.instantiate({"v": 123, "x": datetime.now(), "c": "int"})
        is None
    )

    # object type is not supported
    assert (
        CacheObject.instantiate({
            "v": 123,
            "x": (datetime.now() - EPOCH).total_seconds(),
            "c": object,
        })
        is None
    )

    obj = CacheObject.instantiate(
        {"v": 123, "x": (datetime.now() - EPOCH).total_seconds(), "c": "int"},
        verify=False,
    )
    assert isinstance(obj, CacheObject)
    assert obj.value == 123

    # no HASH and verify is set to true; our checksum will fail
    assert (
        CacheObject.instantiate(
            {
                "v": 123,
                "x": (datetime.now() - EPOCH).total_seconds(),
                "c": "int",
            },
            verify=True,
        )
        is None
    )

    # We can't instantiate our object if the expiry value is bad
    assert (
        CacheObject.instantiate(
            {"v": 123, "x": "garbage", "c": "int"}, verify=False
        )
        is None
    )

    # We need a valid hash sum too
    assert (
        CacheObject.instantiate(
            {
                "v": 123,
                "x": (datetime.now() - EPOCH).total_seconds(),
                "c": "int",
                # Expecting a valid sha string
                "!": 1.0,
            },
            verify=False,
        )
        is None
    )

    # Our Bytes Object with corruption
    assert (
        CacheObject.instantiate(
            {
                "v": "garbage",
                "x": (datetime.now() - EPOCH).total_seconds(),
                "c": "bytes",
            },
            verify=False,
        )
        is None
    )

    obj = CacheObject.instantiate(
        {
            "v": "AA==",
            "x": (datetime.now() - EPOCH).total_seconds(),
            "c": "bytes",
        },
        verify=False,
    )
    assert isinstance(obj, CacheObject)
    assert obj.value == b"\0"

    # Test our datetime objects
    obj = CacheObject.instantiate(
        {
            "v": "2024-06-08T01:50:01.587267",
            "x": (datetime.now() - EPOCH).total_seconds(),
            "c": "datetime",
        },
        verify=False,
    )
    assert isinstance(obj, CacheObject)
    assert obj.value == datetime(2024, 6, 8, 1, 50, 1, 587267)

    # A corrupt datetime object
    assert (
        CacheObject.instantiate(
            {
                "v": "garbage",
                "x": (datetime.now() - EPOCH).total_seconds(),
                "c": "datetime",
            },
            verify=False,
        )
        is None
    )


@pytest.mark.skipif(
    sys.platform == "win32", reason="Unreliable results to be determined"
)
def test_persistent_storage_disk_prune(tmpdir):
    """General testing of a Persistent Store prune calls."""

    # Persistent Storage Initialization
    pc = PersistentStore(
        path=str(tmpdir), namespace="t01", mode=PersistentStoreMode.FLUSH
    )
    # Store some data
    assert pc.write(b"data-t01") is True
    assert pc.set("key-t01", "value")

    pc = PersistentStore(
        path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
    )
    # Store some data
    assert pc.write(b"data-t02") is True
    assert pc.set("key-t02", "value")

    # purne anything older then 30s
    results = PersistentStore.disk_prune(path=str(tmpdir), expires=30)
    # Nothing is older then 30s right now
    assert isinstance(results, dict)
    assert "t01" in results
    assert "t02" in results
    assert len(results["t01"]) == 0
    assert len(results["t02"]) == 0

    pc = PersistentStore(
        path=str(tmpdir), namespace="t01", mode=PersistentStoreMode.FLUSH
    )

    # Nothing is pruned
    assert pc.get("key-t01") == "value"
    assert pc.read() == b"data-t01"

    # An expiry of zero gets everything
    # Note: This test randomly fails in Microsoft Windows for unknown reasons
    # When this is determined, this test can be opened back up
    results = PersistentStore.disk_prune(path=str(tmpdir), expires=0)
    # We match everything now
    assert isinstance(results, dict)
    assert "t01" in results
    assert "t02" in results
    assert len(results["t01"]) == 2
    assert len(results["t02"]) == 2

    # Content is still not removed however because no action was put in place
    pc = PersistentStore(
        path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
    )
    # Nothing is pruned
    assert pc.get("key-t02") == "value"
    assert pc.read() == b"data-t02"
    pc = PersistentStore(
        path=str(tmpdir), namespace="t01", mode=PersistentStoreMode.FLUSH
    )
    # Nothing is pruned
    assert pc.get("key-t01") == "value"
    assert pc.read() == b"data-t01"

    with mock.patch("os.listdir", side_effect=OSError()):
        results = PersistentStore.disk_scan(
            namespace="t01", path=str(tmpdir), closest=True
        )
        assert isinstance(results, list)
        assert len(results) == 0

    with mock.patch("os.listdir", side_effect=FileNotFoundError()):
        results = PersistentStore.disk_scan(
            namespace="t01", path=str(tmpdir), closest=True
        )
        assert isinstance(results, list)
        assert len(results) == 0

        # Without closest flag
        results = PersistentStore.disk_scan(
            namespace="t01", path=str(tmpdir), closest=False
        )
        assert isinstance(results, list)
        assert len(results) == 0

    # Now we'll filter on specific namespaces
    results = PersistentStore.disk_prune(
        namespace="notfound", path=str(tmpdir), expires=0, action=True
    )

    # nothing matched, nothing found
    assert isinstance(results, dict)
    assert len(results) == 0

    results = PersistentStore.disk_prune(
        namespace=("t01", "invalid", "-garbag!"),
        path=str(tmpdir),
        expires=0,
        action=True,
    )

    # only t01 would be cleaned now
    assert isinstance(results, dict)
    assert len(results) == 1
    assert len(results["t01"]) == 2

    # A second call will yield no results because the content has
    # already been cleaned up
    results = PersistentStore.disk_prune(
        namespace="t01", path=str(tmpdir), expires=0, action=True
    )
    assert isinstance(results, dict)
    assert len(results) == 0

    # t02 is still untouched
    pc = PersistentStore(
        path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
    )
    # Nothing is pruned
    assert pc.get("key-t02") == "value"
    assert pc.read() == b"data-t02"

    # t01 of course... it's gone
    pc = PersistentStore(
        path=str(tmpdir), namespace="t01", mode=PersistentStoreMode.FLUSH
    )
    # Nothing is pruned
    assert pc.get("key-t01") is None
    assert pc.read() is None

    with pytest.raises(AttributeError):
        # provide garbage in namespace field and we're going to have a problem
        PersistentStore.disk_prune(
            namespace=object, path=str(tmpdir), expires=0, action=True
        )

    # Error Handling
    with mock.patch("os.path.getmtime", side_effect=FileNotFoundError()):
        results = PersistentStore.disk_prune(
            namespace="t02", path=str(tmpdir), expires=0, action=True
        )
        assert isinstance(results, dict)
        assert len(results) == 1
        assert len(results["t02"]) == 0

        # no files were removed, so our data is still accessible
        pc = PersistentStore(
            path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
        )
        # Nothing is pruned
        assert pc.get("key-t02") == "value"
        assert pc.read() == b"data-t02"

    with mock.patch("os.path.getmtime", side_effect=OSError()):
        results = PersistentStore.disk_prune(
            namespace="t02", path=str(tmpdir), expires=0, action=True
        )
        assert isinstance(results, dict)
        assert len(results) == 1
        assert len(results["t02"]) == 0

        # no files were removed, so our data is still accessible
        pc = PersistentStore(
            path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
        )
        # Nothing is pruned
        assert pc.get("key-t02") == "value"
        assert pc.read() == b"data-t02"

    with mock.patch("os.unlink", side_effect=FileNotFoundError()):
        results = PersistentStore.disk_prune(
            namespace="t02", path=str(tmpdir), expires=0, action=True
        )
        assert isinstance(results, dict)
        assert len(results) == 1
        assert len(results["t02"]) == 2

        # no files were removed, so our data is still accessible
        pc = PersistentStore(
            path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
        )
        # Nothing is pruned
        assert pc.get("key-t02") == "value"
        assert pc.read() == b"data-t02"

    with mock.patch("os.unlink", side_effect=OSError()):
        results = PersistentStore.disk_prune(
            namespace="t02", path=str(tmpdir), expires=0, action=True
        )
        assert isinstance(results, dict)
        assert len(results) == 1
        assert len(results["t02"]) == 2

        # no files were removed, so our data is still accessible
        pc = PersistentStore(
            path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
        )
        # Nothing is pruned
        assert pc.get("key-t02") == "value"
        assert pc.read() == b"data-t02"

    with mock.patch("os.rmdir", side_effect=OSError()):
        results = PersistentStore.disk_prune(
            namespace="t02", path=str(tmpdir), expires=0, action=True
        )
        assert isinstance(results, dict)
        assert len(results) == 1
        assert len(results["t02"]) == 2

        # no files were removed, so our data is still accessible
        pc = PersistentStore(
            path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
        )
        # Nothing is pruned
        assert pc.get("key-t02") is None
        assert pc.read() is None


def test_persistent_storage_disk_changes(tmpdir):
    """General testing of a Persistent Store with underlining disk changes."""

    # Create a garbage file in place of where the namespace should be
    tmpdir.join("t01").write("0" * 1024)

    # Persistent Storage Initialization where namespace directory now is
    # already occupied by a filename
    pc = PersistentStore(
        path=str(tmpdir), namespace="t01", mode=PersistentStoreMode.FLUSH
    )

    # Store some data and note that it isn't possible
    assert pc.write(b"data-t01") is False
    # We actually fell back to memory mode:
    assert pc.mode == PersistentStoreMode.MEMORY

    # Set's work
    assert pc.set("key-t01", "value")

    # But upon reinitializtion (enforcing memory mode check) we will not have
    # the data available to us
    pc = PersistentStore(
        path=str(tmpdir), namespace="t01", mode=PersistentStoreMode.FLUSH
    )

    assert pc.get("key-t01") is None

    #
    # Test situation where the file structure changed after initialization
    #
    pc = PersistentStore(
        path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
    )
    # Our mode stuck as t02 initialized correctly
    assert pc.mode == PersistentStoreMode.FLUSH
    assert os.path.isdir(pc.path)

    shutil.rmtree(pc.path)
    assert not os.path.isdir(pc.path)
    assert pc.set("key-t02", "value")
    # The directory got re-created
    assert os.path.isdir(pc.path)

    # Same test but flag set to AUTO
    pc = PersistentStore(
        path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.AUTO
    )
    # Our mode stuck as t02 initialized correctly
    assert pc.mode == PersistentStoreMode.AUTO
    assert os.path.isdir(pc.path)

    shutil.rmtree(pc.path)
    assert not os.path.isdir(pc.path)
    assert pc.set("key-t02", "value")
    # The directory is not recreated because of auto; it will occur on save
    assert not os.path.isdir(pc.path)
    path = pc.path
    del pc
    # It exists now
    assert os.path.isdir(path)

    pc = PersistentStore(
        path=str(tmpdir), namespace="t02", mode=PersistentStoreMode.FLUSH
    )
    # Content was not lost
    assert pc.get("key-t02") == "value"

    # We'll remove a sub directory of it this time
    shutil.rmtree(os.path.join(pc.path, pc.temp_dir))

    # We will still successfully write our data
    assert pc.write(b"data-t02") is True
    assert os.path.isdir(pc.path)

    shutil.rmtree(pc.path)
    assert not os.path.isdir(pc.path)
    assert pc.set("key-t01", "value")
