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

from importlib import reload
from importlib.metadata import PackageNotFoundError
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

from apprise import (
    Apprise,
    AppriseAsset,
    AppriseResultStatus,
    NotificationManager,
    NotifyBase,
    cli,
)
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

    with mock.patch("requests.request") as mock_request:
        # Prepare Mock
        mock_request.return_value = requests.Request()
        mock_request.return_value.status_code = requests.codes.ok

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
        assert mock_request.call_count == 1
        details = mock_request.call_args_list[0]
        assert details[0][0] == "POST"

        # Our string is now escaped correctly
        assert (
            json.loads(details[1]["data"]).get("message", "")
            == "test body\nsNewLine"
        )

        # Reset
        mock_request.reset_mock()

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
        assert mock_request.call_count == 1
        details = mock_request.call_args_list[0]
        assert details[0][0] == "POST"

        # Our string is now escaped correctly
        assert (
            json.loads(details[1]["data"]).get("message", "")
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

    # Tags are case-insensitive; mytag matches myTag
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
    assert result.exit_code == 0

    # Same command with --dry-run; one entry matches so exit code is 0
    result = runner.invoke(
        cli.main,
        ["-b", "has mytag", "--config", str(t), "--tag", "mytag", "--dry-run"],
    )
    assert result.exit_code == 0

    # A tag that does not exist in the config produces no matches; the live
    # run returns exit code 3 to signal "no services found".
    result = runner.invoke(
        cli.main,
        ["-b", "no match", "--config", str(t), "--tag", "nonexistent"],
    )
    assert result.exit_code == 3

    # --dry-run must mirror the live result: a non-matching tag also returns
    # exit code 3, not 0.  This guards against dry-run masking "no services
    # found" by always reporting success.
    result = runner.invoke(
        cli.main,
        [
            "-b",
            "no match",
            "--config",
            str(t),
            "--tag",
            "nonexistent",
            "--dry-run",
        ],
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
    notify_cmod.write(
        cleandoc("""
    from apprise.decorators import notify

    @notify(on="climod")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass
    """)
    )

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
    notify_cmod2.write(
        cleandoc("""
    from apprise.decorators import notify

    @notify(on="climod2")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        pass
    """)
    )

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
    stdout = result.stdout.strip()

    # Click output can wrap based on terminal width, and storage backend
    # sizes are not stable across Python/OS variations. Validate semantics.
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+unused\b",
        stdout,
        re.MULTILINE,
    )
    assert re.search(r"(?m)^\s*-\s+test://\s*$", stdout)

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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
        re.MULTILINE,
    )

    # Create a stale 8-char namespace on disk that belongs to a different
    # URL — it must NOT appear in the output when filtering by URL.
    tmpdir.mkdir("aaaaaaaa")

    # Filter by URL directly — no config file required; the URL is loaded
    # inline and its uid is used to match storage entries.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "storage",
            "list",
            # Pass the raw URL instead of an 8-char UID prefix
            "test://",
        ],
    )
    # Should produce exactly one entry (the url's namespace); the
    # unrelated stale directory 'aaaaaaaa' must not bleed into output.
    assert result.exit_code == 0

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
        re.MULTILINE,
    )
    # Confirm only one entry — stale 'aaaaaaaa' must be absent
    assert not re.search(r"aaaaaaaa", stdout)

    # URL filter alongside --config: URL filters trump all other sources,
    # including --config.  'a' is reset and only the URL-filter plugin
    # is loaded.  Its storage was already created, so exactly one active
    # entry should appear.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "storage",
            "list",
            "test://",
        ],
    )
    assert result.exit_code == 0
    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
        re.MULTILINE,
    )

    # Duplicate URL filter: the same URL specified twice.  Both entries
    # are added to the fresh Apprise instance; the uids dict groups them
    # under one uid key, so only a single storage entry should appear.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "storage",
            "list",
            "test://",
            "test://",
        ],
    )
    assert result.exit_code == 0
    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
        re.MULTILINE,
    )
    # Only one numbered entry should appear despite two URL arguments
    assert len(re.findall(r"^\d+\.", stdout, re.MULTILINE)) == 1

    # URL filter with an unrecognised schema: a.add() silently rejects the
    # URL, leaving the Apprise instance empty.  With no plugin uids resolved,
    # disk_scan is skipped entirely and the output is empty.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "storage",
            "list",
            "nosuchschema://filter",
        ],
    )
    assert result.exit_code == 0
    assert not result.stdout.strip()

    # URL filter with --tag: URL filter fires rule #1 which clears the tag
    # (same as sending a notification — URLs trump all, including tags).
    # The test:// plugin's storage is shown; the stale dirs are absent
    # because disk_scan is scoped to the URL-filter plugin's uid.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--tag",
            "test",
            "storage",
            "list",
            "test://",
        ],
    )
    assert result.exit_code == 0
    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
        re.MULTILINE,
    )
    # Stale dirs must not bleed into output when URL filter is active
    assert not re.search(r"aaaaaaaa", stdout)

    # URL filter scopes PRUNE too: only the test:// plugin's storage
    # directory is eligible; stale dirs like 'aaaaaaaa' are left alone.
    # Use --dry-run so we exercise the _had_url_filters namespace-scoping
    # branch without actually modifying disk (keeping ea482db7 active for
    # the assertions that follow).
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--storage-prune-days",
            0,
            "--dry-run",
            "storage",
            "prune",
            "test://",
        ],
    )
    assert result.exit_code == 0
    # The stale 'aaaaaaaa' directory must still exist after the URL-scoped
    # prune because it was outside the test:// namespace.
    assert os.path.isdir(os.path.join(str(tmpdir), "aaaaaaaa"))

    # URL filter scopes CLEAR too: only the test:// plugin's namespace is
    # cleared; unrelated stale directories are untouched.
    # Use --dry-run so we exercise the _had_url_filters scoping path
    # without wiping ea482db7 contents (subsequent tests expect it active).
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--dry-run",
            "storage",
            "clear",
            "test://",
        ],
    )
    assert result.exit_code == 0
    # 'aaaaaaaa' must still be present — it was outside the cleared scope
    assert os.path.isdir(os.path.join(str(tmpdir), "aaaaaaaa"))

    # Tag-scoped PRUNE: --tag limits the prune namespace to only the uids
    # that matched the tag filter.  The stale 'aaaaaaaa' directory is
    # outside that namespace and must not be removed.
    # Use --dry-run so the test is non-destructive and ea482db7 stays active.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "--tag",
            "test",
            "--storage-prune-days",
            0,
            "--dry-run",
            "storage",
            "prune",
        ],
    )
    assert result.exit_code == 0
    # The stale 'aaaaaaaa' directory must be untouched — it was outside the
    # tag-scoped prune namespace.
    assert os.path.isdir(os.path.join(str(tmpdir), "aaaaaaaa"))

    # Tag-scoped CLEAR: same principle — only the tagged plugin's namespace
    # is eligible for clearing; everything else is left alone.
    # Use --dry-run to keep ea482db7 active for subsequent assertions.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "--tag",
            "test",
            "--dry-run",
            "storage",
            "clear",
        ],
    )
    assert result.exit_code == 0
    # The stale 'aaaaaaaa' directory must survive — it was not in scope
    assert os.path.isdir(os.path.join(str(tmpdir), "aaaaaaaa"))

    # When a tag or URL filter is specified but resolves to nothing,
    # disk_prune() must NOT be called. The tests below confirm that ea482db7
    # survives each no-match check.

    # Tag-scoped PRUNE with a tag that matches no loaded plugin: nothing
    # resolves so disk_prune() must be skipped entirely.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "--tag",
            "no-such-tag",
            "--storage-prune-days",
            0,
            "storage",
            "prune",
        ],
    )
    assert result.exit_code == 0
    # ea482db7 must be intact -- the no-match prune must not wipe storage
    assert os.path.isdir(os.path.join(str(tmpdir), "ea482db7"))

    # Tag-scoped CLEAR with the same unmatchable tag: same guard must fire.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--config",
            str(config),
            "--tag",
            "no-such-tag",
            "storage",
            "clear",
        ],
    )
    assert result.exit_code == 0
    # ea482db7 must survive -- a no-match clear must not erase everything
    assert os.path.isdir(os.path.join(str(tmpdir), "ea482db7"))

    # URL filter that fails to load (unknown schema): _had_url_filters is
    # True but no uid resolves, so disk_prune() must not be called.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "--storage-prune-days",
            0,
            "storage",
            "prune",
            "nosuchschema://",
        ],
    )
    assert result.exit_code == 0
    assert os.path.isdir(os.path.join(str(tmpdir), "ea482db7"))

    # Same guard applies to clear when the URL filter resolves nothing.
    result = runner.invoke(
        cli.main,
        [
            "--storage-path",
            str(tmpdir),
            "storage",
            "clear",
            "nosuchschema://",
        ],
    )
    assert result.exit_code == 0
    assert os.path.isdir(os.path.join(str(tmpdir), "ea482db7"))

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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
        re.MULTILINE,
    )
    assert re.match(
        r".*\s*[0-9]\.\s+namespace\s+0\.00B\s+stale.*",
        stdout,
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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
        re.MULTILINE,
    )
    assert (
        re.match(
            r".*\s*[0-9]\.\s+namespace\s+0\.00B\s+stale.*",
            stdout,
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

    stdout = result.stdout.strip()
    # back to unused state and 0 bytes
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+unused\b",
        stdout,
        re.MULTILINE,
    )
    # namespace is gone now
    assert (
        re.match(
            r".*\s*[0-9]\.\s+namespace\s+0\.00B\s+stale.*",
            stdout,
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

    stdout = result.stdout.strip()
    # back to unused state and 0 bytes
    assert re.match(
        r"^[0-9]\.\s+[a-z0-9_-]{8}\s+0\.00B\s+unused\s+-\s+test://$",
        stdout,
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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
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

    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+active\b",
        stdout,
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
    stdout = result.stdout.strip()
    assert re.search(
        r"^1\.\s+[a-z0-9_-]{8}\s+\d+(?:\.\d{2})?[KMGT]?B\s+unused\b",
        stdout,
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


@mock.patch("requests.request")
def test_apprise_cli_plugin_loading(mock_request, tmpdir):
    """
    CLI: --plugin-path (-P)

    """
    # Prepare Mock
    mock_request.return_value = requests.Request()
    mock_request.return_value.status_code = requests.codes.ok

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
    notify_hook_a.write(
        cleandoc("""
    raise ImportError
    """)
    )

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
    notify_hook_aa.write(
        cleandoc("""
    garbage entry
    """)
    )

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
    notify_hook_b.write(
        cleandoc("""
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
    """)
    )

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
    notify_hook_b.write(
        cleandoc("""
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
    """)
    )

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
            "--notification-type",
            "invalid",
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
            "-i",
            "warningtest body",
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


@mock.patch("apprise.cli.NotificationManager")
@mock.patch("importlib.metadata.packages_distributions", create=True)
@mock.patch("importlib.metadata.version")
@mock.patch("apprise.cli.logger")
def test_apprise_cli_runtime_env_skip_when_not_debug(
    mock_logger, mock_ver, mock_dist, mock_mgr
):
    """
    CLI: _log_runtime_env() exits immediately when not at DEBUG level.
    """
    # Simulate a logger that is not at DEBUG level
    mock_logger.isEnabledFor.return_value = False

    cli._log_runtime_env()

    # Nothing should be computed or logged
    mock_logger.debug.assert_not_called()
    mock_mgr.assert_not_called()
    mock_dist.assert_not_called()
    mock_ver.assert_not_called()


@mock.patch("apprise.cli.NotificationManager")
@mock.patch("importlib.metadata.packages_distributions", create=True)
@mock.patch("importlib.metadata.version")
@mock.patch("apprise.cli.logger")
def test_apprise_cli_runtime_env_logging(
    mock_logger, mock_ver, mock_dist, mock_mgr
):
    """
    CLI: _log_runtime_env() summary
    """
    # Simulate a DEBUG-level logger
    mock_logger.isEnabledFor.return_value = True

    # Plugin whose dep should appear in output
    class EnabledPlugin:
        enabled = True

        @staticmethod
        def runtime_deps():
            return ("testpkg",)

    # Disabled plugin -- its dep must NOT appear in output
    class DisabledPlugin:
        enabled = False

        @staticmethod
        def runtime_deps():
            return ("disabled-dep",)

    # Plugin with no runtime_deps attribute -- silently skipped
    class NoRuntimeDepsPlugin:
        enabled = True

    mock_mgr.return_value = [
        {
            "plugin": {
                EnabledPlugin,
                DisabledPlugin,
                NoRuntimeDepsPlugin,
            },
        },
    ]
    mock_dist.return_value = {"testpkg": ["test-package"]}
    mock_ver.return_value = "9.9.9"

    cli._log_runtime_env()

    # Collect positional-arg tuples from each debug() call
    calls = [a for a, _ in mock_logger.debug.call_args_list]

    # Environment summary lines must be present
    assert any(a[0] == "Apprise: %s" for a in calls)
    assert any(a[0] == "Python: %s" for a in calls)
    assert any(a[0] == "Platform: %s" for a in calls)
    assert any(a[0] == "Encoding: %s" for a in calls)

    # Resolved deps emitted as a single inline line
    assert any(
        a[0] == "Runtime deps: %s" and a[1] == "test-package=9.9.9"
        for a in calls
    )

    # Disabled plugin dep must not be logged
    assert not any("disabled-dep" in str(a) for a in calls)


@mock.patch("apprise.cli.NotificationManager")
@mock.patch("importlib.metadata.packages_distributions", create=True)
@mock.patch("importlib.metadata.version")
@mock.patch("apprise.cli.logger")
def test_apprise_cli_runtime_env_no_runtime_deps(
    mock_logger, mock_ver, mock_dist, mock_mgr
):
    """
    CLI: _log_runtime_env()
    """
    mock_logger.isEnabledFor.return_value = True

    # Plugin that declares no deps
    class NoDepsPlugin:
        enabled = True

        @staticmethod
        def runtime_deps():
            return ()

    mock_mgr.return_value = [{"plugin": {NoDepsPlugin}}]

    cli._log_runtime_env()

    # Environment header was still logged
    calls = [a for a, _ in mock_logger.debug.call_args_list]
    assert any(a[0] == "Apprise: %s" for a in calls)

    # Package-metadata scan must not have been attempted
    mock_dist.assert_not_called()
    mock_ver.assert_not_called()

    # No "  pkg: ver" lines
    assert not any(a[0] == "Runtime deps: %s" for a in calls)


@mock.patch("apprise.cli.NotificationManager")
@mock.patch("importlib.metadata.packages_distributions", create=True)
@mock.patch("importlib.metadata.version")
@mock.patch("apprise.cli.logger")
def test_apprise_cli_runtime_env_dist_map_exception(
    mock_logger, mock_ver, mock_dist, mock_mgr
):
    """
    CLI: _log_runtime_env() handles packages_distributions() failures.
    """
    mock_logger.isEnabledFor.return_value = True

    class DepPlugin:
        enabled = True

        @staticmethod
        def runtime_deps():
            return ("somepkg",)

    mock_mgr.return_value = [{"plugin": {DepPlugin}}]
    mock_dist.side_effect = Exception("metadata unavailable")

    # Must not raise
    cli._log_runtime_env()

    # pkg_version should never be reached
    mock_ver.assert_not_called()

    # No "  pkg: ver" lines
    calls = [a for a, _ in mock_logger.debug.call_args_list]
    assert not any(a[0] == "Runtime deps: %s" for a in calls)


@mock.patch("apprise.cli.NotificationManager")
@mock.patch("importlib.metadata.packages_distributions", create=True)
@mock.patch("importlib.metadata.version")
@mock.patch("apprise.cli.logger")
def test_apprise_cli_runtime_env_lookup_errors(
    mock_logger, mock_ver, mock_dist, mock_mgr
):
    """
    CLI: _log_runtime_env() silently skips packages exception raised.
    """
    mock_logger.isEnabledFor.return_value = True

    # Plugin whose runtime_deps() raises
    class BrokenPlugin:
        enabled = True

        @staticmethod
        def runtime_deps():
            raise RuntimeError("plugin error")

    # Plugin whose dep import name is not in the dist map
    class UnmappedPlugin:
        enabled = True

        @staticmethod
        def runtime_deps():
            return ("notmapped",)

    # Plugin whose dep maps to a dist but the version lookup fails
    class VersionlessPlugin:
        enabled = True

        @staticmethod
        def runtime_deps():
            return ("verpkg",)

    mock_mgr.return_value = [
        {
            "plugin": {
                BrokenPlugin,
                UnmappedPlugin,
                VersionlessPlugin,
            },
        },
    ]

    # "notmapped" absent from map; "verpkg" present but ver raises
    mock_dist.return_value = {"verpkg": ["ver-package"]}
    mock_ver.side_effect = PackageNotFoundError("ver-package")

    # Must not raise
    cli._log_runtime_env()

    # None of the error paths should produce a "  pkg: ver" line
    calls = [a for a, _ in mock_logger.debug.call_args_list]
    assert not any(a[0] == "Runtime deps: %s" for a in calls)


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="packages_distributions requires Python 3.11+",
)
@mock.patch("apprise.cli.NotificationManager")
@mock.patch("apprise.cli.logger")
def test_apprise_cli_runtime_env_no_packages_distributions(
    mock_logger, mock_mgr
):
    """
    CLI: _log_runtime_env() gracefully skips dep listing when
    packages_distributions() is missing (ImportError path).
    Simulates the Python < 3.11 scenario on Python 3.11+ by temporarily
    removing packages_distributions from importlib.metadata.
    """
    import importlib.metadata as _meta

    mock_logger.isEnabledFor.return_value = True

    class DepPlugin:
        enabled = True

        @staticmethod
        def runtime_deps():
            return ("somepkg",)

    mock_mgr.return_value = [{"plugin": {DepPlugin}}]

    # Temporarily hide packages_distributions to trigger the ImportError
    _pd = _meta.packages_distributions
    del _meta.packages_distributions
    try:
        cli._log_runtime_env()
    finally:
        _meta.packages_distributions = _pd

    # Env summary was still logged despite the missing function
    calls = [a for a, _ in mock_logger.debug.call_args_list]
    assert any(a[0] == "Apprise: %s" for a in calls)

    # No dep listing -- packages_distributions was unavailable
    assert not any(a[0] == "Runtime deps: %s" for a in calls)


# Remove this test when Python 3.9 support is dropped.
@pytest.mark.skipif(
    sys.version_info >= (3, 11),
    reason="packages_distributions exists on Python 3.11+",
)
@mock.patch("apprise.cli.NotificationManager")
@mock.patch("apprise.cli.logger")
def test_apprise_cli_runtime_env_py39_no_packages_distributions(
    mock_logger, mock_mgr
):
    """
    CLI: _log_runtime_env() gracefully skips dep listing on Python < 3.11
    where packages_distributions() is genuinely absent.
    """
    mock_logger.isEnabledFor.return_value = True

    class DepPlugin:
        enabled = True

        @staticmethod
        def runtime_deps():
            return ("somepkg",)

    mock_mgr.return_value = [{"plugin": {DepPlugin}}]

    # packages_distributions() absent natively -- no manipulation needed
    cli._log_runtime_env()

    # Env summary was still logged despite the missing function
    calls = [a for a, _ in mock_logger.debug.call_args_list]
    assert any(a[0] == "Apprise: %s" for a in calls)

    # No dep listing -- packages_distributions unavailable on Python < 3.11
    assert not any(a[0] == "Runtime deps: %s" for a in calls)


def test_apprise_cli_limit_option_in_help():
    """
    CLI: --limit (-L) appears in --help output
    """
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "--limit" in result.output
    assert "-L" in result.output


@mock.patch("requests.request")
def test_apprise_cli_notify_runtime_stat_log(mock_request):
    """
    CLI: right after notify() returns, a single DEBUG line reports how
    long it took and how the AppriseResult broke down (success/failed/
    timeout counts, plus the overall status by name -- PARTIAL or
    TIMEOUT show up there without needing a separate line).

    Only logger.debug itself is patched (not the whole logger object) --
    main() also reads logger.level/setLevel() during its own verbosity
    setup, which would break against a fully mocked logger.
    """
    response = mock.Mock()
    response.status_code = requests.codes.ok
    response.content = b""
    mock_request.return_value = response

    runner = CliRunner()
    with mock.patch.object(cli.logger, "debug") as mock_debug:
        result = runner.invoke(
            cli.main,
            ["-t", "title", "-b", "body", "json://good"],
        )
    assert result.exit_code == 0

    calls = [a for a, _ in mock_debug.call_args_list]
    assert any(
        a[0]
        == (
            "Finished in %.2fs. %d service(s) tried (%s): %d sent / "
            "%d failed / %d timed out."
        )
        # a[1] is the elapsed seconds float -- not asserted here, just
        # that it's present as the first substitution.
        and a[2:] == (1, "SUCCESS", 1, 0, 0)
        for a in calls
    )


@mock.patch("apprise.cli._force_exit")
@mock.patch("requests.request")
def test_apprise_cli_limit_option_times_out_service(
    mock_request, mock_force_exit
):
    """
    CLI: --limit (-L) caps how long a single notification may take,
    reporting the service as timed out and exiting 5.

    _force_exit() is mocked purely as a safety net: for real it calls
    os._exit(), which would otherwise end this test process itself --
    CliRunner.invoke() runs main() in-process, not as a subprocess, so
    os._exit() has no SystemExit for it to catch the way ctx.exit()
    normally provides. In practice it's never actually reached here:
    the service's own 0.2s delay finishes well within the default 5s
    grace period, so _wait_for_abandoned_calls() reports success on
    its own and main() falls through to its normal, catchable
    ctx.exit(status) -- see the assertion below confirming this.
    """
    import time

    def _slow_failure(*args, **kwargs):
        """Return a delayed HTTP failure to force the CLI timeout path."""
        time.sleep(0.2)
        response = mock.Mock()
        response.status_code = requests.codes.internal_server_error
        response.content = b""
        response.text = ""
        return response

    mock_request.side_effect = _slow_failure

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "title",
            "-b",
            "body",
            "--limit",
            "0.05",
            "json://good?retry=3",
        ],
    )

    # The only service dispatched timed out (no plain failure to take
    # priority over it -- see _aggregate_status in apprise/apprise.py),
    # so the overall result -- and thus this exit code -- is TIMEOUT (5)
    # rather than the generic FAILURE (1).
    # (The "timed out" diagnostic itself goes through Python logging,
    # not click.echo, so it isn't visible in CliRunner's captured
    # result.output -- it's covered directly in tests/test_retry_wait.py.)
    assert result.exit_code == AppriseResultStatus.TIMEOUT

    # The abandoned call's own 0.2s delay finished naturally well
    # within the default 5s grace period, so _wait_for_abandoned_calls()
    # already confirmed nothing was left running -- the hard-exit path
    # was never needed. This exit code is itself unambiguous proof the
    # TIMEOUT branch was taken (nothing else in main() produces it).
    mock_force_exit.assert_not_called()


@mock.patch("apprise.cli._force_exit")
@mock.patch("requests.request")
def test_apprise_cli_limit_option_hard_exit_when_call_still_running(
    mock_request, mock_force_exit
):
    """
    CLI: the counterpart to test_apprise_cli_limit_option_times_out_
    service above -- when the abandoned call is STILL genuinely running
    after the full grace period (not just briefly delayed), main()
    actually reaches _force_exit(), rather than falling through to a
    normal ctx.exit().

    CLI_TIMEOUT_EXIT_GRACE_SECONDS is shortened here purely so this
    test runs quickly; the service's own delay is longer than that
    shortened window, so _wait_for_abandoned_calls() genuinely times
    out instead of resolving on its own. _force_exit() is mocked so
    the real os._exit() call doesn't end this test process (see the
    sibling test's docstring for why).
    """
    import time

    def _slow_failure(*args, **kwargs):
        """Return a delayed HTTP failure to force the CLI timeout path."""
        time.sleep(0.5)
        response = mock.Mock()
        response.status_code = requests.codes.internal_server_error
        response.content = b""
        response.text = ""
        return response

    mock_request.side_effect = _slow_failure

    with mock.patch("apprise.cli.CLI_TIMEOUT_EXIT_GRACE_SECONDS", 0.05):
        runner = CliRunner()
        result = runner.invoke(
            cli.main,
            [
                "-t",
                "title",
                "-b",
                "body",
                "--limit",
                "0.05",
                "json://good?retry=3",
            ],
        )

    assert result.exit_code == AppriseResultStatus.TIMEOUT
    mock_force_exit.assert_called_once()
    assert mock_force_exit.call_args.args[1] == AppriseResultStatus.TIMEOUT


def test_wait_for_abandoned_calls_polls_full_grace_period():
    """_wait_for_abandoned_calls() polls in
    CLI_TIMEOUT_EXIT_POLL_INTERVAL increments (never a single lump
    sleep) and returns False once the full timeout elapses with
    _any_abandoned_calls_still_running() still reporting True
    throughout.
    """
    with (
        mock.patch("apprise.cli.time.sleep") as mock_sleep,
        mock.patch(
            "apprise.cli._any_abandoned_calls_still_running",
            return_value=True,
        ) as mock_still_running,
    ):
        result = cli._wait_for_abandoned_calls(
            cli.CLI_TIMEOUT_EXIT_GRACE_SECONDS
        )

    assert result is False
    assert mock_still_running.called
    total_slept = sum(call.args[0] for call in mock_sleep.call_args_list)
    assert total_slept == pytest.approx(cli.CLI_TIMEOUT_EXIT_GRACE_SECONDS)
    for call in mock_sleep.call_args_list:
        assert call.args[0] <= cli.CLI_TIMEOUT_EXIT_POLL_INTERVAL


def test_wait_for_abandoned_calls_logs_service_descriptions_at_debug():
    """_wait_for_abandoned_calls() logs which specific still-running
    service(s) it's waiting on, once, at DEBUG level only -- so this
    stays out of default-verbosity output even though the url() is
    already privacy-masked by _abandoned_call_descriptions()."""
    with (
        mock.patch("apprise.cli.time.sleep"),
        mock.patch(
            "apprise.cli._any_abandoned_calls_still_running",
            return_value=False,
        ),
        mock.patch(
            "apprise.cli._abandoned_call_descriptions",
            return_value=["dummy (dummy://masked@host)"],
        ),
        mock.patch("apprise.cli.logger.debug") as mock_debug,
    ):
        cli._wait_for_abandoned_calls(cli.CLI_TIMEOUT_EXIT_GRACE_SECONDS)

    first_call_message = mock_debug.call_args_list[0].args
    assert "dummy (dummy://masked@host)" in first_call_message


def test_wait_for_abandoned_calls_exits_early_when_calls_finish():
    """_wait_for_abandoned_calls() returns True as soon as
    _any_abandoned_calls_still_running() reports False, rather than
    always waiting out the full grace period -- the whole point of
    polling instead of a single fixed sleep.
    """
    # "Still running" for the first two checks, then finished -- so
    # only 2 short sleeps happen instead of the full grace period.
    with (
        mock.patch("apprise.cli.time.sleep") as mock_sleep,
        mock.patch(
            "apprise.cli._any_abandoned_calls_still_running",
            side_effect=[True, True, False],
        ) as mock_still_running,
    ):
        result = cli._wait_for_abandoned_calls(
            cli.CLI_TIMEOUT_EXIT_GRACE_SECONDS
        )

    assert result is True
    assert mock_still_running.call_count == 3
    assert mock_sleep.call_count == 2
    for call in mock_sleep.call_args_list:
        assert call.args[0] == cli.CLI_TIMEOUT_EXIT_POLL_INTERVAL


def test_wait_for_abandoned_calls_finishes_right_as_grace_period_ends():
    """A final post-loop check can catch work that just finished."""
    with (
        mock.patch("apprise.cli.time.sleep"),
        mock.patch(
            "apprise.cli._any_abandoned_calls_still_running",
            # Four in-loop polls still report running. The final check
            # sees that the abandoned work has just finished.
            side_effect=[True, True, True, True, False],
        ) as mock_still_running,
    ):
        result = cli._wait_for_abandoned_calls(1.0)

    assert result is True
    assert mock_still_running.call_count == 5


def test_force_exit_sequence():
    """_force_exit() unconditionally flushes every service's
    persistent store (AUTO mode only writes on-demand, and os._exit()
    skips the garbage-collection that would normally trigger it),
    flushes logging/stdio, and only then forces the process to end via
    os._exit() with the given status -- no polling of any kind, since
    _wait_for_abandoned_calls() having already reported "still running"
    is a precondition for this being called at all.

    Every external effect is mocked directly (not through the CLI) so
    this asserts the full sequence in isolation, without actually
    ending this test process.
    """
    a = Apprise()
    services = [mock.Mock(spec=NotifyBase) for _ in range(3)]
    for service in services:
        a.add(service)

    with (
        mock.patch("apprise.cli.logging.shutdown") as mock_shutdown,
        mock.patch("apprise.cli.sys.stdout.flush") as mock_stdout_flush,
        mock.patch("apprise.cli.sys.stderr.flush") as mock_stderr_flush,
        mock.patch("apprise.cli.os._exit") as mock_os_exit,
    ):
        cli._force_exit(a, AppriseResultStatus.TIMEOUT)

    for service in services:
        service.flush_store.assert_called_once()
    mock_shutdown.assert_called_once()
    mock_stdout_flush.assert_called_once()
    mock_stderr_flush.assert_called_once()
    mock_os_exit.assert_called_once_with(AppriseResultStatus.TIMEOUT)


def test_force_exit_flush_failure_does_not_skip_others():
    """A failing flush_store() must never prevent the hard exit below,
    NOR stop the remaining services from getting their own chance to
    flush -- one bad store shouldn't cost every other one its own
    flush. The broken service is deliberately added FIRST here so its
    failure has to happen before the good one is ever reached.
    """
    a = Apprise()
    broken_service = mock.Mock(spec=NotifyBase)
    broken_service.flush_store.side_effect = RuntimeError("disk full")
    ok_service = mock.Mock(spec=NotifyBase)
    a.add(broken_service)
    a.add(ok_service)

    with (
        mock.patch("apprise.cli.logging.shutdown") as mock_shutdown,
        mock.patch("apprise.cli.os._exit") as mock_os_exit,
    ):
        cli._force_exit(a, AppriseResultStatus.TIMEOUT)

    # The service after the broken one in iteration order still got
    # its own flush attempt.
    ok_service.flush_store.assert_called_once()
    mock_os_exit.assert_called_once_with(AppriseResultStatus.TIMEOUT)
    # logging.shutdown() is unrelated to the failing store and should
    # still run normally afterward.
    mock_shutdown.assert_called_once()


def test_force_exit_reaches_exit_despite_logging_failure():
    """os._exit() must still run even when logging.shutdown() itself
    raises -- there is nothing reliable left to log to at that point,
    so the failure is swallowed rather than reported. sys.stdout/
    stderr.flush() are independently guarded too, so logging.shutdown()
    failing must not stop them from still being attempted.
    """
    a = Apprise()
    service = mock.Mock(spec=NotifyBase)
    a.add(service)

    with (
        mock.patch(
            "apprise.cli.logging.shutdown",
            side_effect=RuntimeError("logging is broken"),
        ),
        mock.patch("apprise.cli.sys.stdout.flush") as mock_stdout_flush,
        mock.patch("apprise.cli.sys.stderr.flush") as mock_stderr_flush,
        mock.patch("apprise.cli.os._exit") as mock_os_exit,
    ):
        cli._force_exit(a, AppriseResultStatus.TIMEOUT)

    service.flush_store.assert_called_once()
    mock_stdout_flush.assert_called_once()
    mock_stderr_flush.assert_called_once()
    mock_os_exit.assert_called_once_with(AppriseResultStatus.TIMEOUT)


def test_apprise_cli_limit_option_negative_value_errors():
    """
    CLI: --limit (-L) rejects a negative value the same way notify()
    and AppriseAsset(service_timeout=...) do.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        ["-t", "title", "-b", "body", "--limit", "-5", "json://good"],
    )
    assert result.exit_code != 0


def test_apprise_cli_service_limit_option_in_help():
    """
    CLI: --service-limit (-SL) appears in --help output
    """
    runner = CliRunner()
    result = runner.invoke(cli.main, ["--help"])
    assert result.exit_code == 0
    assert "--service-limit" in result.output
    assert "-SL" in result.output


def test_apprise_cli_service_limit_option_negative_value_errors():
    """
    CLI: --service-limit (-SL) rejects a negative value the same way
    AppriseAsset(service_timeout=...) does.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "title",
            "-b",
            "body",
            "--service-limit",
            "-5",
            "json://good",
        ],
    )
    assert result.exit_code != 0


