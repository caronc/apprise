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

from inspect import cleandoc

# Disable logging for a cleaner testing output
import logging
import re
import threading
import types

import pytest

from apprise import Apprise, NotificationManager
from apprise.plugins import NotifyBase

logging.disable(logging.CRITICAL)

# Grant access to our Notification Manager Singleton
N_MGR = NotificationManager()


def test_notification_manager_general():
    """
    N_MGR: Notification Manager General testing

    """
    # Clear our set so we can test init calls
    N_MGR.unload_modules()
    assert isinstance(N_MGR.schemas(), list)
    assert len(N_MGR.schemas()) > 0
    N_MGR.unload_modules(disable_native=True)
    assert isinstance(N_MGR.schemas(), list)
    assert len(N_MGR.schemas()) == 0

    N_MGR.unload_modules()
    assert len(N_MGR) > 0

    N_MGR.unload_modules()
    iter(N_MGR)
    iter(N_MGR)

    N_MGR.unload_modules()
    assert bool(N_MGR) is False
    assert len(list(iter(N_MGR))) > 0
    assert bool(N_MGR)

    N_MGR.unload_modules()
    assert isinstance(N_MGR.plugins(), types.GeneratorType)
    assert len(list(N_MGR.plugins())) > 0
    N_MGR.unload_modules(disable_native=True)
    assert isinstance(N_MGR.plugins(), types.GeneratorType)
    assert len(list(N_MGR.plugins())) == 0
    N_MGR.unload_modules()
    assert isinstance(N_MGR["json"](host="localhost"), NotifyBase)
    N_MGR.unload_modules()
    assert "json" in N_MGR

    # Define our good:// url
    class DisabledNotification(NotifyBase):
        # Always disabled
        enabled = False

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support url() function
            return ""

    # Define our good:// url
    class GoodNotification(NotifyBase):

        secure_protocol = ("good", "goods")

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def notify(self, *args, **kwargs):
            # Pretend everything is okay
            return True

        def url(self, **kwargs):
            # Support url() function
            return ""

    N_MGR.unload_modules()
    assert N_MGR.add(GoodNotification)
    assert "good" in N_MGR
    assert "goods" in N_MGR
    assert "abcd" not in N_MGR
    assert "xyz" not in N_MGR

    N_MGR.unload_modules()
    assert N_MGR.add(GoodNotification, "abcd")
    assert "good" in N_MGR
    assert "goods" in N_MGR
    assert "abcd" in N_MGR
    assert "xyz" not in N_MGR

    N_MGR.unload_modules()
    assert N_MGR.add(GoodNotification, ["abcd", "xYz"])
    assert "good" in N_MGR
    assert "goods" in N_MGR
    assert "abcd" in N_MGR
    # Lower case
    assert "xyz" in N_MGR

    N_MGR.unload_modules()
    # Not going to work; schemas must be a list of string
    assert N_MGR.add(GoodNotification, object) is False

    N_MGR.unload_modules()
    with pytest.raises(KeyError):
        del N_MGR["good"]
    N_MGR["good"] = GoodNotification
    del N_MGR["good"]

    N_MGR.unload_modules()
    N_MGR["good"] = GoodNotification
    assert N_MGR["good"].enabled is True
    N_MGR.enable_only("json", "xml")
    assert N_MGR["good"].enabled is False
    assert N_MGR["json"].enabled is True
    assert N_MGR["jsons"].enabled is True
    assert N_MGR["xml"].enabled is True
    assert N_MGR["xmls"].enabled is True

    # Only two plugins are enabled
    assert len(list(N_MGR.plugins(include_disabled=False))) == 2

    N_MGR.enable_only("good")
    assert N_MGR["good"].enabled is True
    assert N_MGR["json"].enabled is False
    assert N_MGR["jsons"].enabled is False
    assert N_MGR["xml"].enabled is False
    assert N_MGR["xmls"].enabled is False

    assert len(list(N_MGR.plugins(include_disabled=False))) == 1

    N_MGR.unload_modules()
    N_MGR["disabled"] = DisabledNotification
    assert N_MGR["disabled"].enabled is False
    N_MGR.enable_only("disabled")
    # Can't enable items that aren't supposed to be:
    assert N_MGR["disabled"].enabled is False

    N_MGR["good"] = GoodNotification
    assert N_MGR["good"].enabled is True

    # You can't disable someething already disabled
    N_MGR.disable("disabled")
    assert N_MGR["disabled"].enabled is False

    N_MGR.unload_modules()
    N_MGR.enable_only("form", "xml")
    for schema in N_MGR.schemas(include_disabled=False):
        assert re.match(r"^(form|xml)s?$", schema, re.IGNORECASE) is not None

    N_MGR.unload_modules()
    assert N_MGR["form"].enabled is True
    assert N_MGR["xml"].enabled is True
    assert N_MGR["json"].enabled is True
    N_MGR.enable_only("form", "xml")
    assert N_MGR["form"].enabled is True
    assert N_MGR["xml"].enabled is True
    assert N_MGR["json"].enabled is False

    N_MGR.disable("invalid", "xml")
    assert N_MGR["form"].enabled is True
    assert N_MGR["xml"].enabled is False
    assert N_MGR["json"].enabled is False

    # Detect that our json object is enabled
    with pytest.raises(KeyError):
        # The below can not be indexed
        N_MGR["invalid"]

    N_MGR.unload_modules()
    N_MGR.disable("invalid", "xml")

    N_MGR.unload_modules()
    assert N_MGR["json"].enabled is True

    # Work with an empty module tree
    N_MGR.unload_modules(disable_native=True)
    with pytest.raises(KeyError):
        # The below can not be indexed
        N_MGR["good"]

    N_MGR.unload_modules()
    assert "hello" not in N_MGR
    assert "good" not in N_MGR
    assert "goods" not in N_MGR

    N_MGR["hello"] = GoodNotification
    assert "hello" in N_MGR
    assert "good" in N_MGR
    assert "goods" in N_MGR

    N_MGR.unload_modules()
    N_MGR["good"] = GoodNotification

    with pytest.raises(KeyError):
        # Can not assign the value again without getting a Conflict
        N_MGR["good"] = GoodNotification

    N_MGR.unload_modules()
    N_MGR.remove("good", "invalid")
    assert "good" not in N_MGR
    assert "goods" not in N_MGR


