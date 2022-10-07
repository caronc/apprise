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

import re
from unittest import mock

import requests
import mimetypes
from os.path import join
from os.path import dirname
from os.path import getsize
from apprise.attachment.AttachHTTP import AttachHTTP
from apprise import AppriseAttachment
from apprise.plugins.NotifyBase import NotifyBase
from apprise.common import NOTIFY_SCHEMA_MAP
from apprise.common import ContentLocation

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

TEST_VAR_DIR = join(dirname(__file__), 'var')

# Some exception handling we'll use
REQUEST_EXCEPTIONS = (
    requests.ConnectionError(
        0, 'requests.ConnectionError() not handled'),
    requests.RequestException(
        0, 'requests.RequestException() not handled'),
    requests.HTTPError(
        0, 'requests.HTTPError() not handled'),
    requests.ReadTimeout(
        0, 'requests.ReadTimeout() not handled'),
    requests.TooManyRedirects(
        0, 'requests.TooManyRedirects() not handled'),

    # Throw OSError exceptions too
    OSError("SystemError")
)


def test_attach_http_parse_url():
    """
    API: AttachHTTP().parse_url()

    """

    # bad entry
    assert AttachHTTP.parse_url('garbage://') is None

    # no url specified
    assert AttachHTTP.parse_url('http://') is None


def test_attach_http_query_string_dictionary():
    """
    API: AttachHTTP() Query String Dictionary

    """

    # no qsd specified
    results = AttachHTTP.parse_url('http://localhost')
    assert isinstance(results, dict)

    # Create our object
    obj = AttachHTTP(**results)
    assert isinstance(obj, AttachHTTP)

    assert re.search(r'[?&]verify=yes', obj.url())

    # Now lets create a URL with a custom Query String entry

    # some custom qsd entries specified
    results = AttachHTTP.parse_url('http://localhost?dl=1&_var=test')
    assert isinstance(results, dict)

    # Create our object
    obj = AttachHTTP(**results)
    assert isinstance(obj, AttachHTTP)

    assert re.search(r'[?&]verify=yes', obj.url())

    # But now test that our custom arguments have also been set
    assert re.search(r'[?&]dl=1', obj.url())
    assert re.search(r'[?&]_var=test', obj.url())


