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

    def test_extract_retry_none_from_nested_list_no_suffix(self):
        """Nested list without retry suffix returns None.

        Covers the 'if ft.retry is not None' False branch (line 412) and the
        inner for-loop completing without returning (branch 410->406).
        """
        result = Apprise._extract_filter_retry([["alerts"]])
        assert result is None

    def test_server_priority_for_tag_name_absent(self):
        """Returns 0 when no tag in server.tags matches tag_name (line 456)."""
        server = mock.Mock()
        server.tags = {AppriseTag("alerts", priority=3, has_priority=True)}
        assert Apprise._server_priority_for_tag_name(server, "backup") == 0

    def test_match_service_retry_plain_string_tag_backward_compat(self):
        """Plain string in server.tags matched by a priority-prefixed token.

        Covers the else/str fallback inside _match_service_retry when stag is
        not an AppriseTag instance and the name matches (lines 497-498).
        """
        server = mock.Mock()
        server.tags = {"alerts"}  # plain string, not an AppriseTag
        # "3:alerts:2" carries priority=3 + retry=2; plain "alerts" matches
        result = Apprise._match_service_retry(server, "3:alerts:2")
        assert result == 2

    def test_match_service_retry_plain_string_tag_no_match(self):
        """Plain string in server.tags that does not match returns None.

        Covers the else-branch continuation (line 497->489) inside
        _match_service_retry when the plain-string stag name differs from the
        priority-prefixed filter token.
        """
        server = mock.Mock()
        server.tags = {"other"}  # plain string -- does not match "alerts"
        result = Apprise._match_service_retry(server, "3:alerts:2")
        assert result is None

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
        """An Exception escaping the outer gather() round is caught as a
        safety net and treated as a batch failure."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()
            server = _FailThenSucceedNotify(
                host="localhost", asset=asset, fail_times=0
            )
            a = Apprise(asset=asset)
            a.add(server)

            # Mock asyncio.gather to return an escaped exception object.
            # Close any unawaited coroutines passed to the mock to avoid
            # "coroutine was never awaited" RuntimeWarnings.
            async def fake_gather(*args, **kw):
                for arg in args:
                    if asyncio.iscoroutine(arg):
                        arg.close()
                return [RuntimeError("escaped")]

            async def run():
                with mock.patch("apprise.apprise.asyncio.gather", fake_gather):
                    return await a.async_notify(body="test")

            result = asyncio.run(run())
            assert result is False
        finally:
            N_MGR.unload_modules()

    def test_asyncio_gather_type_error(self):
        """A TypeError in gather results is caught and returns False."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset()
            server = _FailThenSucceedNotify(
                host="localhost", asset=asset, fail_times=0
            )
            a = Apprise(asset=asset)
            a.add(server)

            async def fake_gather(*args, **kw):
                for arg in args:
                    if asyncio.iscoroutine(arg):
                        arg.close()
                return [TypeError("validation")]

            async def run():
                with mock.patch("apprise.apprise.asyncio.gather", fake_gather):
                    return await a.async_notify(body="test")

            result = asyncio.run(run())
            assert result is False
        finally:
            N_MGR.unload_modules()