def test_notification_manager_module_loading(tmpdir):
    """
    N_MGR: Notification Manager Module Loading

    """

    # Handle loading modules twice (they gracefully handle not loading more in
    # memory then needed)
    N_MGR.load_modules()
    N_MGR.load_modules()

    #
    # Thread Testing
    #

    # This tests against a racing condition when the modules have not been
    # loaded.  When multiple instances of Apprise are all instantiated,
    # the loading of the modules will occur for each instance if detected
    # having not been previously done, this tests that we can dynamically
    # support the loading of modules once whe multiple instances to apprise
    # are instantiated.
    thread_count = 10

    def thread_test(result, no):
        """Load our apprise object with valid URLs and store our result."""
        apobj = Apprise()
        result[no] = (
            apobj.add("json://localhost")
            and apobj.add("form://localhost")
            and apobj.add("xml://localhost")
        )

    # Unload our modules
    N_MGR.unload_modules()

    # Prepare threads to load
    results = [None] * thread_count
    threads = [
        threading.Thread(target=thread_test, args=(results, no))
        for no in range(thread_count)
    ]

    # Verify we can safely load our modules in a thread safe environment
    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Verify we loaded our urls in all threads successfully
    for result in results:
        assert result is True


def test_notification_manager_decorators(tmpdir):
    """
    N_MGR: Notification Manager Decorator testing

    """

    # Prepare ourselves a file to work with
    notify_hook = tmpdir.mkdir("goodmodule").join("__init__.py")
    notify_hook.write(cleandoc("""
    from apprise.decorators import notify

    # We want to trigger on anyone who configures a call to clihook://
    @notify(on="clihooka")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        # A simple test - print to screen
        print("A {}: {} - {}".format(notify_type, title, body))

        # No return (so a return of None) get's translated to True

    # Define another in the same file; uppercase goes to lower
    @notify(on="CLIhookb")
    def mywrapper(body, title, notify_type, *args, **kwargs):
        # A simple test - print to screen
        print("B {}: {} - {}".format(notify_type, title, body))

        # No return (so a return of None) get's translated to True
    """))

    N_MGR.module_detection(str(notify_hook))

    assert "clihooka" in N_MGR
    assert "clihookb" in N_MGR
    N_MGR.unload_modules()
    assert "clihooka" not in N_MGR
    assert "clihookb" not in N_MGR

    N_MGR.module_detection(str(notify_hook))
    assert "clihooka" in N_MGR
    assert "clihookb" in N_MGR
    del N_MGR["clihookb"]
    assert "clihooka" in N_MGR
    assert "clihookb" not in N_MGR
    del N_MGR["clihooka"]
    assert "clihooka" not in N_MGR
    assert "clihookb" not in N_MGR

    # Prepare ourselves a file to work with
    notify_base = tmpdir.mkdir("plugins")
    notify_test = notify_base.join("NotifyTest.py")
    notify_test.write(cleandoc("""
    #
    # Bare Minimum Valid Object
    #
    from apprise.plugins import NotifyBase
    from apprise.common import NotifyType

    class NotifyTest(NotifyBase):

        service_name = 'Test'

        # The services URL
        service_url = 'https://github.com/caronc/apprise/'

        # Define our protocol
        secure_protocol = 'mytest'

        # A URL that takes you to the setup/help of the specific protocol
        setup_url = 'https://github.com/caronc/apprise/wiki/Notify_mytest'

        # Define object templates
        templates = (
            '{schema}://',
        )

        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        def send(self, body, title='', notify_type=NotifyType.INFO, **kwargs):
            return True

        def url(self):
            return 'mytest://'
    """))
    assert "mytest" not in N_MGR
    N_MGR.load_modules(path=str(notify_base))
    assert "mytest" in N_MGR
    del N_MGR["mytest"]
    assert "mytest" not in N_MGR

    assert "mytest" not in N_MGR
    N_MGR.load_modules(path=str(notify_base))

    # It's still not loaded because the path has already been scanned
    assert "mytest" not in N_MGR
    N_MGR.load_modules(path=str(notify_base), force=True)
    assert "mytest" in N_MGR

    # Double load will test section of code that prevents a notification
    # From reloading if previously already loaded
    N_MGR.load_modules(path=str(notify_base))
    # Our item is still loaded as expected
    assert "mytest" in N_MGR

    # Simple test to make sure we can handle duplicate entries loaded
    N_MGR.load_modules(path=str(notify_base), force=True)
    N_MGR.load_modules(path=str(notify_base), force=True)
