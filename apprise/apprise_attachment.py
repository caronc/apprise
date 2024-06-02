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

from . import URLBase
from .attachment.base import AttachBase
from .asset import AppriseAsset
from .manager_attachment import AttachmentManager
from .logger import logger
from .common import ContentLocation
from .common import CONTENT_LOCATIONS
from .utils import GET_SCHEMA_RE

# Grant access to our Notification Manager Singleton
A_MGR = AttachmentManager()


class AppriseAttachment:
    """
    Our Apprise Attachment File Manager

    """

    def __init__(self, paths=None, asset=None, cache=True, location=None,
                 **kwargs):
        """
        Loads all of the paths/urls specified (if any).

        The path can either be a single string identifying one explicit
        location, otherwise you can pass in a series of locations to scan
        via a list.

        By default we cache our responses so that subsiquent calls does not
        cause the content to be retrieved again.  For local file references
        this makes no difference at all.  But for remote content, this does
        mean more then one call can be made to retrieve the (same) data.  This
        method can be somewhat inefficient if disabled.  Only disable caching
        if you understand the consequences.

        You can alternatively set the cache value to an int identifying the
        number of seconds the previously retrieved can exist for before it
        should be considered expired.

        It's also worth nothing that the cache value is only set to elements
        that are not already of subclass AttachBase()

        Optionally set your current ContentLocation in the location argument.
        This is used to further handle attachments. The rules are as follows:
          - INACCESSIBLE: You simply have disabled use of the object; no
                          attachments will be retrieved/handled.
          - HOSTED:       You are hosting an attachment service for others.
                          In these circumstances all attachments that are LOCAL
                          based (such as file://) will not be allowed.
          - LOCAL:        The least restrictive mode as local files can be
                          referenced in addition to hosted.

        In all both HOSTED and LOCAL modes, INACCESSIBLE attachment types will
        continue to be inaccessible.  However if you set this field (location)
        to None (it's default value) the attachment location category will not
        be tested in any way (all attachment types will be allowed).

        The location field is also a global option that can be set when
        initializing the Apprise object.

        """

        # Initialize our attachment listings
        self.attachments = list()

        # Set our cache flag
        self.cache = cache

        # Prepare our Asset Object
        self.asset = \
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        if location is not None and location not in CONTENT_LOCATIONS:
            msg = "An invalid Attachment location ({}) was specified." \
                  .format(location)
            logger.warning(msg)
            raise TypeError(msg)

        # Store our location
        self.location = location

        # Now parse any paths specified
        if paths is not None:
            # Store our path(s)
            if not self.add(paths):
                # Parse Source domain based on from_addr
                raise TypeError("One or more attachments could not be added.")

    def add(self, attachments, asset=None, cache=None):
        """
        Adds one or more attachments into our list.

        By default we cache our responses so that subsiquent calls does not
        cause the content to be retrieved again.  For local file references
        this makes no difference at all.  But for remote content, this does
        mean more then one call can be made to retrieve the (same) data.  This
        method can be somewhat inefficient if disabled.  Only disable caching
        if you understand the consequences.

        You can alternatively set the cache value to an int identifying the
        number of seconds the previously retrieved can exist for before it
        should be considered expired.

        It's also worth nothing that the cache value is only set to elements
        that are not already of subclass AttachBase()
        """
        # Initialize our return status
        return_status = True

        # Initialize our default cache value
        cache = cache if cache is not None else self.cache

        if asset is None:
            # prepare default asset
            asset = self.asset

        if isinstance(attachments, (AttachBase, str)):
            # store our instance
            attachments = (attachments, )

        elif not isinstance(attachments, (tuple, set, list)):
            logger.error(
                'An invalid attachment url (type={}) was '
                'specified.'.format(type(attachments)))
            return False

        # Iterate over our attachments
        for _attachment in attachments:
            if self.location == ContentLocation.INACCESSIBLE:
                logger.warning(
                    "Attachments are disabled; ignoring {}"
                    .format(_attachment))
                return_status = False
                continue

            if isinstance(_attachment, str):
                logger.debug("Loading attachment: {}".format(_attachment))
                # Instantiate ourselves an object, this function throws or
                # returns None if it fails
                instance = AppriseAttachment.instantiate(
                    _attachment, asset=asset, cache=cache)
                if not isinstance(instance, AttachBase):
                    return_status = False
                    continue

            elif isinstance(_attachment, AppriseAttachment):
                # We were provided a list of Apprise Attachments
                # append our content together
                instance = _attachment.attachments

            elif not isinstance(_attachment, AttachBase):
                logger.warning(
                    "An invalid attachment (type={}) was specified.".format(
                        type(_attachment)))
                return_status = False
                continue

            else:
                # our entry is of type AttachBase, so just go ahead and point
                # our instance to it for some post processing below
                instance = _attachment

            # Apply some simple logic if our location flag is set
            if self.location and ((
                    self.location == ContentLocation.HOSTED
                    and instance.location != ContentLocation.HOSTED)
                    or instance.location == ContentLocation.INACCESSIBLE):
                logger.warning(
                    "Attachment was disallowed due to accessibility "
                    "restrictions ({}->{}): {}".format(
                        self.location, instance.location,
                        instance.url(privacy=True)))
                return_status = False
                continue

            # Add our initialized plugin to our server listings
            if isinstance(instance, list):
                self.attachments.extend(instance)

            else:
                self.attachments.append(instance)

        # Return our status
        return return_status

    @staticmethod
    def instantiate(url, asset=None, cache=None, suppress_exceptions=True):
        """
        Returns the instance of a instantiated attachment plugin based on
        the provided Attachment URL.  If the url fails to be parsed, then None
        is returned.

        A specified cache value will over-ride anything set

        """
        # Attempt to acquire the schema at the very least to allow our
        # attachment based urls.
        schema = GET_SCHEMA_RE.match(url)
        if schema is None:
            # Plan B is to assume we're dealing with a file
            schema = 'file'
            url = '{}://{}'.format(schema, URLBase.quote(url))

        else:
            # Ensure our schema is always in lower case
            schema = schema.group('schema').lower()

            # Some basic validation
            if schema not in A_MGR:
                logger.warning('Unsupported schema {}.'.format(schema))
                return None

        # Parse our url details of the server object as dictionary containing
        # all of the information parsed from our URL
        results = A_MGR[schema].parse_url(url)

        if not results:
            # Failed to parse the server URL
            logger.warning('Unparseable URL {}.'.format(url))
            return None

        # Prepare our Asset Object
        results['asset'] = \
            asset if isinstance(asset, AppriseAsset) else AppriseAsset()

        if cache is not None:
            # Force an over-ride of the cache value to what we have specified
            results['cache'] = cache

        if suppress_exceptions:
            try:
                # Attempt to create an instance of our plugin using the parsed
                # URL information
                attach_plugin = A_MGR[results['schema']](**results)

            except Exception:
                # the arguments are invalid or can not be used.
                logger.warning('Could not load URL: %s' % url)
                return None

        else:
            # Attempt to create an instance of our plugin using the parsed
            # URL information but don't wrap it in a try catch
            attach_plugin = A_MGR[results['schema']](**results)

        return attach_plugin

    def clear(self):
        """
        Empties our attachment list

        """
        self.attachments[:] = []

    def size(self):
        """
        Returns the total size of accumulated attachments
        """
        return sum([len(a) for a in self.attachments if len(a) > 0])

    def pop(self, index=-1):
        """
        Removes an indexed Apprise Attachment from the stack and returns it.

        by default the last element is poped from the list
        """
        # Remove our entry
        return self.attachments.pop(index)

    def __getitem__(self, index):
        """
        Returns the indexed entry of a loaded apprise attachments
        """
        return self.attachments[index]

    def __bool__(self):
        """
        Allows the Apprise object to be wrapped in an 'if statement'.
        True is returned if at least one service has been loaded.
        """
        return True if self.attachments else False

    def __iter__(self):
        """
        Returns an iterator to our attachment list
        """
        return iter(self.attachments)

    def __len__(self):
        """
        Returns the number of attachment entries loaded
        """
        return len(self.attachments)
