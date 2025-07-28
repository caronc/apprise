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

from datetime import datetime, timedelta

# Disable logging for a cleaner testing output
import logging
from timeit import default_timer

import pytest

from apprise import AppriseAsset, NotifyImageSize, NotifyType
from apprise.plugins import NotifyBase

logging.disable(logging.CRITICAL)


def test_notify_base():
    """
    API: NotifyBase() object

    """

    # invalid types throw exceptions
    with pytest.raises(TypeError):
        NotifyBase(**{"format": "invalid"})

    # invalid types throw exceptions
    with pytest.raises(TypeError):
        NotifyBase(**{"overflow": "invalid"})

    # Bad port information
    nb = NotifyBase(port="invalid")
    assert nb.port is None

    nb = NotifyBase(port=10)
    assert nb.port == 10

    assert isinstance(nb.url(), str)
    assert str(nb) == nb.url()

    with pytest.raises(NotImplementedError):
        # Each sub-module is that inherits this as a parent is required to
        # over-ride this function. So direct calls to this throws a not
        # implemented error intentionally
        nb.send("test message")

    # Throttle overrides..
    nb = NotifyBase()
    nb.request_rate_per_sec = 0.0
    start_time = default_timer()
    nb.throttle()
    elapsed = default_timer() - start_time
    # Should be a very fast response time since we set it to zero but we'll
    # check for less then 500 to be fair as some testing systems may be slower
    # then other
    assert elapsed < 0.5

    # Concurrent calls should achieve the same response
    start_time = default_timer()
    nb.throttle()
    elapsed = default_timer() - start_time
    assert elapsed < 0.5

    nb = NotifyBase()
    nb.request_rate_per_sec = 1.0

    # Set our time to now
    start_time = default_timer()
    nb.throttle()
    elapsed = default_timer() - start_time
    # A first call to throttle (Without telling it a time previously ran) does
    # not block for any length of time; it just merely sets us up for
    # concurrent calls to block
    assert elapsed < 0.5

    # Concurrent calls could take up to the rate_per_sec though...
    start_time = default_timer()
    nb.throttle(last_io=datetime.now())
    elapsed = default_timer() - start_time
    assert elapsed > 0.48 and elapsed < 1.5

    nb = NotifyBase()
    nb.request_rate_per_sec = 1.0

    # Set our time to now
    start_time = default_timer()
    nb.throttle(last_io=datetime.now())
    elapsed = default_timer() - start_time
    # because we told it that we had already done a previous action (now)
    # the throttle holds out until the right time has passed
    assert elapsed > 0.48 and elapsed < 1.5

    # Concurrent calls could take up to the rate_per_sec though...
    start_time = default_timer()
    nb.throttle(last_io=datetime.now())
    elapsed = default_timer() - start_time
    assert elapsed > 0.48 and elapsed < 1.5

    nb = NotifyBase()
    start_time = default_timer()
    nb.request_rate_per_sec = 1.0
    # Force a time in the past
    nb.throttle(last_io=(datetime.now() - timedelta(seconds=20)))
    elapsed = default_timer() - start_time
    # Should be a very fast response time since we set it to zero but we'll
    # check for less then 500 to be fair as some testing systems may be slower
    # then other
    assert elapsed < 0.5

    # Force a throttle time
    start_time = default_timer()
    nb.throttle(wait=0.5)
    elapsed = default_timer() - start_time
    assert elapsed > 0.48 and elapsed < 1.5

    # our NotifyBase wasn't initialized with an ImageSize so this will fail
    assert nb.image_url(notify_type=NotifyType.INFO) is None
    assert nb.image_path(notify_type=NotifyType.INFO) is None
    assert nb.image_raw(notify_type=NotifyType.INFO) is None

    # Color handling
    assert nb.color(notify_type="invalid") == \
        AppriseAsset.default_html_color
    assert isinstance(
        nb.color(notify_type=NotifyType.INFO, color_type=None), str
    )
    assert isinstance(
        nb.color(notify_type=NotifyType.INFO, color_type=int), int
    )
    assert isinstance(
        nb.color(notify_type=NotifyType.INFO, color_type=tuple), tuple
    )

    # Ascii Handling
    assert nb.ascii(notify_type="invalid") == \
        AppriseAsset.default_ascii_chars
    assert nb.ascii(NotifyType.INFO) == "[i]"
    assert nb.ascii(NotifyType.SUCCESS) == "[+]"
    assert nb.ascii(NotifyType.WARNING) == "[~]"
    assert nb.ascii(NotifyType.FAILURE) == "[!]"

    # Create an object
    nb = NotifyBase()
    # Force an image size since the default doesn't have one
    nb.image_size = NotifyImageSize.XY_256

    # We'll get an object this time around
    assert nb.image_url(notify_type=NotifyType.INFO) is not None
    assert nb.image_path(notify_type=NotifyType.INFO) is not None
    assert nb.image_raw(notify_type=NotifyType.INFO) is not None

    # Static function testing
    assert (
        NotifyBase.escape_html("<content>'\t \n</content>")
        == "&lt;content&gt;&apos;&emsp;&nbsp;\n&lt;/content&gt;"
    )

    assert (
        NotifyBase.escape_html(
            "<content>'\t \n</content>", convert_new_lines=True
        )
        == "&lt;content&gt;&apos;&emsp;&nbsp;<br/>&lt;/content&gt;"
    )

    # Test invalid data
    assert NotifyBase.split_path(None) == []
    assert NotifyBase.split_path(object()) == []
    assert NotifyBase.split_path(42) == []

    assert NotifyBase.split_path(
        "/path/?name=Dr%20Disrespect", unquote=False
    ) == [
        "path",
        "?name=Dr%20Disrespect",
    ]

    assert NotifyBase.split_path(
        "/path/?name=Dr%20Disrespect", unquote=True
    ) == [
        "path",
        "?name=Dr Disrespect",
    ]

    # a slash found inside the path, if escaped properly will not be broken
    # by split_path while additional concatinated slashes are ignored
    # FYI: %2F = /
    assert NotifyBase.split_path(
        "/%2F///%2F%2F////%2F%2F%2F////", unquote=True
    ) == [
        "/",
        "//",
        "///",
    ]

    # Test invalid data
    assert NotifyBase.parse_list(None) == []
    assert NotifyBase.parse_list(object()) == []
    assert NotifyBase.parse_list(42) == []

    result = NotifyBase.parse_list(
        ",path,?name=Dr%20Disrespect", unquote=False
    )
    assert isinstance(result, list)
    assert len(result) == 2
    assert "path" in result
    assert "?name=Dr%20Disrespect" in result

    result = NotifyBase.parse_list(",path,?name=Dr%20Disrespect", unquote=True)
    assert isinstance(result, list)
    assert len(result) == 2
    assert "path" in result
    assert "?name=Dr Disrespect" in result

    # by parse_list while additional concatinated slashes are ignored
    # FYI: %2F = /
    # In this lit there are actually 4 entries, however parse_list
    # eliminates duplicates in addition to unquoting content by default
    result = NotifyBase.parse_list(
        ",%2F,%2F%2F, , , ,%2F%2F%2F, %2F", unquote=True
    )
    assert isinstance(result, list)
    assert len(result) == 3
    assert "/" in result
    assert "//" in result
    assert "///" in result

    # Phone number parsing
    assert NotifyBase.parse_phone_no(None) == []
    assert NotifyBase.parse_phone_no(object()) == []
    assert NotifyBase.parse_phone_no(42) == []

    result = NotifyBase.parse_phone_no(
        "+1-800-123-1234,(800) 123-4567", unquote=False
    )
    assert isinstance(result, list)
    assert len(result) == 2
    assert "+1-800-123-1234" in result
    assert "(800) 123-4567" in result

    # %2B == +
    result = NotifyBase.parse_phone_no(
        "%2B1-800-123-1234,%2B1%20800%20123%204567", unquote=True
    )
    assert isinstance(result, list)
    assert len(result) == 2
    assert "+1-800-123-1234" in result
    assert "+1 800 123 4567" in result

    # Give nothing, get nothing
    assert NotifyBase.escape_html("") == ""
    assert NotifyBase.escape_html(None) == ""
    assert NotifyBase.escape_html(object()) == ""

    # Test quote
    assert NotifyBase.unquote("%20") == " "
    assert NotifyBase.quote(" ") == "%20"
    assert NotifyBase.unquote(None) == ""
    assert NotifyBase.quote(None) == ""