@mock.patch("apprise.cli.AppriseAsset")
@mock.patch("requests.request")
def test_apprise_cli_service_limit_option_passed_to_asset(
    mock_request, mock_asset_cls
):
    """
    CLI: --service-limit (-SL), when specified, is passed into
    AppriseAsset(service_timeout=...) independently of --limit.
    """
    mock_asset_cls.side_effect = AppriseAsset
    mock_request.return_value = requests.Request()
    mock_request.return_value.status_code = requests.codes.ok

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "title",
            "-b",
            "body",
            "--limit",
            "30",
            "--service-limit",
            "5",
            "json://localhost",
        ],
    )
    assert result.exit_code == 0

    # --service-limit is independently set on the AppriseAsset, no
    # matter what --limit was also set to.
    assert mock_asset_cls.call_args.kwargs.get("service_timeout") == 5.0


@mock.patch("apprise.cli.AppriseAsset")
@mock.patch("requests.request")
def test_apprise_cli_service_limit_option_omitted(
    mock_request, mock_asset_cls
):
    """
    CLI: when --service-limit is not specified, AppriseAsset() receives
    service_timeout=None -- its own built-in default remains in effect,
    even if --limit was specified.
    """
    mock_asset_cls.side_effect = AppriseAsset
    mock_request.return_value = requests.Request()
    mock_request.return_value.status_code = requests.codes.ok

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "-t",
            "title",
            "-b",
            "body",
            "--limit",
            "30",
            "json://localhost",
        ],
    )
    assert result.exit_code == 0
    assert mock_asset_cls.call_args.kwargs.get("service_timeout") is None
