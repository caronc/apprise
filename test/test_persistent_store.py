# -*- coding: utf-8 -*-
# BSD 2-Clause License
#
# Apprise - Push Notification Library.
# Copyright (c) 2024, Chris Caron <lead2gold@gmail.com>
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

import os
import pytest
import json
import gzip
from unittest import mock
from datetime import datetime, timedelta, timezone
from apprise.asset import AppriseAsset
from apprise.persistent_store import (
    CacheJSONEncoder, CacheObject, PersistentStore, PersistentStoreMode)

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')


def test_persistent_storage_asset(tmpdir):
    """
    Tests the Apprise Asset Object when setting the Persistent Store
    """

    asset = AppriseAsset(storage_path=str(tmpdir))
    assert asset.storage_path == str(tmpdir)
    assert asset.storage_mode is PersistentStoreMode.AUTO

    # If there is no storage path, we're always set to memory
    asset = AppriseAsset(
        storage_path=None, storage_mode=PersistentStoreMode.MEMORY)
    assert asset.storage_path is None
    assert asset.storage_mode is PersistentStoreMode.MEMORY


def test_disabled_persistent_storage(tmpdir):
    """
    Persistent Storage General Testing

    """
    # Create ourselves an attachment object set in Memory Mode only
    pc = PersistentStore(
        namespace='abc', path=str(tmpdir), mode=PersistentStoreMode.MEMORY)
    assert pc.read() is None
    assert pc.read('mykey') is None
    with pytest.raises(AttributeError):
        # Invalid key specified
        pc.read('!invalid')
    assert pc.write('data') is False
    assert pc.get('key') is None
    assert pc.set('key', 'value')
    assert pc.get('key') == 'value'

    # After all of the above, nothing was done to the directory
    assert len(os.listdir(str(tmpdir))) == 0

    with pytest.raises(AttributeError):
        # invalid persistent store specified
        PersistentStore(
            namespace='abc', path=str(tmpdir), mode='garbage')


def test_persistent_storage_init(tmpdir):
    """
    Test storage initialization
    """
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
    """
    Persistent Storage General Testing

    """
    namespace = 'abc'
    # Create ourselves an attachment object
    pc = PersistentStore()

    # Default mode when a path is not provided
    assert pc.mode == PersistentStoreMode.MEMORY

    # Create ourselves an attachment object
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir))

    # Default mode when a path is provided
    assert pc.mode == PersistentStoreMode.AUTO

    # Get our path associated with our Persistent Store
    assert pc.path == os.path.join(str(tmpdir), 'abc')

    # Expiry testing
    assert pc.set('key', 'value', datetime.now() + timedelta(hours=1))
    # i min in the future
    assert pc.set('key', 'value', 60)

    with pytest.raises(AttributeError):
        assert pc.set('key', 'value', 'invalid')

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir))

    # Our key is still valid and we load it from disk
    assert pc.get('key') == 'value'
    assert pc['key'] == 'value'

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir))

    with pytest.raises(KeyError):
        # The below
        pc['unassigned_key']


