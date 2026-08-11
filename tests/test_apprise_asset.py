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

    # The private field cannot bypass the validated timezone argument.
    with pytest.raises(AttributeError):
        AppriseAsset(_tzinfo=timezone.utc)


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

    # The private field cannot bypass the validated public argument.
    with pytest.raises(AttributeError):
        AppriseAsset(_service_timeout=99.0)


def test_payload_max_size():
    "asset: payload_max_size() testing"

    # Zero disables the cap by default.
    asset = AppriseAsset()
    assert asset._payload_max_size == 0

    # Accepts a positive int, turning the cap on
    asset = AppriseAsset(payload_max_size=500)
    assert asset._payload_max_size == 500

    # 0 is valid -- it is also the default, and disables the cap entirely
    asset = AppriseAsset(payload_max_size=0)
    assert asset._payload_max_size == 0

    # Negative values are rejected
    with pytest.raises(ValueError):
        AppriseAsset(payload_max_size=-1)

    # Non-int types are rejected -- a float character count makes no sense
    with pytest.raises(TypeError):
        AppriseAsset(payload_max_size=12.5)

    with pytest.raises(TypeError):
        AppriseAsset(payload_max_size="invalid")

    # Booleans are rejected even though bool is technically an int subclass
    with pytest.raises(TypeError):
        AppriseAsset(payload_max_size=True)

    # The private field cannot bypass the validated public argument.
    with pytest.raises(AttributeError):
        AppriseAsset(_payload_max_size=250)


def test_payload_buffer_threshold_and_min_buffer():
    "asset: payload_buffer_threshold() / payload_min_buffer() testing"

    # Defaults match the documented values.
    asset = AppriseAsset()
    assert asset._payload_buffer_threshold == 10
    assert asset._payload_min_buffer == 25

    # Public constructor arguments configure both settings.
    asset = AppriseAsset(payload_buffer_threshold=3, payload_min_buffer=5)
    assert asset._payload_buffer_threshold == 3
    assert asset._payload_min_buffer == 5

    # 0 is valid for both.
    asset = AppriseAsset(payload_buffer_threshold=0, payload_min_buffer=0)
    assert asset._payload_buffer_threshold == 0
    assert asset._payload_min_buffer == 0

    # Negative values are rejected.
    with pytest.raises(ValueError):
        AppriseAsset(payload_buffer_threshold=-1)

    with pytest.raises(ValueError):
        AppriseAsset(payload_min_buffer=-1)

    # Non-int types are rejected.
    with pytest.raises(TypeError):
        AppriseAsset(payload_buffer_threshold=12.5)

    with pytest.raises(TypeError):
        AppriseAsset(payload_min_buffer="invalid")

    # Booleans are rejected even though bool is technically an int subclass.
    with pytest.raises(TypeError):
        AppriseAsset(payload_buffer_threshold=True)

    with pytest.raises(TypeError):
        AppriseAsset(payload_min_buffer=True)

    # Private fields cannot bypass the validated public arguments.
    with pytest.raises(AttributeError):
        AppriseAsset(_payload_buffer_threshold=2)

    with pytest.raises(AttributeError):
        AppriseAsset(_payload_min_buffer=7)


def test_result_log_storage_sizes():
    """Result-log storage accepts non-negative byte limits."""
    asset = AppriseAsset()
    assert asset.result_log_memory_size == 0
    assert asset.result_log_disk_size == 0

    asset = AppriseAsset(
        result_log_memory_size=2048, result_log_disk_size=4096
    )
    assert asset.result_log_memory_size == 2048
    assert asset.result_log_disk_size == 4096

    for name in ("result_log_memory_size", "result_log_disk_size"):
        with pytest.raises(ValueError):
            AppriseAsset(**{name: -1})
        for value in (True, 1.5, "1024"):
            with pytest.raises(TypeError):
                AppriseAsset(**{name: value})
        with pytest.raises(AttributeError):
            AppriseAsset(**{"_{}".format(name): 1})


def test_enforce_payload_max_size():
    "asset: enforce_payload_max_size() testing"

    # Disabled (the default): nothing is ever trimmed.
    asset = AppriseAsset()
    title, body = asset.enforce_payload_max_size("T" * 100, "B" * 1000)
    assert title == "T" * 100
    assert body == "B" * 1000

    # Already within budget: left untouched.
    asset = AppriseAsset(payload_max_size=2000)
    title, body = asset.enforce_payload_max_size("T" * 100, "B" * 1000)
    assert title == "T" * 100
    assert body == "B" * 1000


