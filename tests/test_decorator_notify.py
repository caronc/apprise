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
from os.path import dirname, join
from unittest import mock

import pytest

from apprise import (
    Apprise,
    AppriseAsset,
    AppriseAttachment,
    AppriseConfig,
    NotificationManager,
    NotifyFormat,
    common,
)
from apprise.decorators import notify
from apprise.decorators.base import CustomNotifyPlugin
from apprise.template import NotifyTemplate

logging.disable(logging.CRITICAL)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()

TEST_VAR_DIR = join(dirname(__file__), "var")


def test_notify_simple_decoration():
    """decorators: Test simple @notify"""

    # Verify our schema we're about to declare doesn't already exist
    # in our schema map:
    assert "utiltest" not in N_MGR

    verify_obj = {}

    # Define a function here on the spot
    @notify(on="utiltest", name="Apprise @notify Decorator Testing")
    def my_inline_notify_wrapper(
        body, title, notify_type, attach, *args, **kwargs
    ):

        # Test our body (always present)
        assert isinstance(body, str)

        # Ensure content is of type utf-8
        assert isinstance(body.encode("utf-8"), bytes)

        if attach:
            # attachment is always of type AppriseAttach
            assert isinstance(attach, AppriseAttachment)

        # Populate our object we can use to validate
        verify_obj.update(
            {
                "body": body,
                "title": title,
                "notify_type": notify_type,
                "attach": attach,
                "args": args,
                "kwargs": kwargs,
            }
        )

    # Now after our hook being inline... it's been loaded
    assert "utiltest" in N_MGR

    # Create ourselves an apprise object
    aobj = Apprise()

    assert aobj.add("utiltest://") is True

    assert len(verify_obj) == 0

    assert (
        bool(
            aobj.notify(
                "Hello World",
                title="My Title",
                # add some attachments too
                attach=(
                    join(TEST_VAR_DIR, "apprise-test.gif"),
                    join(TEST_VAR_DIR, "apprise-test.png"),
                ),
            )
        )
        is True
    )

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj["body"] == "Hello World"
    assert verify_obj["title"] == "My Title"
    assert verify_obj["notify_type"] == common.NotifyType.INFO
    assert isinstance(verify_obj["attach"], AppriseAttachment)
    assert len(verify_obj["attach"]) == 2

    # Undeclared input resolves to the wrapper default and is treated
    # as passthrough.
    assert "body_format" in verify_obj["kwargs"]
    assert verify_obj["kwargs"]["body_format"] == common.NotifyFormat.TEXT
    assert verify_obj["kwargs"]["body_passthrough"] is True

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(verify_obj["kwargs"], dict)
    assert "meta" in verify_obj["kwargs"]
    assert isinstance(verify_obj["kwargs"]["meta"], dict)
    assert len(verify_obj["kwargs"]["meta"]) == 5
    assert verify_obj["kwargs"]["meta"]["verify"] is True
    assert "tag" in verify_obj["kwargs"]["meta"]

    assert "asset" in verify_obj["kwargs"]["meta"]
    assert isinstance(verify_obj["kwargs"]["meta"]["asset"], AppriseAsset)

    assert verify_obj["kwargs"]["meta"]["schema"] == "utiltest"
    assert verify_obj["kwargs"]["meta"]["url"] == "utiltest://"

    # Reset our verify object (so it can be populated again)
    verify_obj = {}

    # Send unicode
    assert bool(aobj.notify("ツ".encode())) is True
    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj["body"] == "ツ"  # content comes back as str (utf-8)
    assert verify_obj["title"] == ""
    assert verify_obj["notify_type"] == common.NotifyType.INFO
    assert verify_obj["attach"] is None

    # Undeclared input resolves to the wrapper default and is treated
    # as passthrough.
    assert "body_format" in verify_obj["kwargs"]
    assert verify_obj["kwargs"]["body_format"] == common.NotifyFormat.TEXT
    assert verify_obj["kwargs"]["body_passthrough"] is True

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(verify_obj["kwargs"], dict)
    assert "meta" in verify_obj["kwargs"]
    assert isinstance(verify_obj["kwargs"]["meta"], dict)
    assert len(verify_obj["kwargs"]["meta"]) == 5
    assert verify_obj["kwargs"]["meta"]["verify"] is True
    assert "tag" in verify_obj["kwargs"]["meta"]

    assert "asset" in verify_obj["kwargs"]["meta"]
    assert isinstance(verify_obj["kwargs"]["meta"]["asset"], AppriseAsset)

    assert verify_obj["kwargs"]["meta"]["schema"] == "utiltest"
    assert verify_obj["kwargs"]["meta"]["url"] == "utiltest://"

    # Reset our verify object (so it can be populated again)
    verify_obj = {}

    # Send utf-8 string
    assert bool(aobj.notify("ツ")) is True

    assert len(verify_obj) > 0
    assert verify_obj["body"] == "ツ"  # content comes back as str (utf-8)
    assert verify_obj["title"] == ""
    assert verify_obj["notify_type"] == common.NotifyType.INFO
    assert verify_obj["attach"] is None

    # Undeclared input resolves to the wrapper default and is treated
    # as passthrough.
    assert "body_format" in verify_obj["kwargs"]
    assert verify_obj["kwargs"]["body_format"] == common.NotifyFormat.TEXT
    assert verify_obj["kwargs"]["body_passthrough"] is True

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(verify_obj["kwargs"], dict)
    assert "meta" in verify_obj["kwargs"]
    assert isinstance(verify_obj["kwargs"]["meta"], dict)
    assert len(verify_obj["kwargs"]["meta"]) == 5
    assert verify_obj["kwargs"]["meta"]["verify"] is True
    assert "tag" in verify_obj["kwargs"]["meta"]

    assert "asset" in verify_obj["kwargs"]["meta"]
    assert isinstance(verify_obj["kwargs"]["meta"]["asset"], AppriseAsset)

    assert verify_obj["kwargs"]["meta"]["schema"] == "utiltest"
    assert verify_obj["kwargs"]["meta"]["url"] == "utiltest://"

    # Some cases that will fail internal validation:
    # - No Body
    assert bool(aobj.notify("")) is False
    # - Title only
    assert bool(aobj.notify("", title="hello world!")) is False

    # Reset our verify object (so it can be populated again)
    verify_obj = {}

    # No Body but has attachment (valid)
    assert (
        bool(aobj.notify("", attach=(join(TEST_VAR_DIR, "apprise-test.png"),)))
        is True
    )

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj["body"] == ""
    assert verify_obj["title"] == ""
    assert verify_obj["notify_type"] == common.NotifyType.INFO
    assert isinstance(verify_obj["attach"], AppriseAttachment)
    assert len(verify_obj["attach"]) == 1

    # Undeclared input resolves to the wrapper default and is treated
    # as passthrough.
    assert "body_format" in verify_obj["kwargs"]
    assert verify_obj["kwargs"]["body_format"] == common.NotifyFormat.TEXT
    assert verify_obj["kwargs"]["body_passthrough"] is True

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(verify_obj["kwargs"], dict)
    assert "meta" in verify_obj["kwargs"]
    assert isinstance(verify_obj["kwargs"]["meta"], dict)
    assert len(verify_obj["kwargs"]["meta"]) == 5
    assert verify_obj["kwargs"]["meta"]["verify"] is True
    assert "tag" in verify_obj["kwargs"]["meta"]

    assert "asset" in verify_obj["kwargs"]["meta"]
    assert isinstance(verify_obj["kwargs"]["meta"]["asset"], AppriseAsset)

    assert verify_obj["kwargs"]["meta"]["schema"] == "utiltest"
    assert verify_obj["kwargs"]["meta"]["url"] == "utiltest://"

    # Reset our verify object (so it can be populated again)
    verify_obj = {}

    # We'll do another test now
    assert (
        bool(
            aobj.notify(
                "Hello Another World",
                title="My Other Title",
                body_format=common.NotifyFormat.HTML,
                notify_type=common.NotifyType.WARNING,
            )
        )
        is True
    )

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj["body"] == "Hello Another World"
    assert verify_obj["title"] == "My Other Title"
    assert verify_obj["notify_type"] == common.NotifyType.WARNING
    # We have no attachments
    assert verify_obj["attach"] is None

    # Declared HTML resolves directly and is not treated as passthrough.
    assert "body_format" in verify_obj["kwargs"]
    assert verify_obj["kwargs"]["body_format"] == common.NotifyFormat.HTML
    assert verify_obj["kwargs"]["body_passthrough"] is False

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert "meta" in verify_obj["kwargs"]
    assert isinstance(verify_obj["kwargs"], dict)
    assert len(verify_obj["kwargs"]["meta"]) == 5
    assert verify_obj["kwargs"]["meta"]["verify"] is True
    assert "asset" in verify_obj["kwargs"]["meta"]
    assert isinstance(verify_obj["kwargs"]["meta"]["asset"], AppriseAsset)
    assert "tag" in verify_obj["kwargs"]["meta"]
    assert isinstance(verify_obj["kwargs"]["meta"]["tag"], set)
    assert verify_obj["kwargs"]["meta"]["schema"] == "utiltest"
    assert verify_obj["kwargs"]["meta"]["url"] == "utiltest://"

    assert "notexc" not in N_MGR

    # Define a function here on the spot
    @notify(on="notexc", name="Apprise @notify Exception Handling")
    def my_exception_inline_notify_wrapper(
        body, title, notify_type, attach, *args, **kwargs
    ):
        raise ValueError("An exception was thrown!")

    assert "notexc" in N_MGR

    # Create ourselves an apprise object
    aobj = Apprise()

    assert aobj.add("notexc://") is True

    # Isn't handled
    assert bool(aobj.notify("Exceptions will be thrown!")) is False

    # Tidy
    N_MGR.remove("utiltest", "notexc")


