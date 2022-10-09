# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
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
import time
import mimetypes
from ..URLBase import URLBase
from ..utils import parse_bool
from ..common import ContentLocation
from ..AppriseLocale import gettext_lazy as _


class AttachBase(URLBase):
    """
    This is the base class for all supported attachment types
    """

    # For attachment type detection; this amount of data is read into memory
    # 128KB (131072B)
    max_detect_buffer_size = 131072

    # Unknown mimetype
    unknown_mimetype = 'application/octet-stream'

    # Our filename when we can't otherwise determine one
    unknown_filename = 'apprise-attachment'

    # Our filename extension when we can't otherwise determine one
    unknown_filename_extension = '.obj'

    # The strict argument is a flag specifying whether the list of known MIME
    # types is limited to only the official types registered with IANA. When
    # strict is True, only the IANA types are supported; when strict is False
    # (the default), some additional non-standard but commonly used MIME types
    # are also recognized.
    strict = False

    # The maximum file-size we will accept for an attachment size. If this is
    # set to zero (0), then no check is performed
    # 1 MB = 1048576 bytes
    # 5 MB = 5242880 bytes
    max_file_size = 5242880

    # By default all attachments types are inaccessible.
    # Developers of items identified in the attachment plugin directory
    # are requried to set a location
    location = ContentLocation.INACCESSIBLE

    # Here is where we define all of the arguments we accept on the url
    # such as: schema://whatever/?overflow=upstream&format=text
    # These act the same way as tokens except they are optional and/or
    # have default values set if mandatory. This rule must be followed
    template_args = {
        'cache': {
            'name': _('Cache Age'),
            'type': 'int',
            # We default to (600) which means we cache for 10 minutes
            'default': 600,
        },
        'mime': {
            'name': _('Forced Mime Type'),
            'type': 'string',
        },
        'name': {
            'name': _('Forced File Name'),
            'type': 'string',
        },
        'verify': {
            'name': _('Verify SSL'),
            # SSL Certificate Authority Verification
            'type': 'bool',
            # Provide a default
            'default': True,
        },
    }

    def __init__(self, name=None, mimetype=None, cache=None, **kwargs):
        """
        Initialize some general logging and common server arguments that will
        keep things consistent when working with the configurations that
        inherit this class.

        Optionally provide a filename to over-ride name associated with the
        actual file retrieved (from where-ever).

        The mime-type is automatically detected, but you can over-ride this by
        explicitly stating what it should be.

        By default we cache our responses so that subsiquent calls does not
        cause the content to be retrieved again.  For local file references
        this makes no difference at all.  But for remote content, this does
        mean more then one call can be made to retrieve the (same) data.  This
        method can be somewhat inefficient if disabled.  Only disable caching
        if you understand the consequences.

        You can alternatively set the cache value to an int identifying the
        number of seconds the previously retrieved can exist for before it
        should be considered expired.
        """

        super().__init__(**kwargs)

        if not mimetypes.inited:
            # Ensure mimetypes has been initialized
            mimetypes.init()

        # Attach Filename (does not have to be the same as path)
        self._name = name

        # The mime type of the attached content.  This is detected if not
        # otherwise specified.
        self._mimetype = mimetype

        # The detected_mimetype, this is only used as a fallback if the
        # mimetype wasn't forced by the user
        self.detected_mimetype = None

        # The detected filename by calling child class. A detected filename
        # is always used if no force naming was specified.
        self.detected_name = None

        # Absolute path to attachment
        self.download_path = None

        # Set our cache flag; it can be True, False, None, or a (positive)
        # integer... nothing else
        if cache is not None:
            try:
                self.cache = cache if isinstance(cache, bool) else int(cache)

            except (TypeError, ValueError):
                err = 'An invalid cache value ({}) was specified.'.format(
                    cache)
                self.logger.warning(err)
                raise TypeError(err)

            # Some simple error checking
            if self.cache < 0:
                err = 'A negative cache value ({}) was specified.'.format(
                    cache)
                self.logger.warning(err)
                raise TypeError(err)

        else:
            self.cache = None

        # Validate mimetype if specified
        if self._mimetype:
            if next((t for t in mimetypes.types_map.values()
                     if self._mimetype == t), None) is None:
                err = 'An invalid mime-type ({}) was specified.'.format(
                    mimetype)
                self.logger.warning(err)
                raise TypeError(err)

        return

    @property
    def path(self):
        """
        Returns the absolute path to the filename. If this is not known or
        is know but has been considered expired (due to cache setting), then
        content is re-retrieved prior to returning.
        """

        if not self.exists():
            # we could not obtain our path
            return None

        return self.download_path

    @property
    def name(self):
        """
        Returns the filename
        """
        if self._name:
            # return our fixed content
            return self._name

        if not self.exists():
            # we could not obtain our name
            return None

        if not self.detected_name:
            # If we get here, our download was successful but we don't have a
            # filename based on our content.
            extension = mimetypes.guess_extension(self.mimetype)
            self.detected_name = '{}{}'.format(
                self.unknown_filename,
                extension if extension else self.unknown_filename_extension)

        return self.detected_name

    @property
    def mimetype(self):
        """
        Returns mime type (if one is present).

        Content is cached once determied to prevent overhead of future
        calls.
        """

        if self._mimetype:
            # return our pre-calculated cached content
            return self._mimetype

        if not self.exists():
            # we could not obtain our attachment
            return None

        if not self.detected_mimetype:
            # guess_type() returns: (type, encoding) and sets type to None
            # if it can't otherwise determine it.
            try:
                # Directly reference _name and detected_name to prevent
                # recursion loop (as self.name calls this function)
                self.detected_mimetype, _ = mimetypes.guess_type(
                    self._name if self._name
                    else self.detected_name, strict=self.strict)

            except TypeError:
                # Thrown if None was specified in filename section
                pass

        # Return our mime type
        return self.detected_mimetype \
            if self.detected_mimetype else self.unknown_mimetype

    def exists(self):
        """
        Simply returns true if the object has downloaded and stored the
        attachment AND the attachment has not expired.
        """

        cache = self.template_args['cache']['default'] \
            if self.cache is None else self.cache

        if self.download_path and os.path.isfile(self.download_path) \
                and cache:

            # We have enough reason to look further into our cached content
            # and verify it has not expired.
            if cache is True:
                # return our fixed content as is; we will always cache it
                return True

            # Verify our cache time to determine whether we will get our
            # content again.
            try:
                age_in_sec = time.time() - os.stat(self.download_path).st_mtime
                if age_in_sec <= cache:
                    return True

            except (OSError, IOError):
                # The file is not present
                pass

        return self.download()

    def invalidate(self):
        """
        Release any temporary data that may be open by child classes.
        Externally fetched content should be automatically cleaned up when
        this function is called.

        This function should also reset the following entries to None:
          - detected_name : Should identify a human readable filename
          - download_path: Must contain a absolute path to content
          - detected_mimetype: Should identify mimetype of content
        """
        self.detected_name = None
        self.download_path = None
        self.detected_mimetype = None
        return

    def download(self):
        """
        This function must be over-ridden by inheriting classes.

        Inherited classes MUST populate:
          - detected_name: Should identify a human readable filename
          - download_path: Must contain a absolute path to content
          - detected_mimetype: Should identify mimetype of content

        If a download fails, you should ensure these values are set to None.
        """
        raise NotImplementedError(
            "download() is implimented by the child class.")

    @staticmethod
    def parse_url(url, verify_host=True, mimetype_db=None):
        """Parses the URL and returns it broken apart into a dictionary.

        This is very specific and customized for Apprise.

        Args:
            url (str): The URL you want to fully parse.
            verify_host (:obj:`bool`, optional): a flag kept with the parsed
                 URL which some child classes will later use to verify SSL
                 keys (if SSL transactions take place).  Unless under very
                 specific circumstances, it is strongly recomended that
                 you leave this default value set to True.

        Returns:
            A dictionary is returned containing the URL fully parsed if
            successful, otherwise None is returned.
        """

        results = URLBase.parse_url(url, verify_host=verify_host)

        if not results:
            # We're done; we failed to parse our url
            return results

        # Allow overriding the default config mime type
        if 'mime' in results['qsd']:
            results['mimetype'] = results['qsd'].get('mime', '') \
                .strip().lower()

        # Allow overriding the default file name
        if 'name' in results['qsd']:
            results['name'] = results['qsd'].get('name', '') \
                .strip().lower()

        # Our cache value
        if 'cache' in results['qsd']:
            # First try to get it's integer value
            try:
                results['cache'] = int(results['qsd']['cache'])

            except (ValueError, TypeError):
                # No problem, it just isn't an integer; now treat it as a bool
                # instead:
                results['cache'] = parse_bool(results['qsd']['cache'])

        return results

    def __len__(self):
        """
        Returns the filesize of the attachment.

        """
        return os.path.getsize(self.path) if self.path else 0

    def __bool__(self):
        """
        Allows the Apprise object to be wrapped in an based 'if statement'.
        True is returned if our content was downloaded correctly.
        """
        return True if self.path else False