class TestConfigTagRetry:
    """Config parsers must reject a retry suffix in service tag definitions.

    A tag like 'alerts:3' is only valid at call-time (notify() filter / CLI).
    Putting it in a config file creates ambiguity with the URL ?retry= param
    and the YAML retry: key, so both parsers must warn and skip the entry.
    """

    def test_text_rejects_retry_suffix(self):
        """'alerts:3=json://...' is rejected; no server loaded."""
        servers, _ = ConfigBase.config_parse_text("alerts:3=json://localhost")
        assert servers == []

    def test_text_rejects_priority_and_retry_in_tag(self):
        """'1:alerts:3=json://...' is rejected (priority + retry suffix)."""
        servers, _ = ConfigBase.config_parse_text(
            "1:alerts:3=json://localhost"
        )
        assert servers == []

    def test_text_accepts_priority_tag_without_retry(self):
        """'1:alerts=json://...' loads normally (priority prefix, no retry)."""
        servers, _ = ConfigBase.config_parse_text("1:alerts=json://localhost")
        assert len(servers) == 1

    def test_text_accepts_plain_tag(self):
        """'alerts=json://...' loads normally (no prefix, no retry)."""
        servers, _ = ConfigBase.config_parse_text("alerts=json://localhost")
        assert len(servers) == 1

    def test_yaml_rejects_retry_suffix(self):
        """YAML 'tag: alerts:3' is rejected; no server loaded."""
        servers, _ = ConfigBase.config_parse_yaml(
            "version: 1\nurls:\n  - json://localhost:\n      tag: alerts:3\n"
        )
        assert servers == []

    def test_yaml_rejects_priority_and_retry_in_tag(self):
        """YAML 'tag: 1:alerts:3' is rejected (priority + retry suffix)."""
        servers, _ = ConfigBase.config_parse_yaml(
            "version: 1\nurls:\n  - json://localhost:\n      tag: 1:alerts:3\n"
        )
        assert servers == []

    def test_yaml_accepts_priority_tag_without_retry(self):
        """YAML 'tag: 1:alerts' loads normally (priority prefix, no retry)."""
        servers, _ = ConfigBase.config_parse_yaml(
            "version: 1\nurls:\n  - json://localhost:\n      tag: 1:alerts\n"
        )
        assert len(servers) == 1

    def test_yaml_accepts_plain_tag(self):
        """YAML 'tag: alerts' loads normally (no prefix, no retry)."""
        servers, _ = ConfigBase.config_parse_yaml(
            "version: 1\nurls:\n  - json://localhost:\n      tag: alerts\n"
        )
        assert len(servers) == 1

    def test_text_valid_entry_after_rejected_one_still_loads(self):
        """A valid entry that follows a rejected one is still loaded."""
        servers, _ = ConfigBase.config_parse_text(
            "alerts:3=json://localhost\nalerts=json://localhost\n"
        )
        assert len(servers) == 1

    def test_yaml_valid_entry_after_rejected_one_still_loads(self):
        """A valid entry that follows a rejected one is still loaded."""
        servers, _ = ConfigBase.config_parse_yaml(
            "version: 1\n"
            "urls:\n"
            "  - json://localhost:\n"
            "      tag: alerts:3\n"
            "  - json://localhost:\n"
            "      tag: alerts\n"
        )
        assert len(servers) == 1


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
        """Create a server whose tag is an explicit-priority AppriseTag."""
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
            assert result is True
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
            assert result is True
            assert s_devops._calls == 4
            assert s_mgmt._calls == 3
        finally:
            N_MGR.unload_modules()

    # ------------------------------------------------------------------
    # Independent escalation chains
    # ------------------------------------------------------------------

    def test_independent_chains_devops_success_does_not_skip_management(self):
        """When devops chain succeeds at priority-1, management chain still
        dispatches independently -- its priority-1 failure escalates to its
        priority-2 server."""
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
            assert result is True
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
            assert result is False
            assert s_devops._calls == 1  # its chain succeeded
            assert s_mgmt._calls == 1  # its chain failed
        finally:
            N_MGR.unload_modules()

    # ------------------------------------------------------------------
    # Explicit-priority list with per-service retry (flat dispatch)
    # ------------------------------------------------------------------

    def test_explicit_priority_list_per_service_retry(self):
        """['1:tag:2', '2:tag:0'] flat-dispatches both servers; each gets its
        own retry: the priority-1 server gets retry=2 and the priority-2
        server gets retry=0 (one attempt only)."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # priority-1 server: fails twice; needs retry=2 to succeed
            s1 = _FailThenSucceedNotify(host="h1", asset=asset, fail_times=2)
            s1.tags = {AppriseTag("tag", priority=1, has_priority=True)}

            # priority-2 server: always succeeds; retry=0 means one attempt
            s2 = _FailThenSucceedNotify(host="h2", asset=asset, fail_times=0)
            s2.tags = {AppriseTag("tag", priority=2, has_priority=True)}

            a = Apprise(asset=asset)
            a.add(s1)
            a.add(s2)

            result = a.notify(body="test", tag=["1:tag:2", "2:tag:0"])
            assert result is True
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
            assert result is True
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

            # Server must carry BOTH tags to match
            s_both = _FailThenSucceedNotify(
                host="both", asset=asset, fail_times=0
            )
            s_both.tags = {"devops", "management"}

            # Server with only "devops" -- must NOT match AND filter
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
            assert result is True
            assert s_both._calls == 1  # has both tags -- matched
            assert s_devonly._calls == 0  # missing "management" -- not matched
        finally:
            N_MGR.unload_modules()

    # ------------------------------------------------------------------
    # Edge cases: explicit priority + AND, 3-chain OR, chain exhaustion
    # ------------------------------------------------------------------

    def test_and_filter_explicit_priority_no_match_returns_none(self):
        """AND filter with an explicit priority that no server satisfies
        returns None (no services dispatched at all)."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)

            # Server is tagged 'alerts' at priority 2
            s = _FailThenSucceedNotify(host="s", asset=asset, fail_times=0)
            s.tags = {AppriseTag("alerts", priority=2, has_priority=True)}

            a = Apprise(asset=asset)
            a.add(s)

            # Request 'alerts' at priority 1 AND 'backup' -- server has
            # 'alerts' but at priority 2, not 1; nothing matches.
            result = a.notify(body="test", tag=[["1:alerts", "backup"]])
            assert result is None
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
            assert result is True
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
            assert result is False
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

            # priority-0 server: always fails (no retry configured)
            s_p0 = _FailThenSucceedNotify(
                host="p0", asset=asset, fail_times=99
            )
            s_p0.tags = {AppriseTag("alerts", priority=0, has_priority=False)}

            # priority-1 server: succeeds on first attempt
            s_p1 = _FailThenSucceedNotify(host="p1", asset=asset, fail_times=0)
            s_p1.tags = {AppriseTag("alerts", priority=1, has_priority=True)}

            a = Apprise(asset=asset)
            a.add(s_p0)
            a.add(s_p1)

            result = a.notify(body="test", tag="alerts")
            assert result is True
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

            # priority-0 server: always fails
            s_p0 = _FailThenSucceedNotify(
                host="p0", asset=asset, fail_times=99
            )
            s_p0.tags = {AppriseTag("alerts", priority=0, has_priority=False)}

            # priority-1 server: also always fails
            s_p1 = _FailThenSucceedNotify(
                host="p1", asset=asset, fail_times=99
            )
            s_p1.tags = {AppriseTag("alerts", priority=1, has_priority=True)}

            a = Apprise(asset=asset)
            a.add(s_p0)
            a.add(s_p1)

            result = a.notify(body="test", tag="alerts")
            assert result is False
            # Both groups were attempted
            assert s_p0._calls == 1
            assert s_p1._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_chain_dispatch_future_exception_treated_as_failure(self):
        """An exception escaping _run_batch is caught in the chain-dispatch
        ThreadPoolExecutor loop and treated as a delivery failure.

        Covers the 'except Exception: ok = False' branch (apprise.py:788-792)
        that is only reachable when multiple chains are active simultaneously
        (triggering the ThreadPoolExecutor path) and _run_batch raises.
        Uses _ExplodingAsset (raises on async_mode access) instead of
        patching a @staticmethod, which is unreliable across Python versions
        when the patched method runs inside a ThreadPoolExecutor worker.
        """
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            # _ExplodingAsset.async_mode raises RuntimeError.  _run_batch
            # reads s.asset.async_mode to split seq/par, so a batch with
            # one of these servers raises and the future captures it.
            class _ExplodingAsset(AppriseAsset):
                @property
                def async_mode(self):
                    raise RuntimeError("injected async_mode access")

            # Two servers with distinct tags -> two independent chains so
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
            assert result is False
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
            assert result is False
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
            assert result is False
            # beta failed in round 1 and was exhausted -- abort triggered.
            # alpha's p1 (escalation) should NOT have been attempted.
            assert s_b._calls == 1
            assert s_a_p0._calls == 1
            assert s_a_p1._calls == 0  # skipped due to early abort
        finally:
            N_MGR.unload_modules()

    def test_abort_on_chain_failure_true_async(self):
        """abort_on_chain_failure=True triggers the same early-abort in
        async_notify() (covers apprise.py line 873)."""
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
            assert result is False
            # beta was exhausted in round 1 -- abort fires before alpha's p1
            assert s_b._calls == 1
            assert s_a_p0._calls == 1
            assert s_a_p1._calls == 0
        finally:
            N_MGR.unload_modules()