def test_notify_decorator_body_format():
    """decorators: Test @notify body_format support."""

    assert "multifmt" not in N_MGR

    received = []

    @notify(
        on="multifmt",
        name="Apprise @notify Multi-Format Testing",
        body_format=(NotifyFormat.HTML, NotifyFormat.MARKDOWN),
    )
    def my_multi_format_wrapper(body, title, notify_type, *args, **kwargs):
        """Record the body and original body_format passed to the wrapper."""
        received.append((body, kwargs.get("body_format")))

    assert "multifmt" in N_MGR
    assert N_MGR["multifmt"].notify_format == (
        NotifyFormat.HTML,
        NotifyFormat.MARKDOWN,
    )

    aobj = Apprise()
    assert aobj.add("multifmt://") is True

    # No override and no matching input body_format resolves to the
    # declared default, HTML at index 0.
    assert bool(aobj.notify(body="hello")) is True
    assert received[-1][1] == NotifyFormat.HTML

    # Markdown input aligns directly to the declared Markdown support.
    assert (
        bool(aobj.notify(body="# hi", body_format=NotifyFormat.MARKDOWN))
        is True
    )
    assert received[-1][0] == "# hi"
    assert received[-1][1] == NotifyFormat.MARKDOWN

    # Tidy
    N_MGR.remove("multifmt")


