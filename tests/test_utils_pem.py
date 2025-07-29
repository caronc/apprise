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
import sys
from unittest import mock

import pytest

from apprise import AppriseAsset, PersistentStoreMode, utils

# Disable logging for a cleaner testing output
logging.disable(logging.CRITICAL)

# Attachment Directory
TEST_VAR_DIR = os.path.join(os.path.dirname(__file__), "var")


@pytest.mark.skipif(
    "cryptography" not in sys.modules, reason="Requires cryptography"
)
def test_utils_pem_general(tmpdir):
    """Utils:PEM."""

    # string to manipulate/work with
    unencrypted_str = "message"

    tmpdir0 = tmpdir.mkdir("tmp00")

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
    assert pem_c.x962_str == ""
    assert pem_c.decrypt(b"data") is None
    assert pem_c.encrypt(unencrypted_str) is None
    # Keys can not be generated in memory mode
    assert pem_c.keygen() is False
    assert pem_c.sign(b"data") is None

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
    assert pem_c.x962_str == ""
    assert pem_c.encrypt(unencrypted_str) is None

    # Generate our keys
    assert bool(pem_c) is False
    assert pem_c.keygen() is True
    assert bool(pem_c) is True

    # We have 2 new key files generated
    pub_keyfile = os.path.join(str(tmpdir0), "public_key.pem")
    prv_keyfile = os.path.join(str(tmpdir0), "private_key.pem")
    assert os.path.isfile(pub_keyfile)
    assert os.path.isfile(prv_keyfile)
    assert pem_c.public_keyfile() is not None
    assert pem_c.decrypt("garbage") is None
    assert pem_c.public_key() is not None

    # Keys used later on as ref
    pubkey_ref = pem_c.public_key()
    prvkey_ref = pem_c.private_key()

    assert isinstance(pem_c.x962_str, str)
    assert len(pem_c.x962_str) > 20
    content = pem_c.encrypt(unencrypted_str)
    assert pem_c.decrypt(
        pem_c.encrypt(unencrypted_str.encode("utf-8"))
    ) == pem_c.decrypt(pem_c.encrypt(unencrypted_str))
    assert pem_c.decrypt(
        pem_c.encrypt(unencrypted_str, public_key=pem_c.public_key())
    ) == pem_c.decrypt(pem_c.encrypt(unencrypted_str))
    assert pem_c.decrypt(content) == unencrypted_str
    assert isinstance(content, str)
    assert pem_c.decrypt(content) == unencrypted_str
    # support str as well
    assert pem_c.decrypt(content) == unencrypted_str
    assert pem_c.decrypt(content.encode("utf-8")) == unencrypted_str
    # Sign test
    assert isinstance(pem_c.sign(content.encode("utf-8")), bytes)

    # Web Push handling
    webpush_content = pem_c.encrypt_webpush(
        unencrypted_str, public_key=pem_c.public_key(), auth_secret=b"secret"
    )
    assert isinstance(webpush_content, bytes)

    webpush_content = pem_c.encrypt_webpush(
        unencrypted_str.encode("utf-8"),
        public_key=pem_c.public_key(),
        auth_secret=b"secret",
    )
    assert isinstance(webpush_content, bytes)

    # Non Bytes (garbage basically)
    with pytest.raises(TypeError):
        assert pem_c.decrypt(None) is None

    with pytest.raises(TypeError):
        assert pem_c.decrypt(5) is None

    with pytest.raises(TypeError):
        assert pem_c.decrypt(False) is None

    with pytest.raises(TypeError):
        assert pem_c.decrypt(object) is None

    # Test our initialization
    pem_c = utils.pem.ApprisePEMController(
        path=None, prv_keyfile="invalid", asset=asset
    )
    assert pem_c.private_keyfile() is False
    assert pem_c.public_keyfile() is None
    assert pem_c.prv_keyfile is False
    assert pem_c.pub_keyfile is None
    assert pem_c.private_key() is None
    assert pem_c.public_key() is None
    assert pem_c.decrypt(content) is None

    pem_c = utils.pem.ApprisePEMController(
        path=None, pub_keyfile="invalid", asset=asset
    )
    assert pem_c.private_keyfile() is None
    assert pem_c.public_keyfile() is False
    assert pem_c.prv_keyfile is None
    assert pem_c.pub_keyfile is False
    assert pem_c.private_key() is None
    assert pem_c.public_key() is None
    assert pem_c.decrypt(content) is None

    pem_c = utils.pem.ApprisePEMController(
        path=None, prv_keyfile=prv_keyfile, asset=asset
    )
    assert pem_c.private_keyfile() == prv_keyfile
    assert pem_c.public_keyfile() is None
    assert pem_c.private_key() is not None
    assert pem_c.prv_keyfile == prv_keyfile
    assert pem_c.pub_keyfile is None
    assert pem_c.public_key() is not None
    assert pem_c.decrypt(content) == unencrypted_str

    pem_c = utils.pem.ApprisePEMController(
        path=None, pub_keyfile=pub_keyfile, asset=asset
    )
    assert pem_c.private_keyfile() is None
    assert pem_c.public_keyfile() == pub_keyfile
    assert pem_c.prv_keyfile is None
    assert pem_c.pub_keyfile == pub_keyfile
    assert pem_c.private_key() is None
    assert pem_c.public_key() is not None
    assert pem_c.decrypt(content) is None

    # Test our path references
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    assert pem_c.load_private_key(path=None) is True
    assert pem_c.private_keyfile() == prv_keyfile
    assert pem_c.prv_keyfile is None
    assert pem_c.pub_keyfile is None
    assert pem_c.decrypt(content) == unencrypted_str

    # Generate a new key referencing another location
    pem_c = utils.pem.ApprisePEMController(
        name="keygen-tests", path=str(tmpdir0), asset=asset
    )

    # generate ourselves some keys
    assert pem_c.keygen() is True
    keygen_prv_file = pem_c.prv_keyfile
    keygen_pub_file = pem_c.pub_keyfile

    # Remove 1 (but not both)
    os.unlink(keygen_pub_file)

    pem_c = utils.pem.ApprisePEMController(
        name="keygen-tests", path=str(tmpdir0), asset=asset
    )
    # Private key was found, so this does not work
    assert pem_c.keygen() is False
    os.unlink(keygen_prv_file)

    pem_c = utils.pem.ApprisePEMController(
        name="keygen-tests", path=str(tmpdir0), asset=asset
    )
    # It works now
    assert pem_c.keygen() is True

    # Tests public_key generation failure only
    with mock.patch("builtins.open", side_effect=OSError()):
        assert pem_c.keygen(force=True) is False
        with mock.patch("os.unlink", side_effect=OSError()):
            assert pem_c.keygen(force=True) is False
        with mock.patch("os.unlink", return_value=True):
            assert pem_c.keygen(force=True) is False

    # Tests private key generation
    side_effect = [mock.mock_open(read_data="file contents").return_value] + [
        OSError() for _ in range(10)
    ]
    with mock.patch("builtins.open", side_effect=side_effect):
        assert pem_c.keygen(force=True) is False
    with (
        mock.patch("builtins.open", side_effect=side_effect),
        mock.patch("os.unlink", side_effect=OSError()),
    ):
        assert pem_c.keygen(force=True) is False
    with (
        mock.patch("builtins.open", side_effect=side_effect),
        mock.patch("os.unlink", return_value=True),
    ):
        assert pem_c.keygen(force=True) is False

    # Generate a new key referencing another location
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    # We can't re-generate keys if ones already exist
    assert pem_c.keygen() is False
    # the keygen is the big difference here
    assert pem_c.keygen(name="test") is True
    # under the hood, a key is not regenerated (as one already exists)
    assert pem_c.keygen(name="test") is False
    # Generate it a second time by force
    assert pem_c.keygen(name="test", force=True) is True

    assert pem_c.private_keyfile() == os.path.join(
        str(tmpdir0), "test-private_key.pem"
    )
    assert pem_c.public_keyfile() == os.path.join(
        str(tmpdir0), "test-public_key.pem"
    )
    assert pem_c.private_key() is not None
    assert pem_c.public_key() is not None
    assert pem_c.prv_keyfile == os.path.join(
        str(tmpdir0), "test-private_key.pem"
    )
    assert pem_c.pub_keyfile == os.path.join(
        str(tmpdir0), "test-public_key.pem"
    )
    # 'content' was generated using a different key and can not be
    # decrypted
    assert pem_c.decrypt(content) is None

    # Test Decryption files
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    # Calling decrypt triggers underlining code to auto-load
    assert pem_c.decrypt(content) == unencrypted_str
    # Using a private key by path
    assert (
        pem_c.decrypt(content, private_key=pem_c.private_key())
        == unencrypted_str
    )

    # Test different edge cases of load_private_key()
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    assert pem_c.load_private_key() is True
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    assert pem_c.load_private_key(path=prv_keyfile) is True
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    with mock.patch("builtins.open", side_effect=TypeError()):
        assert pem_c.load_private_key(path=prv_keyfile) is False
    with mock.patch("builtins.open", side_effect=OSError()):
        assert pem_c.load_private_key(path=prv_keyfile) is False
    with mock.patch("builtins.open", side_effect=FileNotFoundError()):
        assert pem_c.load_private_key(path=prv_keyfile) is False

    # Test different edge cases of load_public_key()
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    assert pem_c.load_public_key() is True
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    assert pem_c.load_public_key(path=pub_keyfile) is True
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    with mock.patch("builtins.open", side_effect=TypeError()):
        assert pem_c.load_public_key(path=pub_keyfile) is False
    with mock.patch("builtins.open", side_effect=OSError()):
        assert pem_c.load_public_key(path=pub_keyfile) is False
    with mock.patch("builtins.open", side_effect=FileNotFoundError()):
        assert pem_c.load_public_key(path=pub_keyfile) is False

    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    assert pem_c.public_keyfile("test1", "test2") == pub_keyfile
    assert pem_c.private_keyfile("test1", "test2") == prv_keyfile

    pem_c = utils.pem.ApprisePEMController(
        path=str(tmpdir0), name="pub1", asset=asset
    )
    assert pem_c.public_key(autogen=True)

    pem_c = utils.pem.ApprisePEMController(
        path=str(tmpdir0), name="pub2", asset=asset
    )
    assert pem_c.private_key(autogen=True)

    #
    # Auto key generation turned on
    #
    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.MEMORY,
        storage_path=str(tmpdir0),
        pem_autogen=True,
    )
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir0), asset=asset)
    assert pem_c.load_public_key(path=pub_keyfile) is True
    pem_c = utils.pem.ApprisePEMController(path=None, asset=asset)
    assert pem_c.load_public_key(path=pub_keyfile) is True

    tmpdir1 = tmpdir.mkdir("tmp01")

    # Currently no files here
    assert os.listdir(str(tmpdir1)) == []

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.MEMORY,
        storage_path=str(tmpdir1),
        pem_autogen=False,
    )

    # Auto-Gen is turned off, so weare not successful here
    pem_c = utils.pem.ApprisePEMController(path=None, asset=asset)
    assert pem_c.public_key() is None
    assert pem_c.private_key() is None
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir1), asset=asset)
    assert pem_c.public_key() is None
    assert pem_c.private_key() is None

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.FLUSH,
        storage_path=str(tmpdir1),
        pem_autogen=True,
    )
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir1), asset=asset)
    # Generate ourselves a private key
    assert pem_c.public_key() is not None
    assert pem_c.private_key() is not None
    pub_keyfile = os.path.join(str(tmpdir1), "public_key.pem")
    prv_keyfile = os.path.join(str(tmpdir1), "private_key.pem")
    assert os.path.isfile(pub_keyfile)
    assert os.path.isfile(prv_keyfile)

    with open(pub_keyfile, "w") as f:
        f.write("garbage")

    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir1), asset=asset)
    # we can still load our data as the public key is generated
    # from the private
    assert pem_c.public_key() is not None
    assert pem_c.private_key() is not None

    tmpdir2 = tmpdir.mkdir("tmp02")
    pem_c = utils.pem.ApprisePEMController(path=str(tmpdir2), asset=asset)
    pub_keyfile = os.path.join(str(tmpdir2), "public_key.pem")
    prv_keyfile = os.path.join(str(tmpdir2), "private_key.pem")
    assert not os.path.isfile(pub_keyfile)
    assert not os.path.isfile(prv_keyfile)

    #
    # Public Key Edge Case Tests
    #
    with (
        mock.patch.object(
            pem_c, "public_keyfile", side_effect=[None, pub_keyfile]
        ) as mock_keyfile,
        mock.patch.object(
            pem_c,
            "keygen",
            side_effect=lambda *_, **__: setattr(
                pem_c, "_ApprisePEMController__public_key", pubkey_ref
            )
            or True,
        ) as mock_keygen,
        mock.patch.object(pem_c, "load_public_key", return_value=True),
    ):

        result = pem_c.public_key()
        assert result is pubkey_ref
        assert mock_keyfile.call_count == 2
        mock_keygen.assert_called_once()

    # - First call: None → triggers keygen
    # - Second call (recursive): None → causes fallback
    public_keyfile_side_effect = [None, None]

    with (
        mock.patch.object(
            pem_c, "public_keyfile", side_effect=public_keyfile_side_effect
        ) as mock_keyfile,
        mock.patch.object(pem_c, "keygen", return_value=True) as mock_keygen,
        mock.patch.object(
            pem_c, "load_public_key", return_value=False
        ) as mock_load,
    ):

        # Ensure no key is preset initially
        pem_c._ApprisePEMController__public_key = None

        result = pem_c.public_key()
        assert result is None
        # Once in outer call, once in recursive
        assert mock_keyfile.call_count == 2
        mock_keygen.assert_called_once()
        mock_load.assert_not_called()

    #
    # Private Key Edge Case Tests
    #
    with (
        mock.patch.object(
            pem_c, "private_keyfile", side_effect=[None, prv_keyfile]
        ) as mock_keyfile,
        mock.patch.object(
            pem_c,
            "keygen",
            side_effect=lambda *_, **__: setattr(
                pem_c, "_ApprisePEMController__private_key", prvkey_ref
            )
            or True,
        ) as mock_keygen,
        mock.patch.object(pem_c, "load_private_key", return_value=True),
    ):

        result = pem_c.private_key()
        assert result is prvkey_ref
        assert mock_keyfile.call_count == 2
        mock_keygen.assert_called_once()

    # - First call: None → triggers keygen
    # - Second call (recursive): None → causes fallback
    private_keyfile_side_effect = [None, None]

    with (
        mock.patch.object(
            pem_c, "private_keyfile", side_effect=private_keyfile_side_effect
        ) as mock_keyfile,
        mock.patch.object(pem_c, "keygen", return_value=True) as mock_keygen,
        mock.patch.object(
            pem_c, "load_private_key", return_value=False
        ) as mock_load,
    ):

        # Ensure no key is preset initially
        pem_c._ApprisePEMController__private_key = None

        result = pem_c.private_key()
        assert result is None
        # Once in outer call, once in recursive
        assert mock_keyfile.call_count == 2
        mock_keygen.assert_called_once()
        mock_load.assert_not_called()


