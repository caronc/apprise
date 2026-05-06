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
from unittest import mock

import pytest

from apprise import Apprise, AppriseAsset
from apprise.common import (
    APPRISE_MAX_SERVICE_RETRY,
    APPRISE_MAX_SERVICE_WAIT,
    MATCH_ALL_TAG,
)
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

    def test_wait_zero_not_in_url_parameters(self):
        nb = _TestNotify(host="localhost", wait=0.0, retry=0)
        params = nb.url_parameters()
        assert "wait" not in params
        assert "retry" not in params

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
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)

            server = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.3,
            )
            a.add(server)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert result is True
            # Failed once -> sleep once before retry
            mock_sleep.assert_called_once_with(pytest.approx(0.3))
        finally:
            N_MGR.unload_modules()

    def test_sleep_not_called_when_wait_zero(self):
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)

            server = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.0,
            )
            a.add(server)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert result is True
            mock_sleep.assert_not_called()
        finally:
            N_MGR.unload_modules()

    def test_sleep_not_called_when_no_retry(self):
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)

            # retry=0 means only one attempt; with wait=1.0 sleep should
            # never fire since there are no retries
            server = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=0,
                wait=1.0,
                fail_times=0,  # always succeeds
            )
            a.add(server)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert result is True
            mock_sleep.assert_not_called()
        finally:
            N_MGR.unload_modules()

    def test_sleep_called_multiple_times(self):
        """Fails twice, succeeds on third attempt -> sleep called twice."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            a = Apprise(asset=asset)

            server = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=3,
                wait=0.5,
                fail_times=2,
            )
            a.add(server)

            with mock.patch("apprise.apprise.time.sleep") as mock_sleep:
                result = a.notify(body="test")

            assert result is True
            assert mock_sleep.call_count == 2
            for call in mock_sleep.call_args_list:
                assert call == mock.call(pytest.approx(0.5))
        finally:
            N_MGR.unload_modules()


class TestThreadPoolSleep:
    """time.sleep is called between retries in threadpool dispatch."""

    def test_sleep_called_in_threadpool(self):
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            # async_mode=True -> uses threadpool when > 1 server;
            # but with a single server it falls through to sequential.
            # Use two servers so we actually hit the threadpool path.
            asset = AppriseAsset(async_mode=True)

            # Two separate server objects so a threadpool is used
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

            assert result is True
            # s1 fails once -> sleep once
            mock_sleep.assert_called_once_with(pytest.approx(0.2))
        finally:
            N_MGR.unload_modules()

    def test_sleep_not_called_in_threadpool_when_wait_zero(self):
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

            assert result is True
            mock_sleep.assert_not_called()
        finally:
            N_MGR.unload_modules()


class TestAsyncioSleep:
    """asyncio.sleep is called between retries in async dispatch."""

    def test_asyncio_sleep_called(self):
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()

            server = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.4,
                fail_times=1,
            )

            a = Apprise(asset=asset)
            a.add(server)

            async def run():
                with mock.patch("apprise.apprise.asyncio.sleep") as mock_sleep:
                    mock_sleep.return_value = None
                    result = await a.async_notify(body="test")
                return result, mock_sleep

            result, mock_sleep = asyncio.run(run())

            assert result is True
            mock_sleep.assert_called_once_with(pytest.approx(0.4))
        finally:
            N_MGR.unload_modules()

    def test_asyncio_sleep_not_called_when_wait_zero(self):
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()

            server = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=2,
                wait=0.0,
                fail_times=1,
            )

            a = Apprise(asset=asset)
            a.add(server)

            async def run():
                with mock.patch("apprise.apprise.asyncio.sleep") as mock_sleep:
                    mock_sleep.return_value = None
                    result = await a.async_notify(body="test")
                return result, mock_sleep

            result, mock_sleep = asyncio.run(run())

            assert result is True
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
        return "raise://localhost"

    def send(self, **kwargs):
        raise RuntimeError("plugin exploded")

    async def async_notify(self, **kwargs):
        raise RuntimeError("plugin exploded async")

    @staticmethod
    def parse_url(url):
        return NotifyBase.parse_url(url, verify_host=False)


class TestAppriseTag:
    """Full branch coverage for AppriseTag."""

    def test_parse_returns_same_instance(self):
        """parse() short-circuits when the input is already an AppriseTag."""
        t = AppriseTag("alerts", priority=2)
        # Must return the exact same object, not a copy (tag.py line 93)
        assert AppriseTag.parse(t) is t

    def test_parse_fallback_for_unrecognised_input(self):
        """parse() falls back to a raw-name tag when the regex has no match."""
        # Input starting with '@' does not match _RE_TAG; the fallback branch
        # (tag.py line 107) stores the whole input as the name.
        t = AppriseTag.parse("@invalid")
        assert str(t) == "@invalid"
        assert t.priority == 0
        assert t.retry is None

    # --- __repr__ ---

    def test_repr_plain(self):
        """repr() with default priority and no retry is minimal."""
        assert repr(AppriseTag("simple")) == "AppriseTag('simple')"

    def test_repr_with_priority(self):
        """repr() includes priority= when non-zero (tag.py lines 121-122)."""
        r = repr(AppriseTag("test", priority=3))
        assert "priority=3" in r

    def test_repr_with_retry(self):
        """repr() includes retry= when set (tag.py lines 123-125)."""
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
        regardless of priority or retry (tag.py line 148)."""
        assert AppriseTag("abc") == AppriseTag("abc", priority=5)
        assert AppriseTag("ABC") == AppriseTag("abc")

    def test_eq_with_string(self):
        """An AppriseTag equals a plain str by name (tag.py line 150)."""
        assert AppriseTag("hello") == "hello"
        assert AppriseTag("HELLO") == "hello"

    def test_eq_not_equal_different_name(self):
        assert AppriseTag("abc") != AppriseTag("xyz")
        assert AppriseTag("abc") != "xyz"

    def test_eq_returns_notimplemented_for_other_types(self):
        """Comparing to a non-str/AppriseTag returns NotImplemented
        (tag.py line 151)."""
        result = AppriseTag("abc").__eq__(42)
        assert result is NotImplemented

    # --- __lt__ ---

    def test_lt_two_apprisetags(self):
        """__lt__ sorts by tag name (tag.py lines 159-160)."""
        assert AppriseTag("abc") < AppriseTag("def")
        assert not (AppriseTag("def") < AppriseTag("abc"))

    def test_lt_with_string(self):
        """AppriseTag can be less-than compared to a plain string
        (tag.py lines 161-162)."""
        assert AppriseTag("abc") < "def"
        assert not (AppriseTag("zzz") < "aaa")

    def test_lt_returns_notimplemented_for_other_types(self):
        """__lt__ with non-str/AppriseTag returns NotImplemented
        (tag.py line 163)."""
        result = AppriseTag("abc").__lt__(42)
        assert result is NotImplemented

    # --- __bool__ ---

    def test_bool_empty_tag_is_false(self):
        """An AppriseTag with an empty name is falsy (tag.py line 167)."""
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
        """Retry suffix found inside a nested list entry (apprise.py:413)."""
        # tag = [["alerts:3"]] -- outer list, inner list as AND group
        result = Apprise._extract_filter_retry([["alerts:3"]])
        assert result == 3

    def test_extract_retry_from_list_of_strings(self):
        """Retry suffix found in a plain-string list entry (apprise.py:417)."""
        result = Apprise._extract_filter_retry(["alerts:3"])
        assert result == 3

    def test_extract_retry_none_when_absent(self):
        """Returns None when no retry suffix is present."""
        assert Apprise._extract_filter_retry("alerts") is None
        assert Apprise._extract_filter_retry(["alerts"]) is None

    def test_extract_retry_none_for_match_all(self):
        assert Apprise._extract_filter_retry(MATCH_ALL_TAG) is None
        assert Apprise._extract_filter_retry(None) is None

    def test_has_priority_nested_list(self):
        """Priority prefix found inside a nested list (apprise.py:438)."""
        assert Apprise._filter_has_explicit_priority([["2:alerts"]])

    def test_has_priority_list_of_strings(self):
        """Priority prefix found in a plain-string list (apprise.py:441)."""
        assert Apprise._filter_has_explicit_priority(["2:alerts"])

    def test_has_priority_false_no_prefix(self):
        assert not Apprise._filter_has_explicit_priority("alerts")
        assert not Apprise._filter_has_explicit_priority(["alerts"])

    def test_has_priority_false_for_match_all(self):
        assert not Apprise._filter_has_explicit_priority(MATCH_ALL_TAG)
        assert not Apprise._filter_has_explicit_priority(None)

    # _notify_parallel_threadpool / _notify_parallel_asyncio zero-length -----

    def test_threadpool_zero_servers_returns_true(self):
        """Empty server list returns True immediately (apprise.py:940)."""
        assert Apprise._notify_parallel_threadpool() is True

    def test_asyncio_zero_servers_returns_true(self):
        """Empty server list returns True immediately (apprise.py:1031)."""
        result = asyncio.run(Apprise._notify_parallel_asyncio())
        assert result is True