def test_notify_decorator_default_is_pass_through():
    """decorators: @notify() with no body_format= never converts."""

    assert "passthru" not in N_MGR

    received = []

    @notify(on="passthru")
    def passthru_wrapper(body, title, notify_type, *args, **kwargs):
        received.append((body, kwargs.get("body_format")))

    assert N_MGR["passthru"].notify_format == (
        NotifyFormat.TEXT,
        NotifyFormat.HTML,
        NotifyFormat.MARKDOWN,
    )

    aobj = Apprise()
    assert aobj.add("passthru://") is True

    # Undeclared input passes through, then reports the wrapper default.
    assert bool(aobj.notify(body="<b>hi</b>")) is True
    assert received[-1] == ("<b>hi</b>", NotifyFormat.TEXT)

    # Declared HTML still passes through unchanged.
    assert (
        bool(aobj.notify(body="<b>hi</b>", body_format=NotifyFormat.HTML))
        is True
    )
    assert received[-1] == ("<b>hi</b>", NotifyFormat.HTML)

    # Markdown declared: also unchanged.
    assert (
        bool(aobj.notify(body="*hi*", body_format=NotifyFormat.MARKDOWN))
        is True
    )
    assert received[-1] == ("*hi*", NotifyFormat.MARKDOWN)

    # Tidy
    N_MGR.remove("passthru")


