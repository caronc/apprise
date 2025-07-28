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
import pickle
import sys

from apprise import Apprise, AppriseAsset, AppriseLocale

logging.disable(logging.CRITICAL)

# Ensure we don't create .pyc files for these tests
sys.dont_write_bytecode = True


def test_apprise_pickle_asset(tmpdir):
    """pickle: AppriseAsset"""
    asset = AppriseAsset()
    serialized = pickle.dumps(asset)
    new_asset = pickle.loads(serialized)

    # iterate over some keys to verify they're still the same:
    keys = (
        "app_id",
        "app_desc",
        "app_url",
        "html_notify_map",
        "ascii_notify_map",
        "default_html_color",
        "default_extension",
        "theme",
        "image_url_mask",
        "image_url_logo",
        "image_path_mask",
        "body_format",
        "async_mode",
        "interpret_escapes",
        "encoding",
        "secure_logging",
        "_recursion",
    )

    for key in keys:
        assert getattr(asset, key) == getattr(new_asset, key)


def test_apprise_pickle_locale(tmpdir):
    """pickle: AppriseLocale"""
    _locale = AppriseLocale()
    serialized = pickle.dumps(_locale)
    new_locale = pickle.loads(serialized)

    assert _locale.lang == new_locale.lang

    # Ensure internal functions still call in new object
    new_locale.detect_language()


def test_apprise_pickle_core(tmpdir):
    """pickle: Apprise"""
    asset = AppriseAsset(app_id="default")
    apobj = Apprise(asset=asset)

    # Create a custom asset so we can verify it gets correctly serialized
    xml_asset = AppriseAsset(app_id="xml")

    # Store our Entries
    apobj.add("json://localhost")
    apobj.add("xml://localhost", asset=xml_asset)
    apobj.add("form://localhost")
    apobj.add("mailto://user:pass@localhost", tag="email")
    serialized = pickle.dumps(apobj)

    # Unserialize our object
    new_apobj = pickle.loads(serialized)

    # Verify that it loaded our URLs back
    assert len(new_apobj) == 4

    # Our assets were kept (note the XML altered entry)
    assert apobj[0].app_id == "default"
    assert apobj[1].app_id == "xml"
    assert apobj[2].app_id == "default"
    assert apobj[3].app_id == "default"

    # Our tag was kept
    assert "email" in apobj[3].tags
