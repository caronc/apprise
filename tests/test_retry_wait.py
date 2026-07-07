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

import asyncio
import logging
import threading
import time
from unittest import mock

import pytest

from apprise import Apprise, AppriseAsset, AppriseResultStatus
from apprise.common import (
    APPRISE_MAX_SERVICE_RETRY,
    APPRISE_MAX_SERVICE_WAIT,
    MATCH_ALL_TAG,
)
from apprise.config.base import ConfigBase
from apprise.manager_plugins import NotificationManager
from apprise.plugins import NotifyBase
from apprise.tag import AppriseTag

logging.disable(logging.CRITICAL)

N_MGR = NotificationManager()


class _TestNotify(NotifyBase):
    """Test notification plugin -- controlled pass/fail via side_effect."""

    app_id = "TestApp"
    app_desc = "Test"
    notify_url = "test://"

    title_maxlen = 250
    body_maxlen = 32768

    # Override so NotifyBase doesn't reject the URL
    def url(self, privacy=False, *args, **kwargs):
        return "test://localhost"

    def send(self, **kwargs):
        return True

    @staticmethod
    def parse_url(url):
        results = NotifyBase.parse_url(url, verify_host=False)
        return results


class TestWaitValidation:
    """Tests for the wait= parameter accepted by NotifyBase."""

    def _make(self, **kwargs):
        return _TestNotify(host="localhost", **kwargs)

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, 0.0),
            (0.0, 0.0),
            (0.5, 0.5),
            (1, 1.0),
            (1.0, 1.0),
            ("0.5", 0.5),
            ("1", 1.0),
            ("1.4", 1.4),
            ("20", 20.0),
            (APPRISE_MAX_SERVICE_WAIT, APPRISE_MAX_SERVICE_WAIT),
        ],
    )
    def test_valid_wait(self, value, expected):
        nb = self._make(wait=value)
        assert nb.wait == pytest.approx(expected)

    def test_wait_clamped_to_max(self):
        # Values above the cap are clamped, not rejected
        nb = self._make(wait=APPRISE_MAX_SERVICE_WAIT + 9999)
        assert nb.wait == pytest.approx(APPRISE_MAX_SERVICE_WAIT)

    @pytest.mark.parametrize(
        "bad_value",
        [
            "-3",
            "-0.1",
            "1.3.3.",
            "abc",
            "inf",
            "-inf",
            "nan",
            None,  # None means "use asset default" -- tested separately
        ],
    )
    def test_invalid_wait_uses_asset_default(self, bad_value):
        if bad_value is None:
            # Not passing wait= at all should use asset default
            asset = AppriseAsset(default_service_wait=1.25)
            nb = _TestNotify(host="localhost", asset=asset)
            assert nb.wait == pytest.approx(1.25)
            return

        asset = AppriseAsset(default_service_wait=0.75)
        nb = self._make(wait=bad_value, asset=asset)
        # Falls back to asset default on invalid input
        assert nb.wait == pytest.approx(0.75)

    def test_negative_wait_falls_back(self):
        asset = AppriseAsset(default_service_wait=2.0)
        nb = self._make(wait=-1.0, asset=asset)
        assert nb.wait == pytest.approx(2.0)

    def test_asset_default_zero(self):
        asset = AppriseAsset(default_service_wait=0.0)
        nb = _TestNotify(host="localhost", asset=asset)
        assert nb.wait == pytest.approx(0.0)

    def test_asset_default_clamped_to_max(self):
        asset = AppriseAsset(default_service_wait=APPRISE_MAX_SERVICE_WAIT + 1)
        nb = _TestNotify(host="localhost", asset=asset)
        assert nb.wait == pytest.approx(APPRISE_MAX_SERVICE_WAIT)


class TestRetryValidation:
    """Sanity checks for the retry= parameter."""

    def _make(self, **kwargs):
        return _TestNotify(host="localhost", **kwargs)

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, 0),
            (1, 1),
            ("3", 3),
            (APPRISE_MAX_SERVICE_RETRY, APPRISE_MAX_SERVICE_RETRY),
        ],
    )
    def test_valid_retry(self, value, expected):
        nb = self._make(retry=value)
        assert nb.retry == expected

    def test_retry_clamped_to_max(self):
        nb = self._make(retry=APPRISE_MAX_SERVICE_RETRY + 999)
        assert nb.retry == APPRISE_MAX_SERVICE_RETRY

    @pytest.mark.parametrize("bad", ["-1", "abc", "1.3.3."])
    def test_invalid_retry_uses_asset_default(self, bad):
        asset = AppriseAsset(default_service_retry=2)
        nb = self._make(retry=bad, asset=asset)
        assert nb.retry == 2


class TestUrlRoundTrip:
    def test_wait_in_url_parameters(self):
        nb = _TestNotify(host="localhost", wait=1.5, retry=2)
        params = nb.url_parameters()
        assert "wait" in params
        assert params["wait"] == "1.5"
        assert "retry" in params
        assert params["retry"] == "2"

    def test_wait_zero_always_in_url_parameters(self):
        """retry= and wait= are always present, even at their zero defaults."""
        nb = _TestNotify(host="localhost", wait=0.0, retry=0)
        params = nb.url_parameters()
        assert "wait" in params
        assert params["wait"] == "0.0"
        assert "retry" in params
        assert params["retry"] == "0"

    def test_parse_url_extracts_wait(self):
        results = _TestNotify.parse_url("test://localhost?wait=2.5&retry=3")
        assert results is not None
        assert results.get("wait") == "2.5"
        assert results.get("retry") == "3"

    def test_parse_url_no_wait_key_absent(self):
        results = _TestNotify.parse_url("test://localhost")
        assert results is not None
        assert "wait" not in results


class _FailThenSucceedNotify(NotifyBase):
    """Fails the first N calls, then succeeds."""

    app_id = "FailThenSucceed"
    app_desc = "Test"
    notify_url = "failpass://"
    title_maxlen = 250
    body_maxlen = 32768

    def __init__(self, fail_times=1, **kwargs):
        super().__init__(**kwargs)
        self._fail_times = fail_times
        self._calls = 0

    def url(self, *args, **kwargs):
        return "failpass://localhost"

    def send(self, **kwargs):
        self._calls += 1
        return not self._calls <= self._fail_times

    async def async_notify(self, **kwargs):
        return self.send(**kwargs)

    @staticmethod
    def parse_url(url):
        return NotifyBase.parse_url(url, verify_host=False)


class TestSequentialSleep:
    """time.sleep is called between retries in sequential dispatch."""

    def test_sleep_called_on_retry(self):
        """A failed attempt waits once before its successful retry."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)

            service = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.3,
            )
            a.add(service)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert bool(result) is True
            # Failed once -> sleep once before retry
            mock_sleep.assert_called_once_with(pytest.approx(0.3))
        finally:
            N_MGR.unload_modules()

    def test_sleep_not_called_when_wait_zero(self):
        """A zero wait setting retries without calling sleep."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)

            service = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.0,
            )
            a.add(service)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert bool(result) is True
            mock_sleep.assert_not_called()
        finally:
            N_MGR.unload_modules()

    def test_sleep_not_called_when_no_retry(self):
        """A service without retries never sleeps after failure."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)

            # retry=0 means only one attempt; with wait=1.0 sleep should
            # never fire since there are no retries
            service = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=0,
                wait=1.0,
                fail_times=0,  # always succeeds
            )
            a.add(service)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert bool(result) is True
            mock_sleep.assert_not_called()
        finally:
            N_MGR.unload_modules()

    def test_sleep_called_multiple_times(self):
        """Fails twice, succeeds on third attempt -> sleep called twice."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)

            service = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=3,
                wait=0.5,
                fail_times=2,
            )
            a.add(service)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert bool(result) is True
            assert mock_sleep.call_count == 2
            for call in mock_sleep.call_args_list:
                assert call == mock.call(pytest.approx(0.5))
        finally:
            N_MGR.unload_modules()


class TestThreadPoolSleep:
    """time.sleep is called between retries in threadpool dispatch."""

    def test_sleep_called_in_threadpool(self):
        """A thread-pool retry honors the configured wait interval."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            # async_mode=True -> uses threadpool when > 1 service;
            # but with a single service it falls through to sequential.
            # Use two services so we actually hit the threadpool path.
            asset = AppriseAsset(async_mode=True)

            # Two separate service objects so a threadpool is used
            s1 = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.2,
                fail_times=1,
            )
            s2 = _FailThenSucceedNotify(
                host="localhost2",
                asset=asset,
                retry=0,
                wait=0.0,
                fail_times=0,
            )

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert bool(result) is True
            # s1 fails once -> sleep once
            mock_sleep.assert_called_once_with(pytest.approx(0.2))
        finally:
            N_MGR.unload_modules()

    def test_sleep_not_called_in_threadpool_when_wait_zero(self):
        """A zero thread-pool wait retries without calling sleep."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)

            s1 = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.0,
                fail_times=1,
            )
            s2 = _FailThenSucceedNotify(
                host="localhost2",
                asset=asset,
                retry=0,
                wait=0.0,
                fail_times=0,
            )

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert bool(result) is True
            mock_sleep.assert_not_called()
        finally:
            N_MGR.unload_modules()


class TestAsyncioSleep:
    """asyncio.sleep is called between retries in async dispatch."""

    def test_asyncio_sleep_called(self):
        """An asynchronous retry honors the configured wait interval."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()

            service = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.4,
                fail_times=1,
            )

            a = Apprise(asset=asset)
            a.add(service)

            async def run():
                """Dispatch while capturing the asynchronous retry sleep."""
                with mock.patch("apprise.apprise.asyncio.sleep") as mock_sleep:
                    mock_sleep.return_value = None
                    result = await a.async_notify(body="test")
                return result, mock_sleep

            result, mock_sleep = asyncio.run(run())

            assert bool(result) is True
            mock_sleep.assert_called_once_with(pytest.approx(0.4))
        finally:
            N_MGR.unload_modules()

    def test_asyncio_sleep_not_called_when_wait_zero(self):
        """A zero asynchronous wait retries without calling sleep."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()

            service = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.0,
                fail_times=1,
            )

            a = Apprise(asset=asset)
            a.add(service)

            async def run():
                """Dispatch while checking that asyncio.sleep is unused."""
                with mock.patch("apprise.apprise.asyncio.sleep") as mock_sleep:
                    mock_sleep.return_value = None
                    result = await a.async_notify(body="test")
                return result, mock_sleep

            result, mock_sleep = asyncio.run(run())

            assert bool(result) is True
            mock_sleep.assert_not_called()
        finally:
            N_MGR.unload_modules()


class TestAssetDefault:
    def test_asset_wait_default_used(self):
        asset = AppriseAsset(default_service_wait=1.5)
        nb = _TestNotify(host="localhost", asset=asset)
        assert nb.wait == pytest.approx(1.5)

    def test_explicit_wait_overrides_asset(self):
        asset = AppriseAsset(default_service_wait=1.5)
        nb = _TestNotify(host="localhost", asset=asset, wait=0.2)
        assert nb.wait == pytest.approx(0.2)

    def test_asset_retry_default_used(self):
        asset = AppriseAsset(default_service_retry=3)
        nb = _TestNotify(host="localhost", asset=asset)
        assert nb.retry == 3

    def test_explicit_retry_overrides_asset(self):
        asset = AppriseAsset(default_service_retry=3)
        nb = _TestNotify(host="localhost", asset=asset, retry=1)
        assert nb.retry == 1


class _RaisingNotify(NotifyBase):
    """Plugin that raises a bare Exception from notify()."""

    app_id = "RaisingApp"
    app_desc = "Test"
    notify_url = "raise://"
    title_maxlen = 250
    body_maxlen = 32768

    def url(self, *args, **kwargs):
        """Return the stable URL for this raising test plugin."""
        return "raise://localhost"

    def send(self, **kwargs):
        """Raise a delivery error for synchronous exception tests."""
        raise RuntimeError("plugin exploded")

    async def async_notify(self, **kwargs):
        """Raise a delivery error for asynchronous exception tests."""
        raise RuntimeError("plugin exploded async")

    @staticmethod
    def parse_url(url):
        """Parse the synthetic URL without requiring a real host."""
        return NotifyBase.parse_url(url, verify_host=False)