def test_notify_complex_decoration():
    """decorators: Test complex @notify"""

    # Verify our schema we're about to declare doesn't already exist
    # in our schema map:
    assert "utiltest" not in N_MGR

    verify_obj = {}

    # Define a function here on the spot
    @notify(
        on="utiltest://user@myhost:23?key=value&NOT=CaseSensitive",
        name="Apprise @notify Decorator Testing",
    )
    def my_inline_notify_wrapper(
        body, title, notify_type, attach, *args, **kwargs
    ):

        # Populate our object we can use to validate
        verify_obj.update(
            {
                "body": body,
                "title": title,
                "notify_type": notify_type,
                "attach": attach,
                "args": args,
                "kwargs": kwargs,
            }
        )

    # Now after our hook being inline... it's been loaded
    assert "utiltest" in N_MGR

    # Create ourselves an apprise object
    aobj = Apprise()

    assert aobj.add("utiltest://") is True

    assert len(verify_obj) == 0

    assert (
        bool(
            aobj.notify(
                "Hello World",
                title="My Title",
                # add some attachments too
                attach=(
                    join(TEST_VAR_DIR, "apprise-test.gif"),
                    join(TEST_VAR_DIR, "apprise-test.png"),
                ),
            )
        )
        is True
    )

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj["body"] == "Hello World"
    assert verify_obj["title"] == "My Title"
    assert verify_obj["notify_type"] == common.NotifyType.INFO
    assert isinstance(verify_obj["attach"], AppriseAttachment)
    assert len(verify_obj["attach"]) == 2

    # Undeclared input resolves to the wrapper default and is treated
    # as passthrough.
    assert "body_format" in verify_obj["kwargs"]
    assert verify_obj["kwargs"]["body_format"] == common.NotifyFormat.TEXT
    assert verify_obj["kwargs"]["body_passthrough"] is True

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(verify_obj["kwargs"], dict)
    assert "meta" in verify_obj["kwargs"]
    assert isinstance(verify_obj["kwargs"]["meta"], dict)

    assert "asset" in verify_obj["kwargs"]["meta"]
    assert isinstance(verify_obj["kwargs"]["meta"]["asset"], AppriseAsset)

    assert "tag" in verify_obj["kwargs"]["meta"]
    assert isinstance(verify_obj["kwargs"]["meta"]["tag"], set)

    assert len(verify_obj["kwargs"]["meta"]) == 9
    assert verify_obj["kwargs"]["meta"]["verify"] is True
    # We carry all of our default arguments from the @notify's initialization
    assert verify_obj["kwargs"]["meta"]["schema"] == "utiltest"

    # Case sensitivity is lost on key assignment and always made lowercase
    # however value case sensitivity is preseved.
    # this is the assembled URL based on the combined values of the default
    # parameters with values provided in the URL (user's configuration)
    assert verify_obj["kwargs"]["meta"]["url"].startswith(
        "utiltest://user@myhost:23?"
    )

    # We don't know where they get placed, so just search for their match
    assert "key=value" in verify_obj["kwargs"]["meta"]["url"]
    assert "not=CaseSensitive" in verify_obj["kwargs"]["meta"]["url"]

    # Reset our verify object (so it can be populated again)
    verify_obj = {}

    # We'll do another test now
    aobj = Apprise()

    assert aobj.add("utiltest://customhost?key=new&key2=another") is True

    assert len(verify_obj) == 0

    # Send our notification
    assert bool(aobj.notify("Hello World", title="My Title")) is True

    # Our content was populated after the notify() call
    assert len(verify_obj) > 0
    assert verify_obj["body"] == "Hello World"
    assert verify_obj["title"] == "My Title"
    assert verify_obj["notify_type"] == common.NotifyType.INFO
    assert verify_obj["attach"] is None

    # Undeclared input resolves to the wrapper default and is treated
    # as passthrough.
    assert "body_format" in verify_obj["kwargs"]
    assert verify_obj["kwargs"]["body_format"] == common.NotifyFormat.TEXT
    assert verify_obj["kwargs"]["body_passthrough"] is True

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert "meta" in verify_obj["kwargs"]
    assert isinstance(verify_obj["kwargs"], dict)
    assert len(verify_obj["kwargs"]["meta"]) == 9
    assert verify_obj["kwargs"]["meta"]["verify"] is True

    # We carry all of our default arguments from the @notify's initialization
    assert verify_obj["kwargs"]["meta"]["schema"] == "utiltest"
    # Our host get's correctly over-ridden
    assert verify_obj["kwargs"]["meta"]["host"] == "customhost"

    assert verify_obj["kwargs"]["meta"]["user"] == "user"
    assert verify_obj["kwargs"]["meta"]["port"] == 23
    assert isinstance(verify_obj["kwargs"]["meta"]["qsd"], dict)
    assert len(verify_obj["kwargs"]["meta"]["qsd"]) == 3
    # our key is over-ridden
    assert verify_obj["kwargs"]["meta"]["qsd"]["key"] == "new"
    # Our other keys are preserved
    assert verify_obj["kwargs"]["meta"]["qsd"]["not"] == "CaseSensitive"
    # New keys are added
    assert verify_obj["kwargs"]["meta"]["qsd"]["key2"] == "another"

    # Case sensitivity is lost on key assignment and always made lowercase
    # however value case sensitivity is preseved.
    # this is the assembled URL based on the combined values of the default
    # parameters with values provided in the URL (user's configuration)
    assert verify_obj["kwargs"]["meta"]["url"].startswith(
        "utiltest://user@customhost:23?"
    )

    # We don't know where they get placed, so just search for their match
    assert "key=new" in verify_obj["kwargs"]["meta"]["url"]
    assert "not=CaseSensitive" in verify_obj["kwargs"]["meta"]["url"]
    assert "key2=another" in verify_obj["kwargs"]["meta"]["url"]

    # Tidy
    N_MGR.remove("utiltest")


def test_notify_decorator_urls_with_space():
    """decorators: URLs containing spaces"""
    # This is in relation to https://github.com/caronc/apprise/issues/1264

    # Verify our schema we're about to declare doesn't already exist
    # in our schema map:
    assert "post" not in N_MGR

    verify_obj = []

    @notify(on="posts")
    def apprise_custom_api_call_wrapper(
        body, title, notify_type, attach, meta, *args, **kwargs
    ):

        # Track what is added
        verify_obj.append(
            {
                "body": body,
                "title": title,
                "notify_type": notify_type,
                "attach": attach,
                "meta": meta,
                "args": args,
                "kwargs": kwargs,
            }
        )

    assert "posts" in N_MGR

    # Create ourselves an apprise object
    aobj = Apprise()

    # Add our configuration
    aobj.add("posts://example.com/my endpoint?-token=ab cdefg")

    # We loaded 1 item
    assert len(aobj) == 1

    # Nothing stored yet in our object
    assert len(verify_obj) == 0

    # Send utf-8 characters
    assert bool(aobj.notify("ツ".encode(), title="My Title")) is True

    # Service notified
    assert len(verify_obj) == 1

    # Extract our object
    obj = verify_obj.pop()

    assert obj.get("body") == "ツ"
    assert obj.get("title") == "My Title"
    assert obj.get("notify_type") == "info"
    assert obj.get("attach") is None
    assert isinstance(obj.get("args"), tuple)
    assert len(obj.get("args")) == 0
    assert obj.get("kwargs") == {
        "body_format": NotifyFormat.TEXT,
        "body_passthrough": True,
    }
    meta = obj.get("meta")
    assert isinstance(meta, dict)

    assert meta.get("schema") == "posts"
    assert (
        meta.get("url")
        == "posts://example.com/my%20endpoint?-token=ab%20cdefg"
    )
    assert meta.get("qsd") == {"-token": "ab cdefg"}
    assert meta.get("host") == "example.com"
    assert meta.get("fullpath") == "/my%20endpoint"
    assert meta.get("path") == "/"
    assert meta.get("query") == "my%20endpoint"
    assert isinstance(meta.get("tag"), set)
    assert len(meta.get("tag")) == 0
    assert isinstance(meta.get("asset"), AppriseAsset)

    # Tidy
    N_MGR.remove("posts")


