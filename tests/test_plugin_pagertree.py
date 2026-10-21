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
import json
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.exception import AppriseImproperlyConfigured
from apprise.plugins.pagertree import NotifyPagerTree, PagerTreeAction

logging.disable(logging.CRITICAL)

# a test UUID we can use
INTEGRATION_ID = "int_xxxxxxxxxxx"

# Our Testing URLs
apprise_url_tests = (
    (
        "pagertree://",
        {
            # Missing Integration ID
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Invalid Integration ID
    (
        "pagertree://%s" % ("+" * 24),
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    # Minimum requirements met
    (
        f"pagertree://{INTEGRATION_ID}",
        {
            "instance": NotifyPagerTree,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pagertree://i...x?",
        },
    ),
    # change the integration id
    (
        f"pagertree://{INTEGRATION_ID}?integration=int_yyyyyyyyyy",
        {
            "instance": NotifyPagerTree,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pagertree://i...y?",
        },
    ),
    # entries specified on the URL will over-ride the host (integration id)
    (
        f"pagertree://{INTEGRATION_ID}?id=int_zzzzzzzzzz",
        {
            "instance": NotifyPagerTree,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "pagertree://i...z?",
        },
    ),
    # Integration ID + bad url
    (
        "pagertree://:@/",
        {
            "instance": AppriseImproperlyConfigured,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}",
        {
            "instance": NotifyPagerTree,
            # force a failure
            "response": False,
            "requests_response_code": requests.codes.internal_server_error,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}",
        {
            "instance": NotifyPagerTree,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}",
        {
            "instance": NotifyPagerTree,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}?urgency=low",
        {
            # urgency override
            "instance": NotifyPagerTree,
        },
    ),
    (
        f"pagertree://?id={INTEGRATION_ID}&urgency=low",
        {
            # urgency override and id= (for integration)
            "instance": NotifyPagerTree,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}?tags=production,web",
        {
            # tags
            "instance": NotifyPagerTree,
        },
    ),
    (
        f"pagertree://{INTEGRATION_ID}?action=resolve&thirdparty=123",
        {
            # test resolve
            "instance": NotifyPagerTree,
        },
    ),
    # Custom values
    (
        f"pagertree://{INTEGRATION_ID}?+pagertree-token=123&:env=prod&-m=v",
        {
            # minimum requirements and support custom key/value pairs
            "instance": NotifyPagerTree,
        },
    ),
)


def test_plugin_pagertree_urls():
    """NotifyPagerTree() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_pagertree_general(mock_post):
    """NotifyPagerTree() General Checks."""

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Invalid thirdparty id
    with pytest.raises(AppriseImproperlyConfigured):
        NotifyPagerTree(integration=INTEGRATION_ID, thirdparty="   ")


@mock.patch("requests.post")
def test_plugin_pagertree_action_map(mock_post):
    """NotifyPagerTree() creates or resolves alerts by action."""
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_post.return_value = response

    def sent():
        return json.loads(mock_post.call_args[1]["data"])

    # The default creates a new alert with a new ID every time
    obj = Apprise.instantiate(f"pagertree://{INTEGRATION_ID}")
    assert obj.action == PagerTreeAction.CREATE
    assert obj.notify(
        title="Disk full", body="db01", notify_type=NotifyType.SUCCESS
    )
    first = sent()
    assert first["event_type"] == "create"
    assert obj.notify(title="Disk full", body="db01")
    assert sent()["id"] != first["id"]

    # Map creates on failure and resolves on success
    obj = Apprise.instantiate(f"pagertree://{INTEGRATION_ID}?action=map")
    assert obj.action == PagerTreeAction.MAP
    for notify_type, event in (
        (NotifyType.INFO, "create"),
        (NotifyType.WARNING, "create"),
        (NotifyType.FAILURE, "create"),
        (NotifyType.SUCCESS, "resolve"),
    ):
        assert obj.notify(
            title="Disk full", body="db01", notify_type=notify_type
        )
        assert sent()["event_type"] == event

    # The same title gives the same ID, so the success resolves the
    # alert the failure created
    assert obj.notify(
        title="Disk full", body="at 95%", notify_type=NotifyType.FAILURE
    )
    created = sent()
    assert created["title"] == "Disk full"
    assert obj.notify(
        title="Disk full", body="normal", notify_type=NotifyType.SUCCESS
    )
    assert sent()["id"] == created["id"]
    assert "title" not in sent()

    # Without a title, the first line of the message is used
    assert obj.notify(body="Disk full\nat 95%")
    assert sent()["id"] == created["id"]
    assert obj.notify(body="one")
    untitled = sent()["id"]
    assert obj.notify(body="two")
    assert sent()["id"] != untitled

    # A resolve without its own ID uses the title as well
    obj = Apprise.instantiate(f"pagertree://{INTEGRATION_ID}?action=resolve")
    assert obj.notify(title="Disk full", body="normal")
    assert sent()["id"] == created["id"]

    # ?dedup= sets the ID, the same as ?tid=
    obj = Apprise.instantiate(
        f"pagertree://{INTEGRATION_ID}?action=map&dedup=disk-full"
    )
    assert obj.thirdparty == "disk-full"
    assert obj.notify(body="db01", notify_type=NotifyType.FAILURE)
    assert sent()["id"] == "disk-full"

    # The action and ID survive a round trip
    result = NotifyPagerTree.parse_url(obj.url())
    obj2 = NotifyPagerTree(**result)
    assert obj2.action == PagerTreeAction.MAP
    assert obj2.thirdparty == "disk-full"


@mock.patch("requests.post")
def test_plugin_pagertree_retry_id(mock_post):
    """NotifyPagerTree() keeps its create ID across retries."""

    bad = mock.Mock()
    bad.status_code = requests.codes.internal_server_error
    bad.content = b""
    good = mock.Mock()
    good.status_code = requests.codes.ok
    good.content = b""
    mock_post.side_effect = [bad, good]

    aobj = Apprise()
    assert aobj.add(f"pagertree://{INTEGRATION_ID}?retry=1&wait=0")
    with mock.patch("apprise.apprise.time.sleep"):
        assert aobj.notify(body="Server down")

    # The retry reused the ID so PagerTree sees one alert
    assert mock_post.call_count == 2
    ids = {json.loads(c[1]["data"])["id"] for c in mock_post.call_args_list}
    assert len(ids) == 1