class _SlowNotify(NotifyBase):
    """Plugin whose send() blocks for a configurable delay before
    reporting success -- used to exercise AppriseAsset._service_timeout
    and notify(timeout=...) enforcement with real wall-clock timing."""

    app_id = "SlowApp"
    app_desc = "Test"
    notify_url = "slow://"
    title_maxlen = 250
    body_maxlen = 32768

    def __init__(self, delay=0.0, **kwargs):
        """Initialize the test plugin with its artificial delay."""
        super().__init__(**kwargs)
        self._delay = delay
        self.calls = 0

    def url(self, *args, **kwargs):
        """Return a stable URL containing the test host."""
        return "slow://{}".format(self.host)

    def send(self, **kwargs):
        """Simulate blocking delivery before reporting success."""
        self.calls += 1
        time.sleep(self._delay)
        return True

    async def async_notify(self, **kwargs):
        """Simulate asynchronous delivery before reporting success."""
        self.calls += 1
        await asyncio.sleep(self._delay)
        return True

    @staticmethod
    def parse_url(url):
        """Parse the synthetic URL without requiring a real host."""
        return NotifyBase.parse_url(url, verify_host=False)


class TestAppriseTag:
    """Full branch coverage for AppriseTag."""

    def test_parse_returns_same_instance(self):
        """parse() short-circuits when the input is already an AppriseTag."""
        t = AppriseTag("alerts", priority=2)
        # Must return the exact same object, not a copy
        assert AppriseTag.parse(t) is t

    def test_parse_fallback_for_unrecognised_input(self):
        """parse() falls back to a raw-name tag when the regex has no match."""
        # Input starting with '@' does not match _RE_TAG; the fallback branch
        # stores the whole input as the name.
        t = AppriseTag.parse("@invalid")
        assert str(t) == "@invalid"
        assert t.priority == 0
        assert t.retry is None

    # --- __repr__ ---

    def test_repr_plain(self):
        """repr() with default priority and no retry is minimal."""
        assert repr(AppriseTag("simple")) == "AppriseTag('simple')"

    def test_repr_with_priority(self):
        """repr() includes priority= when the priority is non-zero."""
        r = repr(AppriseTag("test", priority=3))
        assert "priority=3" in r

    def test_repr_with_retry(self):
        """repr() includes retry= when a retry count is set."""
        r = repr(AppriseTag("test", retry=5))
        assert "retry=5" in r

    def test_repr_with_priority_and_retry(self):
        """repr() includes both fields when both are non-default."""
        r = repr(AppriseTag("test", priority=2, retry=3))
        assert "priority=2" in r
        assert "retry=3" in r

    # --- __eq__ ---

    def test_eq_two_apprisetags_same_name(self):
        """Two AppriseTag objects are equal when their names match,
        regardless of priority or retry."""
        assert AppriseTag("abc") == AppriseTag("abc", priority=5)
        assert AppriseTag("ABC") == AppriseTag("abc")

    def test_eq_with_string(self):
        """An AppriseTag equals a plain str by name."""
        assert AppriseTag("hello") == "hello"
        assert AppriseTag("HELLO") == "hello"

    def test_eq_not_equal_different_name(self):
        assert AppriseTag("abc") != AppriseTag("xyz")
        assert AppriseTag("abc") != "xyz"

    def test_eq_returns_notimplemented_for_other_types(self):
        """Comparing to a non-str/AppriseTag returns NotImplemented"""
        result = AppriseTag("abc").__eq__(42)
        assert result is NotImplemented

    # --- __lt__ ---

    def test_lt_two_apprisetags(self):
        """__lt__ sorts two AppriseTag objects by tag name."""
        assert AppriseTag("abc") < AppriseTag("def")
        assert not (AppriseTag("def") < AppriseTag("abc"))

    def test_lt_with_string(self):
        """AppriseTag can be ordered against a plain string."""
        assert AppriseTag("abc") < "def"
        assert not (AppriseTag("zzz") < "aaa")

    def test_lt_returns_notimplemented_for_other_types(self):
        """__lt__ with non-str/AppriseTag returns NotImplemented"""
        result = AppriseTag("abc").__lt__(42)
        assert result is NotImplemented

    # --- __bool__ ---

    def test_bool_empty_tag_is_false(self):
        """An AppriseTag with an empty name is falsy"""
        assert not AppriseTag("")
        assert bool(AppriseTag("")) is False

    def test_bool_nonempty_tag_is_true(self):
        assert bool(AppriseTag("something")) is True

    # --- set / dict integration ---

    def test_apprisetag_in_set_with_plain_string(self):
        """AppriseTag in a set is found by plain string membership test."""
        s = {AppriseTag("endpoint")}
        assert "endpoint" in s

    def test_plain_string_in_set_with_apprisetag(self):
        """A plain string is found in a set containing AppriseTag."""
        s = {"endpoint"}
        assert AppriseTag("endpoint") in s


class TestStaticHelpers:
    """Tests for _extract_filter_retry and _filter_has_explicit_priority
    covering the nested-list branches not reached by integration tests."""

    def test_extract_retry_from_nested_list(self):
        """A retry suffix is found inside a nested list entry."""
        # tag = [["alerts:3"]] -- outer list, inner list as AND group
        result = Apprise._extract_filter_retry([["alerts:3"]])
        assert result == 3

    def test_extract_retry_from_list_of_strings(self):
        """A retry suffix is found in a plain-string list entry."""
        result = Apprise._extract_filter_retry(["alerts:3"])
        assert result == 3

    def test_extract_retry_none_when_absent(self):
        """Returns None when no retry suffix is present."""
        assert Apprise._extract_filter_retry("alerts") is None
        assert Apprise._extract_filter_retry(["alerts"]) is None

    def test_extract_retry_none_from_nested_list_no_suffix(self):
        """Nested list without retry suffix returns None.

        Covers the 'if ft.retry is not None' False branch and the
        inner for-loop completing without returning.
        """
        result = Apprise._extract_filter_retry([["alerts"]])
        assert result is None

    def test_service_priority_for_tag_name_absent(self):
        """Returns 0 when no tag in service.tags matches tag_name."""
        service = mock.Mock()
        service.tags = {AppriseTag("alerts", priority=3, has_priority=True)}
        assert Apprise._server_priority_for_tag_name(service, "backup") == 0

    def test_match_service_retry_plain_string_tag(self):
        """Plain string in service.tags matched by a priority-prefixed token.

        Covers the string fallback when a matching service tag is not an
        AppriseTag instance.
        """
        service = mock.Mock()
        service.tags = {"alerts"}  # plain string, not an AppriseTag
        # "3:alerts:2" carries priority=3 + retry=2; plain "alerts" matches
        result = Apprise._match_service_retry(service, "3:alerts:2")
        assert result == 2

    def test_match_service_retry_plain_string_tag_no_match(self):
        """Plain string in service.tags that does not match returns None."""
        service = mock.Mock()
        service.tags = {"other"}  # plain string -- does not match "alerts"
        result = Apprise._match_service_retry(service, "3:alerts:2")
        assert result is None

    def test_extract_retry_none_for_match_all(self):
        assert Apprise._extract_filter_retry(MATCH_ALL_TAG) is None
        assert Apprise._extract_filter_retry(None) is None

    def test_has_priority_nested_list(self):
        """A priority prefix is found inside a nested list."""
        assert Apprise._filter_has_explicit_priority([["2:alerts"]])

    def test_has_priority_list_of_strings(self):
        """A priority prefix is found in a plain-string list."""
        assert Apprise._filter_has_explicit_priority(["2:alerts"])

    def test_has_priority_false_no_prefix(self):
        """Filters without a prefix do not carry explicit priority."""
        assert not Apprise._filter_has_explicit_priority("alerts")
        assert not Apprise._filter_has_explicit_priority(["alerts"])

    def test_has_priority_false_for_match_all(self):
        """Match-all filters do not carry an explicit priority."""
        assert not Apprise._filter_has_explicit_priority(MATCH_ALL_TAG)
        assert not Apprise._filter_has_explicit_priority(None)

    # _notify_parallel_threadpool / _notify_parallel_asyncio zero-length -----

    def test_threadpool_zero_services_returns_true(self):
        """Empty service list returns (True, []) immediately."""
        ok, results = Apprise._notify_parallel_threadpool()
        assert ok is True
        assert results == []

    def test_asyncio_zero_services_returns_true(self):
        """Empty service list returns (True, []) immediately."""
        ok, results = asyncio.run(Apprise._notify_parallel_asyncio())
        assert ok is True
        assert results == []


class TestDispatchIntegration:
    """End-to-end notify() tests covering the new priority/retry dispatch."""

    def _make_service(self, host, priority, asset, fail_times=0):
        """Create a _FailThenSucceedNotify with an AppriseTag in its tags."""
        s = _FailThenSucceedNotify(
            host=host, asset=asset, fail_times=fail_times
        )
        # Assign a fresh instance-level set rather than mutating the
        # class-level tags set.  URLBase.tags is a class attribute (set());
        # .add() would mutate it and share state across all instances.
        # Assignment shadows the class attribute and gives each service its
        # own set with the correct priority stored in the AppriseTag object.
        s.tags = {AppriseTag("alerts", priority=priority, has_priority=True)}
        return s

    def test_filter_retry_override_via_tag_suffix(self):
        """tag suffix ':N' overrides per-service retry for this call only."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            # Service's own retry=0; tag suffix of 2 should allow 3 attempts
            service = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=0,
                wait=0.0,
                fail_times=2,
            )
            # Tag the service so the filter "failpass:2" (tag name "failpass",
            # retry override 2) can match it via is_exclusive_match.
            service.tags = {"failpass"}
            a = Apprise(asset=asset)
            a.add(service)

            # "failpass:2" -> retry override of 2 (3 total attempts)
            result = a.notify(body="test", tag="failpass:2")
            assert bool(result) is True
            assert service._calls == 3
        finally:
            N_MGR.unload_modules()

    def test_exclusive_priority_dispatch_skips_other_priorities(self):
        """An explicit priority dispatches only matching-priority services."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s1 = self._make_service("host1", priority=1, asset=asset)
            s2 = self._make_service("host2", priority=2, asset=asset)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            # "2:alerts" -> only priority-2 service fires
            result = a.notify(body="test", tag="2:alerts")
            assert bool(result) is True
            assert s1._calls == 0  # priority-1, not contacted
            assert s2._calls == 1  # priority-2, contacted once
        finally:
            N_MGR.unload_modules()

    def test_escalation_stops_after_priority_success(self):
        """If priority-1 group all succeed, priority-2 group is not run."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s1 = self._make_service("host1", priority=1, asset=asset)
            s2 = self._make_service("host2", priority=2, asset=asset)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test", tag="alerts")
            assert bool(result) is True
            assert s1._calls == 1  # priority 1 succeeded
            assert s2._calls == 0  # never escalated to
        finally:
            N_MGR.unload_modules()

    def test_escalation_triggers_on_priority_group_failure(self):
        """Priority-1 group failure escalates to priority-2 group."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            # priority-1 always fails
            s1 = self._make_service(
                "host1", priority=1, asset=asset, fail_times=999
            )
            # priority-2 always succeeds
            s2 = self._make_service("host2", priority=2, asset=asset)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test", tag="alerts")
            assert bool(result) is True
            assert s1._calls == 1
            assert s2._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_async_notify_filter_retry_and_explicit_priority(self):
        """async_notify() supports escalation and exclusive priority paths."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()
            s1 = self._make_service("host1", priority=1, asset=asset)
            s2 = self._make_service("host2", priority=2, asset=asset)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            async def run_exclusive():
                """Dispatch only the explicitly selected priority."""
                return await a.async_notify(body="test", tag="2:alerts")

            async def run_escalation():
                """Dispatch the first successful escalation group."""
                return await a.async_notify(body="test", tag="alerts")

            # exclusive: only priority-2 fires
            r = asyncio.run(run_exclusive())
            assert bool(r) is True
            assert s1._calls == 0
            assert s2._calls == 1

            # escalation: priority-1 succeeds, priority-2 skipped
            s1._calls = 0
            s2._calls = 0
            r = asyncio.run(run_escalation())
            assert bool(r) is True
            assert s1._calls == 1
            assert s2._calls == 0
        finally:
            N_MGR.unload_modules()

    def test_plain_and_zero_prefix_are_equivalent(self):
        """'family' and '0:family' are identical at priority 0.
        A filter of '0:family' must match services tagged with plain
        'family', and both forms must land in the same escalation group."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # s1: tagged with plain "family" (priority=0, has_priority=False)
            s1 = _FailThenSucceedNotify(
                host="host1", asset=asset, fail_times=0
            )
            s1.tags = {AppriseTag.parse("family")}

            # s2: tagged with explicit "0:family" (priority=0,
            # has_priority=True)
            s2 = _FailThenSucceedNotify(
                host="host2", asset=asset, fail_times=0
            )
            s2.tags = {AppriseTag.parse("0:family")}

            # s3: lower-urgency fallback -- should never fire when p-0 succeeds
            s3 = _FailThenSucceedNotify(
                host="host3", asset=asset, fail_times=0
            )
            s3.tags = {AppriseTag.parse("1:family")}

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)
            a.add(s3)

            # Exclusive "0:family": plain "family" and "0:family" services
            # are both priority 0 and must both fire; priority-1 service is
            # skipped.
            result = a.notify(body="test", tag="0:family")
            assert bool(result) is True
            assert s1._calls == 1  # plain "family" matched by "0:family"
            assert s2._calls == 1  # explicit "0:family" matched
            assert s3._calls == 0  # priority 1, not priority 0 -- skipped

            # Escalation "family": s1 and s2 are both in the priority-0
            # group.  Both succeed, so s3 (priority 1) is never escalated to.
            s1._calls = s2._calls = s3._calls = 0
            result = a.notify(body="test", tag="family")
            assert bool(result) is True
            assert s1._calls == 1  # priority-0 group
            assert s2._calls == 1  # same priority-0 group
            assert s3._calls == 0  # not escalated to
        finally:
            N_MGR.unload_modules()