def test_notify_multi_instance_decoration(tmpdir):
    """decorators: Test multi-instance @notify"""

    # Verify our schema we're about to declare doesn't already exist
    # in our schema map:
    assert "multi" not in N_MGR

    verify_obj = []

    # Define a function here on the spot
    @notify(on="multi", name="Apprise @notify Decorator Testing")
    def my_inline_notify_wrapper(
        body, title, notify_type, attach, meta, *args, **kwargs
    ):

        assert isinstance(body, str)

        # Track what is added
        verify_obj.append(
            {
                "body": body,
                "title": title,
                "notify_type": notify_type,
                "attach": attach,
                "meta": meta,
                "args": args,
                "kwargs": kwargs,
            }
        )

    # Now after our hook being inline... it's been loaded
    assert "multi" in N_MGR

    # Prepare our config
    t = tmpdir.mkdir("multi-test").join("apprise.yml")
    t.write("""urls:
    - multi://user1:pass@hostname
    - multi://user2:pass2@hostname?verify=no
    """)

    # Create ourselves a config object
    ac = AppriseConfig(paths=str(t))

    # Create ourselves an apprise object
    aobj = Apprise()

    # Add our configuration
    aobj.add(ac)

    # The number of configuration files that exist
    assert len(ac) == 1

    # 2 notification endpoints are loaded
    assert len(ac.services()) == 2

    # Nothing stored yet in our object
    assert len(verify_obj) == 0

    # Send utf-8 characters
    assert bool(aobj.notify("ツ".encode(), title="My Title")) is True

    assert len(verify_obj) == 2

    # Python 3.6 does not nessisarily return list in order
    # So let's be sure it's sorted by the user id field to make the remaining
    # checks on this test easy
    verify_obj = sorted(verify_obj, key=lambda x: x["meta"]["user"])

    # Our content was populated after the notify() call
    obj = verify_obj[0]
    assert obj["body"] == "ツ"
    assert obj["title"] == "My Title"
    assert obj["notify_type"] == common.NotifyType.INFO

    meta = obj["meta"]
    assert isinstance(meta, dict)

    # Undeclared input resolves to the wrapper default and is treated
    # as passthrough.
    assert "body_format" in obj["kwargs"]
    assert obj["kwargs"]["body_format"] == common.NotifyFormat.TEXT
    assert obj["kwargs"]["body_passthrough"] is True

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(obj["kwargs"], dict)

    assert "asset" in meta
    assert isinstance(meta["asset"], AppriseAsset)

    assert "tag" in meta
    assert isinstance(meta["tag"], set)

    assert len(meta) == 8
    # We carry all of our default arguments from the @notify's initialization
    assert meta["schema"] == "multi"
    assert meta["host"] == "hostname"
    assert meta["user"] == "user1"
    assert meta["verify"] is True
    assert "redirect" not in meta  # absent -- URLBase inherits asset default
    assert meta["password"] == "pass"

    # Verify our URL is correct
    assert meta["url"] == "multi://user1:pass@hostname"

    #
    # Now verify our second URL saved correct
    #

    # Our content was populated after the notify() call
    obj = verify_obj[1]
    assert obj["body"] == "ツ"
    assert obj["title"] == "My Title"
    assert obj["notify_type"] == common.NotifyType.INFO

    meta = obj["meta"]
    assert isinstance(meta, dict)

    # Undeclared input resolves to the wrapper default and is treated
    # as passthrough.
    assert "body_format" in obj["kwargs"]
    assert obj["kwargs"]["body_format"] == common.NotifyFormat.TEXT
    assert obj["kwargs"]["body_passthrough"] is True

    # The meta argument allows us to further parse the URL parameters
    # specified
    assert isinstance(obj["kwargs"], dict)

    assert "asset" in meta
    assert isinstance(meta["asset"], AppriseAsset)

    assert "tag" in meta
    assert isinstance(meta["tag"], set)

    assert len(meta) == 9
    # We carry all of our default arguments from the @notify's initialization
    assert meta["schema"] == "multi"
    assert meta["host"] == "hostname"
    assert meta["user"] == "user2"
    assert meta["password"] == "pass2"
    assert meta["verify"] is False
    assert "redirect" not in meta  # absent -- URLBase inherits asset default
    assert meta["qsd"]["verify"] == "no"

    # Verify our URL is correct
    assert meta["url"] == "multi://user2:pass2@hostname?verify=no"

    # Tidy
    N_MGR.remove("multi")


