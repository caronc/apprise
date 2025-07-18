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

# Disable logging for a cleaner testing output
import logging
import mimetypes
from os.path import dirname, getsize, join
import re
from typing import ClassVar
from unittest import mock

import pytest
import requests

from apprise import Apprise, AppriseAttachment, NotificationManager, exception
from apprise.attachment.http import AttachHTTP
from apprise.common import ContentLocation
from apprise.plugins import NotifyBase

logging.disable(logging.CRITICAL)

TEST_VAR_DIR = join(dirname(__file__), "var")

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()

# Some exception handling we'll use
REQUEST_EXCEPTIONS = (
    requests.ConnectionError(0, "requests.ConnectionError() not handled"),
    requests.RequestException(0, "requests.RequestException() not handled"),
    requests.HTTPError(0, "requests.HTTPError() not handled"),
    requests.ReadTimeout(0, "requests.ReadTimeout() not handled"),
    requests.TooManyRedirects(0, "requests.TooManyRedirects() not handled"),
    # Throw OSError exceptions too
    OSError("SystemError"),
)


def test_attach_http_parse_url():
    """
    API: AttachHTTP().parse_url()

    """

    # bad entry
    assert AttachHTTP.parse_url("garbage://") is None

    # no url specified
    assert AttachHTTP.parse_url("http://") is None


def test_attach_http_query_string_dictionary():
    """
    API: AttachHTTP() Query String Dictionary

    """

    # Set verify off
    results = AttachHTTP.parse_url("http://localhost?verify=no&rto=9&cto=8")
    assert isinstance(results, dict)

    # Create our object
    obj = AttachHTTP(**results)
    assert isinstance(obj, AttachHTTP)

    # verify is disabled and therefore set
    assert re.search(r"[?&]verify=no", obj.url())

    # Our connect timeout flag is set since it differs from the default
    assert re.search(r"[?&]cto=8", obj.url())
    # Our read timeout flag is set since it differs from the default
    assert re.search(r"[?&]rto=9", obj.url())

    # Now lets create a URL with a custom Query String entry

    # some custom qsd entries specified
    results = AttachHTTP.parse_url("http://localhost?dl=1&_var=test")
    assert isinstance(results, dict)

    # Create our object
    obj = AttachHTTP(**results)
    assert isinstance(obj, AttachHTTP)

    # verify is not in the URL as it is implied (default)
    assert not re.search(r"[?&]verify=yes", obj.url())

    # But now test that our custom arguments have also been set
    assert re.search(r"[?&]dl=1", obj.url())
    assert re.search(r"[?&]_var=test", obj.url())


