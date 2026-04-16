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
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise, NotifyType
from apprise.plugins.exotel import NotifyExotel

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "exotel://",
        {
            # No Account SID specified
            "instance": TypeError,
        },
    ),
    (
        "exotel://:@/",
        {
            # invalid Auth token
            "instance": TypeError,
        },
    ),
    (
        "exotel://{}@12345678".format("a" * 32),
        {
            # Just sid provided
            "instance": TypeError,
        },
    ),
    (
        "exotel://{}:{}@_".format("a" * 32, "b" * 32),
        {
            # sid and token provided but invalid from
            "instance": TypeError,
        },
    ),
    (
        "exotel://{}:{}@/%20".format("a" * 32, "b" * 32),
        {
            # sid and token provided but no from
            "instance": TypeError,
        },
    ),
    (
        "exotel://{}:{}@{}".format("a" * 32, "b" * 32, "3" * 8),
        {
            # sid and token provided and from but invalid from no
            "instance": TypeError,
        },
    ),
    (
        "exotel://{}:{}@{}".format("a" * 32, "b" * 32, "3" * 9),
        {
            # sid and token provided and from
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://{}:{}@EXOTEL/{}".format("a" * 32, "b" * 32, "3" * 9),
        {
            # sid and token provided with a sender ID source
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://{}:{}@600123/{}".format("a" * 32, "b" * 32, "3" * 9),
        {
            # sid and token provided with a numeric sender ID source
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://{}:{}@{}/123/{}/abcd/".format(
            "a" * 32, "b" * 32, "3" * 11, "9" * 15
        ),
        {
            # valid everything but target numbers
            "instance": NotifyExotel,
            # Since the targets are invalid, we'll fail to send()
            "notify_response": False,
        },
    ),
    (
        "exotel://{}:{}@12345/{}".format("a" * 32, "b" * 32, "4" * 11),
        {
            # using short-code (5 characters) is not supported
            "instance": TypeError,
        },
    ),
    (
        "exotel://{}:{}@{}".format("a" * 32, "b" * 32, "5" * 11),
        {
            # using phone no with no target - we text ourselves in
            # this case
            "instance": NotifyExotel,
            # Our expected url(privacy=True) startswith() response:
            "privacy_url": "exotel://****:b...b@55555555555/",
        },
    ),
    (
        "exotel://{}:{}@{}?batch=yes".format("a" * 32, "b" * 32, "5" * 11),
        {
            # Test batch flag
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://{}:{}@{}?batch=no".format("a" * 32, "b" * 32, "5" * 11),
        {
            # Test batch flag
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # use get args to accomplish the same thing
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&unicode=Yes".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # Test unicode flag
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&unicode=no".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # Test unicode flag
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&region=us".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # Test region flag (Us)
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&region=in".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # Test region flag (India)
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&region=invalid".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # Test region flag Invalid
            "instance": TypeError,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&priority=normal".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # Test region flag (Us)
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&priority=high".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # Test region flag (India)
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&priority=invalid".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # Test region flag Invalid
            "instance": TypeError,
        },
    ),
    (
        "exotel://_?sid={}&token={}&source={}".format(
            "a" * 32, "b" * 32, "5" * 11
        ),
        {
            # use get args to accomplish the same thing (use source
            # instead of from)
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://_?sid={}&token={}&from={}&to={}".format(
            "a" * 32, "b" * 32, "5" * 11, "7" * 13
        ),
        {
            # use to=
            "instance": NotifyExotel,
        },
    ),
    (
        "exotel://{}:{}@{}".format("a" * 32, "b" * 32, "6" * 11),
        {
            "instance": NotifyExotel,
            # throw a bizarre code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "exotel://{}:{}@{}".format("a" * 32, "b" * 32, "6" * 11),
        {
            "instance": NotifyExotel,
            # Throws a series of connection and transfer exceptions when
            # this flag is set and tests that we gracefully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_exotel_urls():
    """NotifyExotel() Apprise URLs."""

    assert NotifyExotel.setup_url == "https://appriseit.com/services/exotel/"

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


@mock.patch("requests.post")
def test_plugin_exotel_edge_cases(mock_post):
    """NotifyExotel() Edge Cases."""

    sid = "a" * 32
    apikey = "api-key"
    token = "b" * 32
    source = "LM-EXOTEL"
    targets = ("6" * 11, "7" * 11)

    response = requests.Request()
    response.status_code = requests.codes.ok

    mock_post.return_value = response

    with pytest.raises(TypeError):
        NotifyExotel(sid=sid, token=token, source=" ")

    with pytest.raises(TypeError):
        NotifyExotel(sid=sid, token=token, source=source, apikey=" ")

    with pytest.raises(TypeError):
        NotifyExotel(sid=sid, token=token, source=source, region_name=" ")

    with pytest.raises(TypeError):
        NotifyExotel(sid=sid, token=token, source=source, priority=" ")

    # Programmatic priority shorthand is supported as an Apprise convenience.
    obj = NotifyExotel(sid=sid, token=token, source="5" * 11, priority="+")
    assert obj.priority == "high"
    assert obj.targets == ["5" * 11]

    mock_post.reset_mock()
    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
    assert mock_post.call_count == 1
    payload = mock_post.call_args_list[0][1]["data"]
    assert payload["From"] == "5" * 11
    assert payload["To"] == "5" * 11
    assert payload["Priority"] == "high"

    # When a Sender ID is provided without targets, pass it upstream as the
    # implicit recipient and let Exotel decide whether it is deliverable.
    obj = NotifyExotel(sid=sid, token=token, source=source)
    assert obj.targets == [source]
    assert len(obj) == 1

    mock_post.reset_mock()
    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
    assert mock_post.call_count == 1
    payload = mock_post.call_args_list[0][1]["data"]
    assert payload["From"] == source
    assert payload["To"] == source

    obj = Apprise.instantiate(
        "exotel://{}:{}@{}/{}?apikey={}&region=in&unicode=no"
        "&priority=high".format(sid, token, source, "/".join(targets), apikey)
    )

    assert isinstance(obj, NotifyExotel)
    assert len(obj) == len(targets)
    assert set(obj.targets) == set(targets)

    mock_post.reset_mock()
    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO)

    assert mock_post.call_count == len(targets)

    first_call = mock_post.call_args_list[0]
    assert first_call[0][0] == (
        "https://api.in.exotel.com/v1/Accounts/{}/Sms/send".format(sid)
    )
    assert first_call[1]["auth"] == (apikey, token)

    first_payload = first_call[1]["data"]
    assert first_payload["From"] == source
    assert first_payload["To"] == obj.targets[0]
    assert first_payload["Body"] == "title\r\nbody"
    assert first_payload["EncodingType"] == "plain"
    assert first_payload["Priority"] == "high"
    assert "StatusCallback" not in first_payload

    second_call = mock_post.call_args_list[1]
    assert second_call[0][0] == (
        "https://api.in.exotel.com/v1/Accounts/{}/Sms/send".format(sid)
    )
    assert second_call[1]["auth"] == (apikey, token)

    second_payload = second_call[1]["data"]
    assert second_payload["From"] == source
    assert second_payload["To"] == obj.targets[1]
    assert second_payload["Body"] == "title\r\nbody"
    assert second_payload["EncodingType"] == "plain"
    assert second_payload["Priority"] == "high"
    assert "StatusCallback" not in second_payload

    obj = Apprise.instantiate(
        "exotel://{}:{}@{}/{}?apikey={}&region=in&unicode=no"
        "&priority=high&batch=yes".format(
            sid, token, source, "/".join(targets), apikey
        )
    )
    assert isinstance(obj, NotifyExotel)
    assert len(obj) == 1
    assert set(obj.targets) == set(targets)

    mock_post.reset_mock()
    assert obj.notify(body="body", title="title", notify_type=NotifyType.INFO)
    assert mock_post.call_count == 1

    first_call = mock_post.call_args_list[0]
    assert first_call[0][0] == (
        "https://api.in.exotel.com/v1/Accounts/{}/Sms/send".format(sid)
    )
    assert first_call[1]["auth"] == (apikey, token)

    payload = first_call[1]["data"]
    assert payload["From"] == source
    assert payload["To"] == obj.targets
    assert payload["Body"] == "title\r\nbody"
    assert payload["EncodingType"] == "plain"
    assert payload["Priority"] == "high"
    assert "StatusCallback" not in payload
    assert "batch=yes" in obj.url()

    batch_targets = tuple("6{:010d}".format(i) for i in range(101))
    batch_obj = NotifyExotel(
        sid=sid,
        token=token,
        source=source,
        targets=batch_targets,
        batch=True,
    )
    assert len(batch_obj) == 2

    mock_post.reset_mock()
    assert batch_obj.notify(
        body="body", title="title", notify_type=NotifyType.INFO
    )
    assert mock_post.call_count == 2

    first_payload = mock_post.call_args_list[0][1]["data"]
    assert first_payload["To"] == list(batch_targets[:100])

    second_payload = mock_post.call_args_list[1][1]["data"]
    assert second_payload["To"] == list(batch_targets[100:])

    # Targets must not be part of the URL identifier.
    obj_cmp = Apprise.instantiate(
        "exotel://{}:{}@{}/{}?region=in".format(sid, token, source, "8" * 11)
    )
    assert obj.url_id() != obj_cmp.url_id()

    obj_cmp = Apprise.instantiate(
        "exotel://{}:{}@{}/{}?apikey={}&region=in".format(
            sid, token, source, "8" * 11, apikey
        )
    )
    assert obj.url_id() == obj_cmp.url_id()

    obj_cmp = Apprise.instantiate(
        "exotel://{}:{}@{}/{}?key={}&region=in".format(
            sid, token, source, "8" * 11, apikey
        )
    )
    assert obj.url_id() == obj_cmp.url_id()

    # Region changes the upstream API host and should alter the identifier.
    obj_cmp = Apprise.instantiate(
        "exotel://{}:{}@{}/{}?apikey={}&region=us".format(
            sid, token, source, "8" * 11, apikey
        )
    )
    assert obj.url_id() != obj_cmp.url_id()

    # Even if all provided targets are invalid, Apprise treats the notifier
    # as one logical request target for length purposes.
    obj = Apprise.instantiate(f"exotel://{sid}:{token}@{source}/abcd")
    assert isinstance(obj, NotifyExotel)
    assert len(obj) == 1