@mock.patch('requests.get')
def test_attach_http(mock_get):
    """
    API: AttachHTTP() object

    """

    # Define our good:// url
    class GoodNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super(GoodNotification, self).__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self):
            # Support url() function
            return ''

    # Store our good notification in our schema map
    NOTIFY_SCHEMA_MAP['good'] = GoodNotification

    # Temporary path
    path = join(TEST_VAR_DIR, 'apprise-test.gif')

    class DummyResponse:
        """
        A dummy response used to manage our object
        """
        status_code = requests.codes.ok
        headers = {
            'Content-Length': getsize(path),
            'Content-Type': 'image/gif',
        }

        # Pointer to file
        ptr = None

        # used to return random keep-alive chunks
        _keepalive_chunk_ref = 0

        def close(self):
            return

        def iter_content(self, chunk_size=1024):
            """Lazy function (generator) to read a file piece by piece.
            Default chunk size: 1k."""

            while True:
                self._keepalive_chunk_ref += 1
                if 16 % self._keepalive_chunk_ref == 0:
                    # Yield a keep-alive block
                    yield ''

                data = self.ptr.read(chunk_size)
                if not data:
                    break
                yield data

        def raise_for_status(self):
            return

        def __enter__(self):
            self.ptr = open(path, 'rb')
            return self

        def __exit__(self, *args, **kwargs):
            self.ptr.close()

    # Prepare Mock
    dummy_response = DummyResponse()
    mock_get.return_value = dummy_response

    # Test custom url get parameters
    results = AttachHTTP.parse_url(
        'http://user:pass@localhost/apprise.gif?dl=1&cache=300')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True

    # Test that our extended variables are passed along
    assert mock_get.call_count == 0
    assert attachment
    assert mock_get.call_count == 1
    assert 'params' in mock_get.call_args_list[0][1]
    assert 'dl' in mock_get.call_args_list[0][1]['params']

    # Verify that arguments that are reserved for apprise are not
    # passed along
    assert 'cache' not in mock_get.call_args_list[0][1]['params']

    results = AttachHTTP.parse_url(
        'http://user:pass@localhost/apprise.gif?+key=value&cache=True')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None
    # No Content-Disposition; so we use filename from path
    assert attachment.name == 'apprise.gif'
    assert attachment.mimetype == 'image/gif'

    results = AttachHTTP.parse_url(
        'http://localhost:3000/noname.gif?name=usethis.jpg&mime=image/jpeg')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # both mime and name over-ridden
    assert re.search(r'[?&]mime=image%2Fjpeg', attachment.url())
    assert re.search(r'[?&]name=usethis.jpg', attachment.url())
    # No Content-Disposition; so we use filename from path
    assert attachment.name == 'usethis.jpg'
    assert attachment.mimetype == 'image/jpeg'

    # Edge case; download called a second time when content already retrieved
    assert attachment.download()
    assert attachment
    assert len(attachment) == getsize(path)

    # Test case where location is simply set to INACCESSIBLE
    # Below is a bad example, but it proves the section of code properly works.
    # Ideally a server admin may wish to just disable all HTTP based
    # attachments entirely. In this case, they simply just need to change the
    # global singleton at the start of their program like:
    #
    # import apprise
    # apprise.attachment.AttachHTTP.location = \
    #       apprise.ContentLocation.INACCESSIBLE
    attachment = AttachHTTP(**results)
    attachment.location = ContentLocation.INACCESSIBLE
    assert attachment.path is None
    # Downloads just don't work period
    assert attachment.download() is False

    # No path specified
    # No Content-Disposition specified
    # No filename (because no path)
    results = AttachHTTP.parse_url('http://localhost')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None
    assert attachment.mimetype == 'image/gif'
    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == '{}{}'.format(
        AttachHTTP.unknown_filename,
        mimetypes.guess_extension(attachment.mimetype)
    )
    assert attachment
    assert len(attachment) == getsize(path)

    # Set Content-Length to a value that exceeds our maximum allowable
    dummy_response.headers['Content-Length'] = AttachHTTP.max_file_size + 1
    results = AttachHTTP.parse_url('http://localhost/toobig.jpg')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    # we can not download this attachment
    assert not attachment
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None
    assert attachment.mimetype is None
    assert attachment.name is None
    assert len(attachment) == 0

    # Handle cases where we have no Content-Length and we need to rely
    # on what is read as it is streamed
    del dummy_response.headers['Content-Length']
    # No path specified
    # No Content-Disposition specified
    # No Content-Length specified
    # No filename (because no path)
    results = AttachHTTP.parse_url('http://localhost/no-length.gif')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None
    assert attachment.mimetype == 'image/gif'
    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == 'no-length.gif'
    assert attachment
    assert len(attachment) == getsize(path)

    # Set our limit to be the length of our image; everything should work
    # without a problem
    max_file_size = AttachHTTP.max_file_size
    AttachHTTP.max_file_size = getsize(path)
    # Set ourselves a Content-Disposition (providing a filename)
    dummy_response.headers['Content-Disposition'] = \
        'attachment; filename="myimage.gif"'
    # Remove our content type so we're forced to guess it from our filename
    # specified in our Content-Disposition
    del dummy_response.headers['Content-Type']
    # No path specified
    # No Content-Length specified
    # Filename in Content-Disposition (over-rides one found in path
    results = AttachHTTP.parse_url('http://user@localhost/ignore-filename.gif')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None
    assert attachment.mimetype == 'image/gif'
    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == 'myimage.gif'
    assert attachment
    assert len(attachment) == getsize(path)

    # Similar to test above except we make our max message size just 1 byte
    # smaller then our gif file. This will cause us to fail to read the
    # attachment
    AttachHTTP.max_file_size = getsize(path) - 1
    results = AttachHTTP.parse_url('http://localhost/toobig.jpg')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    # we can not download this attachment
    assert not attachment
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None
    assert attachment.mimetype is None
    assert attachment.name is None
    assert len(attachment) == 0

    # Disable our file size limitations
    AttachHTTP.max_file_size = 0
    results = AttachHTTP.parse_url('http://user@localhost')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None
    assert attachment.mimetype == 'image/gif'
    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == 'myimage.gif'
    assert attachment
    assert len(attachment) == getsize(path)

    # Set our header up with an invalid Content-Length; we can still process
    # this data. It just means we track it lower when reading back content
    dummy_response.headers = {
        'Content-Length': 'invalid'
    }
    results = AttachHTTP.parse_url('http://localhost/invalid-length.gif')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None
    assert attachment.mimetype == 'image/gif'
    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == 'invalid-length.gif'
    assert attachment

    # Give ourselves nothing to work with
    dummy_response.headers = {}
    results = AttachHTTP.parse_url('http://user@localhost')
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    # we can not download this attachment
    assert attachment
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', attachment.url()) is None
    assert re.search(r'[?&]name=', attachment.url()) is None

    # Handle edge-case where detected_name is None for whatever reason
    attachment.detected_name = None
    assert attachment.mimetype == attachment.unknown_mimetype
    assert attachment.name.startswith(AttachHTTP.unknown_filename)
    assert len(attachment) == getsize(path)

    # Exception handling
    mock_get.return_value = None
    for _exception in REQUEST_EXCEPTIONS:
        aa = AppriseAttachment.instantiate(
            'http://localhost/exception.gif?cache=30')
        assert isinstance(aa, AttachHTTP)

        mock_get.side_effect = _exception
        assert not aa

    # Restore value
    AttachHTTP.max_file_size = max_file_size
