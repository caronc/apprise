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
from unittest import mock

import requests

import apprise


@mock.patch("requests.post")
def test_apprise_interpret_escapes(mock_post):
    """
    API: Apprise() interpret-escape tests
    """

    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    # Default Escapes interpretation Mode is set to disable
    asset = apprise.AppriseAsset()
    assert asset.interpret_escapes is False

    # Load our asset
    a = apprise.Apprise(asset=asset)

    # add a test server
    assert a.add("json://localhost") is True

    # Our servers should carry this flag
    assert a[0].asset.interpret_escapes is False

    # Send notification
    assert a.notify("ab\\ncd") is True

    # Test our call count
    assert mock_post.call_count == 1

    # content is not escaped
    assert (
        loads(mock_post.call_args_list[0][1]["data"]).get("message", "")
        == "ab\\ncd"
    )

    # Reset
    mock_post.reset_mock()

    # Send notification and provide override:
    assert a.notify("ab\\ncd", interpret_escapes=True) is True

    # Test our call count
    assert mock_post.call_count == 1

    # content IS escaped
    assert (
        loads(mock_post.call_args_list[0][1]["data"]).get("message", "")
        == "ab\ncd"
    )

    # Reset
    mock_post.reset_mock()

    #
    #  Now we test the reverse setup where we set the AppriseAsset
    #  object to True but force it off through the notify() calls
    #

    # Default Escapes interpretation Mode is set to disable
    asset = apprise.AppriseAsset(interpret_escapes=True)
    assert asset.interpret_escapes is True

    # Load our asset
    a = apprise.Apprise(asset=asset)

    # add a test server
    assert a.add("json://localhost") is True

    # Our servers should carry this flag
    assert a[0].asset.interpret_escapes is True

    # Send notification
    assert a.notify("ab\\ncd") is True

    # Test our call count
    assert mock_post.call_count == 1

    # content IS escaped
    assert (
        loads(mock_post.call_args_list[0][1]["data"]).get("message", "")
        == "ab\ncd"
    )

    # Reset
    mock_post.reset_mock()

    # Send notification and provide override:
    assert a.notify("ab\\ncd", interpret_escapes=False) is True

    # Test our call count
    assert mock_post.call_count == 1

    # content is NOT escaped
    assert (
        loads(mock_post.call_args_list[0][1]["data"]).get("message", "")
        == "ab\\ncd"
    )


@mock.patch("requests.post")
def test_apprise_escaping(mock_post):
    """
    API: Apprise() escaping tests

    """
    a = apprise.Apprise()

    response = mock.Mock()
    response.content = ""
    response.status_code = requests.codes.ok
    mock_post.return_value = response

    # Create ourselves a test object to work with
    a.add("json://localhost")

    # Escape our content
    assert a.notify(
        title="\\r\\ntitle\\r\\n",
        body="\\r\\nbody\\r\\n",
        interpret_escapes=True,
    )

    # Verify our content was escaped correctly
    assert mock_post.call_count == 1
    result = loads(mock_post.call_args_list[0][1]["data"])
    assert result["title"] == "title"
    assert result["message"] == "\r\nbody"

    # Reset our mock object
    mock_post.reset_mock()

    #
    # Support Specially encoded content:
    #

    # Escape our content
    assert a.notify(
        # Google Translated to Arabic: "Let's make the world a better place."
        title="دعونا نجعل العالم مكانا أفضل.\\r\\t\\t\\n\\r\\n",
        # Google Translated to Hungarian: "One line of code at a time.'
        body="Egy sor kódot egyszerre.\\r\\n\\r\\r\\n",
        # Our Escape Flag
        interpret_escapes=True,
    )

    # Verify our content was escaped correctly
    assert mock_post.call_count == 1
    result = loads(mock_post.call_args_list[0][1]["data"])
    assert result["title"] == "دعونا نجعل العالم مكانا أفضل."
    assert result["message"] == "Egy sor kódot egyszerre."

    # Error handling
    #
    # We can't escape the content below
    assert a.notify(title=None, body=4, interpret_escapes=True) is False
    assert a.notify(title=4, body=None, interpret_escapes=True) is False
    assert (
        a.notify(title=object(), body=False, interpret_escapes=True) is False
    )
    assert (
        a.notify(title=False, body=object(), interpret_escapes=True) is False
    )

    # We support bytes
    assert (
        a.notify(
            title=b"byte title", body=b"byte body", interpret_escapes=True
        )
        is True
    )

    # However they're escaped as 'utf-8' by default unless we tell Apprise
    # otherwise
    # Now test hebrew types (outside of default utf-8)
    # כותרת נפלאה translates to 'A wonderful title'
    # זו הודעה translates to 'This is a notification'
    title = "כותרת נפלאה".encode("ISO-8859-8")
    body = "[_[זו הודעה](http://localhost)_".encode("ISO-8859-8")
    assert a.notify(title=title, body=body, interpret_escapes=True) is False

    # However if we let Apprise know in advance the encoding, it will handle
    # it for us
    asset = apprise.AppriseAsset(encoding="ISO-8859-8")
    a = apprise.Apprise(asset=asset)
    # Create ourselves a test object to work with
    a.add("json://localhost")
    assert a.notify(title=title, body=body, interpret_escapes=True) is True

    # We'll restore our configuration back to how it was now
    a = apprise.Apprise()
    a.add("json://localhost")

    # The body is proessed first, so the errors thrown above get tested on
    # the body only.  Now we run similar tests but only make the title
    # bad and always mark the body good
    assert a.notify(title=None, body="valid", interpret_escapes=True) is True
    assert a.notify(title=4, body="valid", interpret_escapes=True) is False
    assert (
        a.notify(title=object(), body="valid", interpret_escapes=True) is False
    )
    assert a.notify(title=False, body="valid", interpret_escapes=True) is True
    # Bytes are supported
    assert (
        a.notify(title=b"byte title", body="valid", interpret_escapes=True)
        is True
    )