@mock.patch("requests.post")
@mock.patch("requests.get")
def test_attach_http(mock_get, mock_post):
    """
    API: AttachHTTP() object

    """

    # Define our good:// url
    class GoodNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self):
            # Support url() function
            return ""

    # Store our good notification in our schema map
    N_MGR["good"] = GoodNotification

    # Temporary path
    path = join(TEST_VAR_DIR, "apprise-test.gif")

    class DummyResponse:
        """A dummy response used to manage our object."""

        status_code = requests.codes.ok
        headers: ClassVar[dict[str, str]] = {
            "Content-Length": getsize(path),
            "Content-Type": "text/plain",
        }

        # Pointer to file
        ptr = None

        # used to return random keep-alive chunks
        _keepalive_chunk_ref = 0

        def close(self):
            return

        def iter_content(self, chunk_size=1024):
            """Lazy function (generator) to read a file piece by piece.

            Default chunk size: 1k.
            """

            while True:
                self._keepalive_chunk_ref += 1
                if 16 % self._keepalive_chunk_ref == 0:
                    # Yield a keep-alive block
                    yield ""

                data = self.ptr.read(chunk_size)
                if not data:
                    break
                yield data

        def raise_for_status(self):
            return

        def __enter__(self):
            self.ptr = open(path, "rb")
            return self

        def __exit__(self, *args, **kwargs):
            self.ptr.close()

    # Prepare Mock
    dummy_response = DummyResponse()
    mock_get.return_value = dummy_response

    # Test custom url get parameters
    results = AttachHTTP.parse_url(
        "http://user:pass@localhost/apprise.gif?DL=1&cache=300"
    )
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True

    # Test that our extended variables are passed along
    assert mock_get.call_count == 0
    assert attachment
    assert mock_get.call_count == 1
    assert "params" in mock_get.call_args_list[0][1]
    assert "DL" in mock_get.call_args_list[0][1]["params"]

    # Verify that arguments that are reserved for apprise are not
    # passed along
    assert "cache" not in mock_get.call_args_list[0][1]["params"]

    with mock.patch("os.unlink", side_effect=OSError()):
        # Test invalidation with exception thrown
        attachment.invalidate()

    results = AttachHTTP.parse_url(
        "http://user:pass@localhost/apprise.gif?+key=value&cache=True"
    )
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None
    # No Content-Disposition; so we use filename from path
    assert attachment.name == "apprise.gif"
    # Format is text/plain because of the Content-Type in the HTTP Query
    assert attachment.mimetype == "text/plain"

    # To get our desired effect, we'd have to have had to detect everything
    attachment.detected_mimetype = None
    attachment._mimetype = None

    # Now a call would yield a detected result that we'd agree with:
    assert attachment.mimetype == "image/gif"

    # had it not been there and it was forced to detect it on it's own
    # we would have had a different result; the below forces it to detect it
    # again:
    attachment.detected_mimetype = None

    # Now we get what we would have expected:
    assert attachment.mimetype == "image/gif"

    results = AttachHTTP.parse_url(
        "http://localhost:3000/noname.gif?name=usethis.jpg&mime=image/jpeg"
    )
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # both mime and name over-ridden
    assert re.search(r"[?&]mime=image/jpeg", attachment.url())
    assert re.search(r"[?&]name=usethis.jpg", attachment.url())
    # No Content-Disposition; so we use filename from path
    assert attachment.name == "usethis.jpg"
    assert attachment.mimetype == "image/jpeg"

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
    results = AttachHTTP.parse_url("http://localhost")
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None
    # Format is text/plain because of the Content-Type in the HTTP Query
    assert attachment.mimetype == "text/plain"

    # To get our desired effect, we'd have to have had to detect everything
    attachment.detected_mimetype = None
    attachment._mimetype = None

    # Now we are unable to detect our file without enough data to do it with
    assert attachment.mimetype == "application/octet-stream"

    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert (
        attachment.name
        == f"{AttachHTTP.unknown_filename}"
        f"{mimetypes.guess_extension(attachment.mimetype)}"
    )
    assert attachment
    assert len(attachment) == getsize(path)

    # Set Content-Length to a value that exceeds our maximum allowable
    dummy_response.headers["Content-Length"] = AttachHTTP.max_file_size + 1
    results = AttachHTTP.parse_url("http://localhost/toobig.jpg")
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    # we can not download this attachment
    assert not attachment
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None
    assert attachment.mimetype is None
    assert attachment.name is None
    assert len(attachment) == 0

    # Handle cases where we have no Content-Length and we need to rely
    # on what is read as it is streamed
    del dummy_response.headers["Content-Length"]
    # No path specified
    # No Content-Disposition specified
    # No Content-Length specified
    # No filename (because no path)
    results = AttachHTTP.parse_url("http://localhost/no-length.gif")
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None

    # Format is text/plain because of the Content-Type in the HTTP Query
    assert attachment.mimetype == "text/plain"

    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == "no-length.gif"
    assert attachment
    assert len(attachment) == getsize(path)

    # Set our limit to be the length of our image; everything should work
    # without a problem
    max_file_size = AttachHTTP.max_file_size
    AttachHTTP.max_file_size = getsize(path)
    # Set ourselves a Content-Disposition (providing a filename)
    dummy_response.headers["Content-Disposition"] = (
        'attachment; filename="myimage.gif"'
    )
    # Remove our content type so we're forced to guess it from our filename
    # specified in our Content-Disposition
    del dummy_response.headers["Content-Type"]
    # No path specified
    # No Content-Length specified
    # Filename in Content-Disposition (over-rides one found in path
    results = AttachHTTP.parse_url("http://user@localhost/ignore-filename.gif")
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None
    assert attachment.mimetype == "image/gif"
    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == "myimage.gif"
    assert attachment
    assert len(attachment) == getsize(path)

    # Similar to test above except we make our max message size just 1 byte
    # smaller then our gif file. This will cause us to fail to read the
    # attachment
    AttachHTTP.max_file_size = getsize(path) - 1
    results = AttachHTTP.parse_url("http://localhost/toobig.jpg")
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    # we can not download this attachment
    assert not attachment
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None
    assert attachment.mimetype is None
    assert attachment.name is None
    assert len(attachment) == 0

    # Disable our file size limitations
    AttachHTTP.max_file_size = 0
    results = AttachHTTP.parse_url("http://user@localhost")
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None
    assert attachment.mimetype == "image/gif"
    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == "myimage.gif"
    assert attachment
    assert len(attachment) == getsize(path)

    # Set our header up with an invalid Content-Length; we can still process
    # this data. It just means we track it lower when reading back content
    dummy_response.headers = {"Content-Length": "invalid"}
    results = AttachHTTP.parse_url("http://localhost/invalid-length.gif")
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None
    assert attachment.mimetype == "image/gif"
    # Because we could determine our mime type, we could build an extension
    # for our unknown filename
    assert attachment.name == "invalid-length.gif"
    assert attachment

    # Give ourselves nothing to work with
    dummy_response.headers = {}
    results = AttachHTTP.parse_url("http://user@localhost")
    assert isinstance(results, dict)
    attachment = AttachHTTP(**results)
    # we can not download this attachment
    assert attachment
    assert isinstance(attachment.url(), str) is True
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", attachment.url()) is None
    assert re.search(r"[?&]name=", attachment.url()) is None

    # Handle edge-case where detected_name is None for whatever reason
    attachment.detected_name = None
    assert attachment.mimetype == attachment.unknown_mimetype
    assert attachment.name.startswith(AttachHTTP.unknown_filename)
    assert len(attachment) == getsize(path)

    # Exception handling
    mock_get.return_value = None
    for _exception in REQUEST_EXCEPTIONS:
        aa = AppriseAttachment.instantiate(
            "http://localhost/exception.gif?cache=30"
        )
        assert isinstance(aa, AttachHTTP)

        mock_get.side_effect = _exception
        assert not aa

    # Restore value
    AttachHTTP.max_file_size = max_file_size

    # Multi Message Testing
    mock_get.side_effect = None
    mock_get.return_value = DummyResponse()

    # Prepare our POST response (from notify call)
    response = requests.Request()
    response.status_code = requests.codes.ok
    response.content = ""
    mock_post.return_value = response

    mock_get.reset_mock()
    mock_post.reset_mock()
    assert mock_get.call_count == 0

    apobj = Apprise()
    assert apobj.add("form://localhost")
    assert apobj.add("json://localhost")
    assert apobj.add("xml://localhost")
    assert len(apobj) == 3
    assert (
        apobj.notify(
            body="one attachment split 3 times",
            attach="http://localhost/test.gif",
        )
        is True
    )

    # We posted 3 times
    assert mock_post.call_count == 3
    # We only fetched once and re-used the same fetch for all posts
    assert mock_get.call_count == 1

    mock_get.reset_mock()
    mock_post.reset_mock()
    apobj = Apprise()
    for n in range(10):
        assert apobj.add(f"json://localhost?:entry={n}&method=post")
        assert apobj.add(f"form://localhost?:entry={n}&method=post")
        assert apobj.add(f"xml://localhost?:entry={n}&method=post")

    assert (
        apobj.notify(
            body="one attachment split 30 times",
            attach="http://localhost/test.gif",
        )
        is True
    )

    # We posted 30 times
    assert mock_post.call_count == 30
    # We only fetched once and re-used the same fetch for all posts
    assert mock_get.call_count == 1

    #
    # We will test our base64 handling now
    #
    mock_get.reset_mock()
    mock_post.reset_mock()

    AttachHTTP.max_file_size = getsize(path)
    # Set ourselves a Content-Disposition (providing a filename)
    dummy_response.headers["Content-Disposition"] = (
        'attachment; filename="myimage.gif"'
    )
    results = AttachHTTP.parse_url("http://user@localhost/filename.gif")
    assert isinstance(results, dict)
    obj = AttachHTTP(**results)

    # now test our base64 output
    assert isinstance(obj.base64(), str)
    # No encoding if we choose
    assert isinstance(obj.base64(encoding=None), bytes)

    # Error cases:
    with mock.patch(
        "builtins.open",
        new_callable=mock.mock_open,
        read_data="mocked file content",
    ) as mock_file:
        mock_file.side_effect = FileNotFoundError
        with pytest.raises(exception.AppriseFileNotFound):
            obj.base64()

        mock_file.side_effect = OSError
        with pytest.raises(exception.AppriseDiskIOError):
            obj.base64()
