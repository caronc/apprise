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

# Disable logging for a cleaner testing output
import contextlib
import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import mimetypes
import os
from os.path import dirname, getsize, join
import re
import socket
import threading
import time
from typing import ClassVar
from unittest import mock

import pytest
import requests

from apprise import (
    Apprise,
    AppriseAsset,
    AppriseAttachment,
    NotificationManager,
    exception,
)
from apprise.attachment.http import AttachHTTP
from apprise.common import ContentLocation
from apprise.plugins import NotifyBase
from apprise.utils import http as http_utils
from apprise.utils.http import HTTPPolicy, HTTPPolicySession

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


def test_attach_http_encoded_path():
    """AttachHTTP() keeps an encoded path intact through url()."""

    # A GitLab style file path with encoded slashes
    url = "https://example.com/api/v4/projects/my%2Frepo/files/a%2Fb.txt"
    results = AttachHTTP.parse_url(url)
    attach = AttachHTTP(**results)
    assert attach.fullpath == "/api/v4/projects/my%2Frepo/files/a%2Fb.txt"

    # url() does not encode the path a second time
    assert attach.url().startswith(url + "?")


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


@mock.patch("requests.request")
@mock.patch("requests.Session.get")
def test_attach_http(mock_get, mock_request):
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

    # Detect the MIME type again without a Content-Type header.
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

    # Administrators can disable all HTTP attachments globally:
    #
    # import apprise
    # apprise.attachment.AttachHTTP.location = \
    #       apprise.ContentLocation.INACCESSIBLE
    attachment = AttachHTTP(**results)
    attachment.location = ContentLocation.INACCESSIBLE
    assert attachment.path is None
    # Downloads are blocked when HTTP attachments are inaccessible.
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
        attachment.name == f"{AttachHTTP.unknown_filename}"
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
    for exception_ in REQUEST_EXCEPTIONS:
        aa = AppriseAttachment.instantiate(
            "http://localhost/exception.gif?cache=30"
        )
        assert isinstance(aa, AttachHTTP)

        mock_get.side_effect = exception_
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
    mock_request.return_value = response

    mock_get.reset_mock()
    mock_request.reset_mock()
    assert mock_get.call_count == 0

    apobj = Apprise()
    assert apobj.add("form://localhost")
    assert apobj.add("json://localhost")
    assert apobj.add("xml://localhost")
    assert len(apobj) == 3
    assert (
        bool(
            apobj.notify(
                body="one attachment split 3 times",
                attach="http://localhost/test.gif",
            )
        )
        is True
    )

    # We posted 3 times
    assert mock_request.call_count == 3
    # We only fetched once and re-used the same fetch for all posts
    assert mock_get.call_count == 1

    mock_get.reset_mock()
    mock_request.reset_mock()
    apobj = Apprise()
    for n in range(10):
        assert apobj.add(f"json://localhost?:entry={n}&method=post")
        assert apobj.add(f"form://localhost?:entry={n}&method=post")
        assert apobj.add(f"xml://localhost?:entry={n}&method=post")

    assert (
        bool(
            apobj.notify(
                body="one attachment split 30 times",
                attach="http://localhost/test.gif",
            )
        )
        is True
    )

    # We posted 30 times
    assert mock_request.call_count == 30
    # We only fetched once and re-used the same fetch for all posts
    assert mock_get.call_count == 1

    #
    # We will test our base64 handling now
    #
    mock_get.reset_mock()
    mock_request.reset_mock()

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

    # Test that a 3xx redirect is rejected when redirect=no is set; a
    # status-code range guard (300-399) catches what raise_for_status() misses.
    class RedirectResponse:
        """Simulates a 301 response returned when allow_redirects=False."""

        status_code = requests.codes.moved_permanently
        headers: ClassVar[dict[str, str]] = {}

        def raise_for_status(self):
            return

        def __enter__(self):
            return self

        def __exit__(self, *args, **kwargs):
            return

    mock_get.return_value = RedirectResponse()
    results = AttachHTTP.parse_url(
        "http://user@localhost/filename.gif?redirect=no"
    )
    assert isinstance(results, dict)
    obj_no_redir = AttachHTTP(**results)
    assert obj_no_redir.redirects is False
    # Do not stream a redirect response when redirects are disabled.
    assert obj_no_redir.download() is False
    # Restore for downstream tests
    mock_get.return_value = dummy_response

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


