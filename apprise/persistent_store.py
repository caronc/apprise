# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import os
import re
import gzip
import zlib
import base64
import glob
import tempfile
import json
import binascii
from datetime import datetime, timezone, timedelta
import hashlib
from .common import PersistentStoreMode, PERSISTENT_STORE_MODES
from .utils import path_decode
from .logger import logger

# Used for writing/reading time stored in cache file
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

# isoformat is spelled out for compatibility with Python v3.6
AWARE_DATE_ISO_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'
NAIVE_DATE_ISO_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'


class CacheObject:

    def __init__(self, value=None, expires=False, persistent=True):
        """
        Tracks our objects and associates a time limit with them
        """

        self.__value = value
        self.__class_name = value.__class__.__name__
        self.__expires = None

        if expires:
            self.set_expiry(expires)

        # Whether or not we persist this object to disk or not
        self.__persistent = True if persistent else False

    def set(self, value, expires=None, persistent=None):
        """
        Sets fields on demand, if set to none, then they are left as is

        The intent of set is that it allows you to set a new a value
        and optionally alter meta information against it.

        If expires or persistent isn't specified then their previous values
        are used.

        """

        self.__value = value
        self.__class_name = value.__class__.__name__
        if expires is not None:
            self.set_expiry(expires)

        if persistent is not None:
            self.__persistent = True if persistent else False

    def set_expiry(self, expires=None):
        """
        Sets a new expirty
        """

        if isinstance(expires, datetime):
            self.__expires = expires.astimezone(timezone.utc)

        elif expires in (None, False):
            # Accepted - no expiry
            self.__expires = None

        elif expires is True:
            # Force expiry to now
            self.__expires = datetime.now(tz=timezone.utc)

        elif isinstance(expires, (float, int)):
            self.__expires = \
                datetime.now(tz=timezone.utc) + timedelta(seconds=expires)

        else:  # Unsupported
            raise AttributeError(
                f"An invalid expiry time ({expires} was specified")

    def sha1(self):
        """
        Our checksum to track the validity of our data
        """
        try:
            return hashlib.sha1(
                str(self).encode('utf-8'), usedforsecurity=False).hexdigest()

        except TypeError:
            # Python <= v3.8 - usedforsecurity flag does not work
            return hashlib.sha1(str(self).encode('utf-8')).hexdigest()

    def json(self):
        """
        Returns our preparable json object
        """

        return {
            'v': self.__value,
            'x': (self.__expires - EPOCH).total_seconds()
            if self.__expires else None,
            'c': self.__class_name if not isinstance(self.__value, datetime)
            else (
                'aware_datetime' if self.__value.tzinfo else 'naive_datetime'),
            '!': self.sha1()[:6],
        }

    @staticmethod
    def instantiate(content, persistent=True, verify=True):
        """
        Loads back data read in and returns a CacheObject or None if it could
        not be loaded. You can pass in the contents of CacheObject.json() and
        you'll receive a copy assuming the sha1 checks okay

        """
        try:
            value = content['v']
            expires = content['x']
            if expires is not None:
                expires = datetime.fromtimestamp(expires, timezone.utc)

            # Acquire some useful integrity objects
            class_name = content.get('c', '')
            if not isinstance(class_name, str):
                raise TypeError('Class name not expected string')

            sha1sum = content.get('!', '')
            if not isinstance(sha1sum, str):
                raise TypeError('SHA1SUM not expected string')

        except (TypeError, KeyError) as e:
            logger.trace(f'CacheObject could not be parsed from {content}')
            logger.trace('CacheObject exception: %s' % str(e))
            return None

        if class_name in ('aware_datetime', 'naive_datetime', 'datetime'):
            # If datetime is detected, it will fall under the naive category
            iso_format = AWARE_DATE_ISO_FORMAT \
                if class_name[0] == 'a' else NAIVE_DATE_ISO_FORMAT
            try:
                # Python v3.6 Support
                value = datetime.strptime(value, iso_format)

            except (TypeError, ValueError):
                # TypeError is thrown if content is not string
                # ValueError is thrown if the string is not a valid format
                logger.trace(
                    f'CacheObject (dt) corrupted loading from {content}')
                return None

        elif class_name == 'bytes':
            try:
                # Convert our object back to a bytes
                value = base64.b64decode(value)

            except binascii.Error:
                logger.trace(
                    f'CacheObject (bin) corrupted loading from {content}')
                return None

        # Initialize our object
        co = CacheObject(value, expires, persistent=persistent)
        if verify and co.sha1()[:6] != sha1sum:
            # Our object was tampered with
            logger.debug(f'Tampering detected with cache entry {co}')
            del co
            return None

        return co

    @property
    def value(self):
        """
        Returns our value
        """
        return self.__value

    @property
    def persistent(self):
        """
        Returns our persistent value
        """
        return self.__persistent

    @property
    def expires(self):
        """
        Returns the datetime the object will expire
        """
        return self.__expires

    @property
    def expires_sec(self):
        """
        Returns the number of seconds from now the object will expire
        """

        return None if self.__expires is None else max(
            0.0, (self.__expires - datetime.now(tz=timezone.utc))
            .total_seconds())

    def __bool__(self):
        """
        Returns True it the object hasn't expired, and False if it has
        """
        if self.__expires is None:
            # No Expiry
            return True

        # Calculate if we've expired or not
        return self.__expires > datetime.now(tz=timezone.utc)

    def __eq__(self, other):
        """
        Handles equality == flag
        """
        if isinstance(other, CacheObject):
            return str(self) == str(other)

        return self.__value == other

    def __str__(self):
        """
        string output of our data
        """
        persistent = '+' if self.persistent else '-'
        return f'{self.__class_name}:{persistent}:{self.__value} expires: ' +\
            ('never' if self.__expires is None
             else self.__expires.strftime(NAIVE_DATE_ISO_FORMAT))