class TestExceptionHandling:
    """Verify that plugin exceptions are caught and retried, not propagated."""

    def test_sequential_exception_treated_as_failure(self):
        """A plugin raising Exception is caught; delivery is marked failed."""
        N_MGR["raise"] = _RaisingNotify

        try:
            asset = AppriseAsset(async_mode=False)
            service = _RaisingNotify(host="localhost", asset=asset, retry=0)
            a = Apprise(asset=asset)
            a.add(service)

            result = a.notify(body="test")
            assert bool(result) is False
        finally:
            N_MGR.unload_modules()

    def test_sequential_exception_retried(self):
        """Exception on first attempt is retried; later success counts."""
        N_MGR["failpass"] = _FailThenSucceedNotify
        N_MGR["raise"] = _RaisingNotify

        try:
            asset = AppriseAsset(async_mode=False)
            # Use a plugin that raises on the first attempt then succeeds
            service = _FailThenSucceedNotify(
                host="localhost", asset=asset, retry=1, wait=0.0, fail_times=1
            )
            # Patch notify to raise on the first call then succeed
            call_count = [0]

            def raising_then_ok(**kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("transient error")
                return True

            service.send = raising_then_ok
            a = Apprise(asset=asset)
            a.add(service)

            result = a.notify(body="test")
            assert bool(result) is True
            assert call_count[0] == 2
        finally:
            N_MGR.unload_modules()

    def test_threadpool_future_exception_caught(self):
        """An exception escaping a thread future is caught gracefully."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)
            # Need 2 services to trigger the thread pool path
            s1 = _FailThenSucceedNotify(
                host="host1", asset=asset, fail_times=0
            )
            s2 = _FailThenSucceedNotify(
                host="host2", asset=asset, fail_times=0
            )
            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            # Inject one failed future so the outer safety net is exercised.
            import concurrent.futures as cf

            real_executor_cls = cf.ThreadPoolExecutor

            class _PatchedExecutor:
                """Delegate to a real executor while injecting one failure."""

                def __init__(self, *args, **kwargs):
                    """Create the wrapped executor with the same arguments."""
                    self._real = real_executor_cls(*args, **kwargs)

                def __enter__(self):
                    """Return this wrapper when entering the context."""
                    return self

                def __exit__(self, *exc):
                    """Forward context cleanup to the wrapped executor."""
                    return self._real.__exit__(*exc)

                def submit(self, fn, service, kwargs):
                    """Return a failed future for ``s1`` and submit others."""
                    if service is s1:
                        fut = cf.Future()
                        fut.set_exception(RuntimeError("future boom"))
                        return fut
                    return self._real.submit(fn, service, kwargs)

                def shutdown(self, *args, **kwargs):
                    """Forward shutdown behavior to the wrapped executor."""
                    return self._real.shutdown(*args, **kwargs)

            # Reset the shared executor so the patched class is used here.
            import apprise.apprise as apprise_module

            with (
                mock.patch("apprise.apprise._shared_executor", None),
                mock.patch(
                    "apprise.apprise.cf.ThreadPoolExecutor", _PatchedExecutor
                ),
            ):
                result = a.notify(body="test")

                # Clean up the real executor wrapped by _PatchedExecutor.
                apprise_module._shared_executor._real.shutdown(wait=True)

            # One future raised -> overall result is False
            assert bool(result) is False
        finally:
            N_MGR.unload_modules()

    def test_asyncio_exception_in_do_call_treated_as_failure(self):
        """An exception inside do_call marks the service as failed."""
        N_MGR["raise"] = _RaisingNotify

        try:
            asset = AppriseAsset()
            service = _RaisingNotify(host="localhost", asset=asset, retry=0)
            a = Apprise(asset=asset)
            a.add(service)

            async def run():
                """Execute async notification with the patched gather."""
                return await a.async_notify(body="test")

            result = asyncio.run(run())
            assert bool(result) is False
        finally:
            N_MGR.unload_modules()

    def test_asyncio_gather_unhandled_exception(self):
        """An Exception escaping the outer gather() round is caught as a
        safety net and treated as a batch failure."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()
            service = _FailThenSucceedNotify(
                host="localhost", asset=asset, fail_times=0
            )
            a = Apprise(asset=asset)
            a.add(service)

            # Mock asyncio.gather to return an escaped exception object.
            # Close any unawaited coroutines passed to the mock to avoid
            # "coroutine was never awaited" RuntimeWarnings.
            async def fake_gather(*args, **kw):
                """Return an escaped error while closing input coroutines."""
                for arg in args:
                    if asyncio.iscoroutine(arg):
                        arg.close()
                return [RuntimeError("escaped")]

            async def run():
                """Dispatch while gather returns an escaped exception."""
                with mock.patch("apprise.apprise.asyncio.gather", fake_gather):
                    return await a.async_notify(body="test")

            result = asyncio.run(run())
            assert bool(result) is False
        finally:
            N_MGR.unload_modules()

    def test_asyncio_gather_type_error(self):
        """A TypeError in gather results is caught and returns False."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()
            service = _FailThenSucceedNotify(
                host="localhost", asset=asset, fail_times=0
            )
            a = Apprise(asset=asset)
            a.add(service)

            async def fake_gather(*args, **kw):
                """Return a validation error as a gathered result."""
                for arg in args:
                    if asyncio.iscoroutine(arg):
                        arg.close()
                return [TypeError("validation")]

            async def run():
                """Dispatch while gather returns a validation error."""
                with mock.patch("apprise.apprise.asyncio.gather", fake_gather):
                    return await a.async_notify(body="test")

            result = asyncio.run(run())
            assert bool(result) is False
        finally:
            N_MGR.unload_modules()

    def test_sequential_raise_does_not_block_other_services(self):
        """A raising service is marked failed but every other service in
        the same sequential batch is still attempted and reported."""
        N_MGR["raise"] = _RaisingNotify
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            bad = _RaisingNotify(host="bad", asset=asset)
            good1 = _FailThenSucceedNotify(
                host="good1", asset=asset, fail_times=0
            )
            good2 = _FailThenSucceedNotify(
                host="good2", asset=asset, fail_times=0
            )

            a = Apprise(asset=asset)
            a.add(good1)
            a.add(bad)
            a.add(good2)

            result = a.notify(body="test")
            assert bool(result) is False
            assert len(result) == 3

            # Order matches add() order: good1, bad, good2.
            results = list(result)
            assert bool(results[0]) is True
            assert bool(results[1]) is False
            assert bool(results[2]) is True
            # good2 was still attempted despite bad raising before it
            assert good2._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_threadpool_raise_does_not_block_other_services(self):
        """Same guarantee as above, but across the thread-pool dispatch
        path (async_mode=True, >1 service)."""
        N_MGR["raise"] = _RaisingNotify
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)
            bad = _RaisingNotify(host="bad", asset=asset)
            good1 = _FailThenSucceedNotify(
                host="good1", asset=asset, fail_times=0
            )
            good2 = _FailThenSucceedNotify(
                host="good2", asset=asset, fail_times=0
            )

            a = Apprise(asset=asset)
            a.add(good1)
            a.add(bad)
            a.add(good2)

            result = a.notify(body="test")
            assert bool(result) is False
            assert len(result) == 3

            # Threadpool dispatch preserves original submission order.
            results = list(result)
            assert bool(results[0]) is True
            assert bool(results[1]) is False
            assert bool(results[2]) is True
            assert good2._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_asyncio_raise_does_not_block_other_services(self):
        """Same guarantee as above, but across the asyncio dispatch path."""
        N_MGR["raise"] = _RaisingNotify
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)
            bad = _RaisingNotify(host="bad", asset=asset)
            good1 = _FailThenSucceedNotify(
                host="good1", asset=asset, fail_times=0
            )
            good2 = _FailThenSucceedNotify(
                host="good2", asset=asset, fail_times=0
            )

            a = Apprise(asset=asset)
            a.add(good1)
            a.add(bad)
            a.add(good2)

            result = asyncio.run(a.async_notify(body="test"))
            assert bool(result) is False
            assert len(result) == 3

            # asyncio dispatch preserves original submission order too.
            results = list(result)
            assert bool(results[0]) is True
            assert bool(results[1]) is False
            assert bool(results[2]) is True
            assert good2._calls == 1
        finally:
            N_MGR.unload_modules()


class TestConfigTagRetry:
    """Config parsers must reject a retry suffix in service tag definitions.

    A tag like 'alerts:3' is only valid at call-time (notify() filter / CLI).
    Putting it in a config file creates ambiguity with the URL ?retry= param
    and the YAML retry: key, so both parsers must warn and skip the entry.
    """

    def test_text_rejects_retry_suffix(self):
        """'alerts:3=json://...' is rejected; no service loaded."""
        services, _ = ConfigBase.config_parse_text("alerts:3=json://localhost")
        assert services == []

    def test_text_rejects_priority_and_retry_in_tag(self):
        """'1:alerts:3=json://...' is rejected (priority + retry suffix)."""
        services, _ = ConfigBase.config_parse_text(
            "1:alerts:3=json://localhost"
        )
        assert services == []

    def test_text_accepts_priority_tag_without_retry(self):
        """'1:alerts=json://...' loads normally (priority prefix, no retry)."""
        services, _ = ConfigBase.config_parse_text("1:alerts=json://localhost")
        assert len(services) == 1

    def test_text_accepts_plain_tag(self):
        """'alerts=json://...' loads normally (no prefix, no retry)."""
        services, _ = ConfigBase.config_parse_text("alerts=json://localhost")
        assert len(services) == 1

    def test_yaml_rejects_retry_suffix(self):
        """YAML 'tag: alerts:3' is rejected; no service loaded."""
        services, _ = ConfigBase.config_parse_yaml(
            "version: 1\nurls:\n  - json://localhost:\n      tag: alerts:3\n"
        )
        assert services == []

    def test_yaml_rejects_priority_and_retry_in_tag(self):
        """YAML 'tag: 1:alerts:3' is rejected (priority + retry suffix)."""
        services, _ = ConfigBase.config_parse_yaml(
            "version: 1\nurls:\n  - json://localhost:\n      tag: 1:alerts:3\n"
        )
        assert services == []

    def test_yaml_accepts_priority_tag_without_retry(self):
        """YAML 'tag: 1:alerts' loads normally (priority prefix, no retry)."""
        services, _ = ConfigBase.config_parse_yaml(
            "version: 1\nurls:\n  - json://localhost:\n      tag: 1:alerts\n"
        )
        assert len(services) == 1

    def test_yaml_accepts_plain_tag(self):
        """YAML 'tag: alerts' loads normally (no prefix, no retry)."""
        services, _ = ConfigBase.config_parse_yaml(
            "version: 1\nurls:\n  - json://localhost:\n      tag: alerts\n"
        )
        assert len(services) == 1

    def test_text_valid_entry_after_rejected_one_still_loads(self):
        """A valid entry that follows a rejected one is still loaded."""
        services, _ = ConfigBase.config_parse_text(
            "alerts:3=json://localhost\nalerts=json://localhost\n"
        )
        assert len(services) == 1

    def test_yaml_valid_entry_after_rejected_one_still_loads(self):
        """A valid entry that follows a rejected one is still loaded."""
        services, _ = ConfigBase.config_parse_yaml(
            "version: 1\n"
            "urls:\n"
            "  - json://localhost:\n"
            "      tag: alerts:3\n"
            "  - json://localhost:\n"
            "      tag: alerts\n"
        )
        assert len(services) == 1


class TestMultiTagDispatch:
    """Per-tag independent escalation and per-service retry for multi-tag OR
    filters.

    When notify() receives a filter with multiple OR tokens (e.g.
    'devops management' or ['devops:3', 'management:2']), each token forms an
    independent escalation chain and each service gets the retry value from the
    token that matched it -- not a single global retry applied to all services.
    """

    def _make_tagged(self, tag_str, asset, fail_times=0):
        """Create a _FailThenSucceedNotify tagged with a single AppriseTag."""
        s = _FailThenSucceedNotify(
            host=tag_str, asset=asset, fail_times=fail_times
        )
        # Assign instance-level set to avoid class-level mutation.
        s.tags = {AppriseTag.parse(tag_str)}
        return s

    def _make_priority_tagged(self, tag_str, asset, fail_times=0):
        """Create a service whose tag is an explicit-priority AppriseTag."""
        ft = AppriseTag.parse(tag_str)
        s = _FailThenSucceedNotify(
            host=str(ft), asset=asset, fail_times=fail_times
        )
        s.tags = {ft}
        return s

    # ------------------------------------------------------------------
    # Per-service retry via space-separated string
    # ------------------------------------------------------------------

    def test_per_service_retry_space_separated_string(self):
        """'devops:3 management:2' applies retry=3 to devops services and
        retry=2 to management services independently."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # devops service: fails 3 times; needs retry=3 to succeed
            s_devops = _FailThenSucceedNotify(
                host="devops", asset=asset, fail_times=3
            )
            s_devops.tags = {"devops"}

            # management service: fails 2 times; needs retry=2 to succeed
            s_mgmt = _FailThenSucceedNotify(
                host="mgmt", asset=asset, fail_times=2
            )
            s_mgmt.tags = {"management"}

            a = Apprise(asset=asset)
            a.add(s_devops)
            a.add(s_mgmt)

            result = a.notify(body="test", tag="devops:3 management:2")
            assert bool(result) is True
            # devops: 1 initial + 3 retries = 4 total calls
            assert s_devops._calls == 4
            # management: 1 initial + 2 retries = 3 total calls
            assert s_mgmt._calls == 3
        finally:
            N_MGR.unload_modules()

    def test_per_service_retry_list_of_tokens(self):
        """['devops:3', 'management:2'] gives the same per-service retry
        result as a space-separated string."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            s_devops = _FailThenSucceedNotify(
                host="devops", asset=asset, fail_times=3
            )
            s_devops.tags = {"devops"}

            s_mgmt = _FailThenSucceedNotify(
                host="mgmt", asset=asset, fail_times=2
            )
            s_mgmt.tags = {"management"}

            a = Apprise(asset=asset)
            a.add(s_devops)
            a.add(s_mgmt)

            result = a.notify(body="test", tag=["devops:3", "management:2"])
            assert bool(result) is True
            assert s_devops._calls == 4
            assert s_mgmt._calls == 3
        finally:
            N_MGR.unload_modules()

    # ------------------------------------------------------------------
    # Independent escalation chains
    # ------------------------------------------------------------------

    def test_independent_chains_do_not_skip(self):
        """When devops chain succeeds at priority-1, management chain still
        dispatches independently -- its priority-1 failure escalates to its
        priority-2 service."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # devops chain: priority-1 succeeds; priority-2 must not fire
            s_devops_p1 = _FailThenSucceedNotify(
                host="d1", asset=asset, fail_times=0
            )
            s_devops_p1.tags = {
                AppriseTag("devops", priority=1, has_priority=True)
            }
            s_devops_p2 = _FailThenSucceedNotify(
                host="d2", asset=asset, fail_times=0
            )
            s_devops_p2.tags = {
                AppriseTag("devops", priority=2, has_priority=True)
            }

            # management chain: priority-1 always fails; must escalate to
            # priority-2
            s_mgmt_p1 = _FailThenSucceedNotify(
                host="m1", asset=asset, fail_times=999
            )
            s_mgmt_p1.tags = {
                AppriseTag("management", priority=1, has_priority=True)
            }
            s_mgmt_p2 = _FailThenSucceedNotify(
                host="m2", asset=asset, fail_times=0
            )
            s_mgmt_p2.tags = {
                AppriseTag("management", priority=2, has_priority=True)
            }

            a = Apprise(asset=asset)
            a.add(s_devops_p1)
            a.add(s_devops_p2)
            a.add(s_mgmt_p1)
            a.add(s_mgmt_p2)

            result = a.notify(body="test", tag="devops management")
            assert bool(result) is True
            assert s_devops_p1._calls == 1  # devops chain: p1 succeeded
            assert s_devops_p2._calls == 0  # never escalated to
            assert s_mgmt_p1._calls == 1  # management chain: p1 failed
            assert s_mgmt_p2._calls == 1  # escalated to p2, succeeded
        finally:
            N_MGR.unload_modules()

    def test_both_chains_must_succeed_for_true(self):
        """notify() returns False when one chain exhausts all priority groups
        without any group fully succeeding."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # devops chain: always succeeds
            s_devops = _FailThenSucceedNotify(
                host="d", asset=asset, fail_times=0
            )
            s_devops.tags = {"devops"}

            # management chain: always fails
            s_mgmt = _FailThenSucceedNotify(
                host="m", asset=asset, fail_times=999
            )
            s_mgmt.tags = {"management"}

            a = Apprise(asset=asset)
            a.add(s_devops)
            a.add(s_mgmt)

            result = a.notify(body="test", tag="devops management")
            assert bool(result) is False
            assert s_devops._calls == 1  # its chain succeeded
            assert s_mgmt._calls == 1  # its chain failed
        finally:
            N_MGR.unload_modules()

    # ------------------------------------------------------------------
    # Explicit-priority list with per-service retry (flat dispatch)
    # ------------------------------------------------------------------

    def test_explicit_priority_list_per_service_retry(self):
        """['1:tag:2', '2:tag:0'] flat-dispatches both services; each gets its
        own retry: the priority-1 service gets retry=2 and the priority-2
        service gets retry=0 (one attempt only)."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # priority-1 service: fails twice; needs retry=2 to succeed
            s1 = _FailThenSucceedNotify(host="h1", asset=asset, fail_times=2)
            s1.tags = {AppriseTag("tag", priority=1, has_priority=True)}

            # priority-2 service: always succeeds; retry=0 means one attempt
            s2 = _FailThenSucceedNotify(host="h2", asset=asset, fail_times=0)
            s2.tags = {AppriseTag("tag", priority=2, has_priority=True)}

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test", tag=["1:tag:2", "2:tag:0"])
            assert bool(result) is True
            # s1: 1 initial + 2 retries = 3 total
            assert s1._calls == 3
            # s2: retry=0 -> exactly 1 attempt
            assert s2._calls == 1
        finally:
            N_MGR.unload_modules()

    # ------------------------------------------------------------------
    # CLI OR format (list of single-element lists)
    # ------------------------------------------------------------------

    def test_cli_or_format_independent_chains(self):
        """CLI --tag 'devops:3' --tag 'management:2' generates
        [['devops:3'], ['management:2']] -- single-element inner lists that
        must be treated as independent OR chains, not AND groups."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            s_devops = _FailThenSucceedNotify(
                host="devops", asset=asset, fail_times=3
            )
            s_devops.tags = {"devops"}

            s_mgmt = _FailThenSucceedNotify(
                host="mgmt", asset=asset, fail_times=2
            )
            s_mgmt.tags = {"management"}

            a = Apprise(asset=asset)
            a.add(s_devops)
            a.add(s_mgmt)

            # Simulate CLI: --tag "devops:3" --tag "management:2"
            cli_tag = [["devops:3"], ["management:2"]]
            result = a.notify(body="test", tag=cli_tag)
            assert bool(result) is True
            assert s_devops._calls == 4  # 1 initial + 3 retries
            assert s_mgmt._calls == 3  # 1 initial + 2 retries
        finally:
            N_MGR.unload_modules()

    def test_cli_and_format_shared_chain(self):
        """CLI --tag 'devops, management' generates [['devops', 'management']]
        -- a multi-element inner list that is an AND condition and uses a
        single shared escalation chain."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # Service must carry BOTH tags to match
            s_both = _FailThenSucceedNotify(
                host="both", asset=asset, fail_times=0
            )
            s_both.tags = {"devops", "management"}

            # Service with only "devops" -- must NOT match AND filter
            s_devonly = _FailThenSucceedNotify(
                host="devonly", asset=asset, fail_times=0
            )
            s_devonly.tags = {"devops"}

            a = Apprise(asset=asset)
            a.add(s_both)
            a.add(s_devonly)

            # Simulate CLI: --tag "devops, management" (AND condition)
            cli_tag = [["devops", "management"]]
            result = a.notify(body="test", tag=cli_tag)
            assert bool(result) is True
            assert s_both._calls == 1  # has both tags -- matched
            assert s_devonly._calls == 0  # missing "management" -- not matched
        finally:
            N_MGR.unload_modules()

    # ------------------------------------------------------------------
    # Edge cases: explicit priority + AND, 3-chain OR, chain exhaustion
    # ------------------------------------------------------------------

    def test_and_filter_explicit_priority_no_match_returns_none(self):
        """AND filter with an explicit priority that no service satisfies
        returns AppriseResultStatus.NOMATCH (no services dispatched at
        all)."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # Service is tagged 'alerts' at priority 2
            s = _FailThenSucceedNotify(host="s", asset=asset, fail_times=0)
            s.tags = {AppriseTag("alerts", priority=2, has_priority=True)}

            a = Apprise(asset=asset)
            a.add(s)

            # Request 'alerts' at priority 1 AND 'backup' -- service has
            # 'alerts' but at priority 2, not 1; nothing matches.
            result = a.notify(body="test", tag=[["1:alerts", "backup"]])
            assert result.status == AppriseResultStatus.NOMATCH
            assert len(result) == 0
            assert s._calls == 0
        finally:
            N_MGR.unload_modules()

    def test_three_or_chains_all_succeed(self):
        """Three independent OR chains each succeed at their first priority
        group; notify() returns True and each service is called once."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            s_a = _FailThenSucceedNotify(host="a", asset=asset, fail_times=0)
            s_a.tags = {"alpha"}

            s_b = _FailThenSucceedNotify(host="b", asset=asset, fail_times=0)
            s_b.tags = {"beta"}

            s_c = _FailThenSucceedNotify(host="c", asset=asset, fail_times=0)
            s_c.tags = {"gamma"}

            a = Apprise(asset=asset)
            a.add(s_a)
            a.add(s_b)
            a.add(s_c)

            result = a.notify(body="test", tag=["alpha", "beta", "gamma"])
            assert bool(result) is True
            assert s_a._calls == 1
            assert s_b._calls == 1
            assert s_c._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_three_or_chains_one_fails_overall_false(self):
        """Three OR chains: two succeed, one exhausts all priority groups.
        notify() returns False even though the other chains succeeded."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            s_a = _FailThenSucceedNotify(host="a", asset=asset, fail_times=0)
            s_a.tags = {"alpha"}

            # beta always fails (fail_times > any possible retry)
            s_b = _FailThenSucceedNotify(host="b", asset=asset, fail_times=99)
            s_b.tags = {"beta"}

            s_c = _FailThenSucceedNotify(host="c", asset=asset, fail_times=0)
            s_c.tags = {"gamma"}

            a = Apprise(asset=asset)
            a.add(s_a)
            a.add(s_b)
            a.add(s_c)

            result = a.notify(body="test", tag=["alpha", "beta", "gamma"])
            assert bool(result) is False
            assert s_a._calls == 1  # alpha succeeded
            assert s_c._calls == 1  # gamma succeeded
        finally:
            N_MGR.unload_modules()

    def test_chain_escalation_to_second_priority_group(self):
        """A chain whose priority-0 group fails escalates to the priority-1
        group; the second group succeeds so notify() returns True."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # priority-0 service: always fails (no retry configured)
            s_p0 = _FailThenSucceedNotify(
                host="p0", asset=asset, fail_times=99
            )
            s_p0.tags = {AppriseTag("alerts", priority=0, has_priority=False)}

            # priority-1 service: succeeds on first attempt
            s_p1 = _FailThenSucceedNotify(host="p1", asset=asset, fail_times=0)
            s_p1.tags = {AppriseTag("alerts", priority=1, has_priority=True)}

            a = Apprise(asset=asset)
            a.add(s_p0)
            a.add(s_p1)

            result = a.notify(body="test", tag="alerts")
            assert bool(result) is True
            # priority-0 group was attempted once and failed
            assert s_p0._calls == 1
            # priority-1 group was then tried as fallback
            assert s_p1._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_all_priority_groups_exhausted_returns_false(self):
        """When every priority group in a chain fails, notify() returns False
        and all groups were attempted in order."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # priority-0 service: always fails
            s_p0 = _FailThenSucceedNotify(
                host="p0", asset=asset, fail_times=99
            )
            s_p0.tags = {AppriseTag("alerts", priority=0, has_priority=False)}

            # priority-1 service: also always fails
            s_p1 = _FailThenSucceedNotify(
                host="p1", asset=asset, fail_times=99
            )
            s_p1.tags = {AppriseTag("alerts", priority=1, has_priority=True)}

            a = Apprise(asset=asset)
            a.add(s_p0)
            a.add(s_p1)

            result = a.notify(body="test", tag="alerts")
            assert bool(result) is False
            # Both groups were attempted
            assert s_p0._calls == 1
            assert s_p1._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_chain_dispatch_future_exception_treated_as_failure(self):
        """An exception escaping _run_batch is caught in the chain-dispatch
        ThreadPoolExecutor loop and treated as a delivery failure.

        Covers the exception fallback that is only reachable when multiple
        chains are active simultaneously
        (triggering the ThreadPoolExecutor path) and _run_batch raises.
        Uses _ExplodingAsset (raises on async_mode access) instead of
        patching a @staticmethod, which is unreliable across Python versions
        when the patched method runs inside a ThreadPoolExecutor worker.
        """
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            # _ExplodingAsset.async_mode raises RuntimeError.  _run_batch
            # reads s.asset.async_mode to split seq/par, so a batch with
            # one of these services raises and the future captures it.
            class _ExplodingAsset(AppriseAsset):
                """Asset whose mode lookup fails inside chain dispatch."""

                @property
                def async_mode(self):
                    """Raise the injected failure when dispatch reads mode."""
                    raise RuntimeError("injected async_mode access")

            # Two services with distinct tags -> two independent chains so
            # the ThreadPoolExecutor path (len(active) > 1) is taken.
            s_a = _FailThenSucceedNotify(
                host="a", asset=_ExplodingAsset(), fail_times=0
            )
            s_a.tags = {"alpha"}

            s_b = _FailThenSucceedNotify(
                host="b", asset=_ExplodingAsset(), fail_times=0
            )
            s_b.tags = {"beta"}

            a = Apprise()
            a.add(s_a)
            a.add(s_b)

            result = a.notify(body="test", tag=["alpha", "beta"])

            # Both chains raised instead of returning True -- overall False.
            assert bool(result) is False
        finally:
            N_MGR.unload_modules()


class TestAbortOnChainFailure:
    """AppriseAsset.abort_on_chain_failure controls early-abort behaviour.

    When False (default): all chains are allowed to complete even if one
    has already failed, so every configured URL gets at least one attempt.
    When True: as soon as any chain exhausts all its priority groups without
    success, notify() returns False immediately without running further
    escalation rounds for the other chains.
    """

    def _make_tagged(self, tag_str, asset, fail_times=0):
        s = _FailThenSucceedNotify(
            host=tag_str, asset=asset, fail_times=fail_times
        )
        s.tags = {tag_str}
        return s

    def test_default_false_all_chains_complete(self):
        """With abort_on_chain_failure=False (default), all chains run to
        completion even if one chain has already failed."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # alpha always succeeds
            s_a = self._make_tagged("alpha", asset, fail_times=0)

            # beta always fails (exhausts its only group immediately)
            s_b = self._make_tagged("beta", asset, fail_times=99)

            # gamma always succeeds
            s_c = self._make_tagged("gamma", asset, fail_times=0)

            a = Apprise(asset=asset)
            a.add(s_a)
            a.add(s_b)
            a.add(s_c)

            result = a.notify(body="test", tag=["alpha", "beta", "gamma"])
            assert bool(result) is False
            # alpha and gamma were still dispatched despite beta failing
            assert s_a._calls == 1
            assert s_b._calls == 1
            assert s_c._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_abort_on_chain_failure_true_stops_early(self):
        """With abort_on_chain_failure=True, once beta exhausts all priority
        groups without success, further escalation rounds for other chains
        are skipped."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False, abort_on_chain_failure=True)

            # alpha: two priority levels; priority-0 always fails
            s_a_p0 = _FailThenSucceedNotify(
                host="a0", asset=asset, fail_times=99
            )
            s_a_p0.tags = {AppriseTag("alpha", priority=0, has_priority=False)}

            s_a_p1 = _FailThenSucceedNotify(
                host="a1", asset=asset, fail_times=0
            )
            s_a_p1.tags = {AppriseTag("alpha", priority=1, has_priority=True)}

            # beta: one priority level; always fails
            s_b = _FailThenSucceedNotify(host="b", asset=asset, fail_times=99)
            s_b.tags = {"beta"}

            a = Apprise(asset=asset)
            a.add(s_a_p0)
            a.add(s_a_p1)
            a.add(s_b)

            result = a.notify(body="test", tag=["alpha", "beta"])
            assert bool(result) is False
            # beta failed in round 1 and was exhausted -- abort triggered.
            # alpha's p1 (escalation) should NOT have been attempted.
            assert s_b._calls == 1
            assert s_a_p0._calls == 1
            assert s_a_p1._calls == 0  # skipped due to early abort
        finally:
            N_MGR.unload_modules()

    def test_abort_on_chain_failure_true_async(self):
        """abort_on_chain_failure=True triggers the same early-abort in
        async_notify()"""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True, abort_on_chain_failure=True)

            # alpha has two priority levels; priority-0 always fails
            s_a_p0 = _FailThenSucceedNotify(
                host="a0", asset=asset, fail_times=99
            )
            s_a_p0.tags = {AppriseTag("alpha", priority=0, has_priority=False)}

            s_a_p1 = _FailThenSucceedNotify(
                host="a1", asset=asset, fail_times=0
            )
            s_a_p1.tags = {AppriseTag("alpha", priority=1, has_priority=True)}

            # beta has one priority level; always fails
            s_b = _FailThenSucceedNotify(host="b", asset=asset, fail_times=99)
            s_b.tags = {"beta"}

            a = Apprise(asset=asset)
            a.add(s_a_p0)
            a.add(s_a_p1)
            a.add(s_b)

            result = asyncio.run(
                a.async_notify(body="test", tag=["alpha", "beta"])
            )
            assert bool(result) is False
            # beta was exhausted in round 1 -- abort fires before alpha's p1
            assert s_b._calls == 1
            assert s_a_p0._calls == 1
            assert s_a_p1._calls == 0
        finally:
            N_MGR.unload_modules()


class TestOptionalService:
    """optional=True silently absorbs per-service delivery failures.

    The overall notify()/async_notify() result evaluates truthy even when
    an optional service cannot be reached, so callers are not penalised
    for "nice to have" endpoints (e.g. home screens, debug logging).
    """

    def test_optional_default_false(self):
        """optional defaults to False on a freshly constructed plugin."""
        nb = _TestNotify(host="localhost")
        assert nb.optional is False

    def test_optional_url_includes_flag(self):
        """url_parameters() always emits optional=yes or optional=no."""
        nb = _TestNotify(host="localhost")
        params = nb.url_parameters()
        assert "optional" in params
        assert params["optional"] == "no"

        nb_opt = _TestNotify(host="localhost", optional=True)
        params_opt = nb_opt.url_parameters()
        assert params_opt["optional"] == "yes"

    def test_optional_parse_url_yes(self):
        """parse_url propagates optional=yes into the results dict."""
        results = _TestNotify.parse_url("test://localhost?optional=yes")
        assert results is not None
        assert results.get("optional") is True

    def test_optional_parse_url_no(self):
        """parse_url propagates optional=no into the results dict."""
        results = _TestNotify.parse_url("test://localhost?optional=no")
        assert results is not None
        assert results.get("optional") is False

    def test_optional_kwarg_sets_attribute(self):
        """Passing optional=True/False to __init__ sets .optional."""
        nb_yes = _TestNotify(host="localhost", optional=True)
        assert nb_yes.optional is True

        nb_no = _TestNotify(host="localhost", optional=False)
        assert nb_no.optional is False

    def test_optional_sequential_failure_absorbed(self):
        """Sequential dispatch: failed optional service -> overall True."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=99)
            s.optional = True

            a = Apprise(asset=asset)
            a.add(s)

            result = a.notify(body="test")
            assert bool(result) is True
            assert s._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_optional_threadpool_failure_absorbed(self):
        """Thread-pool dispatch: failed optional services -> overall True.

        Two async_mode=True services ensure _notify_parallel_threadpool
        uses the actual thread pool (n_calls==1 falls back to sequential).
        """
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)
            s1 = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=99)
            s1.optional = True
            s2 = _FailThenSucceedNotify(host="s2", asset=asset, fail_times=99)
            s2.optional = True

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test")
            assert bool(result) is True
        finally:
            N_MGR.unload_modules()

    def test_optional_asyncio_failure_absorbed(self):
        """Asyncio dispatch: failed optional service -> overall True."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)
            s = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=99)
            s.optional = True

            a = Apprise(asset=asset)
            a.add(s)

            result = asyncio.run(a.async_notify(body="test"))
            assert bool(result) is True
        finally:
            N_MGR.unload_modules()

    def test_optional_all_fail_all_optional_returns_true(self):
        """When every service is optional and every service fails -> True."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)
            for i in range(3):
                s = _FailThenSucceedNotify(
                    host=f"s{i}", asset=asset, fail_times=99
                )
                s.optional = True
                a.add(s)

            result = a.notify(body="test")
            assert bool(result) is True
        finally:
            N_MGR.unload_modules()

    def test_optional_mixed_required_fails_returns_false(self):
        """Required service failure taints result even with optional peers."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s_opt = _FailThenSucceedNotify(
                host="opt", asset=asset, fail_times=99
            )
            s_opt.optional = True

            s_req = _FailThenSucceedNotify(
                host="req", asset=asset, fail_times=99
            )
            # s_req.optional is False (default)

            a = Apprise(asset=asset)
            a.add(s_opt)
            a.add(s_req)

            result = a.notify(body="test")
            assert bool(result) is False
        finally:
            N_MGR.unload_modules()

    def test_optional_success_unaffected(self):
        """An optional service that succeeds is still counted as True."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=0)
            s.optional = True

            a = Apprise(asset=asset)
            a.add(s)

            result = a.notify(body="test")
            assert bool(result) is True
            assert s._calls == 1
        finally:
            N_MGR.unload_modules()