class SizedResponse:
    """A dummy response that streams a fixed payload in small chunks."""

    status_code = requests.codes.ok
    headers: ClassVar[dict[str, str]] = {"Content-Type": "text/plain"}

    # The payload streamed back to the caller
    payload = b"abcdefghij"

    def close(self):
        return

    def iter_content(self, chunk_size=1024):
        """Stream our payload back 2 bytes at a time."""
        for index in range(0, len(self.payload), 2):
            yield self.payload[index : index + 2]

    def raise_for_status(self):
        return

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        return


@mock.patch("requests.Session.get")
def test_attach_http_download_dir(mock_get, tmpdir):
    """AttachHTTP writes downloads into the requested directory."""

    mock_get.return_value = SizedResponse()

    # Point our download at a directory of our own choosing
    download_dir = str(tmpdir.mkdir("attachments"))
    results = AttachHTTP.parse_url("http://localhost/file.txt")
    assert isinstance(results, dict)
    attachment = AttachHTTP(download_dir=download_dir, **results)
    assert attachment

    # Our content lives in the directory we asked for
    assert dirname(attachment.path) == download_dir
    assert len(attachment) == len(SizedResponse.payload)

    # Without a download_dir we fall back to the system temporary directory
    attachment = AttachHTTP(**results)
    assert attachment
    assert dirname(attachment.path) != download_dir


@mock.patch("requests.Session.get")
def test_attach_http_size_limit(mock_get):
    """AttachHTTP never writes more than max_file_size bytes."""

    mock_get.return_value = SizedResponse()

    # Track how large the file grew before it was thrown away
    written = []
    invalidate = AttachHTTP.invalidate

    def record(self):
        if self._temp_file:
            # tell() covers buffered writes that have not reached disk yet
            written.append(self._temp_file.tell())

        invalidate(self)

    results = AttachHTTP.parse_url("http://localhost/file.txt")
    assert isinstance(results, dict)

    with mock.patch.object(AttachHTTP, "invalidate", record):
        attachment = AttachHTTP(**results)

        # Allow 5 of the 10 bytes on offer
        attachment.max_file_size = 5

        # Our download fails because the payload is over our limit
        assert attachment.download() is False

    # Stop before the chunk that would cross the limit.
    assert written
    assert all(size <= 5 for size in written)
    assert written[0] == 4

    # A payload landing exactly on our limit is still accepted
    attachment = AttachHTTP(**results)
    attachment.max_file_size = len(SizedResponse.payload)
    assert attachment.download() is True
    assert len(attachment) == len(SizedResponse.payload)


@mock.patch("apprise.attachment.http.NamedTemporaryFile")
@mock.patch("requests.Session.get")
def test_attach_http_preserves_storage_error(mock_get, mock_temp_file):
    """Callers can inspect a download failure caused by local storage."""

    mock_get.return_value = SizedResponse()
    storage_error = OSError(errno.ENOSPC, "disk full")
    mock_temp_file.side_effect = storage_error

    results = AttachHTTP.parse_url("http://localhost/file.txt")
    attachment = AttachHTTP(**results)

    assert attachment.download() is False
    assert attachment.download_error is storage_error


def test_attach_http_trickle():
    """A server that trickles its file in is cut off once time is up."""
    stop = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()

            # One byte at a time, never long enough apart to trip the
            # read timeout
            with contextlib.suppress(OSError):
                while not stop.is_set():
                    self.wfile.write(b"x")
                    self.wfile.flush()
                    time.sleep(0.1)

        def log_message(self, _format, *args):
            # Keep the test server quiet.
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        results = AttachHTTP.parse_url(
            f"http://127.0.0.1:{server.server_port}/file.txt"
        )
        results["asset"] = AppriseAsset(service_timeout=0.5)
        attachment = AttachHTTP(**results)

        started = time.monotonic()
        assert attachment.download() is False

        # Without the limit this would never end; allow a slow machine
        assert time.monotonic() - started < 5.0
        assert attachment.path is None

    finally:
        stop.set()
        server.shutdown()
        thread.join()
        server.server_close()


@mock.patch("requests.Session.get")
def test_attach_http_time_limit(mock_get):
    """The download time limit can be turned off, and still stops a
    transport it cannot cut off between chunks."""

    class SlowResponse(SizedResponse):
        def iter_content(self, chunk_size=1024):
            # Ten times the limit, so the watchdog fires part way through
            # even on a slow machine
            time.sleep(1.0)
            yield from super().iter_content(chunk_size)

    mock_get.return_value = SlowResponse()
    results = AttachHTTP.parse_url("http://localhost/file.txt")

    # This response has no connection to cut off, but the download still
    # fails
    results["asset"] = AppriseAsset(service_timeout=0.1)
    attachment = AttachHTTP(**results)
    assert attachment.download() is False
    assert attachment.path is None

    # 0 turns the limit off
    results["asset"] = AppriseAsset(service_timeout=0)
    attachment = AttachHTTP(**results)
    assert attachment.download() is True
    assert len(attachment) == len(SizedResponse.payload)


