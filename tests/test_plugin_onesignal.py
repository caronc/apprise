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

from json import loads

# Disable logging for a cleaner testing output
import logging
from unittest import mock

from helpers import AppriseURLTester
import pytest
import requests

from apprise import Apprise
from apprise.plugins.one_signal import NotifyOneSignal

logging.disable(logging.CRITICAL)

# Our Testing URLs
apprise_url_tests = (
    (
        "onesignal://",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "onesignal://:@/",
        {
            # We failed to identify any valid authentication
            "instance": TypeError,
        },
    ),
    (
        "onesignal://apikey/",
        {
            # no app id specified
            "instance": TypeError,
        },
    ),
    (
        "onesignal://appid@%20%20/",
        {
            # invalid apikey
            "instance": TypeError,
        },
    ),
    (
        "onesignal://appid@apikey/playerid/?lang=X",
        {
            # invalid language id (must be 2 characters)
            "instance": TypeError,
        },
    ),
    (
        "onesignal://appid@apikey/",
        {
            # No targets specified; we will initialize but not notify anything
            "instance": NotifyOneSignal,
            "notify_response": False,
        },
    ),
    (
        "onesignal://appid@apikey/playerid",
        {
            # Valid playerid
            "instance": NotifyOneSignal,
            "privacy_url": "onesignal://a...d@a...y/playerid",
        },
    ),
    (
        "onesignal://appid@apikey/player",
        {
            # Valid player id
            "instance": NotifyOneSignal,
            # don't include an image by default
            "include_image": False,
        },
    ),
    (
        "onesignal://appid@apikey/@user?image=no",
        {
            # Valid userid, no image
            "instance": NotifyOneSignal,
        },
    ),
    (
        "onesignal://appid@apikey/user@email.com/#seg/player/@user/%20/a",
        {
            # Valid email, valid playerid, valid user, invalid entry (%20),
            # and too short of an entry (a)
            "instance": NotifyOneSignal,
        },
    ),
    (
        "onesignal://appid@apikey?to=#segment,playerid",
        {
            # Test to=
            "instance": NotifyOneSignal,
        },
    ),
    (
        "onesignal://appid@apikey/#segment/@user/?batch=yes",
        {
            # Test batch=
            "instance": NotifyOneSignal,
        },
    ),
    (
        "onesignal://appid@apikey/#segment/@user/?batch=no",
        {
            # Test batch=
            "instance": NotifyOneSignal,
        },
    ),
    (
        "onesignal://templateid:appid@apikey/playerid",
        {
            # Test Template ID
            "instance": NotifyOneSignal,
        },
    ),
    (
        "onesignal://appid@apikey/playerid/?lang=es&subtitle=Sub",
        {
            # Test Language and Subtitle Over-ride
            "instance": NotifyOneSignal,
        },
    ),
    (
        "onesignal://?apikey=abc&template=tp&app=123&to=playerid",
        {
            # Test Kwargs
            "instance": NotifyOneSignal,
        },
    ),
    (
        (
            "onesignal://?apikey=abc&template=tp&app=123&to=playerid&body=no"
            "&:key1=val1&:key2=val2"
        ),
        {
            # Test Kwargs
            "instance": NotifyOneSignal,
        },
    ),
    (
        (
            "onesignal://?apikey=abc&template=tp&app=123&to=playerid&body=no"
            "&+key1=val1&+key2=val2"
        ),
        {
            # Test Kwargs
            "instance": NotifyOneSignal,
        },
    ),
    (
        "onesignal://appid@apikey/#segment/playerid/",
        {
            "instance": NotifyOneSignal,
            # throw a bizzare code forcing us to fail to look it up
            "response": False,
            "requests_response_code": 999,
        },
    ),
    (
        "onesignal://appid@apikey/#segment/playerid/",
        {
            "instance": NotifyOneSignal,
            # Throws a series of i/o exceptions with this flag
            # is set and tests that we gracfully handle them
            "test_requests_exceptions": True,
        },
    ),
)


def test_plugin_onesignal_urls():
    """NotifyOneSignal() Apprise URLs."""

    # Run our general tests
    AppriseURLTester(tests=apprise_url_tests).run_all()


