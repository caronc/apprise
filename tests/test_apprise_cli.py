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

from importlib import reload
from inspect import cleandoc
import json

# Disable logging for a cleaner testing output
import logging
import os
from os.path import dirname, join
import re
import sys
from typing import ClassVar
from unittest import mock

from click.testing import CliRunner
from helpers import environ
import pytest
import requests

from apprise import NotificationManager, NotifyBase, cli
from apprise.locale import gettext_lazy as _
from apprise.plugins.base import RequirementsSpec

logging.disable(logging.CRITICAL)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()


def test_apprise_cli_nux_env(tmpdir):
    """
    CLI: Nux Environment

    """

    class GoodNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, **kwargs):
            # Pretend everything is okay (when passing --disable-async)
            return True

        async def async_notify(self, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, *args, **kwargs):
            # Support url()
            return "good://"

    class BadNotification(NotifyBase):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        async def async_notify(self, **kwargs):
            # Pretend everything is okay
            return False

        def url(self, *args, **kwargs):
            # Support url()
            return "bad://"

    # Set up our notification types
    N_MGR["good"] = GoodNotification
    N_MGR["bad"] = BadNotification

    runner = CliRunner()
    result = runner.invoke(cli.main)
    # no servers specified; we return 1 (non-zero)
    assert result.exit_code == 1

    result = runner.invoke(cli.main, ["-v"])
    assert result.exit_code == 1

    result = runner.invoke(cli.main, ["-vv"])
    assert result.exit_code == 1

    result = runner.invoke(cli.main, ["-vvv"])
    assert result.exit_code == 1

    result = runner.invoke(cli.main, ["-vvvv"])
    assert result.exit_code == 1

    # Display version information and exit
    result = runner.invoke(cli.main, ["-V"])
    assert result.exit_code == 0

    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "good://localhost",
        ],
    )
    assert result.exit_code == 0

    with mock.patch("requests.post") as mock_post:
        # Prepare Mock
        mock_post.return_value = requests.Request()
        mock_post.return_value.status_code = requests.codes.ok

        result = runner.invoke(
            cli.main,
            [
                "-t",
                "test title",
                "-b",
                "test body\\nsNewLine",
                # Test using interpret escapes
                "-e",
                # Use our JSON query
                "json://localhost",
            ],
        )
        assert result.exit_code == 0

        # Test our call count
        assert mock_post.call_count == 1

        # Our string is now escaped correctly
        assert (
            json.loads(mock_post.call_args_list[0][1]["data"]).get(
                "message", ""
            )
            == "test body\nsNewLine"
        )

        # Reset
        mock_post.reset_mock()

        result = runner.invoke(
            cli.main,
            [
                "-t",
                "test title",
                "-b",
                "test body\\nsNewLine",
                # No -e switch at all (so we don't escape the above)
                # Use our JSON query
                "json://localhost",
            ],
        )
        assert result.exit_code == 0

        # Test our call count
        assert mock_post.call_count == 1

        # Our string is now escaped correctly
        assert (
            json.loads(mock_post.call_args_list[0][1]["data"]).get(
                "message", ""
            )
            == "test body\\nsNewLine"
        )

    # Run in synchronous mode
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "good://localhost",
            "--disable-async",
        ],
    )
    assert result.exit_code == 0

    # Test Debug Mode (--debug)
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "good://localhost",
            "--debug",
        ],
    )
    assert result.exit_code == 0

    # Test Debug Mode (-D)
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "good://localhost",
            "-D",
        ],
    )
    assert result.exit_code == 0

    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "good://localhost",
        ],
        input="test stdin body\n",
    )
    assert result.exit_code == 0

    # Run in synchronous mode
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "good://localhost",
            "--disable-async",
        ],
        input="test stdin body\n",
    )
    assert result.exit_code == 0

    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "bad://localhost",
        ],
    )
    assert result.exit_code == 1

    # Run in synchronous mode
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "bad://localhost",
            "-Da",
        ],
    )
    assert result.exit_code == 1

    # Testing with the --dry-run flag reveals a successful response since we
    # don't actually execute the bad:// notification; we only display it
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "bad://localhost",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0

    # Write a simple text based configuration file
    t = tmpdir.mkdir("apprise-obj").join("apprise")
    buf = f"""
    # Include ourselves
    include {t!s}

    taga,tagb=good://localhost
    tagc=good://nuxref.com
    """
    t.write(buf)

    # This will read our configuration and not send any notices at all
    # because we assigned tags to all of our urls and didn't identify
    # a specific match below.

    # 'include' reference in configuration file would have included the file a
    # second time (since recursion default is 1).
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "test config",
            "--config",
            str(t),
        ],
    )
    # Even when recursion take place, tags are all honored
    # so 2 is returned because nothing was notified
    assert result.exit_code == 3

    # This will send out 1 notification because our tag matches
    # one of the entries above
    # translation: has taga
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "has taga",
            "--config",
            str(t),
            "--tag",
            "taga",
        ],
    )
    assert result.exit_code == 0

    # Test recursion
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "--config",
            str(t),
            "--tag",
            "tagc",
            # Invalid entry specified for recursion
            "-R",
            "invalid",
        ],
    )
    assert result.exit_code == 2

    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "--config",
            str(t),
            "--tag",
            "tagc",
            # missing entry specified for recursion
            "--recursive-depth",
        ],
    )
    assert result.exit_code == 2

    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "--config",
            str(t),
            "--tag",
            "tagc",
            # Disable recursion (thus inclusion will be ignored)
            "-R",
            "0",
        ],
    )
    assert result.exit_code == 0

    # Test recursion
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "test title",
            "-b",
            "test body",
            "--config",
            str(t),
            "--tag",
            "tagc",
            # Recurse up to 5 times
            "--recursion-depth",
            "5",
        ],
    )
    assert result.exit_code == 0

    # This will send out 2 notifications because by specifying 2 tag
    # entries, we 'or' them together:
    # translation: has taga or tagb or tagd
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "has taga OR tagc OR tagd",
            "--config",
            str(t),
            "--tag",
            "taga",
            "--tag",
            "tagc",
            "--tag",
            "tagd",
        ],
    )
    assert result.exit_code == 0

    # Write a simple text based configuration file
    t = tmpdir.mkdir("apprise-obj2").join("apprise-test2")
    buf = """
    good://localhost/1
    good://localhost/2
    good://localhost/3
    good://localhost/4
    good://localhost/5
    myTag=good://localhost/6
    """
    t.write(buf)

    # This will read our configuration and send a notification to
    # the first 5 entries in the list, but not the one that has
    # the tag associated with it
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "test config",
            "--config",
            str(t),
        ],
    )
    assert result.exit_code == 0

    # Test our notification type switch (it defaults to info) so we want to
    # try it as a different value. Should return without a problem
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "# test config",
            "--config",
            str(t),
            "-n",
            "success",
        ],
    )
    assert result.exit_code == 0

    # Test our notification type switch when set to something unsupported
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "test config",
            "--config",
            str(t),
            "--notification-type",
            "invalid",
        ],
    )
    # An error code of 2 is returned if invalid input is specified on the
    # command line
    assert result.exit_code == 2

    # The notification type switch is case-insensitive
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "test config",
            "--config",
            str(t),
            "--notification-type",
            "WARNING",
        ],
    )
    assert result.exit_code == 0

    # Test our formatting switch (it defaults to text) so we want to try it as
    # a different value. Should return without a problem
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "# test config",
            "--config",
            str(t),
            "-i",
            "markdown",
        ],
    )
    assert result.exit_code == 0

    # Test our formatting switch when set to something unsupported
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "test config",
            "--config",
            str(t),
            "--input-format",
            "invalid",
        ],
    )
    # An error code of 2 is returned if invalid input is specified on the
    # command line
    assert result.exit_code == 2

    # The formatting switch is not case sensitive
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "# test config",
            "--config",
            str(t),
            "--input-format",
            "HTML",
        ],
    )
    assert result.exit_code == 0

    # As a way of ensuring we match the first 5 entries, we can run a
    # --dry-run against the same result set above and verify the output
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "test config",
            "--config",
            str(t),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    lines = re.split(r"[\r\n]", result.output.strip())
    # 5 lines of all good:// entries matched + url id underneath
    assert len(lines) == 10
    # Verify we match against the remaining good:// entries
    for i in range(0, 10, 2):
        assert lines[i].endswith("good://")

    # This will fail because nothing matches mytag. It's case sensitive
    # and we would only actually match against myTag
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "has mytag",
            "--config",
            str(t),
            "--tag",
            "mytag",
        ],
    )
    assert result.exit_code == 3

    # Same command as the one identified above except we set the --dry-run
    # flag. This causes our list of matched results to be printed only.
    # However, since we don't match anything; we still fail with a return code
    # of 2.
    result = runner.invoke(
        cli.main,
        ["-b", "has mytag", "--config", str(t), "--tag", "mytag", "--dry-run"],
    )
    assert result.exit_code == 3

    # Here is a case where we get what was expected; we also attach a file
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "has myTag",
            "--config",
            str(t),
            "--attach",
            join(dirname(__file__), "var", "apprise-test.gif"),
            "--tag",
            "myTag",
        ],
    )
    assert result.exit_code == 0

    # Testing with the --dry-run flag reveals the same positive results
    # because there was at least one match
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "has myTag",
            "--config",
            str(t),
            "--tag",
            "myTag",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0

    #
    # Test environment variables
    #
    # Write a simple text based configuration file
    t2 = tmpdir.mkdir("apprise-obj-env").join("apprise")
    buf = """
    # A general one
    good://localhost

    # A failure (if we use the fail tag)
    fail=bad://localhost

    # A normal one tied to myTag
    myTag=good://nuxref.com
    """
    t2.write(buf)

    with environ(APPRISE_URLS="good://localhost"):
        # This will load okay because we defined the environment
        # variable with a valid URL
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "test environment",
                # Test that we ignore our tag
                "--tag",
                "mytag",
            ],
        )
        assert result.exit_code == 0

        # Same action but without --tag
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "test environment",
            ],
        )
        assert result.exit_code == 0

    with (
        mock.patch("apprise.cli.DEFAULT_CONFIG_PATHS", []),
        environ(APPRISE_URLS="      "),
    ):
        # An empty string is not valid and therefore not loaded so the below
        # fails. We override the DEFAULT_CONFIG_PATHS because we don't want to
        # detect ones loaded on the machine running the unit tests
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "test environment",
            ],
        )
        assert result.exit_code == 1

    with environ(APPRISE_URLS="bad://localhost"):
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "test environment",
            ],
        )
        assert result.exit_code == 1

        # If we specify an inline URL, it will over-ride the environment
        # variable
        result = runner.invoke(
            cli.main,
            [
                "-t",
                "test title",
                "-b",
                "test body",
                "good://localhost",
            ],
        )
        assert result.exit_code == 0

        # A Config file also over-rides the environment variable if
        # specified on the command line:
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "has myTag",
                "--config",
                str(t2),
                "--tag",
                "myTag",
            ],
        )
        assert result.exit_code == 0

    with environ(APPRISE_CONFIG=str(t2)):
        # Deprecated test case
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "has myTag",
                "--tag",
                "myTag",
            ],
        )
        assert result.exit_code == 0

    with environ(APPRISE_CONFIG_PATH=str(t2)):
        # Our configuration file will load from our environmment variable
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "has myTag",
                "--tag",
                "myTag",
            ],
        )
        assert result.exit_code == 0

    with environ(APPRISE_CONFIG_PATH=str(t2) + ";/another/path"):
        # Our configuration file will load from our environmment variable
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "has myTag",
                "--tag",
                "myTag",
            ],
        )
        assert result.exit_code == 0

    with (
        mock.patch("apprise.cli.DEFAULT_CONFIG_PATHS", []),
        environ(APPRISE_CONFIG="      "),
    ):
        # We will fail to send the notification as no path was specified.
        # We override the DEFAULT_CONFIG_PATHS because we don't want to detect
        # ones loaded on the machine running the unit tests
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "my message",
            ],
        )
        assert result.exit_code == 1

    with environ(APPRISE_CONFIG="garbage/file/path.yaml"):
        # We will fail to send the notification as the path
        # specified is not loadable
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "my message",
            ],
        )
        assert result.exit_code == 1

        # We can force an over-ride by specifying a config file on the
        # command line options:
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "has myTag",
                "--config",
                str(t2),
                "--tag",
                "myTag",
            ],
        )
        assert result.exit_code == 0

    # Just a general test; if both the --config and urls are specified
    # then the the urls trumps all
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "has myTag",
            "--config",
            str(t2),
            "good://localhost",
            "--tag",
            "fail",
        ],
    )
    # Tags are ignored, URL specified, so it trump config
    assert result.exit_code == 0

    # we just repeat the test as a proof that it only executes
    # the urls despite the fact the --config was specified
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "reads the url entry only",
            "--config",
            str(t2),
            "good://localhost",
            "--tag",
            "fail",
        ],
    )
    # Tags are ignored, URL specified, so it trump config
    assert result.exit_code == 0

    # once agian, but we call bad://
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "reads the url entry only",
            "--config",
            str(t2),
            "bad://localhost",
            "--tag",
            "myTag",
        ],
    )
    assert result.exit_code == 1

    # Test Escaping:
    result = runner.invoke(
        cli.main,
        [
            "-e",
            "-t",
            "test\ntitle",
            "-b",
            "test\nbody",
            "good://localhost",
        ],
    )
    assert result.exit_code == 0

    # Test Escaping (without title)
    result = runner.invoke(
        cli.main,
        [
            "--interpret-escapes",
            "-b",
            "test\nbody",
            "good://localhost",
        ],
    )
    assert result.exit_code == 0

    # Test Emojis:
    result = runner.invoke(
        cli.main,
        [
            "-j",
            "-t",
            ":smile:",
            "-b",
            ":grin:",
            "good://localhost",
        ],
    )
    assert result.exit_code == 0

    result = runner.invoke(
        cli.main,
        [
            "--interpret-emojis",
            "-t",
            ":smile:",
            "-b",
            ":grin:",
            "good://localhost",
        ],
    )
    assert result.exit_code == 0