@mock.patch("requests.Session.get")
def test_attach_http_late_reply(mock_get):
    """A reply that arrives just after time ran out is not used."""

    def late(*args, **kwargs):
        # Ten times the limit, so the watchdog fires before the reply exists
        # even on a slow machine
        time.sleep(1.0)
        return SizedResponse()

    mock_get.side_effect = late
    results = AttachHTTP.parse_url("http://localhost/file.txt")
    results["asset"] = AppriseAsset(service_timeout=0.1)
    attachment = AttachHTTP(**results)
    assert attachment.download() is False
    assert attachment.path is None


def _keepalive_server(stop, accepted):
    """Start a keep-alive server on 127.0.0.1 and return its listener.

    - ``/fast`` answers straight away.
    - ``/steady`` sends 30 bytes over 1.5 seconds.
    - ``/redirect`` sends the client to ``/slow`` on ``localhost``.
    - Anything else trickles its headers in far slower than any limit.
    - Each connection accepted is added to ``accepted``.
    """
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    port = listener.getsockname()[1]

    def handle(conn):
        with conn, contextlib.suppress(OSError):
            while not stop.is_set():
                request = conn.recv(4096)
                if not request:
                    return

                path = request.split(b" ")[1]
                if path == b"/fast":
                    conn.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok"
                    )

                elif path == b"/steady":
                    conn.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 30\r\n\r\n"
                    )
                    for _ in range(30):
                        conn.sendall(b"x")
                        time.sleep(0.05)

                elif path == b"/redirect":
                    conn.sendall(
                        b"HTTP/1.1 302 Found\r\nContent-Length: 0\r\n"
                        b"Location: http://localhost:"
                        + str(port).encode()
                        + b"/slow\r\n\r\n"
                    )

                else:
                    # One header byte at a time, never tripping the read
                    # timeout.  It would take over 8 minutes.
                    for byte in b"HTTP/1.1 200 OK\r\nX-Slow: " + b"y" * 10000:
                        if stop.is_set():
                            return

                        conn.sendall(bytes([byte]))
                        time.sleep(0.05)

    def serve():
        while True:
            try:
                conn, _ = listener.accept()

            except OSError:
                # The listener was closed because the test is over
                return

            accepted.append(conn)
            threading.Thread(target=handle, args=(conn,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    return listener


def test_attach_http_trickled_headers():
    """Every transport cuts off a server that trickles its headers."""
    stop = threading.Event()
    accepted = []
    listener = _keepalive_server(stop, accepted)
    port = listener.getsockname()[1]

    def download(session=None):
        results = AttachHTTP.parse_url(f"http://127.0.0.1:{port}/slow")
        results["asset"] = AppriseAsset(service_timeout=0.5)
        if session is not None:
            results["http_session"] = session

        started = time.monotonic()
        assert AttachHTTP(**results).download() is False

        # Ten times the limit, so a slow machine still passes
        assert time.monotonic() - started < 5.0

    try:
        # Requests' own transport
        download()

        # This test permits loopback only to exercise the transport locally.
        session = HTTPPolicySession(
            HTTPPolicy(address_filter=lambda _address: True)
        )

        # A connection the policy session opens for the download
        download(session)

        # A connection kept open from an earlier request
        assert session.get(f"http://127.0.0.1:{port}/fast").content == b"ok"
        before = len(accepted)
        download(session)
        assert len(accepted) == before

    finally:
        stop.set()
        listener.close()


def test_attach_http_trickled_proxy():
    """A proxy that trickles its answer is cut off as well."""
    stop = threading.Event()
    accepted = []
    listener = _keepalive_server(stop, accepted)
    proxy = f"http://127.0.0.1:{listener.getsockname()[1]}"

    # Only our proxy, whatever the machine running the tests has set
    environ = {
        key: value
        for key, value in os.environ.items()
        if key.lower()
        not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")
    }
    environ.update(http_proxy=proxy, https_proxy=proxy)

    try:
        with mock.patch.dict(os.environ, environ, clear=True):
            # A plain request, and one asking the proxy for a tunnel
            for url in (
                "http://apprise.invalid/slow",
                "https://apprise.invalid/slow",
            ):
                results = AttachHTTP.parse_url(url)
                results["asset"] = AppriseAsset(service_timeout=0.5)

                started = time.monotonic()
                assert AttachHTTP(**results).download() is False

                # Ten times the limit, so a slow machine still passes
                assert time.monotonic() - started < 5.0

        # Both went to the proxy
        assert len(accepted) == 2

    finally:
        stop.set()
        listener.close()


def test_attach_http_without_watchdog():
    """A download that cannot be timed is not attempted."""
    results = AttachHTTP.parse_url("http://localhost/file.txt")
    attachment = AttachHTTP(**results)
    with (
        mock.patch.object(http_utils, "_WATCHDOG", http_utils._Watchdog()),
        mock.patch("threading.Thread.start", side_effect=RuntimeError),
        mock.patch("requests.Session.get") as mock_get,
    ):
        assert attachment.download() is False

    assert attachment.path is None
    mock_get.assert_not_called()


def test_attach_http_runtime_error():
    """Other errors are not mistaken for a missing time limit."""
    results = AttachHTTP.parse_url("http://localhost/file.txt")
    with (
        mock.patch("requests.Session.get", side_effect=RuntimeError),
        pytest.raises(RuntimeError),
    ):
        AttachHTTP(**results).download()


def test_attach_http_shared_session():
    """Running out of time never cuts off another download's connection."""
    stop = threading.Event()
    accepted = []
    listener = _keepalive_server(stop, accepted)
    port = listener.getsockname()[1]

    # This test permits loopback only to exercise the transport locally.
    session = HTTPPolicySession(
        HTTPPolicy(address_filter=lambda _address: True)
    )

    def attachment(host, path, service_timeout):
        results = AttachHTTP.parse_url(f"http://{host}:{port}{path}")
        results["asset"] = AppriseAsset(service_timeout=service_timeout)
        results["http_session"] = session
        return AttachHTTP(**results)

    try:
        # The first download is redirected away from 127.0.0.1, and its
        # connection there goes back to the shared pool
        first = attachment("127.0.0.1", "/redirect", 0.5)
        result = {}
        thread = threading.Thread(
            target=lambda: result.update(first=first.download())
        )
        thread.start()
        time.sleep(0.15)

        # The second download takes that connection over, and is still
        # receiving when the first one runs out of time
        second = attachment("127.0.0.1", "/steady", 30)
        assert second.download() is True
        thread.join()

        assert result["first"] is False
        assert len(second) == 30

        # One connection to 127.0.0.1, shared, and one to localhost
        assert len(accepted) == 2

    finally:
        stop.set()
        listener.close()


def test_attach_http_slow_answer():
    """Waits for headers and redirects stay within the time limit."""
    stop = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # The URL's own query (such as rto=) is passed along; ignore it
            path = self.path.split("?")[0]
            if path == "/silent":
                # Say nothing for far longer than the time allowed
                stop.wait(10.0)

            elif path.startswith("/hop/") and path != "/hop/0":
                # Redirect to the next hop after a short pause
                stop.wait(0.15)
                self.send_response(302)
                self.send_header("Location", f"/hop/{int(path[5:]) - 1}")
                self.end_headers()
                return

            with contextlib.suppress(OSError):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")

        def log_message(self, _format, *args):
            # Keep the test server quiet.
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    def attachment(path, service_timeout):
        results = AttachHTTP.parse_url(
            f"http://127.0.0.1:{server.server_port}{path}?rto=30"
        )
        results["asset"] = AppriseAsset(service_timeout=service_timeout)
        return AttachHTTP(**results)

    try:
        # A server that keeps quiet is not waited on past the limit, even
        # with a long read timeout in the URL; it would take 10 seconds
        started = time.monotonic()
        assert attachment("/silent", 0.3).download() is False
        assert time.monotonic() - started < 5.0

        # A long chain of slow redirects is stopped once time is up; all
        # 60 of them would take 9 seconds
        started = time.monotonic()
        assert attachment("/hop/60", 0.5).download() is False
        assert time.monotonic() - started < 5.0

        # Without a limit, redirects are followed to the end
        download = attachment("/hop/2", 0)
        assert download.download() is True
        assert len(download) == 2

    finally:
        stop.set()
        server.shutdown()
        thread.join()
        server.server_close()


@mock.patch("requests.Session.get")
def test_attach_http_separate_locks(mock_get):
    """One attachment's download never waits on another's."""
    mock_get.return_value = SizedResponse()
    results = AttachHTTP.parse_url("http://localhost/file.txt")
    busy = AttachHTTP(**results)
    other = AttachHTTP(**results)
    assert busy._lock is not other._lock

    # Hold one attachment's lock, as a slow download would
    with busy._lock:
        assert other.download() is True
