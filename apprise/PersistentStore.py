# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Chris Caron <lead2gold@gmail.com>
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
import glob
import io
import six
import json
import platform


class PersistentStore(object):
    """
    An object to make working with persistent storage easier
    """

    # The maximum file-size we will allow the persistent store to grow to
    # 1 MB = 1048576 bytes
    max_file_size = 1048576

    # File encoding to use
    encoding = 'utf-8'

    def __init__(self, namespace, root=None):
        """
        Provide the namespace to work within. Since our namespace is built on
        directories, you must separate groups with either a forward or
        backwards slash.

        """

        # Prepare our path
        if root is None:
            self.__path = os.path.normpath(os.path.join(
                os.path.expandvars('%APPDATA%/Apprise/{}')
                if platform.system() == 'Windows'
                else os.path.expanduser('~/local/apprise/{}'), namespace))

        else:
            self.__path = os.path.normpath(os.path.join(root, namespace))

        # A simple file for data i/o
        self.__simple_io_file = "{}.dat".format(self.__path)

        # A caching value to track persistent storage disk size
        self.__size = None

    def read(self, format="json"):
        """
        Returns the content of the persistent store object
        """
        try:
            with io.open(self.__simple_io_file, mode="r",
                         encoding=self.encoding) as fd:
                return fd.read(self.max_file_size)

        except (OSError, IOError):
            # We can't access the file or it does not exist
            pass

        # return none
        return None

    def write(self, data):
        """
        Writes the content to the persistent store if it doesn't exceed our
        filesize limit.
        """
        if not isinstance(data, six.string_types):
            content = json.loads(data)

        if (len(content) + self.size()) > self.max_file_size:
            # The content to store is to large
            self.logger.error(
                'Content exceeds allowable maximum file length '
                '({}KB): {}'.format(
                    int(self.max_file_size / 1024), self.url(privacy=True)))

        try:
            with io.open(self.__simple_io_file, mode="w+",
                         encoding=self.encoding) as fd:
                return fd.write(data)

        except (OSError, IOError):
            # We can't access the file or it does not exist
            pass

    def open(self, path, mode="+", encoding='utf-8'):
        """
        Returns an iterator to a
        """
        # TODO

    @property
    def path(self):
        """
        Returns the full path to the namespace directory
        """
        return self.__path

    def size(self, lazy=True):
        """
        Returns the total size of the persistent storage in bytes
        """

        if lazy and self.__size:
            return self.__size

        # Get a list of files (file paths) in the given directory
        self.__size = 0
        try:
            self.__size += sum(
                [os.stat(path).st_size for path in filter(os.path.isfile,
                 glob.glob(self.__path + '/**/*', recursive=True))])

        except (OSError, IOError):
            # We can't access the directory or it does not exist
            pass

        try:
            if os.path.isfile(self.__simple_io_file):
                self.__size += os.stat(self.__simple_io_file).st_size

        except (OSError, IOError):
            # We can't access the file or it does not exist
            pass

        return self.__size