def test_persistent_storage_flush_mode(tmpdir):
    """
    Persistent Storage Forced Write Testing

    """
    namespace = 'abc'
    # Create ourselves an attachment object
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir),
        mode=PersistentStoreMode.FLUSH)

    # Reference path
    path = os.path.join(str(tmpdir), namespace)

    assert pc.size() == 0
    assert list(pc.files()) == []

    # Key is not set yet
    assert pc.get('key') is None
    assert len(pc.keys()) == 0
    assert 'key' not in pc

    # Verify our data is set
    assert pc.set('key', 'value')
    assert len(pc.keys()) == 1
    assert 'key' in list(pc.keys())

    assert pc.size() > 0
    assert len(pc.files()) == 1

    # Second call uses Lazy cache
    # Just our cache file
    assert len(pc.files()) == 1

    # Setting the same value again uses a lazy mode and
    # bypasses all of the write overhead
    assert pc.set('key', 'value')

    path_content = os.listdir(path)
    # var, cache.psdata, and .tmp
    assert len(path_content) == 3

    # Assignments (causes another disk write)
    pc['key'] = 'value2'

    # Setting the same value and explictly marking the field as not being
    # perisistent
    pc.set('key-xx', 'abc123', persistent=False)
    # Changing it's value doesn't alter the persistent flag
    pc['key-xx'] = 'def678'
    # Setting it twice
    pc['key-xx'] = 'def678'

    # Our retrievals
    assert pc['key-xx'] == 'def678'
    assert pc.get('key-xx') == 'def678'

    # But on the destruction of our object, it is not available again
    del pc
    # Create ourselves an attachment object
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir),
        mode=PersistentStoreMode.FLUSH)

    assert pc.get('key-xx') is None
    with pytest.raises(KeyError):
        pc['key-xx']

    # Now our key is set
    assert 'key' in pc
    assert pc.get('key') == 'value2'

    # A directory was created identified by the namespace
    assert len(os.listdir(str(tmpdir))) == 1
    assert namespace in os.listdir(str(tmpdir))

    path_content = os.listdir(path)
    assert len(path_content) == 4

    # Another write doesn't change the file count
    pc['key'] = 'value3'
    path_content = os.listdir(path)
    assert len(path_content) == 4

    # Our temporary directory used for all file handling in this namespace
    assert '.tmp' in path_content
    # Our cache file
    assert os.path.basename(pc.cache_file) in path_content

    path = os.path.join(pc.path, '.tmp')
    path_content = os.listdir(path)

    # We always do our best to clean any temporary files up
    assert len(path_content) == 0

    # Destroy our object
    del pc

    # Re-initialize it
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir),
        mode=PersistentStoreMode.FLUSH)

    # Our key is persistent and available right away
    assert pc.get('key') == 'value3'
    assert 'key' in pc

    # Remove our item
    del pc['key']
    assert pc.size() == 0
    assert 'key' not in pc

    assert pc.write('data') is True
    assert pc.read() == b'data'
    assert pc.write(b'data') is True
    assert pc.read() == b'data'

    assert pc.read('default') == b'data'
    assert pc.write('data2', key='mykey') is True
    assert pc.read('mykey') == b'data2'

    # We can selectively delete our key
    assert pc.delete('mykey')
    assert pc.read('mykey') is None
    # Other keys are not touched
    assert pc.read('default') == b'data'
    assert pc.read() == b'data'
    # Full purge
    assert pc.delete()
    assert pc.read('mykey') is None
    assert pc.read() is None

    # Practice with files
    with open(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'), 'rb') as fd:
        assert pc.write(fd, key='mykey', compress=False) is True

        # Read our content back
        fd.seek(0)
        assert pc.read('mykey', compress=False) == fd.read()

    with open(os.path.join(TEST_VAR_DIR, 'apprise-test.gif'), 'rb') as fd:
        assert pc.write(fd, key='mykey', compress=True) is True

        # Read our content back; content will be compressed
        fd.seek(0)
        assert pc.read('mykey', compress=True) == fd.read()

    class Foobar:
        def read(*args, **kwargs):
            return 42

    foobar = Foobar()
    # read() returns a non string/bin
    with pytest.raises(AttributeError):
        pc.write(foobar, key='foobar', compress=True)
    assert pc.read('foobar') is None

    class Foobar:
        def read(*args, **kwargs):
            return 'good'

    foobar = Foobar()
    # read() returns a string so the below write works
    assert pc.write(foobar, key='foobar', compress=True)
    assert pc.read('foobar') == b'good'
    pc.delete()

    class Foobar:
        def read(*args, **kwargs):
            # Throw an exception
            raise TypeError()

    foobar = Foobar()
    # read() returns a non string/bin
    with pytest.raises(AttributeError):
        pc.write(foobar, key='foobar', compress=True)
    assert pc.read('foobar') is None

    # Set our max_file_size
    _prev_max_file_size = pc.max_file_size
    pc.max_file_size = 1
    assert pc.delete()

    assert pc.write('data') is False
    assert pc.read() is None

    # Restore setting
    pc.max_file_size = _prev_max_file_size


def test_persistent_storage_corruption_handling(tmpdir):
    """
    Test corrupting handling of storage
    """

    # Namespace
    namespace = 'def456'

    # Initialize it
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir),
        mode=PersistentStoreMode.FLUSH)

    cache_file = pc.cache_file
    assert not os.path.isfile(cache_file)

    # Store our key
    pc['mykey'] = 42
    assert os.path.isfile(cache_file)

    with gzip.open(cache_file, 'rb') as f:
        # Read our content from disk
        json.loads(f.read().decode('utf-8'))

    # Remove object
    del pc

    # Corrupt the file
    with open(cache_file, 'wb') as f:
        f.write(b'{')

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir),
        mode=PersistentStoreMode.FLUSH)

    # File is corrupted
    assert 'mykey' not in pc
    pc['mykey'] = 42
    del pc

    # File is corrected now
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir),
        mode=PersistentStoreMode.FLUSH)

    assert 'mykey' in pc

    # Corrupt the file again
    with gzip.open(cache_file, 'wb') as f:
        # Bad JSON File
        f.write(b'{')

    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir),
        mode=PersistentStoreMode.FLUSH)

    # File is corrupted
    assert 'mykey' not in pc
    pc['mykey'] = 42
    del pc

    with mock.patch('os.makedirs', side_effect=OSError()):
        pc = PersistentStore(
            namespace=namespace, path=str(tmpdir),
            mode=PersistentStoreMode.FLUSH)

        # Directory initialization failed so we fall back to memory mode
        assert pc.mode == PersistentStoreMode.MEMORY

    # directory initialization okay
    pc = PersistentStore(
        namespace=namespace, path=str(tmpdir),
        mode=PersistentStoreMode.FLUSH)

    assert 'mykey' in pc

    # Remove the last entry
    del pc['mykey']
    with mock.patch('os.rename', side_effect=OSError()):
        with mock.patch('os.unlink', side_effect=OSError()):
            assert not pc.flush(force=True)

    # Create another entry
    pc['mykey'] = 42
    with mock.patch('tempfile.NamedTemporaryFile', side_effect=OSError()):
        assert not pc.flush(force=True)

    # Temporary file cleanup failure
    with mock.patch('tempfile._TemporaryFileWrapper.close',
                    side_effect=OSError()):
        assert not pc.flush(force=True)

    with mock.patch('tempfile._TemporaryFileWrapper.close',
                    side_effect=(OSError(), None)):
        with mock.patch('os.unlink', side_effect=(OSError())):
            assert not pc.flush(force=True)

    del pc