def test_apprise_cli_modules(tmpdir):
    """
    CLI: --plugin (-P)

    """

    runner = CliRunner()

    #
    # Loading of modules works correctly
    #
    notify_cmod_base = tmpdir.mkdir("cli_modules")
    notify_cmod = notify_cmod_base.join("hook.py")
    notify_cmod.write(cleandoc("""
    from apprise.decorators import notify

    @notify(on="climod")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass
    """))

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            str(notify_cmod),
            "-t",
            "title",
            "-b",
            "body",
            "climod://",
        ],
    )

    assert result.exit_code == 0

    # Test -P
    result = runner.invoke(
        cli.main,
        [
            "-P",
            str(notify_cmod),
            "-t",
            "title",
            "-b",
            "body",
            "climod://",
        ],
    )

    assert result.exit_code == 0

    # Test double hooks
    notify_cmod2 = notify_cmod_base.join("hook2.py")
    notify_cmod2.write(cleandoc("""
    from apprise.decorators import notify

    @notify(on="climod2")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass
    """))

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            str(notify_cmod),
            "--plugin-path",
            str(notify_cmod2),
            "-t",
            "title",
            "-b",
            "body",
            "climod://",
            "climod2://",
        ],
    )

    assert result.exit_code == 0

    with environ(
        APPRISE_PLUGIN_PATH=str(notify_cmod) + ";" + str(notify_cmod2)
    ):
        # Leverage our environment variables to specify the plugin path
        result = runner.invoke(
            cli.main,
            [
                "-b",
                "body",
                "climod://",
                "climod2://",
            ],
        )

        assert result.exit_code == 0