def test_plugin_onesignal_edge_cases():
    """NotifyOneSignal() Batch Validation."""
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/#segment/@user/playerid/user@email.com"
        "/?batch=yes"
    )
    # Validate that it loaded okay
    assert isinstance(obj, NotifyOneSignal)

    # all 4 types defined; but even in a batch mode, they can not be
    # sent in one submission
    assert len(obj) == 4

    #
    # Users
    #
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/@user1/@user2/@user3/@user4/?batch=yes"
    )
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 1

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/@user1/@user2/@user3/@user4/?batch=no"
    )
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 4

    #
    # Segments
    #
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/#segment1/#seg2/#seg3/#seg4/?batch=yes"
    )
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 1

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/#segment1/#seg2/#seg3/#seg4/?batch=no"
    )
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 4

    #
    # Player ID's
    #
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/pid1/pid2/pid3/pid4/?batch=yes"
    )
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 1

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/pid1/pid2/pid3/pid4/?batch=no"
    )
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 4

    #
    # Emails
    #
    emails = ("abc@yahoo.ca", "def@yahoo.ca", "ghi@yahoo.ca", "jkl@yahoo.ca")
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/{}/?batch=yes".format("/".join(emails))
    )
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 1

    # Same query, but no batch mode set
    obj = Apprise.instantiate(
        "onesignal://appid@apikey/{}/?batch=no".format("/".join(emails))
    )
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 4

    #
    # Mixed
    #
    emails = ("abc@yahoo.ca", "def@yahoo.ca", "ghi@yahoo.ca", "jkl@yahoo.ca")
    users = ("@user1", "@user2", "@user3", "@user4")
    players = ("player1", "player2", "player3", "player4")
    segments = ("#seg1", "#seg2", "#seg3", "#seg4")

    path = "{}/{}/{}/{}".format(
        "/".join(emails),
        "/".join(users),
        "/".join(players),
        "/".join(segments),
    )

    obj = Apprise.instantiate(f"onesignal://appid@apikey/{path}/?batch=yes")
    assert isinstance(obj, NotifyOneSignal)

    # We can lump these together - no problem
    assert len(obj) == 4

    # Same query, but no batch mode set
    obj = Apprise.instantiate(f"onesignal://appid@apikey/{path}/?batch=no")
    assert isinstance(obj, NotifyOneSignal)

    # Individual queries
    assert len(obj) == 16

    # custom must be a dictionary
    with pytest.raises(TypeError):
        NotifyOneSignal(
            app="appid", apikey="key", targets=["@user"], custom="not-a-dict"
        )

    # postback must be a dictionary
    with pytest.raises(TypeError):
        NotifyOneSignal(
            app="appid",
            apikey="key",
            targets=["@user"],
            custom=[],
            postback="not-a-dict",
        )


