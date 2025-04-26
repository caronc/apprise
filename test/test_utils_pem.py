# -*- coding: utf-8 -*-
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

import logging
import os

from apprise import AppriseAsset
from apprise import PersistentStoreMode
from apprise import utils

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), 'var')


def test_utils_pem_general(tmpdir):
    """
    Utils:PEM

    """

    tmpdir0 = tmpdir.mkdir('tmp00')

    # Currently no files here
    assert os.listdir(str(tmpdir0)) == []

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.MEMORY,
        storage_path=str(tmpdir0),
        pem_autogen=False,
    )

    # Create a PEM Controller
    pem_c = utils.pem.ApprisePEMController(path=None, asset=asset)

    # Nothing to lookup
    assert pem_c.public_keyfile() is None
    assert pem_c.public_key() is None
    assert pem_c.x962_str == ''
    assert pem_c.encrypt("message") is None
    # Keys can not be generated in memory mode
    assert pem_c.keygen() is False

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir0),
        pem_autogen=False,
    )

    # No new files
    assert os.listdir(str(tmpdir0)) == []

    # Our asset is now write mode, so we will be able to generate a key
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    # Nothing to lookup
    assert pem_c.public_keyfile() is None
    assert pem_c.public_key() is None
    assert pem_c.x962_str == ''
    assert pem_c.encrypt("message") is None

    # Keys can not be generated in memory mode
    assert pem_c.keygen() is True

    # We have 2 new key files generated
    assert os.listdir(str(tmpdir0)) == ['public_key.pem', 'private_key.pem']
    assert pem_c.public_keyfile() is not None
    assert pem_c.public_key() is not None
    assert len(pem_c.x962_str) > 20
    content = pem_c.encrypt("message")
    assert isinstance(content, str)
    assert pem_c.decrypt(content) == "message"