class CacheJSONEncoder(json.JSONEncoder):
    """
    A JSON Encoder for handling each of our cache objects
    """

    def default(self, entry):
        if isinstance(entry, datetime):
            return entry.strftime(
                AWARE_DATE_ISO_FORMAT if entry.tzinfo is not None
                else NAIVE_DATE_ISO_FORMAT)

        elif isinstance(entry, CacheObject):
            return entry.json()

        elif isinstance(entry, bytes):
            return base64.b64encode(entry).decode('utf-8')

        return super().default(entry)


class PersistentStore:
    """
    An object to make working with persistent storage easier

    read() and write() are used for direct file i/o

    set(), get() are used for caching
    """

    # The maximum file-size we will allow the persistent store to grow to
    # 1 MB = 1048576 bytes
    max_file_size = 1048576

    # File encoding to use
    encoding = 'utf-8'

    # Default data set
    base_key = 'default'

    # Directory to store cache
    __cache_key = 'cache'

    # Our Temporary working directory
    temp_dir = 'tmp'

    # The directory our persistent store content gets placed in
    data_dir = 'var'

    # Our Persistent Store File Extension
    __extension = '.psdata'

    # Identify our backup file extension
    __backup_extension = '._psbak'

    # Used to verify the key specified is valid
    #  - must start with an alpha_numeric
    #  - following optional characters can include period, underscore and
    #    equal
    __valid_key = re.compile(r'[a-z0-9][a-z0-9._-]*', re.I)

    # Reference only
    __not_found_ref = (None, None)

    def __init__(self, path=None, namespace='default', mode=None):
        """
        Provide the namespace to work within. namespaces can only contain
        alpha-numeric characters with the exception of '-' (dash), '_'
        (underscore), and '.' (period). The namespace must be be relative
        to the current URL being controlled.
        """
        # Initalize our mode so __del__() calls don't go bad on the
        # error checking below
        self.__mode = None

        # Populated only once and after size() is called
        self.__exclude_list = None

        if not isinstance(namespace, str) \
                or not self.__valid_key.match(namespace):
            raise AttributeError(
                f"Persistent Storage namespace ({namespace}) provided is"
                " invalid")

        if isinstance(path, str):
            # A storage path has been defined
            if mode is None:
                # Store Default if no mode was provided along side of it
                mode = PERSISTENT_STORE_MODES[0]

            # Store our information
            self.__base_path = os.path.join(path_decode(path), namespace)
            self.__temp_path = os.path.join(self.__base_path, self.temp_dir)
            self.__data_path = os.path.join(self.__base_path, self.data_dir)

        else:  # If no storage path is provide we set our mode to MEMORY
            mode = PersistentStoreMode.MEMORY
            self.__base_path = None
            self.__temp_path = None
            self.__data_path = None

        if mode not in PERSISTENT_STORE_MODES:
            raise AttributeError(
                f"Persistent Storage mode ({mode}) provided is invalid")

        # Store our mode
        self.__mode = mode

        # Tracks when we have content to flush
        self.__dirty = False

        # A caching value to track persistent storage disk size
        self.__cache_size = None
        self.__cache_files = {}

        # Internal Cache
        self._cache = None

        if self.__mode != PersistentStoreMode.MEMORY:
            # Ensure our path exists
            try:
                os.makedirs(self.__base_path, mode=0o770, exist_ok=True)

            except (OSError, IOError) as e:
                # Permission error
                logger.debug(
                    'Could not create persistent store directory %s',
                    self.__base_path)
                logger.debug('Persistent Storage Exception: %s' % str(e))

                # Mode changed back to MEMORY
                self.__mode = PersistentStoreMode.MEMORY

            # Ensure our path exists
            try:
                os.makedirs(self.__temp_path, mode=0o770, exist_ok=True)

            except (OSError, IOError) as e:
                # Permission error
                logger.debug(
                    'Could not create persistent store directory %s',
                    self.__temp_path)
                logger.debug('Persistent Storage Exception: %s' % str(e))

                # Mode changed back to MEMORY
                self.__mode = PersistentStoreMode.MEMORY

            try:
                os.makedirs(self.__data_path, mode=0o770, exist_ok=True)

            except (OSError, IOError) as e:
                # Permission error
                logger.debug(
                    'Could not create persistent store directory %s',
                    self.__data_path)
                logger.debug('Persistent Storage Exception: %s' % str(e))

                # Mode changed back to MEMORY
                self.__mode = PersistentStoreMode.MEMORY

            if self.__mode is PersistentStoreMode.MEMORY:
                logger.warning(
                    'The persistent storage could not be initialized')

    def read(self, key=None, compress=True):
        """
        Returns the content of the persistent store object

        Content is always returned as a byte object
        """
        try:
            with self.open(key, mode="rb", compress=compress) as fd:
                return fd.read(self.max_file_size)

        except FileNotFoundError:
            # No problem
            pass

        except (OSError, zlib.error, EOFError, UnicodeDecodeError,
                IOError) as e:
            # We can't access the file or it does not exist
            logger.warning('Could not read with persistent key: %s', key)
            logger.debug('Persistent Storage Exception: %s' % str(e))

        # return none
        return None

    def write(self, data, key=None, compress=True):
        """
        Writes the content to the persistent store if it doesn't exceed our
        filesize limit.

        Content is always written as a byte object
        """

        if key is None:
            key = self.base_key

        elif not isinstance(key, str) or not self.__valid_key.match(key):
            raise AttributeError(
                f"Persistent Storage key ({key} provided is invalid")

        if not isinstance(data, (bytes, str)):
            # One last check, we will accept read() objets with the expectation
            # it will return a binary dataset
            if not (hasattr(data, 'read') and callable(getattr(data, 'read'))):
                raise AttributeError(
                    "Invalid data type {} provided to Persistent Storage"
                    .format(type(data)))

            try:
                # Read in our data
                data = data.read()
                if not isinstance(data, (bytes, str)):
                    raise AttributeError(
                        "Invalid data type {} provided to Persistent Storage"
                        .format(type(data)))

            except Exception as e:
                logger.warning(
                    'Could read() from potential iostream with persistent '
                    'key: %s', key)
                logger.debug('Persistent Storage Exception: %s' % str(e))
                raise AttributeError(
                    "Invalid data type {} provided to Persistent Storage"
                    .format(type(data)))

        if self.__mode == PersistentStoreMode.MEMORY:
            # Nothing further can be done
            return False

        # generate our filename based on the key provided
        io_file = os.path.join(self.__data_path, f"{key}{self.__extension}")

        # Calculate the files current filesize
        try:
            prev_size = os.stat(io_file).st_size

        except FileNotFoundError:
            # No worries, no size to accomodate
            prev_size = 0

        except (OSError, IOError) as e:
            logger.warning('Could not write with persistent key: %s', key)
            logger.debug('Persistent Storage Exception: %s' % str(e))
            return False

        # Create a temporary file to write our content into
        # ntf = NamedTemporaryFile
        ntf = None
        new_file_size = 0
        try:
            if isinstance(data, str):
                data = data.encode(self.encoding)

            ntf = tempfile.NamedTemporaryFile(
                mode="wb", dir=self.__temp_path,
                delete=False)

            # Close our file
            ntf.close()

            # Pointer to our open call
            _open = open if not compress else gzip.open

            with _open(ntf.name, mode='wb') as fd:
                # Write our content
                fd.write(data)

            # Get our file size
            new_file_size = os.stat(ntf.name).st_size

            # Log our progress
            logger.trace(
                'Wrote %d bytes of data to persistent key: %s',
                new_file_size, key)

        except (OSError, UnicodeEncodeError, IOError) as e:
            # We can't access the file or it does not exist
            logger.warning('Could not write to persistent key: %s', key)
            logger.debug('Persistent Storage Exception: %s' % str(e))

            if ntf:
                try:
                    ntf.close()
                except Exception:
                    pass

                try:
                    os.unlink(ntf.name)
                    logger.trace('Removed temporary file: %s', ntf.name)

                except FileNotFoundError:
                    # no worries; we were removing it anyway
                    pass

                except (OSError, IOError) as e:
                    logger.warning(
                        'Failed to remove persistent backup file: %s',
                        ntf.name)
                    logger.debug('Persistent Storage Exception: %s' % str(e))

            return False

        if self.max_file_size > 0 and (
                new_file_size + self.size() - prev_size) > self.max_file_size:
            # The content to store is to large
            logger.warning(
                'Persistent content exceeds allowable maximum file length '
                '({}KB); provide {}KB'.format(
                    int(self.max_file_size / 1024),
                    int(new_file_size / 1024)))
            return False

        # Return our final move
        if not self.__move(ntf.name, io_file):
            # Attempt to restore things as they were
            try:
                os.unlink(ntf.name)
                logger.trace(
                    'Removed temporary file: %s', ntf.name)

            except FileNotFoundError:
                # no worries; we were removing it anyway
                pass

            except (OSError, IOError) as e:
                logger.warning(
                    'Could not remove temporary file: %s', ntf.name)
                logger.debug('Persistent Storage Exception: %s' % str(e))
            return False

        # Resetour reference variables
        self.__cache_size = None
        self.__cache_files.clear()

        # Content installed
        return True

    def __move(self, src, dst):
        """
        Moves the new file in place and handles the old if it exists already
        If the transaction fails in any way, the old file is swapped back.

        Function returns True if successful and False if not.
        """

        # A temporary backup of the file we want to move in place
        dst_backup = dst[:-len(self.__backup_extension)] + \
            self.__backup_extension

        #
        # Backup the old file (if it exists) allowing us to have a restore
        # point in the event of a failure
        #
        try:
            # make sure the file isn't already present; if it is; remove it
            os.unlink(dst_backup)
            logger.trace(
                'Removed previous persistent backup file: %s', dst_backup)

        except FileNotFoundError:
            # no worries; we were removing it anyway
            pass

        except (OSError, IOError) as e:
            logger.warning(
                'Could not previous persistent data backup: %s', dst_backup)
            logger.debug('Persistent Storage Exception: %s' % str(e))
            return False

        try:
            # Back our file up so we have a fallback
            os.rename(dst, dst_backup)
            logger.trace(
                'Persistent storage backup file created: %s', dst_backup)

        except FileNotFoundError:
            # Not a problem; this is a brand new file we're writing
            # There is nothing to backup
            pass

        except (OSError, IOError) as e:
            # This isn't good... we couldn't put our new file in place
            logger.warning(
                'Could not install persistent content %s -> %s',
                dst, os.path.basename(dst_backup))
            logger.debug('Persistent Storage Exception: %s' % str(e))
            return False

        #
        # Now place the new file
        #
        try:
            os.rename(src, dst)
            logger.trace('Persistent file installed: %s', dst)

        except (OSError, IOError) as e:
            # This isn't good... we couldn't put our new file in place
            # Begin fall-back process before leaving the funtion
            logger.warning(
                'Could not install persistent content %s -> %s',
                src, os.path.basename(dst))
            logger.debug('Persistent Storage Exception: %s' % str(e))
            try:
                # Restore our old backup (if it exists)
                os.rename(dst_backup, dst)
                logger.trace(
                    'Restoring original persistent content: %s', dst)

            except FileNotFoundError:
                # Not a problem
                pass

            except (OSError, IOError) as e:
                logger.warning(
                    'Failed to restore original persistent file: %s', dst)
                logger.debug('Persistent Storage Exception: %s' % str(e))

            return False

        return True

    def open(self, key=None, mode='r', buffering=-1, encoding=None,
             errors=None, newline=None, closefd=True, opener=None,
             compress=False, compresslevel=9):
        """
        Returns an iterator to our our file within our namespace identified
        by the key provided.

        If no key is provided, then the default is used
        """

        if key is None:
            key = self.base_key

        elif not isinstance(key, str) or not self.__valid_key.match(key):
            raise AttributeError(
                f"Persistent Storage key ({key} provided is invalid")

        if self.__mode == PersistentStoreMode.MEMORY:
            # Nothing further can be done
            raise FileNotFoundError()

        io_file = os.path.join(self.__data_path, f"{key}{self.__extension}")
        return open(
            io_file, mode=mode, buffering=buffering, encoding=encoding,
            errors=errors, newline=newline, closefd=closefd, opener=opener) \
            if not compress else gzip.open(
                io_file, compresslevel=compresslevel, encoding=encoding,
                errors=errors, newline=newline)

    def get(self, key, default=None, lazy=True):
        """
        Fetches from cache
        """

        if self._cache is None and not self.__load_cache():
            return default

        return self._cache[key].value \
            if key in self._cache and self._cache[key] else default

    def set(self, key, value, expires=None, persistent=True, lazy=True):
        """
        Cache reference
        """

        if self._cache is None and not self.__load_cache():
            return False

        cache = CacheObject(value, expires, persistent=persistent)
        # Fetch our cache value
        try:
            if lazy and cache == self._cache[key]:
                # We're done; nothing further to do
                return True

        except KeyError:
            pass

        # Store our new cache
        self._cache[key] = CacheObject(value, expires, persistent=persistent)

        # Set our dirty flag
        self.__dirty = persistent

        if self.__dirty and self.__mode == PersistentStoreMode.FLUSH:
            # Flush changes to disk
            return self.flush()

        return True

    def clear(self, *args):
        """
        Remove one or more cache entry by it's key

            e.g: clear('key')
                 clear('key1', 'key2', key-12')

        Or clear everything:
                 clear()
        """
        if self._cache is None and not self.__load_cache():
            return False

        if args:
            for arg in args:

                try:
                    del self._cache['key']

                    # Set our dirty flag (if not set already)
                    self.__dirty = True

                except KeyError:
                    pass

        elif self._cache:
            # Request to remove everything and there is something to remove

            # Set our dirty flag (if not set already)
            self.__dirty = True

            # Reset our object
            self._cache.clear()

        if self.__dirty and self.__mode == PersistentStoreMode.FLUSH:
            # Flush changes to disk
            return self.flush()

    def prune(self):
        """
        Eliminates expired cache entries
        """
        if self._cache is None and not self.__load_cache():
            return False

        change = False
        for key in list(self._cache.keys()):
            if key not in self:
                # It's identified as being expired
                if not change and self._cache[key].persistent:
                    # track change only if content was persistent
                    change = True

                    # Set our dirty flag
                    self.__dirty = True

                del self._cache[key]

        if self.__dirty and self.__mode == PersistentStoreMode.FLUSH:
            # Flush changes to disk
            return self.flush()

        return change

    def __load_cache(self):
        """
        Loads our cache
        """

        # Prepare our dirty flag
        self.__dirty = False

        if self.__mode == PersistentStoreMode.MEMORY:
            # Nothing further to do
            self._cache = {}
            return True

        # Prepare our cache file
        cache_file = self.cache_file
        try:
            with gzip.open(cache_file, 'rb') as f:
                # Read our ontent from disk
                self._cache = {}
                for k, v in json.loads(f.read().decode(self.encoding)).items():
                    co = CacheObject.instantiate(v)
                    if co:
                        # Verify our object before assigning it
                        self._cache[k] = co

                    elif not self.__dirty:
                        # Track changes from our loadset
                        self.__dirty = True

        except (UnicodeDecodeError, json.decoder.JSONDecodeError, zlib.error,
                EOFError):
            # Let users known there was a problem
            self._cache = {}
            logger.warning(
                'Corrupted access persistent cache content: %s',
                cache_file)
            return False

        except FileNotFoundError:
            # No problem; no cache to load
            self._cache = {}

        except (OSError, IOError) as e:
            # We failed (likely a permission issue)
            logger.warning(
                'Could not load persistent cache for namespace %s',
                os.path.basename(self.__base_path))
            logger.debug('Persistent Storage Exception: %s' % str(e))
            return False

        # Ensure our dirty flag is set to False
        return True

    def flush(self, force=False):
        """
        Save's our cache to disk
        """

        if self._cache is None or self.__mode == PersistentStoreMode.MEMORY:
            # nothing to do
            return True

        elif not force and self.__dirty is False:
            # Nothing further to do
            logger.trace('Persistent cache is consistent with memory map')
            return True

        # Unset our size lazy setting
        self.__cache_size = None
        self.__cache_files.clear()

        # Prepare our cache file
        cache_file = self.cache_file
        if not self._cache:
            #
            # We're deleting the cache file s there are no entries left in it
            #
            backup_file = cache_file[:-len(self.__backup_extension)] + \
                self.__backup_extension

            try:
                os.unlink(backup_file)
                logger.trace(
                    'Removed previous persistent cache backup: %s',
                    backup_file)

            except FileNotFoundError:
                # no worries; we were removing it anyway
                pass

            except (OSError, IOError) as e:
                logger.warning(
                    'Could not remove persistent cache backup: %s',
                    backup_file)
                logger.debug('Persistent Storage Exception: %s' % str(e))
                return False

            try:
                os.rename(cache_file, backup_file)
                logger.trace(
                    'Persistent cache backup file created: %s',
                    backup_file)

            except FileNotFoundError:
                # Not a problem; do not create a log entry
                pass

            except (OSError, IOError) as e:
                # This isn't good... we couldn't put our new file in place
                logger.warning(
                    'Could not remove persistent cache file: %s',
                    cache_file)
                logger.debug('Persistent Storage Exception: %s' % str(e))
                return False
            return True

        #
        # If we get here, we need to update our file based cache
        #

        # ntf = NamedTemporaryFile
        ntf = None
        try:
            ntf = tempfile.NamedTemporaryFile(
                mode="w+", encoding=self.encoding, dir=self.__temp_path,
                delete=False)

            ntf.close()

        except OSError as e:
            logger.error(
                'Persistent temporary directory inaccessible: %s',
                self.__temp_path)
            logger.debug('Persistent Storage Exception: %s' % str(e))

            if ntf:
                # Cleanup
                try:
                    ntf.close()
                except OSError:
                    pass

                try:
                    os.unlink(ntf.name)
                    logger.trace(
                        'Persistent temporary file removed: %s', ntf.name)

                except FileNotFoundError:
                    # no worries; we were removing it anyway
                    pass

                except (OSError, IOError) as e:
                    logger.error(
                        'Persistent temporary file removal failed: %s',
                        ntf.name)
                    logger.debug(
                        'Persistent Storage Exception: %s' % str(e))

            # Early Exit
            return False

        # write our content currently saved to disk to our temporary file
        with gzip.open(ntf.name, 'wb') as f:
            # Write our content to disk
            f.write(json.dumps(
                {k: v for k, v in self._cache.items() if v and v.persistent},
                separators=(',', ':'),
                cls=CacheJSONEncoder).encode(self.encoding))

        if not self.__move(ntf.name, cache_file):
            # Attempt to restore things as they were
            try:
                os.unlink(ntf.name)
                logger.trace('Removed temporary file: %s', ntf.name)

            except FileNotFoundError:
                # no worries; we were removing it anyway
                pass

            except (OSError, IOError) as e:
                logger.warning(
                    'Could not remove temporary file: %s', ntf.name)
                logger.debug('Persistent Storage Exception: %s' % str(e))
            return False

        # Ensure our dirty flag is set to False
        self.__dirty = False

        return True

    def files(self, exclude=True, lazy=True):
        """
        Returns the total files
        """

        if lazy and exclude in self.__cache_files:
            # Take an early exit with our cached results
            return self.__cache_files[exclude]

        elif self.__mode == PersistentStoreMode.MEMORY:
            # Take an early exit
            # exclude is our cache switch and can be either True or False.
            # For the below, we just set both cases and set them up as an
            # empty record
            self.__cache_files.update({True: [], False: []})
            return []

        if not lazy or self.__exclude_list is None:
            # A list of criteria that should be excluded from the size count
            self.__exclude_list = (
                # Exclude backup cache file from count
                re.compile(re.escape(os.path.join(
                    self.__base_path,
                    f'{self.__cache_key}{self.__backup_extension}'))),

                # Exclude temporary files
                re.compile(re.escape(self.__temp_path) + r'[/\\].+'),

                # Exclude custom backup persistent files
                re.compile(
                    re.escape(self.__data_path) + r'[/\\].+' + re.escape(
                        self.__backup_extension)),
            )

        try:
            if exclude:
                self.__cache_files[exclude] = \
                    [path for path in filter(os.path.isfile, glob.glob(
                        self.__base_path + '/**/*', recursive=True))
                        if next((False for p in self.__exclude_list
                                 if p.match(path)), True)]

            else:  # No exclusion list applied
                self.__cache_files[exclude] = \
                    [path for path in filter(os.path.isfile, glob.glob(
                        self.__base_path + '/**/*', recursive=True))]

        except (OSError, IOError):
            # We can't access the directory or it does not exist
            self.__cache_files[exclude] = []
            pass

        return self.__cache_files[exclude]

    def size(self, exclude=True, lazy=True):
        """
        Returns the total size of the persistent storage in bytes
        """

        if lazy and self.__cache_size is not None:
            # Take an early exit
            return self.__cache_size

        elif self.__mode == PersistentStoreMode.MEMORY:
            # Take an early exit
            self.__cache_size = 0
            return self.__cache_size

        # Get a list of files (file paths) in the given directory
        try:
            self.__cache_size = sum(
                [os.stat(path).st_size for path in
                    self.files(exclude=exclude, lazy=lazy)])

        except (OSError, IOError):
            # We can't access the directory or it does not exist
            self.__cache_size = 0

        return self.__cache_size

    def __del__(self):
        """
        Deconstruction of our object
        """

        if self.__mode == PersistentStoreMode.AUTO:
            # Flush changes to disk
            self.flush()

    def __delitem__(self, key):
        """
        Remove a cache entry by it's key
        """
        if self._cache is None and not self.__load_cache():
            raise KeyError

        try:
            if self._cache[key].persistent:
                # Set our dirty flag in advance
                self.__dirty = True

            # Store our new cache
            del self._cache[key]

        except KeyError:
            # Nothing to do
            raise

        if self.__dirty and self.__mode == PersistentStoreMode.FLUSH:
            # Flush changes to disk
            self.flush()

        return

    def __contains__(self, key):
        """
        Verify if our storage contains the key specified or not.
        In additiont to this, if the content is expired, it is considered
        to be not contained in the storage.
        """
        if self._cache is None and not self.__load_cache():
            return False

        return key in self._cache and self._cache[key]

    def __setitem__(self, key, value):
        """
        Sets a cache value without disrupting existing settings in place
        """

        if self._cache is None and not self.__load_cache():
            raise OSError("Could not set cache")

        if key not in self._cache and not self.set(key, value):
            raise OSError("Could not set cache")

        else:
            # Update our value
            self._cache[key].set(value)

            if self._cache[key].persistent:
                # Set our dirty flag in advance
                self.__dirty = True

        if self.__dirty and self.__mode == PersistentStoreMode.FLUSH:
            # Flush changes to disk
            self.flush()

        return

    def __getitem__(self, key):
        """
        Returns the indexed value
        """

        if self._cache is None and not self.__load_cache():
            raise KeyError()

        result = self.get(key, default=self.__not_found_ref, lazy=False)
        if result is self.__not_found_ref:
            raise KeyError()

        return result

    def keys(self):
        """
        Returns our keys
        """
        return self._cache.keys()

    def delete(self, *args, all=None, temp=None, cache=None, validate=True):
        """
        Manages our file space and tidys it up

        delete('key', 'key2')
        delete(all=True)
        delete(temp=True, cache=True)
        """

        # Our failure flag
        has_error = False

        valid_key_re = re.compile(
            r'^(?P<key>.+)(' +
            re.escape(self.__backup_extension) +
            r'|' + re.escape(self.__extension) + r')$', re.I)

        # Default asignments
        if all is None:
            all = True if not (len(args) or temp or cache) else False
        if temp is None:
            temp = True if all else False
        if cache is None:
            cache = True if all else False

        if cache and self._cache:
            # Reset our object
            self._cache.clear()
            # Reset dirt flag
            self.__dirty = False

        for path in self.files(exclude=False):

            # Some information we use to validate the actions of our clean()
            # call. This is so we don't remove anything we shouldn't
            base = os.path.dirname(path)
            fname = os.path.basename(path)

            # Clean printable path details
            ppath = os.path.join(os.path.dirname(base), fname)

            if base == self.__base_path and cache:
                # We're handling a cache file (hopefully)
                result = valid_key_re.match(fname)
                key = None if not result else (
                    result['key'] if self.__valid_key.match(result['key'])
                    else None)

                if validate and key != self.__cache_key:
                    # We're not dealing with a cache key
                    logger.debug(
                        'Persistent File cleanup ignoring file: %s', path)
                    continue

                #
                # We should proceed with removing the file if we get here
                #

            elif base == self.__data_path and (args or all):
                # We're handling a file found in our custom data path
                result = valid_key_re.match(fname)
                key = None if not result else (
                    result['key'] if self.__valid_key.match(result['key'])
                    else None)

                if validate and key is None:
                    # we're set to validate and a non-valid file was found
                    logger.debug(
                        'Persistent File cleanup ignoring file: %s', path)
                    continue

                elif not all and (key is None or key not in args):
                    # no match found
                    logger.debug(
                        'Persistent File cleanup ignoring file: %s', path)
                    continue

                #
                # We should proceed with removing the file if we get here
                #

            elif base == self.__temp_path and temp:
                #
                # This directory is a temporary path and nothing in here needs
                # to be further verified. Proceed with the removing of the file
                #
                pass

            else:
                # No match; move on
                logger.debug('Persistent File cleanup ignoring file: %s', path)
                continue

            try:
                os.unlink(path)
                logger.info('Removed persistent file: %s', ppath)

            except FileNotFoundError:
                # no worries; we were removing it anyway
                pass

            except (OSError, IOError) as e:
                has_error = True
                logger.error(
                    'Failed to remove persistent file: %s', ppath)
                logger.debug('Persistent Storage Exception: %s' % str(e))

        # Reset our reference variables
        self.__cache_size = None
        self.__cache_files.clear()

        return not has_error

    @property
    def cache_file(self):
        """
        Returns the full path to the namespace directory
        """
        return os.path.join(
            self.__base_path,
            f'{self.__cache_key}{self.__extension}',
        )

    @property
    def path(self):
        """
        Returns the full path to the namespace directory
        """
        return self.__base_path

    @property
    def mode(self):
        """
        Returns the full path to the namespace directory
        """
        return self.__mode