class TestOptionalService:
    """optional=True silently absorbs per-service delivery failures.

    The overall notify()/async_notify() result is True even when an
    optional service cannot be reached, so callers are not penalised
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
        """Sequential dispatch: failed optional server -> overall True."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=99)
            s.optional = True

            a = Apprise(asset=asset)
            a.add(s)

            result = a.notify(body="test")
            assert result is True
            assert s._calls == 1
        finally:
            N_MGR.unload_modules()

    def test_optional_threadpool_failure_absorbed(self):
        """Thread-pool dispatch: failed optional servers -> overall True.

        Two async_mode=True servers ensure _notify_parallel_threadpool
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
            assert result is True
        finally:
            N_MGR.unload_modules()

    def test_optional_asyncio_failure_absorbed(self):
        """Asyncio dispatch: failed optional server -> overall True."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=True)
            s = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=99)
            s.optional = True

            a = Apprise(asset=asset)
            a.add(s)

            result = asyncio.run(a.async_notify(body="test"))
            assert result is True
        finally:
            N_MGR.unload_modules()

    def test_optional_all_fail_all_optional_returns_true(self):
        """When every server is optional and every server fails -> True."""
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
            assert result is True
        finally:
            N_MGR.unload_modules()

    def test_optional_mixed_required_fails_returns_false(self):
        """Required server failure taints result even with optional peers."""
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
            assert result is False
        finally:
            N_MGR.unload_modules()

    def test_optional_success_unaffected(self):
        """An optional server that succeeds is still counted as True."""
        N_MGR["failpass"] = _FailThenSucceedNotify

        try:
            asset = AppriseAsset(async_mode=False)
            s = _FailThenSucceedNotify(host="s1", asset=asset, fail_times=0)
            s.optional = True

            a = Apprise(asset=asset)
            a.add(s)

            result = a.notify(body="test")
            assert result is True
            assert s._calls == 1
        finally:
            N_MGR.unload_modules()


