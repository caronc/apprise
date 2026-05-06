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
from apprise.common import APPRISE_MAX_SERVICE_RETRY, APPRISE_MAX_SERVICE_WAIT
from apprise.manager_plugins import NotificationManager
from apprise.plugins import NotifyBase

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
