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
import sys
from unittest import mock

import pytest

import apprise

try:
    import syslog

except ImportError:
    # Shim so that test cases can run in environments that
    # do not have syslog
    import types
    syslog = types.SimpleNamespace(
        LOG_PID=0x01,
        LOG_PERROR=0x02,
        LOG_INFO=6,
        LOG_NOTICE=5,
        LOG_CRIT=2,
        LOG_WARNING=4,
        LOG_KERN=0,
        LOG_USER=1,
        LOG_MAIL=2,
        LOG_DAEMON=3,
        LOG_AUTH=4,
        LOG_SYSLOG=5,
        LOG_LPR=6,
        LOG_NEWS=7,
        LOG_UUCP=8,
        LOG_CRON=9,
        LOG_LOCAL0=16,
        LOG_LOCAL1=17,
        LOG_LOCAL2=18,
        LOG_LOCAL3=19,
        LOG_LOCAL4=20,
        LOG_LOCAL5=21,
        LOG_LOCAL6=22,
        LOG_LOCAL7=23,
        openlog=lambda *a, **kw: None,
        syslog=lambda *a, **kw: None,
    )
    sys.modules["syslog"] = syslog


logging.disable(logging.CRITICAL)

from apprise.plugins.syslog import NotifySyslog  # noqa E402


@mock.patch("syslog.syslog")
@mock.patch("syslog.openlog")
def test_plugin_syslog_by_url(openlog, syslog):
    """NotifySyslog() Apprise URLs."""
    # an invalid URL
    assert NotifySyslog.parse_url(object) is None
    assert NotifySyslog.parse_url(42) is None
    assert NotifySyslog.parse_url(None) is None

    obj = apprise.Apprise.instantiate("syslog://")
    assert obj.url().startswith("syslog://user")
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert re.search(r"logperror=no", obj.url()) is not None

    # We do not support generation of a URL ID
    assert obj.url_id() is None

    assert isinstance(
        apprise.Apprise.instantiate("syslog://:@/"), NotifySyslog
    )

    obj = apprise.Apprise.instantiate("syslog://?logpid=no&logperror=yes")
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith("syslog://user")
    assert re.search(r"logpid=no", obj.url()) is not None
    assert re.search(r"logperror=yes", obj.url()) is not None

    # Test sending a notification
    assert obj.notify("body") is True
    assert obj.notify(title="title", body="body") is True

    # Invalid Notification Type
    assert obj.notify("body", notify_type="invalid") is False

    obj = apprise.Apprise.instantiate("syslog://_/?facility=local5")
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith("syslog://local5")
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert re.search(r"logperror=no", obj.url()) is not None

    # Invalid instantiation
    assert apprise.Apprise.instantiate("syslog://_/?facility=invalid") is None

    # j will cause a search to take place and match to daemon
    obj = apprise.Apprise.instantiate("syslog://_/?facility=d")
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith("syslog://daemon")
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert re.search(r"logperror=no", obj.url()) is not None

    # Facility can also be specified on the url as a hostname
    obj = apprise.Apprise.instantiate("syslog://kern?logpid=no&logperror=y")
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith("syslog://kern")
    assert re.search(r"logpid=no", obj.url()) is not None
    assert re.search(r"logperror=yes", obj.url()) is not None

    # Facilities specified as an argument always over-ride host
    obj = apprise.Apprise.instantiate("syslog://kern?facility=d")
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith("syslog://daemon")


@mock.patch("syslog.syslog")
@mock.patch("syslog.openlog")
def test_plugin_syslog_edge_cases(openlog, syslog):
    """NotifySyslog() Edge Cases."""

    # Default
    obj = NotifySyslog(facility=None)
    assert isinstance(obj, NotifySyslog)
    assert obj.url().startswith("syslog://user")
    assert re.search(r"logpid=yes", obj.url()) is not None
    assert re.search(r"logperror=no", obj.url()) is not None

    # Exception should be thrown about the fact no bot token was specified
    with pytest.raises(TypeError):
        NotifySyslog(facility="invalid")

    with pytest.raises(TypeError):
        NotifySyslog(facility=object)
