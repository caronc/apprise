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
import logging
import pickle
import sys
from unittest import mock

import pytest
import requests

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
    locale = AppriseLocale()
    serialized = pickle.dumps(locale)
    new_locale = pickle.loads(serialized)

    assert locale.lang == new_locale.lang

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


@mock.patch("requests.request")
def test_apprise_pickle_notify(mock_request):
    """pickle: Restored Apprise objects can send notifications."""
    response = requests.Request()
    response.status_code = requests.codes.ok
    mock_request.return_value = response

    apobj = Apprise()
    assert apobj.add("json://localhost") is True
    new_apobj = pickle.loads(pickle.dumps(apobj))

    assert bool(new_apobj.notify("x")) is True
    mock_request.assert_called_once()
    assert mock_request.call_args.args[0] == "POST"


@pytest.mark.parametrize(
    "debug, log_level", [(False, None), (True, logging.DEBUG)]
)
def test_apprise_pickle_settings(debug, log_level):
    """pickle: Preserve settings and discard unpicklable callbacks."""
    apobj = Apprise(
        debug=debug,
        log_callback=lambda entry, service: None,
        log_level=log_level,
    )
    new_apobj = pickle.loads(pickle.dumps(apobj))

    assert new_apobj.debug is debug
    assert new_apobj._log_level == log_level
    assert new_apobj._log_callback is None

    # A restored object can be pickled again
    assert pickle.loads(pickle.dumps(new_apobj)).debug is debug


def test_apprise_pickle_legacy_state():
    """pickle: Load state saved before log_level was serialized."""
    apobj = Apprise(debug=True)
    assert apobj.add("json://localhost") is True
    state = apobj.__getstate__()
    state.pop("log_level", None)

    new_apobj = Apprise.__new__(Apprise)
    new_apobj.__setstate__(state)

    assert new_apobj.debug is True
    assert new_apobj._log_callback is None
    assert new_apobj._log_level is None
    assert new_apobj.urls() == apobj.urls()
