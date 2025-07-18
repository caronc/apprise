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
import re
import urllib

import pytest

from apprise import AppriseAttachment, exception
from apprise.attachment.base import AttachBase
from apprise.attachment.memory import AttachMemory
from apprise.common import ContentLocation

logging.disable(logging.CRITICAL)


def test_attach_memory_parse_url():
    """
    API: AttachMemory().parse_url()

    """

    # Bad Entry
    assert AttachMemory.parse_url(object) is None

    # Our filename is detected automatically
    assert AttachMemory.parse_url("memory://")

    # pass our content in as a string
    mem = AttachMemory(content="string")
    # it loads a string type by default
    assert mem.mimetype == "text/plain"
    # Our filename is automatically generated (with .txt)
    assert re.match(r"^[a-z0-9-]+\.txt$", mem.name, re.I)

    # open our file
    with mem as fp:
        assert fp.getbuffer().nbytes == len(mem)

    # pass our content in as a string
    mem = AttachMemory(
        content="<html/>", name="test.html", mimetype="text/html"
    )
    # it loads a string type by default
    assert mem.mimetype == "text/html"
    assert mem.name == "test.html"

    # Stub function
    assert mem.download()

    with pytest.raises(TypeError):
        # garbage in, garbage out
        AttachMemory(content=3)

    # pointer to our data
    pointer = mem.open()
    assert pointer.read() == b"<html/>"

    # pass our content in as a string
    mem = AttachMemory(content=b"binary-data", name="raw.dat")
    # it loads a string type by default
    assert mem.mimetype == "application/octet-stream"
    assert mem.name == "raw.dat"

    # pass our content in as a string
    mem = AttachMemory(content=b"binary-data")
    # it loads a string type by default
    assert mem.mimetype == "application/octet-stream"
    # Our filename is automatically generated (with .dat)
    assert re.match(r"^[a-z0-9-]+\.dat$", mem.name, re.I)


def test_attach_memory():
    """
    API: AttachMemory()

    """
    # A url we can test with
    fname = "testfile"
    url = f"memory:///ignored/path/{fname}"

    # Simple gif test
    response = AppriseAttachment.instantiate(url)
    assert isinstance(response, AttachMemory)

    # There is no path yet as we haven't written anything to our memory object
    # yet
    assert response.path is None
    assert bool(response) is False

    with response as memobj:
        memobj.write(b"content")

    # Memory object defaults
    assert response.name == fname
    assert response.path == response.name
    assert response.mimetype == "application/octet-stream"
    assert bool(response) is True

    #
    fname_in_url = urllib.parse.quote(response.name)
    assert response.url().startswith(f"memory://{fname_in_url}")

    # Mime is always part of url
    assert re.search(r"[?&]mime=", response.url()) is not None

    # Test case where location is simply set to INACCESSIBLE
    # Below is a bad example, but it proves the section of code properly works.
    # Ideally a server admin may wish to just disable all File based
    # attachments entirely. In this case, they simply just need to change the
    # global singleton at the start of their program like:
    #
    # import apprise
    # apprise.attachment.AttachMemory.location = \
    #       apprise.ContentLocation.INACCESSIBLE
    #
    response = AppriseAttachment.instantiate(url)
    assert isinstance(response, AttachMemory)
    with response as memobj:
        memobj.write(b"content")

    response.location = ContentLocation.INACCESSIBLE
    assert response.path is None
    # Downloads just don't work period
    assert response.download() is False

    # File handling (even if image is set to maxium allowable)
    response = AppriseAttachment.instantiate(url)
    assert isinstance(response, AttachMemory)
    with response as memobj:
        memobj.write(b"content")

    # Memory handling when size is to large
    response = AppriseAttachment.instantiate(url)
    assert isinstance(response, AttachMemory)
    with response as memobj:
        memobj.write(b"content")

    # Test case where we exceed our defined max_file_size in memory
    prev_value = AttachBase.max_file_size
    AttachBase.max_file_size = len(response) - 1
    # We can't work in this case
    assert response.path is None
    assert response.download() is False

    # Restore our file_size
    AttachBase.max_file_size = prev_value

    response = AppriseAttachment.instantiate(
        "memory://apprise-file.gif?mime=image/gif"
    )
    assert isinstance(response, AttachMemory)
    with response as memobj:
        memobj.write(b"content")

    assert response.name == "apprise-file.gif"
    assert response.path == response.name
    assert response.mimetype == "image/gif"
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r"[?&]mime=", response.url()) is not None
    assert "image/gif" in response.url()

    # Force a mime-type and new name
    response = AppriseAttachment.instantiate(
        "memory://{}?mime={}&name={}".format(
            "ignored.gif", "image/jpeg", "test.jpeg"
        )
    )
    assert isinstance(response, AttachMemory)
    with response as memobj:
        memobj.write(b"content")

    assert response.name == "test.jpeg"
    assert response.path == response.name
    assert response.mimetype == "image/jpeg"
    # We will match on mime type now  (%2F = /)
    assert re.search(r"[?&]mime=image/jpeg", response.url(), re.I)
    assert response.url().startswith("memory://test.jpeg")

    # Test hosted configuration and that we can't add a valid memory file
    aa = AppriseAttachment(location=ContentLocation.HOSTED)
    assert aa.add(response) is False

    # now test our base64 output
    assert isinstance(response.base64(), str)
    # No encoding if we choose
    assert isinstance(response.base64(encoding=None), bytes)

    response.invalidate()
    with pytest.raises(exception.AppriseFileNotFound):
        response.base64()