class TestPartialStatus:
    """AppriseResultStatus.PARTIAL: a batch where at least one service
    genuinely delivered and at least one did not, in the same call."""

    def test_mixed_success_and_failure_is_partial(self):
        """One service succeeds, one fails outright -> PARTIAL, not
        FAILURE."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s_ok = _FailThenSucceedNotify(host="ok", asset=asset, fail_times=0)
            s_fail = _FailThenSucceedNotify(
                host="fail", asset=asset, fail_times=99
            )

            a = Apprise(asset=asset)
            a.add(s_ok)
            a.add(s_fail)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.PARTIAL
            # PARTIAL is not the truthy SUCCESS value.
            assert bool(result) is False
        finally:
            N_MGR.unload_modules()

    def test_all_succeed_is_success_not_partial(self):
        """Every service succeeding stays SUCCESS -- PARTIAL requires at
        least one non-delivery in the same batch."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s1 = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=0)
            s2 = _FailThenSucceedNotify(host="s2", asset=asset, fail_times=0)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.SUCCESS
        finally:
            N_MGR.unload_modules()

    def test_all_fail_is_failure_not_partial(self):
        """Every service failing outright stays FAILURE -- there is no
        genuine success in the batch to make it PARTIAL."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s1 = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=99)
            s2 = _FailThenSucceedNotify(host="s2", asset=asset, fail_times=99)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.FAILURE
        finally:
            N_MGR.unload_modules()

    def test_optional_absorbed_failure_does_not_count_as_partial(self):
        """A forgiven optional=yes failure does not count as a 'genuine'
        success -- an optional service that never actually delivered,
        paired with a required service that also failed, is still a
        clean FAILURE, not PARTIAL."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s_opt = _FailThenSucceedNotify(
                host="opt", asset=asset, fail_times=99
            )
            s_opt.optional = True
            s_req = _FailThenSucceedNotify(
                host="req", asset=asset, fail_times=99
            )

            a = Apprise(asset=asset)
            a.add(s_opt)
            a.add(s_req)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.FAILURE
        finally:
            N_MGR.unload_modules()

    def test_success_plus_timeout_is_partial(self):
        """One service succeeds, another times out with no failures at
        all -- still a mixed outcome, so PARTIAL rather than TIMEOUT.

        async_mode=True with 2+ services is required so dispatch actually
        goes through _notify_parallel_threadpool -- only that path (and
        the asyncio one) can genuinely abandon an in-flight call via a
        bounded wait; _notify_sequential has no way to stop waiting on a
        single already-blocking call, so s_slow would just eventually
        succeed there instead of timing out.
        """
        N_MGR["failpass"] = _FailThenSucceedNotify
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.05)
            s_ok = _FailThenSucceedNotify(host="ok", asset=asset, fail_times=0)
            s_slow = _SlowNotify(host="slow", asset=asset, delay=0.3)

            a = Apprise(asset=asset)
            a.add(s_ok)
            a.add(s_slow)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.PARTIAL
        finally:
            N_MGR.unload_modules()

    def test_async_notify_mixed_outcome_is_partial(self):
        """The asyncio dispatch path reports PARTIAL the same way as the
        synchronous paths."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)
            s_ok = _FailThenSucceedNotify(host="ok", asset=asset, fail_times=0)
            s_fail = _FailThenSucceedNotify(
                host="fail", asset=asset, fail_times=99
            )

            a = Apprise(asset=asset)
            a.add(s_ok)
            a.add(s_fail)

            result = asyncio.run(a.async_notify(body="test"))
            assert result.status == AppriseResultStatus.PARTIAL
        finally:
            N_MGR.unload_modules()


class TestCreateNotifyCalls:
    """Cover Apprise._create_notify_calls() which splits services into
    sequential and parallel buckets based on their asset.async_mode flag."""

    def test_splits_sequential_and_parallel(self):
        """Sequential and parallel services are split into separate lists."""
        N_MGR["failpass"] = _FailThenSucceedNotify
        try:
            # With async_mode=False all loaded services go to the sequential
            # bucket; the parallel bucket remains empty.
            asset_seq = AppriseAsset(async_mode=False)
            s_seq = _FailThenSucceedNotify(
                host="s1", asset=asset_seq, fail_times=0
            )

            a = Apprise(asset=asset_seq)
            a.add(s_seq)

            seq, par = a._create_notify_calls(body="test")
            assert len(seq) == 1
            assert len(par) == 0

            # With async_mode=True the same service is placed in the parallel
            # bucket instead.
            asset_par = AppriseAsset(async_mode=True)
            s_par = _FailThenSucceedNotify(
                host="s2", asset=asset_par, fail_times=0
            )

            b = Apprise(asset=asset_par)
            b.add(s_par)

            seq2, par2 = b._create_notify_calls(body="test")
            assert len(seq2) == 0
            assert len(par2) == 1
        finally:
            N_MGR.unload_modules()


class TestAsyncioSafetyNet:
    """Cover async safety nets for exceptions that escape do_call."""

    def test_exception_outside_try_block_triggers_safety_net(self):
        """A retry-property failure is reported beside a good service."""

        class _RaisingRetryService:
            """Service whose retry property fails before delivery starts."""

            service_name = "raiser"
            asset = AppriseAsset(async_mode=True)
            optional = False

            @property
            def retry(self):
                """Raise before per-attempt handling to test the safety net."""
                # This escapes do_call and is captured by asyncio.gather.
                raise RuntimeError("injected: property raised outside try")

            async def async_notify(self, **kwargs):
                """Represent delivery that must not be reached in this test."""
                return True  # pragma: no cover -- never reached

        class _GoodService:
            """Minimal well-behaved service that succeeds immediately."""

            service_name = "good"
            asset = AppriseAsset(async_mode=True)
            optional = False
            tags = set()

            def url(self, privacy=False):
                """Return the stable URL used to identify this service."""
                return "good://localhost"

            def url_id(self):
                """Return a stable identifier for result assertions."""
                return "good-id"

            def __len__(self):
                """Report the single target represented by this service."""
                return 1

            async def async_notify(self, **kwargs):
                """Report immediate successful asynchronous delivery."""
                return True

        raiser = _RaisingRetryService()
        good = _GoodService()
        # Exercise both the escaped-exception and successful-result branches.
        ok, results = asyncio.run(
            Apprise._notify_parallel_asyncio((raiser, {}), (good, {}))
        )
        assert ok is False
        assert len(results) == 2


class TestServiceTimeout:
    """AppriseAsset._service_timeout / notify(timeout=...) enforcement.

    Real sleeps are intentional here: these tests protect threaded/async
    deadline behaviour. Margins stay generous so slower CI hosts fail only for
    real regressions, not ordinary timing jitter.
    """

    def test_sequential_between_attempts_timeout(self):
        """A real failure before timeout remains a FAILURE."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=False, service_timeout=0.5)
            # First attempt costs 0.1s and fails, leaving ~0.4s of the
            # 0.5s budget.  retry=5 with wait=5.0 would normally sleep
            # five seconds between attempts, but that must be capped to
            # the remaining budget, and no second attempt may start.
            service = _SlowNotify(
                host="x", asset=asset, delay=0.0, retry=5, wait=5.0
            )
            service.send = lambda **kw: (time.sleep(0.1), False)[1]
            a = Apprise(asset=asset)
            a.add(service)

            t0 = time.monotonic()
            result = a.notify(body="test")
            wall = time.monotonic() - t0
        finally:
            N_MGR.unload_modules()

        r0 = next(iter(result))
        # One real attempt ran; the expired retry is recorded as TIMEOUT.
        assert len(r0.attempts) == 2
        assert r0.attempts[0].status == AppriseResultStatus.FAILURE
        assert r0.attempts[-1].status == AppriseResultStatus.TIMEOUT
        assert r0.max_attempts == 6
        # The confirmed FAILURE outranks the trailing synthetic TIMEOUT.
        assert r0.status == AppriseResultStatus.FAILURE
        assert result.status == AppriseResultStatus.FAILURE
        # The wait= sleep was capped to the remaining budget, not the
        # full 5.0s -- confirms the cap actually applied.
        assert wall < 3.0

    def test_threadpool_between_attempts_timeout_and_sleep_cap(self):
        """Thread-pool retry sleep is capped by the worker deadline."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=2.0)
            # The failed first attempt leaves enough budget for the worker to
            # cap wait=5.0 itself before the outer bounded wait races it.
            slow = _SlowNotify(
                host="slow", asset=asset, delay=0.0, retry=3, wait=5.0
            )
            slow.send = lambda **kw: (time.sleep(0.3), False)[1]
            fast = _SlowNotify(host="fast", asset=asset, delay=0.0)
            a = Apprise(asset=asset)
            a.add(slow)
            a.add(fast)

            t0 = time.monotonic()
            result = a.notify(body="test")
            wall = time.monotonic() - t0
        finally:
            N_MGR.unload_modules()

        by_host = {r.url: r for r in result}
        slow_result = by_host["slow://slow"]
        # Only the one over-budget attempt was made, plus the synthetic
        # TIMEOUT attempt marking the decision to stop.
        assert len(slow_result.attempts) == 2
        assert slow_result.attempts[0].status == AppriseResultStatus.FAILURE
        assert slow_result.attempts[-1].status == AppriseResultStatus.TIMEOUT
        # The confirmed FAILURE on the first attempt outranks the
        # synthetic TIMEOUT that follows it (see NotifyResult.__init__).
        assert slow_result.status == AppriseResultStatus.FAILURE
        assert by_host["slow://fast"].status == AppriseResultStatus.SUCCESS
        # The wait= sleep was capped to the remaining budget rather than
        # running the full 5.0s -- confirms the cap actually applied.
        assert wall < 5.0

    def test_asyncio_between_attempts_timeout_and_sleep_cap(self):
        """Same guarantee as the thread-pool test above, for the asyncio
        do_call() coroutine's own between-attempts deadline check."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=2.0)
            slow = _SlowNotify(
                host="slow", asset=asset, delay=0.0, retry=3, wait=5.0
            )

            async def _fail_slowly(**kw):
                """Delay briefly, then fail so retry waiting consumes time."""
                await asyncio.sleep(0.3)
                return False

            slow.async_notify = _fail_slowly
            fast = _SlowNotify(host="fast", asset=asset, delay=0.0)
            a = Apprise(asset=asset)
            a.add(slow)
            a.add(fast)

            t0 = time.monotonic()
            result = asyncio.run(a.async_notify(body="test"))
            wall = time.monotonic() - t0
        finally:
            N_MGR.unload_modules()

        by_host = {r.url: r for r in result}
        slow_result = by_host["slow://slow"]
        assert len(slow_result.attempts) == 2
        assert slow_result.attempts[0].status == AppriseResultStatus.FAILURE
        assert slow_result.attempts[-1].status == AppriseResultStatus.TIMEOUT
        # The confirmed FAILURE on the first attempt outranks the
        # synthetic TIMEOUT that follows it (see NotifyResult.__init__).
        assert slow_result.status == AppriseResultStatus.FAILURE
        assert by_host["slow://fast"].status == AppriseResultStatus.SUCCESS
        assert wall < 5.0

    def test_sequential_service_timeout_disabled(self):
        """service_timeout=0 disables the cap -- a slow service still
        completes normally."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=False, service_timeout=0)
            service = _SlowNotify(host="x", asset=asset, delay=0.05)
            a = Apprise(asset=asset)
            a.add(service)

            result = a.notify(body="test")
        finally:
            N_MGR.unload_modules()

        r0 = next(iter(result))
        assert r0.status == AppriseResultStatus.SUCCESS
        assert service.calls == 1

    def test_sequential_timeout_disabled_retry_wait(self):
        """With service_timeout=0 (no deadline at all), the retry/wait
        loop keeps its normal uncapped wait behaviour."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=False, service_timeout=0)
            service = _SlowNotify(
                host="x", asset=asset, delay=0.0, retry=1, wait=0.01
            )
            call_count = {"n": 0}

            def _fail_then_succeed(**kw):
                """Fail once, then succeed to exercise an uncapped retry."""
                call_count["n"] += 1
                return call_count["n"] >= 2

            service.send = _fail_then_succeed
            a = Apprise(asset=asset)
            a.add(service)

            result = a.notify(body="test")
        finally:
            N_MGR.unload_modules()

        r0 = next(iter(result))
        assert r0.status == AppriseResultStatus.SUCCESS
        assert len(r0.attempts) == 2

    def test_threadpool_outer_bound_abandons_slow_service(self):
        """A service stuck past its deadline is abandoned by the outer
        bounded wait; the batch returns promptly and the other service is
        unaffected."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.5)
            slow = _SlowNotify(host="slow", asset=asset, delay=2.0)
            fast = _SlowNotify(host="fast", asset=asset, delay=0.0)
            a = Apprise(asset=asset)
            a.add(slow)
            a.add(fast)

            t0 = time.monotonic()
            result = a.notify(body="test")
            wall = time.monotonic() - t0
        finally:
            N_MGR.unload_modules()

        # The whole call returned promptly -- nowhere near the slow
        # service's 2.0s delay -- even though that thread is still
        # running in the background because Python cannot stop the worker.
        assert wall < 3.0
        by_host = {r.url: r for r in result}
        assert by_host["slow://slow"].status == (AppriseResultStatus.TIMEOUT)
        assert by_host["slow://fast"].status == (AppriseResultStatus.SUCCESS)

    def test_asyncio_outer_bound_abandons_slow_service(self):
        """Same guarantee as the thread-pool test, for async_notify()."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.5)
            slow = _SlowNotify(host="slow", asset=asset, delay=2.0)
            fast = _SlowNotify(host="fast", asset=asset, delay=0.0)
            a = Apprise(asset=asset)
            a.add(slow)
            a.add(fast)

            t0 = time.monotonic()
            result = asyncio.run(a.async_notify(body="test"))
            wall = time.monotonic() - t0
        finally:
            N_MGR.unload_modules()

        assert wall < 3.0
        by_host = {r.url: r for r in result}
        assert by_host["slow://slow"].status == (AppriseResultStatus.TIMEOUT)
        assert by_host["slow://fast"].status == (AppriseResultStatus.SUCCESS)

    def test_threadpool_timeout_disabled_retry_wait(self):
        """With service_timeout=0, the thread-pool worker's retry/wait
        loop keeps its normal uncapped wait behaviour."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0)
            call_count = {"n": 0}

            def _fail_then_succeed(**kw):
                """Fail once, then succeed in the thread-pool retry loop."""
                call_count["n"] += 1
                return call_count["n"] >= 2

            flaky = _SlowNotify(
                host="flaky", asset=asset, delay=0.0, retry=1, wait=0.01
            )
            flaky.send = _fail_then_succeed
            other = _SlowNotify(host="other", asset=asset, delay=0.0)
            a = Apprise(asset=asset)
            a.add(flaky)
            a.add(other)

            result = a.notify(body="test")
        finally:
            N_MGR.unload_modules()

        by_host = {r.url: r for r in result}
        assert by_host["slow://flaky"].status == AppriseResultStatus.SUCCESS
        assert len(by_host["slow://flaky"].attempts) == 2
        assert by_host["slow://other"].status == AppriseResultStatus.SUCCESS

    def test_asyncio_timeout_disabled_retry_wait(self):
        """Same guarantee as the thread-pool test above, for the asyncio
        do_call() coroutine's retry/wait loop."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0)
            call_count = {"n": 0}

            async def _fail_then_succeed(**kw):
                """Fail once, then succeed in the asyncio retry loop."""
                call_count["n"] += 1
                return call_count["n"] >= 2

            flaky = _SlowNotify(
                host="flaky", asset=asset, delay=0.0, retry=1, wait=0.01
            )
            flaky.async_notify = _fail_then_succeed
            other = _SlowNotify(host="other", asset=asset, delay=0.0)
            a = Apprise(asset=asset)
            a.add(flaky)
            a.add(other)

            result = asyncio.run(a.async_notify(body="test"))
        finally:
            N_MGR.unload_modules()

        by_host = {r.url: r for r in result}
        assert by_host["slow://flaky"].status == AppriseResultStatus.SUCCESS
        assert len(by_host["slow://flaky"].attempts) == 2
        assert by_host["slow://other"].status == AppriseResultStatus.SUCCESS

    def test_notify_timeout_overrides_longer_asset_default(self):
        """notify(timeout=...) can cut a call short even when the asset
        default would have allowed more time."""
        N_MGR["slow"] = _SlowNotify

        try:
            # Asset default is generous (10s); the call-level override
            # of 0.5s must win since it is the sooner of the two.
            asset = AppriseAsset(async_mode=True, service_timeout=10)
            slow1 = _SlowNotify(host="one", asset=asset, delay=2.0)
            slow2 = _SlowNotify(host="two", asset=asset, delay=2.0)
            a = Apprise(asset=asset)
            a.add(slow1)
            a.add(slow2)

            t0 = time.monotonic()
            result = a.notify(body="test", timeout=0.5)
            wall = time.monotonic() - t0
        finally:
            N_MGR.unload_modules()

        assert wall < 3.0
        assert all(r.status == AppriseResultStatus.TIMEOUT for r in result)

    def test_notify_timeout_keeps_stricter_asset_default(self):
        """The reverse also holds: a short asset default still applies
        even when notify(timeout=...) allows much more time."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.5)
            slow1 = _SlowNotify(host="one", asset=asset, delay=2.0)
            slow2 = _SlowNotify(host="two", asset=asset, delay=2.0)
            a = Apprise(asset=asset)
            a.add(slow1)
            a.add(slow2)

            t0 = time.monotonic()
            result = a.notify(body="test", timeout=60)
            wall = time.monotonic() - t0
        finally:
            N_MGR.unload_modules()

        assert wall < 3.0
        assert all(r.status == AppriseResultStatus.TIMEOUT for r in result)

    def test_notify_negative_timeout_raises(self):
        """notify(timeout=-1) is a caller error, not a silent no-op."""
        a = Apprise()
        a.add("json://localhost")
        with pytest.raises(ValueError):
            a.notify(body="test", timeout=-1)

    def test_async_notify_negative_timeout_raises(self):
        """async_notify(timeout=-1) is a caller error, not a silent
        no-op."""
        a = Apprise()
        a.add("json://localhost")
        with pytest.raises(ValueError):
            asyncio.run(a.async_notify(body="test", timeout=-1))

    def test_notify_infinite_timeout_raises(self):
        """notify(timeout=inf) is rejected; 0 is the unbounded spelling."""
        a = Apprise()
        a.add("json://localhost")
        with pytest.raises(ValueError):
            a.notify(body="test", timeout=float("inf"))

    def test_notify_nan_timeout_raises(self):
        """notify(timeout=nan) is rejected instead of disabling the timeout."""
        a = Apprise()
        a.add("json://localhost")
        with pytest.raises(ValueError):
            a.notify(body="test", timeout=float("nan"))

    def test_async_notify_infinite_timeout_raises(self):
        """async_notify(timeout=inf) is rejected for the same reason as
        notify(timeout=inf)."""
        a = Apprise()
        a.add("json://localhost")
        with pytest.raises(ValueError):
            asyncio.run(a.async_notify(body="test", timeout=float("inf")))

    def test_notify_non_numeric_timeout_raises_typeerror(self):
        """notify(timeout="abc") raises TypeError."""
        a = Apprise()
        a.add("json://localhost")
        with pytest.raises(TypeError):
            a.notify(body="test", timeout="abc")

    def test_notify_bool_timeout_raises_typeerror(self):
        """A bool timeout is rejected even though bool is an int subclass."""
        a = Apprise()
        a.add("json://localhost")
        with pytest.raises(TypeError):
            a.notify(body="test", timeout=True)

    def test_async_notify_non_numeric_timeout_raises_typeerror(self):
        """async_notify(timeout="abc") is a caller error (TypeError)."""
        a = Apprise()
        a.add("json://localhost")
        with pytest.raises(TypeError):
            asyncio.run(a.async_notify(body="test", timeout="abc"))

    def test_notify_timeout_defaults_to_zero(self):
        """timeout defaults to 0 (no call-level override) -- only
        AppriseAsset._service_timeout controls the default behaviour."""
        import inspect

        signature = inspect.signature(Apprise.notify)
        assert signature.parameters["timeout"].default == 0

    def test_timeout_logs_include_error_entry(self):
        """A TIMEOUT attempt includes a matching ERROR log entry."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=False, service_timeout=0.5)
            service = _SlowNotify(host="x", asset=asset, retry=5)
            service.send = lambda **kw: (time.sleep(0.15), False)[1]
            a = Apprise(asset=asset)
            a.add(service)

            result = a.notify(body="test")
        finally:
            N_MGR.unload_modules()

        r0 = next(iter(result))
        # The earlier real failures still outrank the later timeout.
        assert r0.status == AppriseResultStatus.FAILURE
        assert r0.attempts[-1].status == AppriseResultStatus.TIMEOUT
        error_logs = [entry for entry in r0.logs() if entry.level == "ERROR"]
        assert len(error_logs) == 1
        assert "did not finish" in error_logs[0].message
        assert r0.name in error_logs[0].message

    def test_timeout_result_json_includes_start_end_time(self):
        """A TIMEOUT NotifyResult still has start_time/end_time populated."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.5)
            slow = _SlowNotify(host="slow", asset=asset, delay=3.0)
            fast = _SlowNotify(host="fast", asset=asset, delay=0.0)
            a = Apprise(asset=asset)
            a.add(slow)
            a.add(fast)

            result = a.notify(body="test")
        finally:
            N_MGR.unload_modules()

        by_host = {r.url: r for r in result}
        r0 = by_host["slow://slow"]
        assert r0.status == AppriseResultStatus.TIMEOUT
        assert r0.start_time is not None
        assert r0.end_time is not None
        # Datetime arithmetic can differ from float elapsed by tiny rounding.
        assert (r0.end_time - r0.start_time).total_seconds() == pytest.approx(
            r0.elapsed, abs=1e-5
        )

    def test_weight_reflects_service_len(self):
        """NotifyResult.weight mirrors len(service) (the plugin's own
        target count)."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=False)
            service = _SlowNotify(host="x", asset=asset, delay=0.0)
            a = Apprise(asset=asset)
            a.add(service)

            result = a.notify(body="test")
        finally:
            N_MGR.unload_modules()

        # _SlowNotify has no targets/list -- NotifyBase.__len__ always
        # reports at least 1.
        assert next(iter(result)).weight == len(service) == 1

    def test_log_capture_records_warning_message(self):
        """A service WARNING is captured in NotifyResult.logs()."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=False)
            service = _SlowNotify(host="x", asset=asset, delay=0.0)

            def _fail_with_warning(**kw):
                """Emit a warning before reporting a delivery failure."""
                service.logger.warning("HTTP 429 Too Many Requests")
                return False

            service.send = _fail_with_warning
            a = Apprise(asset=asset)
            a.add(service)

            logging.disable(logging.NOTSET)
            try:
                result = a.notify(body="test")
            finally:
                logging.disable(logging.CRITICAL)
        finally:
            N_MGR.unload_modules()

        r0 = next(iter(result))
        assert r0.status == AppriseResultStatus.FAILURE
        logs = list(r0.logs())
        assert len(logs) == 1
        assert logs[0].level == "WARNING"
        assert "429" in logs[0].message
        assert "429" in str(logs[0])

    def test_log_capture_preserves_preexisting_instance_logger(self):
        """_ServiceLogCapture does not replace a service's logger."""
        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=False)
            service = _SlowNotify(host="x", asset=asset, delay=0.0)
            custom_logger = logging.getLogger("apprise.test.custom")
            service.logger = custom_logger

            a = Apprise(asset=asset)
            a.add(service)
            a.notify(body="test")
        finally:
            N_MGR.unload_modules()

        assert "logger" in service.__dict__
        assert service.__dict__["logger"] is custom_logger

    def test_notify_log_callback_default_from_apprise_instance(self):
        """A log_callback given to Apprise() applies to every notify()
        call made with that instance, firing live with (entry, service)
        for each captured entry."""
        N_MGR["slow"] = _SlowNotify
        received = []

        def _cb(entry, service):
            """Collect the instance-level callback's service/message pair."""
            received.append((service.service_name, entry.message))

        try:
            asset = AppriseAsset(async_mode=False)
            service = _SlowNotify(host="x", asset=asset, delay=0.0)

            def _fail_with_warning(**kw):
                """Emit a warning and report a failed delivery attempt."""
                service.logger.warning("HTTP 429 Too Many Requests")
                return False

            service.send = _fail_with_warning
            a = Apprise(asset=asset, log_callback=_cb)
            a.add(service)

            logging.disable(logging.NOTSET)
            try:
                a.notify(body="test")
            finally:
                logging.disable(logging.CRITICAL)
        finally:
            N_MGR.unload_modules()

        assert received == [
            (service.service_name, "HTTP 429 Too Many Requests")
        ]

    def test_notify_log_callback_call_override(self):
        """log_callback passed directly to notify() takes priority over
        the Apprise instance's own default for that one call only."""
        N_MGR["slow"] = _SlowNotify
        default_received = []
        override_received = []

        def _default_cb(entry, service):
            """Collect entries delivered to the instance default callback."""
            default_received.append(entry.message)

        def _override_cb(entry, service):
            """Collect entries delivered to the per-call override callback."""
            override_received.append(entry.message)

        try:
            asset = AppriseAsset(async_mode=False)
            service = _SlowNotify(host="x", asset=asset, delay=0.0)

            def _fail_with_warning(**kw):
                """Emit a warning and report a failed delivery attempt."""
                service.logger.warning("overridden call")
                return False

            service.send = _fail_with_warning
            a = Apprise(asset=asset, log_callback=_default_cb)
            a.add(service)

            logging.disable(logging.NOTSET)
            try:
                a.notify(body="test", log_callback=_override_cb)
            finally:
                logging.disable(logging.CRITICAL)
        finally:
            N_MGR.unload_modules()

        assert default_received == []
        assert override_received == ["overridden call"]

    def test_async_notify_log_callback(self):
        """log_callback works for a plugin's native async_notify()."""
        N_MGR["slow"] = _SlowNotify
        received = []

        def _cb(entry, service):
            """Collect callback entries produced by async_notify()."""
            received.append((service.service_name, entry.message))

        try:
            asset = AppriseAsset(async_mode=True)
            service = _SlowNotify(host="x", asset=asset, delay=0.0)

            async def _fail_with_warning(**kw):
                """Emit a warning from the native async_notify override."""
                service.logger.warning("async 429")
                return False

            service.async_notify = _fail_with_warning
            a = Apprise(asset=asset, log_callback=_cb)
            a.add(service)

            logging.disable(logging.NOTSET)
            try:
                asyncio.run(a.async_notify(body="test"))
            finally:
                logging.disable(logging.CRITICAL)
        finally:
            N_MGR.unload_modules()

        assert received == [(service.service_name, "async 429")]

    def test_notify_log_callback_thread_attribution(self):
        """Concurrent log callbacks are attributed to the right service."""
        N_MGR["slow"] = _SlowNotify
        received = []
        lock = threading.Lock()

        def _cb(entry, service):
            """Append callback data under a lock."""
            with lock:
                received.append((service.host, entry.message))

        def _make_send(service):
            """Build a send() replacement bound to one service instance."""

            def _send(**kw):
                """Emit a host-specific warning from the bound service."""
                service.logger.warning("warning from %s", service.host)
                return True

            return _send

        try:
            asset = AppriseAsset(async_mode=True)
            a = Apprise(asset=asset, log_callback=_cb)
            services = []
            for i in range(6):
                service = _SlowNotify(host=f"host{i}", asset=asset, delay=0.02)
                service.send = _make_send(service)
                services.append(service)
                a.add(service)

            logging.disable(logging.NOTSET)
            try:
                a.notify(body="test")
            finally:
                logging.disable(logging.CRITICAL)
        finally:
            N_MGR.unload_modules()

        assert sorted(received) == sorted(
            (s.host, f"warning from {s.host}") for s in services
        )

    def test_timeout_result_defensive_on_malformed_service(self):
        """Timeout metadata falls back when service helpers are missing."""

        class _MalformedSlowService:
            """A service missing url()/url_id()/__len__ that never finishes
            in time, exercising _timeout_result's defensive except paths.
            """

            service_name = "malformed"
            asset = AppriseAsset(async_mode=True, service_timeout=0.1)
            optional = False
            tags: set = set()
            retry = 0
            wait = 0.0

            async def async_notify(self, **kwargs):
                """Remain active long enough to exceed the test deadline."""
                await asyncio.sleep(1.0)
                return True  # pragma: no cover -- never reached in time

        good = _SlowNotify(
            host="good", asset=AppriseAsset(async_mode=True), delay=0.0
        )
        malformed = _MalformedSlowService()

        ok, results = asyncio.run(
            Apprise._notify_parallel_asyncio(
                (malformed, {}),
                (good, {}),
            )
        )

        assert ok is False
        by_url = {r.url: r for r in results}
        # No url()/url_id()/__len__ on the malformed service -- defensive
        # fallbacks kick in rather than raising.
        assert by_url["unknown://"].status == AppriseResultStatus.TIMEOUT
        assert by_url["unknown://"].url_id is None
        assert by_url["unknown://"].weight == 1
        assert by_url["slow://good"].status == AppriseResultStatus.SUCCESS

    def test_notify_result_tag_is_sorted(self):
        """NotifyResult.tag is sorted for stable output."""
        N_MGR["slow"] = _SlowNotify

        try:
            service = _SlowNotify(
                host="x",
                asset=AppriseAsset(async_mode=False),
                delay=0.0,
                tag=["zeta", "alpha", "middle", "beta"],
            )
            a = Apprise()
            a.add(service)
            result = a.notify(body="test")
        finally:
            N_MGR.unload_modules()

        r0 = next(iter(result))
        assert r0.tag == ("alpha", "beta", "middle", "zeta")

    def test_threadpool_queued_futures_cancelled(self):
        """A service still queued behind other work in a size-limited
        thread pool must not execute later after timeout."""
        N_MGR["slow"] = _SlowNotify

        # More services than the default ThreadPoolExecutor can run at once,
        # so some work is guaranteed to still be queued at the deadline.
        n_services = 40
        started: list[int] = []
        finished: list[int] = []
        lock = threading.Lock()

        def _slow_send(idx):
            """Build a send() replacement that records start and finish."""

            def _send(**kwargs):
                """Simulate slow work so queued futures can be cancelled."""
                with lock:
                    started.append(idx)
                time.sleep(0.3)
                with lock:
                    finished.append(idx)
                return True

            return _send

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.05)
            a = Apprise(asset=asset)
            services = []
            for i in range(n_services):
                service = _SlowNotify(host=f"host{i}", asset=asset, delay=0.0)
                service.send = _slow_send(i)
                services.append(service)
                a.add(service)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.TIMEOUT

            with lock:
                started_at_return = len(started)

            # Give uncancelled queued work enough time to reveal itself.
            time.sleep(1.0)
            with lock:
                started_later = len(started)
                finished_later = len(finished)
        finally:
            N_MGR.unload_modules()

        # Some work stayed queued because the pool is size-limited.
        assert 0 < started_at_return < n_services
        # And none of the ones that hadn't started yet ever did.
        assert started_later == started_at_return
        assert finished_later == started_at_return

    def test_threadpool_shared_across_notify_calls(self):
        """Separate notify() calls reuse the shared executor."""
        N_MGR["slow"] = _SlowNotify

        try:
            import apprise.apprise as apprise_module

            # Force this test to observe executor construction.
            with mock.patch("apprise.apprise._shared_executor", None):
                executors_seen = set()
                for i in range(3):
                    asset = AppriseAsset(async_mode=True, service_timeout=0.05)
                    a = Apprise(asset=asset)
                    service = _SlowNotify(
                        host=f"host{i}", asset=asset, delay=1.0
                    )
                    a.add(service)
                    result = a.notify(body="test")
                    assert result.status == AppriseResultStatus.TIMEOUT
                    executors_seen.add(id(apprise_module._shared_executor))

                # All three notify() calls reused the same executor.
                assert len(executors_seen) == 1

                # Clean up the temporary executor before mock.patch restores.
                apprise_module._shared_executor.shutdown(wait=False)
        finally:
            N_MGR.unload_modules()

    def test_abandoned_calls_reflect_running_state(self):
        """Tracked abandoned calls clear once their background work ends."""
        import apprise.apprise as apprise_module

        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.05)
            a = Apprise(asset=asset)
            service = _SlowNotify(host="host", asset=asset, delay=0.5)
            a.add(service)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.TIMEOUT

            # The 0.5s send() is still running in the background --
            # notify() only gave up waiting on it, it did not stop it.
            assert apprise_module._any_abandoned_calls_still_running() is True

            # Give it a generous window to actually finish.
            time.sleep(0.7)
            assert apprise_module._any_abandoned_calls_still_running() is False
        finally:
            N_MGR.unload_modules()

    def test_abandoned_call_descriptions_clear(self):
        """Abandoned-call descriptions clear once the service finishes."""
        import apprise.apprise as apprise_module

        N_MGR["slow"] = _SlowNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.05)
            a = Apprise(asset=asset)
            service = _SlowNotify(
                host="descriptionhost", asset=asset, delay=0.5
            )
            a.add(service)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.TIMEOUT

            descriptions = apprise_module._abandoned_call_descriptions()
            assert len(descriptions) == 1
            assert "slow://descriptionhost" in descriptions[0]

            # Once the service finishes, its abandoned-call description clears.
            time.sleep(0.7)
            assert apprise_module._abandoned_call_descriptions() == []
        finally:
            N_MGR.unload_modules()

    def test_abandoned_calls_false_when_only_queued(self):
        """Cancelled queued work does not count as still running."""
        import apprise.apprise as apprise_module

        N_MGR["slow"] = _SlowNotify

        n_services = 40
        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.05)
            a = Apprise(asset=asset)
            for i in range(n_services):
                service = _SlowNotify(host=f"host{i}", asset=asset, delay=0.3)
                a.add(service)

            result = a.notify(body="test")
            assert result.status == AppriseResultStatus.TIMEOUT

            # Queued futures are cancelled before they ever touch the tracked
            # abandoned-call list; any running work should settle quickly.
            time.sleep(0.5)
            assert apprise_module._any_abandoned_calls_still_running() is False
        finally:
            N_MGR.unload_modules()