class TestCreateNotifyCalls:
    """Cover Apprise._create_notify_calls() which splits servers into
    sequential and parallel buckets based on their asset.async_mode flag."""

    def test_splits_sequential_and_parallel(self):
        """Sequential and parallel servers are split into separate lists."""
        N_MGR["failpass"] = _FailThenSucceedNotify
        try:
            # With async_mode=False all loaded servers go to the sequential
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

            # With async_mode=True the same server is placed in the parallel
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
    """Cover the safety-net branch in _notify_parallel_asyncio that handles
    exceptions which escape do_call's own try/except block."""

    def test_exception_outside_try_block_triggers_safety_net(self):
        """An exception raised before the per-attempt try block (e.g. from
        a misbehaving server.retry property) escapes do_call, is captured by
        asyncio.gather(return_exceptions=True), and causes the batch to
        return False via the safety-net handler.

        A second well-behaved server is included so that results contains
        both an Exception and a bool value, exercising both branches of the
        inner ``if isinstance(status, Exception)`` check in the loop."""

        class _RaisingRetryServer:
            """Server whose retry property raises to simulate a broken plugin
            that fails before the per-attempt try/except in do_call."""

            service_name = "raiser"
            asset = AppriseAsset(async_mode=True)
            optional = False

            @property
            def retry(self):
                # This exception is raised when do_call evaluates
                # getattr(server, "retry", 0), which happens OUTSIDE the
                # per-attempt try/except.  It therefore escapes do_call
                # entirely and is captured by asyncio.gather as a value.
                raise RuntimeError("injected: property raised outside try")

            async def async_notify(self, **kwargs):
                return True  # pragma: no cover -- never reached

        class _GoodServer:
            """Minimal well-behaved server that succeeds immediately."""

            service_name = "good"

            async def async_notify(self, **kwargs):
                return True

        raiser = _RaisingRetryServer()
        good = _GoodServer()
        # Two servers: raiser -> Exception in results; good -> True in results.
        # The safety-net loop therefore hits both branches of the inner
        # ``if isinstance(status, Exception)`` check.
        result = asyncio.run(
            Apprise._notify_parallel_asyncio((raiser, {}), (good, {}))
        )
        assert result is False