def test_enforce_payload_max_size_absent_side():
    "asset: enforce_payload_max_size() never trims a missing side"

    asset = AppriseAsset(payload_max_size=20)

    # An empty title never competes with the body for room.
    title, body = asset.enforce_payload_max_size("", "B" * 1000)
    assert title == ""
    assert len(body) == 20

    # An empty body never competes with the title for room.
    title, body = asset.enforce_payload_max_size("T" * 1000, "")
    assert len(title) == 20
    assert body == ""


def test_enforce_payload_max_size_short_side_guaranteed():
    """asset: keep a short side whole when the other minimum fits"""

    # A short title stays whole; the body receives the remaining room.
    asset = AppriseAsset(payload_max_size=40)
    title, body = asset.enforce_payload_max_size("T" * 9, "B" * 1000)
    assert title == "T" * 9
    assert len(body) == 31

    # The same rule keeps a short body whole.
    title, body = asset.enforce_payload_max_size("T" * 40, "hi!")
    assert title == "T" * 37
    assert body == "hi!"

    # A title exactly at the buffer width still qualifies.
    title, body = asset.enforce_payload_max_size("T" * 10, "B" * 1000)
    assert title == "T" * 10
    assert len(body) == 30


def test_enforce_payload_max_size_guarantee_unaffordable():
    """asset: use proportional sharing when a guarantee cannot fit"""

    # Two long sides share the cap proportionally.
    asset = AppriseAsset(payload_max_size=20)
    title, body = asset.enforce_payload_max_size("T" * 20, "B" * 18)
    assert len(title) + len(body) == 20
    assert len(title) == 10
    assert len(body) == 10

    # The title is short, but the body minimum cannot fit beside it.
    tiny_asset = AppriseAsset(payload_max_size=11)
    title, body = tiny_asset.enforce_payload_max_size("T" * 10, "B" * 1000)
    assert len(title) + len(body) == 11
    assert len(title) == 1
    assert len(body) == 10

    # The mirrored short-body rule also falls back when space is tight.
    balanced_asset = AppriseAsset(payload_max_size=15)
    title, body = balanced_asset.enforce_payload_max_size("T" * 15, "B" * 10)
    assert len(title) + len(body) == 15
    assert len(title) == 9
    assert len(body) == 6


def test_enforce_payload_max_size_proportional_tier():
    "asset: enforce_payload_max_size() proportional split for two long sides"

    # Both sides are longer than the buffer, so title and body share the
    # cap in proportion to their original lengths.
    asset = AppriseAsset(payload_max_size=200)
    title, body = asset.enforce_payload_max_size("T" * 100, "B" * 1000)
    assert len(title) + len(body) == 200
    # The title receives 100/1100 of the budget, rounded down.
    assert len(title) == 18
    assert len(body) == 182

    # A title-heavy split keeps most of the budget for the title.
    heavy_asset = AppriseAsset(payload_max_size=50)
    title, body = heavy_asset.enforce_payload_max_size("T" * 100, "B" * 60)
    assert len(title) + len(body) == 50
    assert len(title) > len(body)

    # Keep one title character when a title longer than the buffer still
    # has its proportional share round down to zero.
    title, body = asset.enforce_payload_max_size("T" * 11, "B" * 2200)
    assert title == "T"
    assert len(body) == 199


def test_enforce_payload_max_size_configurable_tiers():
    "asset: payload_buffer_threshold / payload_min_buffer are tunable"

    # Public constructor arguments can override both settings.
    asset = AppriseAsset(
        payload_max_size=12,
        payload_buffer_threshold=3,
        payload_min_buffer=5,
    )
    assert asset._payload_buffer_threshold == 3
    assert asset._payload_min_buffer == 5

    # Both sides exceed the custom buffer threshold (3), so this falls
    # through to the proportional split.
    title, body = asset.enforce_payload_max_size("T" * 4, "B" * 20)
    assert len(title) == 2
    assert len(body) == 10

    # A title at or below the custom buffer threshold now qualifies for
    # the whole-and-guaranteed rule, using the custom (smaller) minimum.
    custom_asset = AppriseAsset(
        payload_max_size=12,
        payload_buffer_threshold=5,
        payload_min_buffer=3,
    )
    title, body = custom_asset.enforce_payload_max_size("T" * 4, "B" * 20)
    assert title == "T" * 4
    assert len(body) == 8