def test_notify_yaml_priority_over_qsd():
    """Keep YAML values ahead of query strings for decorator plugins.

    The raw query dictionary remains available in metadata, and query values
    still take priority over URL-path values when YAML omits the field.
    """
    from apprise.config import ConfigBase

    assert "notifyverify" not in N_MGR

    @notify(on="notifyverify", name="Test YAML priority @notify")
    def _handler(body, title, notify_type, attach, meta, *args, **kwargs):
        pass

    assert "notifyverify" in N_MGR

    # URL has ?verify=no&user=qsduser; YAML sibling says verify: yes
    # and user: yamluser.  YAML must win for both.
    result, _ = ConfigBase.config_parse_yaml("""
urls:
  - notifyverify://urluser:urlpass@hostname?verify=no&user=qsduser:
    verify: yes
    user: yamluser
""")

    assert len(result) == 1
    meta = result[0]._default_args

    # qsd must be preserved intact for downstream meta inspection
    assert isinstance(meta.get("qsd"), dict)
    assert meta["qsd"].get("verify") == "no"
    assert meta["qsd"].get("user") == "qsduser"

    # YAML tokens must win over qsd
    assert meta["verify"] is True
    assert meta["user"] == "yamluser"

    # When no YAML token is present for a field, qsd still wins over
    # the URL-path value (qsd > URL path).
    result2, _ = ConfigBase.config_parse_yaml("""
urls:
  - notifyverify://urluser:urlpass@hostname?verify=no:
""")
    assert len(result2) == 1
    meta2 = result2[0]._default_args
    assert meta2["verify"] is False  # qsd wins over URLBase default
    assert meta2["user"] == "urluser"  # URL-path value (no qsd for user)

    # Tidy
    N_MGR.remove("notifyverify")


def test_custom_notify_plugin_decoration():
    """decorators: CustomNotifyPlugin testing"""

    CustomNotifyPlugin()

    # A URL that cannot be parsed is handed back as-is
    assert CustomNotifyPlugin.parse_url(None) is None

    # A parsed URL picks up the same defaults as any other plugin
    results = CustomNotifyPlugin.parse_url("custom://host?verify=no")
    assert results["verify"] is False
    assert results["secure"] is False


@pytest.fixture
def captured():
    """Register a capturing ``capture://`` handler for the test."""
    calls = []

    @notify(on="capture", name="Capture @notify")
    def _handler(body, title, notify_type, meta, *args, **kwargs):
        # Keep each call so the test can inspect what arrived
        calls.append(
            {"body": body, "title": title, "meta": meta, "kwargs": kwargs}
        )

        # A ?fail=yes URL reports a failed delivery
        return meta.get("qsd", {}).get("fail") != "yes"

    assert "capture" in N_MGR
    yield calls

    # Tidy
    N_MGR.remove("capture")


def _yaml(content, **kwargs):
    """Load YAML into an Apprise object and send one notification."""
    apobj = Apprise()
    config = AppriseConfig()
    assert config.add_config(content, format="yaml")
    assert apobj.add(config)
    return apobj, apobj.notify("body", title="title", **kwargs)


def _plain(meta):
    """Return ``meta`` without the shared asset and tag objects."""
    # The asset and tag set are compared separately
    return {k: v for k, v in meta.items() if k not in ("asset", "tag")}


@pytest.mark.parametrize(
    "url",
    (
        "capture://",
        "capture://host",
        "capture://host?x=1",
        "capture://host?verify=no&format=html",
        "capture://bob@host?x=1",
        "capture://host?user=bob&pass=pw",
        "capture://secret@host?user=bob",
        "capture://u:p@host:8080/a/b?x=1&-y=2&+z=3&:w=4",
    ),
)
def test_notify_load_paths_agree(captured, url):
    """Direct, TEXT and YAML loading all give the same meta."""
    # Load the same URL each of the three ways
    direct = Apprise()
    assert direct.add(url)
    assert direct.notify("body", title="title")

    text = Apprise()
    config = AppriseConfig()
    assert config.add_config(url, format="text")
    assert text.add(config)
    assert text.notify("body", title="title")

    _, result = _yaml("urls:\n  - {}\n".format(url))
    assert result

    # Every path delivered once, with identical details
    assert len(captured) == 3
    expected = _plain(captured[0]["meta"])
    assert _plain(captured[1]["meta"]) == expected
    assert _plain(captured[2]["meta"]) == expected