def test_notify_base_urls():
    """
    API: NotifyBase() URLs

    """

    # Test verify switch whih is used as part of the SSL Verification
    # by default all SSL sites are verified unless this flag is set to
    # something like 'No', 'False', 'Disabled', etc.  Boolean values are
    # pretty forgiving.
    results = NotifyBase.parse_url("https://localhost:8080/?verify=No")
    assert "verify" in results
    assert results["verify"] is False

    results = NotifyBase.parse_url("https://localhost:8080/?verify=Yes")
    assert "verify" in results
    assert results["verify"] is True

    # The default is to verify
    results = NotifyBase.parse_url("https://localhost:8080")
    assert "verify" in results
    assert results["verify"] is True

    # Password Handling

    # pass keyword over-rides default password
    results = NotifyBase.parse_url("https://user:pass@localhost")
    assert "password" in results
    assert results["password"] == "pass"

    # pass keyword over-rides default password
    results = NotifyBase.parse_url(
        "https://user:pass@localhost?pass=newpassword"
    )
    assert "password" in results
    assert results["password"] == "newpassword"

    # password keyword can also optionally be used
    results = NotifyBase.parse_url(
        "https://user:pass@localhost?password=passwd"
    )
    assert "password" in results
    assert results["password"] == "passwd"

    # pass= override password=
    # password keyword can also optionally be used
    results = NotifyBase.parse_url(
        "https://user:pass@localhost?pass=pw1&password=pw2"
    )
    assert "password" in results
    assert results["password"] == "pw1"

    # Options
    results = NotifyBase.parse_url("https://localhost?format=invalid")
    assert "format" not in results
    results = NotifyBase.parse_url("https://localhost?format=text")
    assert "format" in results
    assert results["format"] == "text"
    results = NotifyBase.parse_url("https://localhost?format=markdown")
    assert "format" in results
    assert results["format"] == "markdown"
    results = NotifyBase.parse_url("https://localhost?format=html")
    assert "format" in results
    assert results["format"] == "html"

    results = NotifyBase.parse_url("https://localhost?overflow=invalid")
    assert "overflow" not in results
    results = NotifyBase.parse_url("https://localhost?overflow=upstream")
    assert "overflow" in results
    assert results["overflow"] == "upstream"
    results = NotifyBase.parse_url("https://localhost?overflow=split")
    assert "overflow" in results
    assert results["overflow"] == "split"
    results = NotifyBase.parse_url("https://localhost?overflow=truncate")
    assert "overflow" in results
    assert results["overflow"] == "truncate"

    # User Handling

    # user keyword over-rides default password
    results = NotifyBase.parse_url("https://user:pass@localhost")
    assert "user" in results
    assert results["user"] == "user"

    # user keyword over-rides default password
    results = NotifyBase.parse_url("https://user:pass@localhost?user=newuser")
    assert "user" in results
    assert results["user"] == "newuser"

    # Test invalid urls
    assert NotifyBase.parse_url("https://:@/") is None
    assert NotifyBase.parse_url("http://:@") is None
    assert NotifyBase.parse_url("http://@") is None
    assert NotifyBase.parse_url("http:///") is None
    assert NotifyBase.parse_url("http://:test/") is None
    assert NotifyBase.parse_url("http://pass:test/") is None