class TestDispatchIntegration:
    """End-to-end notify() tests covering the new priority/retry dispatch."""

    def _make_server(self, host, priority, asset, fail_times=0):
        """Create a _FailThenSucceedNotify with an AppriseTag in its tags."""
        s = _FailThenSucceedNotify(
            host=host, asset=asset, fail_times=fail_times
        )
        # Assign a fresh instance-level set rather than mutating the
        # class-level tags set.  URLBase.tags is a class attribute (set());
        # .add() would mutate it and share state across all instances.
        # Assignment shadows the class attribute and gives each server its
        # own set with the correct priority stored in the AppriseTag object.
        s.tags = {AppriseTag("alerts", priority=priority, has_priority=True)}
        return s

    def test_filter_retry_override_via_tag_suffix(self):
        """tag suffix ':N' overrides per-server retry for this call only.
        Covers apprise.py line 551 (filter_retry injection)."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            # Server's own retry=0; tag suffix of 2 should allow 3 attempts
            server = _FailThenSucceedNotify(
                host="localhost",
                asset=asset,
                retry=0,
                wait=0.0,
                fail_times=2,
            )
            # Tag the server so the filter "failpass:2" (tag name "failpass",
            # retry override 2) can match it via is_exclusive_match.
            server.tags = {"failpass"}
            a = Apprise(asset=asset)
            a.add(server)

            # "failpass:2" -> retry override of 2 (3 total attempts)
            result = a.notify(body="test", tag="failpass:2")
            assert result is True
            assert server._calls == 3
        finally:
            N_MGR.unload_modules()

    def test_exclusive_priority_dispatch_skips_other_priorities(self):
        """Explicit priority prefix dispatches only matching-priority services.
        Covers apprise.py lines 556-572."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s1 = self._make_server("host1", priority=1, asset=asset)
            s2 = self._make_server("host2", priority=2, asset=asset)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            # "2:alerts" -> only priority-2 service fires
            result = a.notify(body="test", tag="2:alerts")
            assert result is True
            assert s1._calls == 0  # priority-1, not contacted
            assert s2._calls == 1  # priority-2, contacted once
        finally:
            N_MGR.unload_modules()

    def test_escalation_stops_when_highest_priority_group_succeeds(self):
        """If priority-1 group all succeed, priority-2 group is not run."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s1 = self._make_server("host1", priority=1, asset=asset)
            s2 = self._make_server("host2", priority=2, asset=asset)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test", tag="alerts")
            assert result is True
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
            s1 = self._make_server(
                "host1", priority=1, asset=asset, fail_times=999
            )
            # priority-2 always succeeds
            s2 = self._make_server("host2", priority=2, asset=asset)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test", tag="alerts")
            assert result is True
            assert s1._calls == 1
            assert s2._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_async_notify_filter_retry_and_explicit_priority(self):
        """async_notify() covers the same escalation/exclusive paths.
        Covers apprise.py lines 630, 637-649."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()
            s1 = self._make_server("host1", priority=1, asset=asset)
            s2 = self._make_server("host2", priority=2, asset=asset)

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            async def run_exclusive():
                return await a.async_notify(body="test", tag="2:alerts")

            async def run_escalation():
                return await a.async_notify(body="test", tag="alerts")

            # exclusive: only priority-2 fires
            r = asyncio.run(run_exclusive())
            assert r is True
            assert s1._calls == 0
            assert s2._calls == 1

            # escalation: priority-1 succeeds, priority-2 skipped
            s1._calls = 0
            s2._calls = 0
            r = asyncio.run(run_escalation())
            assert r is True
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

            # Exclusive "0:family": plain "family" and "0:family" servers are
            # both priority 0 and must both fire; priority-1 server is skipped.
            result = a.notify(body="test", tag="0:family")
            assert result is True
            assert s1._calls == 1  # plain "family" matched by "0:family"
            assert s2._calls == 1  # explicit "0:family" matched
            assert s3._calls == 0  # priority 1, not priority 0 -- skipped

            # Escalation "family": s1 and s2 are both in the priority-0
            # group.  Both succeed, so s3 (priority 1) is never escalated to.
            s1._calls = s2._calls = s3._calls = 0
            result = a.notify(body="test", tag="family")
            assert result is True
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
            server = _RaisingNotify(host="localhost", asset=asset, retry=0)
            a = Apprise(asset=asset)
            a.add(server)

            result = a.notify(body="test")
            assert result is False
        finally:
            N_MGR.unload_modules()

    def test_sequential_exception_retried(self):
        """Exception on first attempt is retried; later success counts."""
        N_MGR["failpass"] = _FailThenSucceedNotify
        N_MGR["raise"] = _RaisingNotify

        try:
            asset = AppriseAsset(async_mode=False)
            # Use a plugin that raises on the first attempt then succeeds
            server = _FailThenSucceedNotify(
                host="localhost", asset=asset, retry=1, wait=0.0, fail_times=1
            )
            # Patch notify to raise on the first call then succeed
            call_count = [0]

            def raising_then_ok(**kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise RuntimeError("transient error")
                return True

            server.send = raising_then_ok
            a = Apprise(asset=asset)
            a.add(server)

            result = a.notify(body="test")
            assert result is True
            assert call_count[0] == 2
        finally:
            N_MGR.unload_modules()

    def test_threadpool_future_exception_caught(self):
        """An exception escaping a thread future is caught gracefully.
        Covers apprise.py lines 1004-1006."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)
            # Need 2 servers to trigger the thread pool path
            s1 = _FailThenSucceedNotify(
                host="host1", asset=asset, fail_times=0
            )
            s2 = _FailThenSucceedNotify(
                host="host2", asset=asset, fail_times=0
            )
            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            # Patch as_completed so one future raises when .result() is called
            import concurrent.futures as cf

            real_as_completed = cf.as_completed

            def patched_as_completed(futures, **kw):
                for i, f in enumerate(real_as_completed(futures, **kw)):
                    if i == 0:
                        # Wrap first future to raise on .result()
                        m = mock.Mock()
                        m.result.side_effect = RuntimeError("future boom")
                        yield m
                    else:
                        yield f

            with mock.patch(
                "apprise.apprise.cf.as_completed", patched_as_completed
            ):
                result = a.notify(body="test")

            # One future raised -> overall result is False
            assert result is False
        finally:
            N_MGR.unload_modules()

    def test_asyncio_exception_in_do_call_treated_as_failure(self):
        """An exception inside do_call's retry loop is caught and the
        service is marked as failed (covers the new try/except in do_call)."""
        N_MGR["raise"] = _RaisingNotify

        try:
            asset = AppriseAsset()
            server = _RaisingNotify(host="localhost", asset=asset, retry=0)
            a = Apprise(asset=asset)
            a.add(server)

            async def run():
                return await a.async_notify(body="test")

            result = asyncio.run(run())
            assert result is False
        finally:
            N_MGR.unload_modules()

    def test_asyncio_gather_unhandled_exception(self):
        """An exception escaping gather() is caught as a safety net.
        Covers apprise.py lines 1090-1091."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()
            server = _FailThenSucceedNotify(
                host="localhost", asset=asset, fail_times=0
            )
            a = Apprise(asset=asset)
            a.add(server)

            # Mock asyncio.gather to return an unexpected exception object
            async def fake_gather(*args, **kw):
                return [RuntimeError("escaped")]

            async def run():
                with mock.patch("apprise.apprise.asyncio.gather", fake_gather):
                    return await a.async_notify(body="test")

            result = asyncio.run(run())
            assert result is False
        finally:
            N_MGR.unload_modules()

    def test_asyncio_gather_type_error(self):
        """A TypeError in gather results is caught and returns False.
        Covers apprise.py lines 1093-1095."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()
            server = _FailThenSucceedNotify(
                host="localhost", asset=asset, fail_times=0
            )
            a = Apprise(asset=asset)
            a.add(server)

            async def fake_gather(*args, **kw):
                return [TypeError("validation")]

            async def run():
                with mock.patch("apprise.apprise.asyncio.gather", fake_gather):
                    return await a.async_notify(body="test")

            result = asyncio.run(run())
            assert result is False
        finally:
            N_MGR.unload_modules()