def test_notify_yaml_query_without_password(captured):
    """A YAML URL with a query and no password loads and sends."""
    apobj, result = _yaml(
        "urls:\n  - capture://host?x=1\n  - capture://other\n"
    )

    # Both entries load, so one URL cannot break the rest of the file
    assert result
    assert len(apobj) == 2
    assert len(captured) == 2

    meta = next(c["meta"] for c in captured if c["meta"]["host"] == "host")
    assert meta["host"] == "host"
    assert meta["qsd"] == {"x": "1"}
    assert meta["verify"] is True
    assert "password" not in meta


def test_notify_query_overrides(captured):
    """Query string verify, user and pass reach meta and the plugin."""
    apobj = Apprise()
    assert apobj.add("capture://host?verify=no&user=bob&pass=pw")

    # The plugin itself honours verify=no like any other plugin
    service = apobj[0]
    assert service.verify_certificate is False

    assert apobj.notify("body")
    meta = captured[0]["meta"]
    assert meta["verify"] is False
    assert meta["user"] == "bob"
    assert meta["password"] == "pw"

    # The raw query string is still available untouched
    assert meta["qsd"] == {"verify": "no", "user": "bob", "pass": "pw"}
    assert meta["url"] == "capture://bob:pw@host?verify=no&user=bob&pass=pw"


def test_notify_yaml_settings(captured):
    """YAML settings under a URL reach meta like any other plugin."""
    _, result = _yaml(
        "urls:\n"
        "  - capture://host?x=1:\n"
        "      user: yamluser\n"
        "      verify: no\n"
        "      custom: value\n"
        "      tag: mytag\n",
        tag="mytag",
    )
    assert result
    meta = captured[0]["meta"]

    # Built-in and custom settings are both delivered
    assert meta["user"] == "yamluser"
    assert meta["verify"] is False
    assert meta["custom"] == "value"
    assert meta["qsd"] == {"x": "1"}
    assert meta["tag"] == {"mytag"}

    # The assembled URL reflects the YAML user
    assert meta["url"] == "capture://yamluser@host?x=1"


def test_notify_yaml_list_and_siblings(captured):
    """List entries and sibling settings each build their own service."""
    apobj, result = _yaml(
        "urls:\n"
        "  - capture://host?x=1:\n"
        "    - custom: one\n"
        "    - custom: two\n"
        "  - capture://other?y=2:\n"
        "    custom: three\n"
    )
    assert result
    assert len(apobj) == 3

    # Each entry carries its own value and the shared query string
    found = sorted(
        (c["meta"]["host"], c["meta"]["custom"], c["meta"]["qsd"].get("x"))
        for c in captured
    )
    assert found == [
        ("host", "one", "1"),
        ("host", "two", "1"),
        ("other", "three", None),
    ]


def test_notify_template_values(captured):
    """Template values fill every part of a decorator URL."""
    apobj, result = _yaml(
        "template:\n"
        "  - host\n"
        "  - v\n"
        "urls:\n"
        "  - capture://${V}@${HOST}/p/${V}?x=${V}&-q=${V}:\n"
        "      custom: ${V}\n",
        template={"host": "example.com", "v": "val"},
    )
    assert result

    # The pending entry became a real service only once values arrived
    assert isinstance(next(iter(apobj)), NotifyTemplate)

    meta = captured[0]["meta"]
    assert meta["host"] == "example.com"
    assert meta["user"] == "val"
    assert meta["fullpath"] == "/p/val"
    assert meta["qsd"] == {"x": "val", "-q": "val"}
    assert meta["custom"] == "val"
    assert meta["url"] == "capture://val@example.com/p/val?x=val&-q=val"


def test_notify_template_kept_verbatim(captured):
    """Template values with URL punctuation arrive unchanged."""
    hostile = "a b&c=d?e/f@g"
    _, result = _yaml(
        "template:\n  - v\nurls:\n  - capture://host?x=${V}:\n"
        "      custom: ${V}\n",
        template={"v": hostile},
    )
    assert result

    # The value stays one opaque string in both places
    meta = captured[0]["meta"]
    assert meta["qsd"] == {"x": hostile}
    assert meta["custom"] == hostile


def test_notify_template_defaults(captured):
    """Defaults apply, and a missing value skips the entry."""
    apobj, _ = _yaml(
        "template:\n"
        "  v: fallback\n"
        "  required:\n"
        "urls:\n"
        "  - capture://host?x=${V}\n"
        "  - capture://other?x=${REQUIRED}\n"
    )

    # Only the entry with a default could be sent
    assert len(captured) == 1
    assert captured[0]["meta"]["host"] == "host"
    assert captured[0]["meta"]["qsd"] == {"x": "fallback"}

    # Supplying the missing value sends both
    del captured[:]
    assert apobj.notify("body", template={"required": "given"})
    assert sorted(c["meta"]["qsd"]["x"] for c in captured) == [
        "fallback",
        "given",
    ]


def test_notify_template_reuse(captured):
    """Each distinct set of values builds its own service."""
    apobj, _ = _yaml("template:\n  - v\nurls:\n  - capture://host?x=${V}\n")
    del captured[:]

    # Two different values are delivered separately
    assert apobj.notify("body", template={"v": "one"})
    assert apobj.notify("body", template={"v": "two"})
    assert [c["meta"]["qsd"]["x"] for c in captured] == ["one", "two"]

    # The same values hand back the same service
    first = next(apobj.find(template={"v": "one"}))
    assert next(apobj.find(template={"v": "one"})) is first
    assert next(apobj.find(template={"v": "two"})) is not first


