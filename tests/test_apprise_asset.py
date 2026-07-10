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
from datetime import timezone, tzinfo
import logging
import sys
from zoneinfo import ZoneInfo

import pytest

from apprise.asset import AppriseAsset

logging.disable(logging.CRITICAL)

# Ensure we don't create .pyc files for these tests
sys.dont_write_bytecode = True


def test_timezone():
    "asset: timezone() testing"
    asset = AppriseAsset(timezone="utc")
    assert isinstance(asset.tzinfo, tzinfo)

    # Default (uses system value)
    asset = AppriseAsset(timezone=None)
    assert isinstance(asset.tzinfo, tzinfo)

    # Timezone can also already be a tzinfo object
    asset = AppriseAsset(timezone=timezone.utc)
    assert isinstance(asset.tzinfo, tzinfo)
    asset = AppriseAsset(timezone=ZoneInfo("America/Toronto"))
    assert isinstance(asset.tzinfo, tzinfo)

    with pytest.raises(AttributeError):
        AppriseAsset(timezone=object)

    with pytest.raises(AttributeError):
        AppriseAsset(timezone="invalid")


def test_service_timeout():
    "asset: service_timeout() testing"

    # Default value is 60 seconds, defined directly on AppriseAsset
    asset = AppriseAsset()
    assert asset._service_timeout == 60.0

    # Accepts an int and stores it as a float
    asset = AppriseAsset(service_timeout=10)
    assert asset._service_timeout == 10.0
    assert isinstance(asset._service_timeout, float)

    # Accepts a float directly
    asset = AppriseAsset(service_timeout=12.5)
    assert asset._service_timeout == 12.5

    # 0 is valid -- it disables the timeout entirely
    asset = AppriseAsset(service_timeout=0)
    assert asset._service_timeout == 0.0

    # Negative values are rejected
    with pytest.raises(ValueError):
        AppriseAsset(service_timeout=-1)

    # Non-numeric types are rejected
    with pytest.raises(TypeError):
        AppriseAsset(service_timeout="invalid")

    # Booleans are rejected even though bool is technically an int subclass
    with pytest.raises(TypeError):
        AppriseAsset(service_timeout=True)

    # inf might look like a second way to spell "unbounded" (0 is the
    # documented one), but concurrent.futures.Future.result(timeout=
    # float("inf")) raises OverflowError on some platforms, silently
    # turning a successful notification into a reported FAILURE -- so
    # it's rejected outright, same as any other non-finite value.
    with pytest.raises(ValueError):
        AppriseAsset(service_timeout=float("inf"))

    with pytest.raises(ValueError):
        AppriseAsset(service_timeout=float("-inf"))

    # NaN fails every ordering comparison, so it would otherwise slip
    # past a plain "< 0" check and silently disable the timeout as an
    # accidental side effect of its comparison semantics.
    with pytest.raises(ValueError):
        AppriseAsset(service_timeout=float("nan"))

    # The internal/system attribute can also be set the same way every
    # other underscore-prefixed AppriseAsset field can: directly through
    # the generic kwarg mechanism (bypassing the friendly named parameter
    # and its validation).
    asset = AppriseAsset(_service_timeout=99.0)
    assert asset._service_timeout == 99.0