class _SlowFailNotify(NotifyBase):
    """Fails after a configurable delay so deadlines can pass mid-attempt."""

    app_id = "SlowFailApp"
    app_desc = "Test"
    notify_url = "slowfail://"
    title_maxlen = 250
    body_maxlen = 32768

    def __init__(self, delay=0.0, **kwargs):
        """Initialize the test plugin with its artificial delay."""
        super().__init__(**kwargs)
        self._delay = delay
        self.calls = 0

    def url(self, *args, **kwargs):
        """Return a stable URL containing the test host."""
        return "slowfail://{}".format(self.host)

    def send(self, **kwargs):
        """Block for the configured delay, then report failure."""
        self.calls += 1
        time.sleep(self._delay)
        return False

    async def async_notify(self, **kwargs):
        """Block for the configured delay, then report failure."""
        self.calls += 1
        await asyncio.sleep(self._delay)
        return False

    @staticmethod
    def parse_url(url):
        """Parse the synthetic URL without requiring a real host."""
        return NotifyBase.parse_url(url, verify_host=False)


class TestDeadlineExpiresDuringAttempt:
    """Deadline-expired retries should stop without sleeping first."""

    def test_sequential_skips_wait_when_deadline_already_passed(self):
        """Sequential retry skips its wait once the deadline has passed."""
        N_MGR["slowfail"] = _SlowFailNotify

        try:
            asset = AppriseAsset(async_mode=False, service_timeout=0.05)
            service = _SlowFailNotify(
                host="x", asset=asset, retry=1, wait=1.0, delay=0.2
            )
            a = Apprise(asset=asset)
            a.add(service)

            real_sleep = time.sleep
            with mock.patch(
                "apprise.apprise.time.sleep", side_effect=real_sleep
            ) as mock_sleep:
                result = a.notify(body="test")

            # The first attempt failed before the retry deadline check.
            # A confirmed failure takes priority over the later TIMEOUT.
            assert result.status == AppriseResultStatus.FAILURE
            # The retry loop stopped before sleeping or calling send() again.
            assert service.calls == 1
            mock_sleep.assert_called_once_with(pytest.approx(0.2))
        finally:
            N_MGR.unload_modules()

    def test_asyncio_skips_wait_when_deadline_already_passed(self):
        """Async retry skips its wait once the deadline has passed."""
        N_MGR["slowfail"] = _SlowFailNotify

        try:
            asset = AppriseAsset(async_mode=True, service_timeout=0.05)
            service = _SlowFailNotify(
                host="x", asset=asset, retry=1, wait=1.0, delay=0.08
            )
            a = Apprise(asset=asset)
            a.add(service)

            # Keep the delay just above service_timeout so do_call() reaches
            # its retry check before the outer abandon window takes over.
            result = asyncio.run(a.async_notify(body="test"))

            assert result.status == AppriseResultStatus.FAILURE
            assert service.calls == 1
        finally:
            N_MGR.unload_modules()


class TestSharedExecutorRace:
    """_get_shared_executor() must reuse an executor created during locking."""

    def test_inner_check_skips_creation_if_already_set(self):
        """The inner lock check returns the executor another thread created."""
        import apprise.apprise as apprise_module

        sentinel = mock.Mock(name="already-created-executor")

        class _RaceLock:
            """Simulate another thread creating the executor first."""

            def __enter__(self):
                apprise_module._shared_executor = sentinel
                return self

            def __exit__(self, *exc):
                return False

        with (
            mock.patch("apprise.apprise._shared_executor", None),
            mock.patch("apprise.apprise._shared_executor_lock", _RaceLock()),
            mock.patch("apprise.apprise.cf.ThreadPoolExecutor") as mock_pool,
        ):
            result = apprise_module._get_shared_executor()

        assert result is sentinel
        mock_pool.assert_not_called()