# Each common URL option, a value for it, and how to read it back
COMMON_OPTIONS = (
    ("verify", "no", lambda p: p.verify_certificate),
    ("redirect", "no", lambda p: p.redirects),
    ("rto", "7", lambda p: p.socket_read_timeout),
    ("cto", "3", lambda p: p.socket_connect_timeout),
    ("format", "html", lambda p: p._format_override),
    ("overflow", "truncate", lambda p: p.overflow_mode),
    ("emojis", "yes", lambda p: p.interpret_emojis),
    ("tz", "America/Toronto", lambda p: str(p.tzinfo)),
    ("store", "no", lambda p: p.persistent_storage),
    ("retry", "2", lambda p: p.retry),
    ("wait", "1.5", lambda p: p.wait),
    ("optional", "yes", lambda p: p.optional),
)


@pytest.mark.parametrize(
    "key, value, read", COMMON_OPTIONS, ids=[o[0] for o in COMMON_OPTIONS]
)
@pytest.mark.parametrize("how", ("add", "text", "yaml"))
def test_notify_common_options(captured, how, key, value, read):
    """Every common URL option is applied the same as on json://."""
    # json:// is the reference for how the option should land
    reference = Apprise()
    assert reference.add("json://localhost/?{}={}".format(key, value))
    expected = read(reference[0])

    # Load the decorator URL the requested way
    url = "capture://host?{}={}".format(key, value)
    apobj = Apprise()
    if how == "add":
        assert apobj.add(url)

    else:
        config = AppriseConfig()
        assert config.add_config(
            url if how == "text" else "urls:\n  - {}\n".format(url),
            format=how,
        )
        assert apobj.add(config)

    # The plugin applies the option exactly like json:// does
    assert read(apobj[0]) == expected

    # The parsed option is also shown to the decorated function
    assert apobj.notify("body")
    assert key in captured[0]["meta"]


def test_notify_format_option(captured):
    """A ?format= choice decides the format the function receives."""
    apobj = Apprise()
    assert apobj.add("capture://host?format=html")
    assert apobj.notify("<b>body</b>", body_format=NotifyFormat.HTML)
    assert captured[0]["kwargs"]["body_format"] == NotifyFormat.HTML

    # Markdown input is converted to the chosen HTML
    del captured[:]
    assert apobj.notify("**body**", body_format=NotifyFormat.MARKDOWN)
    assert captured[0]["kwargs"]["body_format"] == NotifyFormat.HTML
    assert "<strong>body</strong>" in captured[0]["body"]


def test_notify_emojis_option(captured):
    """A ?emojis=yes URL converts emoji shortcodes before delivery."""
    apobj = Apprise()
    assert apobj.add("capture://host?emojis=yes")
    assert apobj.notify(":smile:")
    assert captured[0]["body"] == "\U0001f604"


@pytest.mark.parametrize(
    "url",
    (
        "capture://host?fail=yes&retry=2&wait=1.5",
        "urls:\n  - capture://host?fail=yes:\n      retry: 2\n"
        "      wait: 1.5\n",
    ),
    ids=("url", "yaml"),
)
def test_notify_retry_option(captured, url):
    """A failing function is retried, from a URL or a YAML setting."""
    apobj = Apprise()
    if url.startswith("urls:"):
        config = AppriseConfig()
        assert config.add_config(url, format="yaml")
        assert apobj.add(config)

    else:
        assert apobj.add(url)

    with mock.patch("apprise.apprise.time.sleep") as sleep:
        assert not apobj.notify("body")

    # The first try plus two retries, with the wait between each
    assert len(captured) == 3
    assert sleep.call_count == 2
    sleep.assert_called_with(pytest.approx(1.5))


def test_notify_optional_option(captured):
    """A failure on an optional URL does not fail the notification."""
    apobj = Apprise()
    assert apobj.add("capture://host?fail=yes&optional=yes")
    assert apobj.add("capture://other")
    assert apobj.notify("body")

    # Both functions still ran
    assert len(captured) == 2

    # Without optional the same failure is reported
    apobj = Apprise()
    assert apobj.add("capture://host?fail=yes")
    assert not apobj.notify("body")


def test_notify_unsupported_options(captured):
    """Unknown format and overflow values fall back to the defaults."""
    apobj = Apprise()
    assert apobj.add("capture://host?format=bogus&overflow=bogus")
    plugin = apobj[0]
    assert plugin._format_override is None
    assert plugin.overflow_mode == common.OverflowMode.UPSTREAM

    # The function still runs, and sees the raw values in the query string
    assert apobj.notify("body")
    assert "format" not in captured[0]["meta"]
    assert captured[0]["meta"]["qsd"]["format"] == "bogus"