@mock.patch("requests.post")
def test_plugin_onesignal_notifications(mock_post):
    """OneSignal() Notifications Support."""
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Load URL with Template
    instance = Apprise.instantiate(
        "onesignal://templateid:appid@apikey/@user/?:key1=value1&+key3=value3"
    )

    # Validate that it loaded okay
    assert isinstance(instance, NotifyOneSignal)

    response = instance.notify("hello world")
    assert response is True
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.onesignal.com/notifications"
    )

    details = mock_post.call_args_list[0]
    payload = loads(details[1]["data"])

    assert payload == {
        "app_id": "appid",
        "contents": {"en": "hello world"},
        "content_available": True,
        "template_id": "templateid",
        "custom_data": {"key1": "value1"},
        "data": {"key3": "value3"},
        "large_icon": (
            "https://github.com/caronc/apprise"
            "/raw/master/apprise/assets/themes/default/apprise-info-72x72.png"
        ),
        "small_icon": (
            "https://github.com/caronc/apprise"
            "/raw/master/apprise/assets/themes/default/apprise-info-32x32.png"
        ),
        "include_external_user_ids": ["@user"],
    }

    mock_post.reset_mock()

    # Load URL with Template and disable body
    instance = Apprise.instantiate(
        "onesignal://templateid:appid@apikey/@user/?contents=no"
    )

    # Validate that it loaded okay
    assert isinstance(instance, NotifyOneSignal)

    response = instance.notify("hello world")
    assert response is True
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.onesignal.com/notifications"
    )

    details = mock_post.call_args_list[0]
    payload = loads(details[1]["data"])

    assert payload == {
        "app_id": "appid",
        "content_available": True,
        "template_id": "templateid",
        "large_icon": (
            "https://github.com/caronc/apprise"
            "/raw/master/apprise/assets/themes/default/apprise-info-72x72.png"
        ),
        "small_icon": (
            "https://github.com/caronc/apprise"
            "/raw/master/apprise/assets/themes/default/apprise-info-32x32.png"
        ),
        "include_external_user_ids": ["@user"],
    }

    # Now set a title
    mock_post.reset_mock()

    response = instance.notify("hello world", title="mytitle")

    assert response is True
    assert mock_post.call_count == 1
    assert (
        mock_post.call_args_list[0][0][0]
        == "https://api.onesignal.com/notifications"
    )

    details = mock_post.call_args_list[0]
    payload = loads(details[1]["data"])

    assert payload == {
        "app_id": "appid",
        "headings": {"en": "mytitle"},
        "content_available": True,
        "template_id": "templateid",
        "large_icon": (
            "https://github.com/caronc/apprise"
            "/raw/master/apprise/assets/themes/default/apprise-info-72x72.png"
        ),
        "small_icon": (
            "https://github.com/caronc/apprise"
            "/raw/master/apprise/assets/themes/default/apprise-info-32x32.png"
        ),
        "include_external_user_ids": ["@user"],
    }

    # Test without decoding parameters
    instance = Apprise.instantiate(
        "onesignal://templateid:appid@apikey/@user/"
        "?:par=b64:eyJhIjoxLCJiIjoyfQ==&decode=no"
    )
    assert isinstance(instance, NotifyOneSignal) and instance.custom_data == {
        "par": "b64:eyJhIjoxLCJiIjoyfQ=="
    }

    # Now same with loading parameters
    instance = Apprise.instantiate(
        "onesignal://templateid:appid@apikey/@user/"
        "?:par=b64:eyJhIjoxLCJiIjoyfQ==&decode=yes"
    )
    assert isinstance(instance, NotifyOneSignal) and instance.custom_data == {
        "par": {"a": 1, "b": 2}
    }

    # Test bad data in general
    instance = Apprise.instantiate(
        "onesignal://templateid:appid@apikey/@user/?:par=garbage1&decode=yes"
    )
    assert isinstance(instance, NotifyOneSignal) and instance.custom_data == {
        "par": "garbage1"
    }

    instance = Apprise.instantiate(
        "onesignal://templateid:appid@apikey/@user/"
        "?:par=b64:garbage2&decode=yes"
    )
    assert isinstance(instance, NotifyOneSignal) and instance.custom_data == {
        "par": "b64:garbage2"
    }

    instance = Apprise.instantiate(
        "onesignal://templateid:appid@apikey/@user/"
        "?:par=b64:garbage3==&decode=yes"
    )
    assert isinstance(instance, NotifyOneSignal) and instance.custom_data == {
        "par": "b64:garbage3=="
    }

    # Now same with not-base64 parameters
    instance = Apprise.instantiate(
        "onesignal://templateid:appid@apikey/@user/"
        "?:par=eyJhIjoxLCJiIjoyfQ==&:par2=123&decode=yes"
    )
    assert isinstance(instance, NotifyOneSignal) and instance.custom_data == {
        "par": "eyJhIjoxLCJiIjoyfQ==",
        "par2": "123",
    }

    # Test incorrect base64 parameters. Second one has incorrect padding
    url = (
        "onesignal://templateid:appid@apikey/@user/"
        "?:par=b64:1234=&:par2=b64:eyJhIjoxLCJiIjoyfQ&"
        ":par3=b64:eyJhIjoxLCJiIjoyfQ==&decode=yes"
    )
    instance = Apprise.instantiate(url)
    assert isinstance(instance, NotifyOneSignal) and instance.custom_data == {
        "par": "b64:1234=",
        "par2": "b64:eyJhIjoxLCJiIjoyfQ",
        "par3": {"a": 1, "b": 2},
    }
