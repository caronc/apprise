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
import time
from unittest import mock

from os.path import dirname
from os.path import join
from apprise.attachment.AttachBase import AttachBase
from apprise.attachment.AttachFile import AttachFile
from apprise import AppriseAttachment
from apprise.common import ContentLocation

# Disable logging for a cleaner testing output
import logging
logging.disable(logging.CRITICAL)

TEST_VAR_DIR = join(dirname(__file__), 'var')


def test_attach_file_parse_url():
    """
    API: AttachFile().parse_url()

    """

    # bad entry
    assert AttachFile.parse_url('garbage://') is None

    # no file path specified
    assert AttachFile.parse_url('file://') is None


def test_file_expiry(tmpdir):
    """
    API: AttachFile Expiry
    """
    path = join(TEST_VAR_DIR, 'apprise-test.gif')
    image = tmpdir.mkdir("apprise_file").join("test.jpg")
    with open(path, 'rb') as data:
        image.write(data)

    aa = AppriseAttachment.instantiate(str(image), cache=30)

    # Our file is now available
    assert aa.exists()

    # Our second call has the file already downloaded, but now compares
    # it's date against when we consider it to have expire.  We're well
    # under 30 seconds here (our set value), so this will succeed
    assert aa.exists()

    with mock.patch('time.time', return_value=time.time() + 31):
        # This will force a re-download as our cache will have
        # expired
        assert aa.exists()

    with mock.patch('time.time', side_effect=OSError):
        # We will throw an exception
        assert aa.exists()


def test_attach_file():
    """
    API: AttachFile()

    """
    # Simple gif test
    path = join(TEST_VAR_DIR, 'apprise-test.gif')
    response = AppriseAttachment.instantiate(path)
    assert isinstance(response, AttachFile)
    assert response.path == path
    assert response.name == 'apprise-test.gif'
    assert response.mimetype == 'image/gif'
    # Download is successful and has already been called by now; below pulls
    # results from cache
    assert response.download()
    assert response.url().startswith('file://{}'.format(path))
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', response.url()) is None
    assert re.search(r'[?&]name=', response.url()) is None

    # Test case where location is simply set to INACCESSIBLE
    # Below is a bad example, but it proves the section of code properly works.
    # Ideally a server admin may wish to just disable all File based
    # attachments entirely. In this case, they simply just need to change the
    # global singleton at the start of their program like:
    #
    # import apprise
    # apprise.attachment.AttachFile.location = \
    #       apprise.ContentLocation.INACCESSIBLE
    #
    response = AppriseAttachment.instantiate(path)
    assert isinstance(response, AttachFile)
    response.location = ContentLocation.INACCESSIBLE
    assert response.path is None
    # Downloads just don't work period
    assert response.download() is False

    # File handling (even if image is set to maxium allowable)
    response = AppriseAttachment.instantiate(path)
    assert isinstance(response, AttachFile)
    with mock.patch('os.path.getsize', return_value=AttachBase.max_file_size):
        # It will still work
        assert response.path == path

    # File handling when size is to large
    response = AppriseAttachment.instantiate(path)
    assert isinstance(response, AttachFile)
    with mock.patch(
            'os.path.getsize', return_value=AttachBase.max_file_size + 1):
        # We can't work in this case
        assert response.path is None

    # File handling when image is not available
    response = AppriseAttachment.instantiate(path)
    assert isinstance(response, AttachFile)
    with mock.patch('os.path.isfile', return_value=False):
        # This triggers a full check and will fail the isfile() check
        assert response.path is None

    # The call to AttachBase.path automatically triggers a call to download()
    # but this same is done with a call to AttachBase.name as well.  Above
    # test cases reference 'path' right after instantiation; here we reference
    # 'name'
    response = AppriseAttachment.instantiate(path)
    assert response.name == 'apprise-test.gif'
    assert response.path == path
    assert response.mimetype == 'image/gif'
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', response.url()) is None
    assert re.search(r'[?&]name=', response.url()) is None

    # continuation to cheking 'name' instead of 'path' first where our call
    # to download() fails
    response = AppriseAttachment.instantiate(path)
    assert isinstance(response, AttachFile)
    with mock.patch('os.path.isfile', return_value=False):
        # This triggers a full check and will fail the isfile() check
        assert response.name is None

    # The call to AttachBase.path automatically triggers a call to download()
    # but this same is done with a call to AttachBase.mimetype as well.  Above
    # test cases reference 'path' right after instantiation; here we reference
    # 'mimetype'
    response = AppriseAttachment.instantiate(path)
    assert response.mimetype == 'image/gif'
    assert response.name == 'apprise-test.gif'
    assert response.path == path
    # No mime-type and/or filename over-ride was specified, so therefore it
    # won't show up in the generated URL
    assert re.search(r'[?&]mime=', response.url()) is None
    assert re.search(r'[?&]name=', response.url()) is None

    # continuation to cheking 'name' instead of 'path' first where our call
    # to download() fails
    response = AppriseAttachment.instantiate(path)
    assert isinstance(response, AttachFile)
    with mock.patch('os.path.isfile', return_value=False):
        # download() fails so we don't have a mimetpe
        assert response.mimetype is None
        assert response.name is None
        assert response.path is None
        # This triggers a full check and will fail the isfile() check

    # Force a mime-type and new name
    response = AppriseAttachment.instantiate(
        'file://{}?mime={}&name={}'.format(path, 'image/jpeg', 'test.jpeg'))
    assert isinstance(response, AttachFile)
    assert response.path == path
    assert response.name == 'test.jpeg'
    assert response.mimetype == 'image/jpeg'
    # We will match on mime type now  (%2F = /)
    assert re.search(r'[?&]mime=image%2Fjpeg', response.url(), re.I)
    assert re.search(r'[?&]name=test\.jpeg', response.url(), re.I)

    # Test hosted configuration and that we can't add a valid file
    aa = AppriseAttachment(location=ContentLocation.HOSTED)
    assert aa.add(path) is False