@pytest.mark.skipif(
    sys.platform == "win32", reason="Unreliable results to be determined"
)
def test_apprise_cli_persistent_storage(tmpdir):
    """
    CLI: test persistent storage

    """

    # This is a made up class that is just used to verify
    class NoURLIDNotification(NotifyBase):
        """A no URL ID."""

        # Update URL identifier
        url_identifier = False

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def send(self, **kwargs):

            # Pretend everything is okay
            return True

        def url(self, *args, **kwargs):
            # Support URL
            return "noper://"

        def parse_url(self, *args, **kwargs):
            # parse our url
            return {"schema": "noper"}

    # This is a made up class that is just used to verify
    class TestNotification(NotifyBase):
        """A Testing Script."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def send(self, **kwargs):

            # Test our persistent settings
            self.store.set("key", "value")
            assert self.store.get("key") == "value"

            # Pretend everything is okay
            return True

        def url(self, *args, **kwargs):
            # Support URL
            return "test://"

        def parse_url(self, *args, **kwargs):
            # parse our url
            return {"schema": "test"}

    # assign test:// to our  notification defined above
    N_MGR["test"] = TestNotification
    N_MGR["noper"] = NoURLIDNotification

    # Write a simple text based configuration file
    config = tmpdir.join("apprise.cfg")
    buf = cleandoc("""
    # Create a config file we can source easily
    test=test://
    noper=noper://

    # Define a second test URL that will
    two-urls=test://

    # Create another entry that has no tag associatd with it
    test://?entry=2
    """)
    config.write(buf)

    runner = CliRunner()

    # Generate notification that creates persistent data
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    # our persist storage has not been created yet
    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9]{8}\s+0\.00B\s+unused\s+-\s+test://\s*",
        _stdout,
        re.MULTILINE,
    )

    # An invalid mode specified
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--storage-mode",
            "invalid",
            "--config",
            str(config),
            "-g",
            "test",
            "-t",
            "title",
            "-b",
            "body",
        ],
    )
    # Bad mode specified
    assert result.exit_code == 2

    # Invalid uid lenth specified
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--storage-mode",
            "flush",
            "--storage-uid-length",
            1,
            "--config",
            str(config),
            "-g",
            "test",
            "-t",
            "title",
            "-b",
            "body",
        ],
    )
    # storage uid length to small
    assert result.exit_code == 2

    # No files written yet; just config file exists
    dir_content = os.listdir(str(tmpdir))
    assert len(dir_content) == 1
    assert "apprise.cfg" in dir_content

    # Generate notification that creates persistent data
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--storage-mode",
            "flush",
            "--config",
            str(config),
            "-t",
            "title",
            "-b",
            "body",
            "-g",
            "test",
        ],
    )
    # We parsed our data accordingly
    assert result.exit_code == 0

    dir_content = os.listdir(str(tmpdir))
    assert len(dir_content) == 2
    assert "apprise.cfg" in dir_content
    assert "ea482db7" in dir_content

    # Have a look at our storage listings
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # keyword list is not required
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # search on something that won't match
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
            "nomatch",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    assert not result.stdout.strip()

    # closest match search
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
            # Closest match will hit a result
            "ea",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # list is the presumed option if no match
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            # Closest match will hit a result
            "ea",
        ],
    )
    # list our entries successfully again..
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # Search based on tag
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
            # We can match by tags too
            "-g",
            "test",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # Prune call but prune-days set incorrectly
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--storage-prune-days",
            -1,
            "storage",
            "prune",
        ],
    )
    # storage prune days is invalid
    assert result.exit_code == 2

    # Create a tmporary namespace
    tmpdir.mkdir("namespace")

    # Generates another listing
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
        ],
    )

    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^[0-9]\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )
    assert re.match(
        r".*\s*[0-9]\.\s+namespace\s+0\.00B\s+stale.*",
        _stdout,
        (re.MULTILINE | re.DOTALL),
    )

    # Generates another listing but utilize the tag
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "--tag",
            "test",
            "storage",
        ],
    )

    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^[0-9]\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )
    assert (
        re.match(
            r".*\s*[0-9]\.\s+namespace\s+0\.00B\s+stale.*",
            _stdout,
            (re.MULTILINE | re.DOTALL),
        )
        is None
    )

    # Clear all of our accumulated disk space
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "clear",
        ],
    )

    # successful
    assert result.exit_code == 0

    # Generate another listing
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
        ],
    )

    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    # back to unused state and 0 bytes
    assert re.match(
        r"^[0-9]\.\s+[a-z0-9_-]{8}\s+0\.00B\s+unused\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )
    # namespace is gone now
    assert (
        re.match(
            r".*\s*[0-9]\.\s+namespace\s+0\.00B\s+stale.*",
            _stdout,
            (re.MULTILINE | re.DOTALL),
        )
        is None
    )

    # Provide both tags and uid
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "ea",
            "-g",
            "test",
        ],
    )

    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    # back to unused state and 0 bytes
    assert re.match(
        r"^[0-9]\.\s+[a-z0-9_-]{8}\s+0\.00B\s+unused\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # Generate notification that creates persistent data
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--storage-mode",
            "flush",
            "--config",
            str(config),
            "-t",
            "title",
            "-b",
            "body",
            "-g",
            "test",
        ],
    )
    # We parsed our data accordingly
    assert result.exit_code == 0

    # Have a look at our storage listings
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # Prune call but prune-days set incorrectly
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "storage",
            "prune",
        ],
    )

    # Run our prune successfully
    assert result.exit_code == 0

    # Have a look at our storage listings (expected no change in output)
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9_-]{8}\s+81\.00B\s+active\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # Prune call but prune-days set incorrectly
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            # zero simulates a full clean
            "--storage-prune-days",
            0,
            "storage",
            "prune",
        ],
    )

    # Run our prune successfully
    assert result.exit_code == 0

    # Have a look at our storage listings (expected no change in output)
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
        ],
    )
    # list our entries
    assert result.exit_code == 0

    # Note: An prune/expiry of zero gets everything except for MS Windows
    # during testing only.
    # Until this can be resolved, this is the section of the test that
    # caused us to disable it in MS Windows
    _stdout = result.stdout.strip()
    assert re.match(
        r"^1\.\s+[a-z0-9_-]{8}\s+0\.00B\s+unused\s+-\s+test://$",
        _stdout,
        re.MULTILINE,
    )

    # New Temporary namespace
    new_persistent_base = tmpdir.mkdir("namespace")
    with environ(APPRISE_STORAGE_PATH=str(new_persistent_base)):
        # Reload our module
        reload(cli)

        # Nothing in our directory yet
        dir_content = os.listdir(str(new_persistent_base))
        assert len(dir_content) == 0

        # Generate notification that creates persistent data
        # storage path is pulled out of our environment variable
        result = runner.invoke(
            cli.main,
            [
                "--storage-mode",
                "flush",
                "--config",
                str(config),
                "-t",
                "title",
                "-b",
                "body",
                "-g",
                "test",
            ],
        )
        # We parsed our data accordingly
        assert result.exit_code == 0

        # Now content exists
        dir_content = os.listdir(str(new_persistent_base))
        assert len(dir_content) == 1

    # Reload our module with our environment variable gone
    reload(cli)

    # Clear loaded modules
    N_MGR.unload_modules()


def test_apprise_cli_details(tmpdir):
    """
    CLI: --details (-l)

    """

    runner = CliRunner()

    #
    # Testing the printout of our details
    #   --details or -l
    #
    result = runner.invoke(
        cli.main,
        [
            "--details",
        ],
    )
    assert result.exit_code == 0

    result = runner.invoke(
        cli.main,
        [
            "-l",
        ],
    )
    assert result.exit_code == 0

    # Clear loaded modules
    N_MGR.unload_modules()

    # This is a made up class that is just used to verify
    class TestReq01Notification(NotifyBase):
        """This class is used to test various requirement configurations."""

        # Set some requirements
        requirements: ClassVar[RequirementsSpec] = {
            "packages_required": [
                "cryptography <= 3.4",
                "ultrasync",
            ],
            "packages_recommended": "django",
        }

        def url(self, **kwargs):
            # Support URL
            return ""

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    N_MGR["req01"] = TestReq01Notification

    # This is a made up class that is just used to verify
    class TestReq02Notification(NotifyBase):
        """This class is used to test various requirement configurations."""

        # Just not enabled at all
        enabled = False

        # Set some requirements
        requirements: ClassVar[RequirementsSpec] = {
            # None and/or [] is implied, but jsut to show that the code won't
            # crash if explicitly set this way:
            "packages_required": None,
            "packages_recommended": [
                "cryptography <= 3.4",
            ],
        }

        def url(self, **kwargs):
            # Support URL
            return ""

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    N_MGR["req02"] = TestReq02Notification

    # This is a made up class that is just used to verify
    class TestReq03Notification(NotifyBase):
        """This class is used to test various requirement configurations."""

        # Set some requirements (but additionally include a details over-ride)
        requirements: ClassVar[RequirementsSpec] = {
            # We can over-ride the default details assigned to our plugin if
            # specified
            "details": _("some specified requirement details"),
            # We can set a string value as well (it does not have to be a list)
            "packages_recommended": "cryptography <= 3.4",
        }

        def url(self, **kwargs):
            # Support URL
            return ""

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    N_MGR["req03"] = TestReq03Notification

    # This is a made up class that is just used to verify
    class TestReq04Notification(NotifyBase):
        """This class is used to test a case where our requirements is fixed to
        a None."""

        # This is the same as saying there are no requirements
        requirements = None

        def url(self, **kwargs):
            # Support URL
            return ""

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    N_MGR["req04"] = TestReq04Notification

    # This is a made up class that is just used to verify
    class TestReq05Notification(NotifyBase):
        """This class is used to test a case where only packages_recommended is
        identified."""

        requirements: ClassVar[RequirementsSpec] = {
            "packages_recommended": "cryptography <= 3.4"
        }

        def url(self, **kwargs):
            # Support URL
            return ""

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    N_MGR["req05"] = TestReq05Notification

    class TestDisabled01Notification(NotifyBase):
        """This class is used to test a pre-disabled state."""

        # Just flat out disable our service
        enabled = False

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = "na01"

        def url(self, **kwargs):
            # Support URL
            return ""

        def notify(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    N_MGR["na01"] = TestDisabled01Notification

    class TestDisabled02Notification(NotifyBase):
        """This class is used to test a post-disabled state."""

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = "na02"

        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)

            # enable state changes **AFTER** we initialize
            self.enabled = False

        def url(self, **kwargs):
            # Support URL
            return ""

        def notify(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    N_MGR["na02"] = TestDisabled02Notification

    # We'll add a good notification to our list
    class TesEnabled01Notification(NotifyBase):
        """This class is just a simple enabled one."""

        # we'll use this as a key to make our service easier to find
        # in the next part of the testing
        service_name = "good"

        def url(self, **kwargs):
            # Support URL
            return ""

        def send(self, **kwargs):
            # Pretend everything is okay (so we don't break other tests)
            return True

    N_MGR["good"] = TesEnabled01Notification

    # Verify that we can pass through all of our different details
    result = runner.invoke(
        cli.main,
        [
            "--details",
        ],
    )
    assert result.exit_code == 0

    result = runner.invoke(
        cli.main,
        [
            "-l",
        ],
    )
    assert result.exit_code == 0

    # Clear loaded modules
    N_MGR.unload_modules()


def test_apprise_cli_print_help():
    """
    CLI: --help (-h)

    """
    runner = CliRunner()

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    N_MGR._paths_previously_scanned.clear()
    N_MGR._custom_module_map.clear()

    # Print help and exit
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0

    result = runner.invoke(cli.main, ["-h"])
    assert result.exit_code == 0


@mock.patch("requests.post")
def test_apprise_cli_plugin_loading(mock_post, tmpdir):
    """
    CLI: --plugin-path (-P)

    """
    # Prepare Mock
    mock_post.return_value = requests.Request()
    mock_post.return_value.status_code = requests.codes.ok

    runner = CliRunner()

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    N_MGR._paths_previously_scanned.clear()
    N_MGR._custom_module_map.clear()

    # Test a path that has no files to load in it
    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            join(str(tmpdir), "invalid_path"),
            "-b",
            "test\nbody",
            "json://localhost",
        ],
    )
    # The path is silently loaded but fails... it's okay because the
    # notification we're choosing to notify does exist
    assert result.exit_code == 0

    # Directories that don't exist passed in by the CLI aren't even scanned
    assert len(N_MGR._paths_previously_scanned) == 0
    assert len(N_MGR._custom_module_map) == 0

    # Test our current existing path that has no entries in it
    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            str(tmpdir.mkdir("empty")),
            "-b",
            "test\nbody",
            "json://localhost",
        ],
    )
    # The path is silently loaded but fails... it's okay because the
    # notification we're choosing to notify does exist
    assert result.exit_code == 0
    assert len(N_MGR._paths_previously_scanned) == 1
    assert join(str(tmpdir), "empty") in N_MGR._paths_previously_scanned

    # However there was nothing to load
    assert len(N_MGR._custom_module_map) == 0

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    N_MGR._paths_previously_scanned.clear()
    N_MGR._custom_module_map.clear()

    # Prepare ourselves a file to work with
    notify_hook_a_base = tmpdir.mkdir("random")
    notify_hook_a = notify_hook_a_base.join("myhook01.py")
    notify_hook_a.write(cleandoc("""
    raise ImportError
    """))

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            str(notify_hook_a),
            "-b",
            "test\nbody",
            # A custom hook:
            "clihook://",
        ],
    )
    # It doesn't exist so it will fail
    # meanwhile we would have failed to load the myhook path
    assert result.exit_code == 1

    # The path is silently loaded but fails... it's okay because the
    # notification we're choosing to notify does exist
    assert len(N_MGR._paths_previously_scanned) == 1
    assert str(notify_hook_a) in N_MGR._paths_previously_scanned
    # However there was nothing to load
    assert len(N_MGR._custom_module_map) == 0

    # Prepare ourselves a file to work with
    notify_hook_aa = notify_hook_a_base.join("myhook02.py")
    notify_hook_aa.write(cleandoc("""
    garbage entry
    """))

    N_MGR.plugins()
    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            str(notify_hook_aa),
            "-b",
            "test\nbody",
            # A custom hook:
            "clihook://custom",
        ],
    )
    # It doesn't exist so it will fail
    # meanwhile we would have failed to load the myhook path
    assert result.exit_code == 1

    # The path is silently loaded but fails...
    # as a result the path stacks with the last
    assert len(N_MGR._paths_previously_scanned) == 2
    assert str(notify_hook_a) in N_MGR._paths_previously_scanned
    assert str(notify_hook_aa) in N_MGR._paths_previously_scanned
    # However there was nothing to load
    assert len(N_MGR._custom_module_map) == 0

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    N_MGR._paths_previously_scanned.clear()
    N_MGR._custom_module_map.clear()

    # Prepare ourselves a file to work with
    notify_hook_b = tmpdir.mkdir("goodmodule").join("__init__.py")
    notify_hook_b.write(cleandoc("""
    from apprise.decorators import notify

    # We want to trigger on anyone who configures a call to clihook://
    @notify(on="clihook")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        # A simple test - print to screen
        print("{}: {} - {}".format(notify_type, title, body))

        # No return (so a return of None) get's translated to True

    # Define another in the same file
    @notify(on="clihookA")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        # A simple test - print to screen
        print("!! {}: {} - {}".format(notify_type, title, body))

        # No return (so a return of None) get's translated to True
    """))

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            str(tmpdir),
            "-b",
            "test body",
            # A custom hook:
            "clihook://still/valid",
        ],
    )

    # We can detect the goodmodule (which has an __init__.py in it)
    # so we'll load okay
    assert result.exit_code == 0

    # Let's see how things got loaded:
    assert len(N_MGR._paths_previously_scanned) == 2
    assert str(tmpdir) in N_MGR._paths_previously_scanned
    # absolute path to detected module is also added
    assert (
        join(str(tmpdir), "goodmodule", "__init__.py")
        in N_MGR._paths_previously_scanned
    )

    # We also loaded our clihook properly
    assert len(N_MGR._custom_module_map) == 1

    # We can find our new hook loaded in our schema map now...
    assert "clihook" in N_MGR

    # Capture our key for reference
    key = next(iter(N_MGR._custom_module_map.keys()))

    # We loaded 2 entries from the same file
    assert len(N_MGR._custom_module_map[key]["notify"]) == 2
    assert "clihook" in N_MGR._custom_module_map[key]["notify"]
    # Converted to lower case
    assert "clihooka" in N_MGR._custom_module_map[key]["notify"]

    # Our function name
    assert (
        N_MGR._custom_module_map[key]["notify"]["clihook"]["fn_name"]
        == "mywrapper"
    )
    # What we parsed from the `on` keyword in the @notify decorator
    assert (
        N_MGR._custom_module_map[key]["notify"]["clihook"]["url"]
        == "clihook://"
    )
    # our default name Assignment.  This can be-overridden on the @notify
    # decorator by just adding a name= to the parameter list
    assert N_MGR["clihook"].service_name == "Custom - clihook"

    # Our Base Notification object when initialized:
    assert (
        len(N_MGR._module_map[N_MGR._custom_module_map[key]["name"]]["plugin"])
        == 2
    )
    for plugin in N_MGR._module_map[N_MGR._custom_module_map[key]["name"]][
        "plugin"
    ]:
        assert isinstance(plugin(), NotifyBase)

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    N_MGR._paths_previously_scanned.clear()
    N_MGR._custom_module_map.clear()
    del N_MGR["clihook"]

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            str(notify_hook_b),
            "-b",
            "test body",
            # A custom hook:
            "clihook://",
        ],
    )

    # Absolute path to __init__.py is okay
    assert result.exit_code == 0

    # we can verify that it prepares our message
    assert result.stdout.strip() == "info:  - test body"

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    N_MGR._paths_previously_scanned.clear()
    N_MGR._custom_module_map.clear()
    del N_MGR["clihook"]

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            dirname(str(notify_hook_b)),
            "-b",
            "test body",
            # A custom hook:
            "clihook://",
        ],
    )

    # Now we succeed to load our module when pointed to it only because
    # an __init__.py is found on the inside of it
    assert result.exit_code == 0

    # we can verify that it prepares our message
    assert result.stdout.strip() == "info:  - test body"

    # Test double paths that are the same; this ensures we only
    # load the plugin once
    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            dirname(str(notify_hook_b)),
            "--plugin-path",
            str(notify_hook_b),
            "--details",
        ],
    )

    # Now we succeed to load our module when pointed to it only because
    # an __init__.py is found on the inside of it
    assert result.exit_code == 0

    # Clear our working variables so they don't obstruct the next test
    # This simulates an actual call from the CLI.  Unfortunately through
    # testing were occupying the same memory space so our singleton's
    # have already been populated
    N_MGR._paths_previously_scanned.clear()
    N_MGR._custom_module_map.clear()
    del N_MGR["clihook"]

    # Prepare ourselves a file to work with
    notify_hook_b = tmpdir.mkdir("complex").join("complex.py")
    notify_hook_b.write(cleandoc("""
    from apprise.decorators import notify

    # We can't over-ride an element that already exists
    # in this case json://
    @notify(on="json")
    def mywrapper_01(body, title, notify_type, *args, **kwargs):
        # Return True (same as None)
        return True

    @notify(on="willfail", name="always failing...")
    def mywrapper_02(body, title, notify_type, *args, **kwargs):
        # Simply fail
        return False

    @notify(on="clihook1", name="the original clihook entry")
    def mywrapper_03(body, title, notify_type, *args, **kwargs):
        # Return True
        return True

    # This is a duplicate o the entry above, so it can not be
    # loaded...
    @notify(on="clihook1", name="a duplicate of the clihook entry")
    def mywrapper_04(body, title, notify_type, *args, **kwargs):
        # Return True
        return True

    # This is where things get realy cool... we can not only
    # define the schema we want to over-ride, but we can define
    # some default values to pass into our wrapper function to
    # act as a base before whatever was actually passed in is
    # applied ontop.... think of it like templating information
    @notify(on="clihook2://localhost")
    def mywrapper_05(body, title, notify_type, *args, **kwargs):
        # Return True
        return True


    # This can't load because of the defined schema/on definition
    @notify(on="", name="an invalid schema was specified")
    def mywrapper_06(body, title, notify_type, *args, **kwargs):
        return True
    """))

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            join(str(tmpdir), "complex"),
            "-b",
            "test body",
            # A custom hook that does not exist
            "clihook://",
        ],
    )

    # Since clihook:// isn't in our complex listing, this will fail
    assert result.exit_code == 1

    # Let's see how things got loaded
    assert len(N_MGR._paths_previously_scanned) == 2
    # Our path we specified on the CLI...
    assert join(str(tmpdir), "complex") in N_MGR._paths_previously_scanned

    # absolute path to detected module is also added
    assert (
        join(str(tmpdir), "complex", "complex.py")
        in N_MGR._paths_previously_scanned
    )

    # We loaded our one module successfuly
    assert len(N_MGR._custom_module_map) == 1

    # We can find our new hook loaded in our SCHEMA_MAP now...
    assert "willfail" in N_MGR
    assert "clihook1" in N_MGR
    assert "clihook2" in N_MGR

    # Capture our key for reference
    key = next(iter(N_MGR._custom_module_map.keys()))

    assert len(N_MGR._custom_module_map[key]["notify"]) == 3
    assert "willfail" in N_MGR._custom_module_map[key]["notify"]
    assert "clihook1" in N_MGR._custom_module_map[key]["notify"]
    # We only load 1 instance of the clihook2, the second will fail
    assert "clihook2" in N_MGR._custom_module_map[key]["notify"]
    # We can never load previously created notifications
    assert "json" not in N_MGR._custom_module_map[key]["notify"]

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            join(str(tmpdir), "complex"),
            "-b",
            "test body",
            # A custom notification set up for failure
            "willfail://",
        ],
    )
    # Note that the failure of the decorator carries all the way back
    # to the CLI
    assert result.exit_code == 1

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            join(str(tmpdir), "complex"),
            "-b",
            "test body",
            # our clihook that returns true
            "clihook1://",
            # our other loaded clihook
            "clihook2://",
        ],
    )
    # Note that the failure of the decorator carries all the way back
    # to the CLI
    assert result.exit_code == 0


    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            join(str(tmpdir), "complex"),
            "--notification-type", "invalid",
            "-b",
            "test body",
            # our clihook that returns true
            "clihook1://",
        ],
    )
    # Bad notification type specified
    assert result.exit_code == 2

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            join(str(tmpdir), "complex"),
            "-b",
            "-i", "warning"
            "test body",
            # our clihook that returns true
            "clihook1://",
        ],
    )
    # Bad notification type specified
    assert result.exit_code == 0

    result = runner.invoke(
        cli.main,
        [
            "--plugin-path",
            join(str(tmpdir), "complex"),
            # Print our custom details to the screen
            "--details",
        ],
    )
    assert "willfail" in result.stdout
    assert "always failing..." in result.stdout

    assert "clihook1" in result.stdout
    assert "the original clihook entry" in result.stdout
    assert "a duplicate of the clihook entry" not in result.stdout

    assert "clihook2" in result.stdout
    assert "Custom - clihook2" in result.stdout

    # Note that the failure of the decorator carries all the way back
    # to the CLI
    assert result.exit_code == 0


@mock.patch("platform.system")
def test_apprise_cli_windows_env(mock_system):
    """
    CLI: Windows Environment

    """
    # Force a windows environment
    mock_system.return_value = "Windows"

    # Reload our module
    reload(cli)
