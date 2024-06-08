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
            # Python <= v3.7 - usedforsecurity flag does not work
            return hashlib.sha1(str(self).encode('utf-8')).hexdigest()

    def json(self):
        """
        Returns our preparable json object
        """
        return {
            'v': self.__value,
            'x': (self.__expires - EPOCH).total_seconds()
            if self.__expires else None,
            'c': self.__class_name,
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

        if class_name == 'datetime':
            # Note: FakeDatetime comes from our test cases so that we can still
            #       verify this code execute okay.

            try:
                # Convert our object back to a datetime object
                value = datetime.fromisoformat(value)

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
             else self.__expires.isoformat())


class CacheJSONEncoder(json.JSONEncoder):
    """
    A JSON Encoder for handling each of our cache objects
    """

    def default(self, entry):
        if isinstance(entry, datetime):
            return entry.isoformat()

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
    cache_file = '_cache.dat'

    # backup cache file (prior to being removed completely)
    cache_file_backup = '_cache.bak'

    # Our Temporary working directory
    temp_dir = '.tmp'

    # Used to verify the token specified is valid
    #  - must start with an alpha_numeric
    #  - following optional characters can include period, underscore and
    #    equal
    __valid_token = re.compile(r'[a-z0-9][a-z0-9._=]*', re.I)

    # Reference only
    __not_found_ref = (None, None)

    def __init__(self, namespace, path, mode=None):
        """
        Provide the namespace to work within. namespaces can only contain
        alpha-numeric characters with the exception of '-' (dash), '_'
        (underscore), and '.' (period). The namespace must be be relative
        to the current URL being controlled.
        """
        # Initalize our mode so __del__() calls don't go bad on the
        # error checking below
        self.__mode = None

        # Track open file pointers
        self.__pointers = set()

        # Populated only once and after size() is called
        self.__exclude_size_list = None

        if not isinstance(namespace, str) \
                or not self.__valid_token.match(namespace):
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

        else:  # If no storage path is provide we set our mode to MEMORY
            mode = PersistentStoreMode.MEMORY
            self.__base_path = None
            self.__temp_path = None

        if mode not in PERSISTENT_STORE_MODES:
            raise AttributeError(
                f"Persistent Storage mode ({mode}) provided is invalid")

        # Store our mode
        self.__mode = mode

        # Tracks when we have content to flush
        self.__dirty = False

        # A caching value to track persistent storage disk size
        self.__size = None
        self.__files = {}

        # Internal Cache
        self._cache = None

    def read(self, key=None):
        """
        Returns the content of the persistent store object
        """

        if key is None:
            key = self.base_key

        elif not isinstance(key, str) or not self.__valid_token.match(key):
            raise AttributeError(
                f"Persistent Storage key ({key} provided is invalid")

        if not self.__mode == PersistentStoreMode.MEMORY:
            # Nothing further can be done
            return None

        # generate our filename
        io_file = os.path.join(self.__base_path, f"{key}.dat")

        try:
            with open(io_file, mode="rb") as fd:
                return fd.read(self.max_file_size)

        except (OSError, IOError):
            # We can't access the file or it does not exist
            pass

        # return none
        return None

    def write(self, data, key=None):
        """
        Writes the content to the persistent store if it doesn't exceed our
        filesize limit.
        """

        if not self.__mode == PersistentStoreMode.MEMORY:
            # Nothing further can be done
            return None

        if key is None:
            key = self.base_key

        elif not isinstance(key, str) or not self.__valid_token.match(key):
            raise AttributeError(
                f"Persistent Storage key ({key} provided is invalid")

        # generate our filename
        io_file = os.path.join(self.__base_path, f"{key}.dat")

        if (len(data) + self.size(exclude=key)) > self.max_file_size:
            # The content to store is to large
            logger.error(
                'Content exceeds allowable maximum file length '
                '({}KB): {}'.format(
                    int(self.max_file_size / 1024), self.url(privacy=True)))
            return False

        # ntf = NamedTemporaryFile
        ntf = None
        try:
            ntf = tempfile.NamedTemporaryFile(
                mode="w+", encoding=self.encoding, dir=self.__temp_path,
                delete=False)

            # Write our content
            ntf.write(data)

        except (OSError, IOError):
            # We can't access the file or it does not exist
            if ntf:
                try:
                    ntf.close()
                except Exception:
                    logger.trace(
                        f'Could not close() persistent content {ntf.name}')
                    pass

                try:
                    ntf.unlink(ntf.name)

                except Exception:
                    logger.error(
                        f'Could not remove persistent content {ntf.name}')

            return False

        try:
            # Set our file
            os.rename(ntf.name, os.path.join(self.path, io_file))

        except (OSError, IOError):

            return False

    def open(self, key=None, mode="rb", encoding=None):
        """
        Returns an iterator to our our file within our namespace identified
        by the key provided.

        If no key is provided, then the default is used
        """

        if not self.__mode == PersistentStoreMode.MEMORY:
            # Nothing further can be done
            return None

        if key is None:
            key = self.base_key

        elif not isinstance(key, str) or not self.__valid_token.match(key):
            raise AttributeError(
                f"Persistent Storage key ({key} provided is invalid")

        if encoding is None:
            encoding = self.encoding

        if key is None:
            key = self.base_key

        io_file = os.path.join(self.__base_path, f"{key}.dat")
        pointer = open(io_file, mode=mode, encoding=encoding)
        self.__pointers.add(pointer)
        return pointer

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
            return self.flush(sync=True)

        return True

    def clean(self):
        """
        Eliminates all cached content
        """
        if self._cache is None and not self.__load_cache():
            return False

    def prune(self):
        """
        Eliminates expired cache entries
        """
        if self._cache is None and not self.__load_cache():
            return False

        change = False
        for key in list(self._cache.keys()):
            if not self._cache:

                if not change and self._cache[key].persistent:
                    # track change only if content was persistent
                    change = True

                    # Set our dirty flag
                    self.__dirty = True

                del self._cache[key]

        if self.__dirty and self.__mode == PersistentStoreMode.FLUSH:
            # Flush changes to disk
            return self.flush(sync=True)

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
        cache_file = os.path.join(self.__base_path, self.cache_file)
        try:
            with gzip.open(cache_file, 'rb') as f:
                # Read our content from disk
                self._cache = {}
                for k, v in json.loads(f.read().decode(self.encoding)).items():
                    co = CacheObject.instantiate(v)
                    if co:
                        # Verify our object before assigning it
                        self._cache[k] = co

                    elif not self.__dirty:
                        # Track changes from our loadset
                        self.__dirty = True

        except (UnicodeDecodeError, json.decoder.JSONDecodeError):
            # Let users known there was a problem
            self._cache = {}
            logger.warning(
                'Corrupted access persistent cache content'
                f' {cache_file}')

        except FileNotFoundError:
            # No problem; no cache to load
            self._cache = {}

        except OSError as e:
            # We failed (likely a permission issue)
            logger.warning(
                'Could not load persistent cache for namespace %s',
                os.path.basename(self.__base_path))
            logger.debug('Persistent Storage Exception: %s' % str(e))
            return False

        # Ensure our dirty flag is set to False
        return True

    def flush(self, sync=False, force=False):
        """
        Save's our cache
        """

        if self._cache is None or self.__mode == PersistentStoreMode.MEMORY:
            # nothing to do
            return True

        elif not force and self.__dirty is False:
            # Nothing further to do
            logger.trace('Persistent cache is consistent with memory map')
            return True

        # Ensure our path exists
        try:
            os.makedirs(self.__base_path, mode=0o770, exist_ok=True)

        except OSError:
            # Permission error
            logger.error(
                'Could not create persistent store directory %s',
                self.__base_path)
            return False

        # Ensure our path exists
        try:
            os.makedirs(self.__temp_path, mode=0o770, exist_ok=True)

        except OSError:
            # Permission error
            logger.error(
                'Could not create persistent store directory %s',
                self.__temp_path)
            return False

        # Unset our size lazy setting
        self.__size = None
        self.__files.clear()

        # Prepare our cache file
        cache_file = os.path.join(self.__base_path, self.cache_file)
        cache_file_backup = os.path.join(
            self.__base_path, self.cache_file_backup)

        if not self._cache:
            # We're deleting the file only
            try:
                os.unlink(f'{cache_file_backup}')

            except OSError:
                # No worries at all
                pass

            try:
                os.rename(f'{cache_file}', f'{cache_file_backup}')

            except OSError:
                # No worries at all
                pass
            return True

        # We're not deleting

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

                except OSError as e:
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

        # Remove our old backup of our cache file if it exists
        try:
            os.unlink(cache_file_backup)
            logger.trace(
                'Persistent cache backup file removed: %s', cache_file_backup)

        except FileNotFoundError:
            # No worries at all
            pass

        except OSError as e:
            logger.warning(
                'Persistent cache file backup removal failed: %s', cache_file)
            logger.debug('Persistent Storage Exception: %s' % str(e))

            # Clean-up if posible
            try:
                os.unlink(ntf.name)
                logger.trace(
                    'Persistent temporary file removed: %s', ntf.name)

            except OSError:
                pass

            return False

        # Create a backup of our existing cache file
        try:
            os.rename(cache_file, cache_file_backup)
            logger.trace(
                'Persistent cache file backed up: %s', cache_file_backup)

        except FileNotFoundError:
            # No worries at all; a previous configuration file simply did not
            # exist
            pass

        except OSError as e:
            logger.warning(
                'Persistent cache file backup failed: %s', ntf.name)
            logger.debug('Persistent Storage Exception: %s' % str(e))

            # Clean-up if posible
            try:
                os.unlink(ntf.name)
                logger.trace(
                    'Persistent temporary file removed: %s', ntf.name)

            except OSError:
                pass

            return False

        try:
            # Rename our file over the original
            os.rename(ntf.name, cache_file)
            logger.trace(
                'Persistent temporary file installed successfully: %s',
                cache_file)

        except OSError:
            # This isn't good... we couldn't put our new file in place
            logger.error(
                'Could not write persistent content to %s', cache_file)

            # Roll our old backup file back in place
            try:
                os.rename(cache_file_backup, cache_file)
                logger.trace(
                    'Restoring original persistent cache file: %s',
                    cache_file_backup)

            except OSError as e:
                logger.warning(
                    'Persistent cache file restoration failed: %s', cache_file)
                logger.debug('Persistent Storage Exception: %s' % str(e))

            # Clean-up if posible
            try:
                os.unlink(ntf.name)
                logger.trace(
                    'Persistent temporary file removed: %s', ntf.name)

            except OSError:
                pass

            # Clean-up if posible
            try:
                os.unlink(ntf.name)
                logger.trace(
                    'Persistent temporary file removed: %s', ntf.name)

            except OSError:
                pass

            return False

        logger.trace('Persistent cache generated for %s', cache_file)

        # Ensure our dirty flag is set to False
        self.__dirty = False

        if sync:
            # Flush our content to disk
            os.sync()

        return True

    def files(self, exclude_temp_files=True, lazy=True):
        """
        Returns the total files
        """

        if lazy and exclude_temp_files in self.__files:
            # Take an early exit with our cached results
            return self.__files[exclude_temp_files]

        elif self.__mode == PersistentStoreMode.MEMORY:
            # Take an early exit
            # exclude_temp_files is our cache switch and can be either True
            # or False.  For the below, we just set both cases and set them up
            # as an empty record
            self.__files.update({True: [], False: []})
            return []

        if not lazy or self.__exclude_size_list is None:
            # A list of criteria that should be excluded from the size count
            self.__exclude_size_list = (
                # Exclude backup cache file from count
                re.compile(re.escape(os.path.join(
                    self.__base_path, self.cache_file_backup))),
                # Exclude temporary files
                re.compile(re.escape(self.__temp_path) + r'[/\\].+'),
            )

        try:
            if exclude_temp_files:
                self.__files[exclude_temp_files] = \
                    [path for path in glob.glob(
                        self.__base_path + '/**/*', recursive=True)
                        if next((False for p in self.__exclude_size_list
                                 if p.match(path)), True)]

            else:  # No exclusion list applied
                self.__files[exclude_temp_files] = \
                    [path for path in glob.glob(
                        self.__base_path + '/**/*', recursive=True)]

        except (OSError, IOError):
            # We can't access the directory or it does not exist
            pass

        return self.__files[exclude_temp_files]

    def size(self, exclude_temp_files=True, lazy=True):
        """
        Returns the total size of the persistent storage in bytes
        """

        if lazy and self.__size is not None:
            # Take an early exit
            return self.__size

        elif self.__mode == PersistentStoreMode.MEMORY:
            # Take an early exit
            self.__size = 0
            return self.__size

        # Initialize our size to zero
        self.__size = 0

        # Get a list of files (file paths) in the given directory
        try:
            self.__size += sum(
                [os.stat(path).st_size for path in filter(
                    os.path.isfile, self.files(
                        exclude_temp_files=exclude_temp_files, lazy=lazy))])

        except (OSError, IOError):
            # We can't access the directory or it does not exist
            pass

        return self.__size

    def __del__(self):
        """
        Deconstruction of our object
        """

        # close all open pointers
        while self.__pointers:
            self.__pointers.pop().close()

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
            self.flush(sync=True)

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
            return False

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
            self.flush(sync=True)

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

    @property
    def path(self):
        """
        Returns the full path to the namespace directory
        """
        return self.__base_path