@pytest.mark.skipif(
    "cryptography" in sys.modules,
    reason="Requires that cryptography NOT be installed",
)
def test_utils_pem_general_without_c(tmpdir):
    """Utils:PEM Without cryptography."""

    tmpdir0 = tmpdir.mkdir("tmp00")

    # Currently no files here
    assert os.listdir(str(tmpdir0)) == []

    asset = AppriseAsset(
        storage_mode=PersistentStoreMode.MEMORY,
        storage_path=str(tmpdir0),
        pem_autogen=False,
    )

    # Create a PEM Controller
    pem_c = utils.pem.ApprisePEMController(path=None, asset=asset)

    # cryptography library missing poses issues with library useage
    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.public_keyfile()

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.public_key()

    with pytest.raises(utils.pem.ApprisePEMException):
        _ = pem_c.x962_str

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.encrypt("message")

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.keygen()

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
    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.private_keyfile()

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.private_key()

    with pytest.raises(utils.pem.ApprisePEMException):
        _ = pem_c.x962_str

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.encrypt("message")

    # Keys can not be generated in memory mode
    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.keygen()

    # No files loaded
    assert os.listdir(str(tmpdir0)) == []

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.public_keyfile()

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.public_key()

    with pytest.raises(utils.pem.ApprisePEMException):
        _ = pem_c.x962_str

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.encrypt("message")

    with pytest.raises(utils.pem.ApprisePEMException):
        pem_c.decrypt("abcd==")