def test_persistent_storage_cache_io_errors(tmpdir):
    """
    Test persistent storage when there is a variety of disk issues
    """

    # Namespace
    namespace = 'abc123'

    with mock.patch('gzip.open', side_effect=OSError()):
        pc = PersistentStore(namespace=namespace, path=str(tmpdir))

        # Falls to default
        assert pc.get('key') is None

        with pytest.raises(KeyError):
            pc['key']


def test_persistent_custom_io(tmpdir):
    """
    Test reading and writing custom files
    """

    # Initialize it for memory only
    pc = PersistentStore()

    with pytest.raises(AttributeError):
        pc.open('!invalid#-Key')

    # We can't open the file as it does not exist
    with pytest.raises(FileNotFoundError):
        pc.open('valid-key')

    with pytest.raises(AttributeError):
        # Bad data
        pc.open(1234)

    with pytest.raises(FileNotFoundError):
        with pc.open('key') as fd:
            pass

    with pytest.raises(AttributeError):
        pc.write(1234)

    with pytest.raises(AttributeError):
        pc.write(None)

    with pytest.raises(AttributeError):
        pc.write(True)

    pc = PersistentStore(str(tmpdir))
    with pc.open('key', 'wb') as fd:
        fd.write(b'test')
        fd.close()


def test_persistent_storage_cache_object(tmpdir):
    """
    General testing of a CacheObject
    """
    # A cache object
    c = CacheObject(123)

    ref = datetime.now(tz=timezone.utc)
    expires = ref + timedelta(days=1)
    # Create a cache object that expires tomorrow
    c = CacheObject('abcd', expires=expires)
    assert c.expires == expires
    assert c.expires_sec > 86390.0 and c.expires_sec <= 86400.0
    assert bool(c) is True
    assert 'never' not in str(c)
    assert 'str:+:abcd' in str(c)

    #
    # Testing CacheObject.set()
    #
    c.set(123)
    assert 'never' not in str(c)
    assert 'int:+:123' in str(c)
    sha1 = c.sha1()
    assert isinstance(sha1, str)

    c.set(124)
    assert 'never' not in str(c)
    assert 'int:+:124' in str(c)
    assert c.sha1() != sha1

    c.set(123)
    # sha is the same again if we set the value back
    assert c.sha1() == sha1

    c.set(124)
    assert isinstance(c.sha1(), str)
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
    a = CacheObject('abc')
    b = CacheObject('abc')

    assert a == b
    assert a == 'abc'
    assert b == 'abc'

    # Equality is no longer a thing
    b = CacheObject('abc', 30)
    assert a != b
    # however we can look at the value inside
    assert a == b.value

    b = CacheObject('abc', persistent=False)
    a = CacheObject('abc', persistent=True)
    # Persistent flag matters
    assert a != b
    # however we can look at the value inside
    assert a == b.value
    b = CacheObject('abc', persistent=True)
    assert a == b

    # Epoch
    EPOCH = datetime(1970, 1, 1)

    # test all of our supported types (also test time naive and aware times)
    for entry in ('string', 123, 1.2222, datetime.now(),
                  datetime.now(tz=timezone.utc), None, False, True, b'\0'):
        # Create a cache object that expires tomorrow
        c = CacheObject(entry, datetime.now() + timedelta(days=1))

        # Verify our content hasn't expired
        assert c

        # Verify we can dump our object
        result = json.loads(json.dumps(
            c, separators=(',', ':'), cls=CacheJSONEncoder))

        # Instantiate our object
        cc = CacheObject.instantiate(result)
        assert cc.json() == c.json()

    # Test our JSON Encoder against items we don't support
    with pytest.raises(TypeError):
        json.loads(json.dumps(
            object(), separators=(',', ':'), cls=CacheJSONEncoder))

    assert CacheObject.instantiate(None) is None
    assert CacheObject.instantiate({}) is None

    # Bad data
    assert CacheObject.instantiate({
        'v': 123,
        'x': datetime.now(),
        'c': 'int'}) is None

    # object type is not supported
    assert CacheObject.instantiate({
        'v': 123,
        'x': (datetime.now() - EPOCH).total_seconds(),
        'c': object}) is None

    obj = CacheObject.instantiate({
        'v': 123,
        'x': (datetime.now() - EPOCH).total_seconds(),
        'c': 'int'}, verify=False)
    assert isinstance(obj, CacheObject)
    assert obj.value == 123

    # no SHA1SUM and verify is set to true; our checksum will fail
    assert CacheObject.instantiate({
        'v': 123,
        'x': (datetime.now() - EPOCH).total_seconds(),
        'c': 'int'}, verify=True) is None

    # We can't instantiate our object if the expiry value is bad
    assert CacheObject.instantiate({
        'v': 123,
        'x': 'garbage',
        'c': 'int'}, verify=False) is None

    # We need a valid sha1 sum too
    assert CacheObject.instantiate({
        'v': 123,
        'x': (datetime.now() - EPOCH).total_seconds(),
        'c': 'int',
        # Expecting a valid sha string
        '!': 1.0}, verify=False) is None

    # Our Bytes Object with corruption
    assert CacheObject.instantiate({
        'v': 'garbage',
        'x': (datetime.now() - EPOCH).total_seconds(),
        'c': 'bytes'}, verify=False) is None

    obj = CacheObject.instantiate({
        'v': 'AA==',
        'x': (datetime.now() - EPOCH).total_seconds(),
        'c': 'bytes'}, verify=False)
    assert isinstance(obj, CacheObject)
    assert obj.value == b'\0'

    # Test our datetime objects
    obj = CacheObject.instantiate({
        'v': '2024-06-08T01:50:01.587267',
        'x': (datetime.now() - EPOCH).total_seconds(),
        'c': 'datetime'}, verify=False)
    assert isinstance(obj, CacheObject)
    assert obj.value == datetime(2024, 6, 8, 1, 50, 1, 587267)

    # A corrupt datetime object
    assert CacheObject.instantiate({
        'v': 'garbage',
        'x': (datetime.now() - EPOCH).total_seconds(),
        'c': 'datetime'}, verify=False) is None
